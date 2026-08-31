"""Persistent worker for China Southern direct booking tasks."""
import asyncio
import json
import threading
import traceback
from datetime import timedelta
from typing import Optional

from app.config import settings
from app.database import SessionLocal
from app.models.booking import Booking
from app.models.nanhang_token import NanHangToken
from app.models.rpa_task import RPATask, RPATaskStatus, RPATaskType
from app.utils.helpers import get_china_now


class DirectBookingWorker:
    def __init__(self, worker_index: int):
        self.worker_index = worker_index
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(
            target=self._run_loop,
            name=f"csa-direct-booking-{self.worker_index}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.running = False

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while self.running:
                try:
                    handled = loop.run_until_complete(self._process_one())
                except Exception:
                    print(f"[CSA Direct Worker {self.worker_index}] loop error\n{traceback.format_exc()}")
                    handled = False
                if not handled:
                    loop.run_until_complete(asyncio.sleep(settings.CHINA_SOUTHERN_AIR_DIRECT_BOOKING_POLL_INTERVAL))
        finally:
            loop.close()

    def _claim_task(self):
        db = SessionLocal()
        try:
            task = (
                db.query(RPATask)
                .filter(
                    RPATask.task_type == RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_BOOKING_EXECUTE.value,
                    RPATask.status == RPATaskStatus.PENDING.value,
                )
                .order_by(RPATask.priority.desc(), RPATask.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )
            if task is None:
                return None
            task.status = RPATaskStatus.RUNNING.value
            task.started_at = get_china_now()
            db.commit()
            return task.id
        finally:
            db.close()

    async def _process_one(self) -> bool:
        task_id = self._claim_task()
        if task_id is None:
            return False
        db = SessionLocal()
        task = None
        try:
            task = db.query(RPATask).filter(RPATask.id == task_id).first()
            if task is None:
                return True
            params = json.loads(task.params or "{}")
            booking_id = int(params["booking_id"])
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if booking is None:
                raise RuntimeError("订舱不存在")
            if booking.booking_status not in {"0", "1", "2"}:
                raise RuntimeError("该订舱正在执行或已订舱成功，不能重复提交")
            form_data = json.loads(booking.form_data)

            # Runtime import avoids the API/worker import cycle.
            from app.api.bookings import (
                _execute_china_southern_air_direct_booking,
                _fill_missing_china_southern_air_cargo_type_codes,
                _get_business_config,
            )
            _fill_missing_china_southern_air_cargo_type_codes(form_data, db)
            original_form_data = json.loads(booking.form_data)
            if form_data != original_form_data:
                booking.form_data = json.dumps(form_data, ensure_ascii=False)
                db.commit()

            config = _get_business_config(db)
            if not config:
                task.error_message = "业务参数配置不存在，等待配置后重试"
                task.status = RPATaskStatus.PENDING.value
                task.started_at = None
                db.commit()
                return True
            token = (
                db.query(NanHangToken)
                .filter(NanHangToken.token.isnot(None), NanHangToken.token != "")
                .order_by(NanHangToken.updated_at.desc(), NanHangToken.id.desc())
                .first()
            )
            if token is None:
                task.error_message = "暂无可用的南航 Token，等待Token刷新后重试"
                task.status = RPATaskStatus.PENDING.value
                task.started_at = None
                db.commit()
                return True

            await _execute_china_southern_air_direct_booking(
                db, booking_id=booking_id, form_data=form_data,
                business_config=config, token=token.token,
            )
            task.result = json.dumps({"booking_id": str(booking_id)}, ensure_ascii=False)
            task.status = RPATaskStatus.SUCCESS.value
            task.finished_at = get_china_now()
            task.error_message = None
            db.commit()
        except Exception as exc:
            db.rollback()
            message = getattr(exc, "detail", None) or str(exc) or repr(exc)
            booking_id = None
            try:
                booking_id = int(json.loads((task.params if task else "{}") or "{}").get("booking_id"))
            except Exception:
                pass
            if booking_id:
                booking = db.query(Booking).filter(Booking.id == booking_id).first()
                if booking and booking.booking_status != "3":
                    booking.booking_status = "2"
                    booking.booking_feedback = message[:255]
            task = db.query(RPATask).filter(RPATask.id == task_id).first()
            if task:
                task.status = RPATaskStatus.FAILED.value
                task.error_message = message[:4000]
                details = getattr(exc, "details", None)
                if details is not None:
                    task.result = json.dumps({"error_details": details}, ensure_ascii=False, default=str)
                task.finished_at = get_china_now()
                db.commit()
            print(f"[CSA Direct Worker {self.worker_index}] task {task_id} failed: {message}")
        finally:
            db.close()
        return True


class DirectBookingWorkerManager:
    def __init__(self):
        self.workers = []

    def start_workers(self) -> None:
        if not settings.CHINA_SOUTHERN_AIR_DIRECT_BOOKING_QUEUE_ENABLED or self.workers:
            return
        self.recover_stale_tasks()
        for index in range(settings.CHINA_SOUTHERN_AIR_DIRECT_BOOKING_WORKER_COUNT):
            worker = DirectBookingWorker(index + 1)
            worker.start()
            self.workers.append(worker)
        print(f"南航直连订舱队列已启用，启动了 {len(self.workers)} 个Worker")

    def stop_workers(self) -> None:
        for worker in self.workers:
            worker.stop()
        self.workers.clear()

    def recover_stale_tasks(self) -> None:
        """Mark stale running tasks as uncertain after a process restart.

        A running task may already have reached ``createOrder``.  Retrying it
        automatically could create a duplicate airline order, so recovery is
        deliberately conservative and requires an operator check.  A grace
        window prevents one healthy application instance from touching a task
        currently being processed by another instance.
        """
        db = SessionLocal()
        try:
            threshold = get_china_now() - timedelta(minutes=30)
            stale = db.query(RPATask).filter(
                RPATask.task_type == RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_BOOKING_EXECUTE.value,
                RPATask.status == RPATaskStatus.RUNNING.value,
                RPATask.started_at < threshold,
            ).all()
            for task in stale:
                task.status = RPATaskStatus.FAILED.value
                task.error_message = "服务重启后任务执行结果不确定，请核查南航订单后再重试"
                task.finished_at = get_china_now()
                try:
                    booking_id = int(json.loads(task.params or "{}")["booking_id"])
                    booking = db.query(Booking).filter(Booking.id == booking_id).first()
                    if booking and booking.booking_status != "3":
                        booking.booking_status = "2"
                        booking.booking_feedback = task.error_message[:255]
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass
            if stale:
                db.commit()
        finally:
            db.close()


direct_booking_worker_manager = DirectBookingWorkerManager()
