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
import os
import pandas as pd

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATaskType
from app.models.robot import TaskProcess
from app.models.shenzhen_air_approval import ShenzhenAirApprovalData
from app.services.rpa_task_service import rpa_task_service


TARGET_TYPE = "approval_data"


class ShenzhenAirApprovalScheduler:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.watch_dir = settings.RPA_GENERATED_FILES_DIR

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
                    
                    # 在休眠间隙轮询文件
                    try:
                        self._check_for_new_files()
                    except Exception as ex:
                        print(f"[ShenzhenAirApprovalScheduler] 文件监控异常: {repr(ex)}\n{traceback.format_exc()}")
                        
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

    def _check_for_new_files(self) -> None:
        if not os.path.exists(self.watch_dir):
            return
            
        for filename in os.listdir(self.watch_dir):
            if "订舱查询导出" in filename and filename.endswith(".xlsx"):
                filepath = os.path.join(self.watch_dir, filename)
                
                # 简单防抖：确保文件不再被写入
                try:
                    os.rename(filepath, filepath)
                except OSError:
                    continue  # 文件仍在使用中
                
                print(f"[ShenzhenAirApprovalScheduler] 发现新的批复数据文件: {filename}，开始解析入库...")
                self._process_file(filepath)

    def _process_file(self, filepath: str) -> None:
        db = SessionLocal()
        try:
            df = pd.read_excel(filepath)
            
            seen_flight_pairs = set()
            
            for index, row in df.iterrows():
                row_dict = row.where(pd.notnull(row), None).to_dict()
                
                flight_number = str(row_dict.get("航班号", ""))
                flight_date = str(row_dict.get("航班日期", ""))
                
                if not flight_number or not flight_date or flight_number == 'None' or flight_date == 'None':
                    continue
                    
                pair_key = f"{flight_number}_{flight_date}"
                
                # 防重策略：相同航班号+航班日期，先删除旧数据再插入新数据
                if pair_key not in seen_flight_pairs:
                    db.query(ShenzhenAirApprovalData).filter(
                        ShenzhenAirApprovalData.flight_number == flight_number,
                        ShenzhenAirApprovalData.flight_date == flight_date
                    ).delete()
                    seen_flight_pairs.add(pair_key)
                    
                export_record = ShenzhenAirApprovalData(
                    flight_number=flight_number,
                    flight_date=flight_date,
                    aircraft_type=str(row_dict.get("机型", "")),
                    departure_time=str(row_dict.get("起飞", "")),
                    routing=str(row_dict.get("航程", "")),
                    agent=str(row_dict.get("代理人", "")),
                    f_booking=str(row_dict.get("F订", "")),
                    f_approval=str(row_dict.get("F批", "")),
                    c_booking=str(row_dict.get("C订", "")),
                    c_approval=str(row_dict.get("C批", "")),
                    other_booking=str(row_dict.get("其他订", "")),
                    other_approval=str(row_dict.get("其他批", "")),
                    status=str(row_dict.get("状态", "")),
                    type=str(row_dict.get("类型", "")),
                    control=str(row_dict.get("控制", "")),
                    open_status=str(row_dict.get("开放", "")),
                    remark=str(row_dict.get("备注", ""))
                )
                db.add(export_record)
                
            db.commit()
            print(f"[ShenzhenAirApprovalScheduler] 文件 {os.path.basename(filepath)} 解析入库完成。")
            
            # 重命名防重处理，防止被再次处理
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[ShenzhenAirApprovalScheduler] 处理文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

# 全局单例
shenzhen_air_approval_scheduler = ShenzhenAirApprovalScheduler()
