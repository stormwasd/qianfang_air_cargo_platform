"""
RPA任务队列模型
用于存储待执行的RPA任务，实现任务队列功能
"""
from sqlalchemy import Column, BigInteger, String, DateTime, Text, Integer, Index
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
import enum


class RPATaskType(str, enum.Enum):
    """RPA任务类型枚举"""
    SHENZHEN_AIR_WAYBILL_EXECUTE = "SHENZHEN_AIR_WAYBILL_EXECUTE"  
    SHENZHEN_AIR_WAYBILL_VOID = "SHENZHEN_AIR_WAYBILL_VOID"  
    SHENZHEN_AIR_BILLING_TIME_CONTAINER = "SHENZHEN_AIR_BILLING_TIME_CONTAINER"  
    SHENZHEN_AIR_TRANSIT_LOADING = "SHENZHEN_AIR_TRANSIT_LOADING"  
    SHENZHEN_AIR_MAIN_WAYBILL_PRINT = "SHENZHEN_AIR_MAIN_WAYBILL_PRINT"  
    SHENZHEN_AIR_APPROVAL_DATA = "SHENZHEN_AIR_APPROVAL_DATA"  
    SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY = "SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY"  
    CHINA_SOUTHERN_AIR_BOOKING_EXECUTE = "CHINA_SOUTHERN_AIR_BOOKING_EXECUTE"  
    CHINA_SOUTHERN_AIR_BOOKING_CANCEL = "CHINA_SOUTHERN_AIR_BOOKING_CANCEL"  
    CHINA_SOUTHERN_AIR_DIRECT_INVOICE = "CHINA_SOUTHERN_AIR_DIRECT_INVOICE"  
    CHINA_SOUTHERN_AIR_WAYBILL_VOID = "CHINA_SOUTHERN_AIR_WAYBILL_VOID"  
    CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE = "CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE"  
    CHINA_SOUTHERN_AIR_APPROVAL_DATA = "CHINA_SOUTHERN_AIR_APPROVAL_DATA"  
    CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA = "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA"  
    CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT = "CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT"  
    CHINA_SOUTHERN_AIR_SECURITY_PRINT = "CHINA_SOUTHERN_AIR_SECURITY_PRINT"  
    CHINA_SOUTHERN_AIR_LABEL_PRINT = "CHINA_SOUTHERN_AIR_LABEL_PRINT"  
    CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING = "CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING"  
    FILE_PRINT = "FILE_PRINT"  
    SHENZHEN_AIR_KEEP_LOGIN = "SHENZHEN_AIR_KEEP_LOGIN"  
    CHINA_SOUTHERN_AIR_KEEP_LOGIN = "CHINA_SOUTHERN_AIR_KEEP_LOGIN"  
    TANGYI_KEEP_LOGIN = "TANGYI_KEEP_LOGIN"  
    TANGYI_RESTART = "TANGYI_RESTART"  


class RPATaskStatus(str, enum.Enum):
    """RPA任务状态枚举"""
    PENDING = "pending"  
    RUNNING = "running"  
    SUCCESS = "success"  
    FAILED = "failed"  
    TIMEOUT = "timeout"  


class RPATargetType(str, enum.Enum):
    """RPA任务目标类型枚举"""
    WAYBILL = "waybill"  
    BOOKING = "booking"  


class RPATask(Base):
    """RPA任务队列表"""
    __tablename__ = "rpa_tasks"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="任务ID")
    task_type = Column(String(50), nullable=False, index=True, comment="任务类型（SHENZHEN_AIR_WAYBILL_EXECUTE/SHENZHEN_AIR_WAYBILL_VOID/CHINA_SOUTHERN_AIR_BOOKING_EXECUTE/CHINA_SOUTHERN_AIR_BOOKING_CANCEL/CHINA_SOUTHERN_AIR_DIRECT_INVOICE）")
    target_type = Column(String(20), nullable=False, index=True, comment="目标类型（waybill/booking）")
    target_id = Column(BigInteger, nullable=False, index=True, comment="目标ID（运单ID或订舱ID）")
    params = Column(Text, nullable=False, comment="RPA调用参数（JSON格式）")
    queue_params = Column(Text, nullable=True, comment="队列参数（JSON格式，用于存储需要创建的队列信息）")
    status = Column(String(20), nullable=False, default=RPATaskStatus.PENDING.value, index=True, comment="任务状态（pending/running/success/failed/timeout）")
    priority = Column(Integer, nullable=False, default=1, index=True, comment="优先级（数值越大越优先，默认1）")
    work_uuid = Column(String(100), nullable=True, index=True, comment="RPA返回的workUuid")
    job_uuid = Column(String(100), nullable=True, comment="RPA的jobUuid")
    robot_id = Column(BigInteger, nullable=True, index=True, comment="指定消费的机器人ID（NULL=任意有权限的机器人消费）")
    location = Column(String(50), nullable=True, index=True, comment="任务所属区域（shenzhen_air/china_southern_air），用于匹配机器人location")
    result = Column(Text, nullable=True, comment="执行结果（JSON格式）")
    error_message = Column(Text, nullable=True, comment="错误信息")
    created_by = Column(BigInteger, nullable=True, index=True, comment="创建用户ID")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, index=True, comment="创建时间（中国时间UTC+8）")
    started_at = Column(DateTime(timezone=True), nullable=True, comment="开始执行时间")
    finished_at = Column(DateTime(timezone=True), nullable=True, comment="完成时间")
    
    __table_args__ = (
        Index('idx_status_priority_created', 'status', 'priority', 'created_at'),
    )
    
    def __repr__(self):
        return f"<RPATask(id={self.id}, task_type={self.task_type}, status={self.status})>"

