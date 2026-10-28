"""Diagnose rejected direct waybills without changing creation or leaking forms."""
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx

from app.api.rpa_tasks import get_task_status
from app.api.waybills import execute_waybill, get_waybill
from app.config import settings
from app.core.exceptions import BadRequestException
from app.models.waybill import ShenzhenAirDirectWaybillTask as Task
from app.services.shenzhen_air_direct_waybill import _safe_upstream_text
from tests import test_shenzhen_air_direct_waybill as waybill_tests
from tests.test_shenzhen_air_direct_waybill import (
    FORM, Client, BookingError, Worker,
)


class RequestDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, stage, response=None, error=None, fields=None):
        def handler(request):
            if error:
                raise error
            return response

        real_client = httpx.AsyncClient
        service = Client(origin="http://local.test")
        auth = AsyncMock(return_value=(
            "https://www.kinggo.com/test?oOr6SIhu=signature-secret",
            {"Cookie": "session=cookie-secret; other=other-secret"},
        ))
        with patch.object(service, "_auth", auth), patch(
            "app.services.shenzhen_air_direct_waybill.httpx.AsyncClient",
            side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
        ):
            with self.assertRaises(BookingError) as caught:
                await service._request(stage, fields)
        return caught.exception

    async def test_business_rejections_identify_every_endpoint_and_preserve_messages(self):
        for stage in Client.ENDPOINTS:
            with self.subTest(stage=stage):
                error = await self.request(stage, httpx.Response(200, json={
                    "retCode": "501", "msg": "计费重量校验失败", "result": {"message": "费用与计费重量不匹配"},
                }))
                self.assertEqual(error.outcome_unknown, stage == "submit")
                self.assertEqual(error.details["stage"], stage)
                self.assertEqual(error.details["endpoint"], Client.ENDPOINTS[stage].split("?")[0])
                self.assertEqual(error.details["http_status"], 200)
                self.assertEqual(error.details["upstream_ret_code"], "501")
                self.assertEqual(error.details["upstream_message"], "计费重量校验失败")
                self.assertEqual(error.details["upstream_result_message"], "费用与计费重量不匹配")
                self.assertEqual(error.details["reason_code"], "business_rejected")
                self.assertGreaterEqual(error.details["elapsed_ms"], 0)

    async def test_response_messages_redact_echoed_contacts_credentials_and_urls(self):
        contact = "李四 13800138000"
        message = ("计费重量不匹配\r\n" + contact + " 王五 "
                   "session=cookie-secret; other-secret "
                   "https://www.kinggo.com/x?oOr6SIhu=signature-secret "
                   "user@example.com token=token-secret password=password-secret")
        error = await self.request("submit", httpx.Response(200, json={
            "retCode": "500", "message": message,
            "result": {"msg": "收货人王五不匹配", "Cookie": "ignored-result-secret"},
            "Cookie": "ignored-body-secret",
        }), fields={"weight": "35", "chargeWeight": "45", "shpInfo": contact, "cneInfo": "王五"})
        diagnostic = json.dumps(error.details, ensure_ascii=False)
        for secret in (contact, "王五", "cookie-secret", "other-secret", "signature-secret", "token-secret",
                       "password-secret", "user@example.com", "ignored-result-secret", "ignored-body-secret"):
            self.assertNotIn(secret, diagnostic)
        self.assertIn("计费重量不匹配", diagnostic)
        self.assertNotIn("\n", error.details["upstream_message"])
        self.assertEqual(error.details["request_summary"], {"weight": "35", "chargeWeight": "45"})

    async def test_http_html_and_transport_errors_remain_distinct_and_safe(self):
        cases = (
            (httpx.Response(503, text="<html>body-secret</html>"), None, "http_error", 503),
            (httpx.Response(200, text="<html>body-secret</html>"), None, "invalid_json", 200),
            (httpx.Response(409, json={"retCode": "901", "errorMsg": "运单冲突"}), None, "http_error", 409),
            (None, httpx.ReadTimeout("https://password-secret"), "network_error", None),
        )
        for response, network_error, reason, status in cases:
            with self.subTest(reason=reason, status=status):
                error = await self.request("submit", response, network_error)
                self.assertTrue(error.outcome_unknown)
                self.assertEqual(error.details["reason_code"], reason)
                self.assertEqual(error.details.get("http_status"), status)
                self.assertNotIn("secret", str(error) + json.dumps(error.details))
        self.assertEqual(error.details["request_error_type"], "ReadTimeout")

    async def test_auth_failure_has_endpoint_without_crossing_send_boundary(self):
        service = Client()
        boundary = AsyncMock()
        with patch.object(service, "_auth", AsyncMock(side_effect=BookingError("签名准备失败"))):
            with self.assertRaises(BookingError) as caught:
                await service._request("submit", before_send=boundary)
        self.assertFalse(caught.exception.outcome_unknown)
        self.assertEqual(caught.exception.details["stage"], "submit")
        self.assertEqual(caught.exception.details["reason_code"], "auth_failed")
        boundary.assert_not_called()

    async def test_result_text_and_missing_or_malformed_messages_do_not_hide_failure(self):
        for payload, expected in (({"retMsg": "校验失败", "result": "请核对费用"}, "请核对费用"),
                                  ({"msg": {"secret": "ignored"}, "result": ["ignored"]}, None),
                                  ({}, None)):
            with self.subTest(payload=payload):
                error = await self.request("check", httpx.Response(200, json={"retCode": "500", **payload}))
                self.assertEqual(error.details.get("upstream_result_message"), expected)
                self.assertFalse(error.outcome_unknown)

    def test_free_text_is_bounded_and_objects_or_html_are_omitted(self):
        self.assertEqual(_safe_upstream_text("长" * 9000), "[上游提示过长，已省略]")
        self.assertLessEqual(len(_safe_upstream_text("长" * 1000)), 513)
        self.assertEqual(_safe_upstream_text("<html>secret</html>"), "[HTML内容已省略]")
        self.assertIsNone(_safe_upstream_text({"msg": "secret"}))
        self.assertNotIn("13800138000", _safe_upstream_text("收货人电话13800138000校验失败"))
        self.assertNotIn("secret", _safe_upstream_text("上游token=secret"))
        self.assertEqual(Client.diagnostic_values({"weight": "35\nsecret", "shipper_info": "secret"}), {})


class TaskDiagnosticTests(unittest.IsolatedAsyncioTestCase):
    setUp = waybill_tests.PersistentTaskTests.setUp

    @unittest.skipUnless(os.environ.get("KINGGO_SIM_ORIGIN"), "Local KingGo simulation required")
    async def test_http_submit_rejection_is_logged_persisted_and_keeps_user_weights(self):
        form = copy.deepcopy(FORM)
        form["cargo_info"].update(weight="35", chargeable_weight="45")
        form["shipper_consignee_info"]["shipper_info"] = "BUSINESS_REJECT"
        self.waybill.form_data = json.dumps(form)
        self.db.commit()
        service = Client(origin=os.environ["KINGGO_SIM_ORIGIN"])
        requests = []

        async def auth(path, method, body):
            requests.append(path)
            return Client.ORIGIN + path + ("&" if "?" in path else "?") + "oOr6SIhu=local", {"Cookie": "session=local-cookie"}

        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_EXECUTION_MODE", "direct"), \
             patch("app.api.waybills._get_business_config", return_value={"shenzhen_air": {}}), \
             patch.object(Client, "validate_configuration"), patch.object(service, "_auth", auth), \
             patch("app.services.shenzhen_air_direct_waybill_worker.shenzhen_air_direct_waybill_service", service):
            queued = await execute_waybill("101", SimpleNamespace(id=1), self.db)
            with self.assertLogs("app.services.shenzhen_air_direct_waybill_worker", "WARNING") as logs:
                self.assertTrue(await Worker(1).process_one())
            self.assertFalse(await Worker(1).process_one())
            with self.assertRaises(BadRequestException):
                await execute_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertEqual(len(requests), 6)  # Check succeeded, one submit, no automatic retry.
        self.assertEqual(len(logs.output), 1)
        output = logs.output[0]
        for expected in ('"weight": "35"', '"chargeable_weight": "45"', '"http_status": 200',
                         '"upstream_ret_code": "501"', '"stage": "submit"', '"waybill_id": "101"',
                         '"task_id": "' + queued.data["task_id"] + '"', "计费重量校验失败", "费用不匹配"):
            self.assertIn(expected, output)
        self.assertNotIn("local-cookie", output)
        self.db.expire_all()
        task = self.db.get(Task, int(queued.data["task_id"]))
        self.assertEqual((task.status, task.stage), ("unknown", "submitting"))
        self.assertEqual(self.waybill.airline_record_status, "2")
        self.assertIsNone(self.waybill.waybill_number)
        response = await get_task_status(queued.data["task_id"], SimpleNamespace(id=1), self.db)
        self.assertEqual(response.data["error_message"], task.error_message)
        self.assertIn("计费重量校验失败", task.error_message)
        detail = await get_waybill("101", SimpleNamespace(id=1), self.db)
        self.assertEqual(detail.data["form_data"]["cargo_info"], form["cargo_info"])
