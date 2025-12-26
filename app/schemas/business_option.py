"""
业务参数选项相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class OptionDictSave(BaseModel):
    """保存选项字典schema"""
    options_data: Dict[str, List[str]] = Field(..., description="选项字典数据，如：{\"freight_code\": [\"M\", \"N\"], \"goods_code\": [\"A\", \"B\"]}")


class OptionDictQuery(BaseModel):
    """获取选项字典查询schema"""
    keys: Optional[List[str]] = Field(None, description="要获取的key列表，如：[\"freight_code\", \"goods_code\"]，不传则返回所有")


class OptionDictResponse(BaseModel):
    """选项字典响应schema"""
    id: str  # ID以字符串形式返回
    user_id: str  # 用户ID以字符串形式返回
    options_data: Dict[str, List[str]]  # 选项字典数据
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

