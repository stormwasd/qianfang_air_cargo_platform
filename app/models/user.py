"""
用户模型
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    """用户表"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True, comment="用户ID")
    phone = Column(String(11), unique=True, index=True, nullable=False, comment="手机号（账号）")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    name = Column(String(50), nullable=False, comment="用户姓名")
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, comment="所属部门ID")
    permissions = Column(Text, nullable=False, comment="权限列表，JSON格式存储")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    department = relationship("Department", back_populates="users")
    
    def __repr__(self):
        return f"<User(id={self.id}, phone={self.phone}, name={self.name})>"

