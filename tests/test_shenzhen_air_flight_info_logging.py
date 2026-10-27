"""Flight sync failures must be actionable without exposing upstream secrets."""
import os
import re
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo
from app.services.shenzhen_air_direct_approval import ShenzhenAirDirectApprovalError
from app.services.shenzhen_air_flight_info import (
    FlightInfoError, KingGoFlightInfoClient, ShenzhenAirFlightInfoSync,
    parse_flight_page, save_changed_flights,
)
from tests.test_shenzhen_air_flight_info import DAY, page_html


LOGGER = "app.services.shenzhen_air_flight_info"


class FlightInfoLoggingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ShenzhenAirFlightInfo.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.enterContext(patch.object(settings, "SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED", True))
        self.enterContext(patch(LOGGER + ".SessionLocal", self.Session))
        with self.Session() as db:
            rows, _, _ = parse_flight_page(page_html())
            save_changed_flights(db, DAY, rows)
            db.commit()

    def assert_safe_failure(self, output, code, *fields):
        self.assertIn("reason_code=" + code, output)
        self.assertIn("保留旧数据", output)
        for field in fields:
            self.assertIn(field, output)
        for secret in ("cookie-secret", "signature-secret", "body-secret", "bad-date-secret",
                       "bad-flight-secret", "password-secret", "Traceback"):
            self.assertNotIn(secret, output)
        with self.Session() as db:
            row = db.query(ShenzhenAirFlightInfo).one()
            self.assertEqual(row.actual_departure_time, "0945")

    async def fetch_failure(self, responses, max_pages=100):
        items = iter(responses)
        requests = []

        def handler(request):
            requests.append(request)
            item = next(items)
            if isinstance(item, Exception):
                raise item
            return httpx.Response(200, text=item) if isinstance(item, str) else item

        real_client = httpx.AsyncClient
        auth = AsyncMock(return_value=(
            "https://www.kinggo.com" + KingGoFlightInfoClient.PATH + "&oOr6SIhu=signature-secret",
            {"Cookie": "cookie-secret"},
        ))
        sync = ShenzhenAirFlightInfoSync()
        with patch(LOGGER + ".httpx.AsyncClient", side_effect=lambda **kwargs: real_client(
            transport=httpx.MockTransport(handler), **kwargs
        )), patch(LOGGER + ".shenzhen_air_direct_approval_service._auth", auth), \
                patch.object(sync.client, "MAX_PAGES", max_pages), self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertFalse(await sync.ensure_fresh(DAY))
            request_count = len(requests)
            # A failed round still obeys the existing retry throttle.
            self.assertFalse(await sync.ensure_fresh(DAY))
            self.assertEqual(len(requests), request_count)
        self.assertEqual(len(logs.output), 1)
        return logs.output[0]

    async def test_html_failures_log_reason_and_location_without_raw_cells(self):
        cases = [
            ("<html>body-secret</html>", "invalid_headers", ("expected_columns=20", "actual_columns=0")),
            (page_html().replace("<th>控制重量</th>", "<th>body-secret</th>"),
             "invalid_headers", ("header_mismatch_column=16",)),
            (re.sub(r'<div class="pagination".*?</div>', '', page_html()),
             "missing_pagination", ("actual_total=None", "page_size=None")),
            (page_html().replace('totalCount="1"', 'totalCount="body-secret"'),
             "invalid_pagination", ()),
            (page_html().replace("<td>国内</td>", ""),
             "invalid_columns", ("row_index=1", "actual_columns=19")),
            (page_html(flight="bad-flight-secret"),
             "invalid_flight_or_route", ("row_index=1", "invalid_fields=flight_number")),
            (page_html(route="cookie-secret"),
             "invalid_flight_or_route", ("invalid_fields=routing",)),
            (page_html().replace(DAY.isoformat(), "bad-date-secret"),
             "invalid_date", ("row_index=1", "flight_number=ZH9883")),
        ]
        for html, code, fields in cases:
            with self.subTest(code=code, fields=fields):
                output = await self.fetch_failure([html])
                self.assert_safe_failure(output, code, "page=1", "http_status=200", "stage=fetch", *fields)

    async def test_pagination_failures_log_counts_and_distinguish_dates_from_duplicates(self):
        first = page_html(total=2, size=1)
        cases = [
            ([first, page_html(flight="ZH9884", total=3, size=1)], 100,
             "total_changed", ("page=2", "expected_total=2", "actual_total=3", "collected_count=1")),
            ([first, first], 100, "duplicate_segment",
             ("page=2", "row_index=1", "flight_number=ZH9883", "origin=SZX", "destination=HGH")),
            ([page_html().replace(DAY.isoformat(), "2026-10-20")], 100,
             "date_mismatch", ("page=1", "returned_date=2026-10-20", "row_index=1")),
            ([page_html(total=2)], 100, "incomplete_pages",
             ("page=1", "expected_total=2", "collected_count=1", "page_rows=1", "page_size=200")),
            ([re.sub(r'<tr target=.*?</tr>', '', first)], 100,
             "empty_page", ("page=1", "expected_total=2", "collected_count=0", "page_rows=0")),
            ([first], 1, "page_limit", ("page=1", "max_pages=1", "collected_count=1")),
        ]
        for responses, limit, code, fields in cases:
            with self.subTest(code=code):
                output = await self.fetch_failure(responses, limit)
                self.assert_safe_failure(output, code, *fields)

    async def test_http_status_and_transport_failure_omit_url_headers_and_body(self):
        for response, fields in (
            (httpx.Response(503, text="body-secret"), ("http_status=503", "request_error_type=HTTPStatusError")),
            (httpx.ReadTimeout("cookie-secret signature-secret"), ("request_error_type=ReadTimeout",)),
        ):
            with self.subTest(fields=fields):
                output = await self.fetch_failure([response])
                self.assert_safe_failure(output, "request_failed", "page=1", *fields)

    async def test_untrusted_exception_text_and_causes_are_not_logged(self):
        for error, code in (
            (ShenzhenAirDirectApprovalError("cookie-secret"), "auth_failed"),
            (TimeoutError("signature-secret"), "sync_timeout"),
            (RuntimeError("body-secret"), "fetch_failed"),
            (FlightInfoError("cookie-secret"), "unknown"),
        ):
            with self.subTest(code=code):
                error.__cause__ = RuntimeError("password-secret")
                sync = ShenzhenAirFlightInfoSync()
                sync.client.fetch = AsyncMock(side_effect=error)
                with self.assertLogs(LOGGER, "WARNING") as logs:
                    self.assertFalse(await sync.ensure_fresh(DAY))
                self.assert_safe_failure(logs.output[0], code)

    async def test_database_failure_logs_persist_stage_without_database_details(self):
        sync = ShenzhenAirFlightInfoSync()
        sync.client.fetch = AsyncMock(return_value=parse_flight_page(page_html())[0])
        with patch(LOGGER + ".save_changed_flights", side_effect=RuntimeError("mysql://password-secret")), \
                self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertFalse(await sync.ensure_fresh(DAY))
        self.assert_safe_failure(logs.output[0], "persist_failed", "stage=persist")

    async def test_save_date_mismatch_is_logged_without_partial_commit(self):
        sync = ShenzhenAirFlightInfoSync()
        rows = parse_flight_page(page_html().replace(DAY.isoformat(), "2026-10-20"))[0]
        sync.client.fetch = AsyncMock(return_value=rows)
        with self.assertLogs(LOGGER, "WARNING") as logs:
            self.assertFalse(await sync.ensure_fresh(DAY))
        self.assert_safe_failure(logs.output[0], "save_date_mismatch", "stage=persist", "row_index=1")

    @unittest.skipUnless(os.environ.get("RPA_DEPARTURE_SIMULATION_URL"), "Local KingGo simulation required")
    async def test_real_http_failures_are_reported_by_the_sync_logger(self):
        origin = os.environ["RPA_DEPARTURE_SIMULATION_URL"].rsplit("/rpa", 1)[0] + "/kinggo"
        for signed, code, fields in (
            (False, "request_failed", ("http_status=400", "page=1")),
            (True, "page_limit", ("expected_total=2", "collected_count=1", "max_pages=1")),
        ):
            with self.subTest(signed=signed):
                sync = ShenzhenAirFlightInfoSync()
                signed_url = "https://www.kinggo.com" + KingGoFlightInfoClient.PATH
                if signed:
                    signed_url += "&oOr6SIhu=signature-secret"
                with patch.object(settings, "SHENZHEN_AIR_KINGGO_API_ORIGIN", origin), \
                        patch.object(sync.client, "MAX_PAGES", 1), \
                        patch(LOGGER + ".shenzhen_air_direct_approval_service._auth",
                              AsyncMock(return_value=(signed_url, {"Cookie": "cookie-secret"}))), \
                        self.assertLogs(LOGGER, "WARNING") as logs:
                    self.assertFalse(await sync.ensure_fresh(DAY))
                self.assert_safe_failure(logs.output[0], code, *fields)
