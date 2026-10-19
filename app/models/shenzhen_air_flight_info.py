"""KingGo flight segments used only by Shenzhen cargo workflows."""
from sqlalchemy import BigInteger, Column, Date, DateTime, String, UniqueConstraint

from app.database import Base
from app.utils.helpers import get_china_now
from app.utils.snowflake import generate_id


class ShenzhenAirFlightInfo(Base):
    __tablename__ = "shenzhen_air_flight_info"
    __table_args__ = (
        UniqueConstraint("flight_date", "flight_number", "origin", "destination",
                         name="uq_szx_flight_segment"),
    )

    id = Column(BigInteger, primary_key=True, default=generate_id)
    flight_date = Column(Date, nullable=False)
    flight_number = Column(String(20), nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    kinggo_id = Column(String(50))
    area = Column(String(20))
    takeoff_time = Column(String(20), comment="计飞时间，KingGo起飞列；不是预飞时间")
    arrival_time = Column(String(20))
    actual_departure_time = Column(String(20))
    actual_arrival_time = Column(String(20))
    aircraft_number = Column(String(30))
    aircraft_type = Column(String(30))
    body_type = Column(String(10))
    status = Column(String(30))
    total_weight = Column(String(50))
    total_volume = Column(String(50))
    control_weight = Column(String(50))
    control_volume = Column(String(50))
    free_weight = Column(String(50))
    cargo_flag = Column(String(10))
    created_at = Column(DateTime, nullable=False, default=get_china_now)
    updated_at = Column(DateTime, nullable=False, default=get_china_now)
