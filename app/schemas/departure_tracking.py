from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

class ShenzhenAirBillingTimeContainerDTO(BaseModel):
    id: str
    waybill_number_8: Optional[str] = Field(None, description="运单号(8位)")
    sequence: Optional[str] = Field(None, description="序号")
    flight_number: Optional[str] = Field(None, description="航班号")
    flight_date: Optional[str] = Field(None, description="航班日期")
    billing_time: Optional[str] = Field(None, description="计飞时间")
    origin: Optional[str] = Field(None, description="起飞站")
    destination: Optional[str] = Field(None, description="目的站")
    quantity: Optional[str] = Field(None, description="件数")
    weight: Optional[str] = Field(None, description="重量")
    container: Optional[str] = Field(None, description="集装器")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShenzhenAirDepartureManualDataDTO(BaseModel):
    id: str
    booking_export_id: str = Field(..., description="关联深航主表ID")
    customer_name: Optional[str] = Field(None, description="客户名称")
    cargo_type: Optional[str] = Field(None, description="货物类型")
    packaging_fee: Optional[str] = Field(None, description="包装费")
    telegram_fee: Optional[str] = Field(None, description="电报费")
    cca: Optional[str] = Field(None, description="CCA")
    door_pickup_fee: Optional[str] = Field(None, description="上门提货费")
    door_pickup_company: Optional[str] = Field(None, description="上门提货单位")
    airport_pickup_fee: Optional[str] = Field(None, description="机场提货费")
    airport_pickup_company: Optional[str] = Field(None, description="机场提货单位")
    delivery_fee: Optional[str] = Field(None, description="派送费")
    delivery_company: Optional[str] = Field(None, description="派送单位")
    carrier_deduction: Optional[str] = Field(None, description="承运扣款")
    other_fees: Optional[str] = Field(None, description="其他费用")
    manual_total_amount: Optional[str] = Field(None, description="总金额")
    remark: Optional[str] = Field(None, description="备注")
    audit_status: Optional[int] = Field(0, description="审核状态(0=未审, 1=暂存, 2=已审)")
    auditor_id: Optional[int] = Field(None, description="审核人ID")
    auditor_name: Optional[str] = Field(None, description="审核人名称")
    audit_time: Optional[datetime] = Field(None, description="审核时间")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ShenzhenAirDepartureManualDataUpsert(BaseModel):
    booking_export_id: str = Field(..., description="关联深航主表ID")
    customer_name: Optional[str] = Field(None, description="客户名称")
    cargo_type: Optional[str] = Field(None, description="货物类型")
    packaging_fee: Optional[str] = Field(None, description="包装费")
    telegram_fee: Optional[str] = Field(None, description="电报费")
    cca: Optional[str] = Field(None, description="CCA")
    door_pickup_fee: Optional[str] = Field(None, description="上门提货费")
    door_pickup_company: Optional[str] = Field(None, description="上门提货单位")
    airport_pickup_fee: Optional[str] = Field(None, description="机场提货费")
    airport_pickup_company: Optional[str] = Field(None, description="机场提货单位")
    delivery_fee: Optional[str] = Field(None, description="派送费")
    delivery_company: Optional[str] = Field(None, description="派送单位")
    carrier_deduction: Optional[str] = Field(None, description="承运扣款")
    other_fees: Optional[str] = Field(None, description="其他费用")
    manual_total_amount: Optional[str] = Field(None, description="总金额")
    remark: Optional[str] = Field(None, description="备注")


class ShenzhenAirDepartureAuditRequest(ShenzhenAirDepartureManualDataUpsert):
    action: Literal["draft", "submit"] = Field(..., description="操作类型: draft (暂存) 或 submit (提交审核)")


class ShenzhenAirDepartureItem(BaseModel):
    id: str
    prefix: Optional[str] = Field(None, description="前缀")
    waybill_number: Optional[str] = Field(None, description="单号")
    waybill_status: Optional[str] = Field(None, description="运单状态")
    creation_time: Optional[str] = Field(None, description="制单时间")
    creator: Optional[str] = Field(None, description="制单人")
    agent: Optional[str] = Field(None, description="代理人")
    routing: Optional[str] = Field(None, description="航程")
    flight_date: Optional[str] = Field(None, description="航班日期")
    billing_flight: Optional[str] = Field(None, description="开单航班")
    actual_flight: Optional[str] = Field(None, description="走货航班")
    shipper: Optional[str] = Field(None, description="发货人")
    consignee: Optional[str] = Field(None, description="收货人")
    carrier: Optional[str] = Field(None, description="承运人")
    storage_precautions: Optional[str] = Field(None, description="储运事项")
    cargo_name: Optional[str] = Field(None, description="品名")
    cabin: Optional[str] = Field(None, description="舱位")
    quantity: Optional[str] = Field(None, description="件数")
    weight: Optional[str] = Field(None, description="重量")
    chargeable_weight: Optional[str] = Field(None, description="计费重量")
    freight_rate: Optional[str] = Field(None, description="费率")
    air_freight: Optional[str] = Field(None, description="航空运费")
    fuel_surcharge: Optional[str] = Field(None, description="燃油费")
    airport_management_fee: Optional[str] = Field(None, description="机管费")
    total_amount: Optional[str] = Field(None, description="总金额")
    price_code: Optional[str] = Field(None, description="运价代码")
    handling_code: Optional[str] = Field(None, description="处理代码")
    payment_method: Optional[str] = Field(None, description="支付方式")
    waybill_type: Optional[str] = Field(None, description="运单类型")
    quantity_difference: Optional[str] = Field(None, description="运输件数差额")
    weight_difference: Optional[str] = Field(None, description="运输重量差额")
    container: Optional[str] = Field(None, description="集装器")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    billing_time_containers: List[ShenzhenAirBillingTimeContainerDTO] = Field(default_factory=list, description="关联的计飞时间集装器数据")
    manual_data: Optional[ShenzhenAirDepartureManualDataDTO] = Field(None, description="手动录入的数据")

    class Config:
        from_attributes = True


class ShenzhenAirDepartureListResponse(BaseModel):
    total: int = Field(..., description="总条数")
    items: List[ShenzhenAirDepartureItem] = Field(..., description="深航出港数据列表")


# ========== 南航出港跟踪 Schemas ==========

class CsaProductInformationDTO(BaseModel):
    id: str
    approval_data_id: Optional[str] = Field(None, description="关联批复数据ID")
    segment: Optional[str] = Field(None, description="航段")
    pieces: Optional[str] = Field(None, description="件数")
    weight: Optional[str] = Field(None, description="重量")
    volume: Optional[str] = Field(None, description="体积")
    abnormal_remark: Optional[str] = Field(None, description="非正常备注")
    storage_remark: Optional[str] = Field(None, description="存放备注")
    flight_date_info: Optional[str] = Field(None, description="所上航班/日期")
    segment_status: Optional[str] = Field(None, description="航段状态")
    is_ready: Optional[str] = Field(None, description="是否READY")
    booked_flight: Optional[str] = Field(None, description="预定航班")
    booked_flight_date: Optional[str] = Field(None, description="预定航班日期")
    security_status: Optional[str] = Field(None, description="安检状态")
    cargo_status: Optional[str] = Field(None, description="货物状态")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CsaLalamoveInformationDTO(BaseModel):
    id: str
    approval_data_id: Optional[str] = Field(None, description="关联批复数据ID")
    capacity_lalamove: Optional[str] = Field(None, description="容量/货拉")
    guarantee_pre_pull: Optional[str] = Field(None, description="保证/预拉")
    container_type: Optional[str] = Field(None, description="容器类型")
    container_position: Optional[str] = Field(None, description="容器位置")
    pieces: Optional[str] = Field(None, description="件数")
    weight: Optional[str] = Field(None, description="重量")
    pre_assigned_flight: Optional[str] = Field(None, description="预配航班")
    manifest_number: Optional[str] = Field(None, description="所在舱单号")
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CsaDepartureManualDataDTO(BaseModel):
    id: str
    approval_data_id: Optional[str] = Field(None, description="关联批复数据ID")
    customer_name: Optional[str] = Field(None, description="客户名称")
    cargo_type: Optional[str] = Field(None, description="货物类型")
    packaging_fee: Optional[str] = Field(None, description="包装费")
    telegram_fee: Optional[str] = Field(None, description="电报费")
    cca: Optional[str] = Field(None, description="CCA")
    door_pickup_fee: Optional[str] = Field(None, description="上门提货费")
    door_pickup_company: Optional[str] = Field(None, description="上门提货单位")
    airport_pickup_fee: Optional[str] = Field(None, description="机场提货费")
    airport_pickup_company: Optional[str] = Field(None, description="机场提货单位")
    delivery_fee: Optional[str] = Field(None, description="派送费")
    delivery_company: Optional[str] = Field(None, description="派送单位")
    carrier_deduction: Optional[str] = Field(None, description="承运扣款")
    other_fees: Optional[str] = Field(None, description="其他费用")
    manual_total_amount: Optional[str] = Field(None, description="总金额")
    remark: Optional[str] = Field(None, description="备注")
    audit_status: Optional[int] = Field(0, description="审核状态(0=未审, 1=暂存, 2=已审)")
    auditor_id: Optional[int] = Field(None, description="审核人ID")
    auditor_name: Optional[str] = Field(None, description="审核人名称")
    audit_time: Optional[datetime] = Field(None, description="审核时间")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CsaDepartureManualDataUpsert(BaseModel):
    approval_data_id: str = Field(..., description="关联批复数据ID（china_southern_air_approval_data.id）")
    customer_name: Optional[str] = Field(None, description="客户名称")
    cargo_type: Optional[str] = Field(None, description="货物类型")
    packaging_fee: Optional[str] = Field(None, description="包装费")
    telegram_fee: Optional[str] = Field(None, description="电报费")
    cca: Optional[str] = Field(None, description="CCA")
    door_pickup_fee: Optional[str] = Field(None, description="上门提货费")
    door_pickup_company: Optional[str] = Field(None, description="上门提货单位")
    airport_pickup_fee: Optional[str] = Field(None, description="机场提货费")
    airport_pickup_company: Optional[str] = Field(None, description="机场提货单位")
    delivery_fee: Optional[str] = Field(None, description="派送费")
    delivery_company: Optional[str] = Field(None, description="派送单位")
    carrier_deduction: Optional[str] = Field(None, description="承运扣款")
    other_fees: Optional[str] = Field(None, description="其他费用")
    manual_total_amount: Optional[str] = Field(None, description="总金额")
    remark: Optional[str] = Field(None, description="备注")


class CsaDepartureAuditRequest(CsaDepartureManualDataUpsert):
    action: Literal["draft", "submit"] = Field(..., description="操作类型: draft (暂存) 或 submit (提交审核)")


class CsaDepartureItem(BaseModel):
    id: str
    flight_info: Optional[str] = Field(None, description="订舱航班")
    aircraft_type: Optional[str] = Field(None, description="机型")
    aircraft_no: Optional[str] = Field(None, description="飞机号")
    aircraft_limit: Optional[str] = Field(None, description="飞机号限制")
    planned_takeoff: Optional[str] = Field(None, description="计划起飞时间")
    expected_takeoff: Optional[str] = Field(None, description="预计起飞时间")
    flight_status: Optional[str] = Field(None, description="航班状态")
    waybill_number: Optional[str] = Field(None, description="运单号")
    agent_code: Optional[str] = Field(None, description="代理人编码")
    key_account_code: Optional[str] = Field(None, description="大客户编码")
    key_account_name: Optional[str] = Field(None, description="大客户名称")
    sales_channel: Optional[str] = Field(None, description="销售渠道")
    booking_no: Optional[str] = Field(None, description="订舱号")
    guarantee_level: Optional[str] = Field(None, description="保障等级")
    cabin_level: Optional[str] = Field(None, description="舱位等级")
    product_code: Optional[str] = Field(None, description="产品代码")
    booking_pieces: Optional[str] = Field(None, description="订舱件数")
    booking_weight: Optional[str] = Field(None, description="订舱重量")
    booking_volume: Optional[str] = Field(None, description="订舱体积")
    goods_name: Optional[str] = Field(None, description="品名")
    commercial_danger_class: Optional[str] = Field(None, description="商用危险品类项")
    self_use_material_class: Optional[str] = Field(None, description="自用航材类项")
    aviation_oil_sample_class: Optional[str] = Field(None, description="航油样品类项")
    booking_uld: Optional[str] = Field(None, description="订舱ULD数量(板/箱)")
    booking_remark: Optional[str] = Field(None, description="订舱备注")
    ad_remark: Optional[str] = Field(None, description="AD备注")
    load_guidance: Optional[str] = Field(None, description="装载指引")
    booking_routing: Optional[str] = Field(None, description="订舱航程")
    special_cargo_code: Optional[str] = Field(None, description="特种货物代码")
    billing_qty: Optional[str] = Field(None, description="制单数量(件数/重量/体积)")
    goods_qty: Optional[str] = Field(None, description="货物数量(件数/重量/体积)")
    actual_qty: Optional[str] = Field(None, description="实走数量(件数/重量/体积)")
    actual_flight: Optional[str] = Field(None, description="实走航班")
    container: Optional[str] = Field(None, description="所在容器")
    cargo_code: Optional[str] = Field(None, description="货物代码")
    routing_country: Optional[str] = Field(None, description="航程国别")
    department: Optional[str] = Field(None, description="部门")
    booking_time: Optional[str] = Field(None, description="订舱时间")
    ref_rate: Optional[str] = Field(None, description="参考运价")
    ref_freight: Optional[str] = Field(None, description="参考运费")
    currency: Optional[str] = Field(None, description="货币")
    other_fee: Optional[str] = Field(None, description="其他费用")
    total_control: Optional[str] = Field(None, description="总控控制")
    auto_approval: Optional[str] = Field(None, description="自动批复")
    level_auto_k: Optional[str] = Field(None, description="等级自动K舱")
    size: Optional[str] = Field(None, description="尺寸")
    settlement_discount_no: Optional[str] = Field(None, description="结算折扣号")
    customs_clearance_status: Optional[str] = Field(None, description="海关放行状态")
    single_window_check: Optional[str] = Field(None, description="单一窗口查验")
    chargeable_weight: Optional[str] = Field(None, description="计费重量")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    product_information: List[CsaProductInformationDTO] = Field(default_factory=list, description="本站货物数据")
    lalamove_information: List[CsaLalamoveInformationDTO] = Field(default_factory=list, description="货拉数据")
    manual_data: Optional[CsaDepartureManualDataDTO] = Field(None, description="手动录入的数据")

    class Config:
        from_attributes = True

