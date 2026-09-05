from sqlalchemy import Column, String, BigInteger, DateTime, func
from sqlalchemy.orm import declarative_base
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class ShenzhenAirBillingTimeContainer(Base):
    __tablename__ = "shenzhen_air_billing_time_containers"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    booking_export_id = Column(BigInteger, index=True, nullable=False, comment="关联 shenzhen_air_booking_exports.id")
    waybill_number_8 = Column(String(50), index=True, comment="运单号(8位)")
    sequence = Column(String(50), comment="序号")
    flight_number = Column(String(50), comment="航班号")
    flight_date = Column(String(50), comment="航班日期")
    billing_time = Column(String(50), comment="计飞时间")
    planned_time = Column(String(50), comment="预飞时间（携程）")
    actual_time = Column(String(50), comment="实飞时间（携程）")
    actual_time_attempts = Column(String(20), default="0", comment="实飞时间查询次数")
    next_actual_time_query_at = Column(DateTime, nullable=True, comment="下一次查询实飞时间时间")
    origin = Column(String(100), comment="起飞站")
    destination = Column(String(100), comment="目的站")
    quantity = Column(String(50), comment="件数")
    weight = Column(String(50), comment="重量")
    container = Column(String(255), comment="集装器")
    
    created_at = Column(DateTime, default=get_china_now, comment="记录创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="记录更新时间")
