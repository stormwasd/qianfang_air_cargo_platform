"""
南航 Token 存储模型
"""
from sqlalchemy import Column, BigInteger, Text, DateTime
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class NanHangToken(Base):
    """南航 Token 存储表"""
    __tablename__ = "nanhang_token"

    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="记录ID")
    robot_id = Column(BigInteger, nullable=True, index=True, comment="关联机器人ID（FK robots.id）")
    token = Column(Text, nullable=False, comment="南航Token数据")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")

    def __repr__(self):
        return f"<NanHangToken(id={self.id}, robot_id={self.robot_id})>"
