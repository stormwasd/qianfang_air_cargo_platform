from sqlalchemy import Column, String, BigInteger, DateTime, Integer
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class PeerRoadDepartureManualData(Base):
    __tablename__ = "peer_road_departure_manual_data"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    consignment_note_id = Column(BigInteger, unique=True, index=True, nullable=False, comment="关联 consignment_notes.id")
    
    audit_status = Column(Integer, default=0, comment="审核状态: 0=未审, 1=暂存, 2=已审")
    auditor_id = Column(BigInteger, comment="审核人ID")
    auditor_name = Column(String(255), comment="审核人")
    audit_time = Column(DateTime, comment="审核时间")
    
    financial_audit_status = Column(Integer, default=0, comment="财务审核状态: 0=未审, 1=暂存, 2=已审")
    financial_auditor_id = Column(BigInteger, comment="财务审核人ID")
    financial_auditor_name = Column(String(255), comment="财务审核人")
    financial_audit_time = Column(DateTime, comment="财务审核时间")
    
    created_at = Column(DateTime, default=get_china_now, comment="记录创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="记录更新时间")
