"""Detail flights own their actual times, independently of the parent flight."""
import os
import json
import unittest
from contextlib import asynccontextmanager
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.departure_tracking import get_shenzhen_air_departures
from app.config import settings
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer as Detail
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.rpa_task import RPATask, RPATaskLastSuccess
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo as Flight
from app.models.transit_loading import ShenzhenAirBookingExport as Export
from app.services.departure_actual_time_sync import DepartureActualTimeSync
from app.services.shenzhen_air_billing_time_container_processor import persist_shenzhen_air_billing_rows
from app.services.shenzhen_air_flight_times import shenzhen_air_flight_times
from app.services.transit_loading_manager import TransitLoadingManager
from app.utils.ctrip_client import CtripClient


DAY = date(2026, 10, 19)
NOW = datetime(2026, 10, 19, 14, 0)


def cargo_row(flight="ZH9883", day="2026-10-19", destination="杭州", sequence="1"):
    return [sequence, flight, day, "0930", "SZX", destination, "1", "5.0", "ZH7298"]


class DetailActualTimeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (Detail, Flight, Export, RPATask, RPATaskLastSuccess, ShenzhenAirDepartureManualData):
            model.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add(Export(id=10, waybill_number="62201856", flight_date=DAY.isoformat(),
                           billing_flight="ZH8985", actual_flight=None, routing="SZX-YBP"))
        self.db.commit()
        self.enterContext(patch.object(settings, "SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED", True))
        self.enterContext(patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", False))
        self.enterContext(patch("app.services.shenzhen_air_flight_times.SessionLocal", self.Session))
        self.enterContext(patch("app.services.departure_actual_time_sync.SessionLocal", self.Session))
        self.enterContext(patch("app.services.departure_actual_time_sync.get_china_now", return_value=NOW))
        self.enterContext(patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh",
                                AsyncMock(return_value=True)))

    def add_flight(self, flight="ZH9883", day=DAY, origin="SZX", destination="HGH", actual="0945"):
        self.db.add(Flight(flight_date=day, flight_number=flight, origin=origin,
                           destination=destination, takeoff_time="0930", actual_departure_time=actual))
        self.db.commit()

    async def test_each_detail_flight_and_date_are_saved_and_returned_by_list(self):
        self.add_flight()
        self.add_flight("ZH9884", actual="1010")
        self.add_flight(day=date(2026, 10, 20), actual="1100")
        rows = [cargo_row(), cargo_row(sequence="2"), cargo_row("ZH9884", sequence="3"),
                cargo_row(day="2026-10-20", sequence="4")]
        with patch.object(shenzhen_air_flight_times, "get_flight_times",
                          wraps=shenzhen_air_flight_times.get_flight_times) as lookup:
            result = await persist_shenzhen_air_billing_rows(self.db, rows, "62201856", 10)
        self.assertEqual(result.inserted_count, 4)
        self.assertEqual(lookup.call_count, 3)  # Two containers on one flight share the lookup.
        details = self.db.query(Detail).order_by(Detail.sequence).all()
        self.assertEqual([row.actual_time for row in details], ["2026-10-19 09:45:00"] * 2 +
                         ["2026-10-19 10:10:00", "2026-10-20 11:00:00"])
        response = await get_shenzhen_air_departures(
            page=1, pageSize=20, flight_number=None, flight_date_start=None, flight_date_end=None,
            waybill_number="62201856", origin=None, destination=None, audit_status=None,
            customer_name=None, is_suspected_abnormal=False, db=self.db, current_user=None,
        )
        returned = response.data["items"][0]["billing_time_containers"]
        self.assertEqual({row["id"]: row["actual_time"] for row in returned},
                         {str(row.id): row.actual_time for row in details})

    async def test_pending_actual_is_filled_even_after_http_retries_exhausted(self):
        self.add_flight(actual=None)
        await persist_shenzhen_air_billing_rows(self.db, [cargo_row()], "62201856", 10)
        row = self.db.query(Detail).one()
        self.assertIsNone(row.actual_time)
        row.actual_time_attempts = "100"
        row.next_actual_time_query_at = datetime(2026, 11, 1)
        self.db.query(Flight).update({Flight.actual_departure_time: "0950"})
        self.db.commit()
        with patch.object(shenzhen_air_flight_times, "get_flight_times", AsyncMock()) as network:
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(row.actual_time, "2026-10-19 09:50:00")
        self.assertEqual(row.actual_time_attempts, "100")
        self.assertIsNone(row.next_actual_time_query_at)
        network.assert_not_awaited()

    async def test_mixed_identifier_details_receive_local_actuals_without_cross_matching(self):
        self.add_flight("ZHT2F8", destination="SZX", actual="0950")
        self.add_flight("ZH30CU", destination="SZX", actual="1010")
        # Retaining the full identifier prevents collisions with ordinary flights.
        self.add_flight("ZH30", destination="SZX", actual="1100")
        for row_id, flight, day, destination in (
            (1, " zht2f8 ", DAY.isoformat(), "SZX"),
            (2, "ZH30CU", DAY.isoformat(), "SZX"),
            (3, "ZH30", DAY.isoformat(), "SZX"),
            (4, "ZHT2F8", "2026-10-20", "SZX"),
            (5, "ZH30CU", DAY.isoformat(), "HGH"),
        ):
            self.db.add(Detail(id=row_id, booking_export_id=10, flight_number=flight,
                               flight_date=day, origin="SZX", destination=destination,
                               actual_time_attempts="100"))
        self.db.commit()
        with patch.object(shenzhen_air_flight_times, "get_flight_times", AsyncMock()) as network:
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual([self.db.get(Detail, i).actual_time for i in range(1, 6)], [
            "2026-10-19 09:50:00", "2026-10-19 10:10:00", "2026-10-19 11:00:00", None, None,
        ])
        network.assert_not_awaited()

    async def test_local_lookup_requires_matching_day_and_segment(self):
        self.add_flight()
        for row_id, day, destination in [(1, "2026-10-19", "杭州"), (2, "2026-10-20", "杭州"),
                                         (3, "2026-10-19", "宜宾")]:
            self.db.add(Detail(id=row_id, booking_export_id=10, flight_number="ZH9883", flight_date=day,
                               origin="SZX", destination=destination, actual_time_attempts="100"))
        self.db.commit()
        await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(self.db.get(Detail, 1).actual_time, "2026-10-19 09:45:00")
        self.assertIsNone(self.db.get(Detail, 2).actual_time)
        self.assertIsNone(self.db.get(Detail, 3).actual_time)

    async def test_local_lookup_rotates_past_unresolved_rows_and_does_not_overwrite(self):
        self.add_flight()
        for row_id in (1, 2, 3):
            self.db.add(Detail(id=row_id, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                               origin="SZX", destination="YBP" if row_id == 1 else "HGH",
                               actual_time="2026-10-19 09:40:00" if row_id == 3 else None,
                               actual_time_attempts="100"))
        self.db.commit()
        sync = DepartureActualTimeSync()
        sync.BATCH_SIZE = 1
        await sync._sync_shenzhen()
        await sync._sync_shenzhen()
        self.db.expire_all()
        self.assertIsNone(self.db.get(Detail, 1).actual_time)
        self.assertEqual(self.db.get(Detail, 2).actual_time, "2026-10-19 09:45:00")
        self.assertEqual(self.db.get(Detail, 3).actual_time, "2026-10-19 09:40:00")

    async def test_local_actual_needs_no_planned_time_and_handles_midnight(self):
        self.add_flight()
        flight = self.db.query(Flight).one()
        flight.takeoff_time = None
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="HGH", actual_time_attempts="100"))
        self.db.commit()
        sync = DepartureActualTimeSync()
        await sync._sync_shenzhen()
        self.db.expire_all()
        row = self.db.get(Detail, 1)
        self.assertEqual(row.actual_time, "2026-10-19 09:45:00")
        self.assertIsNone(row.planned_time)
        row.actual_time = None
        flight.takeoff_time = "2330"
        flight.actual_departure_time = "0020"
        self.db.commit()
        await sync._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(row.actual_time, "2026-10-20 00:20:00")

    async def test_local_backfill_preserves_time_written_during_lookup(self):
        self.add_flight()
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="HGH", actual_time_attempts="100"))
        self.db.commit()
        lookup = shenzhen_air_flight_times.get_stored_times_for_details

        def lookup_with_concurrent_write(db, details):
            result = lookup(db, details)
            with self.Session() as concurrent:
                concurrent.query(Detail).filter_by(id=1).update({
                    Detail.actual_time: "2026-10-19 09:50:00",
                    Detail.planned_time: "2026-10-19 09:35:00",
                }, synchronize_session=False)
                concurrent.commit()
            return result

        with patch.object(shenzhen_air_flight_times, "get_stored_times_for_details",
                          side_effect=lookup_with_concurrent_write):
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(self.db.get(Detail, 1).actual_time, "2026-10-19 09:50:00")
        self.assertEqual(self.db.get(Detail, 1).planned_time, "2026-10-19 09:35:00")

    async def test_local_backfill_preserves_planned_time_written_during_lookup(self):
        self.add_flight()
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="HGH", actual_time_attempts="100"))
        self.db.commit()
        lookup = shenzhen_air_flight_times.get_stored_times_for_details

        def lookup_with_concurrent_write(db, details):
            result = lookup(db, details)
            with self.Session() as concurrent:
                concurrent.query(Detail).filter_by(id=1).update({
                    Detail.planned_time: "2026-10-19 09:35:00",
                }, synchronize_session=False)
                concurrent.commit()
            return result

        with patch.object(shenzhen_air_flight_times, "get_stored_times_for_details",
                          side_effect=lookup_with_concurrent_write):
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(self.db.get(Detail, 1).actual_time, "2026-10-19 09:45:00")
        self.assertEqual(self.db.get(Detail, 1).planned_time, "2026-10-19 09:35:00")

    async def test_disabled_kinggo_does_not_backfill_from_stored_table(self):
        self.add_flight()
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="HGH", actual_time_attempts="100"))
        self.db.commit()
        with patch.object(settings, "SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED", False):
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertIsNone(self.db.get(Detail, 1).actual_time)

    async def test_ambiguous_city_is_not_matched_to_arbitrary_airport(self):
        self.add_flight(destination="AAA")
        self.add_flight(destination="BBB", actual="1000")
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="同名城市", actual_time_attempts="100"))
        self.db.commit()
        with patch.dict("app.services.shenzhen_air_flight_times.AIRPORT_CODE_TO_CITY",
                        {"AAA": "同名城市", "BBB": "同名城市"}):
            await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertIsNone(self.db.get(Detail, 1).actual_time)

    async def test_preallocation_and_upstream_failure_do_not_discard_cargo_rows(self):
        with patch.object(shenzhen_air_flight_times, "get_flight_times", AsyncMock(return_value=None)):
            result = await persist_shenzhen_air_billing_rows(
                self.db, [cargo_row(flight=""), cargo_row(sequence="2")], "62201856", 10)
        self.assertEqual(result.inserted_count, 2)
        self.assertTrue(result.has_invalid_flight)
        rows = self.db.query(Detail).all()
        self.assertTrue(all(row.actual_time is None for row in rows))
        self.assertTrue(all(row.quantity == "1" and row.weight == "5.0" for row in rows))

    async def test_reimport_does_not_erase_resolved_actual_on_lookup_failure(self):
        self.add_flight()
        await persist_shenzhen_air_billing_rows(self.db, [cargo_row()], "62201856", 10)
        with patch.object(shenzhen_air_flight_times, "get_flight_times",
                          AsyncMock(side_effect=RuntimeError("upstream unavailable"))):
            await persist_shenzhen_air_billing_rows(self.db, [cargo_row(), cargo_row("ZH9884", sequence="2")],
                                                  "62201856", 10)
        details = self.db.query(Detail).order_by(Detail.sequence).all()
        self.assertEqual(details[0].actual_time, "2026-10-19 09:45:00")
        self.assertIsNone(details[1].actual_time)

    async def test_missing_export_cannot_replace_existing_details(self):
        self.db.add(Detail(booking_export_id=10, waybill_number_8="62201856", container="KEEP"))
        self.db.commit()
        for waybill in ("62201856", ""):
            with self.subTest(waybill=waybill), self.assertRaises(ValueError):
                await persist_shenzhen_air_billing_rows(self.db, [cargo_row()], waybill, None)
        self.assertEqual(self.db.query(Detail).one().container, "KEEP")

    async def test_direct_and_rpa_schedulers_use_billing_flight_even_without_actual_flight(self):
        manager = TransitLoadingManager()
        with patch("app.services.transit_loading_manager.SessionLocal", self.Session), \
             patch("app.services.transit_loading_manager.get_china_now", return_value=NOW), \
             patch.object(shenzhen_air_flight_times, "get_flight_times",
                          AsyncMock(return_value={"planned_time": "2026-10-19 19:45:00"})) as lookup, \
             patch("app.services.shenzhen_air_direct_billing_time_container.shenzhen_air_direct_billing_time_container_service.fetch_rows",
                   AsyncMock()) as fetch:
            for actual_flight in (None, "ZH9999"):
                parent = self.db.get(Export, 10)
                parent.actual_flight = actual_flight
                self.db.commit()
                await manager._process_direct_billing_time_container_records()
                lookup.assert_awaited_with("ZH8985", DAY.isoformat(), "SZX-YBP", required_times=("planned_time",))
                fetch.assert_not_awaited()  # 18:00 threshold is still respected.
                await manager._enqueue_billing_time_task(self.db, parent, "test-account")
                lookup.assert_awaited_with("ZH8985", DAY.isoformat(), "SZX-YBP", required_times=("planned_time",))
                task = self.db.query(RPATask).one()
                self.assertEqual(task.scheduled_at, datetime(2026, 10, 19, 18, 0))
                self.db.delete(task)
                self.db.commit()

    async def test_direct_due_record_without_parent_actual_flight_fetches_detail_and_saves_own_actual(self):
        self.add_flight("ZH8985", destination="YBP", actual=None)
        self.add_flight()
        with patch("app.services.transit_loading_manager.SessionLocal", self.Session), \
             patch("app.services.transit_loading_manager.get_china_now", return_value=NOW), \
             patch("app.services.tracking_execution_time.record_success_time"), \
             patch("app.services.shenzhen_air_direct_billing_time_container.shenzhen_air_direct_billing_time_container_service.fetch_rows",
                   AsyncMock(return_value=[cargo_row()])) as fetch:
            await TransitLoadingManager()._process_direct_billing_time_container_records()
        fetch.assert_awaited_once_with("62201856", "SZX-YBP", DAY.isoformat())
        self.db.expire_all()
        self.assertEqual(self.db.get(Export, 10).departure_tracking_completed, "1")
        row = self.db.query(Detail).one()
        self.assertEqual(row.flight_number, "ZH9883")
        self.assertEqual(row.actual_time, "2026-10-19 09:45:00")

    async def test_planned_time_compensation_keeps_actual_even_when_planned_is_unavailable(self):
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                           origin="SZX", destination="HGH", actual_time_attempts="0"))
        self.db.commit()
        with patch.object(shenzhen_air_flight_times, "get_flight_times",
                          AsyncMock(return_value={"actual_time": "2026-10-19 09:45:00"})) as lookup:
            await DepartureActualTimeSync()._sync_shenzhen()
        lookup.assert_awaited_once()
        self.db.expire_all()
        self.assertEqual(self.db.get(Detail, 1).actual_time, "2026-10-19 09:45:00")

    async def test_background_lookup_preserves_times_written_while_awaiting_response(self):
        for planned in (None, "2026-10-19 09:30:00"):
            with self.subTest(planned=planned):
                self.db.query(Detail).delete(synchronize_session=False)
                self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9883", flight_date=DAY.isoformat(),
                                   origin="SZX", destination="HGH", planned_time=planned, actual_time_attempts="0"))
                self.db.commit()

                async def lookup_with_concurrent_write(*args, **kwargs):
                    with self.Session() as concurrent:
                        concurrent.query(Detail).filter_by(id=1).update({
                            Detail.actual_time: "2026-10-19 09:50:00",
                            Detail.planned_time: "2026-10-19 09:35:00",
                            Detail.next_actual_time_query_at: None,
                        }, synchronize_session=False)
                        concurrent.commit()
                    return {"actual_time": "2026-10-19 09:45:00", "planned_time": "2026-10-19 09:30:00"}

                with patch.object(shenzhen_air_flight_times, "get_flight_times",
                                  AsyncMock(side_effect=lookup_with_concurrent_write)) as lookup:
                    await DepartureActualTimeSync()._sync_shenzhen()
                lookup.assert_awaited_once()
                self.db.expire_all()
                self.assertEqual(self.db.get(Detail, 1).actual_time, "2026-10-19 09:50:00")
                self.assertEqual(self.db.get(Detail, 1).planned_time, "2026-10-19 09:35:00")
                self.assertIsNone(self.db.get(Detail, 1).next_actual_time_query_at)

    async def test_rpa_queue_and_direct_worker_save_actual_times(self):
        from app.services.rpa_worker import RPAWorker
        self.add_flight()
        worker = RPAWorker(1, "test")
        for mode in ("direct", "rpa"):
            task = RPATask(id=20, task_type="SHENZHEN_AIR_BILLING_TIME_CONTAINER", target_type="booking_export",
                           target_id=10, params='{"waybill_number_8":"62201856"}', status="running")
            self.db.add(task)
            self.db.commit()
            if mode == "direct":
                await worker._persist_shenzhen_air_billing_rows(self.db, task, [cargo_row()], "62201856", 10)
            else:
                with patch("app.services.rpa_worker.rpa_service.consume_queue_data", AsyncMock(return_value=[cargo_row()])), \
                     patch.object(worker, "_cleanup_queues", AsyncMock()):
                    await worker._handle_shenzhen_air_billing_time_container_success(
                        self.db, task, {"billing_time_container": {"queueUUID": "test"}})
            self.db.expire_all()
            self.assertEqual(self.db.query(Detail).one().actual_time, "2026-10-19 09:45:00")
            # Successful tasks are deleted by the existing queue service.
            self.assertIsNone(self.db.get(RPATask, 20))
            self.assertEqual(self.db.get(Export, 10).departure_tracking_completed, "1")

    @asynccontextmanager
    async def ctrip_simulation(self):
        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/ctrip"
        requests = []

        async def route_to_local_mock(request):
            # Preserve the real GUID/payload/client path, rewriting only its
            # destination to the local HTTP simulation. Never contact Ctrip.
            self.assertEqual(request.url.host, "m.ctrip.com")
            if request.method == "POST":
                requests.append(json.loads(request.content)["fltItem"])
            request.url = httpx.URL(origin + request.url.path).copy_with(query=request.url.query)

        client = CtripClient(proxy_enabled=False)
        async with httpx.AsyncClient(event_hooks={"request": [route_to_local_mock]}, trust_env=False) as http:
            with patch.object(client, "_get_client", return_value=http), \
                 patch("app.services.shenzhen_air_flight_times.ctrip_client", client):
                yield requests

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local Ctrip simulation required")
    async def test_http_actual_fallback_toggle_saves_each_detail_without_overwriting_kinggo_plan(self):
        self.add_flight("ZH9203", destination="XIY", actual=None)
        rows = [cargo_row("ZH9203", destination="西安"), cargo_row("ZH9203", destination="西安", sequence="2")]
        async with self.ctrip_simulation() as requests:
            # Disabled: no HTTP request, cargo data still persists.
            await persist_shenzhen_air_billing_rows(self.db, rows, "62201856", 10)
            self.assertEqual(requests, [])
            self.assertTrue(all(row.actual_time is None for row in self.db.query(Detail)))
            with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", True):
                await persist_shenzhen_air_billing_rows(self.db, rows, "62201856", 10)
        self.assertEqual(requests, [{"aPort": "XIY", "dPort": "SZX", "fltno": "ZH9203", "queryDate": DAY.isoformat()}])
        details = self.db.query(Detail).all()
        self.assertEqual(len(details), 2)
        self.assertTrue(all(row.actual_time == "2026-10-19 10:10:00" for row in details))
        self.assertTrue(all(row.planned_time == "2026-10-19 09:30:00" for row in details))

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local Ctrip simulation required")
    async def test_http_background_actual_fallback_uses_detail_flight_not_parent(self):
        self.add_flight("ZH9203", destination="XIY", actual=None)
        await persist_shenzhen_air_billing_rows(self.db, [cargo_row("ZH9203", destination="西安"),
                                                       cargo_row("ZH9203", destination="西安", sequence="2")], "62201856", 10)
        async with self.ctrip_simulation() as requests:
            with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", True):
                await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        rows = self.db.query(Detail).all()
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row.actual_time == "2026-10-19 10:10:00" for row in rows))
        self.assertTrue(all(row.actual_time_attempts == "1" for row in rows))
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["fltno"], "ZH9203")
        self.assertEqual(requests[0]["aPort"], "XIY")

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local Ctrip simulation required")
    async def test_http_scheduler_fallback_uses_billing_flight_when_actual_flight_is_blank(self):
        manager = TransitLoadingManager()
        async with self.ctrip_simulation() as requests:
            with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", True), \
                 patch("app.services.transit_loading_manager.get_china_now", return_value=NOW):
                self.assertTrue(await manager._enqueue_billing_time_task(self.db, self.db.get(Export, 10), "test"))
        self.assertEqual(requests, [{"aPort": "YBP", "dPort": "SZX", "fltno": "ZH8985", "queryDate": DAY.isoformat()}])
        self.assertEqual(self.db.query(RPATask).one().scheduled_at, datetime(2026, 10, 19, 8, 15))

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local Ctrip simulation required")
    async def test_http_fallback_failure_preserves_kinggo_plan_and_saved_actual(self):
        self.add_flight("ZH9999", destination="XIY", actual=None)
        self.db.add(Detail(id=1, booking_export_id=10, flight_number="ZH9999", flight_date=DAY.isoformat(),
                           origin="SZX", destination="西安", actual_time="2026-10-19 09:50:00"))
        self.db.commit()
        async with self.ctrip_simulation() as requests:
            with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", True):
                await persist_shenzhen_air_billing_rows(self.db, [cargo_row("ZH9999", destination="西安")], "62201856", 10)
        self.assertEqual(len(requests), 2)  # Existing Ctrip GUID refresh retry.
        row = self.db.query(Detail).one()
        self.assertEqual(row.planned_time, "2026-10-19 09:30:00")
        self.assertEqual(row.actual_time, "2026-10-19 09:50:00")

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local KingGo simulation required")
    async def test_http_flight_sync_to_detail_persistence_and_late_local_backfill(self):
        from app.services.shenzhen_air_direct_billing_time_container import ShenzhenAirDirectBillingTimeContainerService
        from app.services.shenzhen_air_flight_info import KingGoFlightInfoClient, save_changed_flights
        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"

        async def sign_post(path, body):
            return "https://www.kinggo.com" + path + "&oOr6SIhu=local", {"Cookie": "local"}

        with patch.object(settings, "SHENZHEN_AIR_KINGGO_API_ORIGIN", origin), \
             patch("app.services.shenzhen_air_flight_info.shenzhen_air_direct_approval_service._auth", sign_post):
            flights = await KingGoFlightInfoClient().fetch(DAY)
        save_changed_flights(self.db, DAY, flights)
        self.db.commit()
        service = ShenzhenAirDirectBillingTimeContainerService(origin=origin)

        async def sign_get(path):
            return "https://www.kinggo.com" + path + "&oOr6SIhu=local", {"Cookie": "local"}

        with patch.object(service, "_auth", sign_get):
            rows = await service.fetch_rows("62201856", "SZX-HGH", DAY.isoformat())
        await persist_shenzhen_air_billing_rows(self.db, rows, "62201856", 10)
        self.assertEqual(self.db.query(Detail).one().actual_time, "2026-10-19 09:45:00")
        # A historical row can still receive a newly published local actual.
        row = self.db.query(Detail).one()
        row.actual_time = None
        row.actual_time_attempts = "100"
        self.db.commit()
        await DepartureActualTimeSync()._sync_shenzhen()
        self.db.expire_all()
        self.assertEqual(row.actual_time, "2026-10-19 09:45:00")
