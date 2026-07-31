"""
客服接单台数据库模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Text, DateTime, Date
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class ConsignmentRegistration(Base):
    """委托信息登记表（全局唯一记录）"""
    __tablename__ = "consignment_registrations"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, comment="登记表记录ID")
    create_time = Column(DateTime(timezone=True), nullable=True, comment="制单时间")
    internal_doc_id = Column(String(100), nullable=True, comment="内部单据ID")
    warehouse_entry_date = Column(Date, nullable=True, comment="进仓日期")
    customer_name = Column(String(100), nullable=True, comment="客户名称")
    origin_destination = Column(String(100), nullable=True, comment="始发站-目的站")
    customs_declaration = Column(String(50), nullable=True, comment="报关")
    bill_of_lading = Column(String(100), nullable=True, comment="提单")
    flight_date = Column(Date, nullable=True, comment="航班日期")
    flight_no = Column(String(50), nullable=True, comment="航班号")
    flight_doc_no = Column(String(100), nullable=True, comment="航班单号")
    pieces = Column(Integer, nullable=True, comment="件数")
    actual_weight = Column(Numeric(10, 2), nullable=True, comment="实际重量")
    chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="计费重量")
    volume = Column(Numeric(10, 3), nullable=True, comment="体积")
    first_leg_weight = Column(Numeric(10, 2), nullable=True, comment="一程重量")
    agent = Column(String(100), nullable=True, comment="代理")
    remark = Column(Text, nullable=True, comment="备注")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")


class ConsignmentInfo(Base):
    """委托信息表"""
    __tablename__ = "consignment_infos"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="委托信息ID")
    create_time = Column(DateTime(timezone=True), nullable=True, index=True, comment="制单时间")
    internal_doc_id = Column(String(100), nullable=True, comment="内部单据ID")
    warehouse_entry_date = Column(Date, nullable=True, comment="进仓日期")
    customer_name = Column(String(100), nullable=True, index=True, comment="客户名称")
    origin_destination = Column(String(100), nullable=True, comment="始发站-目的站")
    customs_declaration = Column(String(50), nullable=True, comment="报关")
    bill_of_lading = Column(String(100), nullable=True, comment="提单")
    flight_date = Column(Date, nullable=True, comment="航班日期")
    flight_no = Column(String(50), nullable=True, comment="航班号")
    flight_doc_no = Column(String(100), nullable=True, comment="航班单号")
    pieces = Column(Integer, nullable=True, comment="件数")
    actual_weight = Column(Numeric(10, 2), nullable=True, comment="实际重量")
    chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="计费重量")
    volume = Column(Numeric(10, 3), nullable=True, comment="体积")
    first_leg_weight = Column(Numeric(10, 2), nullable=True, comment="一程重量")
    agent = Column(String(100), nullable=True, comment="代理")
    remark = Column(Text, nullable=True, comment="备注")
    creator_id = Column(BigInteger, nullable=True, comment="创建者ID")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")
