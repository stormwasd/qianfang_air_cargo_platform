"""
派送单位模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class DeliveryUnit(Base):
    """派送单位管理表"""
    __tablename__ = "delivery_units"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="主键ID")
    delivery_code = Column(String(50), nullable=True, index=True, comment="派送单位编码")
    delivery_name = Column(String(200), nullable=False, index=True, comment="派送单位名称")
    contact_person = Column(String(50), nullable=False, comment="联系人")
    contact_phone = Column(String(20), nullable=False, comment="联系电话")
    settlement_method = Column(Integer, nullable=False, comment="结算方式")
    creator_id = Column(BigInteger, nullable=False, comment="创建人ID")
    creator_name = Column(String(50), nullable=False, comment="创建人名称")
    created_at = Column(DateTime, default=get_china_now, comment="创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="更新时间")
