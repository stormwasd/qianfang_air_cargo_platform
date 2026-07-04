from sqlalchemy import Column, String, BigInteger, DateTime, Integer
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now

class AirFinancialAuditData(Base):
    """空运财务审核扩展数据表"""
    __tablename__ = "air_financial_audit_data"

    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="主键ID")
    source_type = Column(String(50), nullable=False, index=True, comment="来源类型: shenzhen_air / china_southern_air / peer_air")
    source_id = Column(BigInteger, nullable=False, index=True, comment="来源主表ID")

    # 人工填写字段（应付）
    payable_telegraph_cost = Column(String(50), nullable=True, comment="电报费/电报成本(应付-人工填写)")
    payable_other_fee_remark = Column(String(500), nullable=True, comment="其他费用说明(应付-人工填写)")

    # 人工填写字段（应收）
    receivable_consignee_phone = Column(String(100), nullable=True, comment="收货电话(应收-人工填写, 仅同行空运)")
    receivable_consignee_unit = Column(String(255), nullable=True, comment="收货单位(应收-人工填写, 仅同行空运)")
    receivable_other_fee_remark = Column(String(500), nullable=True, comment="其他费用说明(应收-人工填写)")
    receivable_pickup_fee = Column(String(50), nullable=True, comment="上门提货费(应收-人工填写)")
    receivable_carrier_deduction = Column(String(50), nullable=True, comment="承运扣款(应收-人工填写)")
    receivable_pickup_method = Column(String(100), nullable=True, comment="提货方式(应收-人工填写)")
    receivable_collection_payment = Column(String(50), nullable=True, comment="代收货款(应收-人工填写)")
    receivable_remark = Column(String(500), nullable=True, comment="备注(应收-人工填写)")

    # 财务审核状态
    financial_audit_status = Column(Integer, default=0, index=True, comment="财务审核状态: 0=未审, 1=暂存, 2=已审")
    financial_auditor_id = Column(BigInteger, nullable=True, comment="财务审核人ID")
    financial_auditor_name = Column(String(255), nullable=True, comment="财务审核人")
    financial_audit_time = Column(DateTime, nullable=True, comment="财务审核时间")

    created_at = Column(DateTime, default=get_china_now, comment="创建时间")
    updated_at = Column(DateTime, default=get_china_now, onupdate=get_china_now, comment="更新时间")
