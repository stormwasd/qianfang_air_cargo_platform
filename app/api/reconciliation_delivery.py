from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List
from datetime import datetime
import json
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse
from urllib.parse import quote

from app.api.deps import get_db, get_current_active_user
from app.core.response import success_response
from app.utils.helpers import get_china_now
from app.api.financial_audit import format_decimal, safe_float, safe_int, safe_str, parse_csa_flight_info

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

from app.schemas.reconciliation_delivery import (
    DeliveryReconciliationQuery,
    DeliveryReconciliationItemResponse,
    DeliveryReconciliationListResponse,
    DeliveryBatchSettleRequest,
    DeliveryReconciliationExportRequest
)

router = APIRouter()

@router.get("/air", summary="派送单位对账列表查询")
def get_delivery_reconciliation_list(
    query: DeliveryReconciliationQuery = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    fa_base_query = db.query(AirFinancialAuditData)
    if query.financial_audit_status is not None:
        fa_base_query = fa_base_query.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)
    if query.settlement_status is not None:
        fa_base_query = fa_base_query.filter(AirFinancialAuditData.delivery_settlement_status == query.settlement_status)
        
    fa_records = fa_base_query.all()
    fa_map = {}
    for fa in fa_records:
        if fa.source_type not in fa_map:
            fa_map[fa.source_type] = {}
        fa_map[fa.source_type][fa.source_id] = fa
        
    fa_status_filter_active = query.financial_audit_status is not None or query.settlement_status is not None

    candidate_items = []
    
    sz_query = db.query(ShenzhenAirBookingExport, ShenzhenAirDepartureManualData).join(
        ShenzhenAirDepartureManualData, ShenzhenAirBookingExport.id == ShenzhenAirDepartureManualData.booking_export_id
    ).filter(
        ShenzhenAirDepartureManualData.audit_status == 2,
        or_(
            and_(ShenzhenAirDepartureManualData.delivery_fee != None, ShenzhenAirDepartureManualData.delivery_fee != ""),
            and_(ShenzhenAirDepartureManualData.airport_pickup_fee != None, ShenzhenAirDepartureManualData.airport_pickup_fee != "")
        )
    )
    
    if query.waybill_numbers:
        wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
        if wbs:
            or_filters = []
            for wb in wbs:
                if "-" in wb:
                    pref, num = wb.split("-", 1)
                    or_filters.append(and_(ShenzhenAirBookingExport.prefix == pref, ShenzhenAirBookingExport.waybill_number == num))
                else:
                    or_filters.append(ShenzhenAirBookingExport.waybill_number == wb)
            sz_query = sz_query.filter(or_(*or_filters))
            
    if query.flight_date_start:
        sz_query = sz_query.filter(ShenzhenAirBookingExport.flight_date >= query.flight_date_start.replace("-", "/"))
    if query.flight_date_end:
        sz_query = sz_query.filter(ShenzhenAirBookingExport.flight_date <= query.flight_date_end.replace("-", "/"))
    
    if query.delivery_company:
        sz_query = sz_query.filter(ShenzhenAirDepartureManualData.delivery_company.like(f"%{query.delivery_company}%"))
        
    sz_records = sz_query.all()
    for export, md in sz_records:
        fa = fa_map.get("shenzhen_air", {}).get(export.id)
        if fa_status_filter_active and not fa:
            continue
            
        c_name = str(md.customer_name) if md and md.customer_name else ""
        if query.customer_name and query.customer_name not in c_name:
            continue
            
        act_flight = str(export.actual_flight or export.billing_flight or "")
        if query.actual_flight_number and query.actual_flight_number not in act_flight:
            continue
            
        rt_parts = [r.strip() for r in str(export.routing).split("-")] if export.routing and "-" in export.routing else ["", str(export.routing or "")]
        dest = rt_parts[1] if len(rt_parts) > 1 else ""
        
        gate_pieces = "0"
        transit_weight = "0"
        waybill_record = db.query(Waybill).filter(Waybill.waybill_number == export.waybill_number).first()
        if waybill_record:
            transit_loading = waybill_record.transit_loading
            if transit_loading and transit_loading.custom_data:
                try:
                    c_data = json.loads(transit_loading.custom_data) if isinstance(transit_loading.custom_data, str) else transit_loading.custom_data
                    if "gate_pieces" in c_data:
                        gate_pieces = str(c_data["gate_pieces"])
                    if "transit_weight" in c_data:
                        transit_weight = str(c_data["transit_weight"])
                except:
                    pass

        candidate_items.append({
            "source_type": "shenzhen_air",
            "source_id": export.id,
            "flight_date": export.flight_date,
            "waybill_number": f"{export.prefix}-{export.waybill_number}" if export.prefix else export.waybill_number,
            "destination": dest,
            "actual_flight_number": act_flight,
            "actual_pieces": gate_pieces,
            "actual_weight": transit_weight,
            "air_freight": export.air_freight,
            "fuel_surcharge": export.fuel_surcharge,
            "customer_name": c_name,
            "_main": export,
            "_md": md,
            "_fa": fa
        })

    csa_query = db.query(ChinaSouthernAirApprovalData, CsaDepartureManualData).join(
        CsaDepartureManualData, ChinaSouthernAirApprovalData.id == CsaDepartureManualData.approval_data_id
    ).filter(
        CsaDepartureManualData.audit_status == 2,
        or_(
            and_(CsaDepartureManualData.delivery_fee != None, CsaDepartureManualData.delivery_fee != ""),
            and_(CsaDepartureManualData.airport_pickup_fee != None, CsaDepartureManualData.airport_pickup_fee != "")
        )
    )
    
    if query.waybill_numbers:
        wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
        if wbs:
            or_filters = []
            for wb in wbs:
                if "-" in wb:
                    num = wb.split("-", 1)[1]
                    or_filters.append(ChinaSouthernAirApprovalData.waybill_number.like(f"%{num}%"))
                else:
                    or_filters.append(ChinaSouthernAirApprovalData.waybill_number.like(f"%{wb}%"))
            csa_query = csa_query.filter(or_(*or_filters))
            

        
    if query.delivery_company:
        csa_query = csa_query.filter(CsaDepartureManualData.delivery_company.like(f"%{query.delivery_company}%"))
        
    csa_records = csa_query.all()
    
    csa_ids = [r[0].id for r in csa_records]
    csa_lalamoves = db.query(CsaLalamoveInformation).filter(CsaLalamoveInformation.approval_data_id.in_(csa_ids)).all() if csa_ids else []
    csa_lms_map = {}
    for lm in csa_lalamoves:
        csa_lms_map.setdefault(lm.approval_data_id, []).append(lm)

    for approval, md in csa_records:
        fa = fa_map.get("china_southern_air", {}).get(approval.id)
        if fa_status_filter_active and not fa:
            continue
            
        c_name = str(md.customer_name) if md and md.customer_name else ""
        if query.customer_name and query.customer_name not in c_name:
            continue
            
        flight_num, f_date, _, csa_dest = parse_csa_flight_info(approval.flight_info)
        
        if query.flight_date_start and f_date < str(query.flight_date_start):
            continue
        if query.flight_date_end and f_date > str(query.flight_date_end):
            continue
            
        act_flight = str(approval.actual_flight or flight_num)
        
        if query.actual_flight_number and query.actual_flight_number not in act_flight:
            continue

        lms = csa_lms_map.get(approval.id, [])
        gate_pieces = str(sum(safe_int(l.pieces) for l in lms))
        transit_weight = str(sum(safe_float(l.weight) for l in lms))

        candidate_items.append({
            "source_type": "china_southern_air",
            "source_id": approval.id,
            "flight_date": f_date,
            "waybill_number": approval.waybill_number,
            "destination": csa_dest or (approval.booking_routing.split("-")[-1] if approval.booking_routing else ""),
            "actual_flight_number": act_flight,
            "actual_pieces": gate_pieces,
            "actual_weight": transit_weight,
            "air_freight": approval.ref_freight,
            "fuel_surcharge": 0,
            "customer_name": c_name,
            "_main": approval,
            "_md": md,
            "_fa": fa
        })

    peer_query = db.query(ConsignmentNote, PeerAirDepartureManualData).join(
        PeerAirDepartureManualData, ConsignmentNote.id == PeerAirDepartureManualData.consignment_note_id
    ).filter(
        ConsignmentNote.transport_type == "0",
        PeerAirDepartureManualData.audit_status == 2,
        or_(
            and_(PeerAirDepartureManualData.delivery_fee != None, PeerAirDepartureManualData.delivery_fee != ""),
            and_(PeerAirDepartureManualData.airport_pickup_fee != None, PeerAirDepartureManualData.airport_pickup_fee != "")
        )
    )
    
    if query.flight_date_start:
        peer_query = peer_query.filter(ConsignmentNote.consignment_date >= query.flight_date_start)
    if query.flight_date_end:
        peer_query = peer_query.filter(ConsignmentNote.consignment_date <= query.flight_date_end)
        
    if query.waybill_numbers:
        wbs = [w.strip() for w in query.waybill_numbers.split(",") if w.strip()]
        if wbs:
            peer_query = peer_query.filter(PeerAirDepartureManualData.waybill_number.in_(wbs))
            
    if query.delivery_company:
        peer_query = peer_query.filter(PeerAirDepartureManualData.delivery_company.like(f"%{query.delivery_company}%"))
        
    peer_records = peer_query.all()
    for note, md in peer_records:
        fa = fa_map.get("peer_air", {}).get(note.id)
        if fa_status_filter_active and not fa:
            continue
            
        c_name = str(md.customer_name) if md and md.customer_name else ""
        if query.customer_name and query.customer_name not in c_name:
            continue

        try:
            form_dict = json.loads(note.form_data) if note.form_data else {}
        except Exception:
            form_dict = {}

        act_flight = str(form_dict.get("actual_flight") or note.flight_number or "")
        if query.actual_flight_number and query.actual_flight_number not in act_flight:
            continue

        gate_pieces = "0"
        transit_weight = "0"
        peer_air_freight = str(form_dict.get("air_freight") or "")
        peer_fuel_surcharge = ""
        if fa and fa.payable_data:
            po = fa.payable_data
            if isinstance(po, str):
                try: po = json.loads(po)
                except Exception: po = {}
            if isinstance(po, dict):
                gate_pieces = str(po.get("gate_pieces") or "0")
                transit_weight = str(po.get("transit_weight") or "0")
                if "air_freight" in po:
                    peer_air_freight = str(po.get("air_freight") or "")
                if "fuel_surcharge" in po:
                    peer_fuel_surcharge = str(po.get("fuel_surcharge") or "")

        candidate_items.append({
            "source_type": "peer_air",
            "source_id": note.id,
            "flight_date": str(note.consignment_date) if note.consignment_date else "",
            "waybill_number": md.waybill_number if md else "",
            "destination": note.destination or "",
            "actual_flight_number": act_flight,
            "actual_pieces": gate_pieces,
            "actual_weight": transit_weight,
            "air_freight": peer_air_freight,
            "fuel_surcharge": peer_fuel_surcharge,
            "customer_name": c_name,
            "_main": note,
            "_md": md,
            "_fa": fa
        })

    candidate_items.sort(key=lambda x: str(x.get("flight_date", "")), reverse=True)
    
    total_count = len(candidate_items)
    start_idx = (query.page - 1) * query.pageSize
    end_idx = start_idx + query.pageSize
    paged_items = candidate_items[start_idx:end_idx]

    customer_ids = {str(item["customer_name"]) for item in paged_items if str(item.get("customer_name")).isdigit()}
    customer_id_map = {}
    if customer_ids:
        customers = db.query(Customer).filter(Customer.id.in_(customer_ids)).all()
        customer_id_map = {str(c.id): c for c in customers}

    result_items = []
    for item in paged_items:
        fa = item["_fa"]
        md = item["_md"]
        
        financial_audit_status = fa.financial_audit_status if fa else 0
        delivery_settlement_status = fa.delivery_settlement_status if fa else 0
        
        delivery_company = str(md.delivery_company or "")
        delivery_fee = str(md.delivery_fee or "")
        
        pay_override = {}
        if fa and fa.payable_data:
            po = fa.payable_data
            if isinstance(po, str):
                try: po = json.loads(po)
                except Exception: po = {}
            if isinstance(po, dict):
                pay_override = po
                
        calc_total_cost = safe_float(pay_override.get("total_cost", 0.0))
        if "total_cost" not in pay_override:
            transit_fee_val = 0.0
            telegraph_cost_val = safe_float(md.telegram_fee)
            cca_cost = safe_float(md.cca)
            pack_fee = safe_float(md.packaging_fee)
            oth_fee = safe_float(md.other_fees)
            penalty_fee = safe_float(pay_override.get("penalty_fee", 0.0))
            
            calc_total_cost = (
                safe_float(item["air_freight"]) +
                safe_float(item["fuel_surcharge"]) +
                transit_fee_val +
                cca_cost +
                telegraph_cost_val +
                penalty_fee +
                pack_fee +
                oth_fee +
                safe_float(md.door_pickup_fee) +
                safe_float(md.airport_pickup_fee) +
                safe_float(md.delivery_fee) 
            )
            
        airport_pickup_fee = format_decimal(calc_total_cost)

        c_name = str(item.get("customer_name") or "").strip()
        actual_customer_name = customer_id_map[c_name].company_name if c_name in customer_id_map else ""

        result_items.append(DeliveryReconciliationItemResponse(
            source_type=item["source_type"],
            source_id=str(item["source_id"]),
            waybill_number=str(item.get("waybill_number", "")).replace("/", "-"),
            financial_audit_status=financial_audit_status,
            delivery_settlement_status=delivery_settlement_status,
            customer_name=item.get("customer_name", ""),
            actual_customer_name=actual_customer_name,
            delivery_company=delivery_company,
            flight_date=str(item.get("flight_date", "")).replace("/", "-"),
            actual_flight_number=item.get("actual_flight_number", ""),
            destination=item.get("destination", ""),
            actual_pieces=item.get("actual_pieces", "0"),
            actual_weight=item.get("actual_weight", "0"),
            airport_pickup_fee=airport_pickup_fee,
            delivery_fee=delivery_fee
        ))

    return success_response({
        "items": [i.dict() for i in result_items],
        "total": total_count,
        "page": query.page,
        "pageSize": query.pageSize
    })

@router.post("/{source_type}/{source_id}/settle", summary="确认结算派送对账")
def confirm_delivery_settlement(
    source_type: str,
    source_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    fa = db.query(AirFinancialAuditData).filter(
        AirFinancialAuditData.source_type == source_type,
        or_(
            AirFinancialAuditData.source_id == source_id,
            AirFinancialAuditData.id == source_id
        )
    ).first()
    
    if not fa:
        fa = AirFinancialAuditData(
            source_type=source_type,
            source_id=source_id
        )
        db.add(fa)
        
    if fa.delivery_settlement_status == 1:
        return success_response(msg="该单据已经结算过了")
        
    fa.delivery_settlement_status = 1
    fa.delivery_settlement_auditor_id = current_user.id
    fa.delivery_settlement_auditor_name = current_user.name
    fa.delivery_settlement_time = get_china_now()
    
    db.commit()
    return success_response(msg="结算确认成功")

@router.post("/{source_type}/{source_id}/cancel-settlement", summary="取消结算派送对账")
def cancel_delivery_settlement(
    source_type: str,
    source_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    fa = db.query(AirFinancialAuditData).filter(
        AirFinancialAuditData.source_type == source_type,
        or_(
            AirFinancialAuditData.source_id == source_id,
            AirFinancialAuditData.id == source_id
        )
    ).first()
    
    if not fa:
        return success_response(msg="数据不存在，无需取消")
        
    fa.delivery_settlement_status = 0
    fa.delivery_settlement_auditor_id = None
    fa.delivery_settlement_auditor_name = None
    fa.delivery_settlement_time = None
    
    db.commit()
    return success_response(msg="取消结算成功")

@router.post("/batch-settle", summary="批量确认结算派送对账")
def batch_confirm_delivery_settlement(
    req: DeliveryBatchSettleRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    if not req.items:
        return success_response(msg="没有需要结算的单据")

    now = get_china_now()
    
    for item in req.items:
        source_id_int = safe_int(item.source_id)
        fa = db.query(AirFinancialAuditData).filter(
            AirFinancialAuditData.source_type == item.source_type,
            or_(
                AirFinancialAuditData.source_id == source_id_int,
                AirFinancialAuditData.id == source_id_int
            )
        ).first()
        
        if not fa:
            fa = AirFinancialAuditData(
                source_type=item.source_type,
                source_id=source_id_int
            )
            db.add(fa)
            
        fa.delivery_settlement_status = 1
        fa.delivery_settlement_auditor_id = current_user.id
        fa.delivery_settlement_auditor_name = current_user.name
        fa.delivery_settlement_time = now
        
    db.commit()
    return success_response(msg=f"成功批量结算 {len(req.items)} 条单据")

@router.post("/export", summary="导出派送单位对账列表 (选中/批量)")
def export_delivery_reconciliation_list(
    req: DeliveryReconciliationExportRequest,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    query = DeliveryReconciliationQuery(
        waybill_numbers=req.waybill_numbers,
        flight_date_start=req.flight_date_start,
        flight_date_end=req.flight_date_end,
        actual_flight_number=req.actual_flight_number,
        financial_audit_status=req.financial_audit_status,
        customer_name=req.customer_name,
        settlement_status=req.settlement_status,
        delivery_company=req.delivery_company,
        page=1,
        pageSize=999999
    )
    
    result = get_delivery_reconciliation_list(query=query, db=db, current_user=current_user)
    all_items = result.data.get("items", []) if result.data else []
    
    if req.selected_items:
        selected_keys = {(item.source_type, str(item.source_id)) for item in req.selected_items}
        items_to_export = [item for item in all_items if (item["source_type"], str(item["source_id"])) in selected_keys]
    else:
        items_to_export = all_items
        
    if not items_to_export:
        raise HTTPException(status_code=400, detail="没有符合条件的数据可导出")
        
    export_data = []
    
    status_map = {0: "未审核", 1: "暂存", 2: "已审核"}
    settle_map = {0: "未结算", 1: "已结算"}
    
    for idx, item in enumerate(items_to_export, 1):
        export_data.append({
            "序号": idx,
            "运单号": item.get("waybill_number", ""),
            "客户名称": item.get("actual_customer_name", ""),
            "财务审核": status_map.get(item.get("financial_audit_status", 0), "未知"),
            "结算状态": settle_map.get(item.get("delivery_settlement_status", 0), "未知"),
            "派送单位": item.get("delivery_company", ""),
            "航班日期": item.get("flight_date", ""),
            "实走航班号": item.get("actual_flight_number", ""),
            "目的站": item.get("destination", ""),
            "件数": item.get("actual_pieces", ""),
            "重量": item.get("actual_weight", ""),
            "机场提货费": item.get("airport_pickup_fee", ""),
            "派送费": item.get("delivery_fee", "")
        })
        
    df = pd.DataFrame(export_data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='派送单位对账记录')
    output.seek(0)
    
    filename = f"派送单位对账列表_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    encoded_filename = quote(filename)
    
    headers = {
        'Content-Disposition': f'attachment; filename="{encoded_filename}"; filename*=utf-8\'\'{encoded_filename}'
    }
    
    return StreamingResponse(
        output, 
        headers=headers,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
