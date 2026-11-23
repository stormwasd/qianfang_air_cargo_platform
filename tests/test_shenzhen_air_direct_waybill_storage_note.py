"""Verify storage instructions across the durable snapshot and actual HTTP form body."""
import base64
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from app.api.rpa_tasks import get_task_status
from app.api.waybills import execute_waybill, get_waybill, _extract_shenzhen_air_params
from app.config import settings
from app.models.waybill import ShenzhenAirDirectWaybillTask as Task
from app.services.shenzhen_air_direct_waybill import ShenzhenAirDirectWaybillService as Client
from app.services.shenzhen_air_direct_waybill_worker import ShenzhenAirDirectWaybillWorker as Worker
from tests import test_shenzhen_air_direct_waybill as fixtures


NOTE_FIELD = "storage_and_transportation_precautions"
NOTE = " 鲜活最长运输时限24小时\r\n轻拿轻放 & 勿倒置+保温=是% \n"
MISSING = object()


class StorageNoteParsingTests(unittest.TestCase):
    def test_optional_note_is_independent_of_cargo_name_and_business_defaults(self):
        defaults = {"shenzhen_air": {"booking": {"business_default": {
            "cargo_name": "默认货物", NOTE_FIELD: "不应自动填入的注意事项",
        }}}}
        for note in (MISSING, None, "", NOTE):
            with self.subTest(note=note):
                form = copy.deepcopy(fixtures.FORM)
                if note is not MISSING:
                    form["cargo_info"][NOTE_FIELD] = note
                values = Client.get_form_values(form, defaults)
                self.assertEqual(values[NOTE_FIELD], "" if note is MISSING or note is None else note)
                self.assertEqual(values["cargo_name"], "配件")
                # Existing RPA extraction remains independently wired to the same form field.
                self.assertEqual(_extract_shenzhen_air_params(form, defaults)[NOTE_FIELD],
                                 "" if note is MISSING else note)


@unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Local KingGo simulation required")
class StorageNoteFlowTests(unittest.IsolatedAsyncioTestCase):
    setUp = fixtures.PersistentTaskTests.setUp

    async def run_flow(self, note=MISSING, *, legacy=False, parsed_empty=False):
        self.db.query(Task).delete()
        form = copy.deepcopy(fixtures.FORM)
        if note is not MISSING:
            form["cargo_info"][NOTE_FIELD] = note
        expected = "" if parsed_empty or note is MISSING or note is None else note
        # Synthetic shipper marker tells the mock what the request contract must contain.
        form["shipper_consignee_info"]["shipper_info"] = "NOTE:" + base64.b64encode(expected.encode()).decode()
        self.waybill.form_data = json.dumps(form, ensure_ascii=False)
        self.waybill.waybill_number = None
        self.waybill.airline_record_status = "0"
        self.db.commit()
        requests = []
        client = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])

        async def auth(path, method, body):
            requests.append((urlsplit(path).path, body))
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local-test-only", {}

        worker = Worker(1)
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"), patch.object(client, "_auth", auth), \
             patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service", client), \
             patch.object(worker, "_after_success", new=AsyncMock()) as after:
            queued = await execute_waybill("101", SimpleNamespace(id=1), self.db)
            task = self.db.get(Task, int(queued.data["task_id"]))
            snapshot = json.loads(task.request_data)
            self.assertEqual(snapshot["values"][NOTE_FIELD], "" if note is MISSING or note is None else note)
            if legacy:
                snapshot["values"].pop(NOTE_FIELD)
            if parsed_empty:
                snapshot["values"][NOTE_FIELD] = ""
            task.request_data = json.dumps(snapshot, ensure_ascii=False)
            if legacy:
                # Direct DB edit models a changed live form; the queued snapshot must win.
                live_form = copy.deepcopy(form)
                live_form["cargo_info"][NOTE_FIELD] = "不应读取的最新表单内容"
                self.waybill.form_data = json.dumps(live_form, ensure_ascii=False)
            self.db.commit()
            self.assertTrue(await worker.process_one())
            self.assertFalse(await worker.process_one())
            after.assert_awaited_once()
        self.db.expire_all()
        persisted = self.db.get(Task, int(queued.data["task_id"]))
        self.assertEqual((persisted.status, persisted.stage), ("success", "confirmed"), persisted.error_message)
        self.assertEqual(json.loads(persisted.request_data), snapshot)
        self.assertEqual(self.waybill.waybill_number, fixtures.RESULT["waybill_number"])
        polled = await get_task_status(str(persisted.id), SimpleNamespace(id=1), self.db)
        self.assertEqual(polled.data["status"], "success")
        self.assertEqual(len(requests), 6)
        self.assertEqual(requests[-2][1], requests[-1][1])
        for path, body in requests[-2:]:
            self.assertTrue(path.endswith(("check_awb", "submit_awb")))
            fields = parse_qs(body, keep_blank_values=True)
            self.assertEqual(fields["transNote"], [expected])
            self.assertEqual(fields["goodsName"], ["配件"])
            self.assertNotEqual(fields["transNote"], fields["goodsName"])
        if not legacy:
            detail = await get_waybill("101", SimpleNamespace(id=1), self.db)
            self.assertEqual(detail.data["form_data"]["cargo_info"], form["cargo_info"])

    async def test_user_note_survives_snapshot_signing_and_http_encoding(self):
        await self.run_flow(NOTE)

    async def test_absent_null_and_empty_notes_submit_empty_without_cargo_fallback(self):
        for note in (MISSING, None, ""):
            with self.subTest(note=note):
                await self.run_flow(note)

    async def test_old_pending_snapshot_recovers_note_without_reading_live_form(self):
        await self.run_flow(NOTE, legacy=True)

    async def test_existing_empty_parsed_value_is_not_overwritten(self):
        await self.run_flow(NOTE, parsed_empty=True)


if __name__ == "__main__":
    unittest.main()
