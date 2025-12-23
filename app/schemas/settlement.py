"""
结算单相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class SettlementCreate(BaseModel):
    """创建结算单schema"""
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式）")


class SettlementQuery(BaseModel):
    """结算单查询schema"""
    airline: Optional[str] = Field(None, description="所属航司（模糊搜索，从form_data JSON中提取）")
    destination: Optional[str] = Field(None, description="目的站（模糊搜索，从form_data JSON中提取）")
    customer_name: Optional[str] = Field(None, description="客户名称/发货人名称（模糊搜索，从form_data JSON中提取）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索，从form_data JSON中提取）")
    master_airwaybill_number: Optional[str] = Field(None, description="主单号（模糊搜索，从form_data JSON中提取）")
    booking_date_start: Optional[date] = Field(None, description="航司制单日期开始（格式：YYYY-MM-DD，通过主单号关联运单表获取）")
    booking_date_end: Optional[date] = Field(None, description="航司制单日期结束（格式：YYYY-MM-DD，通过主单号关联运单表获取）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class SettlementResponse(BaseModel):
    """结算单响应schema"""
    id: str  # ID以字符串形式返回
    form_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SettlementListResponse(BaseModel):
    """结算单列表响应schema"""
    total: int
    items: List[SettlementResponse]

