"""
公司信息模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime, JSON, Boolean
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class CompanyAccount(Base):
    """公司账户表"""
    __tablename__ = "company_accounts"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="账户ID")
    account_name = Column(String(200), nullable=False, comment="账户名")
    account_number = Column(String(100), nullable=False, comment="账号")
    bank_name = Column(String(200), nullable=False, comment="开户行")
    is_active = Column(Boolean, default=False, comment="是否激活(唯一)")
    created_at = Column(DateTime, default=get_china_now, comment="创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="更新时间")


class CompanyInfo(Base):
    """公司基础信息表（单例）"""
    __tablename__ = "company_info"
    
    id = Column(BigInteger, primary_key=True, default=1, index=True, comment="配置主键ID(固定为1)")
    company_name = Column(String(200), nullable=False, default="丰德航空物流有限公司", comment="公司名称")
    company_location = Column(String(255), nullable=False, default="深圳市宝安区宝安机场领航二路148号", comment="公司地址")
    payment_qr_codes = Column(JSON, nullable=True, comment="收款码图片URL数组")
    created_at = Column(DateTime, default=get_china_now, comment="创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="更新时间")
