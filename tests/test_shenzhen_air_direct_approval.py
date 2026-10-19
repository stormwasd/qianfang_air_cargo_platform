import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlsplit

from app.services.shenzhen_air_direct_approval import (
    ShenzhenAirDirectApprovalError,
    ShenzhenAirDirectApprovalService,
)


class _Response:
    status_code = 200
    content = b"PK\x03\x04sanitized-xlsx"


class _AsyncClient:
    requests = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _Response()


class DirectApprovalTests(unittest.IsolatedAsyncioTestCase):
    def test_build_query_body_contains_fixed_contract(self):
        body = ShenzhenAirDirectApprovalService.build_query_body("2026/10/19")
        query = parse_qs(body)
        self.assertEqual(query["depCode"], ["SZX"])
        self.assertEqual(query["flightDate"], ["2026-10-19"])
        self.assertEqual(query["agentCode"], ["SZXFDH"])
        self.assertEqual(query["orderType"], ["1"])
        self.assertEqual(query["ss"], ["1"])
        self.assertEqual(query["nn"], ["0"])

    def test_invalid_date_is_rejected(self):
        with self.assertRaises(ShenzhenAirDirectApprovalError):
            ShenzhenAirDirectApprovalService.build_query_body("2026-99-99")

    async def test_download_writes_xlsx_to_generated_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ShenzhenAirDirectApprovalService(
                origin="http://127.0.0.1:4900/kinggo", output_dir=temp_dir
            )
            service._auth = AsyncMock(return_value=(
                "https://www.kinggo.com/agent_order_look/export/125?oOr6SIhu=test",
                {"Cookie": "sid=test"},
            ))
            _AsyncClient.requests = []
            with patch(
                "app.services.shenzhen_air_direct_approval.httpx.AsyncClient",
                _AsyncClient,
            ):
                output_path = await service.download_export(
                    datetime(2026, 10, 19), now=datetime(2026, 10, 19, 8, 0, 0)
                )

            self.assertTrue(output_path.exists())
            self.assertTrue(output_path.name.startswith("订舱查询导出_20261019_"))
            url, kwargs = _AsyncClient.requests[0]
            self.assertTrue(url.startswith("http://127.0.0.1:4900/kinggo/agent_order_look/export/125"))
            self.assertEqual(kwargs["headers"]["Cookie"], "sid=test")
            query = parse_qs(kwargs["content"])
            self.assertEqual(query["flightDate"], ["2026-10-19"])
            service._auth.assert_awaited_once_with(
                "/agent_order_look/export/125", kwargs["content"]
            )

    async def test_direct_scheduler_downloads_today_and_tomorrow_without_rpa_tasks(self):
        from app.config import settings
        from app.services.shenzhen_air_approval_scheduler import ShenzhenAirApprovalScheduler

        service = ShenzhenAirApprovalScheduler()
        download = AsyncMock()
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "direct"), \
             patch.object(settings, "RPA_QUEUE_ENABLED", False), \
             patch.object(service, "_cleanup_pending_direct_switch_tasks"), \
             patch(
                 "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service.download_export",
                 download,
             ), \
             patch("app.services.shenzhen_air_approval_scheduler.get_china_now", return_value=datetime(2026, 10, 19, 8, 0, 0)):
            await service._enqueue_task()

        self.assertEqual(download.await_count, 2)
        self.assertEqual(
            [call.args[0].strftime("%Y-%m-%d") for call in download.await_args_list],
            ["2026-10-19", "2026-10-20"],
        )


if __name__ == "__main__":
    unittest.main()
