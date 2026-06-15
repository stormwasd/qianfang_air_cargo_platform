from sqlalchemy import Column, String, BigInteger, DateTime, Float, func
from app.database import Base
from app.utils.snowflake import generate_id

class ShenzhenAirDepartureManualData(Base):
    __tablename__ = "shenzhen_air_departure_manual_data"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    waybill_number_8 = Column(String(50), unique=True, index=True, comment="单号后8位")
    customer_name = Column(String(255), comment="客户名称")
    cargo_type = Column(String(50), comment="货物类型")
    packaging_fee = Column(String(50), comment="包装费")
    telegram_fee = Column(String(50), comment="电报费")
    cca = Column(String(50), comment="CCA")
    door_pickup_fee = Column(String(50), comment="上门提货费")
    door_pickup_company = Column(String(255), comment="上门提货单位")
    airport_pickup_fee = Column(String(50), comment="机场提货费")
    airport_pickup_company = Column(String(255), comment="机场提货单位")
    delivery_fee = Column(String(50), comment="派送费")
    delivery_company = Column(String(255), comment="派送单位")
    carrier_deduction = Column(String(50), comment="承运扣款")
    other_fees = Column(String(50), comment="其他费用")
    manual_total_amount = Column(String(50), comment="总金额")
    remark = Column(String(500), comment="备注")
    
    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="记录更新时间")
