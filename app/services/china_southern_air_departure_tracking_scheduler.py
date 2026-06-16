"""
南航出港跟踪数据（本站货物+货拉信息）定时获取调度器
1. 后台服务重启时立即运行一次
2. 定时轮询数据库中最新审批的单据进行状态跟踪
"""

import asyncio
import threading
import traceback
import re
from datetime import datetime, timedelta

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATaskType
from app.services.rpa_task_service import rpa_task_service
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData


TARGET_TYPE = "china_southern_departure_tracking"


class ChinaSouthernAirDepartureTrackingScheduler:
    """南航出港跟踪数据定时调度器"""
    
    def __init__(self):
        self._stop_event = asyncio.Event()
        self._thread = None
        self._loop = None
        
    def start(self):
        """启动调度器"""
        if self._thread is not None and self._thread.is_alive():
            print("[ChinaSouthernAirDepartureTrackingScheduler] 调度器已经在运行")
            return
            
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="CSADepartureTrackingScheduler")
        self._thread.start()
        print("[ChinaSouthernAirDepartureTrackingScheduler] 调度器启动成功")
        
    def stop(self):
        """停止调度器"""
        print("[ChinaSouthernAirDepartureTrackingScheduler] 正在停止调度器...")
        self._stop_event.set()
        
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._stop_event.set)
            
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
        print("[ChinaSouthernAirDepartureTrackingScheduler] 调度器已停止")
        
    def _run(self):
        """线程运行主函数"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._async_scheduler_main())
        except Exception as e:
            print(f"[ChinaSouthernAirDepartureTrackingScheduler] 调度器运行异常: {repr(e)}\n{traceback.format_exc()}")
        finally:
            self._loop.close()

    async def _async_scheduler_main(self) -> None:
        """主循环：定期扫描并下发任务"""
        while not self._stop_event.is_set():
            try:
                interval = getattr(settings, "RPA_CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING_INTERVAL_SECONDS", 900)
                if interval and interval > 0:
                    await self._scan_and_enqueue_tracking_tasks()
            except Exception as e:
                print(f"[ChinaSouthernAirDepartureTrackingScheduler] 调度异常: {repr(e)}\n{traceback.format_exc()}")

            # 睡眠并等待被中断
            remaining = interval if interval and interval > 0 else 60
            while remaining > 0 and not self._stop_event.is_set():
                step = min(5, remaining)
                await asyncio.sleep(step)
                remaining -= step

    async def _scan_and_enqueue_tracking_tasks(self) -> None:
        """扫描数据库并为需要跟踪的记录下发任务"""
        db = SessionLocal()
        try:
            # 只查询过去 3 天内创建的数据，避免全表扫描影响性能
            recent_date = datetime.now() - timedelta(days=3)
            records = db.query(ChinaSouthernAirApprovalData).filter(
                ChinaSouthernAirApprovalData.created_at >= recent_date,
                ChinaSouthernAirApprovalData.booking_no.isnot(None),
                ChinaSouthernAirApprovalData.booking_no != ""
            ).order_by(ChinaSouthernAirApprovalData.id.desc()).all()
            
            enqueued_count = 0
            
            for record in records:
                # 检查该记录是否已经在跟踪中 (PENDING或RUNNING状态)
                existing = rpa_task_service.get_pending_task_for_target(
                    db,
                    target_type=TARGET_TYPE,
                    target_id=record.id,
                    task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
                )
                if existing:
                    continue  # 跳过正在执行的
                    
                # 提取纯数字订舱号
                booking_no_raw = str(record.booking_no).strip()
                match = re.match(r'^(\d+)', booking_no_raw)
                if not match:
                    continue
                
                booking_number = match.group(1)
                
                params = {
                    "booking_number": booking_number
                }
                
                # 下发子任务
                rpa_task_service.create_task(
                    db=db,
                    task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
                    target_type=TARGET_TYPE,
                    target_id=record.id,
                    params=params,
                    job_uuid=None,  # 等待分配时从 extra_config 读取
                    priority=2,
                    created_by=None,
                    robot_id=None
                )
                enqueued_count += 1
                
            if enqueued_count > 0:
                print(f"[ChinaSouthernAirDepartureTrackingScheduler] 成功入队了 {enqueued_count} 个南航出港跟踪任务。")
                
        finally:
            db.close()


# 全局单例
china_southern_air_departure_tracking_scheduler = ChinaSouthernAirDepartureTrackingScheduler()
