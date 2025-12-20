"""
客户模型
"""
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class Customer(Base):
    """客户表"""
    __tablename__ = "customers"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="客户ID")
    company_name = Column(String(200), nullable=False, index=True, comment="承运单位/公司名称")
    settlement_method = Column(String(50), nullable=False, comment="结算方式")
    rate = Column(Numeric(10, 2), nullable=False, comment="费率(元/公斤)")
    contact_person = Column(String(50), nullable=False, index=True, comment="联系人")
    contact_phone = Column(String(20), nullable=False, comment="联系电话")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, company_name={self.company_name})>"

