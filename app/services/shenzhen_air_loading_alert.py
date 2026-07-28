import asyncio
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.database import SessionLocal
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.shenzhen_air_loading_alert_task import ShenzhenAirLoadingAlertTask
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.customer import Customer
from app.config import settings
from app.utils.ctrip_client import ctrip_client
import httpx

class ShenzhenAirLoadingAlertManager:
    """深航装机状态预警（100分钟）双定时任务引擎"""
    def __init__(self):
        self._running = False
        self._sync_task: asyncio.Task = None
        self._exec_task: asyncio.Task = None

    def start(self):
        if self._running:
            return
        self._running = True
        
        self._sync_task = asyncio.create_task(self._sync_loop())
        self._exec_task = asyncio.create_task(self._exec_loop())
        print("[ShenzhenAirLoadingAlertManager] 已启动深航装机状态预警服务")

    def stop(self):
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        if self._exec_task:
            self._exec_task.cancel()

    async def _sync_loop(self):
        """同步循环：扫描当天的 booking export，获取计飞时间，入库"""
        while self._running:
            try:
                interval = settings.ALERT_SHENZHEN_AIR_LOADING_SYNC_INTERVAL_SECONDS
                if interval <= 0:
                    await asyncio.sleep(60)
                    continue
                
                await self._sync_tasks()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"深航装机预警同步任务异常: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)

    async def _sync_tasks(self):
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

                existing_task = db.query(ShenzhenAirLoadingAlertTask).filter(
                    (ShenzhenAirLoadingAlertTask.booking_export_id == export.id) |
                    (
                        (ShenzhenAirLoadingAlertTask.waybill_number.in_(waybill_candidates)) &
                        (ShenzhenAirLoadingAlertTask.flight_date == today_str)
                    )
                ).first()

                if existing_task:
                    continue
                
                billing_flight = export.billing_flight
                routing = export.routing

                # 1. 确定计飞时间（billing_dt），用于计算 100 分钟前触发点
                billing_dt = None
                container = db.query(ShenzhenAirBillingTimeContainer).filter(
                    ShenzhenAirBillingTimeContainer.booking_export_id == export.id
                ).first()
                if container and container.billing_time and str(container.billing_time).strip():
                    bt_clean = str(container.billing_time).strip().replace(":", "")
                    if len(bt_clean) >= 4:
                        try:
                            hour = int(bt_clean[:2])
                            minute = int(bt_clean[2:4])
                            billing_dt = datetime.strptime(today_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
                        except ValueError:
                            pass
                
                if not billing_dt and billing_flight and routing:
                    ctrip_times = await ctrip_client.get_flight_times(
                        flight_no=billing_flight,
                        flight_date=today_str,
                        routing=routing
                    )
                    if ctrip_times and ctrip_times.get("planned_time"):
                        try:
                            planned_time_str = ctrip_times.get("planned_time")
                            if len(planned_time_str) > 16:
                                billing_dt = datetime.strptime(planned_time_str, "%Y-%m-%d %H:%M:%S")
                            else:
                                billing_dt = datetime.strptime(planned_time_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            pass
                
                if not billing_dt:
                    continue

                # 2. 获取预飞时间（ready_time），仅用于模板展示
                display_ready_time = "/"
                if billing_flight and routing:
                    ctrip_times = await ctrip_client.get_flight_times(
                        flight_no=billing_flight,
                        flight_date=today_str,
                        routing=routing
                    )
                    if ctrip_times and ctrip_times.get("ready_time"):
                        ready_time_str = str(ctrip_times.get("ready_time")).strip()
                        if ready_time_str:
                            display_ready_time = ready_time_str[:16]

                trigger_dt = billing_dt - timedelta(minutes=100)
                new_task = ShenzhenAirLoadingAlertTask(
                    booking_export_id=export.id,
                    waybill_number=full_waybill,
                    flight_date=today_str,
                    planned_time=display_ready_time,  # 模板展示【预飞时间】
                    trigger_time=trigger_dt,
                    status="pending"
                )
                db.add(new_task)
                added_export_ids.add(export.id)
            
            db.commit()

        finally:
            db.close()

    async def _exec_loop(self):
        """执行循环：到点提取数据、判断条件并触发企微"""
        interval = getattr(settings, "ALERT_SZX_LOADING_EXEC_INTERVAL_SECONDS", 60)
        while self._running:
            try:
                db = SessionLocal()
                try:
                    now = datetime.now()
                    tasks = db.query(ShenzhenAirLoadingAlertTask).filter(
                        ShenzhenAirLoadingAlertTask.status == "pending",
                        ShenzhenAirLoadingAlertTask.trigger_time <= now
                    ).all()

                    for task in tasks:
                        task.status = "processing"
                    db.commit()

                    for task in tasks:
                        try:
                            await self._process_single_task(task, db)
                            task.status = "processed"
                        except Exception as e:
                            print(f"处理深航装机预警单({task.id})异常: {e}")
                            traceback.print_exc()
                            task.status = "pending"
                        finally:
                            db.commit()
                finally:
                    db.close()
                
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"深航装机预警执行任务异常: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)

    def _format_planned_time(self, flight_date: str, raw_time: str) -> str:
        """规整预飞时间，确保输出为 'YYYY-MM-DD HH:MM' 格式或带有冒号的规范时间"""
        if not raw_time or str(raw_time).strip() in ["", "/", "None", "null"]:
            return "/"
        val = str(raw_time).strip()
        if len(val) >= 16 and "-" in val and ":" in val:
            return val[:16]
        
        clean_digits = val.replace(":", "").strip()
        if len(clean_digits) == 4 and clean_digits.isdigit():
            hh_mm = f"{clean_digits[:2]}:{clean_digits[2:4]}"
            if flight_date and "-" in flight_date:
                return f"{flight_date} {hh_mm}"
            return hh_mm
        
        if ":" in val and len(val) <= 5:
            if flight_date and "-" in flight_date:
                return f"{flight_date} {val}"
            return val
            
        return val

    async def _process_single_task(self, task: ShenzhenAirLoadingAlertTask, db):
        flight_date = task.flight_date or ""
        export = None
        if task.booking_export_id:
            export = db.query(ShenzhenAirBookingExport).filter(
                ShenzhenAirBookingExport.id == task.booking_export_id
            ).first()

        if not export:
            waybill_num = task.waybill_number or ""
            clean_waybill = waybill_num.replace("479-", "") if waybill_num.startswith("479-") else waybill_num
            full_waybill = f"479-{clean_waybill}"
            waybill_candidates = list(set([waybill_num, clean_waybill, full_waybill]))

            export = db.query(ShenzhenAirBookingExport).filter(
                ShenzhenAirBookingExport.waybill_number.in_(waybill_candidates),
                ShenzhenAirBookingExport.flight_date == flight_date
            ).order_by(ShenzhenAirBookingExport.id.desc()).first()

        if not export:
            task.status = "ignored"
            return

        raw_waybill = export.waybill_number or task.waybill_number or ""
        clean_waybill = raw_waybill.replace("479-", "") if raw_waybill.startswith("479-") else raw_waybill
        full_waybill = f"479-{clean_waybill}" if clean_waybill else "/"
        
        export_qty = 0
        export_wt = 0.0
        try:
            export_qty = int(export.quantity) if export.quantity else 0
            export_wt = float(export.weight) if export.weight else 0.0
        except ValueError:
            pass

        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.booking_export_id == export.id
        ).all()

        sum_qty = 0
        sum_wt = 0.0
        has_inconsistent_flight = False
        has_empty_flight = False
        billing_flight = str(export.billing_flight).strip() if export.billing_flight else ""

        container_texts = []

        if not containers:
            has_empty_flight = True
            container_texts.append(f"/ / 未配航班")
        else:
            for c in containers:
                c_qty_str = str(c.quantity).strip() if c.quantity else "0"
                c_wt_str = str(c.weight).strip() if c.weight else "0"
                try:
                    c_qty = int(c_qty_str)
                    sum_qty += c_qty
                except ValueError:
                    c_qty = 0
                try:
                    c_wt = float(c_wt_str)
                    sum_wt += c_wt
                except ValueError:
                    c_wt = 0.0
                
                c_flight = str(c.flight_number).strip() if c.flight_number else ""
                
                if not c_flight:
                    has_empty_flight = True
                    flight_text = "未配航班"
                else:
                    if c_flight != billing_flight:
                        has_inconsistent_flight = True
                    bt_clean = str(c.billing_time).strip().replace(":", "") if c.billing_time else ""
                    flight_text = f"{c_flight} ({bt_clean})" if bt_clean else c_flight
                
                c_code = str(c.container).strip() if c.container else "/"
                container_texts.append(f"{c_code} ({c_qty} / {int(c_wt)}) / {flight_text}")

        diff_qty = export_qty - sum_qty
        diff_wt = int(export_wt - sum_wt)

        is_qty_short = (sum_qty < export_qty) or (sum_wt < export_wt)

        alert_type = ""
        if not is_qty_short and not has_inconsistent_flight and not has_empty_flight:
            alert_type = "装机正常"
        elif not is_qty_short and (has_inconsistent_flight or has_empty_flight):
            alert_type = "疑似拉货预警"
        elif is_qty_short and not has_inconsistent_flight and not has_empty_flight:
            alert_type = "少货/取消货预警"
        elif is_qty_short and (has_inconsistent_flight or has_empty_flight):
            alert_type = "疑似拉货预警 / 少货/取消货预警"

        shipper_unit = ""
        manual_data = db.query(ShenzhenAirDepartureManualData).filter(
            ShenzhenAirDepartureManualData.booking_export_id == export.id
        ).first()
        if manual_data and manual_data.customer_name:
            c_id_str = str(manual_data.customer_name).strip()
            if c_id_str.isdigit():
                cust = db.query(Customer).filter(Customer.id == int(c_id_str)).first()
                if cust and cust.company_name:
                    shipper_unit = cust.company_name
        
        planned_time_display = self._format_planned_time(flight_date or task.flight_date, task.planned_time)

        lines = [
            "装机状态通知（深圳航空）",
            f"<font color=\"{'info' if alert_type == '装机正常' else 'warning'}\">{alert_type}</font>",
            "",
            f"客户名称：{shipper_unit}",
            f"运单号：{full_waybill}",
            f"开单航班/航程：{billing_flight} / {export.routing or '/'}",
            f"预飞时间：{planned_time_display}",
            f"制单数据：{export_qty} / {int(export_wt)}",
            f"过机数据：{int(sum_qty)} / {int(sum_wt)} ({int(diff_qty)} / {int(diff_wt)})",
            "集装器 / 航班号："
        ]
        
        lines.extend(container_texts)

        msg = "\n".join(lines)
        await self._send_wechat_msg(msg)

    async def _send_wechat_msg(self, text: str):
        url = settings.WECHAT_WEBHOOK_URL
        if not url:
            print("WECHAT_WEBHOOK_URL 未配置")
            return
        
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": text
            }
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload, timeout=10)
                resp.raise_for_status()
                print("深航装机预警消息发送成功")
        except Exception as e:
            print(f"深航装机预警发微信异常: {e}")

shenzhen_air_loading_alert_manager = ShenzhenAirLoadingAlertManager()
