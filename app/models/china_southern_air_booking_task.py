"""Persistent tasks for China Southern API-based booking execution."""
from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Text

from app.database import Base
from app.utils.helpers import get_china_now
from app.utils.snowflake import generate_id


class ChinaSouthernAirBookingTaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ChinaSouthernAirBookingTask(Base):
    __tablename__ = "china_southern_air_booking_tasks"

    id = Column(BigInteger, primary_key=True, default=generate_id, index=True)
    batch_id = Column(BigInteger, nullable=False, index=True, comment="批量执行批次ID")
    booking_id = Column(BigInteger, nullable=False, index=True, comment="订舱ID")
    status = Column(String(20), nullable=False, default=ChinaSouthernAirBookingTaskStatus.PENDING, index=True)
    priority = Column(Integer, nullable=False, default=1, index=True)
    params = Column(Text, nullable=False, comment="任务参数（JSON格式）")
    result = Column(Text, nullable=True, comment="执行结果（JSON格式）")
    error_message = Column(Text, nullable=True, comment="错误信息")
    error_details = Column(Text, nullable=True, comment="结构化错误详情（JSON格式）")
    created_by = Column(BigInteger, nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_csa_booking_task_status_priority_created", "status", "priority", "created_at"),
        Index("idx_csa_booking_task_batch_booking", "batch_id", "booking_id"),
    )


__all__ = ["ChinaSouthernAirBookingTask", "ChinaSouthernAirBookingTaskStatus"]
