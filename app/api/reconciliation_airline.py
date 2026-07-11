from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import List
from datetime import datetime
import json

from app.api.deps import get_db, get_current_active_user
from app.core.response import success_response
from app.utils.helpers import safe_float, safe_int
from app.api.financial_audit import format_decimal

from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.consignment_note import ConsignmentNote
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.customer import Customer
from app.models.waybill import Waybill

from app.schemas.reconciliation_airline import (
    AirlineReconciliationQuery,
    AirlineReconciliationItemResponse,
    AirlineReconciliationListResponse
)

router = APIRouter()

@router.get("/air", summary="航司对账列表查询", response_model=AirlineReconciliationListResponse)
def get_airline_reconciliation_list(
    query: AirlineReconciliationQuery = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    统一查询航司应付对账列表。
    与财务审核列表同源，追加了实走航班号，并支持按航司对账结算状态过滤。
    """
    
    # 基础查询，仅包含财务审核状态
    fa_base_query = db.query(AirFinancialAuditData)
    
    if query.financial_audit_status is not None:
        fa_base_query = fa_base_query.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)
        
    if query.settlement_status is not None:
        fa_base_query = fa_base_query.filter(AirFinancialAuditData.airline_settlement_status == query.settlement_status)

    fa_records = fa_base_query.all()
    
    # 构建快速索引
    fa_map = {}
    for fa in fa_records:
        fa_map.setdefault(fa.source_type, {})[fa.source_id] = fa

    # 如果有状态过滤，且某个来源表中没有记录匹配该状态，则提取对应主表时不应包含它们
    fa_status_filter_active = (query.financial_audit_status is not None) or (query.settlement_status is not None)

    candidate_items = []
    
    # ---------------- 1. 深航数据提取 ----------------
    sz_query = db.query(ShenzhenAirBookingExport, ShenzhenAirDepartureManualData).outerjoin(
        ShenzhenAirDepartureManualData, ShenzhenAirBookingExport.id == ShenzhenAirDepartureManualData.booking_export_id
    )
    if query.waybill_numbers:
        wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
        if wbs:
            sz_query = sz_query.filter(ShenzhenAirBookingExport.waybill_number.in_(wbs))
    if query.flight_date_start:
        sz_query = sz_query.filter(ShenzhenAirBookingExport.flight_date >= query.flight_date_start)
    if query.flight_date_end:
        sz_query = sz_query.filter(ShenzhenAirBookingExport.flight_date <= query.flight_date_end)
    if query.airline and query.airline != "全部":
        sz_query = sz_query.filter(ShenzhenAirBookingExport.carrier == query.airline)

    sz_records = sz_query.all()
    for export, md in sz_records:
        fa = fa_map.get("shenzhen_air", {}).get(export.id)
        if fa_status_filter_active and not fa:
            continue
        
        # 匹配客户名称搜索
        c_name = str(export.agent) if export.agent else ""
        if query.customer_name and query.customer_name not in c_name:
            continue
            
        candidate_items.append({
            "source_type": "shenzhen_air",
            "source_id": export.id,
            "is_manual": False,
            "flight_date": export.flight_date,
            "waybill_number": export.waybill_number,
            "origin": "SZX",
            "destination": export.routing,
            "flight_number": export.billing_flight,
            "actual_flight_number": export.actual_flight or export.billing_flight, # 实走航班号
            "customer_name": c_name,
            "airline": export.carrier,
            "cargo_name": export.cargo_name,
            "billing_quantity": export.quantity,
            "billing_weight": export.weight,
            "chargeable_weight": export.chargeable_weight,
            "freight_rate": export.freight_rate,
            "air_freight": export.air_freight,
            "fuel_surcharge": export.fuel_surcharge,
            "_main": export,
            "_md": md,
            "_fa": fa
        })

    # ---------------- 2. 南航数据提取 ----------------
    csa_query = db.query(ChinaSouthernAirApprovalData, CsaDepartureManualData).outerjoin(
        CsaDepartureManualData, ChinaSouthernAirApprovalData.id == CsaDepartureManualData.approval_data_id
    )
    if query.waybill_numbers:
        wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
        if wbs:
            csa_query = csa_query.filter(ChinaSouthernAirApprovalData.waybill_number.in_(wbs))
    # 南航没有 flight_date，提取订舱时间前10位作为替代
    if query.flight_date_start:
        csa_query = csa_query.filter(func.substr(ChinaSouthernAirApprovalData.booking_time, 1, 10) >= query.flight_date_start)
    if query.flight_date_end:
        csa_query = csa_query.filter(func.substr(ChinaSouthernAirApprovalData.booking_time, 1, 10) <= query.flight_date_end)
    if query.airline and query.airline != "全部":
        if query.airline != "南航" and query.airline != "南方航空":
            csa_records = []
        else:
            csa_records = csa_query.all()
    else:
        csa_records = csa_query.all()
        
    for approval, md in csa_records:
        fa = fa_map.get("china_southern_air", {}).get(approval.id)
        if fa_status_filter_active and not fa:
            continue
            
        c_name = str(approval.key_account_name) if approval.key_account_name else ""
        if query.customer_name and query.customer_name not in c_name:
            continue
            
        f_date = approval.booking_time[:10] if approval.booking_time and len(approval.booking_time) >= 10 else ""
        flight_num = approval.flight_info.split("/")[0] if approval.flight_info else ""
        dest = approval.booking_routing.split("-")[-1] if approval.booking_routing else ""
        origin = approval.booking_routing.split("-")[0] if approval.booking_routing else "CAN"
        
        candidate_items.append({
            "source_type": "china_southern_air",
            "source_id": approval.id,
            "is_manual": False,
            "flight_date": f_date,
            "waybill_number": approval.waybill_number,
            "origin": origin,
            "destination": dest,
            "flight_number": flight_num,
            "actual_flight_number": approval.actual_flight or flight_num, # 实走航班号
            "customer_name": c_name,
            "airline": "南方航空",
            "cargo_name": approval.goods_name,
            "billing_quantity": "",
            "billing_weight": "",
            "chargeable_weight": approval.chargeable_weight,
            "freight_rate": approval.ref_rate,
            "air_freight": approval.ref_freight,
            "fuel_surcharge": "",
            "_main": approval,
            "_md": md,
            "_fa": fa
        })

    # ---------------- 3. 同行空运提取 ----------------
    peer_query = db.query(ConsignmentNote, PeerAirDepartureManualData).outerjoin(
        PeerAirDepartureManualData, ConsignmentNote.id == PeerAirDepartureManualData.consignment_note_id
    ).filter(ConsignmentNote.transport_type == "0")
    
    if query.flight_date_start:
        peer_query = peer_query.filter(ConsignmentNote.consignment_date >= query.flight_date_start)
    if query.flight_date_end:
        peer_query = peer_query.filter(ConsignmentNote.consignment_date <= query.flight_date_end)
    if query.airline and query.airline != "全部":
        peer_query = peer_query.filter(ConsignmentNote.airline == query.airline)

    peer_records = peer_query.all()
    for note, md in peer_records:
        fa = fa_map.get("peer_air", {}).get(note.id)
        if fa_status_filter_active and not fa:
            continue
            
        c_name = str(note.customer_name) if note.customer_name else ""
        if query.customer_name and query.customer_name not in c_name:
            continue
            
        try:
            form_dict = json.loads(note.form_data) if note.form_data else {}
        except Exception:
            form_dict = {}

        wb_no = form_dict.get("waybill_number", "")
        if query.waybill_numbers:
            wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
            if wbs and wb_no not in wbs:
                continue

        candidate_items.append({
            "source_type": "peer_air",
            "source_id": note.id,
            "is_manual": False,
            "flight_date": str(note.consignment_date) if note.consignment_date else "",
            "waybill_number": wb_no,
            "origin": form_dict.get("origin", ""),
            "destination": note.destination or form_dict.get("destination", ""),
            "flight_number": note.flight_number or form_dict.get("flight_number", ""),
            "actual_flight_number": form_dict.get("actual_flight") or note.flight_number or form_dict.get("flight_number", ""),
            "customer_name": c_name,
            "airline": note.airline or form_dict.get("airline", ""),
            "cargo_name": form_dict.get("cargo_name", ""),
            "billing_quantity": form_dict.get("quantity", ""),
            "billing_weight": form_dict.get("weight", ""),
            "chargeable_weight": form_dict.get("chargeable_weight", ""),
            "freight_rate": form_dict.get("rate", ""),
            "air_freight": form_dict.get("air_freight", ""),
            "fuel_surcharge": "",
            "_main": note,
            "_md": md,
            "_fa": fa,
            "_form_dict": form_dict
        })

    # ---------------- 4. 纯手工财务审核单据提取 ----------------
    fa_manual_records = [
        f for f in fa_records 
        if (f.source_id == 0 or f.source_id == f.id)
    ]
    for fa in fa_manual_records:
        if query.financial_audit_status is not None and fa.financial_audit_status != query.financial_audit_status:
            continue
        if query.settlement_status is not None and fa.airline_settlement_status != query.settlement_status:
            continue

        recv_dict = fa.receivable_data or {}
        if isinstance(recv_dict, str):
            try: recv_dict = json.loads(recv_dict)
            except Exception: recv_dict = {}
            
        pay_dict = fa.payable_data or {}
        if isinstance(pay_dict, str):
            try: pay_dict = json.loads(pay_dict)
            except Exception: pay_dict = {}

        wb_no = recv_dict.get("waybill_number", "")
        if query.waybill_numbers:
            wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
            if wbs and wb_no not in wbs:
                continue
                
        f_date = recv_dict.get("flight_date", "")
        if query.flight_date_start and f_date < query.flight_date_start:
            continue
        if query.flight_date_end and f_date > query.flight_date_end:
            continue
            
        air = recv_dict.get("airline", "")
        if query.airline and query.airline != "全部" and air != query.airline:
            continue
            
        c_name = recv_dict.get("customer_name", "")
        if query.customer_name and query.customer_name not in c_name:
            continue

        candidate_items.append({
            "source_type": fa.source_type,
            "source_id": fa.id,
            "is_manual": True,
            "flight_date": f_date,
            "waybill_number": wb_no,
            "origin": recv_dict.get("origin", "") or "",
            "destination": recv_dict.get("destination", "") or "",
            "flight_number": recv_dict.get("flight_number", "") or "",
            "actual_flight_number": recv_dict.get("actual_flight_number", "") or recv_dict.get("flight_number", "") or "",
            "customer_name": c_name,
            "airline": air,
            "cargo_name": recv_dict.get("cargo_name", "") or "",
            "billing_quantity": pay_dict.get("billing_pieces", "") or "",
            "billing_weight": pay_dict.get("billing_weight", "") or "",
            "chargeable_weight": pay_dict.get("chargeable_weight", "") or "",
            "freight_rate": pay_dict.get("freight_rate", "") or "",
            "air_freight": pay_dict.get("air_freight", "") or "",
            "fuel_surcharge": pay_dict.get("fuel_surcharge", "") or "",
            "_fa": fa,
            "_pay_dict": pay_dict
        })

    # 分页排序
    candidate_items.sort(key=lambda x: (x["flight_date"] or "", x["waybill_number"] or ""), reverse=True)
    total = len(candidate_items)
    start_idx = (query.page - 1) * query.pageSize
    end_idx = start_idx + query.pageSize
    paged_items = candidate_items[start_idx:end_idx]

    # 加载辅助数据 (Lalamove 和 Waybills)
    csa_approval_ids = [item["source_id"] for item in paged_items if item["source_type"] == "china_southern_air"]
    csa_lalamoves_map = {}
    if csa_approval_ids:
        from app.database import SessionLocal
        lalamoves = db.query(CsaLalamoveInformation).filter(
            CsaLalamoveInformation.approval_data_id.in_(csa_approval_ids)
        ).all()
        for lm in lalamoves:
            csa_lalamoves_map.setdefault(lm.approval_data_id, []).append(lm)

    # 查 customer 名字映射
    customer_ids = {str(item["customer_name"]) for item in paged_items if str(item.get("customer_name")).isdigit()}
    customer_id_map = {}
    if customer_ids:
        customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
        customer_id_map = {str(c.id): c for c in customers}

    result_items = []
    for item in paged_items:
        fa = item.get("_fa")
        
        c_name = str(item.get("customer_name") or "").strip()
        actual_name = customer_id_map[c_name].company_name if c_name in customer_id_map else ""
        
        # 提取 payable 相关字段
        transit_fee_val = 0.0
        gate_pieces_val = ""
        transit_weight_val = ""
        telegraph_cost_val = ""
        cca_cost = 0.0
        pack_fee = 0.0
        oth_fee = 0.0
        penalty_fee = 0.0

        if item.get("is_manual"):
            pay_dict = item["_pay_dict"]
            gate_pieces_val = pay_dict.get("gate_pieces", "")
            transit_weight_val = pay_dict.get("transit_weight", "")
            transit_fee_val = safe_float(pay_dict.get("transit_fee"))
            telegraph_cost_val = safe_str(pay_dict.get("telegraph_cost"))
            cca_cost = safe_float(pay_dict.get("cca_cost"))
            pack_fee = safe_float(pay_dict.get("packaging_fee"))
            oth_fee = safe_float(pay_dict.get("other_fees"))
            penalty_fee = safe_float(pay_dict.get("penalty_fee"))
            
            calc_total_cost = (
                safe_float(item["air_freight"]) +
                safe_float(item["fuel_surcharge"]) +
                transit_fee_val +
                cca_cost +
                safe_float(telegraph_cost_val) +
                penalty_fee +
                pack_fee +
                oth_fee +
                safe_float(pay_dict.get("door_pickup_fee")) +
                safe_float(pay_dict.get("airport_pickup_fee")) +
                safe_float(pay_dict.get("delivery_cost"))
            )
        else:
            md = item.get("_md")
            if md:
                telegraph_cost_val = safe_str(md.telegram_fee)
                cca_cost = safe_float(md.cca)
                pack_fee = safe_float(md.packaging_fee)
                oth_fee = safe_float(md.other_fees)

            # 根据来源类型提取件数重量过站费
            if item["source_type"] == "china_southern_air":
                related_lms = csa_lalamoves_map.get(item["source_id"], [])
                gate_pieces_val = str(sum(safe_int(l.pieces) for l in related_lms)) if related_lms else "0"
                transit_weight_val = format_decimal(sum(safe_float(l.weight) for l in related_lms))
                # 假设 transit_rate 不计算，这里直接默认0
                transit_fee_val = 0.0 
            else:
                pass # 深航由于没有相关上下文传递不便完全重算，依赖 financial_audit 数据
                
            # 我们优先尝试从 fa.payable_data 中恢复结果以保持与财务审核单一致
            pay_override = {}
            if fa and fa.payable_data:
                po = fa.payable_data
                if isinstance(po, str):
                    try: po = json.loads(po)
                    except Exception: po = {}
                if isinstance(po, dict):
                    pay_override = po

            gate_pieces_val = pay_override.get("gate_pieces", gate_pieces_val)
            transit_weight_val = pay_override.get("transit_weight", transit_weight_val)
            transit_fee_val = safe_float(pay_override.get("transit_fee", transit_fee_val))
            telegraph_cost_val = pay_override.get("telegraph_cost", telegraph_cost_val)
            cca_cost = safe_float(pay_override.get("cca_cost", cca_cost))
            pack_fee = safe_float(pay_override.get("packaging_fee", pack_fee))
            oth_fee = safe_float(pay_override.get("other_fees", oth_fee))
            penalty_fee = safe_float(pay_override.get("penalty_fee", penalty_fee))
            
            calc_total_cost = safe_float(pay_override.get("total_cost", 0.0))
            if "total_cost" not in pay_override:
                calc_total_cost = (
                    safe_float(item["air_freight"]) +
                    safe_float(item["fuel_surcharge"]) +
                    transit_fee_val +
                    cca_cost +
                    safe_float(telegraph_cost_val) +
                    penalty_fee +
                    pack_fee +
                    oth_fee +
                    safe_float(pay_override.get("door_pickup_fee")) +
                    safe_float(pay_override.get("airport_pickup_fee")) +
                    safe_float(pay_override.get("delivery_cost"))
                )

        result_items.append({
            "source_type": item["source_type"],
            "source_id": str(item["source_id"]),
            "waybill_number": item["waybill_number"],
            "financial_audit_status": fa.financial_audit_status if fa else 0,
            "financial_auditor_name": fa.financial_auditor_name if fa else "",
            "airline_settlement_status": fa.airline_settlement_status if fa else 0,
            "origin": item["origin"],
            "destination": item["destination"],
            "flight_date": item["flight_date"],
            "airline": item["airline"],
            "actual_customer_name": actual_name,
            "flight_number": item["flight_number"],
            "actual_flight_number": item["actual_flight_number"],
            "cargo_name": item["cargo_name"],
            "billing_quantity": safe_str(item["billing_quantity"]),
            "billing_weight": safe_str(item["billing_weight"]),
            "actual_pieces": safe_str(gate_pieces_val),
            "actual_weight": safe_str(transit_weight_val),
            "chargeable_weight": safe_str(item["chargeable_weight"]),
            "freight_rate": safe_str(item["freight_rate"]),
            "air_freight": safe_str(item["air_freight"]),
            "fuel_surcharge": safe_str(item["fuel_surcharge"]),
            "transit_fee": format_decimal(transit_fee_val),
            "telegraph_cost": safe_str(telegraph_cost_val),
            "cca_cost": format_decimal(cca_cost) if cca_cost else "",
            "penalty_fee": format_decimal(penalty_fee) if penalty_fee else "",
            "total_cost": format_decimal(calc_total_cost),
            "airline_settlement_auditor_name": fa.airline_settlement_auditor_name if fa else ""
        })

    return {"code": 0, "data": {"items": result_items, "total": total, "page": query.page, "pageSize": query.pageSize}, "msg": "success"}


@router.post("/air/{source_type}/{source_id}/settle", summary="确认结算航司对账")
def confirm_airline_settlement(
    source_type: str,
    source_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    source_id_int = safe_int(source_id)
    fa = db.query(AirFinancialAuditData).filter(
        AirFinancialAuditData.source_type == source_type,
        or_(
            AirFinancialAuditData.source_id == source_id_int,
            AirFinancialAuditData.id == source_id_int
        )
    ).first()
    
    if not fa:
        # 如果不存在，自动创建
        fa = AirFinancialAuditData(
            source_type=source_type,
            source_id=source_id_int
        )
        db.add(fa)
        
    fa.airline_settlement_status = 1
    fa.airline_settlement_auditor_id = current_user.id
    fa.airline_settlement_auditor_name = current_user.name
    fa.airline_settlement_time = datetime.now()
    
    db.commit()
    return success_response(msg="确认结算成功")


@router.post("/air/{source_type}/{source_id}/cancel-settlement", summary="取消航司对账结算")
def cancel_airline_settlement(
    source_type: str,
    source_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    source_id_int = safe_int(source_id)
    fa = db.query(AirFinancialAuditData).filter(
        AirFinancialAuditData.source_type == source_type,
        or_(
            AirFinancialAuditData.source_id == source_id_int,
            AirFinancialAuditData.id == source_id_int
        )
    ).first()
    
    if not fa:
        raise HTTPException(status_code=404, detail="对账单不存在")
        
    fa.airline_settlement_status = 0
    fa.airline_settlement_auditor_id = None
    fa.airline_settlement_auditor_name = None
    fa.airline_settlement_time = None
    
    db.commit()
    return success_response(msg="取消结算成功")
