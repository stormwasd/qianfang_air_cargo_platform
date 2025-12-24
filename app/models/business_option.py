"""
业务参数选项模型
用于存储运价代码、货物代码、包装、货物名称等选项
"""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
import enum


class OptionType(str, enum.Enum):
    """选项类型枚举"""
    RATE_CODE = "运价代码"
    CARGO_CODE = "货物代码"
    PACKAGE = "包装"
    CARGO_NAME = "货物名称"


class BusinessOption(Base):
    """业务参数选项表"""
    __tablename__ = "business_options"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="选项ID")
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID（每个用户的选项独立）")
    option_type = Column(String(50), nullable=False, index=True, comment="选项类型（运价代码、货物代码、包装、货物名称）")
    option_value = Column(String(200), nullable=False, comment="选项值")
    is_favorite = Column(Boolean, default=False, nullable=False, index=True, comment="是否常用选项")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    # 唯一索引：同一用户同一类型不能有重复的选项值
    __table_args__ = (
        Index('idx_user_type_value', 'user_id', 'option_type', 'option_value', unique=True),
    )
    
    def __repr__(self):
        return f"<BusinessOption(id={self.id}, option_type={self.option_type}, option_value={self.option_value})>"

