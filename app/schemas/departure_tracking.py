from pydantic import BaseModel, Field
from typing import List, Optional
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

    class Config:
        from_attributes = True


class ShenzhenAirDepartureListResponse(BaseModel):
    total: int = Field(..., description="总条数")
    items: List[ShenzhenAirDepartureItem] = Field(..., description="深航出港数据列表")
