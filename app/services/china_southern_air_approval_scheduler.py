"""南航订舱批复下载、文件解析及出港跟踪子任务调度器。"""

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
from app.utils.helpers import get_china_now
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
import pandas as pd
import math
import re
from sqlalchemy import and_, exists, func, or_


TARGET_TYPE = "approval_data"
DEPARTURE_TRACKING_TARGET_TYPE = "csa_dep_tracking"


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

    @staticmethod
    def _planned_datetime(value: str, flight_date: str):
        """兼容 Excel 中的日期时间、HHMM、HH:MM 等计划起飞格式。"""
        text = str(value or "").strip()
        if not text or text.lower() in {"none", "nan"}:
            return None
        candidates = [text, f"{flight_date} {text}"]
        for candidate in candidates:
            try:
                return datetime.fromisoformat(candidate.replace("/", "-").replace("Z", "+00:00"))
            except ValueError:
                pass
        digits = re.sub(r"[^0-9]", "", text)
        if len(digits) in (3, 4):
            digits = digits.zfill(4)
            try:
                return datetime.strptime(f"{flight_date} {digits[:2]}:{digits[2:]}", "%Y-%m-%d %H:%M")
            except ValueError:
                return None
        return None

    async def _enqueue_departure_tracking_task(
        self,
        db,
        approval_record: ChinaSouthernAirApprovalData,
    ) -> bool:
        """按计划/计飞时间为一条南航批复记录创建唯一出港跟踪任务。"""
        if str(approval_record.departure_tracking_completed or "0") == "1":
            return False

        booking_text = str(approval_record.booking_no or "").strip()
        booking_match = re.match(r"^(\d+)", booking_text)
        flight_parts = [
            part.strip()
            for part in str(approval_record.flight_info or "").split("/")
        ]
        if not booking_match or len(flight_parts) < 3:
            return False

        flight_no = flight_parts[0]
        flight_date_match = re.search(
            r"(\d{4}-\d{2}-\d{2})", str(approval_record.flight_info or "")
        )
        if not flight_no or not flight_date_match:
            return False
        flight_date = flight_date_match.group(1)
        if flight_date < get_china_now().strftime("%Y-%m-%d"):
            return False

        existing_task = rpa_task_service.get_existing_task_for_target(
            db,
            target_type=DEPARTURE_TRACKING_TARGET_TYPE,
            target_id=approval_record.id,
            task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
        )
        if existing_task:
            return False

        planned_dt = self._planned_datetime(
            approval_record.planned_takeoff, flight_date
        )
        if not planned_dt:
            from app.utils.ctrip_client import ctrip_client

            routing = flight_parts[-1]
            try:
                ctrip_times = await ctrip_client.get_flight_times(
                    flight_no, flight_date, routing
                )
            except Exception as exc:
                print(
                    "[ChinaSouthernAirApprovalScheduler] 携程计飞时间查询异常，"
                    "本轮暂不创建子任务: "
                    f"approval_id={approval_record.id}, error={exc}"
                )
                return False
            planned_dt = self._planned_datetime(
                (ctrip_times or {}).get("ready_time"), flight_date
            )
        if not planned_dt:
            print(
                "[ChinaSouthernAirApprovalScheduler] 未取得有效计飞时间，"
                "本轮暂不创建子任务: "
                f"booking={booking_match.group(1)}, "
                f"flight_info={approval_record.flight_info}"
            )
            return False

        scheduled_at = planned_dt - timedelta(minutes=105)
        if scheduled_at.tzinfo:
            scheduled_at = scheduled_at.replace(tzinfo=None)
        task = rpa_task_service.create_task(
            db=db,
            task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
            target_type=DEPARTURE_TRACKING_TARGET_TYPE,
            target_id=approval_record.id,
            params={"booking_number": booking_match.group(1)},
            job_uuid=None,
            priority=2,
            created_by=None,
            robot_id=None,
            scheduled_at=scheduled_at,
            max_attempts=settings.RPA_DEPARTURE_TASK_MAX_ATTEMPTS,
        )
        print(
            "[ChinaSouthernAirApprovalScheduler] 已创建南航出港跟踪子任务: "
            f"task_id={task.id}, approval_id={approval_record.id}, "
            f"scheduled_at={scheduled_at}"
        )
        return True

    async def _enqueue_missing_departure_tracking_tasks(self) -> None:
        """补建旧版本漏派发、或此前未取得计飞时间的南航子任务。"""
        from app.models.rpa_task import RPATask

        db = SessionLocal()
        try:
            today = get_china_now().strftime("%Y-%m-%d")
            # 订舱航班格式固定为“航班 / 日期 / 航程”。生产库为 MySQL，
            # 在 SQL 层剔除已过期航班，避免历史 0 标记记录反复占用回扫资源。
            flight_date_expr = func.trim(func.substring_index(
                func.substring_index(
                    ChinaSouthernAirApprovalData.flight_info, "/", 2
                ),
                "/",
                -1,
            ))
            missing_task = ~exists().where(and_(
                RPATask.target_type == DEPARTURE_TRACKING_TARGET_TYPE,
                RPATask.target_id == ChinaSouthernAirApprovalData.id,
                RPATask.task_type
                == RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
            ))
            last_id = None
            while True:
                query = db.query(ChinaSouthernAirApprovalData).filter(
                    or_(
                        ChinaSouthernAirApprovalData.departure_tracking_completed.is_(None),
                        ChinaSouthernAirApprovalData.departure_tracking_completed != "1",
                    ),
                    ChinaSouthernAirApprovalData.booking_no.isnot(None),
                    ChinaSouthernAirApprovalData.flight_info.isnot(None),
                    flight_date_expr >= today,
                    missing_task,
                )
                if last_id is not None:
                    query = query.filter(ChinaSouthernAirApprovalData.id < last_id)
                records = query.order_by(
                    ChinaSouthernAirApprovalData.id.desc()
                ).limit(200).all()
                if not records:
                    break
                for record in records:
                    record_id = record.id
                    try:
                        await self._enqueue_departure_tracking_task(db, record)
                    except Exception as exc:
                        db.rollback()
                        print(
                            "[ChinaSouthernAirApprovalScheduler] "
                            "补建南航出港跟踪任务失败: "
                            f"approval_id={record_id}, error={exc}"
                        )
                last_id = records[-1].id
        finally:
            db.close()

    async def _async_main(self) -> None:
        """主循环"""
        if not self._stop_event.is_set():
            try:
                await self._enqueue_task()
            except Exception as e:
                print(f"[ChinaSouthernAirApprovalScheduler] 启动时入队失败: {repr(e)}")
            try:
                await self._enqueue_missing_departure_tracking_tasks()
            except Exception as e:
                print(f"[ChinaSouthernAirApprovalScheduler] 启动时补建子任务失败: {repr(e)}")

        loop = asyncio.get_running_loop()
        approval_interval = max(
            1,
            settings.RPA_CHINA_SOUTHERN_AIR_APPROVAL_INTERVAL_SECONDS,
        )
        departure_interval = max(
            1,
            settings.RPA_CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING_INTERVAL_SECONDS,
        )
        next_approval_at = loop.time() + approval_interval
        next_departure_at = loop.time() + departure_interval

        while not self._stop_event.is_set():
            try:
                await self._check_for_new_files()
            except Exception as exc:
                print(
                    "[ChinaSouthernAirApprovalScheduler] 检查新文件异常: "
                    f"{repr(exc)}\n{traceback.format_exc()}"
                )

            current = loop.time()
            if current >= next_approval_at:
                try:
                    await self._enqueue_task()
                except Exception as exc:
                    print(
                        "[ChinaSouthernAirApprovalScheduler] 批复任务入队异常: "
                        f"{repr(exc)}"
                    )
                finally:
                    next_approval_at = loop.time() + approval_interval

            if current >= next_departure_at:
                try:
                    await self._enqueue_missing_departure_tracking_tasks()
                except Exception as exc:
                    print(
                        "[ChinaSouthernAirApprovalScheduler] 子任务补偿异常: "
                        f"{repr(exc)}"
                    )
                finally:
                    next_departure_at = loop.time() + departure_interval

            remaining = min(next_approval_at, next_departure_at) - loop.time()
            await asyncio.sleep(max(0.1, min(5.0, remaining)))

    async def _enqueue_task(self) -> None:
        """创建任务"""
        db = SessionLocal()
        try:
            task_type = RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA.value
            
            existing = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=TARGET_TYPE,
                target_id=1,
                task_type=task_type,
            )
            if existing:
                return

            task_process = db.query(TaskProcess).filter(
                TaskProcess.task_name == task_type
            ).first()
            
            params = {}
            if task_process and task_process.process_param:
                try:
                    params = json.loads(task_process.process_param)
                except Exception:
                    pass
            
            tomorrow = (get_china_now() + timedelta(days=1)).strftime("%Y-%m-%d")
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
            print(f"[ChinaSouthernAirApprovalScheduler] 已生成南航订舱批复数据获取任务({task_type})")
        finally:
            db.close()

    async def _check_for_new_files(self) -> None:
        if not os.path.exists(self.watch_dir):
            return
            
        for filename in os.listdir(self.watch_dir):
            if filename.endswith(".xlsx") and "订舱查询与处理" in filename:
                filepath = os.path.join(self.watch_dir, filename)
                
                try:
                    os.rename(filepath, filepath)
                except OSError:
                    continue  
                
                print(f"[ChinaSouthernAirApprovalScheduler] 发现新的批复数据文件: {filename}，开始解析入库...")
                await self._process_file(filepath)

    async def _process_file(self, filepath: str) -> None:
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

            unique_dates = set()
            for idx, r in df.iterrows():
                if idx < 3:
                    continue
                r_dict = r.to_dict()
                try:
                    f_info = str(r_dict.get(list(r_dict.keys())[0]))
                    if f_info and f_info.strip() and f_info != 'nan':
                        parts = f_info.split('/')
                        if len(parts) >= 2:
                            f_date = parts[1].strip()
                            if f_date:
                                unique_dates.add(f_date)
                except Exception:
                    pass
            
            existing_ids = set()
            if unique_dates:
                conditions = [ChinaSouthernAirApprovalData.flight_info.like(f"%{date_str}%") for date_str in unique_dates]
                
                existing_records = db.query(ChinaSouthernAirApprovalData.id).filter(or_(*conditions)).all()
                existing_ids = {r[0] for r in existing_records}
            
            processed_ids = set()
            
            for index, row in df.iterrows():
                if index < 3:
                    continue
                    
                row_dict = row.to_dict()
                aircraft_type = _get_val(row_dict, 1)
                
                if aircraft_type == "小计":
                    continue
                    
                flight_info = _get_val(row_dict, 0)
                waybill_number = _get_val(row_dict, 7)
                
                if flight_info and "总计" in flight_info:
                    continue
                    
                if not flight_info and not waybill_number:
                    continue
                
                booking_no_raw = _get_val(row_dict, 12)
                existing_record = None
                if booking_no_raw:
                    match = re.match(r'^(\d+)', str(booking_no_raw).strip())
                    if match:
                        booking_number = match.group(1)
                        existing_record = db.query(ChinaSouthernAirApprovalData).filter(
                            ChinaSouthernAirApprovalData.booking_no.like(f"{booking_number}%")
                        ).first()
                    else:
                        existing_record = db.query(ChinaSouthernAirApprovalData).filter(
                            ChinaSouthernAirApprovalData.booking_no == booking_no_raw
                        ).first()
                
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
                    for k, v in field_values.items():
                        if k == "container" and getattr(existing_record, k):
                            continue
                        setattr(existing_record, k, v)
                    export_record = existing_record
                else:
                    export_record = ChinaSouthernAirApprovalData(**field_values)
                    db.add(export_record)
                
                db.flush()
                processed_ids.add(export_record.id)
                
                if booking_no_raw and flight_info:
                    await self._enqueue_departure_tracking_task(db, export_record)
            
            if unique_dates and existing_ids:
                zombie_ids = existing_ids - processed_ids
                if zombie_ids:
                    db.query(ChinaSouthernAirApprovalData).filter(
                        ChinaSouthernAirApprovalData.id.in_(zombie_ids),
                        or_(
                            ChinaSouthernAirApprovalData.container == None,
                            ChinaSouthernAirApprovalData.container == "",
                            ChinaSouthernAirApprovalData.container == "nan"
                        )
                    ).delete(synchronize_session=False)
            
            db.commit()
            print(f"[ChinaSouthernAirApprovalScheduler] 文件 {os.path.basename(filepath)} 解析入库完成。")
            
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[ChinaSouthernAirApprovalScheduler] 处理文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

china_southern_air_approval_scheduler = ChinaSouthernAirApprovalScheduler()
