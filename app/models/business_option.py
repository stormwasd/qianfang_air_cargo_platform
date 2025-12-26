"""
业务参数选项模型
用于存储运价代码、货物代码、包装、货物名称等选项字典
"""
from sqlalchemy import Column, BigInteger, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class BusinessOption(Base):
    """业务参数选项表（存储选项字典JSON）"""
    __tablename__ = "business_options"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="选项ID")
    user_id = Column(BigInteger, ForeignKey("users.id"), unique=True, nullable=False, index=True, comment="用户ID（每个用户的选项独立）")
    options_data = Column(Text, nullable=False, comment="选项字典数据，JSON格式存储，如：{\"freight_code\": [\"M\", \"N\"], \"goods_code\": [\"A\", \"B\"]}")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关系
    user = relationship("User", foreign_keys=[user_id])
    
    def __repr__(self):
        return f"<BusinessOption(id={self.id}, user_id={self.user_id})>"

