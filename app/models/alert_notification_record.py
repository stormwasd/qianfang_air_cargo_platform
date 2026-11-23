from sqlalchemy import Column, String, BigInteger, DateTime, func
from app.database import Base
from app.utils.snowflake import generate_id

class AlertNotificationRecord(Base):
    """预警通知记录表 (统一防重用)"""
    __tablename__ = "alert_notification_records"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    module_name = Column(String(100), index=True, nullable=False, comment="预警模块名称(如 csa_departure_status)")
    target_id = Column(String(100), index=True, nullable=False, comment="目标标识(运单号或业务ID)")
    state_hash = Column(String(255), nullable=False, comment="核心状态哈希(去重特征码)")
    
    created_at = Column(DateTime, default=func.now(), comment="首次发送时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="最后一次状态变更发送时间")
