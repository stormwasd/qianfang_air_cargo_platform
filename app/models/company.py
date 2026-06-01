"""
公司信息模型
"""
from sqlalchemy import Column, BigInteger, String
from app.database import Base
from app.utils.snowflake import generate_id

class CompanyAccount(Base):
    """公司账户表"""
    __tablename__ = "company_accounts"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="账户ID")
    account_name = Column(String(200), nullable=False, comment="账户名")
    account_number = Column(String(100), nullable=False, comment="账号")
    bank_name = Column(String(200), nullable=False, comment="开户行")
