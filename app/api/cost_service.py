"""
费用登记台 API 接口
"""
import io
from datetime import datetime, date
from typing import List, Optional, Any, Dict

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from fastapi import APIRouter, Depends, Path, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.response import success_response
from app.api.deps import get_current_active_user
from app.models.user import User
from app.models.cost_service import CostRegistration, CostConsignment
from app.schemas.cost_service import (
    CostRegistrationSave,
    CostConsignmentCreate,
    CostConsignmentUpdate,
    CostConsignmentQuery,
    CostBatchDeleteRequest,
    CostExportExcelRequest,
)
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()


def _parse_datetime(val: Any) -> Optional[datetime]:
    """解析日期时间"""
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val_str, fmt)
            except ValueError:
                continue
    return None


def _parse_date(val: Any) -> Optional[date]:
    """解析日期"""
    if not val:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        val_str = val.strip()
        if not val_str:
            return None
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d"):
            try:
                return datetime.strptime(val_str, fmt).date()
            except ValueError:
                continue
    return None


def _format_cost_record(record: Any) -> Dict[str, Any]:
    """将 SQLAlchemy 记录格式化为字典响应格式"""
    if not record:
        return {}
    
    def _to_float(v):
        return float(v) if v is not None else None

    def _to_date_str(v):
        if not v:
            return None
        if isinstance(v, (datetime, date)):
            return v.strftime("%Y-%m-%d")
        return str(v)

    def _to_dt_str(v):
        if not v:
            return None
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d %H:%M:%S")
        return str(v)

    data = {
        "id": str(record.id),
        # (1) 货主委托信息
        "create_time": _to_dt_str(record.create_time),
        "internal_doc_id": record.internal_doc_id or "",
        "warehouse_entry_date": _to_date_str(record.warehouse_entry_date),
        "customer_name": record.customer_name or "",
        "origin_destination": record.origin_destination or "",
        "customs_declaration": record.customs_declaration or "",
        "bill_of_lading": record.bill_of_lading or "",
        "flight_date": _to_date_str(record.flight_date),
        "flight_no": record.flight_no or "",
        "flight_doc_no": record.flight_doc_no or "",
        "pieces": record.pieces,
        "actual_weight": _to_float(record.actual_weight),
        "chargeable_weight": _to_float(record.chargeable_weight),
        "volume": _to_float(record.volume),
        "first_leg_weight": _to_float(record.first_leg_weight),
        "agent": record.agent or "",
        "remark": record.remark or "",
        
        # (2) 应收款项
        "unit_price": _to_float(record.unit_price),
        "receivable_freight": _to_float(record.receivable_freight),
        "receivable_lading_info_fee": _to_float(record.receivable_lading_info_fee),
        "receivable_split_offset_telex_fee": _to_float(record.receivable_split_offset_telex_fee),
        "receivable_customs_fee": _to_float(record.receivable_customs_fee),
        "receivable_continuation_sheet_fee": _to_float(record.receivable_continuation_sheet_fee),
        "receivable_customs_inspection_fee": _to_float(record.receivable_customs_inspection_fee),
        "receivable_magnetic_security_fee": _to_float(record.receivable_magnetic_security_fee),
        "receivable_tc_express_fee": _to_float(record.receivable_tc_express_fee),
        "receivable_warehouse_ground_fee": _to_float(record.receivable_warehouse_ground_fee),
        "receivable_doc_make_fee": _to_float(record.receivable_doc_make_fee),
        "receivable_doc_split_fee": _to_float(record.receivable_doc_split_fee),
        "receivable_skid_fee": _to_float(record.receivable_skid_fee),
        "receivable_pallet_packing_fee": _to_float(record.receivable_pallet_packing_fee),
        "receivable_probe_fee": _to_float(record.receivable_probe_fee),
        "receivable_consumables_fee": _to_float(record.receivable_consumables_fee),
        "receivable_first_leg_fee": _to_float(record.receivable_first_leg_fee),
        "receivable_total": _to_float(record.receivable_total),
        "receivable_agent": record.receivable_agent or "",
        
        # (3) 应付款项 - [1] 国际空运信息
        "pay_intl_air_subtotal": _to_float(record.pay_intl_air_subtotal),
        "pay_intl_air_date": _to_date_str(record.pay_intl_air_date),
        "pay_intl_air_outsource_unit": record.pay_intl_air_outsource_unit or "",
        "pay_intl_air_origin": record.pay_intl_air_origin or "",
        "pay_intl_air_destination": record.pay_intl_air_destination or "",
        "pay_intl_air_airline": record.pay_intl_air_airline or "",
        "pay_intl_air_flight_doc_no": record.pay_intl_air_flight_doc_no or "",
        "pay_intl_air_flight_no": record.pay_intl_air_flight_no or "",
        "pay_intl_air_flight_date": _to_date_str(record.pay_intl_air_flight_date),
        "pay_intl_air_pieces": record.pay_intl_air_pieces,
        "pay_intl_air_weight": _to_float(record.pay_intl_air_weight),
        "pay_intl_air_volume": _to_float(record.pay_intl_air_volume),
        "pay_intl_air_chargeable_weight": _to_float(record.pay_intl_air_chargeable_weight),
        "pay_intl_air_rate": _to_float(record.pay_intl_air_rate),
        "pay_intl_air_freight": _to_float(record.pay_intl_air_freight),
        "pay_intl_air_lading_fee": _to_float(record.pay_intl_air_lading_fee),
        "pay_intl_air_split_fee": _to_float(record.pay_intl_air_split_fee),
        "pay_intl_air_borrow_magnetic_fuel_pickup_fee": _to_float(record.pay_intl_air_borrow_magnetic_fuel_pickup_fee),
        "pay_intl_air_tc_network_disposal_fee": _to_float(record.pay_intl_air_tc_network_disposal_fee),
        "pay_intl_air_customs_fee": _to_float(record.pay_intl_air_customs_fee),
        "pay_intl_air_continuation_sheet_fee": _to_float(record.pay_intl_air_continuation_sheet_fee),
        "pay_intl_air_consumables_fee": _to_float(record.pay_intl_air_consumables_fee),
        "pay_intl_air_front_warehouse": _to_float(record.pay_intl_air_front_warehouse),
        "pay_intl_air_other_fee": _to_float(record.pay_intl_air_other_fee),
        "pay_intl_air_remark": record.pay_intl_air_remark or "",
        
        # (3) 应付款项 - [2] 汽运信息
        "pay_trucking_subtotal": _to_float(record.pay_trucking_subtotal),
        "pay_trucking_date": _to_date_str(record.pay_trucking_date),
        "pay_trucking_outsource_unit": record.pay_trucking_outsource_unit or "",
        "pay_trucking_pieces": record.pay_trucking_pieces,
        "pay_trucking_weight": _to_float(record.pay_trucking_weight),
        "pay_trucking_volume": _to_float(record.pay_trucking_volume),
        "pay_trucking_unit_price": _to_float(record.pay_trucking_unit_price),
        "pay_trucking_freight": _to_float(record.pay_trucking_freight),
        "pay_trucking_doc_fee": _to_float(record.pay_trucking_doc_fee),
        "pay_trucking_other_fee": _to_float(record.pay_trucking_other_fee),
        "pay_trucking_remark": record.pay_trucking_remark or "",
        
        # (3) 应付款项 - [3] 国内空运信息
        "pay_dom_air_subtotal": _to_float(record.pay_dom_air_subtotal),
        "pay_dom_air_date": _to_date_str(record.pay_dom_air_date),
        "pay_dom_air_outsource_unit": record.pay_dom_air_outsource_unit or "",
        "pay_dom_air_origin": record.pay_dom_air_origin or "",
        "pay_dom_air_destination": record.pay_dom_air_destination or "",
        "pay_dom_air_airline": record.pay_dom_air_airline or "",
        "pay_dom_air_airline_unit": record.pay_dom_air_airline_unit or "",
        "pay_dom_air_flight_doc_no": record.pay_dom_air_flight_doc_no or "",
        "pay_dom_air_flight_no": record.pay_dom_air_flight_no or "",
        "pay_dom_air_flight_date": _to_date_str(record.pay_dom_air_flight_date),
        "pay_dom_air_pieces": record.pay_dom_air_pieces,
        "pay_dom_air_weight": _to_float(record.pay_dom_air_weight),
        "pay_dom_air_chargeable_weight": _to_float(record.pay_dom_air_chargeable_weight),
        "pay_dom_air_rate": _to_float(record.pay_dom_air_rate),
        "pay_dom_air_freight": _to_float(record.pay_dom_air_freight),
        "pay_dom_air_other_fee": _to_float(record.pay_dom_air_other_fee),
        "pay_dom_air_remark": record.pay_dom_air_remark or "",
        
        # (3) 应付款项 - [4] 报关信息
        "pay_customs_subtotal": _to_float(record.pay_customs_subtotal),
        "pay_customs_date": _to_date_str(record.pay_customs_date),
        "pay_customs_agent": record.pay_customs_agent or "",
        "pay_customs_fee": _to_float(record.pay_customs_fee),
        "pay_customs_continuation_sheet_fee": _to_float(record.pay_customs_continuation_sheet_fee),
        "pay_customs_inspection_delete_fee": _to_float(record.pay_customs_inspection_delete_fee),
        "pay_customs_rebate": _to_float(record.pay_customs_rebate),
        "pay_customs_other_fee": _to_float(record.pay_customs_other_fee),
        "pay_customs_remark": record.pay_customs_remark or "",
        
        # (3) 应付款项 - [5] 地面操作信息
        "pay_ground_subtotal": _to_float(record.pay_ground_subtotal),
        "pay_ground_date": _to_date_str(record.pay_ground_date),
        "pay_ground_outsource_unit": record.pay_ground_outsource_unit or "",
        "pay_ground_chargeable_weight": _to_float(record.pay_ground_chargeable_weight),
        "pay_ground_rate": _to_float(record.pay_ground_rate),
        "pay_ground_freight": _to_float(record.pay_ground_freight),
        "pay_ground_lading_express_fee": _to_float(record.pay_ground_lading_express_fee),
        "pay_ground_security_customs_fee": _to_float(record.pay_ground_security_customs_fee),
        "pay_ground_pallet_exit_fee": _to_float(record.pay_ground_pallet_exit_fee),
        "pay_ground_other_fee": _to_float(record.pay_ground_other_fee),
        "pay_ground_remark": record.pay_ground_remark or "",
        
        # (3) 应付款项 - 合计
        "pay_total": _to_float(record.pay_total),
        
        # (4) 销售提成
        "salesperson": record.salesperson or "",
        "commission_amount": _to_float(record.commission_amount),
        
        # (5) 经营信息
        "profit": _to_float(record.profit),
        "profit_margin": _to_float(record.profit_margin),
        
        "created_at": format_datetime_china(record.created_at),
        "updated_at": format_datetime_china(record.updated_at),
    }
    if hasattr(record, "creator_id") and record.creator_id:
        data["creator_id"] = str(record.creator_id)
    return data


def _apply_cost_payload(record: Any, payload: CostRegistrationSave):
    """将 Payload 属性赋值到 ORM 模型对象"""
    # (1) 货主委托信息
    record.create_time = _parse_datetime(payload.create_time) if payload.create_time is not None else record.create_time
    record.internal_doc_id = payload.internal_doc_id if payload.internal_doc_id is not None else record.internal_doc_id
    record.warehouse_entry_date = _parse_date(payload.warehouse_entry_date) if payload.warehouse_entry_date is not None else record.warehouse_entry_date
    record.customer_name = payload.customer_name if payload.customer_name is not None else record.customer_name
    record.origin_destination = payload.origin_destination if payload.origin_destination is not None else record.origin_destination
    record.customs_declaration = payload.customs_declaration if payload.customs_declaration is not None else record.customs_declaration
    record.bill_of_lading = payload.bill_of_lading if payload.bill_of_lading is not None else record.bill_of_lading
    record.flight_date = _parse_date(payload.flight_date) if payload.flight_date is not None else record.flight_date
    record.flight_no = payload.flight_no if payload.flight_no is not None else record.flight_no
    record.flight_doc_no = payload.flight_doc_no if payload.flight_doc_no is not None else record.flight_doc_no
    record.pieces = payload.pieces if payload.pieces is not None else record.pieces
    record.actual_weight = payload.actual_weight if payload.actual_weight is not None else record.actual_weight
    record.chargeable_weight = payload.chargeable_weight if payload.chargeable_weight is not None else record.chargeable_weight
    record.volume = payload.volume if payload.volume is not None else record.volume
    record.first_leg_weight = payload.first_leg_weight if payload.first_leg_weight is not None else record.first_leg_weight
    record.agent = payload.agent if payload.agent is not None else record.agent
    record.remark = payload.remark if payload.remark is not None else record.remark

    # (2) 应收款项
    record.unit_price = payload.unit_price if payload.unit_price is not None else record.unit_price
    record.receivable_freight = payload.receivable_freight if payload.receivable_freight is not None else record.receivable_freight
    record.receivable_lading_info_fee = payload.receivable_lading_info_fee if payload.receivable_lading_info_fee is not None else record.receivable_lading_info_fee
    record.receivable_split_offset_telex_fee = payload.receivable_split_offset_telex_fee if payload.receivable_split_offset_telex_fee is not None else record.receivable_split_offset_telex_fee
    record.receivable_customs_fee = payload.receivable_customs_fee if payload.receivable_customs_fee is not None else record.receivable_customs_fee
    record.receivable_continuation_sheet_fee = payload.receivable_continuation_sheet_fee if payload.receivable_continuation_sheet_fee is not None else record.receivable_continuation_sheet_fee
    record.receivable_customs_inspection_fee = payload.receivable_customs_inspection_fee if payload.receivable_customs_inspection_fee is not None else record.receivable_customs_inspection_fee
    record.receivable_magnetic_security_fee = payload.receivable_magnetic_security_fee if payload.receivable_magnetic_security_fee is not None else record.receivable_magnetic_security_fee
    record.receivable_tc_express_fee = payload.receivable_tc_express_fee if payload.receivable_tc_express_fee is not None else record.receivable_tc_express_fee
    record.receivable_warehouse_ground_fee = payload.receivable_warehouse_ground_fee if payload.receivable_warehouse_ground_fee is not None else record.receivable_warehouse_ground_fee
    record.receivable_doc_make_fee = payload.receivable_doc_make_fee if payload.receivable_doc_make_fee is not None else record.receivable_doc_make_fee
    record.receivable_doc_split_fee = payload.receivable_doc_split_fee if payload.receivable_doc_split_fee is not None else record.receivable_doc_split_fee
    record.receivable_skid_fee = payload.receivable_skid_fee if payload.receivable_skid_fee is not None else record.receivable_skid_fee
    record.receivable_pallet_packing_fee = payload.receivable_pallet_packing_fee if payload.receivable_pallet_packing_fee is not None else record.receivable_pallet_packing_fee
    record.receivable_probe_fee = payload.receivable_probe_fee if payload.receivable_probe_fee is not None else record.receivable_probe_fee
    record.receivable_consumables_fee = payload.receivable_consumables_fee if payload.receivable_consumables_fee is not None else record.receivable_consumables_fee
    record.receivable_first_leg_fee = payload.receivable_first_leg_fee if payload.receivable_first_leg_fee is not None else record.receivable_first_leg_fee
    record.receivable_total = payload.receivable_total if payload.receivable_total is not None else record.receivable_total
    record.receivable_agent = payload.receivable_agent if payload.receivable_agent is not None else record.receivable_agent

    # (3) 应付款项 - [1] 国际空运
    record.pay_intl_air_subtotal = payload.pay_intl_air_subtotal if payload.pay_intl_air_subtotal is not None else record.pay_intl_air_subtotal
    record.pay_intl_air_date = _parse_date(payload.pay_intl_air_date) if payload.pay_intl_air_date is not None else record.pay_intl_air_date
    record.pay_intl_air_outsource_unit = payload.pay_intl_air_outsource_unit if payload.pay_intl_air_outsource_unit is not None else record.pay_intl_air_outsource_unit
    record.pay_intl_air_origin = payload.pay_intl_air_origin if payload.pay_intl_air_origin is not None else record.pay_intl_air_origin
    record.pay_intl_air_destination = payload.pay_intl_air_destination if payload.pay_intl_air_destination is not None else record.pay_intl_air_destination
    record.pay_intl_air_airline = payload.pay_intl_air_airline if payload.pay_intl_air_airline is not None else record.pay_intl_air_airline
    record.pay_intl_air_flight_doc_no = payload.pay_intl_air_flight_doc_no if payload.pay_intl_air_flight_doc_no is not None else record.pay_intl_air_flight_doc_no
    record.pay_intl_air_flight_no = payload.pay_intl_air_flight_no if payload.pay_intl_air_flight_no is not None else record.pay_intl_air_flight_no
    record.pay_intl_air_flight_date = _parse_date(payload.pay_intl_air_flight_date) if payload.pay_intl_air_flight_date is not None else record.pay_intl_air_flight_date
    record.pay_intl_air_pieces = payload.pay_intl_air_pieces if payload.pay_intl_air_pieces is not None else record.pay_intl_air_pieces
    record.pay_intl_air_weight = payload.pay_intl_air_weight if payload.pay_intl_air_weight is not None else record.pay_intl_air_weight
    record.pay_intl_air_volume = payload.pay_intl_air_volume if payload.pay_intl_air_volume is not None else record.pay_intl_air_volume
    record.pay_intl_air_chargeable_weight = payload.pay_intl_air_chargeable_weight if payload.pay_intl_air_chargeable_weight is not None else record.pay_intl_air_chargeable_weight
    record.pay_intl_air_rate = payload.pay_intl_air_rate if payload.pay_intl_air_rate is not None else record.pay_intl_air_rate
    record.pay_intl_air_freight = payload.pay_intl_air_freight if payload.pay_intl_air_freight is not None else record.pay_intl_air_freight
    record.pay_intl_air_lading_fee = payload.pay_intl_air_lading_fee if payload.pay_intl_air_lading_fee is not None else record.pay_intl_air_lading_fee
    record.pay_intl_air_split_fee = payload.pay_intl_air_split_fee if payload.pay_intl_air_split_fee is not None else record.pay_intl_air_split_fee
    record.pay_intl_air_borrow_magnetic_fuel_pickup_fee = payload.pay_intl_air_borrow_magnetic_fuel_pickup_fee if payload.pay_intl_air_borrow_magnetic_fuel_pickup_fee is not None else record.pay_intl_air_borrow_magnetic_fuel_pickup_fee
    record.pay_intl_air_tc_network_disposal_fee = payload.pay_intl_air_tc_network_disposal_fee if payload.pay_intl_air_tc_network_disposal_fee is not None else record.pay_intl_air_tc_network_disposal_fee
    record.pay_intl_air_customs_fee = payload.pay_intl_air_customs_fee if payload.pay_intl_air_customs_fee is not None else record.pay_intl_air_customs_fee
    record.pay_intl_air_continuation_sheet_fee = payload.pay_intl_air_continuation_sheet_fee if payload.pay_intl_air_continuation_sheet_fee is not None else record.pay_intl_air_continuation_sheet_fee
    record.pay_intl_air_consumables_fee = payload.pay_intl_air_consumables_fee if payload.pay_intl_air_consumables_fee is not None else record.pay_intl_air_consumables_fee
    record.pay_intl_air_front_warehouse = payload.pay_intl_air_front_warehouse if payload.pay_intl_air_front_warehouse is not None else record.pay_intl_air_front_warehouse
    record.pay_intl_air_other_fee = payload.pay_intl_air_other_fee if payload.pay_intl_air_other_fee is not None else record.pay_intl_air_other_fee
    record.pay_intl_air_remark = payload.pay_intl_air_remark if payload.pay_intl_air_remark is not None else record.pay_intl_air_remark

    # (3) 应付款项 - [2] 汽运
    record.pay_trucking_subtotal = payload.pay_trucking_subtotal if payload.pay_trucking_subtotal is not None else record.pay_trucking_subtotal
    record.pay_trucking_date = _parse_date(payload.pay_trucking_date) if payload.pay_trucking_date is not None else record.pay_trucking_date
    record.pay_trucking_outsource_unit = payload.pay_trucking_outsource_unit if payload.pay_trucking_outsource_unit is not None else record.pay_trucking_outsource_unit
    record.pay_trucking_pieces = payload.pay_trucking_pieces if payload.pay_trucking_pieces is not None else record.pay_trucking_pieces
    record.pay_trucking_weight = payload.pay_trucking_weight if payload.pay_trucking_weight is not None else record.pay_trucking_weight
    record.pay_trucking_volume = payload.pay_trucking_volume if payload.pay_trucking_volume is not None else record.pay_trucking_volume
    record.pay_trucking_unit_price = payload.pay_trucking_unit_price if payload.pay_trucking_unit_price is not None else record.pay_trucking_unit_price
    record.pay_trucking_freight = payload.pay_trucking_freight if payload.pay_trucking_freight is not None else record.pay_trucking_freight
    record.pay_trucking_doc_fee = payload.pay_trucking_doc_fee if payload.pay_trucking_doc_fee is not None else record.pay_trucking_doc_fee
    record.pay_trucking_other_fee = payload.pay_trucking_other_fee if payload.pay_trucking_other_fee is not None else record.pay_trucking_other_fee
    record.pay_trucking_remark = payload.pay_trucking_remark if payload.pay_trucking_remark is not None else record.pay_trucking_remark

    # (3) 应付款项 - [3] 国内空运
    record.pay_dom_air_subtotal = payload.pay_dom_air_subtotal if payload.pay_dom_air_subtotal is not None else record.pay_dom_air_subtotal
    record.pay_dom_air_date = _parse_date(payload.pay_dom_air_date) if payload.pay_dom_air_date is not None else record.pay_dom_air_date
    record.pay_dom_air_outsource_unit = payload.pay_dom_air_outsource_unit if payload.pay_dom_air_outsource_unit is not None else record.pay_dom_air_outsource_unit
    record.pay_dom_air_origin = payload.pay_dom_air_origin if payload.pay_dom_air_origin is not None else record.pay_dom_air_origin
    record.pay_dom_air_destination = payload.pay_dom_air_destination if payload.pay_dom_air_destination is not None else record.pay_dom_air_destination
    record.pay_dom_air_airline = payload.pay_dom_air_airline if payload.pay_dom_air_airline is not None else record.pay_dom_air_airline
    record.pay_dom_air_airline_unit = payload.pay_dom_air_airline_unit if payload.pay_dom_air_airline_unit is not None else record.pay_dom_air_airline_unit
    record.pay_dom_air_flight_doc_no = payload.pay_dom_air_flight_doc_no if payload.pay_dom_air_flight_doc_no is not None else record.pay_dom_air_flight_doc_no
    record.pay_dom_air_flight_no = payload.pay_dom_air_flight_no if payload.pay_dom_air_flight_no is not None else record.pay_dom_air_flight_no
    record.pay_dom_air_flight_date = _parse_date(payload.pay_dom_air_flight_date) if payload.pay_dom_air_flight_date is not None else record.pay_dom_air_flight_date
    record.pay_dom_air_pieces = payload.pay_dom_air_pieces if payload.pay_dom_air_pieces is not None else record.pay_dom_air_pieces
    record.pay_dom_air_weight = payload.pay_dom_air_weight if payload.pay_dom_air_weight is not None else record.pay_dom_air_weight
    record.pay_dom_air_chargeable_weight = payload.pay_dom_air_chargeable_weight if payload.pay_dom_air_chargeable_weight is not None else record.pay_dom_air_chargeable_weight
    record.pay_dom_air_rate = payload.pay_dom_air_rate if payload.pay_dom_air_rate is not None else record.pay_dom_air_rate
    record.pay_dom_air_freight = payload.pay_dom_air_freight if payload.pay_dom_air_freight is not None else record.pay_dom_air_freight
    record.pay_dom_air_other_fee = payload.pay_dom_air_other_fee if payload.pay_dom_air_other_fee is not None else record.pay_dom_air_other_fee
    record.pay_dom_air_remark = payload.pay_dom_air_remark if payload.pay_dom_air_remark is not None else record.pay_dom_air_remark

    # (3) 应付款项 - [4] 报关信息
    record.pay_customs_subtotal = payload.pay_customs_subtotal if payload.pay_customs_subtotal is not None else record.pay_customs_subtotal
    record.pay_customs_date = _parse_date(payload.pay_customs_date) if payload.pay_customs_date is not None else record.pay_customs_date
    record.pay_customs_agent = payload.pay_customs_agent if payload.pay_customs_agent is not None else record.pay_customs_agent
    record.pay_customs_fee = payload.pay_customs_fee if payload.pay_customs_fee is not None else record.pay_customs_fee
    record.pay_customs_continuation_sheet_fee = payload.pay_customs_continuation_sheet_fee if payload.pay_customs_continuation_sheet_fee is not None else record.pay_customs_continuation_sheet_fee
    record.pay_customs_inspection_delete_fee = payload.pay_customs_inspection_delete_fee if payload.pay_customs_inspection_delete_fee is not None else record.pay_customs_inspection_delete_fee
    record.pay_customs_rebate = payload.pay_customs_rebate if payload.pay_customs_rebate is not None else record.pay_customs_rebate
    record.pay_customs_other_fee = payload.pay_customs_other_fee if payload.pay_customs_other_fee is not None else record.pay_customs_other_fee
    record.pay_customs_remark = payload.pay_customs_remark if payload.pay_customs_remark is not None else record.pay_customs_remark

    # (3) 应付款项 - [5] 地面操作信息
    record.pay_ground_subtotal = payload.pay_ground_subtotal if payload.pay_ground_subtotal is not None else record.pay_ground_subtotal
    record.pay_ground_date = _parse_date(payload.pay_ground_date) if payload.pay_ground_date is not None else record.pay_ground_date
    record.pay_ground_outsource_unit = payload.pay_ground_outsource_unit if payload.pay_ground_outsource_unit is not None else record.pay_ground_outsource_unit
    record.pay_ground_chargeable_weight = payload.pay_ground_chargeable_weight if payload.pay_ground_chargeable_weight is not None else record.pay_ground_chargeable_weight
    record.pay_ground_rate = payload.pay_ground_rate if payload.pay_ground_rate is not None else record.pay_ground_rate
    record.pay_ground_freight = payload.pay_ground_freight if payload.pay_ground_freight is not None else record.pay_ground_freight
    record.pay_ground_lading_express_fee = payload.pay_ground_lading_express_fee if payload.pay_ground_lading_express_fee is not None else record.pay_ground_lading_express_fee
    record.pay_ground_security_customs_fee = payload.pay_ground_security_customs_fee if payload.pay_ground_security_customs_fee is not None else record.pay_ground_security_customs_fee
    record.pay_ground_pallet_exit_fee = payload.pay_ground_pallet_exit_fee if payload.pay_ground_pallet_exit_fee is not None else record.pay_ground_pallet_exit_fee
    record.pay_ground_other_fee = payload.pay_ground_other_fee if payload.pay_ground_other_fee is not None else record.pay_ground_other_fee
    record.pay_ground_remark = payload.pay_ground_remark if payload.pay_ground_remark is not None else record.pay_ground_remark

    # (3) 应付款项 - 合计
    record.pay_total = payload.pay_total if payload.pay_total is not None else record.pay_total

    # (4) 销售提成
    record.salesperson = payload.salesperson if payload.salesperson is not None else record.salesperson
    record.commission_amount = payload.commission_amount if payload.commission_amount is not None else record.commission_amount

    # (5) 经营信息
    record.profit = payload.profit if payload.profit is not None else record.profit
    record.profit_margin = payload.profit_margin if payload.profit_margin is not None else record.profit_margin


# ============================================================================
# 1. 费用信息登记接口（系统唯一一条数据，支持编辑和保存）
# ============================================================================

@router.get("/cost-registration", summary="获取费用信息登记数据（系统唯一数据）")
async def get_cost_registration(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取系统当前维护的唯一一条费用信息登记模版数据。
    若系统尚未保存过该数据，则 data 返回 null。
    """
    record = db.query(CostRegistration).first()
    if not record:
        return success_response(data=None, msg="暂无费用信息登记数据")
    
    return success_response(data=_format_cost_record(record), msg="查询成功")


@router.put("/cost-registration", summary="编辑并保存费用信息登记数据（系统唯一数据）")
async def save_cost_registration(
    payload: CostRegistrationSave,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    保存/编辑费用信息登记接口（Upsert 操作）。
    系统整体仅维护一条数据，若不存在则新建，若存在则更新。
    """
    record = db.query(CostRegistration).first()
    
    if record:
        _apply_cost_payload(record, payload)
        db.commit()
        db.refresh(record)
        msg = "费用信息登记更新成功"
    else:
        record = CostRegistration()
        _apply_cost_payload(record, payload)
        db.add(record)
        db.commit()
        db.refresh(record)
        msg = "费用信息登记保存成功"

    return success_response(data=_format_cost_record(record), msg=msg)


# ============================================================================
# 2. 单据信息-新增
# ============================================================================

@router.post("/consignments", summary="单据信息-新增")
async def create_cost_consignment(
    payload: CostConsignmentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增一条费用单据记录。
    """
    new_record = CostConsignment(creator_id=current_user.id)
    _apply_cost_payload(new_record, payload)
    
    # 若制单时间未传入，自动填充当前时间
    if not new_record.create_time:
        new_record.create_time = get_china_now()

    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    
    return success_response(data=_format_cost_record(new_record), msg="单据信息创建成功")


# ============================================================================
# 3. 单据信息-列表（支持进仓日期区间、客户名称、代理单位、航司单号、航班号等条件查询及分页）
# ============================================================================

@router.get("/consignments", summary="单据信息-列表")
async def get_cost_consignments(
    start_warehouse_date: Optional[str] = Query(None, description="进仓开始日期 (YYYY-MM-DD)"),
    end_warehouse_date: Optional[str] = Query(None, description="进仓结束日期 (YYYY-MM-DD)"),
    customer_name: Optional[str] = Query(None, description="客户名称 (模糊查询)"),
    agent: Optional[str] = Query(None, description="代理单位 (模糊查询)"),
    flight_doc_no: Optional[str] = Query(None, description="航司单号/航班单号 (模糊查询)"),
    flight_no: Optional[str] = Query(None, description="航班号 (模糊查询)"),
    page: Optional[int] = Query(1, ge=1, description="页码"),
    pageSize: Optional[int] = Query(10, ge=1, description="每页数量"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    单据信息列表查询接口。
    
    支持参数：
    - **start_warehouse_date**: 进仓日期区间开始，例如 '2026-07-25'
    - **end_warehouse_date**: 进仓日期区间结束，例如 '2026-07-30'
    - **customer_name**: 客户名称 (支持模糊匹配)
    - **agent**: 代理单位 (支持模糊匹配)
    - **flight_doc_no**: 航司单号/航班单号 (支持模糊匹配)
    - **flight_no**: 航班号 (支持模糊匹配)
    - **page**: 页码
    - **pageSize**: 每页条数
    """
    query_obj = db.query(CostConsignment)
    
    # 1. 进仓日期区间筛选
    if start_warehouse_date:
        s_date = _parse_date(start_warehouse_date)
        if s_date:
            query_obj = query_obj.filter(CostConsignment.warehouse_entry_date >= s_date)
            
    if end_warehouse_date:
        e_date = _parse_date(end_warehouse_date)
        if e_date:
            query_obj = query_obj.filter(CostConsignment.warehouse_entry_date <= e_date)
            
    # 2. 客户名称模糊查询
    if customer_name and customer_name.strip():
        query_obj = query_obj.filter(CostConsignment.customer_name.like(f"%{customer_name.strip()}%"))
        
    # 3. 代理单位模糊查询
    if agent and agent.strip():
        query_obj = query_obj.filter(CostConsignment.agent.like(f"%{agent.strip()}%"))
        
    # 4. 航司单号/航班单号模糊查询
    if flight_doc_no and flight_doc_no.strip():
        doc_no = flight_doc_no.strip()
        query_obj = query_obj.filter(
            (CostConsignment.flight_doc_no.like(f"%{doc_no}%")) |
            (CostConsignment.bill_of_lading.like(f"%{doc_no}%")) |
            (CostConsignment.pay_intl_air_flight_doc_no.like(f"%{doc_no}%")) |
            (CostConsignment.pay_dom_air_flight_doc_no.like(f"%{doc_no}%"))
        )
        
    # 5. 航班号模糊查询
    if flight_no and flight_no.strip():
        f_no = flight_no.strip()
        query_obj = query_obj.filter(
            (CostConsignment.flight_no.like(f"%{f_no}%")) |
            (CostConsignment.pay_intl_air_flight_no.like(f"%{f_no}%")) |
            (CostConsignment.pay_dom_air_flight_no.like(f"%{f_no}%"))
        )
            
    total = query_obj.count()
    
    # 排序：进仓日期倒序，其次制单时间倒序，其次ID倒序
    query_obj = query_obj.order_by(
        CostConsignment.warehouse_entry_date.desc(),
        CostConsignment.create_time.desc(),
        CostConsignment.id.desc()
    )
    
    # 分页
    if page is not None and pageSize is not None:
        offset = (page - 1) * pageSize
        records = query_obj.offset(offset).limit(pageSize).all()
    else:
        records = query_obj.all()
        
    items = [_format_cost_record(r) for r in records]
    
    return success_response(
        data={"total": total, "items": items, "page": page, "pageSize": pageSize},
        msg="查询成功"
    )


# ============================================================================
# 单据信息-详情
# ============================================================================

@router.get("/consignments/{consignment_id}", summary="单据信息-详情")
async def get_cost_consignment_detail(
    consignment_id: str = Path(..., description="单据明细ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取单条费用单据详情接口"""
    try:
        c_id = int(consignment_id)
    except ValueError:
        raise BadRequestException("consignment_id 必须为合法数字格式")
        
    record = db.query(CostConsignment).filter(CostConsignment.id == c_id).first()
    if not record:
        raise NotFoundException(f"单据信息不存在 (ID: {consignment_id})")
        
    return success_response(data=_format_cost_record(record), msg="查询成功")


# ============================================================================
# 5. 单据信息-修改
# ============================================================================

@router.put("/consignments/{consignment_id}", summary="单据信息-修改")
async def update_cost_consignment(
    payload: CostConsignmentUpdate,
    consignment_id: str = Path(..., description="单据明细ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    修改指定 ID 的费用单据信息接口。
    """
    try:
        c_id = int(consignment_id)
    except ValueError:
        raise BadRequestException("consignment_id 必须为合法数字格式")
        
    record = db.query(CostConsignment).filter(CostConsignment.id == c_id).first()
    if not record:
        raise NotFoundException(f"单据信息不存在 (ID: {consignment_id})")
        
    _apply_cost_payload(record, payload)
    db.commit()
    db.refresh(record)
    
    return success_response(data=_format_cost_record(record), msg="单据信息更新成功")


# ============================================================================
# 4. 单据信息-删除 (批量删除与单个删除)
# ============================================================================

@router.post("/consignments/batch-delete", summary="单据信息-批量删除 (POST)")
@router.delete("/consignments/batch-delete", summary="单据信息-批量删除 (DELETE)")
async def batch_delete_cost_consignments(
    payload: CostBatchDeleteRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    批量删除费用单据接口（同时支持 POST 与 DELETE 方法）。
    
    传入 JSON 数组：`{"ids": ["123", "456"]}`
    """
    if not payload.ids:
        raise BadRequestException("待删除的 ID 数组不能为空")
        
    int_ids = []
    for raw_id in payload.ids:
        try:
            int_ids.append(int(raw_id))
        except ValueError:
            raise BadRequestException(f"ID '{raw_id}' 格式无效")
            
    deleted_count = db.query(CostConsignment).filter(CostConsignment.id.in_(int_ids)).delete(synchronize_session=False)
    db.commit()
    
    return success_response(
        data={"deleted_count": deleted_count, "requested_ids": payload.ids},
        msg=f"成功批量删除 {deleted_count} 条单据信息记录"
    )


@router.delete("/consignments/{consignment_id}", summary="单据信息-删除（单个）")
async def delete_cost_consignment(
    consignment_id: str = Path(..., description="单据明细ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """单个删除费用单据接口"""
    try:
        c_id = int(consignment_id)
    except ValueError:
        raise BadRequestException("consignment_id 必须为合法数字格式")
        
    record = db.query(CostConsignment).filter(CostConsignment.id == c_id).first()
    if not record:
        raise NotFoundException(f"单据信息不存在 (ID: {consignment_id})")
        
    db.delete(record)
    db.commit()
    
    return success_response(data={"id": consignment_id}, msg="单据信息删除成功")


# ============================================================================
# 6. 单据信息-选中下载为 excel
# ============================================================================

@router.post("/consignments/export-excel", summary="单据信息-选中下载为excel")
async def export_cost_consignments_to_excel(
    payload: CostExportExcelRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    选中费用单据列表中的某些项导出为 Excel (.xlsx) 表格文件。
    
    传入选中的 ID 数组：`{"ids": ["123", "456"]}`
    """
    if not payload.ids:
        raise BadRequestException("请选择至少一条需导出的单据记录")
        
    int_ids = []
    for raw_id in payload.ids:
        try:
            int_ids.append(int(raw_id))
        except ValueError:
            raise BadRequestException(f"ID '{raw_id}' 格式无效")
            
    records = db.query(CostConsignment).filter(CostConsignment.id.in_(int_ids)).order_by(CostConsignment.warehouse_entry_date.desc()).all()
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "费用单据信息列表"
    
    headers = [
        "内部单据ID", "进仓日期", "客户名称", "始发站-目的站",
        "报关", "提单", "航班日期", "航班号", "航班单号",
        "件数", "实际重量(kg)", "计费重量(kg)", "体积(m³)", "一程重量(kg)",
        "代理", "应收运费", "应收合计", "应付合计", "利润", "利润率(%)", "业务员", "提成金额", "备注"
    ]
    
    ws.append(headers)
    
    # 样式配置
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="微软雅黑", size=10)
    thin_border = Border(
        left=Side(style='thin', color='D3D3D3'),
        right=Side(style='thin', color='D3D3D3'),
        top=Side(style='thin', color='D3D3D3'),
        bottom=Side(style='thin', color='D3D3D3')
    )
    
    for col_num, _ in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = thin_border
    
    ws.row_dimensions[1].height = 28
    
    for r_idx, rec in enumerate(records, 2):
        wh_date_str = rec.warehouse_entry_date.strftime("%Y-%m-%d") if rec.warehouse_entry_date else ""
        fl_date_str = rec.flight_date.strftime("%Y-%m-%d") if rec.flight_date else ""
        
        row_data = [
            rec.internal_doc_id or "",
            wh_date_str,
            rec.customer_name or "",
            rec.origin_destination or "",
            rec.customs_declaration or "",
            rec.bill_of_lading or "",
            fl_date_str,
            rec.flight_no or "",
            rec.flight_doc_no or "",
            rec.pieces if rec.pieces is not None else "",
            float(rec.actual_weight) if rec.actual_weight is not None else "",
            float(rec.chargeable_weight) if rec.chargeable_weight is not None else "",
            float(rec.volume) if rec.volume is not None else "",
            float(rec.first_leg_weight) if rec.first_leg_weight is not None else "",
            rec.agent or "",
            float(rec.receivable_freight) if rec.receivable_freight is not None else "",
            float(rec.receivable_total) if rec.receivable_total is not None else "",
            float(rec.pay_total) if rec.pay_total is not None else "",
            float(rec.profit) if rec.profit is not None else "",
            float(rec.profit_margin) if rec.profit_margin is not None else "",
            rec.salesperson or "",
            float(rec.commission_amount) if rec.commission_amount is not None else "",
            rec.remark or ""
        ]
        
        ws.append(row_data)
        ws.row_dimensions[r_idx].height = 22
        
        for c_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.font = data_font
            cell.border = thin_border
            # 数字和日期居中，文本左对齐
            if c_idx in (2, 7, 10, 11, 12, 13, 14, 16, 17, 18, 19, 20, 22):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    # 自动自适应列宽
    for col in ws.columns:
        max_len = 0
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or '')
            length = sum(2 if ord(char) > 127 else 1 for char in val_str)
            if length > max_len:
                max_len = length
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"cost_consignment_export_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
    
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )
