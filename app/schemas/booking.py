"""
订舱相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class BookingCreate(BaseModel):
    """创建订舱schema"""
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式）")


class BookingQuery(BaseModel):
    """订舱查询schema"""
    airline: Optional[str] = Field(None, description="航司（模糊搜索，从form_data JSON中提取）")
    booking_status: Optional[str] = Field(None, description="订舱状态筛选（未执行、执行中、执行失败）")
    invoice_status: Optional[str] = Field(None, description="开单状态筛选（未开单、成功）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class BookingResponse(BaseModel):
    """订舱响应schema"""
    id: str  # ID以字符串形式返回
    form_data: Dict[str, Any]
    booking_status: str
    invoice_status: str
    booking_time: datetime
    master_airwaybill_number: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    """订舱列表响应schema"""
    total: int
    items: List[BookingResponse]

