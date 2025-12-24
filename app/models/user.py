"""
用户模型
"""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user_department import user_department
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="用户ID")
    phone = Column(String(11), unique=True, index=True, nullable=False, comment="手机号（账号）")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    name = Column(String(50), nullable=False, comment="用户姓名")
    permissions = Column(Text, nullable=False, comment="权限列表，JSON格式存储（存储权限代码，如：[\"admin\", \"waybill\"]）")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    token_version = Column(BigInteger, default=0, nullable=False, index=True, comment="Token版本号，用于JWT失效机制，权限变更时递增")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间（中国时间UTC+8）")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间（中国时间UTC+8）")
    
    # 多对多关系：用户可以有多个部门
    departments = relationship(
        "Department",
        secondary=user_department,
        back_populates="users",
        lazy="selectin"  # 使用selectin加载策略，提高查询效率
    )
    
    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, name={self.name})>"

