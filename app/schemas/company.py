"""
公司信息与账户相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PaymentQRCode(BaseModel):
    url: str = Field(..., description="收款码图片URL")
    is_active: bool = Field(False, description="是否处于激活状态")


class CompanyInfoUpdate(BaseModel):
    """更新公司基本信息schema"""
    company_name: Optional[str] = Field(None, description="公司名称", max_length=200)
    company_location: Optional[str] = Field(None, description="公司地址", max_length=255)
    payment_qr_codes: Optional[List[PaymentQRCode]] = Field(None, description="收款码图片URL对象数组")


class CompanyAccountCreate(BaseModel):
    """创建公司账户schema"""
    account_name: str = Field(..., description="账户名", min_length=1, max_length=200)
    account_number: str = Field(..., description="账号", min_length=1, max_length=100)
    bank_name: str = Field(..., description="开户行", min_length=1, max_length=200)
    is_active: Optional[bool] = Field(False, description="是否激活")


class CompanyAccountUpdate(BaseModel):
    """更新公司账户schema"""
    account_name: Optional[str] = Field(None, description="账户名", min_length=1, max_length=200)
    account_number: Optional[str] = Field(None, description="账号", min_length=1, max_length=100)
    bank_name: Optional[str] = Field(None, description="开户行", min_length=1, max_length=200)
    is_active: Optional[bool] = Field(None, description="是否激活")


class CompanyAccountResponse(BaseModel):
    """公司账户详情响应schema"""
    id: str  # 以字符串返回
    account_name: str
    account_number: str
    bank_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class CompanyListResponse(BaseModel):
    """公司信息与账户列表响应schema"""
    company_name: str = Field("丰德航空物流有限公司", description="基础信息：公司名称")
    company_location: str = Field("深圳市宝安区宝安机场领航二路148号", description="基础信息：公司地址")
    payment_qr_codes: List[PaymentQRCode] = Field(default_factory=list, description="收款码图片URL对象数组")
    accounts: List[CompanyAccountResponse] = Field(default_factory=list, description="公司账户列表")
