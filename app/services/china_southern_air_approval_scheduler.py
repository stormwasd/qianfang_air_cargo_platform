"""
南航订舱批复数据获取调度器
1. 后台服务重启时立即运行一次
2. 每天定时运行 (默认18:00)
"""

import json
import asyncio
import threading
import traceback
from datetime import datetime, timedelta
from typing import Optional
import os

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATaskType
from app.models.robot import TaskProcess
from app.services.rpa_task_service import rpa_task_service
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
import pandas as pd
import math
import re


TARGET_TYPE = "approval_data"


class ChinaSouthernAirApprovalScheduler:
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
        print("[ChinaSouthernAirApprovalScheduler] 已启动南航订舱批复数据获取调度器")

    def stop(self) -> None:
        self._stop_event.set()
        print("[ChinaSouthernAirApprovalScheduler] 已停止南航订舱批复数据获取调度器")

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
                print(f"[ChinaSouthernAirApprovalScheduler] 启动时入队失败: {repr(e)}")

        # 2. 定期执行
        while not self._stop_event.is_set():
            try:
                interval = getattr(settings, "RPA_CHINA_SOUTHERN_AIR_APPROVAL_INTERVAL_SECONDS", 900)
                remaining = interval if interval and interval > 0 else 900
                
                # 分段 sleep，以支持及时 stop 并在休眠间隙轮询文件
                while remaining > 0 and not self._stop_event.is_set():
                    step = min(5.0, remaining)
                    try:
                        self._check_for_new_files()
                    except Exception as e:
                        print(f"[ChinaSouthernAirApprovalScheduler] 检查新文件异常: {repr(e)}\n{traceback.format_exc()}")
                    await asyncio.sleep(step)
                    remaining -= step
                
                if not self._stop_event.is_set():
                    await self._enqueue_task()

            except Exception as e:
                print(f"[ChinaSouthernAirApprovalScheduler] 调度循环异常: {repr(e)}\n{traceback.format_exc()}")
                await asyncio.sleep(60)  # 异常后等待一分钟重试

    async def _enqueue_task(self) -> None:
        """创建任务"""
        db = SessionLocal()
        try:
            task_type = RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA.value
            
            # 检查是否有未处理完的相同任务，避免重复下发
            existing = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=TARGET_TYPE,
                target_id=1,
                task_type=task_type,
            )
            if existing:
                return

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
            print(f"[ChinaSouthernAirApprovalScheduler] 已生成南航订舱批复数据获取任务({task_type})")
        finally:
            db.close()

    def _check_for_new_files(self) -> None:
        if not os.path.exists(self.watch_dir):
            return
            
        for filename in os.listdir(self.watch_dir):
            if filename.endswith(".xlsx") and "订舱查询与处理" in filename:
                filepath = os.path.join(self.watch_dir, filename)
                
                # 简单防抖：确保文件不再被写入
                try:
                    os.rename(filepath, filepath)
                except OSError:
                    continue  # 文件仍在使用中
                
                print(f"[ChinaSouthernAirApprovalScheduler] 发现新的批复数据文件: {filename}，开始解析入库...")
                self._process_file(filepath)

    def _process_file(self, filepath: str) -> None:
        db = SessionLocal()
        try:
            df = pd.read_excel(filepath)
            
            def _get_val(r_dict, index):
                try:
                    val = r_dict.get(list(r_dict.keys())[index])
                    if val is None or str(val).strip() == '' or str(val) == 'nan' or (isinstance(val, float) and math.isnan(val)):
                        return None
                    return str(val)
                except Exception:
                    return None
            
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # 从第4行（索引为3）开始是真正的表头和数据
            # 索引对应：0->订舱航班, 1->机型, 2->飞机号 ... 49->计费重量
            for index, row in df.iterrows():
                # 跳过表头和无用行
                if index < 3:
                    continue
                    
                row_dict = row.to_dict()
                aircraft_type = _get_val(row_dict, 1)
                
                # 过滤掉"小计"行，只存明细
                if aircraft_type == "小计":
                    continue
                    
                # 确保有基本的航班或单号数据，避免空行
                flight_info = _get_val(row_dict, 0)
                waybill_number = _get_val(row_dict, 7)
                
                # 过滤掉"总计"行
                if flight_info and "总计" in flight_info:
                    continue
                    
                if not flight_info and not waybill_number:
                    continue
                
                # === booking_no 去重（UPSERT）===
                booking_no_raw = _get_val(row_dict, 12)
                existing_record = None
                if booking_no_raw:
                    existing_record = db.query(ChinaSouthernAirApprovalData).filter(
                        ChinaSouthernAirApprovalData.booking_no == booking_no_raw
                    ).first()
                
                # 构造字段映射
                field_values = dict(
                    flight_info=flight_info,
                    aircraft_type=aircraft_type,
                    aircraft_no=_get_val(row_dict, 2),
                    aircraft_limit=_get_val(row_dict, 3),
                    planned_takeoff=_get_val(row_dict, 4),
                    expected_takeoff=_get_val(row_dict, 5),
                    flight_status=_get_val(row_dict, 6),
                    waybill_number=waybill_number,
                    agent_code=_get_val(row_dict, 8),
                    key_account_code=_get_val(row_dict, 9),
                    key_account_name=_get_val(row_dict, 10),
                    sales_channel=_get_val(row_dict, 11),
                    booking_no=booking_no_raw,
                    guarantee_level=_get_val(row_dict, 13),
                    cabin_level=_get_val(row_dict, 14),
                    product_code=_get_val(row_dict, 15),
                    booking_pieces=_get_val(row_dict, 16),
                    booking_weight=_get_val(row_dict, 17),
                    booking_volume=_get_val(row_dict, 18),
                    goods_name=_get_val(row_dict, 19),
                    commercial_danger_class=_get_val(row_dict, 20),
                    self_use_material_class=_get_val(row_dict, 21),
                    aviation_oil_sample_class=_get_val(row_dict, 22),
                    booking_uld=_get_val(row_dict, 23),
                    booking_remark=_get_val(row_dict, 24),
                    ad_remark=_get_val(row_dict, 25),
                    load_guidance=_get_val(row_dict, 26),
                    booking_routing=_get_val(row_dict, 27),
                    special_cargo_code=_get_val(row_dict, 28),
                    billing_qty=_get_val(row_dict, 29),
                    goods_qty=_get_val(row_dict, 30),
                    actual_qty=_get_val(row_dict, 31),
                    actual_flight=_get_val(row_dict, 32),
                    container=_get_val(row_dict, 33),
                    cargo_code=_get_val(row_dict, 34),
                    routing_country=_get_val(row_dict, 35),
                    department=_get_val(row_dict, 36),
                    booking_time=_get_val(row_dict, 37),
                    ref_rate=_get_val(row_dict, 38),
                    ref_freight=_get_val(row_dict, 39),
                    currency=_get_val(row_dict, 40),
                    other_fee=_get_val(row_dict, 41),
                    total_control=_get_val(row_dict, 42),
                    auto_approval=_get_val(row_dict, 43),
                    level_auto_k=_get_val(row_dict, 44),
                    size=_get_val(row_dict, 45),
                    settlement_discount_no=_get_val(row_dict, 46),
                    customs_clearance_status=_get_val(row_dict, 47),
                    single_window_check=_get_val(row_dict, 48),
                    chargeable_weight=_get_val(row_dict, 49)
                )
                
                if existing_record:
                    # 已存在：更新所有字段
                    for k, v in field_values.items():
                        setattr(existing_record, k, v)
                    export_record = existing_record
                else:
                    # 不存在：新增
                    export_record = ChinaSouthernAirApprovalData(**field_values)
                    db.add(export_record)
                
                db.flush()
                
                # === 下发出港跟踪任务（仅当天航班 + 去重）===
                if booking_no_raw and flight_info:
                    # 提取航班日期，格式如：CZ8577 / 2026-06-16 / SZX - WUH
                    flight_date_match = re.search(r'(\d{4}-\d{2}-\d{2})', str(flight_info))
                    flight_date = flight_date_match.group(1) if flight_date_match else None
                    
                    # 仅当航班日期是当天时才下发出港跟踪任务
                    if flight_date == today_str:
                        # 提取左括号前的纯数字订舱号
                        match = re.match(r'^(\d+)', str(booking_no_raw).strip())
                        if match:
                            booking_number = match.group(1)
                            
                            # 检查是否已有 pending/running 的出港跟踪任务（基于同一 approval_data_id）
                            existing_task = rpa_task_service.get_pending_task_for_target(
                                db,
                                target_type="csa_dep_tracking",
                                target_id=export_record.id,
                                task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value
                            )
                            if not existing_task:
                                params = {
                                    "booking_number": booking_number
                                }
                                rpa_task_service.create_task(
                                    db=db,
                                    task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
                                    target_type="csa_dep_tracking",
                                    target_id=export_record.id,
                                    params=params,
                                    job_uuid=None,
                                    priority=2,
                                    created_by=None,
                                    robot_id=None
                                )
            
            db.commit()
            print(f"[ChinaSouthernAirApprovalScheduler] 文件 {os.path.basename(filepath)} 解析入库完成。")
            
            # 重命名防重处理，防止被再次处理
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[ChinaSouthernAirApprovalScheduler] 处理文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

china_southern_air_approval_scheduler = ChinaSouthernAirApprovalScheduler()
