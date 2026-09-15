import unittest
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.rpa_task import RPATask, RPATaskStatus
from app.models.transit_loading import ShenzhenAirBookingExport
from app.services.departure_actual_time_sync import (
    DepartureActualTimeSync,
    _parse_planned,
)
from app.services.china_southern_air_approval_scheduler import (
    ChinaSouthernAirApprovalScheduler,
)
from app.services.rpa_task_service import rpa_task_service


class DepartureActualTimeSyncTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ShenzhenAirBookingExport.__table__.create(self.engine)
        ShenzhenAirBillingTimeContainer.__table__.create(self.engine)
        ChinaSouthernAirApprovalData.__table__.create(self.engine)
        CsaLalamoveInformation.__table__.create(self.engine)
        RPATask.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    async def test_persists_first_query_time_for_future_flight(self):
        db = self.Session()
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=1,
                booking_export_id=10,
                waybill_number_8="12345678",
                flight_number="ZH1234",
                flight_date="2026-09-15 00:00:00",
                planned_time="2026-09-15 12:00:00",
                actual_time_attempts="0",
                origin="SZX",
                destination="SHA",
            )
        )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS",
                1800,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=AsyncMock(),
            ) as get_flight_times,
        ):
            await DepartureActualTimeSync()._sync_shenzhen()

        verify_db = self.Session()
        row = verify_db.query(ShenzhenAirBillingTimeContainer).filter_by(id=1).one()
        self.assertEqual(row.next_actual_time_query_at, datetime(2026, 9, 15, 12, 30))
        self.assertEqual(row.actual_time_attempts, "0")
        get_flight_times.assert_not_awaited()
        verify_db.close()

    async def test_failed_planned_time_lookup_is_deferred(self):
        db = self.Session()
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=2,
                booking_export_id=20,
                waybill_number_8="87654321",
                flight_number="ZH5678",
                flight_date="2026-09-15",
                actual_time_attempts="0",
                origin="SZX",
                destination="PEK",
            )
        )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        get_flight_times = AsyncMock(return_value=None)
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS",
                1800,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=get_flight_times,
            ),
        ):
            await DepartureActualTimeSync()._sync_shenzhen()

        verify_db = self.Session()
        row = verify_db.query(ShenzhenAirBillingTimeContainer).filter_by(id=2).one()
        self.assertEqual(row.next_actual_time_query_at, datetime(2026, 9, 15, 10, 30))
        self.assertEqual(row.actual_time_attempts, "0")
        get_flight_times.assert_awaited_once_with(
            "ZH5678", "2026-09-15", "SZX-PEK"
        )
        verify_db.close()

    async def test_actual_time_request_exception_counts_as_an_attempt(self):
        db = self.Session()
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=3,
                booking_export_id=30,
                waybill_number_8="11223344",
                flight_number="ZH9999",
                flight_date="2026-09-15",
                planned_time="2026-09-15 09:00:00",
                actual_time_attempts="0",
                origin="SZX",
                destination="SHA",
            )
        )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS",
                1800,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_RETRY_INTERVAL_SECONDS",
                1800,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=AsyncMock(side_effect=RuntimeError("network error")),
            ),
        ):
            await DepartureActualTimeSync()._sync_shenzhen()

        verify_db = self.Session()
        row = verify_db.query(ShenzhenAirBillingTimeContainer).filter_by(id=3).one()
        self.assertEqual(row.actual_time_attempts, "1")
        self.assertEqual(row.next_actual_time_query_at, datetime(2026, 9, 15, 10, 30))
        verify_db.close()

    async def test_newly_resolved_planned_time_resets_first_query_delay(self):
        db = self.Session()
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=4,
                booking_export_id=40,
                waybill_number_8="55667788",
                flight_number="ZH8888",
                flight_date="2026-09-15",
                planned_time=None,
                actual_time_attempts="0",
                next_actual_time_query_at=datetime(2026, 9, 15, 10, 0, 0),
                origin="SZX",
                destination="SHA",
            )
        )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        get_flight_times = AsyncMock(
            return_value={"planned_time": "2026-09-15 12:00:00"}
        )
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS",
                1800,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=get_flight_times,
            ),
        ):
            await DepartureActualTimeSync()._sync_shenzhen()

        verify_db = self.Session()
        row = verify_db.query(ShenzhenAirBillingTimeContainer).filter_by(id=4).one()
        self.assertEqual(row.planned_time, "2026-09-15 12:00:00")
        self.assertEqual(row.next_actual_time_query_at, datetime(2026, 9, 15, 12, 30))
        self.assertEqual(row.actual_time_attempts, "0")
        self.assertEqual(get_flight_times.await_count, 1)
        verify_db.close()

    async def test_last_allowed_attempt_clears_next_query_time(self):
        db = self.Session()
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=5,
                booking_export_id=50,
                waybill_number_8="99887766",
                flight_number="ZH7777",
                flight_date="2026-09-15",
                planned_time="2026-09-15 09:00:00",
                actual_time_attempts="7",
                next_actual_time_query_at=datetime(2026, 9, 15, 10, 0, 0),
                origin="SZX",
                destination="SHA",
            )
        )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_MAX_ATTEMPTS",
                8,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=AsyncMock(return_value=None),
            ),
        ):
            await DepartureActualTimeSync()._sync_shenzhen()

        verify_db = self.Session()
        row = verify_db.query(ShenzhenAirBillingTimeContainer).filter_by(id=5).one()
        self.assertEqual(row.actual_time_attempts, "8")
        self.assertIsNone(row.next_actual_time_query_at)
        verify_db.close()

    async def test_future_rows_do_not_starve_later_batches(self):
        db = self.Session()
        for row_id in range(10, 13):
            db.add(
                ShenzhenAirBillingTimeContainer(
                    id=row_id,
                    booking_export_id=row_id,
                    waybill_number_8=str(row_id),
                    flight_number=f"ZH{row_id}",
                    flight_date="2026-09-15",
                    planned_time="2026-09-15 12:00:00",
                    actual_time_attempts="0",
                    origin="SZX",
                    destination="SHA",
                )
            )
        db.commit()
        db.close()

        fixed_now = datetime(2026, 9, 15, 10, 0, 0)
        sync = DepartureActualTimeSync()
        sync.BATCH_SIZE = 2
        with (
            patch(
                "app.services.departure_actual_time_sync.SessionLocal",
                self.Session,
            ),
            patch(
                "app.services.departure_actual_time_sync.get_china_now",
                return_value=fixed_now,
            ),
            patch.object(
                settings,
                "RPA_SHENZHEN_AIR_ACTUAL_TIME_FIRST_QUERY_DELAY_SECONDS",
                1800,
            ),
            patch(
                "app.services.departure_actual_time_sync.ctrip_client.get_flight_times",
                new=AsyncMock(),
            ) as get_flight_times,
        ):
            await sync._sync_shenzhen()
            await sync._sync_shenzhen()

        verify_db = self.Session()
        scheduled_count = verify_db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.next_actual_time_query_at.isnot(None)
        ).count()
        self.assertEqual(scheduled_count, 3)
        get_flight_times.assert_not_awaited()
        verify_db.close()

    def test_parses_time_with_excel_timestamp_flight_date(self):
        parsed = _parse_planned("930", "2026-09-15 00:00:00")

        self.assertEqual(parsed, datetime(2026, 9, 15, 9, 30))

    def test_backfills_completed_flag_for_existing_valid_children(self):
        db = self.Session()
        db.add(
            ShenzhenAirBookingExport(
                id=30,
                waybill_number="12345678",
                flight_date="2026-09-15",
                departure_tracking_completed="0",
            )
        )
        db.add(
            ShenzhenAirBillingTimeContainer(
                id=30,
                booking_export_id=30,
                waybill_number_8="12345678",
                flight_number="ZH1234",
                flight_date="2026-09-15",
                actual_time_attempts="0",
            )
        )
        db.commit()
        db.close()

        with patch(
            "app.services.departure_actual_time_sync.SessionLocal",
            self.Session,
        ):
            DepartureActualTimeSync._backfill_completion_flags()

        verify_db = self.Session()
        parent = verify_db.query(ShenzhenAirBookingExport).filter_by(id=30).one()
        self.assertEqual(parent.departure_tracking_completed, "1")
        verify_db.close()

    def test_backfills_csa_completed_flag_for_existing_valid_children(self):
        db = self.Session()
        db.add(
            ChinaSouthernAirApprovalData(
                id=31,
                flight_info="CZ3568 / 2026-09-15 / SZX - SHA",
                booking_no="123456789",
                departure_tracking_completed="0",
            )
        )
        db.add(
            CsaLalamoveInformation(
                id=31,
                approval_data_id=31,
                pre_assigned_flight="CZ3568",
                actual_time_attempts="0",
            )
        )
        db.commit()
        db.close()

        with patch(
            "app.services.departure_actual_time_sync.SessionLocal",
            self.Session,
        ):
            DepartureActualTimeSync._backfill_completion_flags()

        verify_db = self.Session()
        parent = verify_db.query(ChinaSouthernAirApprovalData).filter_by(id=31).one()
        self.assertEqual(parent.departure_tracking_completed, "1")
        verify_db.close()

    async def test_csa_task_uses_file_planned_time_without_calling_ctrip(self):
        db = self.Session()
        record = ChinaSouthernAirApprovalData(
            id=40,
            flight_info="CZ3568 / 2026-09-15 / SZX - SHA",
            planned_takeoff="12:00",
            booking_no="987654321 / test",
            departure_tracking_completed="0",
        )
        db.add(record)
        db.commit()

        with (
            patch(
                "app.services.china_southern_air_approval_scheduler.get_china_now",
                return_value=datetime(2026, 9, 15, 8, 0, 0),
            ),
            patch(
                "app.utils.ctrip_client.ctrip_client.get_flight_times",
                new=AsyncMock(),
            ) as get_flight_times,
        ):
            created = await ChinaSouthernAirApprovalScheduler()._enqueue_departure_tracking_task(
                db, record
            )

        self.assertTrue(created)
        task = db.query(RPATask).filter_by(target_id=record.id).one()
        self.assertEqual(task.scheduled_at, datetime(2026, 9, 15, 10, 15))
        self.assertEqual(json.loads(task.params)["booking_number"], "987654321")
        get_flight_times.assert_not_awaited()
        db.close()

    async def test_csa_task_falls_back_to_ctrip_ready_time(self):
        db = self.Session()
        record = ChinaSouthernAirApprovalData(
            id=41,
            flight_info="CZ3568 / 2026-09-15 / SZX - SHA",
            planned_takeoff=None,
            booking_no="123456789",
            departure_tracking_completed="0",
        )
        db.add(record)
        db.commit()
        get_flight_times = AsyncMock(
            return_value={"ready_time": "2026-09-15 13:00:00"}
        )

        with (
            patch(
                "app.services.china_southern_air_approval_scheduler.get_china_now",
                return_value=datetime(2026, 9, 15, 8, 0, 0),
            ),
            patch(
                "app.utils.ctrip_client.ctrip_client.get_flight_times",
                new=get_flight_times,
            ),
        ):
            created = await ChinaSouthernAirApprovalScheduler()._enqueue_departure_tracking_task(
                db, record
            )

        self.assertTrue(created)
        task = db.query(RPATask).filter_by(target_id=record.id).one()
        self.assertEqual(task.scheduled_at, datetime(2026, 9, 15, 11, 15))
        get_flight_times.assert_awaited_once_with(
            "CZ3568", "2026-09-15", "SZX - SHA"
        )
        db.close()


class DepartureTaskRetryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        RPATask.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_exhausted_task_is_retained_and_found_for_deduplication(self):
        task = RPATask(
            id=1,
            task_type="SHENZHEN_AIR_BILLING_TIME_CONTAINER",
            target_type="booking_export",
            target_id=10,
            params="{}",
            status=RPATaskStatus.RUNNING.value,
            priority=2,
            scheduled_at=datetime(2026, 9, 15, 10, 0, 0),
            attempt_count=1,
            max_attempts=2,
        )
        self.db.add(task)
        self.db.commit()

        rpa_task_service.requeue_task(
            self.db,
            task.id,
            delay_seconds=900,
            error_message="数据仍未更新",
        )

        retained = rpa_task_service.get_existing_task_for_target(
            self.db,
            target_type="booking_export",
            target_id=10,
            task_type="SHENZHEN_AIR_BILLING_TIME_CONTAINER",
        )
        self.assertIsNotNone(retained)
        self.assertEqual(retained.status, RPATaskStatus.FAILED.value)
        self.assertEqual(retained.attempt_count, 2)


if __name__ == "__main__":
    unittest.main()
