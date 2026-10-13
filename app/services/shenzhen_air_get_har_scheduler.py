"""深航获取 HAR 周期调度器。"""

import asyncio
import json
import threading
import traceback
from typing import Optional

from app.config import settings
from app.database import SessionLocal
from app.models.robot import Robot, TaskProcess
from app.models.rpa_task import RPATaskType
from app.services.rpa_task_service import rpa_task_service


TARGET_TYPE = "shenzhen_air_get_har"
DEFAULT_INTERVAL_SECONDS = 1800
DEFAULT_PARAMS = {"system_url": "https://www.kinggo.com/main"}


class ShenzhenAirGetHarScheduler:
    """为拥有深航获取 HAR 权限的启用机器人周期性创建任务。"""

    def __init__(self) -> None:
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[ShenzhenAirGetHarScheduler] 已启动深航获取HAR定时调度器")

    def stop(self) -> None:
        self._stop_event.set()
        print("[ShenzhenAirGetHarScheduler] 已停止深航获取HAR定时调度器")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        if not self._stop_event.is_set():
            try:
                await self._enqueue_tasks()
            except Exception as exc:
                print(f"[ShenzhenAirGetHarScheduler] 启动时入队任务失败: {exc!r}")

        while not self._stop_event.is_set():
            try:
                interval = settings.RPA_SHENZHEN_AIR_GET_HAR_INTERVAL_SECONDS
                remaining = interval if interval > 0 else DEFAULT_INTERVAL_SECONDS
                while remaining > 0 and not self._stop_event.is_set():
                    step = min(5.0, float(remaining))
                    await asyncio.sleep(step)
                    remaining -= step
                if not self._stop_event.is_set():
                    await self._enqueue_tasks()
            except Exception as exc:
                print(
                    "[ShenzhenAirGetHarScheduler] 调度循环异常: "
                    f"{exc!r}\n{traceback.format_exc()}"
                )
                await asyncio.sleep(60)

    @staticmethod
    def _load_process_params(process: Optional[TaskProcess]) -> dict:
        if process and process.process_param:
            try:
                params = json.loads(process.process_param)
                if isinstance(params, dict) and params.get("system_url"):
                    return params
            except (json.JSONDecodeError, TypeError):
                pass
        return dict(DEFAULT_PARAMS)

    async def _enqueue_tasks(self) -> None:
        db = SessionLocal()
        try:
            task_type = RPATaskType.SHENZHEN_AIR_GET_HAR.value
            process = db.query(TaskProcess).filter(
                TaskProcess.task_name == task_type
            ).first()
            params = self._load_process_params(process)

            robots = db.query(Robot).filter(Robot.status == 1).all()
            enqueued_count = 0
            for robot in robots:
                try:
                    permissions = (
                        json.loads(robot.task_permissions)
                        if isinstance(robot.task_permissions, str)
                        else robot.task_permissions
                    )
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(permissions, list) or task_type not in permissions:
                    continue

                existing = rpa_task_service.get_pending_task_for_target(
                    db,
                    target_type=TARGET_TYPE,
                    target_id=robot.id,
                    task_type=task_type,
                )
                if existing:
                    continue

                rpa_task_service.create_task(
                    db=db,
                    task_type=task_type,
                    target_type=TARGET_TYPE,
                    target_id=robot.id,
                    params=params,
                    priority=2,
                    created_by=None,
                    robot_id=robot.id,
                )
                enqueued_count += 1
                print(
                    "[ShenzhenAirGetHarScheduler] 已创建深航获取HAR任务: "
                    f"robot={robot.name}, robot_id={robot.id}"
                )

            if not enqueued_count:
                print("[ShenzhenAirGetHarScheduler] 本轮没有需要创建的深航获取HAR任务")
        except Exception as exc:
            db.rollback()
            print(
                "[ShenzhenAirGetHarScheduler] 生成HAR任务异常: "
                f"{exc!r}\n{traceback.format_exc()}"
            )
        finally:
            db.close()


shenzhen_air_get_har_scheduler = ShenzhenAirGetHarScheduler()
