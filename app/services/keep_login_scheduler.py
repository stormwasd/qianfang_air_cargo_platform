"""
保持登录调度器

作用：
1. 从数据库 `BusinessConfig` 读取 system_account/login_password
2. 按配置的时间间隔创建保持登录RPATask
3. 由现有 RPAWorker 消费并调用对应RPA jobUuid

注意：该调度流程不涉及机器人端队列数据（不创建/读取/删除RPA队列）。
"""

import json
import asyncio
import threading
import traceback
from typing import Any, Dict, Optional, Callable

from app.config import settings
from app.database import SessionLocal
from app.models.config import BusinessConfig
from app.models.rpa_task import RPATaskType
from app.services.rpa_task_service import rpa_task_service


KEEP_LOGIN_TARGET_TYPE = "keep_login"


def _get_business_config_dict(db_session) -> Dict[str, Any]:
    """读取 BusinessConfig.config_data 并解析为 dict。"""
    config = db_session.query(BusinessConfig).first()
    if not config or not config.config_data:
        return {}
    try:
        return json.loads(config.config_data)
    except Exception:
        return {}


def _load_shenzhen_air_keep_login_creds(business_config: Dict[str, Any]) -> Dict[str, str]:
    """读取深航保持登录 system_account/login_password。"""
    shenzhen_air_config = business_config.get("shenzhen_air", {})
    booking_config = shenzhen_air_config.get("booking", {})
    login_config = booking_config.get("shenzhen_air_login", {})

    return {
        "system_account": login_config.get("system_account", ""),
        "login_password": login_config.get("login_password", ""),
    }


def _load_china_southern_air_keep_login_creds(business_config: Dict[str, Any]) -> Dict[str, str]:
    """读取南航保持登录 system_account/login_password。"""
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    login_config = booking_and_create_config.get("china_southern_air_login", {})

    return {
        "system_account": login_config.get("system_account", ""),
        "login_password": login_config.get("login_password", ""),
    }


def _load_tangyi_keep_login_creds(business_config: Dict[str, Any]) -> Dict[str, str]:
    """
    读取唐翼保持登录 system_account/login_password。

    兼容策略：
    - 优先读取 `booking_and_create.tangi_login` 的 system_account/login_password（如果配置了）
    - 否则回退到 `booking_and_create.china_southern_air_login` 的 system_account/login_password
      （与现有“南航相关流程传参”保持一致，降低变更风险）
    """
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})

    tangi_login = booking_and_create_config.get("tangi_login", {})
    csa_login = booking_and_create_config.get("china_southern_air_login", {})

    system_account = tangi_login.get("system_account", "") or csa_login.get("system_account", "")
    login_password = tangi_login.get("login_password", "") or csa_login.get("login_password", "")

    return {
        "system_account": system_account,
        "login_password": login_password,
    }


class KeepLoginRunner:
    """
    单个保持登录任务的周期调度器

    每个Runner负责：
    - 按间隔创建一个 RPATask（若当前没有 pending/running）
    - 任务参数只包含 system_account/login_password
    """

    def __init__(
        self,
        *,
        task_type: RPATaskType,
        interval_attr_name: str,
        target_id: int,
        job_uuid: str,
        cred_loader: Callable[[Dict[str, Any]], Dict[str, str]],
    ):
        self.task_type = task_type
        self.interval_attr_name = interval_attr_name
        self.target_id = target_id
        self.job_uuid = job_uuid
        self.cred_loader = cred_loader

    def _get_interval_seconds(self) -> Optional[int]:
        return getattr(settings, self.interval_attr_name, None)

    async def _enqueue_once(self) -> None:
        db = SessionLocal()
        try:
            existing = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=KEEP_LOGIN_TARGET_TYPE,
                target_id=self.target_id,
                task_type=self.task_type.value,
            )
            if existing:
                return

            business_config = _get_business_config_dict(db)
            creds = self.cred_loader(business_config)
            system_account = creds.get("system_account", "")
            login_password = creds.get("login_password", "")
            if not system_account or not login_password:
                print(
                    f"[KeepLoginRunner] 缺少保持登录凭据: task_type={self.task_type.value}, target_id={self.target_id}"
                )
                return

            params = {
                "system_account": system_account,
                "login_password": login_password,
            }

            rpa_task_service.create_task(
                db=db,
                task_type=self.task_type.value,
                target_type=KEEP_LOGIN_TARGET_TYPE,
                target_id=self.target_id,
                params=params,
                job_uuid=self.job_uuid,
                priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
                created_by=None,
            )

        except Exception as e:
            print(
                f"[KeepLoginRunner] 入队失败: task_type={self.task_type.value}, target_id={self.target_id}, error={repr(e)}\n"
                f"{traceback.format_exc()}"
            )
            db.rollback()
        finally:
            db.close()

    async def run(self, stop_event: threading.Event) -> None:
        # 先立即尝试入队一次，避免“启动后必须等满一个interval”
        while not stop_event.is_set():
            if not settings.RPA_KEEP_LOGIN_ENABLED:
                await asyncio.sleep(10)
                continue

            interval_seconds = self._get_interval_seconds()
            if not interval_seconds:
                # 未配置间隔 => 不入队
                await asyncio.sleep(60)
                continue

            await self._enqueue_once()

            # 分段sleep：让stop_event能够更快生效
            remaining = interval_seconds
            while remaining > 0 and not stop_event.is_set():
                step = min(5, remaining)
                await asyncio.sleep(step)
                remaining -= step


class KeepLoginScheduler:
    """全局保持登录调度器（启动多个Runner并在停机时停止）"""

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._runners: list[KeepLoginRunner] = []

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        self._runners = [
            KeepLoginRunner(
                task_type=RPATaskType.CHINA_SOUTHERN_AIR_KEEP_LOGIN,
                interval_attr_name="RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_INTERVAL_SECONDS",
                target_id=1,
                job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_JOB_UUID,
                cred_loader=_load_china_southern_air_keep_login_creds,
            ),
            KeepLoginRunner(
                task_type=RPATaskType.SHENZHEN_AIR_KEEP_LOGIN,
                interval_attr_name="RPA_SHENZHEN_AIR_KEEP_LOGIN_INTERVAL_SECONDS",
                target_id=2,
                job_uuid=settings.RPA_SHENZHEN_AIR_KEEP_LOGIN_JOB_UUID,
                cred_loader=_load_shenzhen_air_keep_login_creds,
            ),
            KeepLoginRunner(
                task_type=RPATaskType.TANGYI_KEEP_LOGIN,
                interval_attr_name="RPA_TANGYI_KEEP_LOGIN_INTERVAL_SECONDS",
                target_id=3,
                job_uuid=settings.RPA_TANGYI_KEEP_LOGIN_JOB_UUID,
                cred_loader=_load_tangyi_keep_login_creds,
            ),
        ]

        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[KeepLoginScheduler] 已启动保持登录调度器")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        await asyncio.gather(*(runner.run(self._stop_event) for runner in self._runners))

    def stop(self) -> None:
        self._stop_event.set()
        print("[KeepLoginScheduler] 已停止保持登录调度器")


# 全局单例
rpa_keep_login_scheduler = KeepLoginScheduler()

