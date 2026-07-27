import asyncio
import threading
import traceback
import json
import random
from datetime import datetime, timedelta
import pandas as pd
import os
import re
from typing import Optional, List

from app.config import settings
from app.database import SessionLocal
import httpx
from app.utils.ctrip_client import ctrip_client
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.customer import Customer
from app.models.alert_notification_record import AlertNotificationRecord

class ShenzhenAirDepartureStatusAlertService:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._phone_dict = {}
        self._load_phone_excel()

    def _load_phone_excel(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        excel_path = os.path.join(base_dir, "深航提货电话.xlsx")
        try:
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                for index, row in df.iterrows():
                    city_code = str(row.get("城市代码", "")).strip()
                    phone = str(row.get("联系电话", "")).strip()
                    if city_code and phone and phone != "nan":
                        self._phone_dict[city_code] = phone
                print(f"[ShenzhenAirDepartureStatusAlert] 已加载提货电话 {len(self._phone_dict)} 条记录")
            else:
                print(f"[ShenzhenAirDepartureStatusAlert] 未找到提货电话文件: {excel_path}")
        except Exception as e:
            print(f"[ShenzhenAirDepartureStatusAlert] 加载提货电话文件失败: {e}")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[ShenzhenAirDepartureStatusAlert] 已启动深航出港状态预警服务")

    def stop(self) -> None:
        self._stop_event.set()
        print("[ShenzhenAirDepartureStatusAlert] 已停止深航出港状态预警服务")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        """主循环：处理间隔触发和定时触发"""
        interval = getattr(settings, "ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_INTERVAL_SECONDS", 600)
        fixed_times_str = getattr(settings, "ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_FIXED_TIMES", "")

        fixed_times: List[str] = []
        if fixed_times_str and fixed_times_str.strip():
            fixed_times = [t.strip() for t in fixed_times_str.split(",") if t.strip()]

        triggered_fixed_times: set = set()
        elapsed = 0

        while not self._stop_event.is_set():
            try:
                now = datetime.now()
                current_time_str = now.strftime("%H:%M")
                current_date_str = now.strftime("%Y-%m-%d")

                if current_time_str in fixed_times and current_time_str not in triggered_fixed_times:
                    triggered_fixed_times.add(current_time_str)
                    print(f"[ShenzhenAirDepartureStatusAlert] 定时触发（{current_time_str}）")
                    await self._scan_and_alert()

                if interval and interval > 0:
                    elapsed += 5
                    if elapsed >= interval:
                        elapsed = 0
                        print(f"[ShenzhenAirDepartureStatusAlert] 间隔触发")
                        await self._scan_and_alert()

            except Exception as e:
                print(f"[ShenzhenAirDepartureStatusAlert] 主循环异常: {e}")

            await asyncio.sleep(5)

    def _safe_float(self, val):
        if val is None or str(val).strip() == "": return 0.0
        try: return float(str(val).strip())
        except ValueError: return 0.0

    def _clean_flight_no(self, raw_flight_str: str) -> str:
        """提取纯航班号，去除日期与重量描述等后缀 (如 'ZH9511/2026-06-09(806.00)' -> 'ZH9511')"""
        if not raw_flight_str:
            return ""
        first_part = str(raw_flight_str).split("/")[0].strip()
        match = re.search(r"^[A-Za-z0-9]+", first_part)
        return match.group(0) if match else first_part

    async def _scan_and_alert(self) -> None:
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            records = db.query(ShenzhenAirBookingExport).filter(
                ShenzhenAirBookingExport.flight_date == today_str
            ).all()

            for record in records:
                try:
                    await self._process_single_record(record, db)
                except Exception as e:
                    print(f"[ShenzhenAirDepartureStatusAlert] 处理单号 {record.waybill_number} 异常: {e}")
                await asyncio.sleep(random.uniform(1.0, 3.0))

        except Exception as e:
            print(f"[ShenzhenAirDepartureStatusAlert] 扫描异常: {e}")
            traceback.print_exc()
        finally:
            db.close()

    async def _process_single_record(self, record: ShenzhenAirBookingExport, db) -> None:
        waybill_num = record.waybill_number
        if not waybill_num:
            return

        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.booking_export_id == record.id
        ).all()

        # 条件 1：必须存在有效集装器记录
        valid_containers = [
            c for c in containers 
            if c.container and str(c.container).strip() not in ("", "/")
        ]
        if not valid_containers:
            return

        billing_flight = record.billing_flight or ""
        flight_date = record.flight_date or ""
        routing = record.routing or ""
        clean_billing_flight = self._clean_flight_no(billing_flight)

        # 条件 2：通过携程获取预飞时间 ready_time，必须满足 当前时间 >= 预飞时间 才触发
        now = datetime.now()
        ready_dt = None
        planned_time_str = ""

        if routing and "-" in routing and clean_billing_flight:
            flight_res = await ctrip_client.get_flight_times(clean_billing_flight, flight_date, routing)
            if flight_res:
                if flight_res.get("planned_time"):
                    planned_time_str = flight_res.get("planned_time")
                if flight_res.get("ready_time"):
                    ready_time_str = flight_res.get("ready_time")
                    try:
                        if len(ready_time_str) > 16:
                            ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M:%S")
                        else:
                            ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M")
                    except ValueError:
                        pass

        if not ready_dt and containers and containers[0].billing_time:
            bt_clean = str(containers[0].billing_time).strip().replace(":", "")
            if len(bt_clean) >= 4:
                try:
                    hour = int(bt_clean[:2])
                    minute = int(bt_clean[2:4])
                    ready_dt = datetime.strptime(flight_date, "%Y-%m-%d").replace(hour=hour, minute=minute)
                except ValueError:
                    pass

        # 触发判定：若无法解析预飞时间，或当前时间尚未达到预飞时间，则不触发通知
        if not ready_dt or now < ready_dt:
            return

        qty_diff = self._safe_float(record.quantity_difference)
        wt_diff = self._safe_float(record.weight_difference)
        
        actual_flight_str = record.actual_flight or billing_flight
        raw_actual_flights = [f.strip() for f in re.split(r'[,;]', actual_flight_str) if f.strip()]
        parsed_actual_flights = []
        for raw_flt in raw_actual_flights:
            clean_flt = self._clean_flight_no(raw_flt)
            if clean_flt and clean_flt not in parsed_actual_flights:
                parsed_actual_flights.append(clean_flt)

        if not parsed_actual_flights and clean_billing_flight:
            parsed_actual_flights = [clean_billing_flight]

        # 收集需要查询实飞时间的去重航班列表（开单航班 + 实走航班）
        query_flights = []
        if clean_billing_flight and clean_billing_flight not in query_flights:
            query_flights.append(clean_billing_flight)
        for flt in parsed_actual_flights:
            if flt not in query_flights:
                query_flights.append(flt)

        actual_time_displays = []
        is_delayed = False
        
        for flt in query_flights:
            if routing and "-" in routing:
                flight_res = await ctrip_client.get_flight_times(flt, flight_date, routing)
                if flight_res and flight_res.get("actual_time"):
                    act_time = flight_res.get("actual_time")
                    actual_time_displays.append(f"{flt} / {act_time}")
                    
                    if planned_time_str:
                        try:
                            act_dt_str = act_time if len(act_time) > 16 else act_time + ":00"
                            act_dt = datetime.strptime(act_dt_str, "%Y-%m-%d %H:%M:%S")
                            
                            plan_dt_str = planned_time_str if len(planned_time_str) > 16 else planned_time_str + ":00"
                            plan_dt = datetime.strptime(plan_dt_str, "%Y-%m-%d %H:%M:%S")
                            
                            if act_dt > plan_dt:
                                is_delayed = True
                        except Exception:
                            pass
                else:
                    actual_time_displays.append(f"{flt} / 暂无")
        
        is_abnormal = qty_diff > 0 or wt_diff > 0 or is_delayed
        status_text = "出港异常" if is_abnormal else "出港正常"
        
        actual_time_text = " ；".join(actual_time_displays) if actual_time_displays else "/"
        actual_flight_display = "；".join(parsed_actual_flights) if parsed_actual_flights else clean_billing_flight

        state_hash = f"{qty_diff}_{wt_diff}_{is_delayed}"
        
        alert_record = db.query(AlertNotificationRecord).filter(
            AlertNotificationRecord.module_name == "shenzhen_air_departure_status",
            AlertNotificationRecord.target_id == str(record.id)
        ).first()

        if alert_record and alert_record.state_hash == state_hash:
            return
        
        customer_name = ""
        manual_data = db.query(ShenzhenAirDepartureManualData).filter(
            ShenzhenAirDepartureManualData.booking_export_id == record.id
        ).first()
        if manual_data and manual_data.customer_name:
            c_id_str = str(manual_data.customer_name).strip()
            if c_id_str.isdigit():
                cust = db.query(Customer).filter(Customer.id == int(c_id_str)).first()
                if cust and cust.company_name:
                    customer_name = cust.company_name

        full_waybill = waybill_num if waybill_num.startswith("479-") else f"479-{waybill_num}"
            
        sum_qty = sum([self._safe_float(c.quantity) for c in containers])
        sum_wt = sum([self._safe_float(c.weight) for c in containers])
        
        qty_diff_actual = self._safe_float(record.quantity) - sum_qty
        wt_diff_actual = self._safe_float(record.weight) - sum_wt
        
        telephone = "/"
        if routing and "-" in routing:
            dest = routing.split("-")[1].strip()
            telephone = self._phone_dict.get(dest, "/")
            
        msg = f"""出港状态通知（深圳航空）
{status_text}

客户名称：{customer_name}
运单号：{full_waybill}
开单航班/航程：{billing_flight} / {record.routing}
实走航班：{actual_flight_display}
实飞时间：{actual_time_text}
制单数据：{record.quantity} / {record.weight}
实走数据：{int(sum_qty)} / {int(sum_wt)} ({int(qty_diff_actual)} / {wt_diff_actual})
收货人：{record.consignee}
提货电话：{telephone}

落地两小时后联系提货（收货人携带好身份证）"""

        await self._send_wechat_message(msg)
        
        if alert_record:
            alert_record.state_hash = state_hash
        else:
            new_record = AlertNotificationRecord(
                module_name="shenzhen_air_departure_status",
                target_id=str(record.id),
                state_hash=state_hash
            )
            db.add(new_record)
        db.commit()
        
        print(f"[ShenzhenAirDepartureStatusAlert] 已发送单号 {waybill_num} 状态: {status_text}")

    async def _send_wechat_message(self, text: str) -> None:
        url = settings.WECHAT_WEBHOOK_URL
        if not url:
            print("[ShenzhenAirDepartureStatusAlert] WECHAT_WEBHOOK_URL 未配置")
            return
        
        payload = {
            "msgtype": "text",
            "text": {
                "content": text
            }
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
        except Exception as e:
            print(f"[ShenzhenAirDepartureStatusAlert] 发送企业微信消息失败: {e}")

shenzhen_air_departure_status_alert = ShenzhenAirDepartureStatusAlertService()
