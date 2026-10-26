"""Timestamp persistence and list contracts, using a local database only."""
import unittest
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.china_southern_air_approval import get_china_southern_air_approvals
from app.api.departure_tracking import get_china_southern_air_departures, get_shenzhen_air_departures
from app.api.shenzhen_air_approval import get_shenzhen_air_approvals
from app.config import settings
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.config import BusinessConfig
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaProductInformation, CsaLalamoveInformation
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.rpa_task import RPATask, RPATaskLastSuccess, RPATaskType
from app.models.shenzhen_air_approval import ShenzhenAirApprovalData, ShenzhenAirApprovalWideBodyData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.services import tracking_execution_time as timestamps
from app.services.rpa_task_service import rpa_task_service


class TrackingExecutionTimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.engine = create_engine("sqlite:///" + str(Path(self.temp_dir.name) / "tracking.sqlite"))
        for model in (
            RPATask, RPATaskLastSuccess, BusinessConfig, ChinaSouthernAirApprovalData,
            CsaProductInformation, CsaLalamoveInformation, CsaDepartureManualData,
            ShenzhenAirBookingExport, ShenzhenAirBillingTimeContainer,
            ShenzhenAirDepartureManualData, ShenzhenAirApprovalData, ShenzhenAirApprovalWideBodyData,
        ):
            model.__table__.create(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.db = self.factory()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.factory_patch = patch.object(timestamps, "SessionLocal", self.factory)
        self.factory_patch.start()
        self.addCleanup(self.factory_patch.stop)
        self.now = datetime(2026, 10, 20, 18, 9, 0)
        self.clock_patch = patch.object(timestamps, "get_china_now", return_value=self.now)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

    def test_rpa_end_time_survives_legacy_completion_and_out_of_order_results(self):
        task_type = RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value
        key = timestamps.RPA_EXECUTION_SUCCESS_TYPES[task_type]
        self.db.add(RPATask(id=1, target_id=10, target_type="csa_dep_tracking",
                            task_type=task_type, params="{}", status="running"))
        self.db.commit()
        end = datetime(2026, 10, 20, 18, 2, 15)
        self.assertTrue(timestamps.record_rpa_execution_success(task_type, {"endTime": str(end)}))
        with patch("app.services.rpa_task_service.get_china_now", return_value=self.now):
            self.assertTrue(rpa_task_service.complete_task(self.db, 1, True))
        self.assertTrue(timestamps.record_rpa_execution_success(task_type, {"endTime": "2026-08-11 09:36:00"}))
        self.db.expire_all()
        self.assertEqual(self.db.get(RPATaskLastSuccess, key).last_success_at, end)
        self.assertEqual(self.db.get(RPATaskLastSuccess, task_type).last_success_at, self.now)
        self.assertIsNone(self.db.get(RPATask, 1))

    def test_offsets_and_naive_rpa_times_are_china_local(self):
        task_type = RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value
        key = timestamps.RPA_EXECUTION_SUCCESS_TYPES[task_type]
        for value in ("2026-10-20 18:02:15", "2026-10-20T10:02:15Z",
                      "2026-10-20T18:02:15+08:00"):
            with self.subTest(value=value):
                self.assertTrue(timestamps.record_rpa_execution_success(task_type, {"endTime": value}))
                self.db.expire_all()
                self.assertEqual(self.db.get(RPATaskLastSuccess, key).last_success_at,
                                 datetime(2026, 10, 20, 18, 2, 15))
        self.assertEqual(timestamps.format_success_time(datetime(2026, 10, 20, 10, 2, tzinfo=timezone.utc)),
                         "2026-10-20 18:02")

    def test_missing_or_invalid_rpa_end_uses_confirmation_time(self):
        task_type = RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA.value
        for value in (None, "", "not-a-time"):
            with self.subTest(value=value):
                self.assertTrue(timestamps.record_rpa_execution_success(task_type, {"endTime": value}))
                self.db.expire_all()
                self.assertEqual(self.db.get(RPATaskLastSuccess, timestamps.RPA_EXECUTION_SUCCESS_TYPES[task_type]).last_success_at, self.now)

    def test_timestamp_failure_is_nonfatal(self):
        with patch.object(timestamps, "SessionLocal", side_effect=RuntimeError("offline")):
            self.assertFalse(timestamps.record_success_time(timestamps.DIRECT_BILLING_SUCCESS_TYPE))

    def test_timestamp_writer_does_not_commit_pending_business_changes(self):
        self.db.add(ChinaSouthernAirApprovalData(id=99, flight_info="uncommitted"))
        self.assertTrue(timestamps.record_success_time(timestamps.DIRECT_BILLING_SUCCESS_TYPE))
        with self.factory() as observer:
            self.assertIsNone(observer.get(ChinaSouthernAirApprovalData, 99))
            self.assertIsNotNone(observer.get(RPATaskLastSuccess, timestamps.DIRECT_BILLING_SUCCESS_TYPE))
        self.db.rollback()

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_direct_approval_http_download_records_separate_report_times(self):
        from app.services.shenzhen_air_approval_scheduler import ShenzhenAirApprovalScheduler
        from app.services.shenzhen_air_direct_approval import ShenzhenAirDirectApprovalService

        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"
        client = ShenzhenAirDirectApprovalService(origin=origin, output_dir=self.temp_dir.name)

        async def auth(path, body):
            return client.ORIGIN + path + "?oOr6SIhu=local-test", {"Cookie": "local-test"}

        with patch.object(client, "_auth", side_effect=auth), patch(
            "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service", client
        ):
            await ShenzhenAirApprovalScheduler()._download_direct_exports()
        self.assertEqual(len(list(Path(self.temp_dir.name).glob("*.xlsx"))), 4)
        for key in timestamps.DIRECT_APPROVAL_SUCCESS_TYPES:
            self.assertEqual(self.db.get(RPATaskLastSuccess, key).last_success_at, self.now)

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_failed_direct_approval_http_requests_leave_success_time_unchanged(self):
        from app.services.shenzhen_air_approval_scheduler import ShenzhenAirApprovalScheduler
        from app.services.shenzhen_air_direct_approval import ShenzhenAirDirectApprovalService

        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"
        client = ShenzhenAirDirectApprovalService(origin=origin, output_dir=self.temp_dir.name)
        old = self.now.replace(hour=9)
        for key in timestamps.DIRECT_APPROVAL_SUCCESS_TYPES:
            self.assertTrue(timestamps.record_success_time(key, old))

        async def invalid_auth(path, body):
            # The HTTP fixture rejects missing signatures with status 400.
            return client.ORIGIN + path, {"Cookie": "local-test"}

        with patch.object(client, "_auth", side_effect=invalid_auth), patch(
            "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service", client
        ):
            await ShenzhenAirApprovalScheduler()._download_direct_exports()
        self.assertEqual(list(Path(self.temp_dir.name).glob("*.xlsx")), [])
        for key in timestamps.DIRECT_APPROVAL_SUCCESS_TYPES:
            self.assertEqual(self.db.get(RPATaskLastSuccess, key).last_success_at, old)

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_direct_billing_http_records_success_and_preserves_completion(self):
        from app.services.transit_loading_manager import TransitLoadingManager
        from app.services.shenzhen_air_direct_billing_time_container import ShenzhenAirDirectBillingTimeContainerService

        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"
        client = ShenzhenAirDirectBillingTimeContainerService(origin=origin)
        self.db.add(ShenzhenAirBookingExport(
            id=99, waybill_number="62134380", billing_flight="ZH9883",
            flight_date="2026-10-20", routing="SZX-HGH", departure_tracking_completed="0"))
        self.db.commit()
        with (
            patch.object(client, "_auth", AsyncMock(return_value=(client.ORIGIN + client.PATH + "?oOr6SIhu=local-test", {"Cookie": "local-test"}))),
            patch("app.services.shenzhen_air_direct_billing_time_container.shenzhen_air_direct_billing_time_container_service", client),
            patch("app.services.transit_loading_manager.SessionLocal", self.factory),
            patch("app.services.transit_loading_manager.get_china_now", return_value=self.now),
            patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_times.get_flight_times",
                  AsyncMock(return_value={"planned_time": "2026-10-20 18:00:00"})),
        ):
            await TransitLoadingManager()._process_direct_billing_time_container_records()
        self.db.expire_all()
        self.assertEqual(self.db.get(RPATaskLastSuccess, timestamps.DIRECT_BILLING_SUCCESS_TYPE).last_success_at, self.now)
        self.assertEqual(self.db.get(ShenzhenAirBookingExport, 99).departure_tracking_completed, "1")
        self.assertEqual(self.db.query(ShenzhenAirBillingTimeContainer).filter_by(booking_export_id=99).count(), 1)

    async def _download_transit_export(self, *, signed=True):
        from app.services.transit_loading_manager import TransitLoadingManager
        from app.services.shenzhen_air_direct_transit_loading import ShenzhenAirDirectTransitLoadingService

        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"
        client = ShenzhenAirDirectTransitLoadingService(origin=origin, output_dir=self.temp_dir.name)
        manager = TransitLoadingManager()
        manager.watch_dir = self.temp_dir.name
        signed_url = client.ORIGIN + client.EXPORT_PATH + ("?oOr6SIhu=local-test" if signed else "")
        with (
            patch.object(client, "_auth", AsyncMock(return_value=(signed_url, {"Cookie": "local-test"}))),
            patch("app.services.shenzhen_air_direct_transit_loading.shenzhen_air_direct_transit_loading_service", client),
            patch("app.services.shenzhen_air_direct_transit_loading.get_china_now", return_value=self.now),
            patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", "direct"),
        ):
            await manager._scan_and_enqueue_transit_loading()
        return manager

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_direct_main_export_download_import_and_list_use_its_success_time(self):
        old = datetime(2026, 10, 19, 15, 4)
        self.assertTrue(timestamps.record_success_time(timestamps.DIRECT_BILLING_SUCCESS_TYPE, old))
        manager = await self._download_transit_export()
        self.assertEqual(len(list(Path(self.temp_dir.name).glob("AwbQueryExport*.xlsx"))), 1)
        # Exercise the existing Excel reader and database mapping without invoking detail requests.
        with patch("app.services.transit_loading_manager.SessionLocal", self.factory), \
             patch.object(settings, "SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE", "direct"):
            await manager._check_for_new_files()
        self.db.expire_all()
        record = self.db.query(ShenzhenAirBookingExport).one()
        self.assertEqual(record.waybill_number, "62000001")
        self.assertEqual(record.creation_time, "2026-10-19 15:04:00")
        self.assertEqual(record.departure_tracking_completed, "0")
        self.assertEqual(self.db.query(ShenzhenAirBillingTimeContainer).count(), 0)
        self.assertEqual(len(list(Path(self.temp_dir.name).glob("*.xlsx.processed"))), 1)
        with patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", "direct"):
            response = await self._list("sz_departure")
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data_update_time"], "2026-10-20 18:09")
        self.assertEqual(self.db.get(RPATaskLastSuccess, timestamps.DIRECT_BILLING_SUCCESS_TYPE).last_success_at, old)

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_failed_direct_main_export_keeps_previous_success_time(self):
        key = timestamps.DIRECT_TRANSIT_LOADING_SUCCESS_TYPE
        old = datetime(2026, 10, 19, 15, 4)
        self.assertTrue(timestamps.record_success_time(key, old))
        await self._download_transit_export(signed=False)
        self.assertEqual(list(Path(self.temp_dir.name).glob("*.xlsx")), [])
        self.db.expire_all()
        self.assertEqual(self.db.get(RPATaskLastSuccess, key).last_success_at, old)

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local acquisition simulation required")
    async def test_main_export_timestamp_failure_does_not_abort_download(self):
        with patch.object(timestamps, "SessionLocal", side_effect=RuntimeError("timestamp store offline")):
            await self._download_transit_export()
        self.assertEqual(len(list(Path(self.temp_dir.name).glob("AwbQueryExport*.xlsx"))), 1)
        self.assertIsNone(self.db.get(RPATaskLastSuccess, timestamps.DIRECT_TRANSIT_LOADING_SUCCESS_TYPE))

    async def _list(self, name):
        common = dict(flight_date_start=None, flight_date_end=None, flight_number=None,
                      page=1, pageSize=10, current_user=None, db=self.db)
        if name == "sz_approval":
            return await get_shenzhen_air_approvals(cabin_type=0, **common)
        if name == "csa_approval":
            return await get_china_southern_air_approvals(waybill_number=None, **common)
        departure = dict(waybill_number=None, audit_status=None, origin=None, destination=None,
                         customer_name=None, is_suspected_abnormal=None, **common)
        if name == "sz_departure":
            return await get_shenzhen_air_departures(**departure)
        return await get_china_southern_air_departures(waybill_status=None, **departure)

    async def test_all_lists_expose_success_even_when_empty(self):
        keys = {
            "sz_approval": timestamps.DIRECT_APPROVAL_SUCCESS_TYPES[0],
            "sz_departure": timestamps.DIRECT_TRANSIT_LOADING_SUCCESS_TYPE,
            "csa_approval": timestamps.RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA.value],
            "csa_departure": timestamps.RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value],
        }
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "direct"), \
             patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", "direct"):
            for name, key in keys.items():
                with self.subTest(page=name):
                    self.assertTrue(timestamps.record_success_time(key, self.now))
                    response = await self._list(name)
                    self.assertEqual(response.data["items"], [])
                    self.assertEqual(response.data["total"], 0)
                    self.assertEqual(response.data["data_update_time"], "2026-10-20 18:09")

    async def test_all_lists_ignore_unrelated_old_times_and_manual_updates(self):
        self.db.add_all([
            ChinaSouthernAirApprovalData(id=1, flight_info="CZ1234 / 2026-10-20 / SZX - SHA", updated_at=self.now),
            ShenzhenAirBookingExport(id=2, updated_at=self.now),
            ShenzhenAirApprovalData(id=3, updated_at=self.now),
            ShenzhenAirBillingTimeContainer(id=4, booking_export_id=2, created_at=self.now),
        ])
        for task_type in timestamps.RPA_EXECUTION_SUCCESS_TYPES:
            self.db.add(RPATaskLastSuccess(task_type=task_type, last_success_at=self.now))
        self.db.commit()
        self.assertTrue(timestamps.record_success_time(timestamps.DIRECT_BILLING_SUCCESS_TYPE))
        self.assertTrue(timestamps.record_success_time(
            timestamps.RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.SHENZHEN_AIR_BILLING_TIME_CONTAINER.value]))
        for mode in ("direct", "rpa"):
            with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", mode), \
                 patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", mode):
                for name in ("sz_approval", "sz_departure", "csa_approval", "csa_departure"):
                    with self.subTest(mode=mode, page=name):
                        response = await self._list(name)
                        self.assertEqual(response.data["total"], 1)
                        self.assertIsNone(response.data["data_update_time"])

    async def test_shenzhen_departure_time_uses_main_export_mode_not_billing_mode(self):
        direct_key = timestamps.DIRECT_TRANSIT_LOADING_SUCCESS_TYPE
        rpa_key = timestamps.RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.SHENZHEN_AIR_TRANSIT_LOADING.value]
        direct_time = datetime(2026, 10, 27, 2, 1, 21)
        rpa_time = datetime(2026, 10, 27, 2, 5, 0)
        self.assertTrue(timestamps.record_success_time(direct_key, direct_time))
        self.assertTrue(timestamps.record_success_time(rpa_key, rpa_time))
        # A later detail request must not change the main export's time either.
        for key in (
            timestamps.DIRECT_BILLING_SUCCESS_TYPE,
            timestamps.RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.SHENZHEN_AIR_BILLING_TIME_CONTAINER.value],
        ):
            self.assertTrue(timestamps.record_success_time(key, datetime(2026, 10, 27, 3)))
        for mode, expected in (("direct", "2026-10-27 02:01"), ("rpa", "2026-10-27 02:05")):
            for detail_mode in ("direct", "rpa"):
                with self.subTest(mode=mode, detail_mode=detail_mode), \
                     patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", mode), \
                     patch.object(settings, "SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE", detail_mode):
                    response = await self._list("sz_departure")
                    self.assertEqual(response.data["data_update_time"], expected)

    async def test_rpa_modes_and_cabins_use_only_their_own_keys(self):
        for index, (task_type, key) in enumerate(timestamps.RPA_EXECUTION_SUCCESS_TYPES.items()):
            self.assertTrue(timestamps.record_success_time(key, self.now.replace(minute=index)))
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "rpa"), \
             patch.object(settings, "SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE", "rpa"):
            for name, minute in (("sz_approval", 0), ("sz_departure", 5), ("csa_approval", 3), ("csa_departure", 4)):
                response = await self._list(name)
                self.assertEqual(response.data["data_update_time"], f"2026-10-20 18:{minute:02d}")
            response = await get_shenzhen_air_approvals(
                flight_date_start=None, flight_date_end=None, flight_number=None,
                cabin_type=1, page=1, pageSize=10, current_user=None, db=self.db)
            self.assertEqual(response.data["data_update_time"], "2026-10-20 18:01")


if __name__ == "__main__":
    unittest.main()
