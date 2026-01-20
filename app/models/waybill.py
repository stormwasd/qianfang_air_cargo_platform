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
    SUCCESS = "执行成功"  # RPA执行成功状态


class Waybill(Base):
    """运单表"""
    __tablename__ = "waybills"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="运单ID")
    booking_id = Column(BigInteger, nullable=True, index=True, comment="关联的订舱ID（可选，用于从订舱回显数据创建运单时建立关联）")
    waybill_number = Column(String(100), nullable=True, index=True, comment="运单号（RPA执行后写入）")
    form_data = Column(Text, nullable=False, comment="表单数据，JSON格式存储")
    airline_record_status = Column(String(20), nullable=False, default="0", index=True, comment="航司录单执行状态（数据字典值：0=未开单，1=开单中，2=失败，3=成功）")
    cargo_station_record_status = Column(String(20), nullable=False, default="0", index=True, comment="货站录单执行状态（数据字典值：0=未执行，1=执行中，2=失败）")
    document_print_status = Column(String(20), nullable=False, default="0", index=True, comment="单据打印执行状态（数据字典值：0=未执行，1=执行中，2=失败）")
    waybill_void_status = Column(String(20), nullable=False, default="0", index=True, comment="运单作废状态（数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功）")
    departure_time = Column(DateTime(timezone=True), nullable=True, comment="起飞时间（RPA执行后写入，中国时间UTC+8）")
    booking_date = Column(Date, nullable=False, index=True, comment="开单日期（格式：YYYY-MM-DD）")
    rpa_work_uuid = Column(String(100), nullable=True, index=True, comment="RPA任务workUuid（用于查询RPA执行状态，新增或作废时都会更新）")
    rpa_queue_uuids = Column(Text, nullable=True, comment="RPA队列UUIDs（JSON格式，存储4个队列的UUID和ID信息）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Waybill(id={self.id}, waybill_number={self.waybill_number})>"

