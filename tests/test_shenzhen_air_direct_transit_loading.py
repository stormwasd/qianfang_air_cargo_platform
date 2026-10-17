import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs

from app.services.shenzhen_air_direct_transit_loading import (
    ShenzhenAirDirectTransitLoadingError,
    ShenzhenAirDirectTransitLoadingService,
)


XLSX_CONTENT = b"PK\x03\x04fake"


class _Response:
    status_code = 200
    content = XLSX_CONTENT


class _AsyncClient:
    response = _Response()
    requests = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return self.response


class DirectTransitLoadingServiceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.service = ShenzhenAirDirectTransitLoadingService(
            origin="http://127.0.0.1:4900/kinggo",
            output_dir=self.temp_dir.name,
        )
        self.now = datetime(2026, 10, 18, 12, 30, 0)

    async def test_query_body_uses_beijing_today(self):
        body = self.service.build_query_body(self.now)
        fields = parse_qs(body, keep_blank_values=True)
        for key in ("operDateBeginQ", "operDateEndQ", "flightDateBeginQ", "flightDateEndQ"):
            self.assertEqual(fields[key], ["2026-10-18"])
        self.assertEqual(fields["flightDateCheck"], ["true"])
        self.assertEqual(fields["internationalFlag"], ["1"])

    async def test_download_writes_xlsx_into_output_dir(self):
        self.service._auth = AsyncMock(return_value=(
            "https://www.kinggo.com/awb/query/export/119?oOr6SIhu=test",
            {"Cookie": "sid=test"},
        ))
        _AsyncClient.requests = []
        with patch(
            "app.services.shenzhen_air_direct_transit_loading.httpx.AsyncClient",
            _AsyncClient,
        ):
            output_path = await self.service.download_export(self.now)

        self.assertTrue(output_path.name.startswith("AwbQueryExport_"))
        self.assertTrue(output_path.name.endswith(".xlsx"))
        self.assertEqual(output_path.read_bytes(), XLSX_CONTENT)
        url, kwargs = _AsyncClient.requests[0]
        self.assertTrue(url.startswith("http://127.0.0.1:4900/kinggo/awb/query/export/119?oOr6SIhu=test"))
        body_fields = parse_qs(kwargs["content"], keep_blank_values=True)
        self.assertEqual(body_fields["flightDateBeginQ"], ["2026-10-18"])
        self.assertEqual(kwargs["headers"]["Cookie"], "sid=test")

    async def test_invalid_content_raises(self):
        self.service._auth = AsyncMock(return_value=("https://www.kinggo.com/awb/query/export/119", {}))
        _AsyncClient.response = type("_R", (), {"status_code": 200, "content": b"<html>"})()
        with patch(
            "app.services.shenzhen_air_direct_transit_loading.httpx.AsyncClient",
            _AsyncClient,
        ):
            with self.assertRaises(ShenzhenAirDirectTransitLoadingError):
                await self.service.download_export(self.now)
