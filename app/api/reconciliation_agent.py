"""空运代理对账：复用费用登记台应收投影，独立维护结算状态。"""
from datetime import date
from io import BytesIO
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.api.financial_audit import build_air_financial_audits
from app.core.response import ResponseModel, success_response
from app.database import get_db
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.consignment_note import ConsignmentNote
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.schemas.financial_audit import AirFinancialAuditQuery, ReceivableResponse
from app.schemas.reconciliation_agent import (
    MAX_SOURCE_ID, AirSourceType, AgentBatchSettleRequest,
    AgentReconciliationExportRequest, AgentReconciliationItemResponse,
    AgentReconciliationListResponse, AgentReconciliationQuery,
)
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()


def _get_list_query(
    waybill_numbers: Optional[str] = Query(None, description="运单号，多个用英文逗号隔开"),
    flight_date_start: Optional[date] = Query(None, description="航班日期起始，包含当天"),
    flight_date_end: Optional[date] = Query(None, description="航班日期结束，包含当天"),
    airline: Optional[str] = Query(None, description="航司，如深航、南航；全部表示不限制"),
    financial_audit_status: Optional[int] = Query(None, ge=0, le=2, description="财务审核：0=未审，1=暂存，2=已审"),
    customer_name: Optional[str] = Query(None, description="客户名称，通常传客户ID"),
    settlement_status: Optional[int] = Query(None, ge=0, le=1, description="空运代理结算：0=未结算，1=已结算"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, description="每页数量"),
):
    # Validate at the HTTP parameter boundary: older FastAPI versions otherwise
    # let Pydantic model dependency errors escape as internal server errors.
    return AgentReconciliationQuery(
        waybill_numbers=waybill_numbers, flight_date_start=flight_date_start,
        flight_date_end=flight_date_end, airline=airline,
        financial_audit_status=financial_audit_status, customer_name=customer_name,
        settlement_status=settlement_status, page=page, pageSize=pageSize,
    )


async def _collect_items(query, db, current_user):
    if query.flight_date_start and query.flight_date_end and query.flight_date_start > query.flight_date_end:
        raise HTTPException(status_code=400, detail="航班日期开始不能晚于结束")
    # Do not page before applying agent-specific filters. One canonical projection
    # also keeps overrides, customer fees and total/profit calculations in sync.
    result = await build_air_financial_audits(
        AirFinancialAuditQuery(audit_status=2, financial_audit_status=query.financial_audit_status),
        db, current_user, paginate=False, allow_peer_without_departure_audit=True,
    )
    records = db.query(
        AirFinancialAuditData.id, AirFinancialAuditData.source_type, AirFinancialAuditData.source_id,
        AirFinancialAuditData.agent_settlement_status,
        AirFinancialAuditData.agent_settlement_auditor_name, AirFinancialAuditData.agent_settlement_time,
    ).all()
    fa_map = {
        (fa.source_type, str(fa.id if fa.source_id in (0, fa.id) else fa.source_id)): fa
        for fa in records
    }
    waybills = {w.strip() for w in (query.waybill_numbers or "").split(",") if w.strip()}
    items = []
    for row in result.data["items"]:
        receivable = dict(row["receivable"])
        # Source-backed fee-desk rows expose the default waybill at the top level;
        # preserve a financial override when one has been supplied.
        if receivable.get("waybill_number") is None:
            receivable["waybill_number"] = row["waybill_number"]
        fa = fa_map.get((row["source_type"], row["source_id"]))
        status = (fa.agent_settlement_status or 0) if fa else 0
        flight_date = receivable.get("flight_date") or ""
        airline = receivable.get("airline") or ""
        customer = receivable.get("customer_name") or ""
        if waybills and receivable.get("waybill_number") not in waybills:
            continue
        if query.flight_date_start and flight_date < query.flight_date_start.isoformat():
            continue
        if query.flight_date_end and flight_date > query.flight_date_end.isoformat():
            continue
        if query.airline and query.airline != "全部" and airline != query.airline:
            continue
        if query.customer_name and query.customer_name not in customer:
            continue
        if query.settlement_status is not None and status != query.settlement_status:
            continue
        items.append(AgentReconciliationItemResponse(
            **receivable,
            source_type=row["source_type"], source_id=row["source_id"],
            agent_settlement_status=status,
            agent_settlement_auditor_name=fa.agent_settlement_auditor_name if fa else None,
            agent_settlement_time=format_datetime_china(fa.agent_settlement_time) if fa and fa.agent_settlement_time else None,
            financial_audit_status=row["financial_audit_status"],
            financial_auditor_name=row["financial_auditor_name"],
            actual_customer_name=row["actual_customer_name"],
        ).model_dump())
    items.sort(key=lambda item: (item["flight_date"] or "", item["waybill_number"] or "", int(item["source_id"])), reverse=True)
    return items


@router.get("/air", summary="空运代理对账列表查询", response_model=ResponseModel[AgentReconciliationListResponse])
async def get_agent_reconciliation_list(
    query: AgentReconciliationQuery = Depends(_get_list_query),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    items = await _collect_items(query, db, current_user)
    start = (query.page - 1) * query.pageSize
    return success_response({
        "items": items[start:start + query.pageSize], "total": len(items),
        "page": query.page, "pageSize": query.pageSize,
    })


def _load_settlement_records(db, keys):
    """Lock sources before extensions to serialize first settlement, then validate all."""
    valid_keys = set()
    sources = (
        ("shenzhen_air", ShenzhenAirBookingExport, ShenzhenAirDepartureManualData, "booking_export_id"),
        ("china_southern_air", ChinaSouthernAirApprovalData, CsaDepartureManualData, "approval_data_id"),
        ("peer_air", ConsignmentNote, PeerAirDepartureManualData, "consignment_note_id"),
    )
    for source_type, main, manual, relation in sources:
        ids = sorted(source_id for kind, source_id in keys if kind == source_type)
        if not ids:
            continue
        if source_type == "peer_air":
            # Peer-air consignment notes enter the fee desk directly; the
            # departure extension is optional and is not a settlement gate.
            query = db.query(main.id).outerjoin(manual, main.id == getattr(manual, relation)).filter(
                main.id.in_(ids), main.transport_type == "0",
            )
        else:
            query = db.query(main.id).join(manual, main.id == getattr(manual, relation)).filter(
                main.id.in_(ids), manual.audit_status == 2,
            )
        valid_keys.update((source_type, row[0]) for row in query.order_by(main.id).with_for_update().all())

    predicates = []
    for source_type in ("shenzhen_air", "china_southern_air", "peer_air"):
        ids = [source_id for kind, source_id in keys if kind == source_type]
        if ids:
            predicates.append(and_(
                AirFinancialAuditData.source_type == source_type,
                or_(AirFinancialAuditData.source_id.in_(ids), AirFinancialAuditData.id.in_(ids)),
            ))
    rows = db.query(AirFinancialAuditData).filter(or_(*predicates)).order_by(
        AirFinancialAuditData.source_type, AirFinancialAuditData.source_id, AirFinancialAuditData.id,
    ).populate_existing().with_for_update().all()
    existing = {}
    for fa in rows:
        manual = fa.source_id in (0, fa.id)
        key = (fa.source_type, fa.id if manual else fa.source_id)
        if key in keys:
            existing[key] = fa
            if manual:
                valid_keys.add(key)
    if keys - valid_keys:
        raise HTTPException(status_code=404, detail="单据不存在或尚未通过业务审核")
    return existing


def _settle(db, keys, current_user):
    try:
        records = _load_settlement_records(db, keys)
        now = get_china_now()
        for source_type, source_id in sorted(keys):
            fa = records.get((source_type, source_id))
            if fa is None:
                fa = AirFinancialAuditData(source_type=source_type, source_id=source_id)
                db.add(fa)
            if fa.agent_settlement_status == 1:
                continue
            fa.agent_settlement_status = 1
            fa.agent_settlement_auditor_id = current_user.id
            fa.agent_settlement_auditor_name = current_user.name
            fa.agent_settlement_time = now
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="单据正在被其他操作更新，请刷新后重试") from exc
    except Exception:
        db.rollback()
        raise


@router.post("/air/{source_type}/{source_id}/settle", summary="确认结算空运代理对账")
def confirm_agent_settlement(
    source_type: AirSourceType,
    source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    _settle(db, {(source_type, source_id)}, current_user)
    return success_response(msg="确认结算成功")


@router.post("/air/{source_type}/{source_id}/cancel-settlement", summary="取消空运代理对账结算")
def cancel_agent_settlement(
    source_type: AirSourceType,
    source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    try:
        records = _load_settlement_records(db, {(source_type, source_id)})
        fa = records.get((source_type, source_id))
        if fa:
            fa.agent_settlement_status = 0
            fa.agent_settlement_auditor_id = None
            fa.agent_settlement_auditor_name = None
            fa.agent_settlement_time = None
        db.commit()
    except Exception:
        db.rollback()
        raise
    return success_response(msg="取消结算成功")


@router.post("/air/batch-settle", summary="批量确认结算空运代理对账")
def batch_confirm_agent_settlement(
    req: AgentBatchSettleRequest,
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    keys = {(item.source_type, int(item.source_id)) for item in req.items}
    if keys:
        _settle(db, keys, current_user)
    return success_response(msg=f"成功批量结算 {len(keys)} 条单据")


@router.post("/air/export", summary="导出空运代理对账列表（选中/批量）")
async def export_agent_reconciliation_list(
    req: AgentReconciliationExportRequest,
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    items = await _collect_items(req, db, current_user)
    if req.selected_items:
        keys = {(item.source_type, item.source_id) for item in req.selected_items}
        items = [item for item in items if (item["source_type"], item["source_id"]) in keys]
    if not items:
        raise HTTPException(status_code=400, detail="没有符合条件的数据可导出")

    columns = [("agent_settlement_status", "结算状态"), ("actual_customer_name", "客户公司名称")]
    columns.extend((name, field.description or name) for name, field in ReceivableResponse.model_fields.items())
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("空运代理对账记录")
    sheet.append(["序号"] + [label for _, label in columns])
    for index, item in enumerate(items, 1):
        values = []
        for name, _ in columns:
            value = item.get(name) or ""
            if name == "agent_settlement_status":
                value = "已结算" if item[name] == 1 else "未结算"
            # Force text cells so formulas cannot execute and negative amounts
            # remain intact, without adding visible apostrophes to user data.
            if isinstance(value, str):
                cell = WriteOnlyCell(sheet, value=value)
                cell.data_type = "s"
                value = cell
            values.append(value)
        sheet.append([index] + values)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = quote(f"空运代理对账列表_{get_china_now():%Y%m%d%H%M%S}.xlsx")
    return StreamingResponse(output, headers={
        "Content-Disposition": f"attachment; filename*=utf-8''{filename}",
    }, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
