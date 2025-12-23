"""
结算单模型
"""
from sqlalchemy import Column, BigInteger, Text, DateTime
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class Settlement(Base):
    """结算单表"""
    __tablename__ = "settlements"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="结算单ID")
    form_data = Column(Text, nullable=False, comment="表单数据，JSON格式存储")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Settlement(id={self.id})>"

