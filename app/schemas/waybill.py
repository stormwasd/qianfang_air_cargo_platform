"""
运单相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class WaybillCreate(BaseModel):
    """创建运单schema"""
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式）")


class WaybillQuery(BaseModel):
    """运单查询schema"""
    airline_record_status: Optional[str] = Field(None, description="航司录单执行状态筛选（未执行、执行中、执行失败）")
    cargo_station_record_status: Optional[str] = Field(None, description="货站录单执行状态筛选（未执行、执行中、执行失败）")
    document_print_status: Optional[str] = Field(None, description="单据打印执行状态筛选（未执行、执行中、执行失败）")
    booking_date_start: Optional[date] = Field(None, description="开单日期开始（格式：YYYY-MM-DD）")
    booking_date_end: Optional[date] = Field(None, description="开单日期结束（格式：YYYY-MM-DD）")
    airline: Optional[str] = Field(None, description="航司（模糊搜索）")
    destination: Optional[str] = Field(None, description="目的站（模糊搜索）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索）")
    shipper: Optional[str] = Field(None, description="托运单位（模糊搜索）")
    waybill_number: Optional[str] = Field(None, description="运单号（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class WaybillResponse(BaseModel):
    """运单响应schema"""
    id: str  # ID以字符串形式返回
    waybill_number: Optional[str]
    form_data: Dict[str, Any]
    airline_record_status: str
    cargo_station_record_status: str
    document_print_status: str
    departure_time: Optional[datetime]
    booking_date: date
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WaybillListResponse(BaseModel):
    """运单列表响应schema"""
    total: int
    items: List[WaybillResponse]

