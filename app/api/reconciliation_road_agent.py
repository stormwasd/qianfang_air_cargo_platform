"""汽运代理对账：读取汽运费用登记台的数据源，独立标记结算。"""
import json
import math
from io import BytesIO
from datetime import date
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from sqlalchemy import LargeBinary, String, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.response import ResponseModel, success_response
from app.database import get_db
from app.models.consignment_note import ConsignmentNote
from app.models.customer import Customer
from app.models.peer_road_manual_data import PeerRoadDepartureManualData
from app.schemas.reconciliation_road_agent import (
    MAX_SOURCE_ID, RoadAgentBatchSettleRequest, RoadAgentReceivableResponse,
    RoadAgentReconciliationExportRequest, RoadAgentReconciliationItemResponse,
    RoadAgentReconciliationListResponse, RoadAgentReconciliationQuery,
)
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()


def _get_list_query(
    date_start: Optional[date] = Query(None, description="托运日期开始，默认北京时间当天往前30天"),
    date_end: Optional[date] = Query(None, description="托运日期结束，默认北京时间当天"),
    customer_name: Optional[str] = Query(None, description="客户ID精确匹配或客户名称模糊搜索"),
    destination_city: Optional[str] = Query(None, description="目的城市模糊搜索"),
    settlement_status: Optional[int] = Query(None, ge=0, le=1, description="汽运代理结算状态：0=未结算，1=已结算；不传不限"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=200),
):
    dates = {key: value for key, value in (("date_start", date_start), ("date_end", date_end)) if value is not None}
    return RoadAgentReconciliationQuery(
        **dates, customer_name=customer_name, destination_city=destination_city,
        settlement_status=settlement_status, page=page, pageSize=pageSize,
    )


def _query_rows(query, db):
    if query.date_start and query.date_end and query.date_start > query.date_end:
        raise HTTPException(status_code=400, detail="托运日期开始不能晚于结束")
    # Reconciliation starts after fee-desk financial approval; business audit is retired.
    rows = db.query(ConsignmentNote, PeerRoadDepartureManualData, Customer.company_name).outerjoin(
        PeerRoadDepartureManualData,
        PeerRoadDepartureManualData.consignment_note_id == ConsignmentNote.id,
    ).outerjoin(
        Customer,
        # IDs require exact matching. Binary comparison avoids MySQL 1267 when
        # CAST uses the connection collation and the stored column uses another.
        # Do not compare as numbers: MySQL would also match values such as '7abc'.
        cast(cast(Customer.id, String), LargeBinary) == cast(ConsignmentNote.customer_name, LargeBinary),
    ).filter(
        ConsignmentNote.transport_type == "1",
        PeerRoadDepartureManualData.financial_audit_status == 2,
    )
    if query.date_start:
        rows = rows.filter(ConsignmentNote.consignment_date >= query.date_start)
    if query.date_end:
        rows = rows.filter(ConsignmentNote.consignment_date <= query.date_end)
    customer = (query.customer_name or "").strip()
    if customer:
        if customer.isdecimal():
            rows = rows.filter(ConsignmentNote.customer_name == customer)
        else:
            rows = rows.filter(or_(
                ConsignmentNote.customer_name.contains(customer, autoescape=True),
                Customer.company_name.contains(customer, autoescape=True),
            ))
    destination = (query.destination_city or "").strip()
    if destination:
        rows = rows.filter(ConsignmentNote.destination.contains(destination, autoescape=True))
    return rows


def _query_agent_rows(query, db):
    # The base query is also used by receivable reconciliation, whose settlement
    # state is independent. Apply this module's filter only in its own endpoints.
    rows = _query_rows(query, db)
    if query.settlement_status is not None:
        rows = rows.filter(
            func.coalesce(PeerRoadDepartureManualData.agent_settlement_status, 0)
            == query.settlement_status,
        )
    return rows


def _text(value):
    """Dynamic form numbers are returned as strings, without inventing missing values."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return str(value)


def _project_row(row):
    note, manual, company = row
    try:
        form = json.loads(note.form_data)
        if not isinstance(form, dict):
            raise ValueError("表单必须是对象")
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=500, detail=f"汽运托运书{note.id}的表单数据格式异常") from exc
    receivable = {name: _text(form.get(name)) for name in RoadAgentReceivableResponse.model_fields}
    # These normalized columns are populated by the existing fee-desk save API.
    receivable.update(
        transport_date=note.consignment_date.isoformat() if note.consignment_date else None,
        customer_name=note.customer_name,
        destination_city=note.destination,
    )
    return RoadAgentReconciliationItemResponse(
        **receivable, source_id=str(note.id), actual_customer_name=company or note.customer_name or "",
        agent_settlement_status=(manual.agent_settlement_status or 0) if manual else 0,
        agent_settlement_auditor_name=manual.agent_settlement_auditor_name if manual else None,
        agent_settlement_time=format_datetime_china(manual.agent_settlement_time) if manual and manual.agent_settlement_time else None,
    ).model_dump()


@router.get("/road", summary="汽运代理对账列表查询", response_model=ResponseModel[RoadAgentReconciliationListResponse])
def get_road_agent_reconciliation_list(
    query: RoadAgentReconciliationQuery = Depends(_get_list_query),
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    rows = _query_agent_rows(query, db)
    total = rows.count()
    rows = rows.order_by(ConsignmentNote.consignment_date.desc(), ConsignmentNote.id.desc()).offset(
        (query.page - 1) * query.pageSize,
    ).limit(query.pageSize).all()
    return success_response({
        "items": [_project_row(row) for row in rows], "total": total,
        "page": query.page, "pageSize": query.pageSize,
    })


def _set_settlement(db, source_ids, user, settled):
    if not source_ids:
        return
    try:
        # Lock sources before extensions in the same order for all operations.
        notes = db.query(ConsignmentNote.id).filter(
            ConsignmentNote.id.in_(source_ids), ConsignmentNote.transport_type == "1",
        ).order_by(ConsignmentNote.id).with_for_update().all()
        if {note.id for note in notes} != source_ids:
            raise HTTPException(status_code=404, detail="汽运托运书不存在或托运方式不是汽运")
        records = db.query(PeerRoadDepartureManualData).filter(
            PeerRoadDepartureManualData.consignment_note_id.in_(source_ids),
        ).order_by(PeerRoadDepartureManualData.consignment_note_id).populate_existing().with_for_update().all()
        by_note = {record.consignment_note_id: record for record in records}
        if settled and any(
            source_id not in by_note or by_note[source_id].financial_audit_status != 2 for source_id in source_ids
        ):
            raise HTTPException(status_code=400, detail="单据尚未通过财务审核，不能确认结算")
        now = get_china_now()
        for source_id in sorted(source_ids):
            record = by_note.get(source_id)
            if not record:
                continue  # Cancellation never creates an empty extension.
            if (record.agent_settlement_status or 0) == int(settled):
                continue
            record.agent_settlement_status = int(settled)
            record.agent_settlement_auditor_id = user.id if settled else None
            record.agent_settlement_auditor_name = user.name if settled else None
            record.agent_settlement_time = now if settled else None
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="单据正在被其他操作更新，请刷新后重试") from exc
    except Exception:
        db.rollback()
        raise


@router.post("/road/{source_id}/settle", summary="确认结算汽运代理对账")
def confirm_road_agent_settlement(
    source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    _set_settlement(db, {source_id}, current_user, True)
    return success_response(msg="确认结算成功")


@router.post("/road/{source_id}/cancel-settlement", summary="取消汽运代理对账结算")
def cancel_road_agent_settlement(
    source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    _set_settlement(db, {source_id}, current_user, False)
    return success_response(msg="取消结算成功")


@router.post("/road/batch-settle", summary="批量确认结算汽运代理对账")
def batch_confirm_road_agent_settlement(
    req: RoadAgentBatchSettleRequest,
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    source_ids = {int(item.source_id) for item in req.items}
    _set_settlement(db, source_ids, current_user, True)
    return success_response(msg=f"成功批量结算 {len(source_ids)} 条单据")


@router.post("/road/export", summary="导出汽运代理对账列表（选中/批量）")
def export_road_agent_reconciliation_list(
    req: RoadAgentReconciliationExportRequest,
    db: Session = Depends(get_db), current_user=Depends(get_current_active_user),
):
    rows = _query_agent_rows(req, db)
    if req.selected_items:
        rows = rows.filter(ConsignmentNote.id.in_({int(item.source_id) for item in req.selected_items}))
    rows = rows.order_by(ConsignmentNote.consignment_date.desc(), ConsignmentNote.id.desc())
    if rows.first() is None:
        raise HTTPException(status_code=400, detail="没有符合条件的数据可导出")
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("汽运代理对账")
    columns = [(name, field.description) for name, field in RoadAgentReceivableResponse.model_fields.items()]
    sheet.append(["序号", "结算状态"] + [label for _, label in columns])
    for index, row in enumerate(rows.yield_per(500), 1):
        item = _project_row(row)
        values = [index, "已结算" if item["agent_settlement_status"] == 1 else "未结算"]
        for name, _ in columns:
            value = item["actual_customer_name"] if name == "customer_name" else item[name]
            if isinstance(value, str):
                cell = WriteOnlyCell(sheet, value=value)
                cell.data_type = "s"
                value = cell
            values.append(value)
        sheet.append(values)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = quote(f"汽运代理对账列表_{get_china_now():%Y%m%d%H%M%S}.xlsx")
    return StreamingResponse(output, headers={
        "Content-Disposition": f"attachment; filename*=utf-8''{filename}",
    }, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
