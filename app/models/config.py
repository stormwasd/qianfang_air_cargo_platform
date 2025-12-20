"""
业务参数配置模型
"""
from sqlalchemy import Column, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class BusinessConfig(Base):
    """业务参数配置表"""
    __tablename__ = "business_configs"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="配置ID")
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    config_data = Column(Text, nullable=False, comment="配置数据，JSON格式存储")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<BusinessConfig(id={self.id}, user_id={self.user_id})>"

