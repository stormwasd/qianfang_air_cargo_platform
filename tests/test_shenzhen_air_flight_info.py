import unittest
from datetime import date, datetime
from unittest.mock import AsyncMock, patch

import httpx
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo
from app.services.shenzhen_air_flight_info import (
    FlightInfoError, KingGoFlightInfoClient, ShenzhenAirFlightInfoSync,
    parse_flight_page, save_changed_flights,
)
from app.services.shenzhen_air_flight_times import ShenzhenAirFlightTimes, times_from_record


DAY = date(2026, 10, 19)
HEADERS = ["序号", "日期", "航班号", "航程", "区域", "起飞", "到达", "实际起飞", "实际到达",
           "飞机号", "机型", "宽/窄", "状态", "总重量", "总体积", "控制重量", "控制体积", "开放重量", "货机", "详情"]


def page_html(flight="ZH9883", route="SZX-HGH", total=1, size=200, actual="0945"):
    cells = ["1", DAY.isoformat(), flight, route, "国内", "0930", "1130", actual,
             "", "B1234", "738", "窄", "正常", "5000", "30", "4000", "20", "1000", "否", ""]
    return (
        '<table><thead><tr>' + ''.join(f'<th>{h}</th>' for h in HEADERS) + '</tr></thead>'
        '<tbody><tr target="flight_info_id" rel="42">' + ''.join(f'<td>{c}</td>' for c in cells)
        + f'</tr></tbody></table><div class="pagination" totalCount="{total}" numPerPage="{size}"></div>'
    )


class FlightDatabaseTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        ShenzhenAirFlightInfo.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.addCleanup(self.engine.dispose)

    def test_unique_identity_and_only_changed_rows_are_updated(self):
        rows, _, _ = parse_flight_page(page_html())
        db = self.Session()
        self.addCleanup(db.close)
        self.assertEqual(save_changed_flights(db, DAY, rows), (1, 0))
        db.commit()
        record = db.query(ShenzhenAirFlightInfo).one()
        original_id, original_updated = record.id, record.updated_at
        statements = []
        event.listen(self.engine, "before_cursor_execute", lambda conn, cursor, statement, *args: statements.append(statement))
        self.assertEqual(save_changed_flights(db, DAY, rows), (0, 0))
        db.commit()
        self.assertFalse(any(s.startswith("UPDATE") for s in statements))
        self.assertEqual(record.updated_at, original_updated)
        rows[0]["actual_departure_time"] = "0950"
        self.assertEqual(save_changed_flights(db, DAY, rows), (0, 1))
        db.commit()
        self.assertEqual(record.id, original_id)
        self.assertEqual(record.actual_departure_time, "0950")
        # Same flight, another leg and day must never overwrite this row.
        another_leg = {**rows[0], "destination": "SHA"}
        self.assertEqual(save_changed_flights(db, DAY, [another_leg]), (1, 0))
        tomorrow = date(2026, 10, 20)
        self.assertEqual(save_changed_flights(db, tomorrow, [{**rows[0], "flight_date": tomorrow}]), (1, 0))
        db.commit()
        self.assertEqual(db.query(ShenzhenAirFlightInfo).count(), 3)

    async def test_sync_failure_preserves_rows_and_success_is_throttled(self):
        rows, _, _ = parse_flight_page(page_html())
        sync = ShenzhenAirFlightInfoSync()
        sync.client.fetch = AsyncMock(return_value=rows)
        with patch("app.services.shenzhen_air_flight_info.SessionLocal", self.Session):
            self.assertTrue(await sync.ensure_fresh(DAY))
            self.assertTrue(await sync.ensure_fresh(DAY))
            sync.client.fetch.assert_awaited_once()
            sync._success.clear()
            sync._attempt.clear()
            sync.client.fetch.side_effect = FlightInfoError("incomplete second page")
            self.assertFalse(await sync.ensure_fresh(DAY))
            self.assertFalse(await sync.ensure_fresh(DAY))
            self.assertEqual(sync.client.fetch.await_count, 2)
        with self.Session() as db:
            self.assertEqual(db.query(ShenzhenAirFlightInfo).count(), 1)

    async def test_kinggo_preferred_and_fallback_only_fills_missing_estimate(self):
        rows, _, _ = parse_flight_page(page_html())
        with self.Session() as db:
            save_changed_flights(db, DAY, rows)
            db.commit()
        fallback = AsyncMock(return_value={"planned_time": "WRONG", "ready_time": "2026-10-19 09:40:00", "actual_time": "WRONG"})
        with patch("app.services.shenzhen_air_flight_times.SessionLocal", self.Session), \
             patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh", AsyncMock(return_value=True)), \
             patch("app.services.shenzhen_air_flight_times.ctrip_client.get_flight_times", fallback):
            client = ShenzhenAirFlightTimes()
            result = await client.get_flight_times("ZH9883", DAY, "SZX-杭州")
            self.assertEqual(result["planned_time"], "2026-10-19 09:30:00")
            self.assertEqual(result["actual_time"], "2026-10-19 09:45:00")
            self.assertIsNone(result["ready_time"])
            fallback.assert_not_awaited()
            result = await client.get_flight_times("ZH9883", DAY, "SZX-HGH", required_times=("ready_time",))
            self.assertEqual(result["ready_time"], "2026-10-19 09:40:00")
            self.assertEqual(result["actual_time"], "2026-10-19 09:45:00")
            fallback.assert_awaited_once()

    async def test_disabled_fallback_does_not_query_ctrip_or_invent_estimated_time(self):
        rows, _, _ = parse_flight_page(page_html(actual=""))
        with self.Session() as db:
            save_changed_flights(db, DAY, rows)
            db.commit()
        with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", False), \
             patch("app.services.shenzhen_air_flight_times.SessionLocal", self.Session), \
             patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh", AsyncMock()), \
             patch("app.services.shenzhen_air_flight_times.ctrip_client.get_flight_times", AsyncMock()) as fallback:
            result = await ShenzhenAirFlightTimes().get_flight_times("ZH9883", DAY, "SZX-HGH", required_times=("ready_time",))
            self.assertIsNone(result["ready_time"])
            self.assertIsNone(result["actual_time"])
            fallback.assert_not_awaited()

    async def test_missing_route_never_matches_another_leg(self):
        rows, _, _ = parse_flight_page(page_html())
        with self.Session() as db:
            save_changed_flights(db, DAY, rows)
            db.commit()
        with patch.object(settings, "SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED", False), \
             patch("app.services.shenzhen_air_flight_times.SessionLocal", self.Session), \
             patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh", AsyncMock()):
            result = await ShenzhenAirFlightTimes().get_flight_times("ZH9883", DAY, "SZX-SHA")
            self.assertIsNone(result)

    async def test_failed_ctrip_fallback_preserves_known_kinggo_times(self):
        rows, _, _ = parse_flight_page(page_html())
        with self.Session() as db:
            save_changed_flights(db, DAY, rows)
            db.commit()
        with patch("app.services.shenzhen_air_flight_times.SessionLocal", self.Session), \
             patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh", AsyncMock()), \
             patch("app.services.shenzhen_air_flight_times.ctrip_client.get_flight_times", AsyncMock(side_effect=RuntimeError("blocked"))):
            result = await ShenzhenAirFlightTimes().get_flight_times(
                "ZH9883", DAY, "SZX-HGH", required_times=("ready_time",)
            )
            self.assertEqual(result["planned_time"], "2026-10-19 09:30:00")
            self.assertEqual(result["actual_time"], "2026-10-19 09:45:00")
            self.assertIsNone(result["ready_time"])

    async def test_disabled_kinggo_preserves_ctrip_only_mode(self):
        expected = {"planned_time": "2026-10-19 09:30:00", "actual_time": None, "ready_time": None}
        with patch.object(settings, "SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED", False), \
             patch("app.services.shenzhen_air_flight_times.SessionLocal") as db, \
             patch("app.services.shenzhen_air_flight_times.shenzhen_air_flight_info_sync.ensure_fresh", AsyncMock()) as sync, \
             patch("app.services.shenzhen_air_flight_times.ctrip_client.get_flight_times", AsyncMock(return_value=expected)) as fallback:
            result = await ShenzhenAirFlightTimes().get_flight_times("ZH9883", DAY, "SZX-HGH")
            self.assertEqual(result, expected)
            sync.assert_not_awaited()
            db.assert_not_called()
            fallback.assert_awaited_once()


class FlightPageTests(unittest.IsolatedAsyncioTestCase):
    def test_parser_rejects_login_and_preserves_empty_times(self):
        with self.assertRaises(FlightInfoError):
            parse_flight_page("<html>Login</html>")
        with self.assertRaises(FlightInfoError):
            parse_flight_page(page_html().replace("<th>控制重量</th>", "<th>控制体积</th>"))
        rows, count, size = parse_flight_page(page_html(actual=""))
        self.assertEqual((count, size), (1, 200))
        self.assertIsNone(rows[0]["actual_departure_time"])

    def test_next_day_actual_and_invalid_clock(self):
        record = ShenzhenAirFlightInfo(flight_date=DAY, takeoff_time="2330", actual_departure_time="0020")
        self.assertEqual(times_from_record(record)["actual_time"], "2026-10-20 00:20:00")
        record.takeoff_time, record.actual_departure_time = "0000", "2348"
        self.assertEqual(times_from_record(record)["actual_time"], "2026-10-18 23:48:00")
        record.actual_departure_time = "9999"
        self.assertIsNone(times_from_record(record)["actual_time"])

    async def test_pagination_re_signs_each_body_and_rejects_repeated_page(self):
        bodies = []
        def handler(request):
            from urllib.parse import parse_qs
            fields = parse_qs(request.content.decode())
            bodies.append(fields)
            flight = "ZH9883" if fields["pageNum"] == ["1"] else "ZH9884"
            return httpx.Response(200, text=page_html(flight=flight, total=2, size=1))
        real_client = httpx.AsyncClient
        auth = AsyncMock(return_value=("https://www.kinggo.com/flight_info/index/92?flag=true&oOr6SIhu=test", {"Cookie": "test"}))
        with patch("app.services.shenzhen_air_flight_info.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs)), \
             patch("app.services.shenzhen_air_flight_info.shenzhen_air_direct_approval_service._auth", auth):
            rows = await KingGoFlightInfoClient().fetch(DAY)
        self.assertEqual(len(rows), 2)
        self.assertEqual([b["pageNum"] for b in bodies], [["1"], ["2"]])
        self.assertEqual(auth.await_count, 2)
        self.assertNotEqual(auth.await_args_list[0].args[1], auth.await_args_list[1].args[1])
        # An upstream ignoring pageNum must fail, not silently miss later rows.
        with patch("app.services.shenzhen_air_flight_info.httpx.AsyncClient", side_effect=lambda **kwargs: real_client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=page_html(total=2, size=1))), **kwargs)), \
             patch("app.services.shenzhen_air_flight_info.shenzhen_air_direct_approval_service._auth", auth):
            with self.assertRaises(FlightInfoError):
                await KingGoFlightInfoClient().fetch(DAY)
