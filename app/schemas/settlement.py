"""
结算单相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class SettlementCreate(BaseModel):
    """创建结算单schema"""
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式）")


class SettlementUpdate(BaseModel):
    """修改结算单schema"""
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），与新增接口结构一致，整体替换原form_data")


class SettlementQuery(BaseModel):
    """结算单查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    airline: Optional[str] = Field(None, description="所属航司（模糊搜索，从form_data JSON中提取）")
    destination: Optional[str] = Field(None, description="目的站（模糊搜索，从form_data JSON中提取）")
    customer_name: Optional[str] = Field(None, description="客户名称/发货人名称（模糊搜索，从form_data JSON中提取）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索，从form_data JSON中提取）")
    master_airwaybill_number: Optional[str] = Field(None, description="主单号（模糊搜索，从form_data JSON中提取）")
    settlement_status: Optional[str] = Field(None, description="结算状态（精确匹配，从form_data JSON中提取，可选值：未结算、已结算）")
    financial_review: Optional[str] = Field(None, description="财务审核状态（精确匹配，从form_data JSON中提取，可选值：未审核、已审核）")
    airline_record_time_start: Optional[date] = Field(None, description="航司录单时间开始（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选）")
    airline_record_time_end: Optional[date] = Field(None, description="航司录单时间结束（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")


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

