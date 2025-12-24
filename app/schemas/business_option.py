"""
业务参数选项相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class OptionCreate(BaseModel):
    """创建选项schema"""
    option_type: str = Field(..., description="选项类型（运价代码、货物代码、包装、货物名称）")
    option_value: str = Field(..., description="选项值", min_length=1, max_length=200)


class OptionResponse(BaseModel):
    """选项响应schema"""
    id: str  # ID以字符串形式返回
    user_id: str  # 用户ID以字符串形式返回
    option_type: str
    option_value: str
    is_favorite: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class OptionListResponse(BaseModel):
    """选项列表响应schema"""
    total: int
    items: List[OptionResponse]


class FavoriteOptionQuery(BaseModel):
    """常用选项查询schema"""
    option_type: str = Field(..., description="选项类型（运价代码、货物代码、包装、货物名称）")


class FavoriteOptionResponse(BaseModel):
    """常用选项响应schema"""
    option_type: str
    items: List[str]  # 常用选项值列表

