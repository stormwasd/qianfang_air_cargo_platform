from sqlalchemy import Column, String, BigInteger, DateTime, func, Index
from app.database import Base
from app.utils.snowflake import generate_id

class CsaDepartureAlertTask(Base):
    """南航出港跟踪预警任务表"""
    __tablename__ = "csa_departure_alert_tasks"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    approval_data_id = Column(BigInteger, index=True, unique=True, nullable=False, comment="关联 china_southern_air_approval_data.id")
    waybill_number = Column(String(50), index=True, comment="运单号")
    flight_date = Column(String(50), index=True, comment="航班日期")
    planned_time = Column(String(50), comment="计飞时间")
    trigger_time = Column(DateTime, index=True, comment="触发时间点")
    status = Column(String(20), index=True, default="pending", comment="状态: pending/processing/processed/ignored")
    
    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="记录更新时间")
