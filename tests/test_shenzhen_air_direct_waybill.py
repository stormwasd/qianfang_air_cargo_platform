import copy
import json
import os
import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from urllib.parse import parse_qs

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.core.exceptions import BadRequestException
from app.models.rpa_task import RPATask
from app.models.waybill import Waybill, ShenzhenAirDirectWaybillTask as Task, ShenzhenAirDirectWaybillQueueLock
from app.services.shenzhen_air_direct_waybill import (
    ShenzhenAirDirectWaybillError as BookingError, ShenzhenAirDirectWaybillService as Client,
)
from app.services.shenzhen_air_direct_waybill_worker import (
    ShenzhenAirDirectWaybillWorker as Worker, ShenzhenAirDirectWaybillWorkerManager as Manager,
)
from app.utils.helpers import get_china_now

FORM = {
    "airline": "1",
    "flight_info": {
        "origin_station": "SZX", "destination": "TAO", "flight_date": "2026-10-16",
        "flight_number": "ZH9919", "waybill_type": "0",
    },
    "shipper_consignee_info": {"shipper_info": "发货人", "consignee_info": "收货人"},
    "cargo_info": {
        "quantity": "1", "weight": "2", "chargeable_weight": "3", "freight_code": "GEN",
        "cargo_code": "000", "cargo_name": "配件", "package": "木箱",
    },
}
VALUES = Client.get_form_values(FORM, {})
RESULT = {"waybill_number": "479-62046633", "awb_id": "7220434", "aviation_rate": 5.3,
          "aviation_fee": 50, "delivery_fee": 0}


class ClientTests(unittest.IsolatedAsyncioTestCase):
    def test_invalid_quantity_money_and_nested_config_are_rejected(self):
        for key, value in (("quantity", "1.5"), ("weight", "NaN"), ("chargeable_weight", "")):
            with self.subTest(key=key):
                form = copy.deepcopy(FORM)
                form["cargo_info"][key] = value
                with self.assertRaises(BookingError):
                    Client.get_form_values(form, {})
        with self.assertRaises(BookingError):
            Client.get_form_values(FORM, {"shenzhen_air": "invalid"})

    async def test_each_auth_replays_body_then_generates_with_original_digest(self):
        extracted = {"config": {"cookie": "test=only"}, "cookie": "test=only",
                     "payload": {"requestDigest": 123}}
        with patch("kinggo_token.har.replay_offline", new=AsyncMock(return_value=extracted)) as replay, \
             patch("kinggo_token.generate", return_value={"url": "/test?oOr6SIhu=test"}) as generate:
            for body in ("a=b", "a=c"):
                await Client()._auth("/test", "POST", body)
                self.assertEqual(replay.call_args.kwargs["body"], body)
        self.assertEqual(replay.await_count, 2)
        self.assertEqual(generate.call_count, 2)
        generate.assert_called_with("/test", extracted["config"], digest=123)

    async def test_auth_failure_does_not_expose_secrets(self):
        with patch("kinggo_token.har.replay_offline", new=AsyncMock(side_effect=ValueError("cookie=SECRET"))):
            with self.assertRaises(BookingError) as caught:
                await Client()._auth("/test", "POST", "")
        self.assertNotIn("SECRET", str(caught.exception))


class PersistentTaskTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.sessions = sessionmaker(bind=self.engine)
        for model in (Waybill, Task, RPATask, ShenzhenAirDirectWaybillQueueLock):
            model.__table__.create(self.engine)
        session_patch = patch("app.services.shenzhen_air_direct_waybill_worker.SessionLocal", self.sessions)
        session_patch.start()
        self.addCleanup(session_patch.stop)
        self.addCleanup(self.engine.dispose)
        self.db = self.sessions()
        self.addCleanup(self.db.close)
        self.waybill = Waybill(id=101, form_data=json.dumps(FORM), booking_date=date(2026, 10, 16),
                               airline_record_status="0")
        self.db.add(self.waybill)
        self.db.commit()

    def enqueue(self):
        self.waybill.airline_record_status = "1"
        task = Task(id=201, waybill_id=101, request_data=json.dumps({"form_data": FORM, "values": VALUES}))
        self.db.add(task)
        self.db.commit()
        return task

    def test_shared_account_only_claims_one_task_at_a_time(self):
        self.enqueue()
        self.db.add(Task(id=202, waybill_id=102, request_data="{}"))
        self.db.commit()
        self.assertEqual(Worker._claim(), 201)
        self.assertIsNone(Worker._claim())
        self.db.expire_all()
        self.assertEqual(self.db.get(Task, 202).status, "pending")
        self.db.get(Task, 201).status = "success"
        self.db.commit()
        self.assertEqual(Worker._claim(), 202)

    async def test_success_and_postprocessing_failure_never_reopen_creation(self):
        self.enqueue()
        worker = Worker(1)
        async def create(values, *, before_submit):
            before_submit(RESULT["waybill_number"])
            with self.sessions() as verification:
                persisted = verification.get(Task, 201)
                self.assertEqual(persisted.stage, "submitting")
                self.assertEqual(persisted.candidate_waybill_number, RESULT["waybill_number"])
            return RESULT.copy()
        with patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service.create_waybill", new=create), \
             patch.object(worker, "_after_success", new=AsyncMock(side_effect=RuntimeError("document failure"))):
            self.assertTrue(await worker.process_one())
            self.assertFalse(await worker.process_one())
        self.db.expire_all()
        task = self.db.get(Task, 201)
        self.assertEqual(task.status, "success")
        self.assertEqual(task.stage, "confirmed")
        self.assertIn("post_processing_error", json.loads(task.result))
        self.assertEqual(self.waybill.airline_record_status, "3")
        self.assertEqual(self.waybill.waybill_number, RESULT["waybill_number"])
        self.assertIsNotNone(self.waybill.airline_record_time)

    async def test_failures_before_and_after_send_boundary(self):
        self.enqueue()
        worker = Worker(1)
        for after_send in (False, True):
            with self.subTest(after_send=after_send):
                task = self.db.get(Task, 201)
                task.status, task.stage = "pending", "preparing"
                self.waybill.airline_record_status = "1"
                self.db.commit()
                async def create(values, *, before_submit):
                    if after_send:
                        before_submit(RESULT["waybill_number"])
                    raise RuntimeError("sensitive details")
                with patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service.create_waybill", new=create):
                    await worker.process_one()
                self.db.expire_all()
                task = self.db.get(Task, 201)
                self.assertEqual(task.status, "unknown" if after_send else "failed")
                self.assertNotIn("sensitive", task.error_message)
                self.assertEqual(self.waybill.airline_record_status, "2")
                self.assertIsNone(self.waybill.waybill_number)
                if after_send:
                    self.assertEqual(task.candidate_waybill_number, RESULT["waybill_number"])

    async def test_automation_disabled_skips_settlement_and_documents(self):
        with patch("app.services.document_print_service.is_post_waybill_automation_enabled", return_value=False):
            await Worker(1)._after_success(object(), self.waybill, FORM, RESULT)

    def test_recovery_distinguishes_preparation_from_potential_submission(self):
        task = self.enqueue()
        task.status = "running"
        task.started_at = get_china_now() - timedelta(minutes=31)
        self.db.commit()
        Manager.recover_stale_tasks()
        self.db.expire_all()
        self.assertEqual(task.status, "failed")
        task.status, task.stage = "running", "submitting"
        self.db.commit()
        Manager.recover_stale_tasks()
        self.db.expire_all()
        self.assertEqual(task.status, "unknown")

    async def test_execute_queues_snapshot_and_returns_without_waiting(self):
        from app.api.waybills import execute_waybill
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"):
            response = await execute_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertEqual(response.data["execution_mode"], "direct")
        self.assertEqual(response.data["airline_record_status"], "1")
        task = self.db.get(Task, int(response.data["task_id"]))
        self.assertEqual(task.status, "pending")
        self.assertEqual(json.loads(task.request_data)["form_data"], FORM)

    @unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Requires local Postman simulation")
    async def test_execute_worker_http_and_polling_complete_one_creation(self):
        from app.api.waybills import execute_waybill
        from app.api.rpa_tasks import get_task_status
        client = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])
        async def auth(path, method, body):
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local-test-only", {}
        client._auth = auth
        worker = Worker(1)
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"), \
             patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service", client), \
             patch.object(worker, "_after_success", new=AsyncMock()):
            queued = await execute_waybill("101", SimpleNamespace(id=1), self.db)
            self.assertEqual(queued.data["airline_record_status"], "1")
            self.assertTrue(await worker.process_one())
        self.db.expire_all()
        detail = await get_task_status(queued.data["task_id"], SimpleNamespace(id=1), self.db)
        self.assertEqual(detail.data["status"], "success")
        self.assertEqual(detail.data["stage"], "confirmed")
        self.assertEqual(detail.data["result"], RESULT)
        self.assertEqual(self.waybill.waybill_number, RESULT["waybill_number"])
        self.assertEqual(self.waybill.airline_record_status, "3")

    async def test_unknown_blocks_both_modes_and_form_editing(self):
        from app.api.waybills import execute_waybill, update_waybill
        from app.schemas.waybill import WaybillUpdate
        task = self.enqueue()
        task.status = "unknown"
        self.waybill.airline_record_status = "2"
        self.db.commit()
        for mode in ("direct", "rpa"):
            with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", mode):
                with self.assertRaises(BadRequestException):
                    await execute_waybill("101", SimpleNamespace(id=1), self.db)
        with self.assertRaises(BadRequestException):
            await update_waybill("101", WaybillUpdate(form_data=FORM), SimpleNamespace(id=1), self.db)

    async def test_existing_rpa_blocks_direct_enqueue(self):
        from app.api.waybills import execute_waybill
        self.db.add(RPATask(id=301, task_type="SHENZHEN_AIR_WAYBILL_EXECUTE", target_type="waybill",
                            target_id=101, params="{}", status="pending"))
        self.db.commit()
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"):
            with self.assertRaises(BadRequestException):
                await execute_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertEqual(self.db.query(Task).count(), 0)

    async def test_rpa_switch_uses_original_task_and_parameters(self):
        from app.api.waybills import execute_waybill
        config = {"shenzhen_air": {"booking": {"shenzhen_air_login": {
            "system_url": "https://www.kinggo.com/main", "system_account": "test-only",
            "login_password": "test-only",
        }}}}
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "rpa"), \
             patch("app.api.waybills._get_business_config", return_value=config):
            response = await execute_waybill("101", SimpleNamespace(id=1), self.db)
        task = self.db.get(RPATask, int(response.data["task_id"]))
        self.assertEqual(task.task_type, "SHENZHEN_AIR_WAYBILL_EXECUTE")
        self.assertEqual(json.loads(task.params)["flight_number"], "ZH9919")
        self.assertEqual(self.db.query(Task).count(), 0)

    async def test_detail_exposes_reconciliation_fields_with_string_ids(self):
        from app.api.rpa_tasks import get_task_status
        task = self.enqueue()
        task.id = 369409067778707456
        task.status, task.stage = "unknown", "submitting"
        task.candidate_waybill_number = RESULT["waybill_number"]
        self.db.commit()
        response = await get_task_status(str(task.id), SimpleNamespace(id=1), self.db)
        self.assertEqual(response.data["id"], str(task.id))
        self.assertEqual(response.data["target_id"], "101")
        self.assertEqual(response.data["status"], "unknown")
        self.assertEqual(response.data["stage"], "submitting")
        self.assertEqual(response.data["candidate_waybill_number"], RESULT["waybill_number"])


@unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Start Postman simulation and set KINGGO_SIM_ORIGIN")
class SimulationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])
        self.requests = []
        async def auth(path, method, body):
            self.requests.append((path, method, body))
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local-test-only", {}
        self.client._auth = auth
        config_patch = patch.object(Client, "validate_configuration")
        config_patch.start()
        self.addCleanup(config_patch.stop)

    async def test_six_real_http_calls_map_data_and_preserve_zero_fees(self):
        boundary = Mock()
        result = await self.client.create_waybill(VALUES, before_submit=boundary)
        self.assertEqual(result, RESULT)
        boundary.assert_called_once_with("479-62046633")
        self.assertEqual(len(self.requests), 6)
        self.assertEqual(self.requests[-2][2], self.requests[-1][2])
        fields = parse_qs(self.requests[-1][2], keep_blank_values=True)
        self.assertEqual(fields["deliveryFee"], ["0"])
        self.assertEqual(fields["totalFee"], ["51"])
        self.assertEqual(fields["goodsName"], ["配件"])
        self.assertEqual(fields["oldCabinType"], ["C"])

    async def test_check_rejection_never_submits(self):
        boundary = Mock()
        with self.assertRaises(BookingError) as caught:
            await self.client.create_waybill({**VALUES, "shipper_info": "FAIL_CHECK"}, before_submit=boundary)
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertIn("业务失败", str(caught.exception))
        boundary.assert_not_called()
        self.assertEqual(len(self.requests), 5)

    async def test_submit_gateway_error_is_unknown_and_never_retried(self):
        boundary = Mock()
        with self.assertRaises(BookingError) as caught:
            await self.client.create_waybill({**VALUES, "shipper_info": "FAIL_SUBMIT"}, before_submit=boundary)
        self.assertTrue(caught.exception.outcome_unknown)
        boundary.assert_called_once_with("479-62046633")
        self.assertEqual(len(self.requests), 6)

    async def test_unconfirmed_submit_responses_never_report_success(self):
        for scenario in ("WRONG_NUMBER", "MISSING_ID", "INVALID_JSON"):
            with self.subTest(scenario=scenario):
                self.requests.clear()
                boundary = Mock()
                with self.assertRaises(BookingError) as caught:
                    await self.client.create_waybill({**VALUES, "shipper_info": scenario}, before_submit=boundary)
                self.assertTrue(caught.exception.outcome_unknown)
                boundary.assert_called_once_with("479-62046633")
                self.assertEqual(len(self.requests), 6)

    async def test_failed_durable_boundary_does_not_send_submit(self):
        boundary = Mock(side_effect=RuntimeError("database commit failed"))
        with self.assertRaisesRegex(RuntimeError, "database commit failed"):
            await self.client.create_waybill(VALUES, before_submit=boundary)
        boundary.assert_called_once()
        # The sixth auth is prepared, but before_send aborted the HTTP call.
        self.assertEqual(len(self.requests), 6)

    async def test_unreachable_submit_is_unknown_without_retry(self):
        self.client.origin = "http://127.0.0.1:1"
        boundary = Mock()
        with self.assertRaises(BookingError) as caught:
            await self.client._request("submit", {}, before_send=boundary)
        self.assertTrue(caught.exception.outcome_unknown)
        boundary.assert_called_once()
        self.assertEqual(len(self.requests), 1)


if __name__ == "__main__":
    unittest.main()
