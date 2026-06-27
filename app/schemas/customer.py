"""
客户相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import List, Optional, Dict, Any
from decimal import Decimal
from datetime import datetime


class CustomerCreate(BaseModel):
    """创建客户schema（仅 company_name 必填，其余可选）"""
    company_name: str = Field(..., description="承运单位/公司名称", min_length=1, max_length=200)
    rate: Optional[Decimal] = Field(None, description="费率(元/公斤)", ge=0)
    contact_person: Optional[str] = Field(None, description="联系人", min_length=1, max_length=50)
    contact_phone: Optional[str] = Field(None, description="联系电话", min_length=1, max_length=20)
    
    minimum_ticket_fee: Optional[Decimal] = Field(None, description="最低票费用", ge=0)
    document_fee: Optional[Decimal] = Field(None, description="制单费", ge=0)
    minimum_ticket_fee_condition: Optional[Decimal] = Field(None, description="最低票收取条件")
    document_fee_condition: Optional[Decimal] = Field(None, description="制单费收取条件")
    weight_range_operation_fee_rate: Optional[Dict[str, Any]] = Field(None, description="重量范围_操作费费率")
    cargo_type_transit_fee_rate: Optional[Dict[str, Any]] = Field(None, description="货物类型_过站费费率")
    settlement_cycle: Optional[int] = Field(None, description="结算周期(1=周结, 2=半月结, 3=月结, 4=现结)")
    is_invoiced: Optional[bool] = Field(False, description="是否开票")


class CustomerUpdate(BaseModel):
    """更新客户schema"""
    company_name: Optional[str] = Field(None, description="承运单位/公司名称", min_length=1, max_length=200)
    rate: Optional[Decimal] = Field(None, description="费率(元/公斤)", ge=0)
    contact_person: Optional[str] = Field(None, description="联系人", min_length=1, max_length=50)
    contact_phone: Optional[str] = Field(None, description="联系电话", min_length=1, max_length=20)
    
    minimum_ticket_fee: Optional[Decimal] = Field(None, description="最低票费用", ge=0)
    document_fee: Optional[Decimal] = Field(None, description="制单费", ge=0)
    minimum_ticket_fee_condition: Optional[Decimal] = Field(None, description="最低票收取条件")
    document_fee_condition: Optional[Decimal] = Field(None, description="制单费收取条件")
    weight_range_operation_fee_rate: Optional[Dict[str, Any]] = Field(None, description="重量范围_操作费费率")
    cargo_type_transit_fee_rate: Optional[Dict[str, Any]] = Field(None, description="货物类型_过站费费率")
    settlement_cycle: Optional[int] = Field(None, description="结算周期(1=周结, 2=半月结, 3=月结, 4=现结)")
    is_invoiced: Optional[bool] = Field(None, description="是否开票")


class CustomerResponse(BaseModel):
    """客户响应schema"""
    id: str  # ID以字符串形式返回
    customer_code: Optional[str] = None
    company_name: str
    rate: Decimal
    contact_person: str
    contact_phone: str
    minimum_ticket_fee: Optional[Decimal] = None
    document_fee: Optional[Decimal] = None
    minimum_ticket_fee_condition: Optional[Decimal] = None
    document_fee_condition: Optional[Decimal] = None
    weight_range_operation_fee_rate: Optional[Dict[str, Any]] = None
    cargo_type_transit_fee_rate: Optional[Dict[str, Any]] = None
    settlement_cycle: Optional[int] = None
    is_invoiced: Optional[bool] = False
    creator_id: Optional[str] = None
    creator_name: Optional[str] = None
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
    model_config = ConfigDict(populate_by_name=True)

    company_name: Optional[str] = Field(None, validation_alias=AliasChoices("company_name", "companyName", "customer_name", "customerName"), description="公司名称（模糊搜索）")
    contact_person: Optional[str] = Field(None, validation_alias=AliasChoices("contact_person", "contactPerson"), description="联系人（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")

