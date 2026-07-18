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
from app.models.shenzhen_air_approval import ShenzhenAirApprovalData, ShenzhenAirApprovalWideBodyData
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
        if not self._stop_event.is_set():
            try:
                await self._enqueue_task()
            except Exception as e:
                print(f"[ShenzhenAirApprovalScheduler] 启动时入队失败: {repr(e)}")

        while not self._stop_event.is_set():
            try:
                interval = getattr(settings, "RPA_SHENZHEN_AIR_APPROVAL_INTERVAL_SECONDS", 900)
                remaining = interval if interval and interval > 0 else 900
                
                while remaining > 0 and not self._stop_event.is_set():
                    step = min(5.0, remaining)
                    try:
                        self._check_for_new_files()
                    except Exception as ex:
                        print(f"[ShenzhenAirApprovalScheduler] 文件监控异常: {repr(ex)}\n{traceback.format_exc()}")
                    await asyncio.sleep(step)
                    remaining -= step
                
                if not self._stop_event.is_set():
                    await self._enqueue_task()

            except Exception as e:
                print(f"[ShenzhenAirApprovalScheduler] 调度循环异常: {repr(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(60)  

    async def _enqueue_task(self) -> None:
        """创建任务"""
        db = SessionLocal()
        try:
            task_types_to_enqueue = [
                RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value,
                RPATaskType.SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY.value
            ]
            
            for task_type in task_types_to_enqueue:
                existing = rpa_task_service.get_pending_task_for_target(
                    db,
                    target_type=TARGET_TYPE,
                    target_id=1,
                    task_type=task_type,
                )
                if existing:
                    continue

                task_process = db.query(TaskProcess).filter(
                    TaskProcess.task_name == task_type
                ).first()
                
                params = {}
                if task_process and task_process.process_param:
                    try:
                        params = json.loads(task_process.process_param)
                    except Exception:
                        pass
                
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
                    robot_id=None,  
                )
                print(f"[ShenzhenAirApprovalScheduler] 已生成深航订舱批复数据获取任务({task_type}), flight_date={tomorrow}")
        finally:
            db.close()

    def _check_for_new_files(self) -> None:
        if not os.path.exists(self.watch_dir):
            return
            
        for filename in os.listdir(self.watch_dir):
            if filename.endswith(".xlsx"):
                is_wide_body = "宽体机订舱查询与修改导出" in filename
                is_narrow_body = "订舱查询导出" in filename and not is_wide_body
                
                if not (is_wide_body or is_narrow_body):
                    continue

                filepath = os.path.join(self.watch_dir, filename)
                
                try:
                    os.rename(filepath, filepath)
                except OSError:
                    continue  
                
                print(f"[ShenzhenAirApprovalScheduler] 发现新的批复数据文件: {filename}，开始解析入库...")
                if is_wide_body:
                    self._process_wide_body_file(filepath)
                else:
                    self._process_file(filepath)

    def _process_file(self, filepath: str) -> None:
        db = SessionLocal()
        try:
            df = pd.read_excel(filepath)
            
            if "航班日期" in df.columns:
                unique_dates = df["航班日期"].dropna().unique().tolist()
                date_strs = [str(d).strip() for d in unique_dates if str(d).strip() and str(d) != 'nan']
                if date_strs:
                    parent_records = db.query(ShenzhenAirApprovalData.id).filter(
                        ShenzhenAirApprovalData.flight_date.in_(date_strs),
                        ShenzhenAirApprovalData.parent_id == None
                    ).all()
                    
                    parent_ids = [p[0] for p in parent_records]
                    if parent_ids:
                        db.query(ShenzhenAirApprovalData).filter(
                            ShenzhenAirApprovalData.parent_id.in_(parent_ids)
                        ).delete(synchronize_session=False)
                        db.query(ShenzhenAirApprovalData).filter(
                            ShenzhenAirApprovalData.id.in_(parent_ids)
                        ).delete(synchronize_session=False)
                        db.commit()
            
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
                
                is_parent = bool(flight_number and flight_date)
                
                if is_parent:
                    pair_key = f"{flight_number}_{flight_date}"
                    
                    if pair_key not in seen_flight_pairs:
                        existing_parents = db.query(ShenzhenAirApprovalData).filter(
                            ShenzhenAirApprovalData.flight_number == flight_number,
                            ShenzhenAirApprovalData.flight_date == flight_date,
                            ShenzhenAirApprovalData.parent_id == None
                        ).all()
                        
                        parent_ids = [p.id for p in existing_parents]
                        if parent_ids:
                            db.query(ShenzhenAirApprovalData).filter(
                                ShenzhenAirApprovalData.parent_id.in_(parent_ids)
                            ).delete(synchronize_session=False)
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
                    db.flush() 
                    current_parent_id = export_record.id
                    
                else:
                    if current_parent_id is None:
                        continue 
                        
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
            
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[ShenzhenAirApprovalScheduler] 处理文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

    def _process_wide_body_file(self, filepath: str) -> None:
        db = SessionLocal()
        try:
            df = pd.read_excel(filepath)
            
            if "航班日期" in df.columns:
                unique_dates = df["航班日期"].dropna().unique().tolist()
                date_strs = [str(d).strip() for d in unique_dates if str(d).strip() and str(d) != 'nan']
                if date_strs:
                    parent_records = db.query(ShenzhenAirApprovalWideBodyData.id).filter(
                        ShenzhenAirApprovalWideBodyData.flight_date.in_(date_strs),
                        ShenzhenAirApprovalWideBodyData.parent_id == None
                    ).all()
                    
                    parent_ids = [p[0] for p in parent_records]
                    if parent_ids:
                        db.query(ShenzhenAirApprovalWideBodyData).filter(
                            ShenzhenAirApprovalWideBodyData.parent_id.in_(parent_ids)
                        ).delete(synchronize_session=False)
                        db.query(ShenzhenAirApprovalWideBodyData).filter(
                            ShenzhenAirApprovalWideBodyData.id.in_(parent_ids)
                        ).delete(synchronize_session=False)
                        db.commit()
            
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
                
                is_parent = bool(flight_number and flight_date)
                
                if is_parent:
                    pair_key = f"{flight_number}_{flight_date}"
                    
                    if pair_key not in seen_flight_pairs:
                        existing_parents = db.query(ShenzhenAirApprovalWideBodyData).filter(
                            ShenzhenAirApprovalWideBodyData.flight_number == flight_number,
                            ShenzhenAirApprovalWideBodyData.flight_date == flight_date,
                            ShenzhenAirApprovalWideBodyData.parent_id == None
                        ).all()
                        
                        parent_ids = [p.id for p in existing_parents]
                        if parent_ids:
                            db.query(ShenzhenAirApprovalWideBodyData).filter(
                                ShenzhenAirApprovalWideBodyData.parent_id.in_(parent_ids)
                            ).delete(synchronize_session=False)
                            db.query(ShenzhenAirApprovalWideBodyData).filter(
                                ShenzhenAirApprovalWideBodyData.id.in_(parent_ids)
                            ).delete(synchronize_session=False)
                            
                        seen_flight_pairs.add(pair_key)
                    
                    export_record = ShenzhenAirApprovalWideBodyData(
                        flight_number=flight_number,
                        flight_date=flight_date,
                        parent_id=None,
                        aircraft_type=_get_val(row_dict, "机型"),
                        departure_time=_get_val(row_dict, "起飞"),
                        routing=_get_val(row_dict, "航程"),
                        agent=_get_val(row_dict, "代理人"),
                        board_booking=_get_val(row_dict, "板订"),
                        board_approval=_get_val(row_dict, "板批"),
                        backup_board=_get_val(row_dict, "备份板"),
                        box_booking=_get_val(row_dict, "箱订"),
                        box_approval=_get_val(row_dict, "箱批"),
                        backup_box=_get_val(row_dict, "备份箱"),
                        status=_get_val(row_dict, "状态"),
                        type=_get_val(row_dict, "类型"),
                        remark=_get_val(row_dict, "备注")
                    )
                    db.add(export_record)
                    db.flush() 
                    current_parent_id = export_record.id
                    
                else:
                    if current_parent_id is None:
                        continue 
                        
                    export_record = ShenzhenAirApprovalWideBodyData(
                        flight_number=None,
                        flight_date=None,
                        parent_id=current_parent_id,
                        aircraft_type=None,
                        departure_time=None,
                        routing=_get_val(row_dict, "航程"),
                        agent=_get_val(row_dict, "代理人"),
                        board_booking=_get_val(row_dict, "板订"),
                        board_approval=_get_val(row_dict, "板批"),
                        backup_board=_get_val(row_dict, "备份板"),
                        box_booking=_get_val(row_dict, "箱订"),
                        box_approval=_get_val(row_dict, "箱批"),
                        backup_box=_get_val(row_dict, "备份箱"),
                        status=_get_val(row_dict, "状态"),
                        type=_get_val(row_dict, "类型"),
                        remark=_get_val(row_dict, "备注")
                    )
                    db.add(export_record)
                
            db.commit()
            print(f"[ShenzhenAirApprovalScheduler] 宽体机文件 {os.path.basename(filepath)} 解析入库完成。")
            
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[ShenzhenAirApprovalScheduler] 处理宽体机文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

shenzhen_air_approval_scheduler = ShenzhenAirApprovalScheduler()
