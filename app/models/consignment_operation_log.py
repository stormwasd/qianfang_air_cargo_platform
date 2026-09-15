"""客服与费用单据共用的操作记录，独立保留，不随业务单据或账号删除。"""
from sqlalchemy import BigInteger, Column, DateTime, Index, String

from app.database import Base
from app.utils.helpers import get_china_now
from app.utils.snowflake import generate_id


class ConsignmentOperationLog(Base):
    __tablename__ = "consignment_operation_logs"
    __table_args__ = (
        Index("idx_consignment_operation_time", "consignment_id", "operated_at", "id"),
    )

    id = Column(BigInteger, primary_key=True, default=generate_id, comment="操作记录ID")
    consignment_id = Column(BigInteger, nullable=False, comment="两台共用单据ID")
    source = Column(String(32), nullable=False, comment="操作来源台")
    action = Column(String(16), nullable=False, comment="draft/save/void/delete")
    operation_name = Column(String(50), nullable=False, comment="操作名称快照")
    operator_id = Column(BigInteger, nullable=False, comment="实际操作用户ID")
    operator_name = Column(String(50), nullable=False, comment="操作时用户姓名快照")
    operated_at = Column(DateTime(timezone=True), nullable=False, default=get_china_now, comment="操作时间（中国时间）")
