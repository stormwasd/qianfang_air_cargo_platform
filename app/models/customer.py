"""
客户模型
"""
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Boolean, JSON, Integer
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class Customer(Base):
    """客户表"""
    __tablename__ = "customers"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="客户ID")
    customer_code = Column(String(50), nullable=True, index=True, comment="客户编码")
    company_name = Column(String(200), nullable=False, index=True, comment="承运单位/公司名称")
    rate = Column(Numeric(10, 2), nullable=False, comment="费率(元/公斤)")
    contact_person = Column(String(50), nullable=False, index=True, comment="联系人")
    contact_phone = Column(String(20), nullable=False, comment="联系电话")
    
    minimum_ticket_fee = Column(Numeric(10, 2), nullable=True, comment="最低票费用")
    document_fee = Column(Numeric(10, 2), nullable=True, comment="制单费")
    minimum_ticket_fee_condition = Column(Numeric(10, 2), nullable=True, comment="最低票收取条件")
    document_fee_condition = Column(Numeric(10, 2), nullable=True, comment="制单费收取条件")
    weight_range_operation_fee_rate = Column(JSON, nullable=True, comment="重量范围_操作费费率")
    cargo_type_transit_fee_rate = Column(JSON, nullable=True, comment="货物类型_过站费费率")
    settlement_cycle = Column(Integer, nullable=True, comment="结算周期(1=周结, 2=半月结, 3=月结, 4=现结)")
    is_invoiced = Column(Boolean, nullable=True, default=False, comment="是否开票")
    
    creator_id = Column(BigInteger, nullable=True, comment="创建人ID")
    creator_name = Column(String(50), nullable=True, comment="创建人名称")
    
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Customer(id={self.id}, company_name={self.company_name})>"

