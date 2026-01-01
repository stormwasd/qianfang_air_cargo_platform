"""
字典类型相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DictTypeCreate(BaseModel):
    """创建字典类型schema"""
    name: str = Field(..., description="名称", min_length=1, max_length=100)
    type: str = Field(..., description="唯一类型标识（如：freight_code, goods_code）", min_length=1, max_length=50)
    status: int = Field(1, description="状态（0=禁用，1=开启）", ge=0, le=1)


class DictTypeUpdate(BaseModel):
    """更新字典类型schema"""
    name: Optional[str] = Field(None, description="名称", min_length=1, max_length=100)
    type: Optional[str] = Field(None, description="唯一类型标识", min_length=1, max_length=50)
    status: Optional[int] = Field(None, description="状态（0=禁用，1=开启）", ge=0, le=1)


class DictTypeResponse(BaseModel):
    """字典类型响应schema"""
    id: str  # ID以字符串形式返回
    name: str
    type: str
    status: int  # 状态（0=禁用，1=开启）
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DictTypeListResponse(BaseModel):
    """字典类型列表响应schema"""
    total: int
    items: List[DictTypeResponse]


class DictTypeQuery(BaseModel):
    """字典类型查询schema"""
    type: Optional[str] = Field(None, description="类型标识筛选（唯一标识，如：freight_code）")
    status: Optional[int] = Field(None, description="状态筛选（0=禁用，1=开启）", ge=0, le=1)
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")
