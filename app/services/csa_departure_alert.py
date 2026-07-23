import asyncio
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
import traceback
import re
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.config import settings
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.departure_manual_data import CsaDepartureManualData
from app.models.customer import Customer
from app.models.csa_departure_alert_task import CsaDepartureAlertTask
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


class CsaDepartureAlertManager:
    """南航出港跟踪预警服务"""

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
        print("[CsaDepartureAlertManager] 已启动南航过机状态与卡号预警服务")

    def stop(self):
        """停止后台调度器"""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
        if self._exec_task:
            self._exec_task.cancel()
        print("南航出港跟踪预警服务已停止")

    async def _sync_loop(self):
        """同步任务：每 N 分钟扫描新运单并加入待办队列表"""
        interval = getattr(settings, "ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_SYNC_INTERVAL_SECONDS", 300)
        while self._running:
            try:
                await self._sync_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"南航出港跟踪同步任务异常: {e}")
                traceback.print_exc()
            finally:
                await asyncio.sleep(interval)

    async def _exec_loop(self):
        """执行任务：每 1 分钟扫描到点的任务并执行"""
        interval = getattr(settings, "ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_EXEC_INTERVAL_SECONDS", 60)
        while self._running:
            try:
                await self._exec_tasks()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"南航出港跟踪执行任务异常: {e}")
                traceback.print_exc()
            finally:
                await asyncio.sleep(interval)


    async def _sync_tasks(self):
        """扫描当天 china_southern_air_approval_data 表，更新队列表"""
        db = SessionLocal()
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            approvals = db.query(ChinaSouthernAirApprovalData).filter(
                ChinaSouthernAirApprovalData.flight_info.contains(today_str)
            ).all()

            added_approval_ids = set()

            for appv in approvals:
                if is_uu_booking(appv.booking_no):
                    continue

                appv_id = appv.id
                waybill_num = appv.waybill_number
                flight_info = appv.flight_info
                if not waybill_num or not flight_info:
                    continue
                
                if appv_id in added_approval_ids:
                    continue
                
                parts = [p.strip() for p in flight_info.split("/")]
                if len(parts) < 3:
                    continue
                flight_no = parts[0]
                flight_date = parts[1]
                routing = parts[2].replace(" ", "")  

                if flight_date != today_str:
                    continue

                existing_task = db.query(CsaDepartureAlertTask).filter(
                    CsaDepartureAlertTask.approval_data_id == appv_id
                ).first()

                if existing_task:
                    continue  

                planned_dt = None
                
                takeoff_str = appv.planned_takeoff
                if takeoff_str and str(takeoff_str).strip():
                    bt_clean = str(takeoff_str).strip().replace(":", "")
                    if len(bt_clean) >= 4:
                        try:
                            hour = int(bt_clean[:2])
                            minute = int(bt_clean[2:4])
                            planned_dt = datetime.strptime(today_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
                        except ValueError:
                            pass
                
                if not planned_dt:
                    ctrip_times = await ctrip_client.get_flight_times(
                        flight_no=flight_no,
                        flight_date=today_str,
                        routing=routing
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
                new_task = CsaDepartureAlertTask(
                    approval_data_id=appv_id,
                    waybill_number=waybill_num,
                    flight_date=today_str,
                    planned_time=planned_dt.strftime("%Y-%m-%d %H:%M"),
                    trigger_time=trigger_dt,
                    status="pending"
                )
                db.add(new_task)
                added_approval_ids.add(appv_id)
            
            db.commit()

        finally:
            db.close()


    async def _exec_tasks(self):
        """拉取到点的 pending 任务，执行预警逻辑"""
        db = SessionLocal()
        try:
            now = datetime.now()
            tasks = db.query(CsaDepartureAlertTask).filter(
                CsaDepartureAlertTask.status == "pending",
                CsaDepartureAlertTask.trigger_time <= now
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
            task = db.query(CsaDepartureAlertTask).filter(CsaDepartureAlertTask.id == task_id).first()
            if not task:
                return

            approval_data_id = task.approval_data_id
            waybill_num = task.waybill_number
            flight_date = task.flight_date

            appv_record = db.query(ChinaSouthernAirApprovalData).filter(
                ChinaSouthernAirApprovalData.id == approval_data_id
            ).first()

            if not appv_record or is_uu_booking(appv_record.booking_no):
                task.status = "ignored"
                db.commit()
                return

            containers = db.query(CsaLalamoveInformation).filter(
                CsaLalamoveInformation.approval_data_id == appv_record.id
            ).all()

            await self._evaluate_and_send_alert(db, task, appv_record, containers)

            task.status = "processed"
            db.commit()
        except Exception as e:
            print(f"处理南航出港跟踪预警单({task_id})异常: {e}")
            traceback.print_exc()
            task.status = "pending" 
            db.commit()
        finally:
            db.close()

    async def _evaluate_and_send_alert(self, db: Session, task: CsaDepartureAlertTask, appv_record: ChinaSouthernAirApprovalData, containers: List[CsaLalamoveInformation]):
        """核心业务逻辑：分析数据，判断场景，发送模板"""
        
        customer_name = ""
        manual_data = db.query(CsaDepartureManualData).filter(
            CsaDepartureManualData.approval_data_id == appv_record.id
        ).first()
        if manual_data and manual_data.customer_name:
            c_id_str = str(manual_data.customer_name).strip()
            if c_id_str.isdigit():
                cust = db.query(Customer).filter(Customer.id == int(c_id_str)).first()
                if cust and cust.company_name:
                    customer_name = cust.company_name
        
        flight_parts = [p.strip() for p in (appv_record.flight_info or "").split("/")]
        billing_flight = flight_parts[0] if len(flight_parts) > 0 else "未知航班"
        routing = flight_parts[2] if len(flight_parts) > 2 else "未知航程"
        
        def _safe_float(val):
            if val is None or str(val).strip() == "": return 0.0
            try: return float(str(val).strip())
            except ValueError: return 0.0

        booking_pieces = _safe_float(appv_record.booking_pieces)
        booking_weight = _safe_float(appv_record.booking_weight)
        
        billing_str = extract_base_qty(appv_record.billing_qty)

        valid_containers = []
        sum_qty = 0.0
        sum_wt = 0.0
        container_details = []
        
        for c in containers:
            raw_container = c.capacity_lalamove or ""
            c_code = raw_container.split("/")[0].strip()
            
            if c_code:
                c_qty = _safe_float(c.pieces)
                c_wt = _safe_float(c.weight)
                sum_qty += c_qty
                sum_wt += c_wt
                valid_containers.append(c)
                container_details.append(f"{c_code}({int(c_qty)} / {int(c_wt)})")

        if not valid_containers:
            alert_title = "过机时间超时预警"
            machine_data_str = "/"
            containers_str = "/"
        else:
            goods_str = extract_base_qty(appv_record.goods_qty)
            machine_data_str = goods_str if goods_str != "/" else "/"
            containers_str = "\n".join(container_details)

            if sum_qty >= booking_pieces and sum_wt >= booking_weight:
                alert_title = "过机正常"
            else:
                alert_title = "少货/取消货预警"

        planned_time_display = task.planned_time.replace(" ", "  ") 
        
        message = (
            f"过机状态通知（南方航空）\n"
            f"{alert_title}\n\n"
            f"客户名称：{customer_name}\n"
            f"运单号：{task.waybill_number}\n"
            f"开单航班/航程：{billing_flight}  / {routing}\n"
            f"计飞时间：{planned_time_display}\n"
            f"制单数据：{billing_str}\n"
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
                print("南航出港跟踪预警消息发送成功")
        except Exception as e:
            print(f"南航出港跟踪预警消息发送失败: {e}")

csa_departure_alert_manager = CsaDepartureAlertManager()
