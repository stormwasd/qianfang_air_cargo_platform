"""深航/南航出港明细实飞时间同步。"""
import asyncio
import threading
from datetime import datetime, timedelta

from app.config import settings
from app.database import SessionLocal
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.utils.ctrip_client import ctrip_client
from app.utils.helpers import get_china_now


def _parse_dt(value):
    if not value:
        return None
    try:
        text = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=None) if dt.tzinfo else dt
    except (TypeError, ValueError):
        return None


def _parse_planned(value, flight_date=None):
    parsed = _parse_dt(value)
    if parsed or not flight_date:
        return parsed
    text = str(value or "").strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) in (3, 4):
        try:
            digits = digits.zfill(4)
            return datetime.strptime(f"{flight_date} {digits[:2]}:{digits[2:]}", "%Y-%m-%d %H:%M")
        except ValueError:
            return None
    return None


class DepartureActualTimeSync:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._main())
        finally:
            loop.close()

    async def _main(self):
        while not self._stop.is_set():
            try:
                await self._sync_shenzhen()
                await self._sync_csa()
            except Exception as exc:
                print(f"[DepartureActualTimeSync] 同步异常: {exc}")
            await asyncio.sleep(60)

    async def _sync_shenzhen(self):
        db = SessionLocal()
        try:
            now = get_china_now()
            rows = db.query(ShenzhenAirBillingTimeContainer).filter(
                ShenzhenAirBillingTimeContainer.flight_number.isnot(None),
                ShenzhenAirBillingTimeContainer.flight_number != "",
                ShenzhenAirBillingTimeContainer.planned_time.isnot(None),
                ShenzhenAirBillingTimeContainer.actual_time.is_(None),
            ).limit(200).all()
            for row in rows:
                if (int(row.actual_time_attempts or 0) >= settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_MAX_ATTEMPTS):
                    continue
                planned = _parse_planned(row.planned_time, row.flight_date)
                if not planned or now < planned + timedelta(seconds=settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_INTERVAL_SECONDS):
                    continue
                result = await ctrip_client.get_flight_times(row.flight_number, row.flight_date, f"{row.origin}-{row.destination}")
                row.actual_time_attempts = str(int(row.actual_time_attempts or 0) + 1)
                if result and result.get("actual_time"):
                    row.actual_time = str(result["actual_time"])
            db.commit()
        finally:
            db.close()

    async def _sync_csa(self):
        db = SessionLocal()
        try:
            now = get_china_now()
            rows = db.query(CsaLalamoveInformation, ChinaSouthernAirApprovalData).join(
                ChinaSouthernAirApprovalData,
                CsaLalamoveInformation.approval_data_id == ChinaSouthernAirApprovalData.id,
            ).filter(
                CsaLalamoveInformation.pre_assigned_flight.isnot(None),
                CsaLalamoveInformation.pre_assigned_flight != "",
                CsaLalamoveInformation.actual_time.is_(None),
            ).limit(200).all()
            for row, approval in rows:
                if int(row.actual_time_attempts or 0) >= settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_MAX_ATTEMPTS:
                    continue
                flight_info = str(approval.flight_info or "")
                parts = [p.strip() for p in flight_info.split("/")]
                if len(parts) < 3:
                    continue
                flight_no, flight_date, routing = parts[0], parts[1], parts[2].replace(" ", "")
                planned = _parse_planned(approval.planned_takeoff, flight_date) or _parse_planned(approval.expected_takeoff, flight_date)
                if not planned or now < planned + timedelta(seconds=settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_INTERVAL_SECONDS):
                    continue
                result = await ctrip_client.get_flight_times(str(row.pre_assigned_flight).split("/")[0].strip(), flight_date, routing)
                row.actual_time_attempts = str(int(row.actual_time_attempts or 0) + 1)
                if result and result.get("actual_time"):
                    row.actual_time = str(result["actual_time"])
            db.commit()
        finally:
            db.close()


departure_actual_time_sync = DepartureActualTimeSync()
