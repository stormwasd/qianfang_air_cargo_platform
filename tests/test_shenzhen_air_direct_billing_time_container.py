import unittest
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from app.services.shenzhen_air_direct_billing_time_container import (
    ShenzhenAirDirectBillingTimeContainerError,
    ShenzhenAirDirectBillingTimeContainerService,
)


HTML = """
<div id="getWay"><table><thead><tr><th>序号</th><th>航班号</th></tr></thead>
<tbody><tr><td><div class="remain" title="1">1</div></td><td>ZH9883</td>
<td>2026-10-19</td><td>0930</td><td>SZX</td><td>杭州</td><td>1</td><td>5.0</td><td>ZH7298</td></tr>
<tr><td></td><td>合计</td><td></td><td></td><td></td><td></td><td>1</td><td>5.0</td><td></td></tr></tbody></table></div>
"""


class _Response:
    status_code = 200
    text = HTML


class _AsyncClient:
    requests = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def get(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _Response()


class DirectBillingTimeContainerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.service = ShenzhenAirDirectBillingTimeContainerService(
            origin="http://127.0.0.1:4900/kinggo"
        )

    def test_build_path_contains_expected_query_and_timestamp(self):
        path = self.service.build_path("479-62134380", "SZX - SHA", "2026/10/19", now_ms=1792378895172)
        query = parse_qs(urlsplit(path).query)
        self.assertEqual(query["awbPrefix"], ["479"])
        self.assertEqual(query["awbNo"], ["62134380"])
        self.assertEqual(query["depCode"], ["SZX-SHA"])
        self.assertEqual(query["flightDate"], ["2026-10-19"])
        self.assertEqual(query["historyCheck"], ["false"])
        self.assertEqual(query["nti"], ["119"])
        self.assertEqual(query["_"], ["1792378895172"])

    def test_parse_rows_ignores_header_and_total(self):
        rows = self.service.parse_rows(HTML)
        self.assertEqual(rows, [["1", "ZH9883", "2026-10-19", "0930", "SZX", "杭州", "1", "5.0", "ZH7298"]])

    async def test_fetch_rows_sends_get_with_cookie(self):
        auth = AsyncMock(return_value=(
            "https://www.kinggo.com/awb/query/getaway?oOr6SIhu=test",
            {"Cookie": "sid=test"},
        ))
        self.service._auth = auth
        _AsyncClient.requests = []
        with patch(
            "app.services.shenzhen_air_direct_billing_time_container.httpx.AsyncClient",
            _AsyncClient,
        ):
            rows = await self.service.fetch_rows("62134380", "SZX-SHA", "2026-10-19")
        self.assertEqual(rows[0][1], "ZH9883")
        url, kwargs = _AsyncClient.requests[0]
        self.assertTrue(url.startswith("http://127.0.0.1:4900/kinggo/awb/query/getaway?oOr6SIhu=test"))
        self.assertEqual(kwargs["headers"]["Cookie"], "sid=test")
        auth.assert_awaited_once()
        signed_path = auth.await_args.args[0]
        signed_query = parse_qs(urlsplit(signed_path).query)
        self.assertEqual(signed_query["awbNo"], ["62134380"])
        self.assertEqual(signed_query["depCode"], ["SZX-SHA"])
        self.assertEqual(signed_query["flightDate"], ["2026-10-19"])
        self.assertRegex(signed_query["_"][0], r"^\d{13}$")

    def test_parse_empty_page_is_safe(self):
        self.assertEqual(self.service.parse_rows("<html><body>登录</body></html>"), [])

    async def test_direct_scheduler_does_not_enqueue_rpa_task(self):
        from app.services.transit_loading_manager import TransitLoadingManager
        from app.config import settings

        manager = TransitLoadingManager()
        direct_process = AsyncMock()
        with patch.object(settings, "SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE", "direct"), \
             patch.object(manager, "_process_direct_billing_time_container_records", direct_process), \
             patch.object(manager, "_enqueue_billing_time_task", AsyncMock()) as enqueue_rpa:
            await manager._enqueue_missing_billing_tasks()

        direct_process.assert_awaited_once()
        enqueue_rpa.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
