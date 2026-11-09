import unittest
from datetime import datetime
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.api import customer_service
from app.api.deps import get_current_active_user
from app.database import get_db
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
            flight_doc_no=None,
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
                self.assertEqual(await self.query_ids(destination=keyword), {"1", "5"} if keyword == "K" else {"1"})

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
        self.assertIsNone(ConsignmentInfoQuery().flight_doc_no)

        app = FastAPI()
        app.include_router(customer_service.router, prefix="/customer-service")
        parameters = {
            item["name"]: item
            for item in app.openapi()["paths"]["/customer-service/consignments"]["get"]["parameters"]
        }

        for name in ("destination", "flight_no", "flight_doc_no"):
            with self.subTest(name=name):
                self.assertIn(name, parameters)
                self.assertFalse(parameters[name]["required"])


class CustomerServiceMasterDocFilterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")

        @event.listens_for(self.engine, "connect")
        def register_mysql_functions(connection, _record):
            connection.create_function("substring_index", 3, _sqlite_substring_index)

        ConsignmentInfo.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add_all([
            ConsignmentInfo(
                id=1, create_time=datetime(2026, 11, 1), status=0,
                customer_name="客户A", origin_destination="CAN-KUL", flight_no="CZ1234",
                flight_doc_no="784-12345678", bill_of_lading="提单原值",
                financial_data={"payables": {"intl_air": {"flight_doc_no": "国际原值"}}},
            ),
            ConsignmentInfo(
                id=2, create_time=datetime(2026, 11, 2), status=1,
                customer_name="客户A", origin_destination="SZX-SIN", flight_no="CZ5678",
                flight_doc_no="999-12345678",
            ),
            ConsignmentInfo(
                id=3, create_time=datetime(2026, 11, 3), status=2, edit_locked=True,
                customer_name="客户B", origin_destination="CAN-KUL", flight_no="ZH1234",
                flight_doc_no="888-12345678",
            ),
            ConsignmentInfo(id=4, flight_doc_no="另一个号码", bill_of_lading="784-12345678",
                            financial_data={"payables": {
                                "intl_air": {"flight_doc_no": "784-12345678"},
                                "dom_air": {"flight_doc_no": "784-12345678"},
                                "trucking": {"flight_doc_no": "784-12345678"},
                            }}),
            ConsignmentInfo(id=5, flight_doc_no=None, internal_doc_id="784-12345678"),
            ConsignmentInfo(id=6, flight_doc_no=""),
            ConsignmentInfo(id=7, flight_doc_no="AbC_01%/尾号"),
        ])
        self.db.commit()
        app = FastAPI()
        app.include_router(customer_service.router, prefix="/api/v1/customer-service")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=99)
        self.app = app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def query(self, **params):
        response = await self.client.get("/api/v1/customer-service/consignments", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], 0)
        return response.json()["data"]

    async def test_only_matches_entrustment_master_doc_and_preserves_business_fields(self):
        result = await self.query(flight_doc_no="  784-12345678  ")
        self.assertEqual(result["total"], 1)
        self.assertEqual([item["id"] for item in result["items"]], ["1"])
        item = result["items"][0]
        self.assertEqual(item["flight_doc_no"], "784-12345678")
        self.assertEqual(item["bill_of_lading"], "提单原值")
        self.assertEqual(item["payables"]["intl_air"]["flight_doc_no"], "国际原值")
        self.assertEqual((item["status"], item["editable"]), (0, True))
        self.assertFalse(self.db.dirty)

    async def test_partial_match_pagination_total_and_sort(self):
        first = await self.query(flight_doc_no="123456", page=1, pageSize=2)
        self.assertEqual(first["total"], 3)
        self.assertEqual([item["id"] for item in first["items"]], ["3", "2"])
        second = await self.query(flight_doc_no="123456", page=2, pageSize=2)
        self.assertEqual(second["total"], 3)
        self.assertEqual([item["id"] for item in second["items"]], ["1"])
        self.assertEqual((second["page"], second["pageSize"]), (2, 2))
        ascending = await self.query(flight_doc_no="123456", sort_order="asc")
        self.assertEqual([item["id"] for item in ascending["items"]], ["1", "2", "3"])

    async def test_missing_empty_and_whitespace_do_not_filter(self):
        for params in ({}, {"flight_doc_no": ""}, {"flight_doc_no": "  "}):
            with self.subTest(params=params):
                result = await self.query(**params)
                self.assertEqual(result["total"], 7)
                self.assertEqual({item["id"] for item in result["items"]}, {str(i) for i in range(1, 8)})

    async def test_combines_with_existing_filters(self):
        for params, expected in (
            ({"customer_name": "客户A"}, {"1", "2"}),
            ({"status": 0}, {"1"}), ({"status": 1}, {"2"}), ({"status": 2}, {"3"}),
            ({"destination": "KUL"}, {"1", "3"}),
            ({"flight_no": "CZ"}, {"1", "2"}),
            ({"start_date": "2026-11-02", "end_date": "2026-11-03"}, {"2", "3"}),
            ({"destination": "KUL", "customer_name": "客户A", "flight_no": "CZ", "status": 0,
              "start_date": "2026-11-01", "end_date": "2026-11-01"}, {"1"}),
            ({"destination": "KUL", "flight_no": "CZ5678"}, set()),
        ):
            with self.subTest(params=params):
                result = await self.query(flight_doc_no="123456", **params)
                self.assertEqual(result["total"], len(expected))
                self.assertEqual({item["id"] for item in result["items"]}, expected)

    async def test_case_insensitive_and_literal_wildcards(self):
        for keyword in ("abc", "尾号", "_", "%", "01%/", "aBc_01%/尾号"):
            with self.subTest(keyword=keyword):
                result = await self.query(flight_doc_no=keyword)
                self.assertEqual([item["id"] for item in result["items"]], ["7"])

    async def test_no_match_returns_original_empty_page_shape(self):
        for keyword in ("不存在", "' OR 1=1 --"):
            self.assertEqual(await self.query(flight_doc_no=keyword), {
                "total": 0, "items": [], "page": 1, "pageSize": 10,
            })

    def test_openapi_and_query_schema_describe_optional_customer_master_doc(self):
        parameters = self.app.openapi()["paths"]["/api/v1/customer-service/consignments"]["get"]["parameters"]
        parameter = next(p for p in parameters if p["name"] == "flight_doc_no")
        self.assertFalse(parameter["required"])
        self.assertIn("主单号", parameter["description"])
        self.assertIn("顶层 flight_doc_no", parameter["description"])
        field = ConsignmentInfoQuery.model_fields["flight_doc_no"]
        self.assertIsNone(field.default)
        self.assertIn("顶层 flight_doc_no", field.description)


if __name__ == "__main__":
    unittest.main()
