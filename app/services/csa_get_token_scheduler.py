"""
南航获取Token定时调度器
定期为分配了“南航获取token”权限的机器人触发 Token 获取任务
"""

import json
import asyncio
import threading
import traceback
from typing import Optional

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATaskType
from app.models.robot import Robot, TaskProcess
from app.services.rpa_task_service import rpa_task_service

TARGET_TYPE = "csa_get_token"


class CsaGetTokenScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[CsaGetTokenScheduler] 已启动南航获取Token定时调度器")

    def stop(self) -> None:
        self._stop_event.set()
        print("[CsaGetTokenScheduler] 已停止南航获取Token定时调度器")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        """主循环"""
        if not self._stop_event.is_set():
            try:
                await self._enqueue_tasks()
            except Exception as e:
                print(f"[CsaGetTokenScheduler] 启动时入队任务失败: {repr(e)}")

        while not self._stop_event.is_set():
            try:
                interval = getattr(settings, "RPA_CHINA_SOUTHERN_AIR_GET_TOKEN_INTERVAL_SECONDS", 1800)
                remaining = interval if interval and interval > 0 else 1800

                while remaining > 0 and not self._stop_event.is_set():
                    step = min(5.0, float(remaining))
                    await asyncio.sleep(step)
                    remaining -= step

                if not self._stop_event.is_set():
                    await self._enqueue_tasks()

            except Exception as e:
                print(f"[CsaGetTokenScheduler] 调度循环异常: {repr(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(60)

    async def _enqueue_tasks(self) -> None:
        """为所有南航机器人（包含分配了“南航获取token”或拥有任意南航业务权限的启用机器人）创建获取 Token 任务"""
        db = SessionLocal()
        try:
            task_type = RPATaskType.CHINA_SOUTHERN_AIR_GET_TOKEN.value

            robots = db.query(Robot).filter(Robot.status == 1).all()
            target_robots = []

            for robot in robots:
                if not robot.task_permissions:
                    continue
                try:
                    perms = json.loads(robot.task_permissions) if isinstance(robot.task_permissions, str) else robot.task_permissions
                    if isinstance(perms, list):
                        is_csa_robot = task_type in perms or any(isinstance(p, str) and p.startswith("CHINA_SOUTHERN_AIR_") for p in perms)
                        if is_csa_robot:
                            target_robots.append((robot, perms))
                except Exception:
                    continue

            if not target_robots:
                print("[CsaGetTokenScheduler] 当前没有启用的南航机器人，暂不生成 Token 任务")
                return

            task_process = db.query(TaskProcess).filter(
                TaskProcess.task_name == task_type
            ).first()

            base_params = {}
            if task_process and task_process.process_param:
                try:
                    base_params = json.loads(task_process.process_param)
                except Exception:
                    base_params = {}

            if not base_params:
                base_params = {
                    "system_url": "https://cargo.csair.com/tangb2gweb/order-management",
                    "queue_token_name": ""
                }

            from app.services.robot_job_service import RobotJobService

            for robot, perms in target_robots:
                # 自动为南航机器人补充 CHINA_SOUTHERN_AIR_GET_TOKEN 权限及专属队列记录
                if task_type not in perms:
                    perms.append(task_type)
                    robot.task_permissions = json.dumps(perms, ensure_ascii=False)
                    db.commit()

                # 保证该机器人的 robot_queues 关联记录自动建立
                RobotJobService._sync_robot_queues(db, robot, [task_type])

                existing = rpa_task_service.get_pending_task_for_target(
                    db,
                    target_type=TARGET_TYPE,
                    target_id=robot.id,
                    task_type=task_type,
                )
                if existing:
                    continue

                new_task = rpa_task_service.create_task(
                    db=db,
                    task_type=task_type,
                    target_type=TARGET_TYPE,
                    target_id=robot.id,
                    params=base_params,
                    job_uuid=None,
                    priority=2,
                    created_by=None,
                    robot_id=robot.id,
                )
                print(f"[CsaGetTokenScheduler] 已成功为机器人 '{robot.name}' (ID: {robot.id}) 生成南航获取Token任务: task_id={new_task.id}")
        except Exception as e:
            db.rollback()
            print(f"[CsaGetTokenScheduler] 生成 Token 任务过程发生异常: {str(e)}\n{traceback.format_exc()}")
        finally:
            db.close()



csa_get_token_scheduler = CsaGetTokenScheduler()
