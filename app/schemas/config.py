"""
业务参数配置相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Dict, Any
from datetime import datetime


class BusinessConfigCreate(BaseModel):
    """创建业务参数配置schema"""
    config_data: Dict[str, Any] = Field(..., description="配置数据，JSON格式")


class BusinessConfigResponse(BaseModel):
    """业务参数配置响应schema"""
    id: str  # ID以字符串形式返回
    user_id: str  # 用户ID以字符串形式返回
    config_data: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

