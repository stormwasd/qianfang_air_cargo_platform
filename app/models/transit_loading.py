from sqlalchemy import Column, String, BigInteger, DateTime, Float, func
from sqlalchemy.orm import declarative_base
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class ShenzhenAirBookingExport(Base):
    __tablename__ = "shenzhen_air_booking_exports"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    prefix = Column(String(20), comment="前缀")
    waybill_number = Column(String(50), index=True, comment="单号")
    waybill_status = Column(String(50), comment="运单状态")
    creation_time = Column(String(50), comment="制单时间")
    creator = Column(String(100), comment="制单人")
    agent = Column(String(100), comment="代理人")
    routing = Column(String(100), comment="航程")
    flight_date = Column(String(50), comment="航班日期")
    billing_flight = Column(String(50), comment="开单航班")
    actual_flight = Column(String(50), comment="走货航班")
    shipper = Column(String(255), comment="发货人")
    consignee = Column(String(255), comment="收货人")
    carrier = Column(String(100), comment="承运人")
    storage_precautions = Column(String(255), comment="储运事项")
    cargo_name = Column(String(255), comment="品名")
    cabin = Column(String(50), comment="舱位")
    quantity = Column(String(50), comment="件数")
    weight = Column(String(50), comment="重量")
    chargeable_weight = Column(String(50), comment="计费重量")
    freight_rate = Column(String(50), comment="费率")
    air_freight = Column(String(50), comment="航空运费")
    fuel_surcharge = Column(String(50), comment="燃油费")
    airport_management_fee = Column(String(50), comment="机管费")
    total_amount = Column(String(50), comment="总金额")
    price_code = Column(String(50), comment="运价代码")
    handling_code = Column(String(50), comment="处理代码")
    payment_method = Column(String(50), comment="支付方式")
    waybill_type = Column(String(50), comment="运单类型")
    quantity_difference = Column(String(50), comment="运输件数差额")
    weight_difference = Column(String(50), comment="运输重量差额")
    container = Column(String(255), comment="集装器")
    departure_tracking_completed = Column(String(1), nullable=False, default="0", comment="出港明细是否已完成抓取")
    
    created_at = Column(DateTime, default=get_china_now, comment="记录创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="记录更新时间")
