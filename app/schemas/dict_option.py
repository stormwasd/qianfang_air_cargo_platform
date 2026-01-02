"""
字典选项相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class DictOptionCreate(BaseModel):
    """创建字典选项schema"""
    dict_type: str = Field(..., description="父级type（字典类型的唯一标识，如：freight_code）", min_length=1, max_length=50)
    label: str = Field(..., description="显示字段", min_length=1, max_length=100)
    value: str = Field(..., description="存储的值（单个字符串，如：\"L\"）", min_length=1, max_length=200)
    status: int = Field(1, description="状态（0=禁用，1=开启）", ge=0, le=1)


class DictOptionUpdate(BaseModel):
    """更新字典选项schema"""
    dict_type: Optional[str] = Field(None, description="父级type（字典类型的唯一标识）", min_length=1, max_length=50)
    label: Optional[str] = Field(None, description="显示字段", min_length=1, max_length=100)
    value: Optional[str] = Field(None, description="存储的值（单个字符串）", min_length=1, max_length=200)
    status: Optional[int] = Field(None, description="状态（0=禁用，1=开启）", ge=0, le=1)


class DictOptionResponse(BaseModel):
    """字典选项响应schema"""
    id: str  # ID以字符串形式返回
    dict_type_id: str  # 字典类型ID
    dict_type: str  # 字典类型的唯一标识
    label: str  # 显示字段
    value: str  # 存储的值（单个字符串）
    status: int  # 状态（0=禁用，1=开启）
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DictOptionListResponse(BaseModel):
    """字典选项列表响应schema"""
    total: int
    items: List[DictOptionResponse]


class DictOptionQuery(BaseModel):
    """字典选项查询schema"""
    dict_type: Optional[str] = Field(None, description="字典类型（唯一标识，如：freight_code）")
    status: Optional[int] = Field(None, description="状态筛选（0=禁用，1=开启）", ge=0, le=1)
    page: Optional[int] = Field(None, ge=1, description="页码（不传则不分页，返回全部）")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="每页数量（不传则不分页，返回全部）")
