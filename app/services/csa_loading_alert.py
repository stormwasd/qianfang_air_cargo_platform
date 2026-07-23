import asyncio
import httpx
import traceback
from datetime import datetime, timedelta
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func

import re
from app.database import SessionLocal
from app.config import settings
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_tracking import CsaLalamoveInformation, CsaProductInformation
from app.models.departure_manual_data import CsaDepartureManualData
from app.models.customer import Customer
from app.models.csa_loading_alert_task import CsaLoadingAlertTask
from app.utils.ctrip_client import ctrip_client


def is_uu_booking(booking_no: str) -> bool:
    if not booking_no:
        return False
    return "UU" in str(booking_no).upper()


def extract_base_qty(qty_str: str) -> str:
    """
    剥离体积和差异数据，例如：
    "139 / 2530 / 15.15 (1 / -110 / -0.66)" -> "139 / 2530 (1 / -110)"
    "10 / 87 / 0.52 (3 / 37 / 0.22)" -> "10 / 87 (3 / 37)"
    """
    if not qty_str or str(qty_str).strip() == "":
        return "/"
    
    qty_str = str(qty_str).strip()
    
    if "(" in qty_str and qty_str.endswith(")"):
        part1, part2 = qty_str.split("(", 1)
        part2 = part2.rstrip(")")
        
        p1_parts = [x.strip() for x in part1.split("/")]
        if len(p1_parts) >= 2:
            base_str = f"{p1_parts[0]} /{p1_parts[1]}"
        else:
            base_str = part1.strip()
            
        p2_parts = [x.strip() for x in part2.split("/")]
        if len(p2_parts) >= 2:
            diff_str = f"{p2_parts[0]} / {p2_parts[1]}"
        else:
            diff_str = part2.strip()
            
        return f"{base_str} ({diff_str})"
    else:
        parts = [x.strip() for x in qty_str.split("/")]
        if len(parts) >= 2:
            return f"{parts[0]} /{parts[1]}"
        return qty_str


class CsaLoadingAlertManager:
    """南航装机状态预警（100分钟）双定时任务引擎"""
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
        print("[CsaLoadingAlertManager] 已启动南航装机状态预警服务")

    def stop(self):
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        if self._exec_task:
            self._exec_task.cancel()

    async def _sync_loop(self):
        """同步循环：扫描当天的 approval data，获取计飞时间，入库"""
        while self._running:
            try:
                interval = settings.ALERT_CSA_LOADING_SYNC_INTERVAL_SECONDS
                if interval <= 0:
                    await asyncio.sleep(60)
                    continue
                
                await self._sync_tasks()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"南航装机预警同步任务异常: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)

    async def _sync_tasks(self):
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            approvals = db.query(ChinaSouthernAirApprovalData).filter(
                ChinaSouthernAirApprovalData.flight_info.like(f"%{today_str}%")
            ).all()

            added_approvals = set()

            for appv in approvals:
                if is_uu_booking(appv.booking_no):
                    continue

                appv_id = appv.id
                waybill_num = appv.waybill_number
                if not waybill_num:
                    continue
                
                if appv_id in added_approvals:
                    continue

                existing_task = db.query(CsaLoadingAlertTask).filter(
                    CsaLoadingAlertTask.approval_data_id == appv_id
                ).first()

                if existing_task:
                    continue
                
                flight_parts = [p.strip() for p in (appv.flight_info or "").split("/")]
                billing_flight = flight_parts[0] if len(flight_parts) > 0 else ""
                routing = flight_parts[2] if len(flight_parts) > 2 else ""
                
                ready_dt = None
                display_planned_time = ""

                if appv.planned_takeoff and str(appv.planned_takeoff).strip():
                    bt_clean = str(appv.planned_takeoff).strip().replace(":", "")
                    if len(bt_clean) >= 4:
                        try:
                            hour = int(bt_clean[:2])
                            minute = int(bt_clean[2:4])
                            ready_dt = datetime.strptime(today_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
                        except ValueError:
                            pass

                if billing_flight and routing:
                    routing_clean = routing.replace(" ", "") 
                    ctrip_times = await ctrip_client.get_flight_times(
                        flight_no=billing_flight,
                        flight_date=today_str,
                        routing=routing_clean
                    )
                    if ctrip_times and ctrip_times.get("ready_time"):
                        ready_time_str = ctrip_times.get("ready_time")
                        display_planned_time = ready_time_str
                        try:
                            if len(ready_time_str) > 16:
                                ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M:%S")
                            else:
                                ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M")
                        except ValueError:
                            pass

                if not display_planned_time:
                    display_planned_time = ready_dt.strftime("%Y-%m-%d %H:%M") if ready_dt else "未知预飞时间"

                if not ready_dt:
                    continue

                trigger_dt = ready_dt - timedelta(minutes=100)
                new_task = CsaLoadingAlertTask(
                    approval_data_id=appv_id,
                    waybill_number=waybill_num,
                    flight_date=today_str,
                    planned_time=display_planned_time,
                    trigger_time=trigger_dt,
                    status="pending"
                )
                db.add(new_task)
                added_approvals.add(appv_id)
            
            db.commit()

        finally:
            db.close()

    async def _exec_loop(self):
        """执行循环：到点提取数据、判断条件并触发企微"""
        while self._running:
            try:
                interval = settings.ALERT_CSA_LOADING_EXEC_INTERVAL_SECONDS
                if interval <= 0:
                    await asyncio.sleep(60)
                    continue

                now = datetime.now()
                db = SessionLocal()
                try:
                    tasks = db.query(CsaLoadingAlertTask).filter(
                        CsaLoadingAlertTask.status == "pending",
                        CsaLoadingAlertTask.trigger_time <= now
                    ).with_for_update(skip_locked=True).all()

                    for task in tasks:
                        task.status = "processing"
                    db.commit()

                    for task in tasks:
                        try:
                            await self._process_single_task(task, db)
                            task.status = "processed"
                        except Exception as e:
                            print(f"南航装机预警执行单任务异常 {task.id}: {e}")
                            traceback.print_exc()
                            task.status = "pending" 
                    
                    db.commit()
                finally:
                    db.close()
                
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"南航装机预警执行任务异常: {e}")
                traceback.print_exc()
                await asyncio.sleep(60)

    def _safe_float(self, val):
        if val is None or str(val).strip() == "": return 0.0
        try: return float(str(val).strip())
        except ValueError: return 0.0

    async def _process_single_task(self, task: CsaLoadingAlertTask, db: Session):
        approval_data_id = task.approval_data_id
        waybill_num = task.waybill_number
        flight_date = task.flight_date

        appv = db.query(ChinaSouthernAirApprovalData).filter(
            ChinaSouthernAirApprovalData.id == approval_data_id
        ).first()

        if not appv or is_uu_booking(appv.booking_no):
            task.status = "ignored"
            return
        
        shipper_unit = ""
        manual_data = db.query(CsaDepartureManualData).filter(
            CsaDepartureManualData.approval_data_id == appv.id
        ).first()
        if manual_data and manual_data.customer_name:
            c_id_str = str(manual_data.customer_name).strip()
            if c_id_str.isdigit():
                cust = db.query(Customer).filter(Customer.id == int(c_id_str)).first()
                if cust and cust.company_name:
                    shipper_unit = cust.company_name
                
        flight_parts = [p.strip() for p in (appv.flight_info or "").split("/")]
        billing_flight = flight_parts[0] if len(flight_parts) > 0 else "未知航班"
        routing = flight_parts[2] if len(flight_parts) > 2 else "未知航程"

        export_qty = self._safe_float(appv.booking_pieces)
        export_wt = self._safe_float(appv.booking_weight)
        
        billing_str = extract_base_qty(appv.billing_qty)
        goods_str = extract_base_qty(appv.goods_qty)
        machine_data_str = goods_str if goods_str != "/" else "/"

        lalamoves = db.query(CsaLalamoveInformation).filter(
            CsaLalamoveInformation.approval_data_id == appv.id
        ).all()
        
        products = db.query(CsaProductInformation).filter(
            CsaProductInformation.approval_data_id == appv.id
        ).all()

        sum_qty = 0.0
        sum_wt = 0.0
        has_inconsistent_flight = False
        has_empty_flight = False

        if not products:
            has_empty_flight = True
        else:
            for p in products:
                fd_info = str(p.flight_date_info).strip() if p.flight_date_info else ""
                if not fd_info:
                    has_empty_flight = True
                else:
                    p_flight = fd_info.split("/")[0].strip()
                    if p_flight != billing_flight:
                        has_inconsistent_flight = True
                        
        container_texts = []
        for l in lalamoves:
            l_qty = self._safe_float(l.pieces)
            l_wt = self._safe_float(l.weight)
            sum_qty += l_qty
            sum_wt += l_wt
            
            cap = str(l.capacity_lalamove).strip() if l.capacity_lalamove else ""
            c_code = cap.split("/")[0].strip() if cap else "/"
            
            display_flight = "未配航班"
            if products:
                for p in products:
                    fd_info = str(p.flight_date_info).strip() if p.flight_date_info else ""
                    if fd_info:
                        p_flight = fd_info.split("/")[0].strip()
                        display_flight = p_flight
                        if p_flight != billing_flight:
                            break 
            
            if display_flight != "未配航班" and appv.planned_takeoff:
                bt_clean = str(appv.planned_takeoff).strip().replace(":", "")
                if bt_clean:
                    display_flight = f"{display_flight} ({bt_clean})"
                    
            container_texts.append(f"{c_code}({int(l_qty)} / {int(l_wt)}) / {display_flight}")

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
            
        planned_time_display = task.planned_time.replace(" ", "  ")

        lines = [
            "装机状态通知（南方航空）",
            f"<font color=\"{'info' if alert_type == '装机正常' else 'warning'}\">{alert_type}</font>",
            "",
            f"客户名称：{shipper_unit}",
            f"运单号：{waybill_num}",
            f"开单航班/航程：{billing_flight} / {routing}",
            f"预飞时间：{planned_time_display}",
            f"制单数据：{billing_str}",
            f"过机数据：{machine_data_str}",
            "集装器/航班号："
        ]
        
        if not container_texts:
            lines.append("无集装器记录")
        else:
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
                print("南航装机预警消息发送成功")
        except Exception as e:
            print(f"南航装机预警发微信异常: {e}")

csa_loading_alert_manager = CsaLoadingAlertManager()
