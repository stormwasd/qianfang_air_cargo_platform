"""南航最近导入批次单号可用性后台扫描。"""
import asyncio
import logging
import threading
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.booking import Booking
from app.models.nanhang_token import NanHangToken
from app.models.waybill import Waybill
from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirServiceError,
    china_southern_air_service,
)
from app.utils.helpers import CHINA_TIMEZONE, get_china_now


logger = logging.getLogger("uvicorn.error")

AUTOMATIC_INVALID_REASONS = (
    "南航提示运单号已被使用",
    "南航开单结果不确定",
    "南航订舱结果不确定",
    "南航开单调用异常",
    "南航订舱调用异常",
)


class CsaWaybillStockScanError(Exception):
    """扫描整轮无法开始时的前置条件异常。"""


def _load_latest_nanhang_token() -> str:
    db = SessionLocal()
    try:
        token_record = (
            db.query(NanHangToken)
            .filter(NanHangToken.token.isnot(None), NanHangToken.token != "")
            .order_by(NanHangToken.updated_at.desc(), NanHangToken.id.desc())
            .first()
        )
        if token_record is not None:
            token = china_southern_air_service._clean_token(token_record.token)
            if token:
                return token
        raise CsaWaybillStockScanError("nanhang_token 中没有可用Token")
    finally:
        db.close()


def get_latest_csa_batch_item_ids(db: Session) -> tuple[Optional[int], List[int]]:
    """只返回南航最近导入的一个批次及其全部单号 ID。"""
    latest_batch = (
        db.query(WaybillStockBatch)
        .join(WaybillStock, WaybillStockBatch.stock_id == WaybillStock.id)
        .filter(WaybillStock.airline_name == "china_southern_air")
        .order_by(
            WaybillStockBatch.claim_date.desc(),
            WaybillStockBatch.created_at.desc(),
            WaybillStockBatch.id.desc(),
        )
        .first()
    )
    if latest_batch is None:
        return None, []
    item_ids = [
        item_id
        for (item_id,) in (
            db.query(WaybillStockItem.id)
            .filter(WaybillStockItem.batch_id == latest_batch.id)
            .order_by(WaybillStockItem.id.asc())
            .all()
        )
    ]
    return latest_batch.id, item_ids


def orders_indicate_waybill_used(orders: List[Dict]) -> bool:
    """空列表或全部已取消为未使用；任一其他状态即为已使用。"""
    return bool(orders) and any(
        str(item.get("statusCN") or "").strip() != "已取消" for item in orders
    )


def _has_local_execution_in_progress(db: Session, full_number: str) -> bool:
    booking_exists = (
        db.query(Booking.id)
        .filter(
            Booking.master_airwaybill_number == full_number,
            Booking.booking_status == "1",
        )
        .first()
        is not None
    )
    if booking_exists:
        return True
    return (
        db.query(Waybill.id)
        .filter(
            Waybill.waybill_number == full_number,
            Waybill.airline_record_status == "1",
        )
        .first()
        is not None
    )


def _is_within_release_grace(item: WaybillStockItem) -> bool:
    grace_seconds = settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_RELEASE_GRACE_SECONDS
    if grace_seconds <= 0 or item.updated_at is None:
        return False
    updated_at = item.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=CHINA_TIMEZONE)
    return (get_china_now() - updated_at).total_seconds() < grace_seconds


def synchronize_stock_item_status(
    db: Session,
    stock_item_id: int,
    *,
    is_used_by_csa: bool,
) -> str:
    """锁定单号并按南航结果双向校准，返回处理结果。"""
    item = (
        db.query(WaybillStockItem)
        .filter(WaybillStockItem.id == stock_item_id)
        .with_for_update()
        .first()
    )
    if item is None:
        return "missing"

    if is_used_by_csa:
        changed = item.usage_status != "1" or item.usage_date is None
        item.usage_status = "1"
        if item.usage_date is None:
            item.usage_date = get_china_now().date()
        return "marked_used" if changed else "unchanged_used"

    # 南航订单刚创建时查询接口可能存在短暂延迟；同时保护本系统正在提交的单号。
    if item.usage_status == "1" and (
        _has_local_execution_in_progress(db, item.full_number)
        or _is_within_release_grace(item)
    ):
        return "protected"

    changed = item.usage_status != "0" or item.usage_date is not None
    item.usage_status = "0"
    item.usage_date = None

    # 仅解除系统因南航占用/结果不确定而自动设置的隔离，保留人工失效原因。
    invalid_reason = str(item.invalid_reason or "").strip()
    if item.is_invalid == "1" and invalid_reason.startswith(AUTOMATIC_INVALID_REASONS):
        item.is_invalid = "0"
        item.invalid_reason = None
        changed = True
    return "marked_unused" if changed else "unchanged_unused"


async def scan_latest_csa_waybill_batch_once(
    *,
    wait_between_items: Optional[Callable[[int], Awaitable[None]]] = None,
    should_stop: Optional[Callable[[], bool]] = None,
) -> Dict[str, int]:
    """扫描南航最近一批单号；单条失败不会中断其余单号。"""
    token = _load_latest_nanhang_token()
    db = SessionLocal()
    try:
        batch_id, item_ids = get_latest_csa_batch_item_ids(db)
    finally:
        db.close()

    stats = {
        "batch_id": batch_id or 0,
        "total": len(item_ids),
        "checked": 0,
        "marked_used": 0,
        "marked_unused": 0,
        "protected": 0,
        "failed": 0,
    }
    if batch_id is None:
        return stats

    for index, item_id in enumerate(item_ids):
        if should_stop and should_stop():
            break

        db = SessionLocal()
        try:
            item = db.query(WaybillStockItem).filter(WaybillStockItem.id == item_id).first()
            if item is None:
                continue
            awb_no = item.number_suffix
            full_number = item.full_number
        finally:
            db.close()

        try:
            orders = await china_southern_air_service.query_waybill_orders(
                token=token,
                awb_no=awb_no,
            )
            db = SessionLocal()
            try:
                result = synchronize_stock_item_status(
                    db,
                    item_id,
                    is_used_by_csa=orders_indicate_waybill_used(orders),
                )
                db.commit()
            except Exception:
                db.rollback()
                raise
            finally:
                db.close()

            stats["checked"] += 1
            if result in stats:
                stats[result] += 1
            logger.info(
                "[CsaWaybillStockScan] 单号 %s 扫描完成：%s，南航订单数=%d",
                full_number,
                result,
                len(orders),
            )
        except Exception as exc:
            stats["failed"] += 1
            logger.warning(
                "[CsaWaybillStockScan] 单号 %s 扫描失败，保持原状态：%s",
                full_number,
                exc,
            )

        if index < len(item_ids) - 1:
            delay = settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_ITEM_INTERVAL_SECONDS
            if wait_between_items is not None:
                await wait_between_items(delay)
            else:
                await asyncio.sleep(delay)

    return stats


class CsaWaybillStockScanScheduler:
    """服务启动立即扫描，之后按周期扫描最近导入批次。"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_ENABLED:
            logger.info("[CsaWaybillStockScan] 南航单号可用性扫描已禁用")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="csa-waybill-stock-scan",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            "[CsaWaybillStockScan] 调度器已启动，将立即扫描最近导入批次；"
            "单号间隔=%d秒，轮次间隔=%d秒",
            settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_ITEM_INTERVAL_SECONDS,
            settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_CYCLE_INTERVAL_SECONDS,
        )

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=6)
        self._thread = None
        logger.info("[CsaWaybillStockScan] 南航单号可用性扫描已停止")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        except Exception:
            logger.exception("[CsaWaybillStockScan] 调度线程异常退出")
        finally:
            loop.close()

    async def _async_main(self) -> None:
        while not self._stop_event.is_set():
            succeeded = False
            try:
                logger.info("[CsaWaybillStockScan] 开始扫描南航最近导入批次")
                stats = await scan_latest_csa_waybill_batch_once(
                    wait_between_items=self._wait_until_next_run,
                    should_stop=self._stop_event.is_set,
                )
                succeeded = True
                logger.info(
                    "[CsaWaybillStockScan] 本轮完成：批次=%s，总数=%d，已检查=%d，"
                    "改为已使用=%d，回流未使用=%d，保护跳过=%d，失败=%d",
                    stats["batch_id"] or "无",
                    stats["total"],
                    stats["checked"],
                    stats["marked_used"],
                    stats["marked_unused"],
                    stats["protected"],
                    stats["failed"],
                )
            except (CsaWaybillStockScanError, ChinaSouthernAirServiceError) as exc:
                logger.warning("[CsaWaybillStockScan] 本轮未启动：%s", exc)
            except Exception:
                logger.exception("[CsaWaybillStockScan] 本轮发生未预期异常")

            delay = (
                settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_CYCLE_INTERVAL_SECONDS
                if succeeded
                else settings.CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_RETRY_SECONDS
            )
            await self._wait_until_next_run(delay)

    async def _wait_until_next_run(self, delay_seconds: int) -> None:
        remaining = max(0, int(delay_seconds))
        while remaining > 0 and not self._stop_event.is_set():
            step = min(5, remaining)
            await asyncio.sleep(step)
            remaining -= step


csa_waybill_stock_scan_scheduler = CsaWaybillStockScanScheduler()
