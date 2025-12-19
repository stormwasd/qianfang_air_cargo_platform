"""
部门模型
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Department(Base):
    """部门表"""
    __tablename__ = "departments"
    
    id = Column(Integer, primary_key=True, index=True, comment="部门ID")
    name = Column(String(100), unique=True, nullable=False, comment="部门名称")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    users = relationship("User", back_populates="department")
    
    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name})>"

