import json
import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.rpa_task import RPATask
from app.models.settlement import Settlement
from app.models.waybill import Waybill
from app.services.shenzhen_air_direct_waybill_void import (
    ShenzhenAirDirectWaybillVoidError,
    ShenzhenAirDirectWaybillVoidService,
)


HTML = """
<table><tbody>
<tr rel="7221144"><td name="awbPrefix">479</td><td name="awbNo">62134026</td>
<td><input type="hidden" name="awbId" value="7221144"/></td></tr>
</tbody></table>
"""


class _Response:
    def __init__(self, status_code=200, text="", payload=None):
        self.status_code = status_code
        self.text = text
        self._payload = payload

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _AsyncClient:
    responses = []
    requests = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.responses.pop(0)


class DirectVoidServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = ShenzhenAirDirectWaybillVoidService(origin="http://127.0.0.1:4900/kinggo")
        self.auth = AsyncMock(side_effect=self._auth)
        self.auth_calls = []

    async def _auth(self, path, method, body):
        self.auth_calls.append((path, method, body))
        suffix = "&" if "?" in path else "?"
        return f"https://www.kinggo.com{path}{suffix}oOr6SIhu=test", {"Cookie": "sid=test"}

    async def test_query_resolves_upstream_id_and_delete_uses_new_auth_and_empty_body(self):
        _AsyncClient.responses = [
            _Response(text=HTML),
            _Response(payload={"statusCode": "200", "message": "成功删除"}),
        ]
        _AsyncClient.requests = []
        with patch.object(self.service, "_auth", self.auth), patch(
            "app.services.shenzhen_air_direct_waybill_void.httpx.AsyncClient", _AsyncClient
        ):
            result = await self.service.void_waybill("479-62134026")

        self.assertEqual(result, {"awb_id": "7221144", "waybill_number": "479-62134026"})
        self.assertEqual(len(self.auth_calls), 2)
        query_fields = parse_qs(self.auth_calls[0][2], keep_blank_values=True)
        self.assertEqual(query_fields["awbNoQ"], ["62134026"])
        self.assertEqual(self.auth_calls[1][0], "/awb/query/delete_awb_info/119?awbId=7221144")
        self.assertEqual(self.auth_calls[1][2], "")
        self.assertEqual(urlsplit(_AsyncClient.requests[1][0]).query, "awbId=7221144&oOr6SIhu=test")
        self.assertEqual(_AsyncClient.requests[1][1]["content"], "")

    def test_parser_rejects_wrong_or_duplicate_rows(self):
        with self.assertRaises(ShenzhenAirDirectWaybillVoidError):
            self.service._find_awb_id(HTML.replace("62134026", "62134027"), "62134026")
        duplicate = HTML.replace("</tbody>", HTML.split("<tbody>", 1)[1].split("</tbody>", 1)[0] + "</tbody>")
        with self.assertRaises(ShenzhenAirDirectWaybillVoidError):
            self.service._find_awb_id(duplicate, "62134026")

    async def test_unconfirmed_delete_is_outcome_unknown(self):
        _AsyncClient.responses = [_Response(text=HTML), _Response(payload={"statusCode": "500", "message": "失败"})]
        with patch.object(self.service, "_auth", self.auth), patch(
            "app.services.shenzhen_air_direct_waybill_void.httpx.AsyncClient", _AsyncClient
        ):
            with self.assertRaises(ShenzhenAirDirectWaybillVoidError) as caught:
                await self.service.void_waybill("62134026")
        self.assertTrue(caught.exception.outcome_unknown)


class DirectVoidApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://")
        self.sessions = sessionmaker(bind=self.engine)
        for model in (Waybill, Settlement, RPATask):
            model.__table__.create(self.engine)
        self.db = self.sessions()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.waybill = Waybill(
            id=101,
            waybill_number="479-62134026",
            form_data=json.dumps({"airline": "1"}),
            booking_date=date(2026, 10, 17),
        )
        self.settlement = Settlement(
            id=201,
            form_data=json.dumps({"master_airwaybill_number": "479-62134026"}),
        )
        self.db.add_all([self.waybill, self.settlement])
        self.db.commit()

    async def test_direct_success_updates_waybill_and_settlement(self):
        from app.api.waybills import void_waybill

        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_VOID_EXECUTION_MODE", "direct"), patch(
            "app.services.shenzhen_air_direct_waybill_void.shenzhen_air_direct_waybill_void_service"
        ) as service, patch(
            "app.services.rpa_task_service.RPATaskService.get_pending_task_for_target", return_value=None
        ):
            service.void_waybill = AsyncMock(return_value={"awb_id": "7221144"})
            response = await void_waybill("101", SimpleNamespace(id=1), self.db)

        self.assertEqual(response.data["execution_mode"], "direct")
        self.assertEqual(response.data["kinggo_awb_id"], "7221144")
        self.db.expire_all()
        self.assertEqual(self.db.get(Waybill, 101).waybill_void_status, "3")
        self.assertEqual(self.db.get(Settlement, 201).waybill_void_status, "3")

    async def test_unknown_delete_keeps_in_progress_marker(self):
        from app.api.waybills import void_waybill

        error = ShenzhenAirDirectWaybillVoidError("结果不确定", outcome_unknown=True)
        with patch.object(settings, "SHENZHEN_AIR_WAYBILL_VOID_EXECUTION_MODE", "direct"), patch(
            "app.services.shenzhen_air_direct_waybill_void.shenzhen_air_direct_waybill_void_service"
        ) as service, patch(
            "app.services.rpa_task_service.RPATaskService.get_pending_task_for_target", return_value=None
        ):
            service.void_waybill = AsyncMock(side_effect=error)
            with self.assertRaises(Exception):
                await void_waybill("101", SimpleNamespace(id=1), self.db)
        self.db.expire_all()
        self.assertEqual(self.db.get(Waybill, 101).waybill_void_status, "1")


if __name__ == "__main__":
    unittest.main()
