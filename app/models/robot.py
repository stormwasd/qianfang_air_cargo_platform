"""
机器人管理模型
用于存储RPA机器人的配置信息
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text, SmallInteger, Index
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class Robot(Base):
    """机器人管理表"""
    __tablename__ = "robots"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="机器人记录ID")
    robot_id = Column(String(500), nullable=False, unique=True, index=True, comment="机器人ID（加密后存储）")
    name = Column(String(200), nullable=False, comment="机器人名称")
    location = Column(String(200), nullable=False, comment="机器人所在位置")
    location_required = Column(SmallInteger, nullable=False, default=1, comment="是否启用location区域限制（1=开启，0=关闭）")
    task_permissions = Column(Text, nullable=False, comment="可执行任务权限列表（JSON数组）")
    extra_config = Column(Text, nullable=True, comment="机器人其他配置（JSON对象）")
    status = Column(SmallInteger, nullable=False, default=1, index=True, comment="机器人状态（1=启用，0=未启用）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Robot(id={self.id}, name={self.name}, status={self.status})>"


class TaskProcess(Base):
    """RPA流程详情表"""
    __tablename__ = "task_processes"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="记录ID")
    task_name = Column(String(100), nullable=False, unique=True, index=True, comment="任务名称（如 SHENZHEN_AIR_WAYBILL_EXECUTE）")
    chinese_name = Column(String(200), nullable=False, comment="中文名称")
    process_detail_uuid = Column(String(100), nullable=False, comment="RPA流程详情UUID")
    version = Column(String(20), nullable=False, comment="版本号")
    process_param = Column(Text, nullable=True, comment="流程入参（JSON格式）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")


class RobotJob(Base):
    """机器人生成的Job映射表"""
    __tablename__ = "robot_jobs"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="记录ID")
    robot_id = Column(BigInteger, nullable=False, index=True, comment="机器人记录ID（FK robots.id）")
    task_name = Column(String(100), nullable=False, index=True, comment="任务名称")
    job_uuid = Column(String(100), nullable=False, index=True, comment="生成的RPA jobUUID")
    process_detail_uuid = Column(String(100), nullable=False, comment="生成时使用的流程UUID")
    bot_uuid = Column(String(100), nullable=True, comment="生成时使用的机器人UUID")
    job_name = Column(String(200), nullable=True, comment="生成的RPA任务名称")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")


class RobotQueue(Base):
    """机器人队列配置表"""
    __tablename__ = "robot_queues"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="记录ID")
    robot_id = Column(BigInteger, nullable=False, index=True, comment="机器人记录ID（FK robots.id）")
    task_name = Column(String(100), nullable=False, index=True, comment="任务名称（如 SHENZHEN_AIR_WAYBILL_EXECUTE）")
    queue_key = Column(String(100), nullable=False, comment="队列用途标识（如 waybill_number, freight_rate）")
    queue_name = Column(String(200), nullable=False, comment="队列名称（全局唯一，带机器人标识）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")
    
    __table_args__ = (
        Index('uk_robot_task_queue', 'robot_id', 'task_name', 'queue_key', unique=True),
    )


class RPARecurringTaskScheduleState(Base):
    """按机器人记录周期性 RPA 任务的最近入队时间。"""
    __tablename__ = "rpa_recurring_task_schedule_states"

    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="记录ID")
    robot_id = Column(BigInteger, nullable=False, index=True, comment="机器人记录ID")
    task_type = Column(String(100), nullable=False, index=True, comment="周期性RPA任务类型")
    last_enqueued_at = Column(DateTime(timezone=True), nullable=False, comment="最近一次入队时间（中国时间UTC+8）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")

    __table_args__ = (
        Index("uk_robot_recurring_task_type", "robot_id", "task_type", unique=True),
    )

