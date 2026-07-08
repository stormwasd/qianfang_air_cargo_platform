from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Dict, Any, Optional
import json
import re
from datetime import date, datetime

from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.utils.snowflake import generate_id

# 导入所有相关模型
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.consignment_note import ConsignmentNote
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.customer import Customer
from app.models.waybill import Waybill

# 导入 Schemas
from app.schemas.financial_audit import (
    AirFinancialAuditQuery,
    AirFinancialAuditDataUpsert,
    AirFinancialAuditCreateRequest,
    AirFinancialAuditItemResponse,
    PayableResponse,
    ReceivableResponse,
    ExtraData
)
from app.utils.airport_code_mapper import get_airport_name_by_code
from app.utils.pickup_phone_mapper import pickup_phone_mapper

SETTLEMENT_CYCLE_MAP = {
    1: "周结",
    2: "半月结",
    3: "月结",
    4: "现结"
}

router = APIRouter()

# ----------------- Helper Functions -----------------

def safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def safe_int(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    try:
        cleaned = re.sub(r'[^\d\-]', '', str(val))
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0

def safe_str(val: Any) -> str:
    return str(val) if val is not None else ""

def format_decimal(val: float) -> str:
    return f"{val:.2f}"

def parse_csa_qty_weight(billing_qty: str):
    if not billing_qty:
        return "", ""
    parts = [p.strip() for p in billing_qty.split('/')]
    pieces = parts[0] if len(parts) > 0 else ""
    weight = parts[1] if len(parts) > 1 else ""
    return pieces, weight

def parse_csa_flight_info(flight_info: str):
    if not flight_info:
        return "", "", "", ""
    parts = [p.strip() for p in flight_info.split('/')]
    flight_number = parts[0] if len(parts) > 0 else ""
    flight_date = parts[1].replace('/', '-') if len(parts) > 1 else ""
    route_str = parts[2] if len(parts) > 2 else ""
    origin, destination = "", ""
    if route_str and '-' in route_str:
        route_parts = [r.strip() for r in route_str.split('-')]
        origin = route_parts[0] if len(route_parts) > 0 else ""
        destination = route_parts[1] if len(route_parts) > 1 else ""
    return flight_number, flight_date, origin, destination

def parse_consignee_phone_name(consignee: str):
    if not consignee:
        return "", ""
    match = re.search(r'([0-9\-+]{7,20})$', consignee.strip())
    if match:
        phone = match.group(1)
        name = consignee.replace(phone, "").strip()
        return phone, name
    return "", consignee

def get_customer_transit_rate(customer: Optional[Customer], cargo_type: str) -> float:
    if not customer or not cargo_type:
        return 0.0
    rates = customer.cargo_type_transit_fee_rate
    if not rates:
        return 0.0
    if isinstance(rates, str):
        try:
            rates = json.loads(rates)
        except Exception:
            return 0.0
    if isinstance(rates, dict):
        try:
            return float(rates.get(cargo_type, 0.0))
        except Exception:
            return 0.0
    return 0.0

# ----------------- API Endpoints -----------------

@router.get("/air", summary="统一空运财务审核列表")
async def get_air_financial_audits(
    query: AirFinancialAuditQuery = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query_shenzhen = not bool(query.agent_name)
    query_southern = not bool(query.agent_name)
    query_peer = True

    if query.airline_type:
        if query.airline_type == "shenzhen_air":
            query_southern = False
            query_peer = False
        elif query.airline_type == "china_southern_air":
            query_shenzhen = False
            query_peer = False
        elif query.airline_type == "peer_air":
            query_shenzhen = False
            query_southern = False
        else:
            query_shenzhen = False
            query_southern = False
            query_peer = False

    candidate_items = []
    waybill_list = [w.strip() for w in query.waybill_number.split(',') if w.strip()] if query.waybill_number else []

    # ================= 1.1 查询深航 =================
    if query_shenzhen:
        sz_q = db.query(
            ShenzhenAirBookingExport,
            ShenzhenAirDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            ShenzhenAirDepartureManualData,
            ShenzhenAirDepartureManualData.booking_export_id == ShenzhenAirBookingExport.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "shenzhen_air",
                AirFinancialAuditData.source_id == ShenzhenAirBookingExport.id
            )
        )

        if waybill_list:
            or_filters = []
            for wb in waybill_list:
                if '-' in wb:
                    pref, num = wb.split('-', 1)
                    or_filters.append(
                        and_(
                            ShenzhenAirBookingExport.prefix == pref,
                            ShenzhenAirBookingExport.waybill_number == num
                        )
                    )
                else:
                    or_filters.append(ShenzhenAirBookingExport.waybill_number == wb)
            sz_q = sz_q.filter(or_(*or_filters))

        if query.flight_date_start:
            sz_q = sz_q.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') >= str(query.flight_date_start))
        if query.flight_date_end:
            sz_q = sz_q.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') <= str(query.flight_date_end))

        if query.destination:
            sz_q = sz_q.filter(ShenzhenAirBookingExport.routing.like(f"%{query.destination}%"))

        if query.flight_number:
            sz_q = sz_q.filter(ShenzhenAirBookingExport.billing_flight.like(f"%{query.flight_number}%"))

        if query.audit_status is not None:
            if query.audit_status == 0:
                sz_q = sz_q.filter(or_(ShenzhenAirDepartureManualData.audit_status == 0, ShenzhenAirDepartureManualData.audit_status.is_(None)))
            else:
                sz_q = sz_q.filter(ShenzhenAirDepartureManualData.audit_status == query.audit_status)

        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                sz_q = sz_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                sz_q = sz_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        if query.telegram_status:
            if query.telegram_status == "有电报":
                sz_q = sz_q.filter(
                    or_(
                        and_(ShenzhenAirDepartureManualData.telegram_fee != None, ShenzhenAirDepartureManualData.telegram_fee != ""),
                        and_(ShenzhenAirDepartureManualData.telegram_code != None, ShenzhenAirDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                sz_q = sz_q.filter(
                    and_(
                        or_(ShenzhenAirDepartureManualData.telegram_fee == None, ShenzhenAirDepartureManualData.telegram_fee == ""),
                        or_(ShenzhenAirDepartureManualData.telegram_code == None, ShenzhenAirDepartureManualData.telegram_code == "")
                    )
                )

        if query.cca_status:
            if query.cca_status == "有CCA":
                sz_q = sz_q.filter(and_(ShenzhenAirDepartureManualData.cca != None, ShenzhenAirDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                sz_q = sz_q.filter(or_(ShenzhenAirDepartureManualData.cca == None, ShenzhenAirDepartureManualData.cca == ""))

        for export, md, fa in sz_q.all():
            f_date = safe_str(export.flight_date).replace('/', '-')
            waybill_full = f"{safe_str(export.prefix)}-{safe_str(export.waybill_number)}" if export.prefix else safe_str(export.waybill_number)
            
            routing = safe_str(export.routing)
            origin, dest = "", ""
            if '-' in routing:
                rt_parts = [r.strip() for r in routing.split('-')]
                origin = rt_parts[0] if len(rt_parts) > 0 else ""
                dest = rt_parts[1] if len(rt_parts) > 1 else ""
            
            candidate_items.append({
                "source_type": "shenzhen_air",
                "source_id": str(export.id),
                "flight_date": f_date,
                "waybill_number": waybill_full,
                "origin": origin,
                "destination": dest or query.destination or "",
                "flight_number": safe_str(export.billing_flight),
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else "",
                "agent_name": safe_str(export.agent),
                "airline": "深航",
                "cargo_name": safe_str(export.cargo_name),
                "billing_quantity": safe_str(export.quantity),
                "billing_weight": safe_str(export.weight),
                "creator": safe_str(export.creator),
                "creation_time": safe_str(export.creation_time),
                "_main": export,
                "_md": md,
                "_fa": fa
            })

    # ================= 1.2 查询南航 =================
    if query_southern:
        csa_q = db.query(
            ChinaSouthernAirApprovalData,
            CsaDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            CsaDepartureManualData,
            CsaDepartureManualData.approval_data_id == ChinaSouthernAirApprovalData.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "china_southern_air",
                AirFinancialAuditData.source_id == ChinaSouthernAirApprovalData.id
            )
        )

        if waybill_list:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.waybill_number.in_(waybill_list))

        if query.destination:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%{query.destination}%"))

        if query.flight_number:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%{query.flight_number}%"))

        if query.audit_status is not None:
            if query.audit_status == 0:
                csa_q = csa_q.filter(or_(CsaDepartureManualData.audit_status == 0, CsaDepartureManualData.audit_status.is_(None)))
            else:
                csa_q = csa_q.filter(CsaDepartureManualData.audit_status == query.audit_status)

        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                csa_q = csa_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                csa_q = csa_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        if query.telegram_status:
            if query.telegram_status == "有电报":
                csa_q = csa_q.filter(
                    or_(
                        and_(CsaDepartureManualData.telegram_fee != None, CsaDepartureManualData.telegram_fee != ""),
                        and_(CsaDepartureManualData.telegram_code != None, CsaDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                csa_q = csa_q.filter(
                    and_(
                        or_(CsaDepartureManualData.telegram_fee == None, CsaDepartureManualData.telegram_fee == ""),
                        or_(CsaDepartureManualData.telegram_code == None, CsaDepartureManualData.telegram_code == "")
                    )
                )

        if query.cca_status:
            if query.cca_status == "有CCA":
                csa_q = csa_q.filter(and_(CsaDepartureManualData.cca != None, CsaDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                csa_q = csa_q.filter(or_(CsaDepartureManualData.cca == None, CsaDepartureManualData.cca == ""))

        for approval, md, fa in csa_q.all():
            fl_num, fl_date, orig, dest = parse_csa_flight_info(approval.flight_info)
            
            if query.flight_date_start and fl_date < str(query.flight_date_start):
                continue
            if query.flight_date_end and fl_date > str(query.flight_date_end):
                continue
                
            pieces, weight = parse_csa_qty_weight(approval.billing_qty)

            candidate_items.append({
                "source_type": "china_southern_air",
                "source_id": str(approval.id),
                "flight_date": fl_date,
                "waybill_number": safe_str(approval.waybill_number),
                "origin": orig,
                "destination": dest or query.destination or "",
                "flight_number": fl_num,
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else "",
                "agent_name": safe_str(approval.agent_code),
                "airline": "南航",
                "cargo_name": safe_str(approval.goods_name),
                "billing_quantity": pieces,
                "billing_weight": weight,
                "creator": "",
                "creation_time": safe_str(approval.booking_time),
                "_main": approval,
                "_md": md,
                "_fa": fa
            })

    # ================= 1.3 查询同行空运 =================
    if query_peer:
        peer_q = db.query(
            ConsignmentNote,
            PeerAirDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            PeerAirDepartureManualData,
            PeerAirDepartureManualData.consignment_note_id == ConsignmentNote.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "peer_air",
                AirFinancialAuditData.source_id == ConsignmentNote.id
            )
        ).filter(
            ConsignmentNote.transport_type == "0"
        )

        if waybill_list:
            peer_q = peer_q.filter(PeerAirDepartureManualData.waybill_number.in_(waybill_list))

        if query.flight_date_start:
            peer_q = peer_q.filter(ConsignmentNote.consignment_date >= query.flight_date_start)
        if query.flight_date_end:
            peer_q = peer_q.filter(ConsignmentNote.consignment_date <= query.flight_date_end)

        if query.agent_name:
            peer_q = peer_q.filter(ConsignmentNote.company_name.like(f"%{query.agent_name}%"))

        if query.destination:
            peer_q = peer_q.filter(ConsignmentNote.destination.like(f"%{query.destination}%"))

        if query.flight_number:
            peer_q = peer_q.filter(ConsignmentNote.flight_number.like(f"%{query.flight_number}%"))

        if query.audit_status is not None:
            if query.audit_status == 0:
                peer_q = peer_q.filter(or_(PeerAirDepartureManualData.audit_status == 0, PeerAirDepartureManualData.audit_status.is_(None)))
            else:
                peer_q = peer_q.filter(PeerAirDepartureManualData.audit_status == query.audit_status)

        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                peer_q = peer_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                peer_q = peer_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        if query.telegram_status:
            if query.telegram_status == "有电报":
                peer_q = peer_q.filter(
                    or_(
                        and_(PeerAirDepartureManualData.telegram_fee != None, PeerAirDepartureManualData.telegram_fee != ""),
                        and_(PeerAirDepartureManualData.telegram_code != None, PeerAirDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                peer_q = peer_q.filter(
                    and_(
                        or_(PeerAirDepartureManualData.telegram_fee == None, PeerAirDepartureManualData.telegram_fee == ""),
                        or_(PeerAirDepartureManualData.telegram_code == None, PeerAirDepartureManualData.telegram_code == "")
                    )
                )

        if query.cca_status:
            if query.cca_status == "有CCA":
                peer_q = peer_q.filter(and_(PeerAirDepartureManualData.cca != None, PeerAirDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                peer_q = peer_q.filter(or_(PeerAirDepartureManualData.cca == None, PeerAirDepartureManualData.cca == ""))

        for note, md, fa in peer_q.all():
            f_date = note.consignment_date.isoformat() if note.consignment_date else ""
            
            form_dict = {}
            if note.form_data:
                try:
                    form_dict = json.loads(note.form_data)
                except Exception:
                    pass

            candidate_items.append({
                "source_type": "peer_air",
                "source_id": str(note.id),
                "flight_date": f_date,
                "waybill_number": md.waybill_number if md else "",
                "origin": form_dict.get("origin_station", ""),
                "destination": note.destination or "",
                "flight_number": safe_str(note.flight_number),
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else note.customer_name,
                "agent_name": note.company_name or "",
                "airline": note.airline or "",
                "cargo_name": form_dict.get("cargo_name", ""),
                "billing_quantity": safe_str(form_dict.get("quantity", "")),
                "billing_weight": safe_str(form_dict.get("weight", "")),
                "creator": safe_str(note.creator_name),
                "creation_time": note.created_at.strftime("%Y-%m-%d %H:%M:%S") if note.created_at else "",
                "_main": note,
                "_form_dict": form_dict,
                "_md": md,
                "_fa": fa
            })

    # ================= 1.4 查询手工新增的记录 =================
    manual_q = db.query(AirFinancialAuditData).filter(
        or_(
            AirFinancialAuditData.source_id == 0,
            AirFinancialAuditData.source_id == AirFinancialAuditData.id
        )
    )

    if query.airline_type:
        manual_q = manual_q.filter(AirFinancialAuditData.source_type == query.airline_type)

    if query.financial_audit_status is not None:
        if query.financial_audit_status == 0:
            manual_q = manual_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
        else:
            manual_q = manual_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

    for fa in manual_q.all():
        # 从 receivable_data JSON 中提取列表层字段
        recv = fa.receivable_data or {}
        if isinstance(recv, str):
            try:
                recv = json.loads(recv)
            except Exception:
                recv = {}
        pay = fa.payable_data or {}
        if isinstance(pay, str):
            try:
                pay = json.loads(pay)
            except Exception:
                pay = {}

        fl_date = recv.get("flight_date", "") or ""
        wb_number = recv.get("waybill_number", "") or ""
        agent_name_val = pay.get("agent_name", "") or ""

        if waybill_list and wb_number not in waybill_list:
            continue

        # 航班日期范围过滤
        if query.flight_date_start and fl_date < str(query.flight_date_start):
            continue
        if query.flight_date_end and fl_date > str(query.flight_date_end):
            continue

        # 目的站模糊搜索
        if query.destination and query.destination not in (recv.get("destination", "") or ""):
            continue

        # 航班号模糊搜索
        if query.flight_number and query.flight_number not in (recv.get("flight_number", "") or ""):
            continue
            
        # 同行空运需支持代理名称过滤
        if query.agent_name and query.agent_name not in agent_name_val:
            if fa.source_type == "peer_air":
                continue

        candidate_items.append({
            "source_type": fa.source_type,
            "source_id": str(fa.id),
            "is_manual": True,
            "flight_date": fl_date,
            "waybill_number": wb_number,
            "origin": recv.get("origin", "") or "",
            "destination": recv.get("destination", "") or "",
            "flight_number": recv.get("flight_number", "") or "",
            "audit_status": 0,
            "financial_audit_status": fa.financial_audit_status or 0,
            "customer_name": recv.get("customer_name", "") or "",
            "agent_name": agent_name_val,
            "airline": recv.get("airline", "") or "",
            "cargo_name": recv.get("cargo_name", "") or "",
            "billing_quantity": pay.get("billing_pieces", "") or "",
            "billing_weight": pay.get("billing_weight", "") or "",
            "creator": pay.get("_creator_name", "") or "",
            "creation_time": fa.created_at.strftime("%Y-%m-%d %H:%M:%S") if fa.created_at else "",
            "_fa": fa
        })

    # ================= 2. 内存全局排序 =================
    candidate_items.sort(key=lambda x: (x["flight_date"] or "", x["source_id"]), reverse=True)
    total = len(candidate_items)

    offset = (query.page - 1) * query.pageSize
    paged_items = candidate_items[offset : offset + query.pageSize]

    # ================= 3. 批量提取/组装本页详细数据 =================
    customers = db.query(Customer).all()
    customer_map = {c.company_name: c for c in customers if c.company_name}
    customer_id_map = {str(c.id): c for c in customers}

    sz_waybill_8s = []
    csa_approval_ids = []
    csa_waybills = []

    for item in paged_items:
        if item["source_type"] == "shenzhen_air":
            export = item["_main"]
            if export.waybill_number and len(export.waybill_number) >= 8:
                sz_waybill_8s.append(export.waybill_number[-8:])
        elif item["source_type"] == "china_southern_air":
            csa_approval_ids.append(int(item["source_id"]))
            if item["waybill_number"]:
                csa_waybills.append(item["waybill_number"])

    sz_containers_map = {}
    if sz_waybill_8s:
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.waybill_number_8.in_(sz_waybill_8s)
        ).all()
        for cont in containers:
            sz_containers_map.setdefault(cont.waybill_number_8, []).append(cont)

    csa_lalamoves_map = {}
    if csa_approval_ids:
        lalamoves = db.query(CsaLalamoveInformation).filter(
            CsaLalamoveInformation.approval_data_id.in_(csa_approval_ids)
        ).all()
        for lm in lalamoves:
            csa_lalamoves_map.setdefault(lm.approval_data_id, []).append(lm)

    csa_waybill_map = {}
    if csa_waybills:
        wb_records = db.query(Waybill).filter(Waybill.waybill_number.in_(csa_waybills)).all()
        for wb in wb_records:
            csa_waybill_map[wb.waybill_number] = wb

    result_items = []
    for item in paged_items:
        source_type = item["source_type"]

        payable_data = None
        receivable_data = None

        if item.get("is_manual"):
            # 手工新增的记录直接从payable_data/receivable_data JSON渲染
            fa = item["_fa"]
            pay_raw = fa.payable_data or {}
            if isinstance(pay_raw, str):
                try:
                    pay_raw = json.loads(pay_raw)
                except Exception:
                    pay_raw = {}
            recv_raw = fa.receivable_data or {}
            if isinstance(recv_raw, str):
                try:
                    recv_raw = json.loads(recv_raw)
                except Exception:
                    recv_raw = {}

            # 重新计算成本合计 (total_cost)
            calc_total_cost = (
                safe_float(pay_raw.get("air_freight")) +
                safe_float(pay_raw.get("fuel_surcharge")) +
                safe_float(pay_raw.get("transit_fee")) +
                safe_float(pay_raw.get("cca_cost")) +
                safe_float(pay_raw.get("telegraph_cost")) +
                safe_float(pay_raw.get("packaging_fee")) +
                safe_float(pay_raw.get("other_fees")) +
                safe_float(pay_raw.get("door_pickup_fee")) +
                safe_float(pay_raw.get("airport_pickup_fee")) +
                safe_float(pay_raw.get("delivery_cost"))
            )
            pay_raw["total_cost"] = format_decimal(calc_total_cost)

            payable_res = PayableResponse(**{k: (str(v) if v is not None else None) for k, v in pay_raw.items() if k in PayableResponse.model_fields})
            receivable_dict = {k: (str(v) if v is not None else None) for k, v in recv_raw.items() if k in ReceivableResponse.model_fields}
            
            customer_name_raw = str(item.get("customer_name") or "").strip()
            actual_customer_name = ""
            if customer_name_raw in customer_id_map:
                cust = customer_id_map[customer_name_raw]
                actual_customer_name = cust.company_name
                cycle_str = SETTLEMENT_CYCLE_MAP.get(cust.settlement_cycle, "") if cust.settlement_cycle else ""
                receivable_dict["payment_method"] = cycle_str
                receivable_dict["document_fee"] = str(cust.document_fee) if cust.document_fee is not None else ""
            elif not customer_name_raw.isdigit():
                receivable_dict["payment_method"] = ""
                receivable_dict["document_fee"] = ""

            # 重新计算应收总金额 (total_amount)
            calc_total_amount = (
                safe_float(receivable_dict.get("freight")) +
                safe_float(receivable_dict.get("document_fee")) +
                safe_float(receivable_dict.get("door_pickup_fee")) +
                safe_float(receivable_dict.get("packaging_fee")) +
                safe_float(receivable_dict.get("airport_pickup_fee")) +
                safe_float(receivable_dict.get("delivery_fee")) +
                safe_float(receivable_dict.get("cca")) +
                safe_float(receivable_dict.get("telegram_fee")) +
                safe_float(receivable_dict.get("carrier_deduction")) +
                safe_float(receivable_dict.get("other_fees"))
            )
            receivable_dict["total_amount"] = format_decimal(calc_total_amount)
            # 同时也需要更新毛利
            calc_gross_profit = calc_total_amount - calc_total_cost
            receivable_dict["gross_profit"] = format_decimal(calc_gross_profit)

            receivable_res = ReceivableResponse(**receivable_dict)

            dest_code = item.get("destination", "")
            dest_name = get_airport_name_by_code(dest_code)
            
            airline = item.get("airline", "")
            if airline == "深航":
                phone = pickup_phone_mapper.get_shenzhen_air_phone(dest_code, dest_name)
            else:
                phone = pickup_phone_mapper.get_national_phone(dest_name, airline)

            extra_data = ExtraData(
                pickup_point=dest_name if dest_name != dest_code else dest_code,
                pickup_phone=phone,
                billing_time=""
            )

            result_items.append(AirFinancialAuditItemResponse(
                source_type=item["source_type"],
                source_id=item["source_id"],
                audit_status=0,
                financial_audit_status=item["financial_audit_status"],
                flight_date=item["flight_date"],
                customer_name=item["customer_name"],
                actual_customer_name=actual_customer_name,
                agent_name=item["agent_name"],
                airline=item["airline"],
                waybill_number=item["waybill_number"],
                origin=item["origin"],
                destination=item["destination"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                billing_quantity=item["billing_quantity"],
                billing_weight=item["billing_weight"],
                creator=item["creator"],
                creation_time=item["creation_time"],
                payable=payable_res,
                receivable=receivable_res,
                extra_data=extra_data
            ))
            continue

        md = item["_md"]
        fa = item["_fa"]
        cust_name = item["customer_name"]
        customer = customer_map.get(cust_name)

        billing_time_val = ""

        if source_type == "shenzhen_air":
            export = item["_main"]
            wb_8 = export.waybill_number[-8:] if export.waybill_number and len(export.waybill_number) >= 8 else ""
            related_conts = sz_containers_map.get(wb_8, [])
            
            for cont in related_conts:
                if cont.billing_time:
                    billing_time_val = str(cont.billing_time)
                    break
            
            gate_pieces_val = sum(safe_int(c.quantity) for c in related_conts)
            transit_weight_val = sum(safe_float(c.weight) for c in related_conts)
            
            cargo_type = md.cargo_type if md else ""
            transit_rate = get_customer_transit_rate(customer, cargo_type)
            transit_fee_val = transit_weight_val * transit_rate

            telegraph_cost_val = md.telegram_fee if md else ""

            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.delivery_fee if md else 0.0)

            total_cost_val = (
                safe_float(export.air_freight) +
                safe_float(export.fuel_surcharge) +
                transit_fee_val +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=None,
                cargo_type=cargo_type,
                billing_pieces=safe_str(export.quantity),
                billing_weight=safe_str(export.weight),
                gate_pieces=str(gate_pieces_val) if related_conts else "0",
                chargeable_weight=safe_str(export.chargeable_weight),
                freight_rate=safe_str(export.freight_rate),
                air_freight=safe_str(export.air_freight),
                fuel_surcharge=safe_str(export.fuel_surcharge),
                transit_weight=format_decimal(transit_weight_val),
                transit_fee=format_decimal(transit_fee_val),
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark="",
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            consignee_phone, consignee_name = parse_consignee_phone_name(export.consignee)
            receivable_freight = safe_float(export.chargeable_weight) * safe_float(export.freight_rate)

            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(md.door_pickup_fee if md else 0.0) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0)
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone=consignee_phone,
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=safe_str(export.quantity),
                chargeable_weight=safe_str(export.chargeable_weight),
                freight_rate=safe_str(export.freight_rate),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark="",
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(md.carrier_deduction if md else ""),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee=consignee_name,
                destination=item["destination"],
                pickup_method="",
                weight=safe_str(export.chargeable_weight),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.delivery_fee if md else ""),
                collection_payment="",
                remark="",
                gross_profit=format_decimal(gross_profit_val)
            )

        elif source_type == "china_southern_air":
            approval = item["_main"]
            related_lms = csa_lalamoves_map.get(approval.id, [])
            
            gate_pieces_val = sum(safe_int(l.pieces) for l in related_lms)
            transit_weight_val = sum(safe_float(l.weight) for l in related_lms)
            
            cargo_type = md.cargo_type if md else ""
            transit_rate = get_customer_transit_rate(customer, cargo_type)
            transit_fee_val = transit_weight_val * transit_rate

            telegraph_cost_val = md.telegram_fee if md else ""

            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.delivery_fee if md else 0.0)

            total_cost_val = (
                safe_float(approval.ref_freight) +
                transit_fee_val +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=None,
                cargo_type=cargo_type,
                billing_pieces=item["billing_quantity"],
                billing_weight=item["billing_weight"],
                gate_pieces=str(gate_pieces_val) if related_lms else "0",
                chargeable_weight=safe_str(approval.chargeable_weight),
                freight_rate=safe_str(approval.ref_rate),
                air_freight=safe_str(approval.ref_freight),
                fuel_surcharge="",
                transit_weight=format_decimal(transit_weight_val),
                transit_fee=format_decimal(transit_fee_val),
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark="",
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            wb_phone = ""
            wb_consignee = ""
            if approval.waybill_number and approval.waybill_number in csa_waybill_map:
                waybill_obj = csa_waybill_map[approval.waybill_number]
                if waybill_obj.form_data:
                    try:
                        wb_form = json.loads(waybill_obj.form_data)
                        wb_phone = wb_form.get("contact_info", {}).get("consignee_phone", "")
                        wb_consignee = wb_form.get("contact_info", {}).get("consignee", "")
                    except Exception:
                        pass

            receivable_freight = safe_float(approval.chargeable_weight) * safe_float(approval.ref_rate)

            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(md.door_pickup_fee if md else 0.0) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0)
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone=wb_phone,
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=item["billing_quantity"],
                chargeable_weight=safe_str(approval.chargeable_weight),
                freight_rate=safe_str(approval.ref_rate),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark="",
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(md.carrier_deduction if md else ""),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee=wb_consignee,
                destination=item["destination"],
                pickup_method="",
                weight=safe_str(approval.chargeable_weight),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.delivery_fee if md else ""),
                collection_payment="",
                remark="",
                gross_profit=format_decimal(gross_profit_val)
            )

        elif source_type == "peer_air":
            note = item["_main"]
            form_dict = item["_form_dict"]

            gate_pieces_val = ""
            transit_fee_val = 0.0

            telegraph_cost_val = md.telegram_fee if md else ""

            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.delivery_fee if md else 0.0)

            total_cost_val = (
                safe_float(form_dict.get("air_freight", 0.0)) +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=note.company_name,
                cargo_type=md.cargo_type if md else "",
                billing_pieces=safe_str(form_dict.get("quantity", "")),
                billing_weight=safe_str(form_dict.get("weight", "")),
                gate_pieces="",
                chargeable_weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight_rate=safe_str(form_dict.get("rate", "")),
                air_freight=safe_str(form_dict.get("air_freight", "")),
                fuel_surcharge="",
                transit_weight="",
                transit_fee="",
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark="",
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            receivable_freight = safe_float(form_dict.get("chargeable_weight", 0.0)) * safe_float(form_dict.get("rate", 0.0))

            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(md.door_pickup_fee if md else 0.0) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0)
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone="",
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=safe_str(form_dict.get("quantity", "")),
                chargeable_weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight_rate=safe_str(form_dict.get("rate", "")),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark="",
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(md.carrier_deduction if md else ""),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee="",
                destination=item["destination"],
                pickup_method="",
                weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.delivery_fee if md else ""),
                collection_payment="",
                remark="",
                gross_profit=format_decimal(gross_profit_val)
            )

        # ================= 4. 合并财务人工自定义覆盖的应付应收 JSON 数据 =================
        payable_dict = payable_data.model_dump()
        if fa and fa.payable_data:
            p_override = fa.payable_data
            if isinstance(p_override, str):
                try:
                    p_override = json.loads(p_override)
                except Exception:
                    p_override = {}
            if isinstance(p_override, dict):
                payable_dict.update({k: str(v) for k, v in p_override.items() if v is not None})
        
        # 重新计算成本合计 (total_cost)
        calc_total_cost = (
            safe_float(payable_dict.get("air_freight")) +
            safe_float(payable_dict.get("fuel_surcharge")) +
            safe_float(payable_dict.get("transit_fee")) +
            safe_float(payable_dict.get("cca_cost")) +
            safe_float(payable_dict.get("telegraph_cost")) +
            safe_float(payable_dict.get("packaging_fee")) +
            safe_float(payable_dict.get("other_fees")) +
            safe_float(payable_dict.get("door_pickup_fee")) +
            safe_float(payable_dict.get("airport_pickup_fee")) +
            safe_float(payable_dict.get("delivery_cost"))
        )
        payable_dict["total_cost"] = format_decimal(calc_total_cost)

        payable_res = PayableResponse(**payable_dict)

        receivable_dict = receivable_data.model_dump()
        if fa and fa.receivable_data:
            r_override = fa.receivable_data
            if isinstance(r_override, str):
                try:
                    r_override = json.loads(r_override)
                except Exception:
                    r_override = {}
            if isinstance(r_override, dict):
                receivable_dict.update({k: str(v) for k, v in r_override.items() if v is not None})

        customer_name_raw = str(cust_name).strip() if cust_name else ""
        actual_customer_name = ""
        if customer_name_raw in customer_id_map:
            cust = customer_id_map[customer_name_raw]
            actual_customer_name = cust.company_name
            cycle_str = SETTLEMENT_CYCLE_MAP.get(cust.settlement_cycle, "") if cust.settlement_cycle else ""
            receivable_dict["payment_method"] = cycle_str
            receivable_dict["document_fee"] = str(cust.document_fee) if cust.document_fee is not None else ""
        elif not customer_name_raw.isdigit():
            receivable_dict["payment_method"] = ""
            receivable_dict["document_fee"] = ""

        # 重新计算应收总金额 (total_amount)
        calc_total_amount = (
            safe_float(receivable_dict.get("freight")) +
            safe_float(receivable_dict.get("document_fee")) +
            safe_float(receivable_dict.get("door_pickup_fee")) +
            safe_float(receivable_dict.get("packaging_fee")) +
            safe_float(receivable_dict.get("airport_pickup_fee")) +
            safe_float(receivable_dict.get("delivery_fee")) +
            safe_float(receivable_dict.get("cca")) +
            safe_float(receivable_dict.get("telegram_fee")) +
            safe_float(receivable_dict.get("carrier_deduction")) +
            safe_float(receivable_dict.get("other_fees"))
        )
        receivable_dict["total_amount"] = format_decimal(calc_total_amount)
        # 同时也需要更新毛利
        calc_gross_profit = calc_total_amount - calc_total_cost
        receivable_dict["gross_profit"] = format_decimal(calc_gross_profit)

        receivable_res = ReceivableResponse(**receivable_dict)

        dest_code = item.get("destination", "")
        dest_name = get_airport_name_by_code(dest_code)
        
        airline = item.get("airline", "")
        if airline == "深航":
            phone = pickup_phone_mapper.get_shenzhen_air_phone(dest_code, dest_name)
        else:
            phone = pickup_phone_mapper.get_national_phone(dest_name, airline)

        extra_data = ExtraData(
            pickup_point=dest_name if dest_name != dest_code else dest_code,
            pickup_phone=phone,
            billing_time=billing_time_val
        )

        result_items.append(AirFinancialAuditItemResponse(
            source_type=source_type,
            source_id=item["source_id"],
            audit_status=item["audit_status"],
            financial_audit_status=item["financial_audit_status"],
            flight_date=item["flight_date"],
            customer_name=cust_name,
            actual_customer_name=actual_customer_name,
            agent_name=item["agent_name"],
            airline=item["airline"],
            waybill_number=item["waybill_number"],
            origin=item["origin"],
            destination=item["destination"],
            flight_number=item["flight_number"],
            cargo_name=item["cargo_name"],
            billing_quantity=item["billing_quantity"],
            billing_weight=item["billing_weight"],
            creator=item["creator"],
            creation_time=item["creation_time"],
            payable=payable_res,
            receivable=receivable_res,
            extra_data=extra_data
        ))

    return success_response(data={
        "total": total,
        "items": [item.model_dump() for item in result_items]
    })


@router.post("/air/audit", summary="统一空运财务审核暂存/提交")
async def audit_air_financial(
    req: AirFinancialAuditDataUpsert,
    action: str = Query(..., description="操作类型：save (暂存), submit (已审核/提交)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if action not in ["save", "submit"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'save' or 'submit'")

    source_type = req.source_type
    source_id = int(req.source_id)

    exists = False
    is_manual = False

    if source_type == "shenzhen_air":
        exists_record = db.query(ShenzhenAirBookingExport.id).filter(ShenzhenAirBookingExport.id == source_id).first()
        if exists_record: exists = True
    elif source_type == "china_southern_air":
        exists_record = db.query(ChinaSouthernAirApprovalData.id).filter(ChinaSouthernAirApprovalData.id == source_id).first()
        if exists_record: exists = True
    elif source_type == "peer_air":
        exists_record = db.query(ConsignmentNote.id).filter(ConsignmentNote.id == source_id, ConsignmentNote.transport_type == "0").first()
        if exists_record: exists = True
    else:
        raise HTTPException(status_code=400, detail="Invalid source_type")

    # 如果主表不存在，检查是否是手工新增的记录（自身 id == source_id 或 source_id == 0 兼容旧数据）
    if not exists:
        fa_manual = db.query(AirFinancialAuditData.id).filter(
            AirFinancialAuditData.id == source_id,
            AirFinancialAuditData.source_type == source_type,
            or_(
                AirFinancialAuditData.source_id == 0,
                AirFinancialAuditData.source_id == source_id
            )
        ).first()
        if fa_manual:
            exists = True
            is_manual = True

    if not exists:
        raise HTTPException(status_code=404, detail="Source record not found")

    if is_manual:
        fa_data = db.query(AirFinancialAuditData).filter(AirFinancialAuditData.id == source_id).first()
    else:
        fa_data = db.query(AirFinancialAuditData).filter(
            AirFinancialAuditData.source_type == source_type,
            AirFinancialAuditData.source_id == source_id
        ).first()

        if not fa_data:
            fa_data = AirFinancialAuditData(
                source_type=source_type,
                source_id=source_id
            )
            db.add(fa_data)

    # 支持对整个 payable & receivable 中传递的字段全部进行序列化并作为 JSON 保存到数据库中
    if req.payable is not None:
        fa_data.payable_data = req.payable.model_dump()
    if req.receivable is not None:
        fa_data.receivable_data = req.receivable.model_dump()

    target_status = 1 if action == "save" else 2
    fa_data.financial_audit_status = target_status
    fa_data.financial_auditor_id = current_user.id
    fa_data.financial_auditor_name = current_user.name
    fa_data.financial_audit_time = datetime.now()

    db.commit()
    db.refresh(fa_data)

    return success_response(msg="操作成功", data={
        "source_type": fa_data.source_type,
        "source_id": str(fa_data.id) if (fa_data.source_id == 0 or fa_data.source_id == fa_data.id) else str(fa_data.source_id),
        "financial_audit_status": fa_data.financial_audit_status
    })


@router.post("/air", summary="新增空运财务审核单据")
async def create_air_financial_audit(
    req: AirFinancialAuditCreateRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    新增空运财务审核单据接口。
    手动创建一条单独的财务审核记录，不关联任何源表数据（source_id 为 0）。
    通过 receivable.airline 字段推导 source_type：深航/南航/同行空运。
    receivable 中的 waybill_number 和 airline 必传。
    """
    # 校验运单号必填
    if not req.receivable.waybill_number or not req.receivable.waybill_number.strip():
        raise HTTPException(status_code=400, detail="receivable 中的 waybill_number（运单号）为必填项")
        
    airline_val = req.receivable.airline
    if not airline_val or not airline_val.strip():
        raise HTTPException(status_code=400, detail="receivable 中的 airline（航空公司）为必填项")
        
    airline_val = airline_val.strip()
    if airline_val == "深航":
        derived_source_type = "shenzhen_air"
    elif airline_val == "南航":
        derived_source_type = "china_southern_air"
    else:
        derived_source_type = "peer_air"

    pay_dict = req.payable.model_dump()
    pay_dict["_creator_name"] = current_user.name

    # 预先生成唯一ID，并作为 source_id 保存，避免触发 ux_source 唯一约束冲突（source_type, source_id)
    new_id = generate_id()

    fa_data = AirFinancialAuditData(
        id=new_id,
        source_type=derived_source_type,
        source_id=new_id,
        payable_data=pay_dict,
        receivable_data=req.receivable.model_dump(),
        financial_audit_status=0,

        financial_auditor_id=None,
        financial_auditor_name=None,
        financial_audit_time=None
    )
    db.add(fa_data)
    db.commit()
    db.refresh(fa_data)

    return success_response(msg="新增成功", data={
        "id": str(fa_data.id),
        "source_type": derived_source_type,
        "waybill_number": req.receivable.waybill_number.strip()
    })

