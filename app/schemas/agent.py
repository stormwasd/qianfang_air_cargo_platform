"""
代理管理相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from decimal import Decimal
from datetime import datetime


class AgentCreate(BaseModel):
    """创建代理schema"""
    agent_code: Optional[str] = Field(None, description="代理编码", max_length=50)
    agent_type: int = Field(..., description="代理类型")
    agent_name: str = Field(..., description="代理名称", min_length=1, max_length=200)
    contact_person: str = Field(..., description="联系人", min_length=1, max_length=50)
    contact_phone: str = Field(..., description="联系电话", min_length=1, max_length=20)
    document_fee: Decimal = Field(..., description="制单费", ge=0)
    settlement_method: int = Field(..., description="结算方式")


class AgentUpdate(BaseModel):
    """更新代理schema"""
    agent_code: Optional[str] = Field(None, description="代理编码", max_length=50)
    agent_type: Optional[int] = Field(None, description="代理类型")
    agent_name: Optional[str] = Field(None, description="代理名称", min_length=1, max_length=200)
    contact_person: Optional[str] = Field(None, description="联系人", min_length=1, max_length=50)
    contact_phone: Optional[str] = Field(None, description="联系电话", min_length=1, max_length=20)
    document_fee: Optional[Decimal] = Field(None, description="制单费", ge=0)
    settlement_method: Optional[int] = Field(None, description="结算方式")


class AgentResponse(BaseModel):
    """代理详情响应schema"""
    id: str  
    agent_code: Optional[str] = None
    agent_type: int
    agent_name: str
    contact_person: str
    contact_phone: str
    document_fee: Decimal
    settlement_method: int
    creator_id: str
    creator_name: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class AgentListResponse(BaseModel):
    """代理列表响应schema"""
    total: int
    items: List[AgentResponse]


class AgentQuery(BaseModel):
    """代理查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    agent_name: Optional[str] = Field(None, description="代理名称（模糊搜索）")
    agent_type: Optional[int] = Field(None, description="代理类型（精确筛选）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")
