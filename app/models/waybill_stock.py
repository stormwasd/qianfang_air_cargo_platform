"""
单号库模型
包含领单批次表和单号详情表
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class WaybillStockBatch(Base):
    """领单批次表"""
    __tablename__ = "waybill_stock_batches"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="领单批次ID")
    claim_date = Column(Date, nullable=False, index=True, comment="领单日期")
    first_number = Column(String(50), nullable=False, comment="首单号（数字后缀部分）")
    last_number = Column(String(50), nullable=False, comment="尾单号（数字后缀部分）")
    claim_quantity = Column(Integer, nullable=False, comment="领单数量")
    airline_name = Column(String(100), nullable=False, index=True, comment="航司名称（如china_southern_air）")
    number_prefix = Column(String(20), nullable=False, comment="单号前缀（如784-）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关联单号详情（级联删除，删除批次时自动删除关联的详情记录）
    items = relationship("WaybillStockItem", back_populates="batch", cascade="all, delete-orphan", lazy="dynamic")
    
    def __repr__(self):
        return f"<WaybillStockBatch(id={self.id}, airline_name={self.airline_name}, claim_quantity={self.claim_quantity})>"


class WaybillStockItem(Base):
    """单号详情表"""
    __tablename__ = "waybill_stock_items"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="单号详情ID")
    batch_id = Column(BigInteger, ForeignKey("waybill_stock_batches.id", ondelete="CASCADE"), nullable=False, index=True, comment="关联领单批次ID")
    claim_date = Column(Date, nullable=False, comment="领单日期")
    number_prefix = Column(String(20), nullable=False, comment="单号前缀（如784-）")
    number_suffix = Column(String(50), nullable=False, comment="单号后缀（数字部分）")
    full_number = Column(String(100), nullable=False, index=True, comment="完整单号（前缀+后缀）")
    usage_status = Column(String(2), nullable=False, default="0", index=True, comment="使用状态（0=未使用，1=已使用，2=异常，3=失效）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关联领单批次
    batch = relationship("WaybillStockBatch", back_populates="items")
    
    def __repr__(self):
        return f"<WaybillStockItem(id={self.id}, full_number={self.full_number}, usage_status={self.usage_status})>"
