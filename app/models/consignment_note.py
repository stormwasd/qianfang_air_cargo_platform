"""
托运书模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text, Date
from app.database import Base
from app.utils.helpers import get_china_now


class ConsignmentNote(Base):
    """托运书表"""
    __tablename__ = "consignment_notes"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True, index=True, comment="托运书ID")
    transport_type = Column(String(10), nullable=False, index=True, comment="托运方式：0=空运，1=汽运")
    company_name = Column(String(100), nullable=True, index=True, comment="代理公司名称")
    customer_name = Column(String(100), nullable=True, index=True, comment="客户名称")
    consignment_date = Column(Date, nullable=True, index=True, comment="托运日期（空运为航班日期，汽运为托运日期）")
    destination = Column(String(100), nullable=True, index=True, comment="目的站/终点城市")
    flight_number = Column(String(100), nullable=True, index=True, comment="航班号（空运特有）")
    airline = Column(String(100), nullable=True, index=True, comment="航司（空运特有）")
    form_data = Column(Text, nullable=False, comment="托运单动态业务数据（JSON格式）")
    creator_id = Column(String(50), nullable=True, comment="制单人ID")
    creator_name = Column(String(100), nullable=True, comment="制单人姓名")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间/制单时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")

    def __repr__(self):
        return f"<ConsignmentNote(id={self.id}, transport_type={self.transport_type}, company={self.company_name})>"
