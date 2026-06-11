from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime

class ChinaSouthernAirApprovalItem(BaseModel):
    id: str
    flight_info: Optional[str] = None
    aircraft_type: Optional[str] = None
    aircraft_no: Optional[str] = None
    aircraft_limit: Optional[str] = None
    planned_takeoff: Optional[str] = None
    expected_takeoff: Optional[str] = None
    flight_status: Optional[str] = None
    waybill_number: Optional[str] = None
    agent_code: Optional[str] = None
    key_account_code: Optional[str] = None
    key_account_name: Optional[str] = None
    sales_channel: Optional[str] = None
    booking_no: Optional[str] = None
    guarantee_level: Optional[str] = None
    cabin_level: Optional[str] = None
    product_code: Optional[str] = None
    booking_pieces: Optional[str] = None
    booking_weight: Optional[str] = None
    booking_volume: Optional[str] = None
    goods_name: Optional[str] = None
    commercial_danger_class: Optional[str] = None
    self_use_material_class: Optional[str] = None
    aviation_oil_sample_class: Optional[str] = None
    booking_uld: Optional[str] = None
    booking_remark: Optional[str] = None
    ad_remark: Optional[str] = None
    load_guidance: Optional[str] = None
    booking_routing: Optional[str] = None
    special_cargo_code: Optional[str] = None
    billing_qty: Optional[str] = None
    goods_qty: Optional[str] = None
    actual_qty: Optional[str] = None
    actual_flight: Optional[str] = None
    container: Optional[str] = None
    cargo_code: Optional[str] = None
    routing_country: Optional[str] = None
    department: Optional[str] = None
    booking_time: Optional[str] = None
    ref_rate: Optional[str] = None
    ref_freight: Optional[str] = None
    currency: Optional[str] = None
    other_fee: Optional[str] = None
    total_control: Optional[str] = None
    auto_approval: Optional[str] = None
    level_auto_k: Optional[str] = None
    size: Optional[str] = None
    settlement_discount_no: Optional[str] = None
    customs_clearance_status: Optional[str] = None
    single_window_check: Optional[str] = None
    chargeable_weight: Optional[str] = None
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
