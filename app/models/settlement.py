"""
结算单模型
"""
from sqlalchemy import Column, BigInteger, Text, DateTime, String
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class Settlement(Base):
    """结算单表"""
    __tablename__ = "settlements"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="结算单ID")
    form_data = Column(Text, nullable=False, comment="表单数据，JSON格式存储")
    waybill_void_status = Column(String(20), nullable=False, default="0", index=True, comment="运单作废状态（数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功），从waybills表同步")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    def __repr__(self):
        return f"<Settlement(id={self.id})>"

