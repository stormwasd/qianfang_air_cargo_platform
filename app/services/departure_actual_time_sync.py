"""深航/南航出港明细实飞时间同步。"""
import asyncio
import threading
from datetime import datetime, timedelta

from sqlalchemy import Integer, case, cast, func, or_

from app.config import settings
from app.database import SessionLocal
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.transit_loading import ShenzhenAirBookingExport
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
            normalized_date = str(flight_date).strip().replace("/", "-")[:10]
            return datetime.strptime(
                f"{normalized_date} {digits[:2]}:{digits[2:]}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            return None
    return None


def _parse_attempt_count(value):
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        try:
            return max(0, int(float(str(value).strip())))
        except (TypeError, ValueError):
            return 0


class DepartureActualTimeSync:
    BATCH_SIZE = 200

    def __init__(self):
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[DepartureActualTimeSync] 已启动深航/南航实飞时间同步")

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
                self._backfill_completion_flags()
            except Exception as exc:
                print(f"[DepartureActualTimeSync] 历史完成标记补偿异常: {exc}")

            airline_names = ("深航", "南航")
            results = await asyncio.gather(
                self._sync_shenzhen(),
                self._sync_csa(),
                return_exceptions=True,
            )
            for airline_name, result in zip(airline_names, results):
                if isinstance(result, Exception):
                    # 两个航司并行且相互隔离，单侧异常或慢请求不阻断另一侧。
                    print(f"[DepartureActualTimeSync] {airline_name}同步异常: {result}")
            await asyncio.sleep(60)

    @staticmethod
    def _backfill_completion_flags():
        """补偿旧版本已抓到完整子项、但父记录完成标记未写入的数据。"""
        db = SessionLocal()
        try:
            shenzhen_invalid_count = func.sum(case(
                (
                    or_(
                        ShenzhenAirBillingTimeContainer.flight_number.is_(None),
                        func.trim(ShenzhenAirBillingTimeContainer.flight_number) == "",
                    ),
                    1,
                ),
                else_=0,
            ))
            shenzhen_ids = [
                row_id
                for (row_id,) in (
                    db.query(ShenzhenAirBillingTimeContainer.booking_export_id)
                    .join(
                        ShenzhenAirBookingExport,
                        ShenzhenAirBookingExport.id
                        == ShenzhenAirBillingTimeContainer.booking_export_id,
                    )
                    .filter(or_(
                        ShenzhenAirBookingExport.departure_tracking_completed.is_(None),
                        ShenzhenAirBookingExport.departure_tracking_completed != "1",
                    ))
                    .group_by(ShenzhenAirBillingTimeContainer.booking_export_id)
                    .having(func.count(ShenzhenAirBillingTimeContainer.id) > 0)
                    .having(shenzhen_invalid_count == 0)
                    .limit(DepartureActualTimeSync.BATCH_SIZE)
                    .all()
                )
            ]

            csa_invalid_count = func.sum(case(
                (
                    or_(
                        CsaLalamoveInformation.pre_assigned_flight.is_(None),
                        func.trim(CsaLalamoveInformation.pre_assigned_flight) == "",
                    ),
                    1,
                ),
                else_=0,
            ))
            csa_ids = [
                row_id
                for (row_id,) in (
                    db.query(CsaLalamoveInformation.approval_data_id)
                    .join(
                        ChinaSouthernAirApprovalData,
                        ChinaSouthernAirApprovalData.id
                        == CsaLalamoveInformation.approval_data_id,
                    )
                    .filter(or_(
                        ChinaSouthernAirApprovalData.departure_tracking_completed.is_(None),
                        ChinaSouthernAirApprovalData.departure_tracking_completed != "1",
                    ))
                    .group_by(CsaLalamoveInformation.approval_data_id)
                    .having(func.count(CsaLalamoveInformation.id) > 0)
                    .having(csa_invalid_count == 0)
                    .limit(DepartureActualTimeSync.BATCH_SIZE)
                    .all()
                )
            ]

            updated = 0
            if shenzhen_ids:
                updated += db.query(ShenzhenAirBookingExport).filter(
                    ShenzhenAirBookingExport.id.in_(shenzhen_ids),
                    or_(
                        ShenzhenAirBookingExport.departure_tracking_completed.is_(None),
                        ShenzhenAirBookingExport.departure_tracking_completed != "1",
                    ),
                ).update(
                    {ShenzhenAirBookingExport.departure_tracking_completed: "1"},
                    synchronize_session=False,
                )
            if csa_ids:
                updated += db.query(ChinaSouthernAirApprovalData).filter(
                    ChinaSouthernAirApprovalData.id.in_(csa_ids),
                    or_(
                        ChinaSouthernAirApprovalData.departure_tracking_completed.is_(None),
                        ChinaSouthernAirApprovalData.departure_tracking_completed != "1",
                    ),
                ).update(
                    {ChinaSouthernAirApprovalData.departure_tracking_completed: "1"},
                    synchronize_session=False,
                )
            if updated:
                db.commit()
                print(
                    "[DepartureActualTimeSync] 已补偿历史出港跟踪完成标记: "
                    f"shenzhen={len(shenzhen_ids)}, csa={len(csa_ids)}"
                )
        finally:
            db.close()

    @staticmethod
    def _defer_after_error(
        db,
        model,
        row_id,
        retry_seconds,
        max_attempts,
    ):
        """单条同步失败后持久化下一次时间，避免每分钟反复打同一条数据。"""
        db.rollback()
        try:
            row = db.query(model).filter(model.id == row_id).first()
            if row is not None and row.actual_time is None:
                if _parse_attempt_count(row.actual_time_attempts) >= max_attempts:
                    row.next_actual_time_query_at = None
                else:
                    row.next_actual_time_query_at = (
                        get_china_now().replace(tzinfo=None)
                        + timedelta(seconds=retry_seconds)
                    )
                db.commit()
        except Exception as defer_exc:
            db.rollback()
            print(
                "[DepartureActualTimeSync] 持久化失败记录的下次查询时间异常: "
                f"model={model.__name__}, id={row_id}, error={defer_exc}"
            )

    @staticmethod
    def _claim_actual_time_query(
        db,
        model,
        row_id,
        current_time,
        retry_seconds,
        max_attempts,
    ):
        """原子领取一条到期记录，并在发起请求前记录本次查询。"""
        claimed = db.query(model).filter(
            model.id == row_id,
            model.actual_time.is_(None),
            cast(func.coalesce(model.actual_time_attempts, "0"), Integer)
            < max_attempts,
            or_(
                model.next_actual_time_query_at.is_(None),
                model.next_actual_time_query_at <= current_time,
            ),
        ).update(
            {
                model.next_actual_time_query_at: current_time
                + timedelta(seconds=retry_seconds),
                # 查询次数必须在外部请求前落库。即使请求抛异常或进程中断，
                # 也不会绕过最大次数限制而无限重试。
                model.actual_time_attempts: cast(
                    func.coalesce(model.actual_time_attempts, "0"), Integer
                ) + 1,
            },
            synchronize_session=False,
        )
        db.commit()
        return claimed == 1

    async def _sync_shenzhen(self):
        db = SessionLocal()
        try:
            now = get_china_now().replace(tzinfo=None)
            max_attempts = settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_MAX_ATTEMPTS
            rows = db.query(ShenzhenAirBillingTimeContainer).filter(
                ShenzhenAirBillingTimeContainer.flight_number.isnot(None),
                func.trim(ShenzhenAirBillingTimeContainer.flight_number) != "",
                ShenzhenAirBillingTimeContainer.actual_time.is_(None),
                cast(
                    func.coalesce(
                        ShenzhenAirBillingTimeContainer.actual_time_attempts, "0"
                    ),
                    Integer,
                ) < max_attempts,
                or_(
                    ShenzhenAirBillingTimeContainer.next_actual_time_query_at.is_(None),
                    ShenzhenAirBillingTimeContainer.next_actual_time_query_at <= now,
                ),
            ).order_by(
                case(
                    (
                        ShenzhenAirBillingTimeContainer.next_actual_time_query_at.is_(None),
                        1,
                    ),
                    else_=0,
                ).asc(),
                ShenzhenAirBillingTimeContainer.next_actual_time_query_at.asc(),
                ShenzhenAirBillingTimeContainer.created_at.asc(),
                ShenzhenAirBillingTimeContainer.id.asc(),
            ).limit(self.BATCH_SIZE).all()
            for row in rows:
                row_id = row.id
                flight_label = row.flight_number
                try:
                    current_time = get_china_now().replace(tzinfo=None)
                    if not row.planned_time:
                        result = await ctrip_client.get_flight_times(
                            row.flight_number,
                            row.flight_date,
                            f"{row.origin}-{row.destination}",
                        )
                        planned_time = (
                            (result or {}).get("planned_time") if result else None
                        )
                        if not planned_time:
                            row.next_actual_time_query_at = current_time + timedelta(
                                seconds=settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS
                            )
                            db.commit()
                            continue
                        row.planned_time = str(planned_time)
                        print(
                            "[DepartureActualTimeSync] 深航预飞时间补偿成功: "
                            f"id={row_id}, flight={flight_label}, planned={planned_time}"
                        )

                    planned = _parse_planned(row.planned_time, row.flight_date)
                    if not planned:
                        row.next_actual_time_query_at = current_time + timedelta(
                            seconds=settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS
                        )
                        db.commit()
                        continue

                    first_query_at = planned + timedelta(
                        seconds=settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS
                    )
                    attempt_count = _parse_attempt_count(row.actual_time_attempts)
                    next_query_at = row.next_actual_time_query_at
                    if attempt_count == 0:
                        # planned_time 可能是补偿查询刚取得的，旧的 next 值只是
                        # “再次查询预飞”的时间，不能拿来绕过首次实飞延迟。
                        next_query_at = first_query_at
                    elif next_query_at is None:
                        next_query_at = first_query_at
                    if row.next_actual_time_query_at != next_query_at:
                        row.next_actual_time_query_at = next_query_at
                        db.commit()
                    if current_time < next_query_at:
                        continue

                    if not self._claim_actual_time_query(
                        db,
                        ShenzhenAirBillingTimeContainer,
                        row_id,
                        current_time,
                        settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS,
                        max_attempts,
                    ):
                        continue
                    print(
                        "[DepartureActualTimeSync] 查询深航实飞时间: "
                        f"id={row_id}, flight={flight_label}, "
                        f"attempt={_parse_attempt_count(row.actual_time_attempts)}"
                    )
                    result = await ctrip_client.get_flight_times(
                        row.flight_number,
                        row.flight_date,
                        f"{row.origin}-{row.destination}",
                        force_refresh=True,
                    )
                    if result and result.get("actual_time"):
                        row.actual_time = str(result["actual_time"])
                        row.next_actual_time_query_at = None
                        print(
                            "[DepartureActualTimeSync] 深航实飞时间已写入: "
                            f"id={row_id}, actual_time={row.actual_time}"
                        )
                    else:
                        if _parse_attempt_count(row.actual_time_attempts) >= max_attempts:
                            row.next_actual_time_query_at = None
                        else:
                            row.next_actual_time_query_at = (
                                get_china_now().replace(tzinfo=None) + timedelta(
                                    seconds=settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS
                                )
                            )
                    db.commit()
                except Exception as exc:
                    print(
                        "[DepartureActualTimeSync] 深航单条同步异常: "
                        f"id={row_id}, flight={flight_label}, error={exc}"
                    )
                    self._defer_after_error(
                        db,
                        ShenzhenAirBillingTimeContainer,
                        row_id,
                        settings.RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS,
                        max_attempts,
                    )
        finally:
            db.close()

    async def _sync_csa(self):
        db = SessionLocal()
        try:
            now = get_china_now().replace(tzinfo=None)
            max_attempts = settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_MAX_ATTEMPTS
            rows = db.query(CsaLalamoveInformation, ChinaSouthernAirApprovalData).join(
                ChinaSouthernAirApprovalData,
                CsaLalamoveInformation.approval_data_id == ChinaSouthernAirApprovalData.id,
            ).filter(
                CsaLalamoveInformation.pre_assigned_flight.isnot(None),
                func.trim(CsaLalamoveInformation.pre_assigned_flight) != "",
                CsaLalamoveInformation.actual_time.is_(None),
                cast(
                    func.coalesce(CsaLalamoveInformation.actual_time_attempts, "0"),
                    Integer,
                ) < max_attempts,
                or_(
                    CsaLalamoveInformation.next_actual_time_query_at.is_(None),
                    CsaLalamoveInformation.next_actual_time_query_at <= now,
                ),
            ).order_by(
                case(
                    (CsaLalamoveInformation.next_actual_time_query_at.is_(None), 1),
                    else_=0,
                ).asc(),
                CsaLalamoveInformation.next_actual_time_query_at.asc(),
                CsaLalamoveInformation.created_at.asc(),
                CsaLalamoveInformation.id.asc(),
            ).limit(self.BATCH_SIZE).all()
            for row, approval in rows:
                row_id = row.id
                flight_label = row.pre_assigned_flight
                try:
                    current_time = get_china_now().replace(tzinfo=None)
                    flight_info = str(approval.flight_info or "")
                    parts = [part.strip() for part in flight_info.split("/")]
                    if len(parts) < 3:
                        raise ValueError(f"订舱航班格式无效: {flight_info!r}")
                    flight_date = parts[1]
                    routing = parts[-1].replace(" ", "")
                    actual_flight_no = str(row.pre_assigned_flight).split("/")[0].strip()
                    planned = _parse_planned(
                        approval.planned_takeoff, flight_date
                    ) or _parse_planned(approval.expected_takeoff, flight_date)
                    if not planned:
                        result = await ctrip_client.get_flight_times(
                            actual_flight_no,
                            flight_date,
                            routing,
                        )
                        planned = _parse_planned(
                            (result or {}).get("planned_time"), flight_date
                        )
                        if not planned:
                            row.next_actual_time_query_at = current_time + timedelta(
                                seconds=settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS
                            )
                            db.commit()
                            continue
                        row.next_actual_time_query_at = planned + timedelta(
                            seconds=settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS
                        )
                        db.commit()
                        print(
                            "[DepartureActualTimeSync] 南航预飞时间补偿成功: "
                            f"id={row_id}, flight={flight_label}, planned={planned}"
                        )

                    first_query_at = planned + timedelta(
                        seconds=settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS
                    )
                    attempt_count = _parse_attempt_count(row.actual_time_attempts)
                    next_query_at = row.next_actual_time_query_at
                    if attempt_count == 0:
                        next_query_at = first_query_at
                    elif next_query_at is None:
                        next_query_at = first_query_at
                    if row.next_actual_time_query_at != next_query_at:
                        row.next_actual_time_query_at = next_query_at
                        db.commit()
                    if current_time < next_query_at:
                        continue

                    if not self._claim_actual_time_query(
                        db,
                        CsaLalamoveInformation,
                        row_id,
                        current_time,
                        settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS,
                        max_attempts,
                    ):
                        continue
                    print(
                        "[DepartureActualTimeSync] 查询南航实飞时间: "
                        f"id={row_id}, flight={flight_label}, "
                        f"attempt={_parse_attempt_count(row.actual_time_attempts)}"
                    )
                    result = await ctrip_client.get_flight_times(
                        actual_flight_no,
                        flight_date,
                        routing,
                        force_refresh=True,
                    )
                    if result and result.get("actual_time"):
                        row.actual_time = str(result["actual_time"])
                        row.next_actual_time_query_at = None
                        print(
                            "[DepartureActualTimeSync] 南航实飞时间已写入: "
                            f"id={row_id}, actual_time={row.actual_time}"
                        )
                    else:
                        if _parse_attempt_count(row.actual_time_attempts) >= max_attempts:
                            row.next_actual_time_query_at = None
                        else:
                            row.next_actual_time_query_at = (
                                get_china_now().replace(tzinfo=None) + timedelta(
                                    seconds=settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS
                                )
                            )
                    db.commit()
                except Exception as exc:
                    print(
                        "[DepartureActualTimeSync] 南航单条同步异常: "
                        f"id={row_id}, flight={flight_label}, error={exc}"
                    )
                    self._defer_after_error(
                        db,
                        CsaLalamoveInformation,
                        row_id,
                        settings.RPA_CHINA_SOUTHERN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS,
                        max_attempts,
                    )
        finally:
            db.close()


departure_actual_time_sync = DepartureActualTimeSync()
