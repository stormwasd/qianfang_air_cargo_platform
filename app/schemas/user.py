"""
用户相关的Pydantic schemas
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime


class UserBase(BaseModel):
    """用户基础schema"""
    phone: str = Field(..., description="手机号", min_length=11, max_length=11)
    name: str = Field(..., description="用户姓名", min_length=1, max_length=50)
    department_ids: List[str] = Field(default_factory=list, description="所属部门ID列表（字符串格式）")
    permissions: List[str] = Field(..., description="权限列表（权限代码，如：admin, waybill, booking, settlement）")
    
    @validator("phone")
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not v.isdigit():
            raise ValueError("手机号必须为数字")
        if len(v) != 11:
            raise ValueError("手机号必须为11位")
        if not v.startswith("1"):
            raise ValueError("手机号格式不正确")
        return v


class UserCreate(UserBase):
    """创建用户schema"""
    password: str = Field(..., description="密码", min_length=6, max_length=50)


class UserUpdate(BaseModel):
    """更新用户schema（所有字段都是可选的，传入值的就修改，没传值的就保留）"""
    phone: Optional[str] = Field(None, description="手机号", min_length=11, max_length=11)
    password: Optional[str] = Field(None, description="密码", min_length=6, max_length=50)
    name: Optional[str] = Field(None, description="用户姓名", min_length=1, max_length=50)
    department_ids: Optional[List[str]] = Field(None, description="所属部门ID列表（字符串格式）")
    permissions: Optional[List[str]] = Field(None, description="权限列表（权限代码，如：admin, waybill, booking, settlement）")
    
    @validator("phone")
    def validate_phone(cls, v):
        """验证手机号格式"""
        if v is None:
            return v
        if not v.isdigit():
            raise ValueError("手机号必须为数字")
        if len(v) != 11:
            raise ValueError("手机号必须为11位")
        if not v.startswith("1"):
            raise ValueError("手机号格式不正确")
        return v


class UserPasswordUpdate(BaseModel):
    """更新密码schema"""
    password: str = Field(..., description="新密码", min_length=6, max_length=50)
    user_id: Optional[str] = Field(None, description="用户ID（管理员更新其他用户密码时使用，字符串格式）")


class UserPasswordReset(BaseModel):
    """重置密码schema（用户中心使用，需要旧密码）"""
    old_password: str = Field(..., description="旧密码", min_length=6, max_length=50)
    new_password: str = Field(..., description="新密码", min_length=6, max_length=50)


class UserResponse(UserBase):
    """用户响应schema"""
    id: str  # ID以字符串形式返回
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """用户列表响应schema"""
    total: int
    items: List[UserResponse]


class LoginRequest(BaseModel):
    """登录请求schema"""
    phone: str = Field(..., description="手机号", min_length=11, max_length=11)
    password: str = Field(..., description="密码", min_length=6)
    
    @validator("phone")
    def validate_phone(cls, v):
        """验证手机号格式"""
        if not v.isdigit():
            raise ValueError("手机号必须为数字")
        if len(v) != 11:
            raise ValueError("手机号必须为11位")
        if not v.startswith("1"):
            raise ValueError("手机号格式不正确")
        return v


class LoginResponse(BaseModel):
    """登录响应schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    has_initialized: bool = Field(..., description="是否已初始化配置")
    permissions: List[str] = Field(..., description="用户权限列表")


class TokenData(BaseModel):
    """Token数据schema"""
    user_id: int  # 内部使用，保持int类型
    phone: str
    token_version: int  # Token版本号，用于JWT失效机制


class BatchUserStatusUpdate(BaseModel):
    """批量更新用户状态schema"""
    user_ids: List[str] = Field(..., description="用户ID列表（字符串格式）")
    is_active: bool = Field(..., description="是否启用")


class BatchUserDelete(BaseModel):
    """批量删除用户schema"""
    user_ids: List[str] = Field(..., description="用户ID列表（字符串格式）")

