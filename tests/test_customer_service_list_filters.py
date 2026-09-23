import unittest
from datetime import datetime

from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api import customer_service
from app.models.customer_service import ConsignmentInfo
from app.schemas.customer_service import (
    ConsignmentInfoQuery,
    ConsignmentInfoSortField,
    ConsignmentInfoSortOrder,
)


def _sqlite_substring_index(value, delimiter, count):
    """Provide MySQL SUBSTRING_INDEX semantics needed by the production query."""
    if value is None:
        return None
    parts = value.split(delimiter)
    if count > 0:
        return delimiter.join(parts[:count])
    if count < 0:
        return delimiter.join(parts[count:])
    return ""


class CustomerServiceListFilterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def register_mysql_functions(dbapi_connection, _connection_record):
            dbapi_connection.create_function("substring_index", 3, _sqlite_substring_index)

        ConsignmentInfo.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

        self.db.add_all([
            ConsignmentInfo(
                id=1,
                create_time=datetime(2026, 9, 1),
                origin_destination="SZX-CKG-KUL",
                flight_no="ZH1234",
            ),
            ConsignmentInfo(
                id=2,
                create_time=datetime(2026, 9, 2),
                origin_destination="KUL-SIN",
                flight_no="CZ5678",
            ),
            ConsignmentInfo(
                id=3,
                create_time=datetime(2026, 9, 3),
                origin_destination="SZX-吉隆坡",
                flight_no="中文航班一号",
            ),
            ConsignmentInfo(
                id=4,
                create_time=datetime(2026, 9, 4),
                origin_destination="深圳-广州-吉隆坡国际机场",
                flight_no="ZH9876",
            ),
            ConsignmentInfo(
                id=5,
                create_time=datetime(2026, 9, 5),
                origin_destination="SZX-PEK",
                flight_no="CA1000",
            ),
            ConsignmentInfo(
                id=6,
                create_time=datetime(2026, 9, 6),
                origin_destination="SZX-A_B",
                flight_no="TEST_01",
            ),
        ])
        self.db.commit()

    async def query_ids(self, *, destination=None, flight_no=None):
        response = await customer_service.get_consignments(
            start_date=None,
            end_date=None,
            customer_name=None,
            destination=destination,
            flight_no=flight_no,
            status=None,
            sort_by=ConsignmentInfoSortField.CREATE_TIME,
            sort_order=ConsignmentInfoSortOrder.DESC,
            page=1,
            pageSize=100,
            current_user=None,
            db=self.db,
        )
        return {item["id"] for item in response.data["items"]}

    async def test_destination_matches_any_english_substring_of_final_segment(self):
        for keyword in ("K", "U", "L", "KU", "UL", "kul"):
            with self.subTest(keyword=keyword):
                self.assertEqual(await self.query_ids(destination=keyword), {"1"})

    async def test_destination_matches_chinese_in_final_segment(self):
        self.assertEqual(await self.query_ids(destination="隆"), {"3", "4"})
        self.assertEqual(await self.query_ids(destination="国际"), {"4"})

    async def test_destination_does_not_match_an_origin_or_transit_segment(self):
        self.assertEqual(await self.query_ids(destination="广州"), set())
        self.assertEqual(await self.query_ids(destination="KUL"), {"1"})

    async def test_blank_destination_does_not_filter(self):
        self.assertEqual(
            await self.query_ids(destination="   "),
            {"1", "2", "3", "4", "5", "6"},
        )

    async def test_sql_wildcards_are_treated_as_literal_characters(self):
        self.assertEqual(await self.query_ids(destination="_"), {"6"})

    async def test_flight_no_matches_substring_case_insensitively(self):
        self.assertEqual(await self.query_ids(flight_no="ZH"), {"1", "4"})
        self.assertEqual(await self.query_ids(flight_no="h12"), {"1"})
        self.assertEqual(await self.query_ids(flight_no="987"), {"4"})

    async def test_flight_no_supports_chinese_and_combines_with_destination(self):
        self.assertEqual(await self.query_ids(flight_no="航班一"), {"3"})
        self.assertEqual(
            await self.query_ids(destination="KUL", flight_no="ZH1234"),
            {"1"},
        )
        self.assertEqual(
            await self.query_ids(destination="KUL", flight_no="CZ"),
            set(),
        )

    async def test_blank_flight_no_does_not_filter(self):
        self.assertEqual(
            await self.query_ids(flight_no="   "),
            {"1", "2", "3", "4", "5", "6"},
        )

    async def test_flight_no_sql_wildcards_are_literal(self):
        self.assertEqual(await self.query_ids(flight_no="_"), {"6"})

    def test_list_filters_are_optional_in_schema_and_openapi(self):
        self.assertIsNone(ConsignmentInfoQuery().destination)
        self.assertIsNone(ConsignmentInfoQuery().flight_no)

        app = FastAPI()
        app.include_router(customer_service.router, prefix="/customer-service")
        parameters = {
            item["name"]: item
            for item in app.openapi()["paths"]["/customer-service/consignments"]["get"]["parameters"]
        }

        for name in ("destination", "flight_no"):
            with self.subTest(name=name):
                self.assertIn(name, parameters)
                self.assertFalse(parameters[name]["required"])


if __name__ == "__main__":
    unittest.main()
