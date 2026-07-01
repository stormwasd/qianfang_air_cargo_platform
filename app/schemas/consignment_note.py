"""
托运书相关的 Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, date


class ConsignmentNoteCreate(BaseModel):
    """
    创建托运书schema
    
    参数说明：
    - transport_type: 托运方式，"0"=空运，"1"=汽运
    - company_name: 代理公司名称
    - customer_name: 客户名称
    - form_data: 动态表单数据，根据 transport_type 包含不同结构
    
    空运 (transport_type="0") 的 form_data 结构：
    {
      "airline": "航司名称",
      "flight_date": "YYYY-MM-DD",
      "flight_number": "航班号",
      "origin_station": "始发站",
      "destination_station": "到达站",
      "estimated_flight_time": "计飞时间",
      "quantity": "件数",
      "weight": "重量",
      "chargeable_weight": "计费重量(KG)",
      "cabin_type": "舱位类型",
      "cabin_grade": "舱位等级",
      "volume": "体积",
      "pickup_method": "提货方式",
      "consignee": "收货人",
      "cargo_name": "货物名称",
      "rate": "费率",
      "air_freight": "航空运费",
      "other_fees": "其他费用",
      "telegraph_fee": "电报费",
      "destination_weather": "目的站天气"
    }
    
    汽运 (transport_type="1") 的 form_data 结构：
    {
      "transport_date": "YYYY-MM-DD",
      "quantity": "件数",
      "weight": "重量",
      "volume": "体积(立方)",
      "vehicle_type": "车型",
      "cargo_name": "货物名称",
      "total_freight": "总运费",
      "other_fees": "其他费用",
      "origin_city": "始发城市",
      "origin_address": "始发城市详细地址",
      "destination_city": "终点城市",
      "destination_address": "终点城市详细地址",
      "destination_weather": "目的站天气"
    }
    """
    transport_type: str = Field(..., description="托运方式：0=空运，1=汽运")
    company_name: str = Field(..., description="代理公司名称")
    customer_name: str = Field(..., description="客户名称")
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），根据托运方式包含不同结构")


class ConsignmentNoteUpdate(BaseModel):
    """
    修改托运书 schema
    与创建结构一致，整体覆盖。
    """
    transport_type: str = Field(..., description="托运方式：0=空运，1=汽运")
    company_name: str = Field(..., description="代理公司名称")
    customer_name: str = Field(..., description="客户名称")
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），根据托运方式包含不同结构")


class ConsignmentNoteQuery(BaseModel):
    """
    托运书查询 schema
    
    空运查询条件：托运日期范围, 目的站, 航班号, 航司, 代理公司
    汽运查询条件：托运日期范围, 代理公司, 客户名称
    """
    model_config = ConfigDict(populate_by_name=True)

    transport_type: Optional[str] = Field(None, description="托运方式筛选：0=空运，1=汽运")
    date_start: Optional[date] = Field(None, description="托运日期范围-开始（格式：YYYY-MM-DD）")
    date_end: Optional[date] = Field(None, description="托运日期范围-结束（格式：YYYY-MM-DD）")
    company_name: Optional[str] = Field(None, description="代理公司（模糊搜索）")
    customer_name: Optional[str] = Field(None, description="客户名称（模糊搜索，仅汽运）")
    destination: Optional[str] = Field(None, description="目的站（模糊搜索，仅空运）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索，仅空运）")
    airline: Optional[str] = Field(None, description="航司（模糊搜索，仅空运）")
    audit_status: Optional[int] = Field(None, description="审核状态(0:未审, 1:暂存, 2:已审，仅空运审核列表有效)")
    flight_date: Optional[date] = Field(None, description="航班日期/托运日期（精确匹配，格式：YYYY-MM-DD）")
    origin_station: Optional[str] = Field(None, description="始发站（模糊搜索，仅空运）")
    waybill_number: Optional[str] = Field(None, description="主单号（模糊搜索，仅空运）")
    origin_city: Optional[str] = Field(None, description="始发城市（模糊搜索，仅汽运）")
    destination_city: Optional[str] = Field(None, description="目的城市（模糊搜索，仅汽运）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")


class PeerAirDepartureManualDataDTO(BaseModel):
    """同行空运出港扩展（手动/审核）数据出参"""
    id: str
    consignment_note_id: str = Field(..., description="关联托运书ID")
    waybill_number: Optional[str] = Field(None, description="主单号")
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
    audit_status: Optional[int] = Field(0, description="审核状态")
    auditor_id: Optional[int] = Field(None, description="审核人ID")
    auditor_name: Optional[str] = Field(None, description="审核人")
    audit_time: Optional[datetime] = Field(None, description="审核时间")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PeerRoadDepartureManualDataDTO(BaseModel):
    """同行汽运出港审核数据出参"""
    id: str
    consignment_note_id: str = Field(..., description="关联托运书ID")
    audit_status: Optional[int] = Field(0, description="审核状态")
    auditor_id: Optional[int] = Field(None, description="审核人ID")
    auditor_name: Optional[str] = Field(None, description="审核人")
    audit_time: Optional[datetime] = Field(None, description="审核时间")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PeerAirDepartureManualDataUpsert(BaseModel):
    """同行空运出港扩展数据暂存/审核入参"""
    consignment_note_id: str = Field(..., description="关联托运书ID")
    waybill_number: Optional[str] = Field(None, description="主单号")
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


class ConsignmentNoteResponse(BaseModel):
    """托运书响应 schema"""
    id: str
    transport_type: str
    company_name: Optional[str]
    customer_name: Optional[str]
    consignment_date: Optional[date]
    destination: Optional[str]
    flight_number: Optional[str]
    airline: Optional[str]
    form_data: Dict[str, Any]
    creator_id: Optional[str]
    creator_name: Optional[str]
    manual_data: Optional[Union[PeerAirDepartureManualDataDTO, PeerRoadDepartureManualDataDTO]] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ConsignmentNoteListResponse(BaseModel):
    """托运书列表响应 schema"""
    total: int
    items: List[ConsignmentNoteResponse]
