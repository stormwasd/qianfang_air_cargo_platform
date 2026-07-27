import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
import traceback
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.config import settings
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.customer import Customer
from app.models.shenzhen_air_departure_alert_task import ShenzhenAirDepartureAlertTask
from app.utils.ctrip_client import ctrip_client


class ShenzhenAirDepartureAlertManager:
    """深航出港跟踪预警服务"""

    def __init__(self):
        self._sync_task = None
        self._exec_task = None
        self._running = False

    def start(self):
        """启动后台调度器"""
        if self._running:
            return
        self._running = True
        self._sync_task = asyncio.create_task(self._sync_loop())
        self._exec_task = asyncio.create_task(self._exec_loop())
        print("[ShenzhenAirDepartureAlertManager] 已启动深航过机状态与卡号预警服务")

    def stop(self):
        """停止后台调度器"""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        if self._exec_task:
            self._exec_task.cancel()
        print("深航出港跟踪预警服务已停止")

    async def _sync_loop(self):
        """同步任务：每 N 分钟扫描新运单并加入待办队列表"""
        interval = getattr(settings, "ALERT_SHENZHEN_AIR_DEPARTURE_SYNC_INTERVAL_SECONDS", 300)
        while self._running:
            try:
                await self._sync_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"出港跟踪同步任务异常: {e}")
                traceback.print_exc()
            finally:
                await asyncio.sleep(interval)

    async def _exec_loop(self):
        """执行任务：每 1 分钟扫描到点的任务并执行"""
        interval = getattr(settings, "ALERT_SHENZHEN_AIR_DEPARTURE_EXEC_INTERVAL_SECONDS", 60)
        while self._running:
            try:
                await self._exec_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"出港跟踪执行任务异常: {e}")
                traceback.print_exc()
            finally:
                await asyncio.sleep(interval)


    async def _sync_tasks(self):
        """扫描当天 booking_exports 表，更新队列表"""
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            exports = db.query(ShenzhenAirBookingExport).filter(
                ShenzhenAirBookingExport.flight_date == today_str
            ).all()

            added_export_ids = set()

            for export in exports:
                if not export.id or not export.waybill_number:
                    continue
                
                if export.id in added_export_ids:
                    continue

                raw_waybill = str(export.waybill_number or "").strip()
                clean_waybill = raw_waybill.replace("479-", "")
                full_waybill = f"479-{clean_waybill}"
                waybill_candidates = list(set([raw_waybill, clean_waybill, full_waybill]))

                existing_task = db.query(ShenzhenAirDepartureAlertTask).filter(
                    (ShenzhenAirDepartureAlertTask.booking_export_id == export.id) |
                    (
                        (ShenzhenAirDepartureAlertTask.waybill_number.in_(waybill_candidates)) &
                        (ShenzhenAirDepartureAlertTask.flight_date == today_str)
                    )
                ).first()

                if existing_task:
                    continue  

                containers = db.query(ShenzhenAirBillingTimeContainer).filter(
                    ShenzhenAirBillingTimeContainer.booking_export_id == export.id
                ).all()

                billing_time_str = None
                if containers:
                    for c in containers:
                        if c.billing_time and str(c.billing_time).strip():
                            billing_time_str = str(c.billing_time).strip()
                            break
                
                planned_dt = None
                if billing_time_str:
                    bt_clean = billing_time_str.replace(":", "")
                    if len(bt_clean) >= 4:
                        try:
                            hour = int(bt_clean[:2])
                            minute = int(bt_clean[2:4])
                            planned_dt = datetime.strptime(today_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
                        except ValueError:
                            pass
                
                if not planned_dt:
                    flight_no_to_query = export.billing_flight
                    if flight_no_to_query and export.routing:
                        ctrip_times = await ctrip_client.get_flight_times(
                            flight_no=flight_no_to_query,
                            flight_date=today_str,
                            routing=export.routing
                        )
                        if ctrip_times and ctrip_times.get("planned_time"):
                            try:
                                planned_time_str = ctrip_times.get("planned_time")
                                if len(planned_time_str) > 16:
                                    planned_dt = datetime.strptime(planned_time_str, "%Y-%m-%d %H:%M:%S")
                                else:
                                    planned_dt = datetime.strptime(planned_time_str, "%Y-%m-%d %H:%M")
                            except ValueError:
                                pass
                
                if not planned_dt:
                    continue

                trigger_dt = planned_dt - timedelta(minutes=135)
                new_task = ShenzhenAirDepartureAlertTask(
                    booking_export_id=export.id,
                    waybill_number=full_waybill,
                    flight_date=today_str,
                    planned_time=planned_dt.strftime("%Y-%m-%d %H:%M"),
                    trigger_time=trigger_dt,
                    status="pending"
                )
                db.add(new_task)
                added_export_ids.add(export.id)
            
            db.commit()

        finally:
            db.close()


    async def _exec_tasks(self):
        """拉取到点的 pending 任务，执行预警逻辑"""
        db = SessionLocal()
        try:
            now = datetime.now()
            tasks = db.query(ShenzhenAirDepartureAlertTask).filter(
                ShenzhenAirDepartureAlertTask.status == "pending",
                ShenzhenAirDepartureAlertTask.trigger_time <= now
            ).with_for_update(skip_locked=True).all()

            if not tasks:
                return

            for t in tasks:
                t.status = "processing"
            db.commit()

            sem = asyncio.Semaphore(5)
            
            async def _bounded_process(task_id: int):
                async with sem:
                    await self._process_single_task(task_id)

            coros = [_bounded_process(t.id) for t in tasks]
            await asyncio.gather(*coros)

        finally:
            db.close()

    async def _process_single_task(self, task_id: int):
        db = SessionLocal()
        try:
            task = db.query(ShenzhenAirDepartureAlertTask).filter(ShenzhenAirDepartureAlertTask.id == task_id).first()
            if not task:
                return

            export_record = None
            if task.booking_export_id:
                export_record = db.query(ShenzhenAirBookingExport).filter(
                    ShenzhenAirBookingExport.id == task.booking_export_id
                ).first()

            if not export_record:
                waybill_num = task.waybill_number
                flight_date = task.flight_date
                clean_waybill = waybill_num.replace("479-", "") if waybill_num.startswith("479-") else waybill_num
                full_waybill = f"479-{clean_waybill}"
                waybill_candidates = list(set([waybill_num, clean_waybill, full_waybill]))

                export_record = db.query(ShenzhenAirBookingExport).filter(
                    ShenzhenAirBookingExport.waybill_number.in_(waybill_candidates),
                    ShenzhenAirBookingExport.flight_date == flight_date
                ).order_by(ShenzhenAirBookingExport.id.desc()).first()

            if not export_record:
                task.status = "ignored"
                db.commit()
                return

            containers = db.query(ShenzhenAirBillingTimeContainer).filter(
                ShenzhenAirBillingTimeContainer.booking_export_id == export_record.id
            ).all()

            await self._evaluate_and_send_alert(db, task, export_record, containers)

            task.status = "processed"
            db.commit()
        except Exception as e:
            print(f"处理出港跟踪预警单({task_id})异常: {e}")
            task.status = "pending" 
            db.commit()
        finally:
            db.close()

    async def _evaluate_and_send_alert(self, db: Session, task: ShenzhenAirDepartureAlertTask, export_record: ShenzhenAirBookingExport, containers: List[ShenzhenAirBillingTimeContainer]):
        """核心业务逻辑：分析数据，判断场景，发送模板"""
        
        customer_name = ""
        manual_data = db.query(ShenzhenAirDepartureManualData).filter(
            ShenzhenAirDepartureManualData.booking_export_id == export_record.id
        ).first()
        if manual_data and manual_data.customer_name:
            c_id_str = str(manual_data.customer_name).strip()
            if c_id_str.isdigit():
                cust = db.query(Customer).filter(Customer.id == int(c_id_str)).first()
                if cust and cust.company_name:
                    customer_name = cust.company_name

        full_waybill = f"479-{export_record.waybill_number}" if not str(export_record.waybill_number or "").startswith("479-") else export_record.waybill_number
        
        def _safe_float(val):
            if val is None or str(val).strip() == "": return 0.0
            try: return float(str(val).strip())
            except ValueError: return 0.0

        export_qty = _safe_float(export_record.quantity)
        export_wt = _safe_float(export_record.weight)

        valid_containers = []
        for c in containers:
            if c.container and str(c.container).strip():
                valid_containers.append(c)

        sum_qty = 0.0
        sum_wt = 0.0
        container_details = []
        for c in valid_containers:
            c_qty = _safe_float(c.quantity)
            c_wt = _safe_float(c.weight)
            sum_qty += c_qty
            sum_wt += c_wt
            container_code = c.container or "/"
            container_details.append(f"{container_code} ({int(c_qty)} / {int(c_wt)})")

        if not valid_containers:
            alert_title = "过机时间超时预警"
            machine_data_str = "/"
            containers_str = "/"
        else:
            diff_qty = int(export_qty - sum_qty)
            diff_wt = int(export_wt - sum_wt)
            machine_data_str = f"{int(sum_qty)} / {int(sum_wt)} ({diff_qty} / {diff_wt})"
            containers_str = "\n".join(container_details)

            if sum_qty >= export_qty and sum_wt >= export_wt:
                alert_title = "过机正常"
            else:
                alert_title = "少货/取消货预警"

        routing = export_record.routing or "未知航程"
        billing_flight = export_record.billing_flight or "未知航班"
        planned_time = task.planned_time

        message = (
            f"过机状态通知（深圳航空）\n"
            f"{alert_title}\n\n"
            f"客户名称：{customer_name}\n"
            f"运单号：{full_waybill}\n"
            f"开单航班/航程：{billing_flight} / {routing}\n"
            f"计飞时间：{planned_time}\n"
            f"制单数据：{int(export_qty)} / {int(export_wt)}\n"
            f"过机数据：{machine_data_str}\n"
            f"集装器：\n"
            f"{containers_str}"
        )

        await self._send_wechat_msg(message)

    async def _send_wechat_msg(self, text: str):
        url = settings.WECHAT_WEBHOOK_URL
        if not url:
            print("WECHAT_WEBHOOK_URL 未配置")
            return
        
        payload = {
            "msgtype": "text",
            "text": {
                "content": text
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                print("出港跟踪预警消息发送成功")
        except Exception as e:
            print(f"出港跟踪预警消息发送失败: {e}")

shenzhen_air_departure_alert_manager = ShenzhenAirDepartureAlertManager()
