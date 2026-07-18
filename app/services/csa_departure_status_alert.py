import asyncio
import threading
import traceback
import random
import re
from datetime import datetime
import pandas as pd
import os
from typing import Optional, List
import httpx

from app.config import settings
from app.database import SessionLocal
from app.utils.ctrip_client import ctrip_client
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.waybill import Waybill
from app.utils.airport_code_mapper import get_city_name_by_code
from app.models.csa_departure_alert_task import CsaDepartureAlertTask
from app.models.alert_notification_record import AlertNotificationRecord

class CsaDepartureStatusAlertService:
    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._phone_dict = {}
        self._load_phone_excel()

    def _load_phone_excel(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        excel_path = os.path.join(base_dir, "全国民用机场提货电话.xlsx")
        try:
            if os.path.exists(excel_path):
                df = pd.read_excel(excel_path)
                for index, row in df.iterrows():
                    dest = str(row.get("目的地", "")).strip()
                    airline = str(row.get("航司", "")).strip()
                    phone = str(row.get("联系电话", "")).strip()
                    
                    if dest and dest != "nan" and phone and phone != "nan":
                        if "南方航空" in airline or "南航" in airline:
                            self._phone_dict[dest] = phone
                print(f"[CsaDepartureStatusAlert] 已加载南航提货电话 {len(self._phone_dict)} 条记录")
            else:
                print(f"[CsaDepartureStatusAlert] 未找到提货电话文件: {excel_path}")
        except Exception as e:
            print(f"[CsaDepartureStatusAlert] 加载提货电话文件失败: {e}")

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[CsaDepartureStatusAlert] 已启动南航出港状态预警服务")

    def stop(self) -> None:
        self._stop_event.set()
        print("[CsaDepartureStatusAlert] 已停止南航出港状态预警服务")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        interval = getattr(settings, "ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_INTERVAL_SECONDS", 600)
        fixed_times_str = getattr(settings, "ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_FIXED_TIMES", "")

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
                    print(f"[CsaDepartureStatusAlert] 定时触发（{current_time_str}）")
                    await self._scan_and_alert()

                if interval and interval > 0:
                    elapsed += 5
                    if elapsed >= interval:
                        elapsed = 0
                        print(f"[CsaDepartureStatusAlert] 间隔触发")
                        await self._scan_and_alert()

            except Exception as e:
                print(f"[CsaDepartureStatusAlert] 主循环异常: {e}")

            await asyncio.sleep(5)

    def _parse_flight_info(self, flight_info_str):
        if not flight_info_str: return "", "", ""
        parts = [p.strip() for p in str(flight_info_str).split("/")]
        billing_flight = parts[0] if len(parts) > 0 else ""
        flight_date = parts[1] if len(parts) > 1 else ""
        routing = parts[2] if len(parts) > 2 else ""
        return billing_flight, flight_date, routing
        
    def _extract_billing_qty(self, qty_str: str):
        if not qty_str: return "0 / 0"
        match = re.search(r"([\d\.]+)\s*/\s*([\d\.]+)", str(qty_str))
        if match:
            return f"{match.group(1)} / {match.group(2)}"
        return "0 / 0"

    def _extract_actual_qty(self, qty_str: str):
        if not qty_str: return "0 / 0 (0 / 0)", 0.0, 0.0
        match = re.search(r"([\d\.]+)\s*/\s*([\d\.]+).*?\(([\-\d\.]+)\s*/\s*([\-\d\.]+)", str(qty_str))
        if match:
            display = f"{match.group(1)} / {match.group(2)} ({match.group(3)} / {match.group(4)})"
            diff_p = float(match.group(3))
            diff_w = float(match.group(4))
            return display, diff_p, diff_w
        
        match = re.search(r"([\d\.]+)\s*/\s*([\d\.]+)", str(qty_str))
        if match:
            return f"{match.group(1)} / {match.group(2)} (0 / 0)", 0.0, 0.0
        return "0 / 0 (0 / 0)", 0.0, 0.0

    async def _scan_and_alert(self) -> None:
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            records = db.query(ChinaSouthernAirApprovalData).filter(
                ChinaSouthernAirApprovalData.flight_info.like(f"%{today_str}%")
            ).all()

            for record in records:
                try:
                    await self._process_single_record(record, db)
                except Exception as e:
                    print(f"[CsaDepartureStatusAlert] 处理单号 {record.waybill_number} 异常: {e}")
                
                await asyncio.sleep(random.uniform(1.0, 3.0))

        except Exception as e:
            print(f"[CsaDepartureStatusAlert] 扫描异常: {e}")
            traceback.print_exc()
        finally:
            db.close()

    async def _process_single_record(self, record: ChinaSouthernAirApprovalData, db) -> None:
        waybill_num = record.waybill_number
        if not waybill_num:
            return
            
        billing_flight, flight_date, routing = self._parse_flight_info(record.flight_info)
        
        billing_data_display = self._extract_billing_qty(record.billing_qty)
        actual_data_display, diff_pieces, diff_weight = self._extract_actual_qty(record.actual_qty)
        
        planned_time_str = ""
        if routing and "-" in routing and billing_flight and flight_date:
            flight_res = await ctrip_client.get_flight_times(billing_flight, flight_date, routing)
            if flight_res and flight_res.get("ready_time"):
                planned_time_str = flight_res.get("ready_time")
                
        actual_flight_str = record.actual_flight or ""
        actual_flights = [f.strip() for f in re.split(r'[,;]', actual_flight_str) if f.strip()]
        actual_time_displays = []
        is_delayed = False
        
        for flt in actual_flights:
            if routing and "-" in routing and flight_date:
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
        
        is_abnormal = diff_pieces > 0 or diff_weight > 0 or is_delayed
        status_text = "出港异常" if is_abnormal else "出港正常"
        
        actual_time_text = "；".join(actual_time_displays) if actual_time_displays else "/"
        actual_flight_display = "；".join(actual_flights) if actual_flights else "/"
        
        state_hash = f"{diff_pieces}_{diff_weight}_{is_delayed}"
        
        alert_record = db.query(AlertNotificationRecord).filter(
            AlertNotificationRecord.module_name == "csa_departure_status",
            AlertNotificationRecord.target_id == str(record.id)
        ).first()
        
        if alert_record and alert_record.state_hash == state_hash:
            return 
            
        customer_name = "未知客户"
        consignee_name = "未知"
        waybill_record = db.query(Waybill).filter(
            Waybill.waybill_number == waybill_num,
            Waybill.airline_record_status == 3
        ).first()
        
        if waybill_record and waybill_record.form_data:
            shipper_info = waybill_record.form_data.get("shipper_consignee_info", {})
            customer_name = shipper_info.get("shipper_unit", "未知客户")
            contact_info = waybill_record.form_data.get("contact_info", {})
            consignee_name = contact_info.get("consignee", "未知")

        telephone = "/"
        if routing and "-" in routing:
            dest_code = routing.split("-")[1].strip()
            city_name = get_city_name_by_code(dest_code)
            if city_name:
                telephone = self._phone_dict.get(city_name, "/")

        msg = f"""出港状态通知（南方航空）
{status_text}

客户名称：{customer_name}
运单号：{waybill_num}
开单航班/航程：{billing_flight} / {routing}
实走航班/航程：{actual_flight_display}
实飞时间：{actual_time_text}
制单数据：{billing_data_display}
实走数据：{actual_data_display}
收货人：{consignee_name}
提货电话：{telephone}

落地两小时后联系提货（收货人携带好身份证）"""

        await self._send_wechat_message(msg)
        
        if alert_record:
            alert_record.state_hash = state_hash
        else:
            new_record = AlertNotificationRecord(
                module_name="csa_departure_status",
                target_id=str(record.id),
                state_hash=state_hash
            )
            db.add(new_record)
        db.commit()
        
        print(f"[CsaDepartureStatusAlert] 已发送单号 {waybill_num} 状态: {status_text}")

    async def _send_wechat_message(self, text: str) -> None:
        url = settings.WECHAT_WEBHOOK_URL
        if not url:
            print("[CsaDepartureStatusAlert] WECHAT_WEBHOOK_URL 未配置")
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
            print(f"[CsaDepartureStatusAlert] 发送企业微信消息失败: {e}")

csa_departure_status_alert = CsaDepartureStatusAlertService()
