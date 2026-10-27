"""Shenzhen-only flight times: persisted KingGo data, optional Ctrip fallback."""
from datetime import datetime, timedelta
import logging
import re

from sqlalchemy import and_, or_

from app.config import settings
from app.database import SessionLocal
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo
from app.services.shenzhen_air_flight_info import (
    is_valid_kinggo_flight_number, normalize_date, shenzhen_air_flight_info_sync,
)
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
    @staticmethod
    def get_stored_times_for_details(db, details):
        """Batch local lookups, without a network call or consuming retry attempts.

        Match the detail's own flight/date/segment, never its parent's flight.
        Ambiguous city names must not select an arbitrary airport segment.
        """
        if not settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED:
            return {}
        keys = {}
        for row in details:
            flight = str(row.flight_number or "").strip().upper()
            if not is_valid_kinggo_flight_number(flight):
                continue
            try:
                day = normalize_date(row.flight_date)
            except (TypeError, ValueError):
                continue
            origins = _airport_candidates(str(row.origin or ""))
            destinations = _airport_candidates(str(row.destination or ""))
            if origins and destinations:
                keys[row.id] = (day, flight, origins, destinations)
        if not keys:
            return {}
        flights_by_day = {}
        for day, flight, _, _ in keys.values():
            flights_by_day.setdefault(day, set()).add(flight)
        records = db.query(ShenzhenAirFlightInfo).filter(or_(*[
            and_(ShenzhenAirFlightInfo.flight_date == day,
                 ShenzhenAirFlightInfo.flight_number.in_(flights))
            for day, flights in flights_by_day.items()
        ])).all()
        segments = {}
        for record in records:
            segments.setdefault((record.flight_date, record.flight_number), []).append(record)
        result = {}
        for row_id, (day, flight, origins, destinations) in keys.items():
            matches = [record for record in segments.get((day, flight), [])
                       if record.origin in origins and record.destination in destinations]
            if len(matches) == 1:
                result[row_id] = times_from_record(matches[0])
        return result

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
        origins = _airport_candidates(route[0])
        destinations = _airport_candidates(route[1])
        fallback_routing = (
            f"{origins[0]}-{destinations[0]}"
            if len(origins) == len(destinations) == 1 else None
        )
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
                    ShenzhenAirFlightInfo.origin.in_(origins),
                    ShenzhenAirFlightInfo.destination.in_(destinations),
                ).limit(2).all()
                if len(records) == 1:
                    result = times_from_record(records[0])
                    fallback_routing = f"{records[0].origin}-{records[0].destination}"
            except Exception as exc:
                logger.warning("深航KingGo航班表查询失败 error_type=%s", type(exc).__name__)
            finally:
                db.close()

        if settings.SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED and any(
            not result.get(key) for key in required_times
        ):
            if not fallback_routing:
                # Ctrip requires airport codes. Do not send Chinese labels or
                # choose an arbitrary airport when a city has several matches.
                logger.warning(
                    "深航携程兜底跳过 reason=ambiguous_or_unknown_airports flight=%s date=%s routing=%s",
                    flight, day, routing,
                )
                return result if any(result.values()) else None
            try:
                fallback = await ctrip_client.get_flight_times(
                    flight, day.isoformat(), fallback_routing, force_refresh=force_refresh
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
