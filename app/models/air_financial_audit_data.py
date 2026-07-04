from sqlalchemy import Column, String, BigInteger, DateTime, Integer, JSON
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class AirFinancialAuditData(Base):
    """空运财务审核扩展数据表"""
    __tablename__ = "air_financial_audit_data"

    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="主键ID")
    source_type = Column(String(50), nullable=False, index=True, comment="来源类型: shenzhen_air / china_southern_air / peer_air")
    source_id = Column(BigInteger, nullable=False, index=True, comment="来源主表ID")

    # 应收与应付板块的整表自定义覆盖数据JSON，支持全部字段修改保存
    payable_data = Column(JSON, nullable=True, comment="应付修改后的全部数据 JSON")
    receivable_data = Column(JSON, nullable=True, comment="应收修改后的全部数据 JSON")

    # 财务审核状态
    financial_audit_status = Column(Integer, default=0, index=True, comment="财务审核状态: 0=未审, 1=暂存, 2=已审")
    financial_auditor_id = Column(BigInteger, nullable=True, comment="财务审核人ID")
    financial_auditor_name = Column(String(255), nullable=True, comment="财务审核人")
    financial_audit_time = Column(DateTime, nullable=True, comment="财务审核时间")

    created_at = Column(DateTime, default=get_china_now, comment="创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="更新时间")
