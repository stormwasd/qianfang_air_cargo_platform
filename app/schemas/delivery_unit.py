"""
派送单位相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field, AliasChoices
from typing import List, Optional
from datetime import datetime


class DeliveryUnitCreate(BaseModel):
    """创建派送单位schema"""
    delivery_code: Optional[str] = Field(None, description="派送单位编码", max_length=50)
    delivery_name: str = Field(..., description="派送单位名称", min_length=1, max_length=200)
    contact_person: str = Field(..., description="联系人", min_length=1, max_length=50)
    contact_phone: str = Field(..., description="联系电话", min_length=1, max_length=20)
    settlement_method: int = Field(..., description="结算方式")


class DeliveryUnitUpdate(BaseModel):
    """更新派送单位schema"""
    delivery_code: Optional[str] = Field(None, description="派送单位编码", max_length=50)
    delivery_name: Optional[str] = Field(None, description="派送单位名称", min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, description="联系人", min_length=1, max_length=50)
    contact_phone: Optional[str] = Field(None, description="联系电话", min_length=1, max_length=20)
    settlement_method: Optional[int] = Field(None, description="结算方式")


class DeliveryUnitResponse(BaseModel):
    """派送单位详情响应schema"""
    id: str
    delivery_code: Optional[str] = None
    delivery_name: str
    contact_person: str
    contact_phone: str
    settlement_method: int
    creator_id: str
    creator_name: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DeliveryUnitListResponse(BaseModel):
    """派送单位列表响应schema"""
    total: int
    items: List[DeliveryUnitResponse]


class DeliveryUnitQuery(BaseModel):
    """派送单位查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    delivery_name: Optional[str] = Field(None, validation_alias=AliasChoices("delivery_name", "deliveryName"), description="派送单位名称（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")
