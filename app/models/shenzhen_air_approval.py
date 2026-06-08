from sqlalchemy import Column, String, BigInteger, DateTime, Text, func
from app.database import Base
from app.utils.snowflake import generate_id

class ShenzhenAirApprovalData(Base):
    """深航订舱批复数据"""
    __tablename__ = "shenzhen_air_approval_data"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    parent_id = Column(BigInteger, index=True, nullable=True, default=None, comment="父级ID，用于关联子项到父项")
    flight_number = Column(String(50), index=True, nullable=True, comment="航班号")
    flight_date = Column(String(50), index=True, nullable=True, comment="航班日期")
    aircraft_type = Column(String(50), comment="机型")
    departure_time = Column(String(50), comment="起飞")
    routing = Column(String(100), comment="航程")
    agent = Column(String(100), comment="代理人")
    f_booking = Column(String(50), comment="F订")
    f_approval = Column(String(50), comment="F批")
    c_booking = Column(String(50), comment="C订")
    c_approval = Column(String(50), comment="C批")
    other_booking = Column(String(50), comment="其他订")
    other_approval = Column(String(50), comment="其他批")
    status = Column(String(50), comment="状态")
    type = Column(String(50), comment="类型")
    control = Column(String(50), comment="控制")
    open_status = Column(String(50), comment="开放")
    remark = Column(Text, comment="备注")
    
    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="记录更新时间")
