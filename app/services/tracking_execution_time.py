"""Successful acquisition times, separate from business-data completion."""
from datetime import datetime
import logging

from sqlalchemy import case
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import SessionLocal
from app.models.rpa_task import RPATaskLastSuccess, RPATaskType
from app.utils.helpers import CHINA_TIMEZONE, get_china_now


logger = logging.getLogger(__name__)

DIRECT_APPROVAL_SUCCESS_TYPES = (
    "SHENZHEN_AIR_APPROVAL_DATA_DIRECT",
    "SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY_DIRECT",
)
DIRECT_BILLING_SUCCESS_TYPE = "SHENZHEN_AIR_BILLING_TIME_CONTAINER_DIRECT"
DIRECT_TRANSIT_LOADING_SUCCESS_TYPE = "SHENZHEN_AIR_TRANSIT_LOADING_DIRECT"
RPA_EXECUTION_SUCCESS_TYPES = {
    task_type.value: f"{task_type.value}_RPA_RUN"
    for task_type in (
        RPATaskType.SHENZHEN_AIR_APPROVAL_DATA,
        RPATaskType.SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY,
        RPATaskType.SHENZHEN_AIR_BILLING_TIME_CONTAINER,
        RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA,
        RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING,
        RPATaskType.SHENZHEN_AIR_TRANSIT_LOADING,
    )
}


def _china_naive(value: datetime) -> datetime:
    """MySQL DATETIME stores local wall time, not a UTC offset."""
    if value.tzinfo is not None:
        value = value.astimezone(CHINA_TIMEZONE)
    return value.replace(tzinfo=None)


def record_success_time(success_type: str, succeeded_at: datetime | None = None) -> bool:
    """Atomically retain the latest success without committing a caller's work.

    Dedicated keys prevent legacy complete_task() calls from overwriting these
    times. The upsert prevents out-of-order workers from moving time back.
    Timestamp failures never change acquisition or retry decisions.
    """
    try:
        observed_at = _china_naive(get_china_now())
        succeeded_at = _china_naive(succeeded_at) if succeeded_at is not None else observed_at
        with SessionLocal() as db:
            dialect = db.get_bind().dialect.name
            if dialect in ("mysql", "mariadb"):
                statement = mysql_insert(RPATaskLastSuccess).values(
                    task_type=success_type, last_success_at=succeeded_at, updated_at=observed_at
                )
                incoming = statement.inserted.last_success_at
            elif dialect == "sqlite":
                statement = sqlite_insert(RPATaskLastSuccess).values(
                    task_type=success_type, last_success_at=succeeded_at, updated_at=observed_at
                )
                incoming = statement.excluded.last_success_at
            else:
                raise ValueError("Unsupported tracking timestamp database dialect")
            newer = RPATaskLastSuccess.last_success_at < incoming
            updates = {
                "updated_at": case((newer, observed_at), else_=RPATaskLastSuccess.updated_at),
                "last_success_at": case((newer, incoming), else_=RPATaskLastSuccess.last_success_at),
            }
            if dialect in ("mysql", "mariadb"):
                # Evaluate the condition before assigning last_success_at.
                statement = statement.on_duplicate_key_update(list(updates.items()))
            else:
                statement = statement.on_conflict_do_update(index_elements=["task_type"], set_=updates)
            db.execute(statement)
            db.commit()
        return True
    except Exception as exc:
        logger.warning("Tracking success time could not be saved: type=%s, error_type=%s",
                       success_type, type(exc).__name__)
        return False


def record_rpa_execution_success(task_type: str, status_info: dict) -> bool:
    """Use the matched workUuid's endTime; old RPA versions may omit it."""
    success_type = RPA_EXECUTION_SUCCESS_TYPES[task_type]
    raw_end_time = status_info.get("endTime")
    try:
        if isinstance(raw_end_time, datetime):
            end_time = raw_end_time
        else:
            end_time = datetime.fromisoformat(str(raw_end_time).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        # Never substitute a business row's modification time.
        logger.warning("RPA endTime unavailable; using success confirmation time: type=%s", task_type)
        end_time = None
    return record_success_time(success_type, end_time)


def format_success_time(value: datetime | None) -> str | None:
    return _china_naive(value).strftime("%Y-%m-%d %H:%M") if value is not None else None
