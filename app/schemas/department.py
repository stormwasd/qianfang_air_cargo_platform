"""
部门相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime


class DepartmentCreate(BaseModel):
    """创建部门schema"""
    name: str = Field(..., description="部门名称", min_length=1, max_length=100)


class DepartmentUpdate(BaseModel):
    """更新部门schema"""
    name: str = Field(..., description="部门名称", min_length=1, max_length=100)


class DepartmentResponse(BaseModel):
    """部门响应schema"""
    id: str  # ID以字符串形式返回
    name: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class DepartmentListResponse(BaseModel):
    """部门列表响应schema"""
    total: int
    items: List[DepartmentResponse]

