from sqlalchemy import Column, String, BigInteger, DateTime, Float, func, Integer
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class PeerAirDepartureManualData(Base):
    __tablename__ = "peer_air_departure_manual_data"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    consignment_note_id = Column(BigInteger, unique=True, index=True, nullable=False, comment="关联 consignment_notes.id")
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
    
    audit_status = Column(Integer, default=0, comment="审核状态: 0=未审, 1=暂存, 2=已审")
    auditor_id = Column(BigInteger, comment="审核人ID")
    auditor_name = Column(String(255), comment="审核人")
    audit_time = Column(DateTime, comment="审核时间")
    
    created_at = Column(DateTime, default=get_china_now, comment="记录创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="记录更新时间")
