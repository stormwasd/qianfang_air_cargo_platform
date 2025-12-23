"""
订舱模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
import enum


class BookingStatus(str, enum.Enum):
    """订舱状态枚举"""
    NOT_EXECUTED = "未执行"
    EXECUTING = "执行中"
    FAILED = "执行失败"


class InvoiceStatus(str, enum.Enum):
    """开单状态枚举"""
    NOT_INVOICED = "未开单"
    SUCCESS = "成功"


class Booking(Base):
    """订舱表"""
    __tablename__ = "bookings"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="订舱ID")
    form_data = Column(Text, nullable=False, comment="表单数据，JSON格式存储")
    booking_status = Column(String(20), nullable=False, default=BookingStatus.NOT_EXECUTED.value, index=True, comment="订舱状态（未执行、执行中、执行失败）")
    invoice_status = Column(String(20), nullable=False, default=InvoiceStatus.NOT_INVOICED.value, index=True, comment="开单状态（未开单、成功）")
    booking_time = Column(DateTime(timezone=True), nullable=False, comment="订舱时间（中国时间UTC+8）")
    master_airwaybill_number = Column(String(100), nullable=True, index=True, comment="主单号（开单RPA成功后写入，如：475-65665）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Booking(id={self.id}, master_airwaybill_number={self.master_airwaybill_number})>"

