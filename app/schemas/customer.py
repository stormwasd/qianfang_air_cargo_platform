"""
客户相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


class CustomerCreate(BaseModel):
    """创建客户schema"""
    company_name: str = Field(..., description="承运单位/公司名称", min_length=1, max_length=200)
    settlement_method: str = Field(..., description="结算方式", min_length=1, max_length=50)
    rate: Decimal = Field(..., description="费率(元/公斤)", ge=0)
    contact_person: str = Field(..., description="联系人", min_length=1, max_length=50)
    contact_phone: str = Field(..., description="联系电话", min_length=1, max_length=20)


class CustomerUpdate(BaseModel):
    """更新客户schema"""
    company_name: Optional[str] = Field(None, description="承运单位/公司名称", min_length=1, max_length=200)
    settlement_method: Optional[str] = Field(None, description="结算方式", min_length=1, max_length=50)
    rate: Optional[Decimal] = Field(None, description="费率(元/公斤)", ge=0)
    contact_person: Optional[str] = Field(None, description="联系人", min_length=1, max_length=50)
    contact_phone: Optional[str] = Field(None, description="联系电话", min_length=1, max_length=20)


class CustomerResponse(BaseModel):
    """客户响应schema"""
    id: int
    company_name: str
    settlement_method: str
    rate: Decimal
    contact_person: str
    contact_phone: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CustomerListResponse(BaseModel):
    """客户列表响应schema"""
    total: int
    items: List[CustomerResponse]


class CustomerQuery(BaseModel):
    """客户查询schema"""
    company_name: Optional[str] = Field(None, description="公司名称（模糊搜索）")
    contact_person: Optional[str] = Field(None, description="联系人（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

