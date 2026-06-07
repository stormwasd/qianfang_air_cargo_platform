from sqlalchemy import Column, String, BigInteger, DateTime, func
from sqlalchemy.orm import declarative_base
from app.database import Base

class ShenzhenAirBillingTimeContainer(Base):
    __tablename__ = "shenzhen_air_billing_time_containers"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True, comment="主键ID")
    waybill_number_8 = Column(String(50), index=True, comment="运单号(8位)")
    sequence = Column(String(50), comment="序号")
    flight_number = Column(String(50), comment="航班号")
    flight_date = Column(String(50), comment="航班日期")
    billing_time = Column(String(50), comment="计飞时间")
    origin = Column(String(100), comment="起飞站")
    destination = Column(String(100), comment="目的站")
    quantity = Column(String(50), comment="件数")
    weight = Column(String(50), comment="重量")
    container = Column(String(255), comment="集装器")
    
    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="记录更新时间")
