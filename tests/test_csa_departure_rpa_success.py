"""Real HTTP regression checks against postman/simulations/rpa-departure.sim.yaml."""
import os
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.departure_tracking import get_china_southern_air_departures
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaLalamoveInformation, CsaProductInformation
from app.models.rpa_task import RPATask, RPATaskLastSuccess, RPATaskType
from app.services.rpa_service import rpa_service
from app.services.rpa_worker import RPAWorker
from app.services.tracking_execution_time import RPA_EXECUTION_SUCCESS_TYPES


@unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local RPA simulation required")
class CsaDepartureRPASuccessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (
            RPATask, RPATaskLastSuccess, ChinaSouthernAirApprovalData,
            CsaProductInformation, CsaLalamoveInformation, CsaDepartureManualData,
        ):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine, autoflush=False)()
        self.worker = RPAWorker(robot_db_id=1, robot_name="regression")
        self.old_time = datetime(2026, 8, 11, 9, 36, 56)
        self.now = datetime(2026, 10, 20, 18, 2, 16)
        self.rpa_end = datetime(2026, 10, 20, 18, 2, 15)
        self.run_type = RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value]
        self.task = RPATask(
            id=1, target_id=10, target_type="csa_dep_tracking",
            task_type=RPATaskType.CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING.value,
            params="{}", status="running", job_uuid="success-job",
            created_at=datetime(2026, 10, 20, 18, 0),
            attempt_count=0, max_attempts=3,
        )
        self.db.add_all([
            self.task,
            ChinaSouthernAirApprovalData(
                id=10, flight_info="CZ1234 / 2026-10-20 / SZX - SHA",
                departure_tracking_completed="0",
            ),
            RPATaskLastSuccess(
                task_type=self.task.task_type, last_success_at=self.old_time,
            ),
            RPATaskLastSuccess(task_type=self.run_type, last_success_at=self.old_time),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def _poll(self, product="empty", cargo="empty", timestamp_failure=False):
        queues = {
            "product_information_on_this_site": {"queueUUID": product, "queueID": "1"},
            "lalamove_information": {"queueUUID": cargo, "queueID": "2"},
        }
        with (
            patch.object(rpa_service, "base_url", os.environ["RPA_DEPARTURE_SIMULATION_URL"]),
            patch.object(rpa_service, "app_key", "local-test"),
            patch.object(rpa_service, "app_secret", "local-test"),
            patch.object(rpa_service, "cookie", ""),
            patch("app.services.rpa_worker.settings.RPA_POLL_MAX_COUNT", 1),
            patch("app.services.rpa_worker.settings.RPA_POLL_INTERVAL", 0),
            patch("app.services.rpa_task_service.get_china_now", return_value=self.now),
            patch("app.services.tracking_execution_time.get_china_now", return_value=self.now),
            patch("app.services.tracking_execution_time.SessionLocal",
                  side_effect=RuntimeError("unavailable") if timestamp_failure else sessionmaker(bind=self.engine)),
        ):
            await self.worker._poll_china_southern_air_departure_tracking_status(
                self.db, self.task, "test-work", queues,
            )

    def _success_time(self):
        self.db.expire_all()
        return self.db.get(RPATaskLastSuccess, self.run_type).last_success_at

    async def test_successful_rpa_with_empty_queues_updates_time_but_retries_data(self):
        await self._poll()
        self.assertEqual(self._success_time(), self.rpa_end)
        self.assertEqual(self.db.get(RPATask, 1).status, "pending")
        self.assertEqual(self.db.get(ChinaSouthernAirApprovalData, 10).departure_tracking_completed, "0")
        self.assertEqual(self.db.query(CsaLalamoveInformation).count(), 0)
        response = await get_china_southern_air_departures(
            waybill_number=None, flight_date_start=None, flight_date_end=None,
            flight_number=None, audit_status=None, origin=None, destination=None,
            customer_name=None, waybill_status=None, is_suspected_abnormal=None,
            page=1, pageSize=10, current_user=None, db=self.db,
        )
        self.assertEqual(response.data["data_update_time"], "2026-10-20 18:02")
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["items"][0]["lalamove_information"], [])

    async def test_successful_rpa_with_valid_data_completes_normally(self):
        await self._poll(product="product", cargo="cargo")
        self.assertEqual(self._success_time(), self.rpa_end)
        self.assertEqual(self.db.get(RPATaskLastSuccess, self.task.task_type).last_success_at, self.now)
        self.assertIsNone(self.db.get(RPATask, 1))
        self.assertEqual(self.db.get(ChinaSouthernAirApprovalData, 10).departure_tracking_completed, "1")
        self.assertEqual(self.db.query(CsaProductInformation).count(), 1)
        self.assertEqual(self.db.query(CsaLalamoveInformation).one().pre_assigned_flight, "CZ1234")

    async def test_successful_rpa_with_missing_flight_still_retries(self):
        await self._poll(product="product", cargo="no-flight")
        self.assertEqual(self._success_time(), self.rpa_end)
        self.assertEqual(self.db.get(RPATask, 1).status, "pending")
        self.assertEqual(self.db.get(ChinaSouthernAirApprovalData, 10).departure_tracking_completed, "0")

    async def test_failed_rpa_does_not_refresh_success_time(self):
        self.task.job_uuid = "failed-job"
        self.db.commit()
        await self._poll()
        self.assertEqual(self._success_time(), self.old_time)
        self.assertEqual(self.db.get(ChinaSouthernAirApprovalData, 10).departure_tracking_completed, "0")
        self.assertEqual(self.db.query(CsaProductInformation).count(), 0)
        self.assertEqual(self.db.query(CsaLalamoveInformation).count(), 0)

    async def test_missing_rpa_end_time_uses_success_confirmation(self):
        self.task.job_uuid = "missing-end-job"
        self.db.commit()
        await self._poll()
        self.assertEqual(self._success_time(), self.now)
        self.assertEqual(self.db.get(RPATask, 1).status, "pending")

    async def test_rpa_utc_end_time_is_converted_to_china_time(self):
        self.task.job_uuid = "utc-end-job"
        self.db.commit()
        await self._poll()
        self.assertEqual(self._success_time(), self.rpa_end)

    async def test_older_success_report_does_not_replace_newer_success(self):
        self.db.get(RPATaskLastSuccess, self.run_type).last_success_at = self.rpa_end
        self.task.job_uuid = "older-end-job"
        self.db.commit()
        await self._poll()
        self.assertEqual(self._success_time(), self.rpa_end)

    async def test_timestamp_database_failure_does_not_abort_data_completion(self):
        await self._poll(product="product", cargo="cargo", timestamp_failure=True)
        self.assertEqual(self._success_time(), self.old_time)
        self.assertIsNone(self.db.get(RPATask, 1))
        self.assertEqual(self.db.get(ChinaSouthernAirApprovalData, 10).departure_tracking_completed, "1")

    async def test_approval_pollers_record_their_own_rpa_end_time(self):
        for task_type, poller in (
            (RPATaskType.SHENZHEN_AIR_APPROVAL_DATA, self.worker._poll_shenzhen_air_approval_data_status),
            (RPATaskType.SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY, self.worker._poll_shenzhen_air_approval_data_status),
            (RPATaskType.CHINA_SOUTHERN_AIR_APPROVAL_DATA, self.worker._poll_china_southern_air_approval_data_status),
        ):
            with self.subTest(task_type=task_type):
                task = RPATask(id=2, target_id=1, target_type="approval",
                               task_type=task_type.value, job_uuid="success-job", params="{}", status="running")
                self.db.add(task)
                self.db.commit()
                with (
                    patch.object(rpa_service, "base_url", os.environ["RPA_DEPARTURE_SIMULATION_URL"]),
                    patch.object(rpa_service, "app_key", "local-test"),
                    patch.object(rpa_service, "app_secret", "local-test"),
                    patch.object(rpa_service, "cookie", ""),
                    patch("app.services.tracking_execution_time.SessionLocal", sessionmaker(bind=self.engine)),
                ):
                    await poller(self.db, task, "test-work")
                self.db.expire_all()
                self.assertIsNone(self.db.get(RPATask, 2))
                self.assertEqual(self.db.get(RPATaskLastSuccess, RPA_EXECUTION_SUCCESS_TYPES[task_type.value]).last_success_at, self.rpa_end)

    async def test_shenzhen_billing_rpa_records_success_before_empty_queue_retry(self):
        task_type = RPATaskType.SHENZHEN_AIR_BILLING_TIME_CONTAINER.value
        self.task.task_type = task_type
        self.db.commit()
        with (
            patch.object(rpa_service, "base_url", os.environ["RPA_DEPARTURE_SIMULATION_URL"]),
            patch.object(rpa_service, "app_key", "local-test"),
            patch.object(rpa_service, "app_secret", "local-test"),
            patch.object(rpa_service, "cookie", ""),
            patch("app.services.tracking_execution_time.SessionLocal", sessionmaker(bind=self.engine)),
        ):
            await self.worker._poll_shenzhen_air_billing_time_container_status(
                self.db, self.task, "test-work",
                {"billing_time_container": {"queueUUID": "empty", "queueID": "1"}},
            )
        self.db.expire_all()
        self.assertEqual(self.db.get(RPATaskLastSuccess, RPA_EXECUTION_SUCCESS_TYPES[task_type]).last_success_at, self.rpa_end)
        self.assertEqual(self.db.get(RPATask, 1).status, "pending")


if __name__ == "__main__":
    unittest.main()
