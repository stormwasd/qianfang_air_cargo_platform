import asyncio
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any

from app.database import SessionLocal
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.shenzhen_air_loading_alert_task import ShenzhenAirLoadingAlertTask
from app.models.waybill import Waybill
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
        
        # 即使配了0也启动协程，里面会判断是否跳过
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
            
            # 查出当天的所有出口单
            exports = db.query(ShenzhenAirBookingExport).filter(
                ShenzhenAirBookingExport.flight_date == today_str
            ).all()

            added_waybills = set()

            for export in exports:
                waybill_num = export.waybill_number
                if not waybill_num:
                    continue
                
                if waybill_num in added_waybills:
                    continue

                # 检查是否已在任务表中
                existing_task = db.query(ShenzhenAirLoadingAlertTask).filter(
                    ShenzhenAirLoadingAlertTask.waybill_number == waybill_num,
                    ShenzhenAirLoadingAlertTask.flight_date == today_str
                ).first()

                if existing_task:
                    continue
                
                # 尝试去深圳航空的过机表里拿计飞时间
                waybill_num_8 = waybill_num.replace("479-", "")
                container = db.query(ShenzhenAirBillingTimeContainer).filter(
                    ShenzhenAirBillingTimeContainer.waybill_number_8 == waybill_num_8,
                    ShenzhenAirBillingTimeContainer.flight_date == today_str
                ).first()

                ready_dt = None
                
                # 1. 尝试从过机表里拿计飞时间 (ReadyDateTime)
                if container and container.billing_time and str(container.billing_time).strip():
                    bt_clean = str(container.billing_time).strip().replace(":", "")
                    if len(bt_clean) >= 4:
                        try:
                            hour = int(bt_clean[:2])
                            minute = int(bt_clean[2:4])
                            ready_dt = datetime.strptime(today_str, "%Y-%m-%d").replace(hour=hour, minute=minute)
                        except ValueError:
                            pass
                
                # 2. 从携程拿预飞时间(plannedDateTime) 和 兜底计飞时间(ReadyDateTime)
                display_planned_time = ""
                actual_flight = export.actual_flight
                routing = export.routing
                if actual_flight and routing:
                    ctrip_times = await ctrip_client.get_flight_times(
                        flight_no=actual_flight,
                        flight_date=today_str,
                        routing=routing
                    )
                    if ctrip_times:
                        # 预飞时间用于展示
                        display_planned_time = ctrip_times.get("planned_time") or ""
                        # 如果过机表里没拿到计飞时间，用携程的兜底
                        if not ready_dt and ctrip_times.get("ready_time"):
                            try:
                                ready_time_str = ctrip_times.get("ready_time")
                                if len(ready_time_str) > 16:
                                    ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M:%S")
                                else:
                                    ready_dt = datetime.strptime(ready_time_str, "%Y-%m-%d %H:%M")
                            except ValueError:
                                pass
                
                # 如果没有获取到展示的预飞时间，尽量回退
                if not display_planned_time:
                    display_planned_time = ready_dt.strftime("%Y-%m-%d %H:%M") if ready_dt else "未知预飞时间"
                
                # 最终拿不到计飞时间，跳过
                if not ready_dt:
                    continue

                # 创建任务 (计飞时间提前 100 分钟触发)
                trigger_dt = ready_dt - timedelta(minutes=100)
                new_task = ShenzhenAirLoadingAlertTask(
                    waybill_number=waybill_num,
                    flight_date=today_str,
                    planned_time=display_planned_time,  # 用于模板中展示“预飞时间”
                    trigger_time=trigger_dt,
                    status="pending"
                )
                db.add(new_task)
                added_waybills.add(waybill_num)
            
            db.commit()

        finally:
            db.close()

    async def _exec_loop(self):
        """执行循环：到点提取数据、判断条件并触发企微"""
        while self._running:
            try:
                interval = settings.ALERT_SHENZHEN_AIR_LOADING_EXEC_INTERVAL_SECONDS
                if interval <= 0:
                    await asyncio.sleep(60)
                    continue

                now = datetime.now()
                db = SessionLocal()
                try:
                    # 获取待执行任务
                    tasks = db.query(ShenzhenAirLoadingAlertTask).filter(
                        ShenzhenAirLoadingAlertTask.status == "pending",
                        ShenzhenAirLoadingAlertTask.trigger_time <= now
                    ).with_for_update(skip_locked=True).all()

                    for task in tasks:
                        task.status = "processing"
                    db.commit()

                    for task in tasks:
                        try:
                            await self._process_single_task(task, db)
                            task.status = "processed"
                        except Exception as e:
                            print(f"深航装机预警执行单任务异常 {task.id}: {e}")
                            traceback.print_exc()
                            task.status = "pending" # 可以等下次重试
                    
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

    async def _process_single_task(self, task: ShenzhenAirLoadingAlertTask, db):
        waybill_num = task.waybill_number
        flight_date = task.flight_date

        # 取最新的开单数据
        export = db.query(ShenzhenAirBookingExport).filter(
            ShenzhenAirBookingExport.waybill_number == waybill_num,
            ShenzhenAirBookingExport.flight_date == flight_date
        ).order_by(ShenzhenAirBookingExport.id.desc()).first()

        if not export:
            task.status = "ignored"
            return
        
        # 提取制单的件重
        export_qty = 0
        export_wt = 0.0
        try:
            export_qty = int(export.quantity) if export.quantity else 0
            export_wt = float(export.weight) if export.weight else 0.0
        except ValueError:
            pass

        # 关联所有集装器数据 (过机数据)
        waybill_num_8 = waybill_num.replace("479-", "")
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.waybill_number_8 == waybill_num_8,
            ShenzhenAirBillingTimeContainer.flight_date == flight_date
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
                    # 这里提取航班的四位计飞时间展示
                    bt_clean = str(c.billing_time).strip().replace(":", "") if c.billing_time else ""
                    flight_text = f"{c_flight} ({bt_clean})" if bt_clean else c_flight
                
                c_code = str(c.container).strip() if c.container else "/"
                container_texts.append(f"{c_code} ({c_qty} / {int(c_wt)}) / {flight_text}")

        # 计算差异
        diff_qty = export_qty - sum_qty
        diff_wt = int(export_wt - sum_wt)

        # 核心逻辑判定
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

        # 发货人获取
        shipper_unit = "未知发货人"
        query_wb = waybill_num if waybill_num.startswith("479-") else f"479-{waybill_num}"
        wb_record = db.query(Waybill).filter(Waybill.waybill_number == query_wb).first()
        if wb_record and wb_record.form_data:
            shipper_info = wb_record.form_data.get("shipper_consignee_info", {})
            shipper_unit = shipper_info.get("shipper_unit", "未知发货人")
            if not shipper_unit:
                shipper_unit = "未知发货人"
        
        # 拼装消息
        lines = [
            "装机状态通知（深圳航空）",
            f"<font color=\"{'info' if alert_type == '装机正常' else 'warning'}\">{alert_type}</font>",
            "",
            f"客户名称：{shipper_unit}",
            f"运单号：{waybill_num}",
            f"开单航班/航程：{billing_flight} / {export.routing or '/'}",
            f"预飞时间：{task.planned_time}",
            f"制单数据：{export_qty} / {int(export_wt)}",
            f"过机数据：{sum_qty} / {int(sum_wt)} ({diff_qty} / {diff_wt})",
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
