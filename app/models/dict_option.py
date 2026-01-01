"""
字典选项模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class DictOption(Base):
    """字典选项表（全局共享）"""
    __tablename__ = "dict_options"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="字典选项ID")
    dict_type_id = Column(BigInteger, ForeignKey("dict_types.id", ondelete="CASCADE"), nullable=False, index=True, comment="字典类型ID")
    label = Column(String(100), nullable=False, comment="显示字段")
    value = Column(Text, nullable=False, comment="存储的值（JSON数组格式，如：[\"L\", \"M\", \"X\"]）")
    status = Column(Integer, default=1, nullable=False, index=True, comment="状态（0=禁用，1=开启）")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 关系
    dict_type = relationship("DictType", foreign_keys=[dict_type_id])
    
    def __repr__(self):
        return f"<DictOption(id={self.id}, dict_type_id={self.dict_type_id}, label={self.label})>"
