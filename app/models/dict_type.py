"""
字典类型模型
"""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class DictType(Base):
    """字典类型表（每个用户的字典类型独立）"""
    __tablename__ = "dict_types"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="字典类型ID")
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID（每个用户的字典类型独立）")
    name = Column(String(100), nullable=False, comment="名称")
    type = Column(String(50), nullable=False, index=True, comment="唯一类型标识（如：freight_code, goods_code）")
    status = Column(Boolean, default=True, nullable=False, index=True, comment="状态（True=开启，False=禁用）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    # 唯一索引：同一用户下不能有重复的type
    __table_args__ = (
        Index('idx_user_type', 'user_id', 'type', unique=True),
    )
    
    def __repr__(self):
        return f"<DictType(id={self.id}, user_id={self.user_id}, type={self.type}, name={self.name})>"

