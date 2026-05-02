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
    task_permissions = Column(Text, nullable=False, comment="可执行任务权限列表（JSON数组）")
    extra_config = Column(Text, nullable=True, comment="机器人其他配置（JSON对象）")
    status = Column(SmallInteger, nullable=False, default=1, index=True, comment="机器人状态（1=启用，0=未启用）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Robot(id={self.id}, name={self.name}, status={self.status})>"
