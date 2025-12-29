"""
字典选项相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
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


class DictOptionUpdateByIdentifier(BaseModel):
    """通过dictType和value更新字典选项schema"""
    dict_type: str = Field(..., description="父级type（字典类型的唯一标识）", min_length=1, max_length=50)
    value: str = Field(..., description="存储的值（用于定位要更新的选项）", min_length=1, max_length=200)
    label: Optional[str] = Field(None, description="显示字段", min_length=1, max_length=100)
    status: Optional[bool] = Field(None, description="状态（True=开启，False=禁用）")


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


class DictOptionValueItem(BaseModel):
    """字典选项值项（包含id和value）"""
    id: str  # 选项ID
    value: str  # 存储的值


class DictOptionGroupedResponse(BaseModel):
    """字典选项分组响应schema（按dict_type和label分组）"""
    dict_type: str  # 字典类型的唯一标识
    label: str  # 显示字段
    value: List[DictOptionValueItem]  # 存储的值列表（包含id和value）
    status: bool  # 状态（所有选项的状态应该相同）
    
    class Config:
        from_attributes = True


class DictOptionListResponse(BaseModel):
    """字典选项列表响应schema（旧格式，保留兼容）"""
    total: int
    items: List[DictOptionResponse]


class DictOptionGroupedListResponse(BaseModel):
    """字典选项分组列表响应schema（新格式，按dict_type和label分组）"""
    total: int
    items: List[DictOptionGroupedResponse]


class DictOptionQuery(BaseModel):
    """字典选项查询schema"""
    dict_type: Optional[str] = Field(None, description="字典类型（唯一标识，如：freight_code）")
    status: Optional[bool] = Field(None, description="状态筛选（True=开启，False=禁用）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")

