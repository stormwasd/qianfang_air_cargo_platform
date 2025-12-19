"""
业务参数配置模型
"""
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class BusinessConfig(Base):
    """业务参数配置表"""
    __tablename__ = "business_configs"
    
    id = Column(Integer, primary_key=True, index=True, comment="配置ID")
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, comment="用户ID")
    config_data = Column(Text, nullable=False, comment="配置数据，JSON格式存储")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<BusinessConfig(id={self.id}, user_id={self.user_id})>"

