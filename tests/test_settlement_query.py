import unittest
from datetime import date
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Query, Session

from app.api.deps import get_current_active_user
from app.api.settlements import router
from app.database import get_db
from app.schemas.settlement import SettlementQuery


class SettlementQueryTests(unittest.TestCase):
    def test_record_time_range_parameters_are_parsed(self):
        query = SettlementQuery(
            airline_record_time_start="2026-10-21",
            airline_record_time_end="2026-10-22",
        )

        self.assertEqual(query.airline_record_time_start, date(2026, 10, 21))
        self.assertEqual(query.airline_record_time_end, date(2026, 10, 22))

    def test_flight_date_parameters_are_not_used_as_record_time_filters(self):
        query = SettlementQuery(
            flight_date_start="2026-10-21",
            flight_date_end="2026-10-22",
        )

        self.assertIsNone(query.airline_record_time_start)
        self.assertIsNone(query.airline_record_time_end)


class SettlementListFilterTests(unittest.TestCase):
    def setUp(self):
        self.db = Session()
        self.addCleanup(self.db.close)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/settlements")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: object()
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_date_filters_compile_for_mysql_and_target_record_time(self):
        for params, operators in (
            ({"airline_record_time_start": "2026-10-21"}, (">=",)),
            ({"airline_record_time_end": "2026-10-21"}, ("<=",)),
            ({"airline_record_time_start": "2026-10-21",
              "airline_record_time_end": "2026-10-21"}, (">=", "<=")),
            ({}, ()),
        ):
            with self.subTest(params=params), patch.object(
                Query, "count", autospec=True, return_value=0
            ) as count, patch.object(Query, "all", autospec=True, return_value=[]):
                response = self.client.get("/api/v1/settlements", params=params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"], {"total": 0, "items": []})
                sql = str(count.call_args.args[0].statement.compile(
                    dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}
                ))
                self.assertNotIn("$.flight_date", sql)
                self.assertIn("waybill_void_status != '3'", sql)
                if operators:
                    self.assertIn("$.airline_record_time", sql)
                    for operator in operators:
                        self.assertIn(f"{operator} '2026-10-21'", sql)
                else:
                    self.assertNotIn("$.airline_record_time", sql)

    def test_invalid_record_date_is_rejected(self):
        response = self.client.get("/api/v1/settlements", params={
            "airline_record_time_start": "invalid-date",
        })
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
