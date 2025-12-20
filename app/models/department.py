"""
部门模型
"""
from sqlalchemy import Column, BigInteger, String, DateTime
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.user_department import user_department
from app.utils.snowflake import generate_id
from app.utils.helpers import get_utc_now


class Department(Base):
    """部门表"""
    __tablename__ = "departments"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="部门ID")
    name = Column(String(100), unique=True, nullable=False, comment="部门名称")
    created_at = Column(DateTime(timezone=True), default=get_utc_now, nullable=False, comment="创建时间（UTC）")
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now, nullable=False, comment="更新时间（UTC）")
    
    # 多对多关系：部门可以有多个用户
    users = relationship(
        "User",
        secondary=user_department,
        back_populates="departments"
    )
    
    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name})>"

