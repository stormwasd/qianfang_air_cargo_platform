"""Shenzhen-only flight times: persisted KingGo data, optional Ctrip fallback."""
from datetime import datetime, timedelta
import logging
import re

from app.config import settings
from app.database import SessionLocal
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo
from app.services.shenzhen_air_flight_info import normalize_date, shenzhen_air_flight_info_sync
from app.utils.airport_code_mapper import AIRPORT_CODE_TO_CITY
from app.utils.ctrip_client import ctrip_client

logger = logging.getLogger(__name__)


def _airport_candidates(value):
    text = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", text):
        return [text]
    return [code for code, city in AIRPORT_CODE_TO_CITY.items() if city == text]


def _as_datetime(day, clock):
    text = str(clock or "").strip().replace(":", "")
    if not re.fullmatch(r"\d{4}", text):
        return None
    try:
        return datetime.combine(day, datetime.strptime(text, "%H%M").time())
    except ValueError:
        return None


def times_from_record(record):
    scheduled = _as_datetime(record.flight_date, record.takeoff_time)
    actual = _as_datetime(record.flight_date, record.actual_departure_time)
    # KingGo supplies HHMM only. Choose the closest day to scheduled time,
    # including early departures just before midnight. Delays over 12h remain
    # ambiguous without an explicit actual departure date from the upstream.
    if actual and scheduled and actual < scheduled - timedelta(hours=12):
        actual += timedelta(days=1)
    elif actual and scheduled and actual > scheduled + timedelta(hours=12):
        actual -= timedelta(days=1)
    return {
        "planned_time": scheduled.strftime("%Y-%m-%d %H:%M:%S") if scheduled else None,
        "ready_time": None,  # KingGo does NOT provide an estimated departure.
        "actual_time": actual.strftime("%Y-%m-%d %H:%M:%S") if actual else None,
    }


class ShenzhenAirFlightTimes:
    async def get_flight_times(
        self, flight_no, flight_date, routing, force_refresh=False,
        *, required_times=("planned_time", "actual_time"),
    ):
        result = {"planned_time": None, "ready_time": None, "actual_time": None}
        if not flight_no or not flight_date or not routing:
            return None
        try:
            day = normalize_date(flight_date)
        except (TypeError, ValueError):
            return None
        route = re.split(r"\s*-\s*", str(routing).strip())
        if len(route) != 2:
            return None
        flight = str(flight_no).strip().upper()
        if settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED:
            # Startup seeds today's table before consumers start. Dates not
            # seeded (tomorrow/history) are synchronized on demand, throttled
            # across threads. force_refresh never causes a full fetch per AWB.
            await shenzhen_air_flight_info_sync.ensure_fresh(day)
            db = SessionLocal()
            try:
                records = db.query(ShenzhenAirFlightInfo).filter(
                    ShenzhenAirFlightInfo.flight_date == day,
                    ShenzhenAirFlightInfo.flight_number == flight,
                    ShenzhenAirFlightInfo.origin.in_(_airport_candidates(route[0])),
                    ShenzhenAirFlightInfo.destination.in_(_airport_candidates(route[1])),
                ).limit(2).all()
                if len(records) == 1:
                    result = times_from_record(records[0])
            except Exception as exc:
                logger.warning("深航KingGo航班表查询失败 error_type=%s", type(exc).__name__)
            finally:
                db.close()

        if settings.SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED and any(
            not result.get(key) for key in required_times
        ):
            try:
                fallback = await ctrip_client.get_flight_times(
                    flight_no, flight_date, routing, force_refresh=force_refresh
                )
            except Exception as exc:
                logger.warning("深航携程兜底失败 error_type=%s；保留KingGo时间", type(exc).__name__)
                fallback = None
            # Fill missing fields only; Ctrip must never overwrite KingGo's
            # scheduled or actual takeoff when its own cached result differs.
            for key in result:
                if not result[key] and fallback:
                    result[key] = fallback.get(key)
        return result if any(result.values()) else None


shenzhen_air_flight_times = ShenzhenAirFlightTimes()
