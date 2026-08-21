"""南航货物类型数据字典自动同步。"""
import asyncio
import logging
import threading
from typing import Dict, List, Mapping, Optional, Sequence

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.models.nanhang_token import NanHangToken
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirServiceError,
    china_southern_air_service,
)
from app.utils.helpers import get_china_now


logger = logging.getLogger(__name__)

CARGO_TYPE_DICT_TYPE = "nanfang_air_cargo_type"
CARGO_TYPE_DICT_NAME = "南航货物类型"


class CsaCargoTypeSyncError(Exception):
    """南航货物类型同步前置条件或本地覆盖失败。"""


def replace_cargo_type_dict_options(
    db: Session,
    options: Sequence[Mapping[str, str]],
) -> int:
    """在当前事务中完整替换南航货物类型字典选项。"""
    if not options:
        raise CsaCargoTypeSyncError("南航货物类型列表为空，已保留原数据字典")

    normalized: List[Dict[str, str]] = []
    seen_labels: Dict[str, str] = {}
    for index, item in enumerate(options):
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if not label or not value:
            raise CsaCargoTypeSyncError(
                f"南航货物类型第 {index + 1} 项名称或代码为空，已保留原数据字典"
            )
        previous_value = seen_labels.get(label)
        if previous_value is not None:
            if previous_value != value:
                raise CsaCargoTypeSyncError(
                    f"南航货物类型名称“{label}”对应多个代码，已保留原数据字典"
                )
            continue
        seen_labels[label] = value
        normalized.append({"label": label, "value": value})

    # 锁定字典类型行，使同一数据库上的并发覆盖按事务串行执行。
    dict_type = (
        db.query(DictType)
        .filter(DictType.type == CARGO_TYPE_DICT_TYPE)
        .with_for_update()
        .first()
    )
    now = get_china_now()
    if dict_type is None:
        dict_type = DictType(
            name=CARGO_TYPE_DICT_NAME,
            type=CARGO_TYPE_DICT_TYPE,
            status=1,
            created_at=now,
            updated_at=now,
        )
        db.add(dict_type)
        db.flush()
    else:
        dict_type.updated_at = now

    (
        db.query(DictOption)
        .filter(DictOption.dict_type_id == dict_type.id)
        .delete(synchronize_session=False)
    )
    db.flush()

    db.add_all(
        [
            DictOption(
                dict_type_id=dict_type.id,
                label=item["label"],
                value=item["value"],
                status=1,
                color_type=None,
                created_at=now,
                updated_at=now,
            )
            for item in normalized
        ]
    )
    db.flush()
    return len(normalized)


def _load_latest_nanhang_token() -> str:
    db = SessionLocal()
    try:
        token_record = (
            db.query(NanHangToken)
            .filter(NanHangToken.token.isnot(None), NanHangToken.token != "")
            .order_by(NanHangToken.updated_at.desc(), NanHangToken.id.desc())
            .first()
        )
        if token_record is None:
            raise CsaCargoTypeSyncError(
                "暂无可用的南航 Token，暂不覆盖货物类型数据字典"
            )
        return token_record.token
    finally:
        db.close()


async def sync_csa_cargo_types_once() -> int:
    """调用南航接口并以单事务覆盖货物类型字典，返回写入数量。"""
    token = _load_latest_nanhang_token()
    options = await china_southern_air_service.query_shipment_types(token=token)

    db = SessionLocal()
    try:
        option_count = replace_cargo_type_dict_options(db, options)
        db.commit()
        return option_count
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


class CsaCargoTypeSyncScheduler:
    """启动立即同步，成功后按配置周期重复同步。"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        if not settings.CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_ENABLED:
            logger.info("[CsaCargoTypeSync] 南航货物类型自动同步已禁用")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="csa-cargo-type-sync",
            daemon=True,
        )
        self._thread.start()
        logger.info("[CsaCargoTypeSync] 已启动南航货物类型自动同步")

    def stop(self) -> None:
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=6)
        self._thread = None
        logger.info("[CsaCargoTypeSync] 已停止南航货物类型自动同步")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        while not self._stop_event.is_set():
            succeeded = False
            try:
                count = await sync_csa_cargo_types_once()
                succeeded = True
                logger.info(
                    "[CsaCargoTypeSync] 已覆盖 %s，共写入 %d 个货物类型",
                    CARGO_TYPE_DICT_TYPE,
                    count,
                )
            except (ChinaSouthernAirServiceError, CsaCargoTypeSyncError) as exc:
                logger.warning("[CsaCargoTypeSync] 同步未完成：%s", exc)
            except Exception:
                logger.exception("[CsaCargoTypeSync] 同步发生未预期异常，原字典已回滚保留")

            delay = (
                settings.CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_INTERVAL_SECONDS
                if succeeded
                else settings.CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_RETRY_SECONDS
            )
            await self._wait_until_next_run(delay)

    async def _wait_until_next_run(self, delay_seconds: int) -> None:
        remaining = max(1, int(delay_seconds))
        while remaining > 0 and not self._stop_event.is_set():
            step = min(5, remaining)
            await asyncio.sleep(step)
            remaining -= step


csa_cargo_type_sync_scheduler = CsaCargoTypeSyncScheduler()
