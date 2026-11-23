"""Chargeable-weight cabin policy through enqueue, worker and real local HTTP."""
import base64
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from app.api.rpa_tasks import get_task_status
from app.api.waybills import execute_waybill
from app.config import settings
from app.models.waybill import ShenzhenAirDirectWaybillTask as Task
from app.services.shenzhen_air_direct_waybill import ShenzhenAirDirectWaybillService as Client
from app.services.shenzhen_air_direct_waybill_worker import ShenzhenAirDirectWaybillWorker as Worker
from tests import test_shenzhen_air_direct_waybill as fixtures


@unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Local KingGo simulation required")
class WeightCabinPolicyTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixtures.PersistentTaskTests.setUp

    async def run_flow(self, charge_weight, *, weight="30", configured=("C", "C舱"),
                       expected=("F", "F舱"), rejection_stage=None, target="Z",
                       gateway_error=False, legacy=False):
        self.db.query(Task).delete()
        form = copy.deepcopy(fixtures.FORM)
        form["cargo_info"].update(weight=weight, chargeable_weight=charge_weight)
        contract = {
            "chargeWeight": charge_weight, "weight": weight,
            "cabinType": expected[0], "cabinTypeName": expected[1],
            "rejectionStage": rejection_stage, "target": target, "gatewayError": gateway_error,
        }
        form["shipper_consignee_info"]["shipper_info"] = "WEIGHT_POLICY:" + base64.b64encode(
            json.dumps(contract).encode()
        ).decode()
        self.waybill.form_data = json.dumps(form)
        self.waybill.waybill_number = None
        self.waybill.airline_record_status = "0"
        self.db.commit()
        client = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])
        requests = []

        async def auth(path, method, body):
            requests.append((urlsplit(path).path, parse_qs(body or "", keep_blank_values=True)))
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local-test", {}

        worker = Worker(1)
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch.object(settings, "SHENZHEN_AIR_KINGGO_CABIN_TYPE", configured[0]), \
             patch.object(settings, "SHENZHEN_AIR_KINGGO_CABIN_TYPE_NAME", configured[1]), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"), patch.object(client, "_auth", auth), \
             patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service", client), \
             patch.object(worker, "_after_success", new=AsyncMock()) as after, \
             patch.object(worker, "_mark_submitting", wraps=worker._mark_submitting) as boundary:
            queued = await execute_waybill("101", SimpleNamespace(id=1), self.db)
            task = self.db.get(Task, int(queued.data["task_id"]))
            snapshot = json.loads(task.request_data)
            if legacy:
                # Old tasks have no cabin-policy field. Execution must derive
                # it from their saved weight, even if the live form differs.
                live_form = copy.deepcopy(form)
                live_form["cargo_info"]["chargeable_weight"] = "50"
                self.waybill.form_data = json.dumps(live_form)
                self.db.commit()
            if rejection_stage:
                with self.assertLogs("app.services", "WARNING"):
                    self.assertTrue(await worker.process_one())
            else:
                self.assertTrue(await worker.process_one())
            self.assertFalse(await worker.process_one())
            if rejection_stage == "check":
                boundary.assert_not_called()
            else:
                boundary.assert_called_once_with(int(queued.data["task_id"]), "479-62046633")

        self.db.expire_all()
        task = self.db.get(Task, int(queued.data["task_id"]))
        self.assertEqual(json.loads(task.request_data), snapshot)
        self.assertEqual(sum(path.endswith("get_awb_no") for path, _ in requests), 1)
        self.assertEqual(len(requests), 5 if rejection_stage == "check" else 6)
        sent = [(path, fields) for path, fields in requests if path.endswith(("check_awb", "submit_awb"))]
        for _, fields in sent:
            self.assertEqual(fields["cabinType"], [expected[0]])
            self.assertEqual(fields["cabinTypeName"], [expected[1]])
            self.assertEqual(fields["oldCabinType"], ["C"])
            self.assertEqual(fields["weight"], [weight])
            self.assertEqual(fields["chargeWeight"], [charge_weight])
        if len(sent) == 2:
            self.assertEqual(sent[0][1], sent[1][1])
        polled = await get_task_status(str(task.id), SimpleNamespace(id=1), self.db)
        self.assertEqual(polled.data["status"], task.status)
        if rejection_stage:
            after.assert_not_awaited()
            self.assertIsNone(self.waybill.waybill_number)
            self.assertEqual(task.status, "unknown" if gateway_error and rejection_stage == "submit" else "failed",
                             task.error_message)
            self.assertIn('"cabin_policy": "chargeable_weight_lt_45_fixed_f"', task.error_message)
            self.assertNotIn('"cabin_adjustment":', task.error_message)
            if not gateway_error:
                self.assertIn(f"变更为{target}舱", task.error_message)
                if target != "F":
                    self.assertIn('"cabin_adjustment_blocked": true', task.error_message)
            if rejection_stage == "submit" and not gateway_error:
                self.assertIn('"submission_rejected": true', task.error_message)
                self.assertIn('"outcome_unknown": false', task.error_message)
        else:
            self.assertEqual((task.status, task.stage), ("success", "confirmed"), task.error_message)
            after.assert_awaited_once()
            self.assertEqual(self.waybill.waybill_number, "479-62046633")
            self.assertNotIn("cabin_adjustment", json.loads(task.result))

    async def test_below_45_overrides_config_and_upstream_cabin_using_chargeable_weight(self):
        cases = (
            ("30", "30", ("C", "C舱")),
            ("30", "60", ("Z", "Z舱")),
            ("44.999999999999999999", "35", ("", "")),
            ("0.5", "0.5", ("F", "F舱")),
        )
        for charge, weight, configured in cases:
            with self.subTest(charge=charge, weight=weight, configured=configured):
                await self.run_flow(charge, weight=weight, configured=configured)

    async def test_45_and_above_preserve_config_or_bill_fallback_even_when_gross_below_45(self):
        cases = (
            ("45", ("C", "C舱"), ("C", "C舱")),
            ("45.000", ("Z", "Z舱"), ("Z", "Z舱")),
            ("45.001", ("", ""), ("C", "C舱")),
            ("50", ("A", "A舱"), ("A", "A舱")),
        )
        for charge, configured, expected in cases:
            with self.subTest(charge=charge, configured=configured):
                await self.run_flow(charge, configured=configured, expected=expected)

    async def test_fixed_f_never_follows_check_or_submit_suggestions(self):
        for stage in ("check", "submit"):
            for target in ("C", "Z", "A", "F"):
                with self.subTest(stage=stage, target=target):
                    await self.run_flow("30", rejection_stage=stage, target=target)

    async def test_submit_gateway_failure_remains_unknown_and_is_not_retried(self):
        await self.run_flow("30", rejection_stage="submit", gateway_error=True)

    async def test_old_pending_task_uses_its_snapshot_chargeable_weight(self):
        await self.run_flow("30", legacy=True)


if __name__ == "__main__":
    unittest.main()
