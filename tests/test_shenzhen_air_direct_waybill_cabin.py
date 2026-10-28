"""Real local HTTP plus persistent-worker regression for the cabin correction."""
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from app.api.rpa_tasks import get_task_status
from app.api.waybills import execute_waybill, get_waybill, update_waybill
from app.config import settings
from app.core.exceptions import BadRequestException
from app.models.waybill import ShenzhenAirDirectWaybillTask as Task
from app.schemas.waybill import WaybillUpdate
from app.services.shenzhen_air_direct_waybill import (
    ShenzhenAirDirectWaybillError as BookingError, ShenzhenAirDirectWaybillService as Client,
)
from app.services.shenzhen_air_direct_waybill_worker import ShenzhenAirDirectWaybillWorker as Worker
from tests import test_shenzhen_air_direct_waybill as fixtures


@unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Local KingGo simulation required")
class CabinCorrectionTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixtures.PersistentTaskTests.setUp

    async def run_scenario(self, scenario, timeout=30):
        form = copy.deepcopy(fixtures.FORM)
        form["cargo_info"].update(weight="35", chargeable_weight="45")
        form["shipper_consignee_info"]["shipper_info"] = scenario
        self.waybill.form_data = json.dumps(form)
        self.db.commit()
        service = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])
        requests = []

        async def auth(path, method, body):
            fields = {key: values[0] for key, values in parse_qs(body or "", keep_blank_values=True).items()}
            if scenario == "CABIN_AUTH_FAIL" and fields.get("cabinTypeName") == "Z":
                raise BookingError("签名准备失败")
            requests.append((urlsplit(path).path, method, fields))
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local-test", {"Cookie": "session=local-cookie"}

        worker = Worker(1)
        after_success = AsyncMock()
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch.object(settings, "SHENZHEN_AIR_KINGGO_CABIN_TYPE_NAME", "Z" if scenario == "CABIN_CODE_MISMATCH" else "F舱"), \
             patch.object(settings, "SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS", timeout), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"), patch.object(service, "_auth", auth), \
             patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service", service), \
             patch.object(worker, "_after_success", after_success), \
             patch.object(worker, "_mark_submitting", wraps=worker._mark_submitting) as boundary:
            queued = await execute_waybill("101", SimpleNamespace(id=1), self.db)
            with self.assertLogs("app.services", "WARNING") as logs:
                self.assertTrue(await worker.process_one())
            self.assertFalse(await worker.process_one())
            persisted = self.db.get(Task, int(queued.data["task_id"]))
            self.db.refresh(persisted)
            if persisted.status != "failed":
                with self.assertRaises(BadRequestException):
                    await execute_waybill("101", SimpleNamespace(id=1), self.db)
            boundary.assert_called_once_with(int(queued.data["task_id"]), "479-62046633")
        self.db.expire_all()
        task = self.db.get(Task, int(queued.data["task_id"]))
        snapshot = json.loads(task.request_data)
        self.assertEqual(snapshot["form_data"], form)
        detail = await get_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertEqual(detail.data["form_data"]["cargo_info"], form["cargo_info"])
        polled = await get_task_status(str(task.id), SimpleNamespace(id=1), self.db)
        self.assertEqual(polled.data["status"], task.status)
        if task.status == "success":
            self.assertEqual(polled.data["result"], json.loads(task.result))
        else:
            self.assertEqual(polled.data["error_message"], task.error_message)
        self.assertEqual(task.candidate_waybill_number, "479-62046633")
        self.assertNotIn("local-cookie", " ".join(logs.output))
        self.assertEqual(sum(path.endswith("get_awb_no") for path, _, _ in requests), 1)
        return task, requests, logs.output, after_success

    async def test_submit_correction_to_z_and_a_aligns_name_and_code_and_confirms_once(self):
        # Each subcase uses an independent task/db to preserve real enqueue guards.
        for target in ("Z", "A"):
            with self.subTest(target=target):
                if target == "A":
                    self.db.query(Task).delete()
                    self.waybill.waybill_number = None
                    self.waybill.airline_record_status = "0"
                    self.db.commit()
                task, requests, logs, after = await self.run_scenario("CABIN_" + target)
                self.assertEqual((task.status, task.stage), ("success", "confirmed"))
                self.assertEqual(self.waybill.airline_record_status, "3")
                self.assertEqual(self.waybill.waybill_number, "479-62046633")
                after.assert_awaited_once()
                self.assertEqual(len(requests), 8)
                original_check, original_submit, retry_check, retry_submit = [entry[2] for entry in requests[-4:]]
                self.assertEqual(original_check, original_submit)
                self.assertEqual(retry_check, retry_submit)
                self.assertEqual({key for key in original_submit if original_submit[key] != retry_submit[key]}, {"cabinTypeName", "cabinType"})
                self.assertEqual(retry_submit["cabinTypeName"], target)
                self.assertEqual((retry_submit["cabinType"], retry_submit["oldCabinType"]), (target, "C"))
                self.assertEqual((retry_submit["weight"], retry_submit["chargeWeight"]), ("35", "45"))
                result = json.loads(task.result)
                self.assertEqual(result["cabin_adjustment"]["to_cabin_type_name"], target)
                self.assertEqual(result["cabin_adjustment"]["from_cabin_type"], "F")
                self.assertEqual(result["cabin_adjustment"]["to_cabin_type"], target)
                self.assertEqual(result["cabin_adjustment"]["trigger_stage"], "submit")
                self.assertEqual(result["cabin_adjustment"]["retry_count"], 1)
                self.assertIn("cabinTypeName", " ".join(logs))

    async def test_matching_name_with_different_code_still_corrects_code(self):
        task, requests, _, after = await self.run_scenario("CABIN_CODE_MISMATCH")
        self.assertEqual((task.status, task.stage), ("success", "confirmed"))
        self.assertEqual(len(requests), 8)
        original_check, original_submit, retry_check, retry_submit = [entry[2] for entry in requests[-4:]]
        self.assertEqual(original_check, original_submit)
        self.assertEqual(retry_check, retry_submit)
        self.assertEqual({key for key in original_submit if original_submit[key] != retry_submit[key]}, {"cabinType"})
        self.assertEqual((retry_submit["cabinTypeName"], retry_submit["cabinType"], retry_submit["oldCabinType"]), ("Z", "Z", "C"))
        after.assert_awaited_once()

    async def test_check_stage_correction_validates_changed_name_before_first_submit(self):
        task, requests, _, after = await self.run_scenario("CABIN_CHECK_Z")
        self.assertEqual(task.status, "success")
        self.assertEqual(len(requests), 7)
        self.assertEqual([entry[0].split("/")[-1] for entry in requests[-3:]], ["check_awb", "check_awb", "submit_awb"])
        self.assertEqual(requests[-1][2]["cabinTypeName"], "Z")
        self.assertEqual(requests[-1][2]["cabinType"], "Z")
        self.assertEqual(requests[-2][2]["cabinType"], "Z")
        self.assertEqual(json.loads(task.result)["cabin_adjustment"]["trigger_stage"], "check")
        after.assert_awaited_once()

    async def test_repeated_explicit_rejection_allows_manual_execution_but_does_not_loop(self):
        task, requests, _, after = await self.run_scenario("CABIN_REPEAT")
        self.assertEqual((task.status, task.stage), ("failed", "submitting"))
        self.assertEqual(len(requests), 8)
        self.assertIn('"cabin_adjustment"', task.error_message)
        self.assertIn('"to_cabin_type_name": "Z"', task.error_message)
        self.assertIn("变更为A舱", task.error_message)
        self.assertIn('"submission_rejected": true', task.error_message)
        self.assertNotIn("提交结果未知", task.error_message)
        self.assertIsNone(self.waybill.waybill_number)
        after.assert_not_awaited()
        self.assertEqual(self.waybill.airline_record_status, "2")
        old_task_id = task.id
        original_snapshot = task.request_data
        edited_form = copy.deepcopy(json.loads(self.waybill.form_data))
        edited_form["cargo_info"]["chargeable_weight"] = "50"
        saved = await update_waybill("101", WaybillUpdate(form_data=edited_form), SimpleNamespace(id=1), self.db)
        self.assertEqual(saved.data["form_data"], edited_form)
        self.assertEqual(saved.data["airline_record_status"], "2")
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"):
            retried = await execute_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertNotEqual(retried.data["task_id"], str(old_task_id))
        self.assertEqual(retried.data["direct_task_status"], "pending")
        self.assertEqual(self.db.query(Task).count(), 2)
        self.assertEqual(self.db.get(Task, old_task_id).status, "failed")
        self.assertEqual(self.db.get(Task, old_task_id).request_data, original_snapshot)
        new_task = self.db.get(Task, int(retried.data["task_id"]))
        self.assertEqual(json.loads(new_task.request_data)["form_data"], edited_form)
        self.assertEqual(json.loads(new_task.request_data)["values"]["chargeable_weight"], "50")

    async def test_ambiguous_or_unrelated_rejections_are_not_retried(self):
        scenarios = ("CABIN_SAME", "CABIN_OTHER_CODE", "CABIN_OTHER_MESSAGE", "CABIN_CREATED", "CABIN_BAD_TARGET")
        for index, scenario in enumerate(scenarios):
            with self.subTest(scenario=scenario):
                if index:
                    self.db.query(Task).delete()
                    self.waybill.airline_record_status = "0"
                    self.db.commit()
                task, requests, _, after = await self.run_scenario(scenario)
                self.assertEqual(task.status, "failed" if scenario == "CABIN_SAME" else "unknown")
                self.assertEqual(len(requests), 6)
                self.assertNotIn('"cabin_adjustment"', task.error_message)
                after.assert_not_awaited()

    async def test_failed_retry_check_or_signing_does_not_send_second_submit(self):
        for index, scenario in enumerate(("CABIN_CHECK_FAIL", "CABIN_AUTH_FAIL")):
            with self.subTest(scenario=scenario):
                if index:
                    self.db.query(Task).delete()
                    self.waybill.airline_record_status = "0"
                    self.db.commit()
                task, requests, _, after = await self.run_scenario(scenario)
                self.assertEqual((task.status, task.stage), ("failed", "submitting"))
                self.assertEqual(sum(path.endswith("submit_awb") for path, _, _ in requests), 1)
                self.assertIn('"cabin_adjustment"', task.error_message)
                self.assertIn('"submission_rejected": true', task.error_message)
                after.assert_not_awaited()

    async def test_retry_http_non_json_and_timeout_are_unknown_without_third_submit(self):
        cases = (("CABIN_RETRY_HTTP_ERROR", "http_error", 30),
                 ("CABIN_RETRY_INVALID_JSON", "invalid_json", 30),
                 ("CABIN_RETRY_TIMEOUT", "network_error", 0.2))
        for index, (scenario, reason, timeout) in enumerate(cases):
            with self.subTest(scenario=scenario):
                if index:
                    self.db.query(Task).delete()
                    self.waybill.airline_record_status = "0"
                    self.db.commit()
                task, requests, _, after = await self.run_scenario(scenario, timeout=timeout)
                self.assertEqual((task.status, task.stage), ("unknown", "submitting"))
                self.assertEqual(sum(path.endswith("submit_awb") for path, _, _ in requests), 2)
                self.assertIn('"reason_code": "' + reason + '"', task.error_message)
                self.assertIn('"cabin_adjustment"', task.error_message)
                after.assert_not_awaited()

    async def test_retry_success_must_still_confirm_candidate_number_and_upstream_id(self):
        for index, scenario in enumerate(("CABIN_WRONG_NUMBER", "CABIN_MISSING_ID")):
            with self.subTest(scenario=scenario):
                if index:
                    self.db.query(Task).delete()
                    self.waybill.airline_record_status = "0"
                    self.db.commit()
                task, requests, _, after = await self.run_scenario(scenario)
                self.assertEqual((task.status, task.stage), ("unknown", "submitting"))
                self.assertIsNone(self.waybill.waybill_number)
                self.assertEqual(len(requests), 8)
                self.assertIn('"reason_code": "unconfirmed_result"', task.error_message)
                self.assertIn('"cabin_adjustment"', task.error_message)
                after.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
