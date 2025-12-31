"""
字典选项相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime


class DictOptionCreate(BaseModel):
    """创建字典选项schema（支持批量创建）"""
    dict_type: str = Field(..., description="父级type（字典类型的唯一标识，如：freight_code）", min_length=1, max_length=50)
    label: str = Field(..., description="显示字段", min_length=1, max_length=100)
    value: List[str] = Field(..., description="存储的值列表（每个值会创建一个选项）", min_items=1)
    status: bool = Field(True, description="状态（True=开启，False=禁用）")


class DictOptionUpdate(BaseModel):
    """更新字典选项schema"""
    dict_type: Optional[str] = Field(None, description="父级type（字典类型的唯一标识）", min_length=1, max_length=50)
    label: Optional[str] = Field(None, description="显示字段", min_length=1, max_length=100)
    value: Optional[List[str]] = Field(None, description="存储的值列表（批量更新该分组下的所有选项）", min_items=1)
    status: Optional[bool] = Field(None, description="状态（True=开启，False=禁用）")


class DictOptionUpsert(BaseModel):
    """创建或更新字典选项schema（upsert模式：按dict_type和label查找，存在则更新，不存在则创建）"""
    dict_type: str = Field(..., description="父级type（字典类型的唯一标识）", min_length=1, max_length=50)
    label: str = Field(..., description="显示字段", min_length=1, max_length=100)
    value: Union[str, List[str]] = Field(..., description="存储的值（单个字符串如：\"L\"，或字符串数组如：[\"M\", \"L\"]，支持批量操作）")
    status: bool = Field(True, description="状态（True=开启，False=禁用）")


class DictOptionValueDelete(BaseModel):
    """删除字典选项中的某个value的schema"""
    option_id: Optional[str] = Field(None, description="选项ID（字符串格式，即option_group_id）")
    dict_type: Optional[str] = Field(None, description="父级type（字典类型的唯一标识，如：freight_code）")
    label: Optional[str] = Field(None, description="显示字段")
    value: str = Field(..., description="要删除的值（单个字符串）", min_length=1, max_length=200)


class DictOptionValueUpdate(BaseModel):
    """更新字典选项中的某个value的schema（替换模式）"""
    option_id: Optional[str] = Field(None, description="选项ID（字符串格式，即option_group_id）")
    dict_type: Optional[str] = Field(None, description="父级type（字典类型的唯一标识，如：freight_code）")
    label: Optional[str] = Field(None, description="显示字段")
    old_value: str = Field(..., description="要更新的旧值（单个字符串）", min_length=1, max_length=200)
    new_value: str = Field(..., description="新的值（单个字符串）", min_length=1, max_length=200)


class DictOptionResponse(BaseModel):
    """字典选项响应schema（单个选项）"""
    id: str  # ID以字符串形式返回
    dict_type_id: str
    dict_type: str  # 字典类型的唯一标识
    label: str
    value: str
    status: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DictOptionItemResponse(BaseModel):
    """字典选项项响应schema（一个option是一个整体）"""
    dict_type: str  # 字典类型的唯一标识
    label: str  # 显示字段
    value: List[str]  # 存储的值列表（字符串数组，如：["L", "X"]）
    option_id: str  # 选项ID（对应这个value列表）
    status: bool  # 状态
    
    class Config:
        from_attributes = True


class DictOptionListResponse(BaseModel):
    """字典选项列表响应schema（旧格式，保留兼容）"""
    total: int
    items: List[DictOptionResponse]


class DictOptionGroupedListResponse(BaseModel):
    """字典选项分组列表响应schema（新格式，每个item是一个option）"""
    total: int
    items: List[DictOptionItemResponse]


class DictOptionQuery(BaseModel):
    """字典选项查询schema"""
    dict_type: Optional[str] = Field(None, description="字典类型（唯一标识，如：freight_code）")
    status: Optional[bool] = Field(None, description="状态筛选（True=开启，False=禁用）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

