"""逐单走货明细限速：真实管理器及 SQLite，本地时间/HTTP 依赖。"""
from contextlib import ExitStack
from datetime import timedelta
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings, settings
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.rpa_task import RPATask
from app.models.transit_loading import ShenzhenAirBookingExport
from app.services import transit_loading_manager as manager_module
from app.services import shenzhen_air_billing_time_container_processor as processor
from app.services.shenzhen_air_direct_billing_time_container import (
    ShenzhenAirDirectBillingTimeContainerError,
    ShenzhenAirDirectBillingTimeContainerService,
)
from app.services.shenzhen_air_flight_times import shenzhen_air_flight_times
from app.utils.helpers import get_china_now


class BillingRequestIntervalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        for model in (ShenzhenAirBookingExport, ShenzhenAirBillingTimeContainer, RPATask):
            model.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.manager = manager_module.TransitLoadingManager()
        self.now = get_china_now()
        self.clock = 0.0
        self.starts = []
        self.sleeps = []
        self.stop_during_wait = False
        self.failures = set()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(manager_module, "SessionLocal", self.Session))
        self.stack.enter_context(patch.object(manager_module, "get_china_now", return_value=self.now))
        self.stack.enter_context(patch.object(manager_module, "time", SimpleNamespace(monotonic=lambda: self.clock)))
        self.stack.enter_context(patch.object(manager_module, "asyncio", SimpleNamespace(sleep=self.sleep)))
        self.stack.enter_context(patch.object(settings, "SHENZHEN_AIR_BILLING_TIME_CONTAINER_REQUEST_INTERVAL_SECONDS", 5.0))
        self.stack.enter_context(patch.object(shenzhen_air_flight_times, "get_flight_times", new=AsyncMock(side_effect=self.flight_times)))
        self.stack.enter_context(patch("app.services.tracking_execution_time.record_success_time"))
        self.stack.enter_context(patch(
            "app.services.shenzhen_air_direct_billing_time_container.shenzhen_air_direct_billing_time_container_service.fetch_rows",
            new=AsyncMock(side_effect=self.fetch),
        ))

    async def sleep(self, delay):
        self.sleeps.append(delay)
        self.clock += delay
        if self.stop_during_wait:
            self.manager.stop()

    async def flight_times(self, flight, *_args, **_kwargs):
        if flight == "MISSING":
            return None
        planned = self.now + timedelta(hours=4) if flight == "FUTURE" else self.now
        return {"planned_time": planned.isoformat(), "actual_time": None}

    def rows(self):
        return [["1", "ZH9883", self.now.date().isoformat(), "0930", "SZX", "HGH", "1", "5", "SYNTHETIC"]]

    async def fetch(self, awb, _routing, _day):
        self.starts.append((awb, self.clock))
        self.clock += 2.0  # Simulate two seconds of request/parse time.
        if awb in self.failures:
            raise ShenzhenAirDirectBillingTimeContainerError("synthetic network failure")
        return self.rows()

    def add_records(self, *flights):
        with self.Session() as db:
            for index, flight in enumerate(flights, start=1):
                db.add(ShenzhenAirBookingExport(
                    id=index, waybill_number=f"{index:08}", billing_flight=flight,
                    flight_date=self.now.date().isoformat(), routing="SZX-HGH",
                    departure_tracking_completed="0",
                ))
            db.commit()

    async def run_batch(self):
        await self.manager._process_direct_billing_time_container_records()

    async def test_success_waits_after_completion_without_delaying_first_or_last(self):
        self.add_records("ZH9883", "ZH9883", "ZH9883")
        await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 7, 14])
        self.assertEqual(sum(self.sleeps), 10)
        self.assertEqual(self.clock, 16)
        with self.Session() as db:
            self.assertEqual(db.query(ShenzhenAirBookingExport).filter_by(departure_tracking_completed="1").count(), 3)
            self.assertEqual(db.query(ShenzhenAirBillingTimeContainer).count(), 3)
            self.assertEqual(db.query(RPATask).count(), 0)

    async def test_failed_request_still_delays_next_and_keeps_failed_record_incomplete(self):
        self.add_records("ZH9883", "ZH9883")
        self.failures.add("00000001")
        await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 7])
        with self.Session() as db:
            self.assertEqual(db.get(ShenzhenAirBookingExport, 1).departure_tracking_completed, "0")
            self.assertEqual(db.get(ShenzhenAirBookingExport, 2).departure_tracking_completed, "1")

    async def test_interval_survives_next_batch_after_failure(self):
        self.add_records("ZH9883")
        self.failures.add("00000001")
        await self.run_batch()
        await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 7])

    async def test_skipped_records_do_not_consume_interval(self):
        self.add_records("", "MISSING", "FUTURE", "ZH9883")
        await self.run_batch()
        self.assertEqual(self.starts, [("00000004", 0)])
        self.assertEqual(self.sleeps, [])

    async def test_processing_time_counts_towards_interval(self):
        self.add_records("ZH9883", "ZH9883")
        persist = processor.persist_shenzhen_air_billing_rows
        async def slower_persist(*args):
            self.clock += 6
            return await persist(*args)
        with patch.object(processor, "persist_shenzhen_air_billing_rows", new=slower_persist):
            await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 8])
        self.assertEqual(self.sleeps, [])

    async def test_zero_disables_extra_wait(self):
        self.add_records("ZH9883", "ZH9883")
        with patch.object(settings, "SHENZHEN_AIR_BILLING_TIME_CONTAINER_REQUEST_INTERVAL_SECONDS", 0):
            await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 2])
        self.assertEqual(self.sleeps, [])

    async def test_stop_during_wait_prevents_next_request(self):
        self.add_records("ZH9883", "ZH9883")
        self.stop_during_wait = True
        await self.run_batch()
        self.assertEqual(len(self.starts), 1)
        self.assertEqual(self.sleeps, [1.0])

    async def test_stopped_manager_never_requests(self):
        self.add_records("ZH9883")
        self.manager.stop()
        await self.run_batch()
        self.assertEqual(self.starts, [])

    def test_interval_setting_supports_environment_and_validates_bounds(self):
        key = "SHENZHEN_AIR_BILLING_TIME_CONTAINER_REQUEST_INTERVAL_SECONDS"
        self.assertEqual(Settings.model_fields[key].default, 5.0)
        with patch.dict(os.environ, {key: "0.25"}):
            self.assertEqual(getattr(Settings(_env_file=None), key), 0.25)
        for invalid in (-1, 3601, "nan", "inf"):
            with self.subTest(value=invalid), self.assertRaises(ValidationError):
                Settings(_env_file=None, **{key: invalid})

    @unittest.skipUnless(os.environ.get("KINGGO_SIMULATION_URL"), "Local KingGo simulation required")
    async def test_real_http_requests_observe_completion_based_interval(self):
        self.add_records("ZH9883", "ZH9883")
        service = ShenzhenAirDirectBillingTimeContainerService(origin=os.environ["KINGGO_SIMULATION_URL"])
        async def auth(path):
            return "https://www.kinggo.com" + path + "&oOr6SIhu=synthetic", {"Cookie": "synthetic"}
        service._auth = AsyncMock(side_effect=auth)
        async def real_fetch(awb, routing, day):
            self.starts.append((awb, self.clock))
            return await service.fetch_rows(awb, routing, day)
        # The HTTP mock returns a fixed date; time lookup is isolated from KingGo here.
        with patch(
            "app.services.shenzhen_air_direct_billing_time_container.shenzhen_air_direct_billing_time_container_service.fetch_rows",
            new=real_fetch,
        ):
            await self.run_batch()
        self.assertEqual([start for _, start in self.starts], [0, 5])
        with self.Session() as db:
            self.assertEqual(db.query(ShenzhenAirBookingExport).filter_by(departure_tracking_completed="1").count(), 2)
            self.assertEqual(db.query(ShenzhenAirBillingTimeContainer).count(), 2)
