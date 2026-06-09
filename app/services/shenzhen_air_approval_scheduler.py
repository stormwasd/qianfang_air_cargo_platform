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
            task_types_to_enqueue = [
                RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value,
                RPATaskType.SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY.value
            ]
            
            for task_type in task_types_to_enqueue:
                # 检查是否有未处理完的相同任务，避免重复下发
                existing = rpa_task_service.get_pending_task_for_target(
                    db,
                    target_type=TARGET_TYPE,
                    target_id=1,
                    task_type=task_type,
                )
                if existing:
                    continue

                # 查询数据库里的基础参数
                task_process = db.query(TaskProcess).filter(
                    TaskProcess.task_name == task_type
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
                    task_type=task_type,
                    target_type=TARGET_TYPE,
                    target_id=1,
                    params=params,
                    job_uuid=None,
                    priority=2,
                    created_by=None,
                    robot_id=None,  # 允许任何有权限的机器人执行
                )
                print(f"[ShenzhenAirApprovalScheduler] 已生成深航订舱批复数据获取任务({task_type}), flight_date={tomorrow}")
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
            current_parent_id = None
            
            def _get_val(r_dict, k):
                val = r_dict.get(k)
                if val is None or str(val).strip() == '' or str(val) == 'nan':
                    return None
                return str(val)
            
            for index, row in df.iterrows():
                row_dict = row.where(pd.notnull(row), None).to_dict()
                
                flight_number = _get_val(row_dict, "航班号")
                flight_date = _get_val(row_dict, "航班日期")
                
                if flight_number and "总计" in flight_number:
                    continue
                
                # 判断是否是父级（汇总）行：有航班号且有航班日期
                is_parent = bool(flight_number and flight_date)
                
                if is_parent:
                    pair_key = f"{flight_number}_{flight_date}"
                    
                    # 防重策略：如果遇到新的航班组合，先清空数据库中已有的父级和子级记录
                    if pair_key not in seen_flight_pairs:
                        existing_parents = db.query(ShenzhenAirApprovalData).filter(
                            ShenzhenAirApprovalData.flight_number == flight_number,
                            ShenzhenAirApprovalData.flight_date == flight_date,
                            ShenzhenAirApprovalData.parent_id == None
                        ).all()
                        
                        parent_ids = [p.id for p in existing_parents]
                        if parent_ids:
                            # 删子项
                            db.query(ShenzhenAirApprovalData).filter(
                                ShenzhenAirApprovalData.parent_id.in_(parent_ids)
                            ).delete(synchronize_session=False)
                            # 删父项
                            db.query(ShenzhenAirApprovalData).filter(
                                ShenzhenAirApprovalData.id.in_(parent_ids)
                            ).delete(synchronize_session=False)
                            
                        seen_flight_pairs.add(pair_key)
                    
                    export_record = ShenzhenAirApprovalData(
                        flight_number=flight_number,
                        flight_date=flight_date,
                        parent_id=None,
                        aircraft_type=_get_val(row_dict, "机型"),
                        departure_time=_get_val(row_dict, "起飞"),
                        routing=_get_val(row_dict, "航程"),
                        agent=_get_val(row_dict, "代理人"),
                        f_booking=_get_val(row_dict, "F订"),
                        f_approval=_get_val(row_dict, "F批"),
                        c_booking=_get_val(row_dict, "C订"),
                        c_approval=_get_val(row_dict, "C批"),
                        other_booking=_get_val(row_dict, "其他订"),
                        other_approval=_get_val(row_dict, "其他批"),
                        status=_get_val(row_dict, "状态"),
                        type=_get_val(row_dict, "类型"),
                        control=_get_val(row_dict, "控制"),
                        open_status=_get_val(row_dict, "开放"),
                        remark=_get_val(row_dict, "备注")
                    )
                    db.add(export_record)
                    db.flush() # 获取自增的主键ID
                    current_parent_id = export_record.id
                    
                else:
                    # 子项（细节）行：没有航班号
                    if current_parent_id is None:
                        continue # 孤儿行，忽略
                        
                    export_record = ShenzhenAirApprovalData(
                        flight_number=None,
                        flight_date=None,
                        parent_id=current_parent_id,
                        aircraft_type=None,
                        departure_time=None,
                        routing=_get_val(row_dict, "航程"),
                        agent=_get_val(row_dict, "代理人"),
                        f_booking=_get_val(row_dict, "F订"),
                        f_approval=_get_val(row_dict, "F批"),
                        c_booking=_get_val(row_dict, "C订"),
                        c_approval=_get_val(row_dict, "C批"),
                        other_booking=_get_val(row_dict, "其他订"),
                        other_approval=_get_val(row_dict, "其他批"),
                        status=_get_val(row_dict, "状态"),
                        type=_get_val(row_dict, "类型"),
                        control=_get_val(row_dict, "控制"),
                        open_status=_get_val(row_dict, "开放"),
                        remark=_get_val(row_dict, "备注")
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
