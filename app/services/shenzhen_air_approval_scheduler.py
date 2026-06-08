"""
深航订舱批复数据获取调度器
1. 后台服务重启时立即运行一次
2. 每天18:00定时运行
"""

import json
import asyncio
import threading
import traceback
from datetime import datetime, timedelta
from typing import Optional

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATaskType
from app.models.robot import TaskProcess
from app.services.rpa_task_service import rpa_task_service


TARGET_TYPE = "shenzhen_air_approval_data"


class ShenzhenAirApprovalScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[ShenzhenAirApprovalScheduler] 已启动深航订舱批复数据获取调度器")

    def stop(self) -> None:
        self._stop_event.set()
        print("[ShenzhenAirApprovalScheduler] 已停止深航订舱批复数据获取调度器")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        """主循环"""
        # 1. 启动时立即执行一次下发
        if not self._stop_event.is_set():
            try:
                await self._enqueue_task()
            except Exception as e:
                print(f"[ShenzhenAirApprovalScheduler] 启动时入队失败: {repr(e)}")

        # 2. 定时每天指定时间执行（可配置，默认18:00）
        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                # 从配置读取执行时间，例如 "18:00"
                time_str = getattr(settings, "RPA_SHENZHEN_AIR_APPROVAL_DATA_TIME", "18:00")
                try:
                    hour, minute = map(int, time_str.split(':'))
                except ValueError:
                    hour, minute = 18, 0

                # 计算下一个目标时间
                target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                if now >= target:
                    target += timedelta(days=1)
                
                seconds_to_wait = (target - now).total_seconds()
                
                # 分段 sleep，以支持及时 stop
                while seconds_to_wait > 0 and not self._stop_event.is_set():
                    step = min(5.0, seconds_to_wait)
                    await asyncio.sleep(step)
                    seconds_to_wait -= step
                
                if not self._stop_event.is_set():
                    await self._enqueue_task()

            except Exception as e:
                print(f"[ShenzhenAirApprovalScheduler] 调度循环异常: {repr(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(60)  # 异常后等待一分钟重试

    async def _enqueue_task(self) -> None:
        """创建任务"""
        db = SessionLocal()
        try:
            # 检查是否有未处理完的相同任务，避免重复下发
            existing = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=TARGET_TYPE,
                target_id=1,
                task_type=RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value,
            )
            if existing:
                return

            # 查询数据库里的基础参数
            task_process = db.query(TaskProcess).filter(
                TaskProcess.task_name == RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value
            ).first()
            
            params = {}
            if task_process and task_process.process_param:
                try:
                    params = json.loads(task_process.process_param)
                except Exception:
                    pass
            
            # 动态覆盖 flight_date (明天的日期)
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            params["flight_date"] = tomorrow
            
            rpa_task_service.create_task(
                db=db,
                task_type=RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value,
                target_type=TARGET_TYPE,
                target_id=1,
                params=params,
                job_uuid=None,
                priority=2,
                created_by=None,
                robot_id=None,  # 允许任何有权限的机器人执行
            )
            print(f"[ShenzhenAirApprovalScheduler] 已生成深航订舱批复数据获取任务, flight_date={tomorrow}")
        finally:
            db.close()

# 全局单例
shenzhen_air_approval_scheduler = ShenzhenAirApprovalScheduler()
