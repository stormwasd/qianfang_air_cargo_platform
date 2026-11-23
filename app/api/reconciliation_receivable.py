"""应收对账：复用费用登记台投影，隔离五个模块及原有应付结算状态。"""
from dataclasses import dataclass
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Callable, Optional, Type
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.api.financial_audit import build_air_financial_audits
from app.api.reconciliation_agent import _load_settlement_records
from app.api.reconciliation_road_agent import _project_row, _query_rows
from app.core.response import ResponseModel, success_response
from app.database import get_db
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.consignment_note import ConsignmentNote
from app.models.peer_road_manual_data import PeerRoadDepartureManualData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.schemas.financial_audit import AirFinancialAuditQuery, ReceivableResponse
from app.schemas.reconciliation_agent import MAX_SOURCE_ID, AgentBatchSettleRequest, AirSourceType
from app.schemas.reconciliation_receivable import (
    AirReceivableItem, AirReceivableList, AirReceivableQuery,
    AirlineReceivableExport, AirlineReceivableQuery,
    DeliveryReceivableExport, DeliveryReceivableQuery,
    PickupReceivableExport, PickupReceivableQuery,
    RoadReceivableExport, RoadReceivableItem, RoadReceivableList, RoadReceivableQuery,
)
from app.schemas.reconciliation_road_agent import RoadAgentBatchSettleRequest, RoadAgentReceivableResponse
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()


@dataclass(frozen=True)
class AirModule:
    path: str
    label: str
    state: str
    query_dependency: Callable
    export_model: Type[BaseModel]


def _common_query(
    waybill_numbers: Optional[str] = Query(None),
    flight_date_start: Optional[date] = Query(None),
    flight_date_end: Optional[date] = Query(None),
    financial_audit_status: Optional[int] = Query(None, ge=0, le=2, description="仅查询财务已审2；不传或传2返回已审，传0/1返回空列表"),
    customer_name: Optional[str] = Query(None),
    settlement_status: Optional[int] = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1), pageSize: int = Query(10, ge=1, le=200),
):
    return AirReceivableQuery(
        waybill_numbers=waybill_numbers, flight_date_start=flight_date_start,
        flight_date_end=flight_date_end, financial_audit_status=financial_audit_status,
        customer_name=customer_name, settlement_status=settlement_status, page=page, pageSize=pageSize,
    )


def _airline_query(common=Depends(_common_query), airline: Optional[str] = Query(None)):
    return AirlineReceivableQuery(**common.model_dump(), airline=airline)


def _pickup_query(common=Depends(_common_query), actual_flight_number: Optional[str] = Query(None),
                  pickup_company: Optional[str] = Query(None)):
    return PickupReceivableQuery(**common.model_dump(), actual_flight_number=actual_flight_number,
                                 pickup_company=pickup_company)


def _delivery_query(common=Depends(_common_query), actual_flight_number: Optional[str] = Query(None),
                    delivery_company: Optional[str] = Query(None)):
    return DeliveryReceivableQuery(**common.model_dump(), actual_flight_number=actual_flight_number,
                                   delivery_company=delivery_company)


AIR_MODULES = (
    AirModule("airline", "航司对账", "receivable_airline_settlement", _airline_query, AirlineReceivableExport),
    AirModule("pickup", "提货单位对账", "receivable_pickup_settlement", _pickup_query, PickupReceivableExport),
    AirModule("delivery", "派送单位对账", "receivable_delivery_settlement", _delivery_query, DeliveryReceivableExport),
    AirModule("air-agent", "空运代理对账", "receivable_agent_settlement", _airline_query, AirlineReceivableExport),
)


def _settlement_values(record, prefix):
    timestamp = getattr(record, prefix + "_time") if record else None
    return {
        "settlement_status": (getattr(record, prefix + "_status") or 0) if record else 0,
        "settlement_auditor_name": getattr(record, prefix + "_auditor_name") if record else None,
        "settlement_time": format_datetime_china(timestamp) if timestamp else None,
    }


def _nonzero(value):
    try:
        amount = Decimal(str(value))
        return amount.is_finite() and amount != 0
    except (InvalidOperation, ValueError):
        return False


def _belongs_to_module(module, row):
    if module.path == "pickup":
        return bool((row["payable"].get("door_pickup_company") or "").strip())
    if module.path == "delivery":
        return bool((row["payable"].get("delivery_company") or "").strip()) or any(
            _nonzero(row["receivable"].get(key)) for key in ("airport_pickup_fee", "delivery_fee")
        )
    return True


def _actual_flights(db, rows):
    """Batch source metadata, avoiding a database query for each projected bill."""
    flights = {}
    for kind, model, fallback in (
        ("shenzhen_air", ShenzhenAirBookingExport, ShenzhenAirBookingExport.billing_flight),
        ("china_southern_air", ChinaSouthernAirApprovalData, None),
    ):
        ids = [int(row["source_id"]) for row in rows if row["source_type"] == kind]
        columns = [model.id, model.actual_flight]
        if fallback is not None:
            columns.append(fallback)
        for start in range(0, len(ids), 500):
            for record in db.query(*columns).filter(model.id.in_(ids[start:start + 500])).all():
                flights[(kind, str(record[0]))] = record[1] or (record[2] if fallback is not None else None)
    ids = [int(row["source_id"]) for row in rows if row["source_type"] == "peer_air"]
    for start in range(0, len(ids), 500):
        for note in db.query(ConsignmentNote.id, ConsignmentNote.form_data).filter(
            ConsignmentNote.id.in_(ids[start:start + 500]), ConsignmentNote.transport_type == "0",
        ).all():
            try:
                form = json.loads(note.form_data or "{}")
            except (ValueError, TypeError):
                form = {}
            value = form.get("actual_flight") if isinstance(form, dict) else None
            if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                flights[("peer_air", str(note.id))] = str(value)
    return flights


async def collect_air_items(module, query, db, user):
    if query.flight_date_start and query.flight_date_end and query.flight_date_start > query.flight_date_end:
        raise HTTPException(status_code=400, detail="航班日期开始不能晚于结束")
    result = await build_air_financial_audits(
        AirFinancialAuditQuery(financial_audit_status=2),
        db, user, paginate=False, allow_peer_without_departure_audit=True,
    )
    columns = [AirFinancialAuditData.id, AirFinancialAuditData.source_type, AirFinancialAuditData.source_id]
    columns += [getattr(AirFinancialAuditData, module.state + suffix)
                for suffix in ("_status", "_auditor_name", "_time")]
    records = db.query(*columns).all()
    by_source = {(row.source_type, str(row.id if row.source_id in (0, row.id) else row.source_id)): row
                 for row in records}
    rows = result.data["items"]
    flights = _actual_flights(db, rows)
    waybills = {value.strip() for value in (query.waybill_numbers or "").split(",") if value.strip()}
    items = []
    for row in rows:
        if query.financial_audit_status is not None and row["financial_audit_status"] != query.financial_audit_status:
            continue
        if not _belongs_to_module(module, row):
            continue
        receivable = dict(row["receivable"])
        if receivable.get("waybill_number") is None:
            receivable["waybill_number"] = row["waybill_number"]
        state = _settlement_values(by_source.get((row["source_type"], row["source_id"])), module.state)
        flight_date = receivable.get("flight_date") or ""
        if waybills and receivable.get("waybill_number") not in waybills:
            continue
        if (query.flight_date_start or query.flight_date_end) and not flight_date:
            continue
        if query.flight_date_start and flight_date < query.flight_date_start.isoformat():
            continue
        if query.flight_date_end and flight_date > query.flight_date_end.isoformat():
            continue
        if getattr(query, "airline", None) not in (None, "", "全部", receivable.get("airline")):
            continue
        if query.customer_name and query.customer_name not in (receivable.get("customer_name") or ""):
            continue
        if query.settlement_status is not None and query.settlement_status != state["settlement_status"]:
            continue
        actual_flight = flights.get((row["source_type"], row["source_id"])) or receivable.get("flight_number")
        pickup = row["payable"].get("door_pickup_company")
        delivery = row["payable"].get("delivery_company")
        if getattr(query, "actual_flight_number", None) and query.actual_flight_number not in (actual_flight or ""):
            continue
        if getattr(query, "pickup_company", None) and query.pickup_company not in (pickup or ""):
            continue
        if getattr(query, "delivery_company", None) and query.delivery_company not in (delivery or ""):
            continue
        items.append(AirReceivableItem(
            **receivable, **state, source_type=row["source_type"], source_id=row["source_id"],
            financial_audit_status=row["financial_audit_status"],
            financial_auditor_name=row["financial_auditor_name"], actual_customer_name=row["actual_customer_name"],
            actual_flight_number=actual_flight, pickup_company=pickup, delivery_company=delivery,
        ).model_dump())
    items.sort(key=lambda item: (item["flight_date"] or "", item["waybill_number"] or "", int(item["source_id"])), reverse=True)
    return items


def _update_settlement(record, prefix, user, settled, now):
    # Preserve the original actor/time on retries. Cancellation also clears stale metadata.
    if settled and getattr(record, prefix + "_status") == 1:
        return
    setattr(record, prefix + "_status", int(settled))
    setattr(record, prefix + "_auditor_id", user.id if settled else None)
    setattr(record, prefix + "_auditor_name", user.name if settled else None)
    setattr(record, prefix + "_time", now if settled else None)


async def set_air_settlement(module, keys, db, user, settled):
    if not keys:
        return
    try:
        records = _load_settlement_records(db, keys, require_financial_audit=settled)
        if settled and module.path in ("pickup", "delivery"):
            # Validate module membership against the same final projection as the list.
            eligible = {(row["source_type"], int(row["source_id"])) for row in await collect_air_items(
                module, AirReceivableQuery(), db, user,
            )}
            if keys - eligible:
                raise HTTPException(status_code=400, detail="单据不属于当前应收对账模块")
        now = get_china_now()
        for kind, source_id in sorted(keys):
            record = records.get((kind, source_id))
            if record is None:
                continue  # Cancellation never creates an empty extension.
            _update_settlement(record, module.state, user, settled, now)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="单据正在被其他操作更新，请刷新后重试") from exc
    except Exception:
        db.rollback()
        raise


def _excel_response(items, columns, label):
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(label)
    sheet.append(["序号"] + [description for _, description in columns])
    for index, item in enumerate(items, 1):
        values = [index]
        for name, _ in columns:
            value = item.get(name)
            if name == "settlement_status":
                value = "已结算" if value == 1 else "未结算"
            if isinstance(value, str):
                cell = WriteOnlyCell(sheet, value=value)
                cell.data_type = "s"
                value = cell
            values.append(value)
        sheet.append(values)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    filename = quote(f"应收{label}_{get_china_now():%Y%m%d%H%M%S}.xlsx")
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename*=utf-8''{filename}"})


def _register_air_routes(module):
    """Register explicit module contracts; shared internals keep all four behaviors aligned."""
    module_router = APIRouter(prefix=f"/{module.path}", tags=[f"应收对账-{module.label}"])
    export_model = module.export_model

    @module_router.get("/air", summary=f"应收{module.label}列表", response_model=ResponseModel[AirReceivableList])
    async def list_items(query=Depends(module.query_dependency), db: Session = Depends(get_db),
                         user=Depends(get_current_active_user)):
        items = await collect_air_items(module, query, db, user)
        start = (query.page - 1) * query.pageSize
        return success_response({"items": items[start:start + query.pageSize], "total": len(items),
                                 "page": query.page, "pageSize": query.pageSize})

    @module_router.post("/air/{source_type}/{source_id}/settle", summary=f"确认应收{module.label}结算")
    async def settle(source_type: AirSourceType, source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
                     db: Session = Depends(get_db), user=Depends(get_current_active_user)):
        await set_air_settlement(module, {(source_type, source_id)}, db, user, True)
        return success_response(msg="确认结算成功")

    @module_router.post("/air/{source_type}/{source_id}/cancel-settlement", summary=f"取消应收{module.label}结算")
    async def cancel(source_type: AirSourceType, source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID),
                     db: Session = Depends(get_db), user=Depends(get_current_active_user)):
        await set_air_settlement(module, {(source_type, source_id)}, db, user, False)
        return success_response(msg="取消结算成功")

    @module_router.post("/air/batch-settle", summary=f"批量确认应收{module.label}结算")
    async def batch(req: AgentBatchSettleRequest, db: Session = Depends(get_db),
                    user=Depends(get_current_active_user)):
        keys = {(item.source_type, int(item.source_id)) for item in req.items}
        await set_air_settlement(module, keys, db, user, True)
        return success_response(msg=f"成功结算{len(keys)}条单据")

    @module_router.post("/air/export", summary=f"导出应收{module.label}")
    async def export(req: export_model, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
        items = await collect_air_items(module, req, db, user)
        if req.selected_items:
            selected = {(item.source_type, item.source_id) for item in req.selected_items}
            items = [row for row in items if (row["source_type"], row["source_id"]) in selected]
        if not items:
            raise HTTPException(status_code=400, detail="没有符合条件的数据可导出")
        columns = [("source_type", "来源类型"), ("source_id", "来源ID"), ("settlement_status", "结算状态"),
                   ("settlement_auditor_name", "结算操作人"), ("settlement_time", "结算时间"),
                   ("financial_audit_status", "财务审核状态"), ("actual_customer_name", "客户公司名称"),
                   ("actual_flight_number", "实走航班号"), ("pickup_company", "上门提货单位"),
                   ("delivery_company", "派送单位")]
        columns += [(name, field.description or name) for name, field in ReceivableResponse.model_fields.items()]
        return _excel_response(items, columns, module.label)

    router.include_router(module_router)


for _module in AIR_MODULES:
    _register_air_routes(_module)


def _road_query(
    date_start: Optional[date] = Query(None), date_end: Optional[date] = Query(None),
    customer_name: Optional[str] = Query(None), destination_city: Optional[str] = Query(None),
    settlement_status: Optional[int] = Query(None, ge=0, le=1),
    page: int = Query(1, ge=1), pageSize: int = Query(10, ge=1, le=200),
):
    dates = {key: value for key, value in (("date_start", date_start), ("date_end", date_end)) if value is not None}
    return RoadReceivableQuery(**dates, customer_name=customer_name, destination_city=destination_city,
                               settlement_status=settlement_status, page=page, pageSize=pageSize)


def _road_rows(query, db):
    rows = _query_rows(query, db)
    if query.settlement_status is not None:
        rows = rows.filter(func.coalesce(PeerRoadDepartureManualData.receivable_agent_settlement_status, 0)
                           == query.settlement_status)
    return rows


def _road_item(row):
    # The established projection owns dynamic form normalization; discard its payable state.
    data = _project_row(row)
    data.update(_settlement_values(row[1], "receivable_agent_settlement"))
    return RoadReceivableItem.model_validate(data).model_dump()


road_router = APIRouter(prefix="/road-agent", tags=["应收对账-汽运代理对账"])


@road_router.get("/road", summary="应收汽运代理对账列表", response_model=ResponseModel[RoadReceivableList])
def list_road_items(query=Depends(_road_query), db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    rows = _road_rows(query, db)
    total = rows.count()
    page_rows = rows.order_by(ConsignmentNote.consignment_date.desc(), ConsignmentNote.id.desc()).offset(
        (query.page - 1) * query.pageSize,
    ).limit(query.pageSize).all()
    return success_response({"items": [_road_item(row) for row in page_rows], "total": total,
                             "page": query.page, "pageSize": query.pageSize})


def set_road_settlement(ids, db, user, settled):
    if not ids:
        return
    try:
        notes = db.query(ConsignmentNote.id).filter(
            ConsignmentNote.id.in_(ids), ConsignmentNote.transport_type == "1",
        ).order_by(ConsignmentNote.id).with_for_update().all()
        if {row.id for row in notes} != ids:
            raise HTTPException(status_code=404, detail="汽运托运书不存在或托运方式不是汽运")
        records = db.query(PeerRoadDepartureManualData).filter(
            PeerRoadDepartureManualData.consignment_note_id.in_(ids),
        ).order_by(PeerRoadDepartureManualData.consignment_note_id).populate_existing().with_for_update().all()
        by_note = {record.consignment_note_id: record for record in records}
        if settled and any(
            source_id not in by_note or by_note[source_id].financial_audit_status != 2 for source_id in ids
        ):
            raise HTTPException(status_code=400, detail="单据尚未通过财务审核，不能确认结算")
        now = get_china_now()
        for source_id in sorted(ids):
            record = by_note.get(source_id)
            if record is None:
                continue  # Confirmation already validated every financial record.
            _update_settlement(record, "receivable_agent_settlement", user, settled, now)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="单据正在被其他操作更新，请刷新后重试") from exc
    except Exception:
        db.rollback()
        raise


@road_router.post("/road/{source_id}/settle", summary="确认应收汽运代理对账结算")
def settle_road(source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID), db: Session = Depends(get_db),
                user=Depends(get_current_active_user)):
    set_road_settlement({source_id}, db, user, True)
    return success_response(msg="确认结算成功")


@road_router.post("/road/{source_id}/cancel-settlement", summary="取消应收汽运代理对账结算")
def cancel_road(source_id: int = Path(..., gt=0, le=MAX_SOURCE_ID), db: Session = Depends(get_db),
                user=Depends(get_current_active_user)):
    set_road_settlement({source_id}, db, user, False)
    return success_response(msg="取消结算成功")


@road_router.post("/road/batch-settle", summary="批量确认应收汽运代理对账结算")
def batch_road(req: RoadAgentBatchSettleRequest, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    ids = {int(item.source_id) for item in req.items}
    set_road_settlement(ids, db, user, True)
    return success_response(msg=f"成功结算{len(ids)}条单据")


@road_router.post("/road/export", summary="导出应收汽运代理对账")
def export_road(req: RoadReceivableExport, db: Session = Depends(get_db), user=Depends(get_current_active_user)):
    rows = _road_rows(req, db)
    if req.selected_items:
        rows = rows.filter(ConsignmentNote.id.in_({int(item.source_id) for item in req.selected_items}))
    rows = rows.order_by(ConsignmentNote.consignment_date.desc(), ConsignmentNote.id.desc())
    if rows.first() is None:
        raise HTTPException(status_code=400, detail="没有符合条件的数据可导出")
    columns = [("source_id", "来源ID"), ("settlement_status", "结算状态"),
               ("settlement_auditor_name", "结算操作人"), ("settlement_time", "结算时间"),
               ("actual_customer_name", "客户公司名称")]
    columns += [(name, field.description or name) for name, field in RoadAgentReceivableResponse.model_fields.items()]
    return _excel_response((_road_item(row) for row in rows.yield_per(500)), columns, "汽运代理对账")


router.include_router(road_router)
