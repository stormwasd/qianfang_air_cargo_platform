"""国际空运主单号查重的事务互斥键，不作为运单或永久唯一约束。"""
from sqlalchemy import Column, String

from app.database import Base


class ConsignmentNumberGuard(Base):
    __tablename__ = "consignment_number_guards"

    number_hash = Column(String(64), primary_key=True, comment="规范化国际空运主单号的SHA256，用于事务行锁")
