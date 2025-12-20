"""
用户-部门关联表
实现用户和部门的多对多关系
"""
from sqlalchemy import Column, BigInteger, ForeignKey, Table
from app.database import Base

# 用户-部门关联表
user_department = Table(
    'user_departments',
    Base.metadata,
    Column('user_id', BigInteger, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, comment="用户ID"),
    Column('department_id', BigInteger, ForeignKey('departments.id', ondelete='CASCADE'), primary_key=True, comment="部门ID"),
    comment="用户-部门关联表"
)

