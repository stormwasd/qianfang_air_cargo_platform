"""
运单模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text, Date
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
import enum


class ExecutionStatus(str, enum.Enum):
    """执行状态枚举"""
    NOT_EXECUTED = "未执行"
    EXECUTING = "执行中"
    FAILED = "执行失败"


class Waybill(Base):
    """运单表"""
    __tablename__ = "waybills"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="运单ID")
    waybill_number = Column(String(100), nullable=True, index=True, comment="运单号（RPA执行后写入）")
    form_data = Column(Text, nullable=False, comment="表单数据，JSON格式存储")
    airline_record_status = Column(String(20), nullable=False, default=ExecutionStatus.NOT_EXECUTED.value, index=True, comment="航司录单执行状态（未执行、执行中、执行失败）")
    cargo_station_record_status = Column(String(20), nullable=False, default=ExecutionStatus.NOT_EXECUTED.value, index=True, comment="货站录单执行状态（未执行、执行中、执行失败）")
    document_print_status = Column(String(20), nullable=False, default=ExecutionStatus.NOT_EXECUTED.value, index=True, comment="单据打印执行状态（未执行、执行中、执行失败）")
    departure_time = Column(DateTime(timezone=True), nullable=True, comment="起飞时间（RPA执行后写入，中国时间UTC+8）")
    booking_date = Column(Date, nullable=False, index=True, comment="开单日期（格式：YYYY-MM-DD）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Waybill(id={self.id}, waybill_number={self.waybill_number})>"

