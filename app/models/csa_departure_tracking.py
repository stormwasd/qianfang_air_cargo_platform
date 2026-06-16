"""
南航出港跟踪数据模型
- CsaProductInformation: 本站货物数据
- CsaLalamoveInformation: 货拉数据
两者均通过 approval_data_id 关联到 china_southern_air_approval_data 表
"""
from sqlalchemy import Column, String, BigInteger, DateTime, func
from app.database import Base
from app.utils.snowflake import generate_id


class CsaProductInformation(Base):
    """南航出港跟踪 - 本站货物数据"""
    __tablename__ = "csa_product_information"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    approval_data_id = Column(BigInteger, index=True, nullable=False, comment="关联 china_southern_air_approval_data.id")
    segment = Column(String(100), nullable=True, comment="航段")
    pieces = Column(String(50), nullable=True, comment="件数")
    weight = Column(String(50), nullable=True, comment="重量")
    volume = Column(String(50), nullable=True, comment="体积")
    abnormal_remark = Column(String(255), nullable=True, comment="非正常备注")
    storage_remark = Column(String(255), nullable=True, comment="存放备注")
    flight_date_info = Column(String(255), nullable=True, comment="所上航班/日期")
    segment_status = Column(String(100), nullable=True, comment="航段状态")
    is_ready = Column(String(50), nullable=True, comment="是否READY")
    booked_flight = Column(String(100), nullable=True, comment="预定航班")
    booked_flight_date = Column(String(50), nullable=True, comment="预定航班日期")
    security_status = Column(String(100), nullable=True, comment="安检状态")
    cargo_status = Column(String(100), nullable=True, comment="货物状态")

    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")


class CsaLalamoveInformation(Base):
    """南航出港跟踪 - 货拉数据"""
    __tablename__ = "csa_lalamove_information"

    id = Column(BigInteger, primary_key=True, index=True, default=generate_id, comment="主键ID")
    approval_data_id = Column(BigInteger, index=True, nullable=False, comment="关联 china_southern_air_approval_data.id")
    capacity_lalamove = Column(String(255), nullable=True, comment="容量/货拉")
    guarantee_pre_pull = Column(String(100), nullable=True, comment="保证/预拉")
    container_type = Column(String(100), nullable=True, comment="容器类型")
    container_position = Column(String(100), nullable=True, comment="容器位置")
    pieces = Column(String(50), nullable=True, comment="件数")
    weight = Column(String(50), nullable=True, comment="重量")
    pre_assigned_flight = Column(String(255), nullable=True, comment="预配航班")
    manifest_number = Column(String(255), nullable=True, comment="所在舱单号")

    created_at = Column(DateTime, default=func.now(), comment="记录创建时间")
