import os
import time
import json
import asyncio
import threading
import traceback
import pandas as pd
from typing import Any, Dict, Optional

from app.config import settings
from app.database import SessionLocal
from app.models.config import BusinessConfig
from app.models.rpa_task import RPATaskType
from app.models.transit_loading import ShenzhenAirBookingExport
from app.services.rpa_task_service import rpa_task_service


TRANSIT_LOADING_TARGET_TYPE = "transit_loading"
BILLING_TIME_TARGET_TYPE = "booking_export"

def _get_business_config_dict(db_session) -> Dict[str, Any]:
    config = db_session.query(BusinessConfig).first()
    if not config or not config.config_data:
        return {}
    try:
        return json.loads(config.config_data)
    except Exception:
        return {}


class TransitLoadingManager:
    """
    深航过机装机数据获取管理器
    包含两部分功能：
    1. 定时调度深航过机装机数据获取任务 (RPA下载表格)
    2. 后台轮询监控下载目录，解析表格并入库，同时派发子任务
    """
    def __init__(self):
        self._scheduler_thread: Optional[threading.Thread] = None
        self._watcher_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.watch_dir = settings.RPA_GENERATED_FILES_DIR

    def start(self) -> None:
        if not os.path.exists(self.watch_dir):
            os.makedirs(self.watch_dir, exist_ok=True)
            
        self._stop_event.clear()
        
        # 启动调度器线程
        if not (self._scheduler_thread and self._scheduler_thread.is_alive()):
            self._scheduler_thread = threading.Thread(target=self._run_scheduler, daemon=True)
            self._scheduler_thread.start()
            
        # 启动文件监控线程
        if not (self._watcher_thread and self._watcher_thread.is_alive()):
            self._watcher_thread = threading.Thread(target=self._run_watcher, daemon=True)
            self._watcher_thread.start()
            
        print("[TransitLoadingManager] 已启动定时调度与文件监控服务")

    def stop(self) -> None:
        self._stop_event.set()
        print("[TransitLoadingManager] 正在停止...")

    def _run_scheduler(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_scheduler_main())
        finally:
            loop.close()

    def _run_watcher(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_watcher_main())
        finally:
            loop.close()

    async def _async_scheduler_main(self) -> None:
        """主循环：定期下发下载表格任务"""
        while not self._stop_event.is_set():
            try:
                interval = getattr(settings, "RPA_SHENZHEN_AIR_TRANSIT_LOADING_INTERVAL_SECONDS", 3600)
                if interval and interval > 0:
                    await self._scan_and_enqueue_transit_loading()
            except Exception as e:
                print(f"[TransitLoadingManager] 调度异常: {repr(e)}\n{traceback.format_exc()}")

            remaining = interval if interval and interval > 0 else 60
            while remaining > 0 and not self._stop_event.is_set():
                step = min(5, remaining)
                await asyncio.sleep(step)
                remaining -= step

    async def _scan_and_enqueue_transit_loading(self) -> None:
        """创建下载表格任务"""
        db = SessionLocal()
        try:
            # 检查是否已有 pending/running 任务
            existing = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=TRANSIT_LOADING_TARGET_TYPE,
                target_id=1,  # 全局单例
                task_type=RPATaskType.SHENZHEN_AIR_TRANSIT_LOADING.value,
            )
            if existing:
                return

            business_config = _get_business_config_dict(db)
            node = business_config.get("shenzhen_air", {}).get("booking", {}).get("shenzhen_air_login", {})
            system_account = node.get("system_account", "")
            if not system_account:
                # Fallback to default or just skip if critical
                system_account = "szxfdh002"

            params = {
                "system_url": "https://www.kinggo.com/main",
                "system_account": system_account
            }

            rpa_task_service.create_task(
                db=db,
                task_type=RPATaskType.SHENZHEN_AIR_TRANSIT_LOADING.value,
                target_type=TRANSIT_LOADING_TARGET_TYPE,
                target_id=1,
                params=params,
                job_uuid=None,  # 任务分配时会读取 task_processes
                priority=2,
                created_by=None,
                robot_id=None,  # 允许任何有权限的机器人执行
            )
            print("[TransitLoadingManager] 已生成深航过机装机数据获取(下载表格)定时任务")
        finally:
            db.close()

    async def _async_watcher_main(self) -> None:
        """主循环：轮询监控文件夹"""
        while not self._stop_event.is_set():
            try:
                self._check_for_new_files()
            except Exception as e:
                print(f"[TransitLoadingManager] 文件监控异常: {repr(e)}\n{traceback.format_exc()}")
            
            await asyncio.sleep(5)  # 每5秒检查一次

    def _check_for_new_files(self) -> None:
        if not os.path.exists(self.watch_dir):
            return
            
        for filename in os.listdir(self.watch_dir):
            if "AwbQueryExport" in filename and filename.endswith(".xlsx"):
                filepath = os.path.join(self.watch_dir, filename)
                
                # 简单防抖：确保文件不再被写入
                try:
                    os.rename(filepath, filepath)
                except OSError:
                    continue  # 文件仍在使用中
                
                print(f"[TransitLoadingManager] 发现新的数据文件: {filename}，开始解析入库...")
                self._process_file(filepath)

    def _process_file(self, filepath: str) -> None:
        db = SessionLocal()
        try:
            df = pd.read_excel(filepath)
            
            business_config = _get_business_config_dict(db)
            node = business_config.get("shenzhen_air", {}).get("booking", {}).get("shenzhen_air_login", {})
            system_account = node.get("system_account", "szxfdh002")

            # 遍历行
            for index, row in df.iterrows():
                # 读取全部31列（处理 NaN 为 None）
                row_dict = row.where(pd.notnull(row), None).to_dict()
                
                waybill_number = str(row_dict.get("单号", ""))
                if waybill_number.endswith('.0'):
                    waybill_number = waybill_number[:-2]
                
                if not waybill_number or waybill_number == 'None':
                    continue
                
                # 入库
                export_record = ShenzhenAirBookingExport(
                    prefix=str(row_dict.get("前缀", "")),
                    waybill_number=waybill_number,
                    waybill_status=str(row_dict.get("运单状态", "")),
                    creation_time=str(row_dict.get("制单时间", "")),
                    creator=str(row_dict.get("制单人", "")),
                    agent=str(row_dict.get("代理人", "")),
                    routing=str(row_dict.get("航程", "")),
                    flight_date=str(row_dict.get("航班日期", "")),
                    billing_flight=str(row_dict.get("开单航班", "")),
                    actual_flight=str(row_dict.get("走货航班", "")),
                    shipper=str(row_dict.get("发货人", "")),
                    consignee=str(row_dict.get("收货人", "")),
                    carrier=str(row_dict.get("承运人", "")),
                    storage_precautions=str(row_dict.get("储运事项", "")),
                    cargo_name=str(row_dict.get("品名", "")),
                    cabin=str(row_dict.get("舱位", "")),
                    quantity=str(row_dict.get("件数", "")),
                    weight=str(row_dict.get("重量", "")),
                    chargeable_weight=str(row_dict.get("计费重量", "")),
                    freight_rate=str(row_dict.get("费率", "")),
                    air_freight=str(row_dict.get("航空运费", "")),
                    fuel_surcharge=str(row_dict.get("燃油费", "")),
                    airport_management_fee=str(row_dict.get("机管费", "")),
                    total_amount=str(row_dict.get("总金额", "")),
                    price_code=str(row_dict.get("运价代码", "")),
                    handling_code=str(row_dict.get("处理代码", "")),
                    payment_method=str(row_dict.get("支付方式", "")),
                    waybill_type=str(row_dict.get("运单类型", "")),
                    quantity_difference=str(row_dict.get("运输件数差额", "")),
                    weight_difference=str(row_dict.get("运输重量差额", "")),
                    container=str(row_dict.get("集装器", ""))
                )
                db.add(export_record)
                db.flush()  # 获取 export_record.id
                
                # 下发子任务：计飞时间与集装器获取
                params = {
                    "system_url": "https://www.kinggo.com/main",
                    "system_account": system_account,
                    "waybill_number_8": waybill_number
                }
                
                rpa_task_service.create_task(
                    db=db,
                    task_type=RPATaskType.SHENZHEN_AIR_BILLING_TIME_CONTAINER.value,
                    target_type=BILLING_TIME_TARGET_TYPE,
                    target_id=export_record.id,
                    params=params,
                    job_uuid=None,
                    priority=2,
                    created_by=None,
                    robot_id=None
                )
                
            db.commit()
            print(f"[TransitLoadingManager] 文件 {os.path.basename(filepath)} 解析入库及子任务下发完成。")
            
            # 重命名防重处理
            os.rename(filepath, filepath + ".processed")
            
        except Exception as e:
            db.rollback()
            print(f"[TransitLoadingManager] 处理文件 {filepath} 失败: {repr(e)}\n{traceback.format_exc()}")
        finally:
            db.close()

# 全局单例
transit_loading_manager = TransitLoadingManager()
