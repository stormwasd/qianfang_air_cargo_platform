"""Persistent worker for KingGo direct Shenzhen Airlines waybill tasks."""
import asyncio
import json
import logging
import threading
import time
import traceback
from datetime import timedelta
from typing import Optional
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import SessionLocal
from app.models.waybill import (
    Waybill, ShenzhenAirDirectWaybillTask, ShenzhenAirDirectWaybillQueueLock,
    ShenzhenAirDirectWaybillTaskStatus as Status,
)
from app.models.settlement import Settlement
from app.services.shenzhen_air_direct_waybill import (
    ShenzhenAirDirectWaybillError, shenzhen_air_direct_waybill_service,
)
from app.utils.helpers import get_china_now

logger = logging.getLogger(__name__)


class ShenzhenAirDirectWaybillWorker:
    def __init__(self, index: int):
        self.index = index
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self._last_recovery = 0.0

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, name=f"shenzhen-direct-waybill-{self.index}", daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self.running:
                try:
                    if time.monotonic() - self._last_recovery > 60:
                        ShenzhenAirDirectWaybillWorkerManager.recover_stale_tasks()
                        self._last_recovery = time.monotonic()
                    handled = loop.run_until_complete(self.process_one())
                except Exception:
                    print(f"[Shenzhen Direct Waybill {self.index}] worker loop failed\n{traceback.format_exc()}")
                    handled = False
                if not handled:
                    loop.run_until_complete(asyncio.sleep(settings.SHENZHEN_AIR_DIRECT_WAYBILL_POLL_INTERVAL))
        finally:
            loop.close()

    @staticmethod
    def _claim():
        db = SessionLocal()
        try:
            # get_awb_no is not documented as reserving a number. Serialize the
            # shared account across threads/processes, holding this lock only
            # during claim, never during HAR replay or HTTP requests.
            gate = db.query(ShenzhenAirDirectWaybillQueueLock).filter_by(id=1).with_for_update().first()
            if gate is None:
                db.add(ShenzhenAirDirectWaybillQueueLock(id=1))
                try:
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    return None  # Another worker initialized the mutex.
                db.query(ShenzhenAirDirectWaybillQueueLock).filter_by(id=1).with_for_update().one()
            if db.query(ShenzhenAirDirectWaybillTask.id).filter(
                ShenzhenAirDirectWaybillTask.status == Status.RUNNING
            ).with_for_update().first():
                return None
            task = (db.query(ShenzhenAirDirectWaybillTask)
                    .filter(ShenzhenAirDirectWaybillTask.status == Status.PENDING)
                    .order_by(ShenzhenAirDirectWaybillTask.priority.desc(), ShenzhenAirDirectWaybillTask.created_at.asc())
                    .with_for_update().first())
            if task is None:
                return None
            task.status = Status.RUNNING
            task.started_at = get_china_now()
            db.commit()
            return task.id
        finally:
            db.close()

    async def process_one(self):
        task_id = self._claim()
        if task_id is None:
            return False
        db = SessionLocal()
        values = {}
        try:
            task = db.query(ShenzhenAirDirectWaybillTask).filter(ShenzhenAirDirectWaybillTask.id == task_id).first()
            waybill = db.query(Waybill).filter(Waybill.id == task.waybill_id).with_for_update().first()
            if waybill is None:
                raise RuntimeError("运单不存在")
            if waybill.airline_record_status != "1" or waybill.waybill_number:
                raise RuntimeError("运单已在执行或已有运单号，拒绝重复开单")
            snapshot = json.loads(task.request_data)
            form_data = snapshot["form_data"]
            values = snapshot["values"]
            waybill_id = waybill.id
            # Never hold a row lock or database connection while replaying HAR or
            # waiting for upstream requests. The immutable snapshot was enqueued
            # atomically with the waybill's running status.
            db.commit()
            db.close()
            result = await asyncio.wait_for(
                shenzhen_air_direct_waybill_service.create_waybill(
                    values, before_submit=lambda number: self._mark_submitting(task_id, number)
                ), timeout=1200,
            )
            task = db.query(ShenzhenAirDirectWaybillTask).filter_by(id=task_id).with_for_update().one()
            waybill = db.query(Waybill).filter_by(id=waybill_id).with_for_update().one()
            waybill.waybill_number = result["waybill_number"]
            waybill.airline_record_status = "3"
            waybill.airline_record_time = get_china_now()
            task.result = json.dumps(result, ensure_ascii=False)
            task.stage = "confirmed"
            task.status = Status.SUCCESS
            task.finished_at = get_china_now()
            db.commit()

            try:
                await self._after_success(db, waybill, form_data, result)
            except Exception as exc:
                # The upstream waybill is already committed. Post-processing must
                # never turn a confirmed creation into a retryable failure.
                db.rollback()
                task = db.query(ShenzhenAirDirectWaybillTask).filter_by(id=task_id).one()
                result["post_processing_error"] = f"开单已成功，后处理失败（{type(exc).__name__}），请检查制单和打印状态"
                task.result = json.dumps(result, ensure_ascii=False)
                db.commit()
            return True
        except Exception as exc:
            db.rollback()
            task = db.query(ShenzhenAirDirectWaybillTask).filter(ShenzhenAirDirectWaybillTask.id == task_id).first()
            waybill = db.query(Waybill).filter(Waybill.id == task.waybill_id).first() if task else None
            # Once the durable send boundary was crossed, even a local DB error
            # after upstream success must remain blocked for reconciliation.
            if task and task.status == Status.SUCCESS:
                return True
            unknown = bool(getattr(exc, "outcome_unknown", False)) or bool(task and task.stage == "submitting")
            message = str(exc) if isinstance(exc, ShenzhenAirDirectWaybillError) else f"深航直连开单异常（{type(exc).__name__}）"
            diagnostic = {
                "task_id": str(task_id), "waybill_id": str(task.waybill_id) if task else None,
                "task_stage": task.stage if task else None,
                "outcome_unknown": unknown, "error_type": type(exc).__name__,
                **shenzhen_air_direct_waybill_service.diagnostic_values(values),
                **(exc.details if isinstance(exc, ShenzhenAirDirectWaybillError) else {}),
            }
            diagnostic_json = json.dumps(diagnostic, ensure_ascii=False)
            if task:
                task.status = Status.UNKNOWN if unknown else Status.FAILED
                task.error_message = (("提交结果未知，请核查KingGo运单后再决定是否重试：" if unknown else "")
                                      + message + "；诊断=" + diagnostic_json)
                task.finished_at = get_china_now()
            if waybill:
                if waybill.airline_record_status == "1":
                    waybill.airline_record_status = "2"
            db.commit()
            logger.warning("[Shenzhen Direct Waybill %s] task=%s failed: %s；诊断=%s",
                           self.index, task_id, message, diagnostic_json)
            return True
        finally:
            db.close()

    @staticmethod
    def _mark_submitting(task_id: int, number: str):
        db = SessionLocal()
        try:
            task = db.query(ShenzhenAirDirectWaybillTask).filter_by(id=task_id).with_for_update().one()
            if task.status != Status.RUNNING or task.stage != "preparing":
                raise ShenzhenAirDirectWaybillError("任务状态已改变，拒绝提交运单")
            task.stage = "submitting"
            task.candidate_waybill_number = number
            db.commit()
        finally:
            db.close()

    async def _after_success(self, db, waybill: Waybill, form_data: dict, result: dict):
        from app.services.document_print_service import is_post_waybill_automation_enabled
        if not is_post_waybill_automation_enabled("1"):
            return
        flight = form_data.get("flight_info") or {}
        contacts = form_data.get("shipper_consignee_info") or {}
        cargo = form_data.get("cargo_info") or {}
        fees = form_data.get("other_fees") or {}
        settlement_data = {
            "airline_record_time": get_china_now().strftime("%Y-%m-%d"),
            "settlement_method": "1", "settlement_status": "0", "financial_review": "0",
            "master_airwaybill_number": waybill.waybill_number or "", "transport_method": "2", "airline": "1",
            "origin_station": flight.get("origin_station", ""), "destination": flight.get("destination", ""),
            "flight_number": flight.get("flight_number", ""), "flight_date": flight.get("flight_date", ""),
            "customer_name": contacts.get("shipper_unit", ""), "recipient_name": contacts.get("consignee_info", ""),
            "cargo_name": cargo.get("cargo_name", ""), "quantity": cargo.get("quantity", ""),
            "weight": cargo.get("weight", ""), "chargeable_weight": cargo.get("chargeable_weight", ""),
            "sub_rate": "", "sub_airline_fee": "", "sub_document_fee": "", "sub_telegraph_fee": "",
            "sub_telegraph_number": "", "sub_cca_fee": "", "sub_packaging_fee": fees.get("packaging_fee", ""),
            "sub_pickup_fee": fees.get("pickup_fee", ""), "sub_airport_pickup_fee": "",
            "sub_delivery_fee": fees.get("delivery_fee", ""), "sub_carrier_deduction": "", "sub_other_fee": "",
            "sub_other_fee_remark": "", "sub_total_amount": "", "sub_remark": "",
            "master_rate": str(result.get("aviation_rate", "")),
            "master_airline_fee": str(result.get("aviation_fee", "")),
            "master_fuel_surcharge": "", "master_transit_weight": "", "master_transit_fee": "",
            "master_cca_cost": "", "master_packaging_fee": "", "master_telegraph_fee": "",
            "master_pickup_unit": "", "master_pickup_fee": "", "master_delivery_unit": "",
            "master_airport_pickup_fee": "", "master_delivery_fee": str(result.get("delivery_fee", "")),
            "master_other_fee": "", "master_total_cost": "", "master_remark": "",
        }
        db.add(Settlement(form_data=json.dumps(settlement_data, ensure_ascii=False), waybill_void_status=waybill.waybill_void_status or "0"))
        db.commit()
        from app.services.rpa_worker import RPAWorker
        worker = RPAWorker(robot_db_id=0, robot_name="KingGo直连")
        await worker._auto_generate_cargo_station_documents(db, waybill, form_data)


class ShenzhenAirDirectWaybillWorkerManager:
    def __init__(self):
        self.workers = []

    def start_workers(self):
        if not settings.SHENZHEN_AIR_DIRECT_WAYBILL_QUEUE_ENABLED or self.workers:
            return
        self.recover_stale_tasks()
        for index in range(settings.SHENZHEN_AIR_DIRECT_WAYBILL_WORKER_COUNT):
            worker = ShenzhenAirDirectWaybillWorker(index + 1)
            worker.start()
            self.workers.append(worker)
        print(f"深航KingGo直连开单队列已启用，启动了 {len(self.workers)} 个Worker")

    def stop_workers(self):
        for worker in self.workers:
            worker.stop()
        self.workers.clear()

    @staticmethod
    def recover_stale_tasks():
        db = SessionLocal()
        try:
            threshold = get_china_now() - timedelta(minutes=30)
            stale = db.query(ShenzhenAirDirectWaybillTask).filter(
                ShenzhenAirDirectWaybillTask.status == Status.RUNNING,
                ShenzhenAirDirectWaybillTask.started_at < threshold,
            ).with_for_update(skip_locked=True).all()
            for task in stale:
                task.status = Status.UNKNOWN if task.stage == "submitting" else Status.FAILED
                task.error_message = ("任务执行中断，请按候选运单号核查KingGo，禁止直接重试"
                                      if task.stage == "submitting" else "任务执行中断，未发送提交请求，可重新开单")
                task.finished_at = get_china_now()
                waybill = db.query(Waybill).filter(Waybill.id == task.waybill_id).first()
                if waybill and waybill.airline_record_status != "3":
                    waybill.airline_record_status = "2"
            if stale:
                db.commit()
        finally:
            db.close()


shenzhen_air_direct_waybill_worker_manager = ShenzhenAirDirectWaybillWorkerManager()
