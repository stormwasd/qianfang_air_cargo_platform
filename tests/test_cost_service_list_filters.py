import unittest
from datetime import date, datetime
from types import SimpleNamespace

import httpx

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.cost_service import CostConsignment
from app.schemas.cost_service import CostConsignmentQuery, CostConsignmentSortField, CostConsignmentSortOrder


class CostServiceListDateFilterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        CostConsignment.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

        self.db.add_all([
            CostConsignment(
                id=1,
                create_time=datetime(2026, 9, 1, 8, 0),
                warehouse_entry_date=date(2026, 9, 1),
                flight_date=date(2026, 9, 20),
                pay_intl_air_flight_date=date(2026, 9, 20),
                customer_name="委托和国际空运日期均匹配",
            ),
            CostConsignment(
                id=2,
                create_time=datetime(2026, 9, 2, 8, 0),
                warehouse_entry_date=date(2026, 9, 20),
                flight_date=date(2026, 9, 21),
                pay_intl_air_flight_date=date(2026, 9, 21),
                customer_name="仅进仓日期匹配",
            ),
            CostConsignment(
                id=3,
                create_time=datetime(2026, 9, 3, 8, 0),
                warehouse_entry_date=date(2026, 9, 20),
                flight_date=date(2026, 9, 20),
                pay_intl_air_flight_date=date(2026, 9, 19),
                customer_name="仅货主和进仓日期匹配",
            ),
            CostConsignment(
                id=4,
                create_time=datetime(2026, 9, 4, 8, 0),
                warehouse_entry_date=date(2026, 9, 22),
                flight_date=date(2026, 9, 22),
                pay_intl_air_flight_date=date(2026, 9, 20),
                pay_dom_air_flight_date=date(2026, 9, 20),
                customer_name="仅应付航班日期匹配",
            ),
            CostConsignment(id=5, flight_date=date(2026, 9, 20),
                            pay_dom_air_flight_date=date(2026, 9, 20)),
            CostConsignment(id=6, pay_intl_air_flight_date=date(2026, 9, 22)),
            CostConsignment(id=7, pay_dom_air_flight_date=date(2026, 9, 20)),
        ])
        self.db.commit()

    async def query_ids(self, **overrides):
        params = {
            "start_warehouse_date": None,
            "end_warehouse_date": None,
            "start_flight_date": None,
            "end_flight_date": None,
            "customer_name": None,
            "status": None,
            "agent": None,
            "flight_doc_no": None,
            "flight_no": None,
            "sort_by": CostConsignmentSortField.WAREHOUSE_ENTRY_DATE,
            "sort_order": CostConsignmentSortOrder.DESC,
            "page": 1,
            "pageSize": 100,
            "current_user": None,
            "db": self.db,
        }
        params.update(overrides)
        response = await cost_service.get_cost_consignments(**params)
        return {item["id"] for item in response.data["items"]}

    async def test_flight_date_can_filter_without_warehouse_date(self):
        ids = await self.query_ids(
            start_flight_date="2026-09-20",
            end_flight_date="2026-09-20",
        )

        self.assertEqual(ids, {"1", "3", "5"})

    async def test_warehouse_date_filter_keeps_its_existing_behavior(self):
        ids = await self.query_ids(
            start_warehouse_date="2026-09-20",
            end_warehouse_date="2026-09-20",
        )

        self.assertEqual(ids, {"2", "3"})

    async def test_flight_and_warehouse_date_filters_are_combined(self):
        ids = await self.query_ids(
            start_warehouse_date="2026-09-20",
            end_warehouse_date="2026-09-20",
            start_flight_date="2026-09-20",
            end_flight_date="2026-09-20",
        )

        self.assertEqual(ids, {"3"})
        self.assertEqual(await self.query_ids(
            start_warehouse_date="2026-09-20", end_warehouse_date="2026-09-20",
            start_flight_date="2026-09-21", end_flight_date="2026-09-21",
        ), {"2"})

    async def test_flight_date_supports_independent_one_sided_bounds(self):
        self.assertEqual(
            await self.query_ids(start_flight_date="2026-09-21"),
            {"2", "4"},
        )
        self.assertEqual(
            await self.query_ids(end_flight_date="2026-09-20"),
            {"1", "3", "5"},
        )

    async def test_unfiltered_list_keeps_null_dates_and_filter_does_not_write_dates(self):
        self.assertEqual(await self.query_ids(), {str(i) for i in range(1, 8)})
        self.assertEqual(await self.query_ids(
            start_flight_date="2026-09-19", end_flight_date="2026-09-22",
        ), {str(i) for i in range(1, 6)})
        self.assertIsNone(self.db.get(CostConsignment, 6).flight_date)
        self.assertIsNone(self.db.get(CostConsignment, 7).flight_date)
        self.assertEqual(self.db.get(CostConsignment, 3).pay_intl_air_flight_date, date(2026, 9, 19))
        self.assertFalse(self.db.dirty)

    def test_openapi_marks_both_flight_date_parameters_as_optional(self):
        app = FastAPI()
        app.include_router(cost_service.router, prefix="/cost-service")
        parameters = {
            item["name"]: item
            for item in app.openapi()["paths"]["/cost-service/consignments"]["get"]["parameters"]
        }

        for name in ("start_flight_date", "end_flight_date"):
            with self.subTest(name=name):
                self.assertIn(name, parameters)
                self.assertFalse(parameters[name]["required"])
                self.assertIn("consignor_info.flight_date", parameters[name]["description"])
                self.assertIn("consignor_info.flight_date", CostConsignmentQuery.model_fields[name].description)


class CostServiceMasterDocFilterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        CostConsignment.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.db.add_all([
            CostConsignment(
                id=1, status=0, customer_name="客户A", agent="代理A",
                warehouse_entry_date=date(2026, 11, 1), flight_date=date(2026, 11, 3),
                pay_intl_air_flight_date=date(2026, 11, 1),
                flight_doc_no="货主原值", bill_of_lading="提单原值", flight_no="CZ-TOP",
                pay_intl_air_flight_doc_no="784-12345678", pay_dom_air_flight_doc_no="国内原值",
            ),
            CostConsignment(id=2, status=0, flight_doc_no="784-12345678", pay_intl_air_flight_doc_no="另一个主单号",
                            flight_date=date(2026, 11, 2), pay_dom_air_flight_date=date(2026, 11, 2)),
            CostConsignment(id=3, status=0, pay_dom_air_flight_doc_no="784-12345678"),
            CostConsignment(id=4, status=0, bill_of_lading="784-12345678", pay_intl_air_flight_doc_no=""),
            CostConsignment(id=5, status=0, pay_trucking_flight_doc_no="784-12345678"),
            CostConsignment(
                id=6, status=1, customer_name="客户A", agent="代理A",
                warehouse_entry_date=date(2026, 11, 2), flight_date=date(2026, 11, 1),
                pay_intl_air_flight_date=date(2026, 11, 2),
                pay_intl_air_flight_doc_no="999-12345678", pay_intl_air_flight_no="CZ-INTL",
            ),
            CostConsignment(
                id=7, status=2, customer_name="客户B", agent="代理B",
                warehouse_entry_date=date(2026, 11, 3), flight_date=date(2026, 11, 2),
                pay_intl_air_flight_date=date(2026, 11, 3),
                pay_intl_air_flight_doc_no="888-12345678", pay_dom_air_flight_no="CZ-DOM",
            ),
            CostConsignment(id=8, status=0),
        ])
        self.db.commit()
        app = FastAPI()
        app.include_router(cost_service.router, prefix="/api/v1/cost-service")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=99)
        self.app = app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def query(self, **params):
        response = await self.client.get("/api/v1/cost-service/consignments", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], 0)
        return response.json()["data"]

    async def test_master_doc_only_matches_international_payables_and_preserves_response_fields(self):
        result = await self.query(flight_doc_no="  784-12345678  ")
        self.assertEqual(result["total"], 1)
        self.assertEqual([item["id"] for item in result["items"]], ["1"])
        item = result["items"][0]
        self.assertEqual(item["payables"]["intl_air"]["flight_doc_no"], "784-12345678")
        self.assertEqual(item["consignor_info"]["flight_doc_no"], "货主原值")
        self.assertEqual(item["consignor_info"]["bill_of_lading"], "提单原值")
        self.assertEqual(item["payables"]["dom_air"]["flight_doc_no"], "国内原值")
        self.assertFalse(self.db.dirty)
        self.assertEqual(await self.query(flight_doc_no="不存在的号码"),
                         {"total": 0, "items": [], "page": 1, "pageSize": 10})

    async def test_partial_search_keeps_pagination_total_and_sort_order(self):
        result = await self.query(flight_doc_no="123456", page=1, pageSize=2)
        self.assertEqual(result["total"], 3)
        self.assertEqual([item["id"] for item in result["items"]], ["7", "6"])
        second = await self.query(flight_doc_no="123456", page=2, pageSize=2)
        self.assertEqual(second["total"], 3)
        self.assertEqual([item["id"] for item in second["items"]], ["1"])
        self.assertEqual((second["page"], second["pageSize"]), (2, 2))
        ascending = await self.query(flight_doc_no="123456", sort_order="asc")
        self.assertEqual([item["id"] for item in ascending["items"]], ["1", "6", "7"])

    async def test_missing_empty_and_whitespace_master_doc_do_not_filter(self):
        for params in ({}, {"flight_doc_no": ""}, {"flight_doc_no": "  "}):
            with self.subTest(params=params):
                result = await self.query(**params)
                self.assertEqual(result["total"], 8)
                self.assertEqual({item["id"] for item in result["items"]}, {str(i) for i in range(1, 9)})

    async def test_master_doc_combines_with_other_filters_without_changing_flight_no_search(self):
        for params, expected in (
            ({"status": 0}, {"1"}), ({"status": 1}, {"6"}), ({"status": 2}, {"7"}),
            ({"customer_name": "客户A", "agent": "代理A"}, {"1", "6"}),
            ({"customer_name": "客户A", "agent": "代理B"}, set()),
            ({"start_flight_date": "2026-11-02", "end_flight_date": "2026-11-02"}, {"7"}),
            ({"start_warehouse_date": "2026-11-01", "end_warehouse_date": "2026-11-01"}, {"1"}),
            ({"flight_no": "CZ-TOP"}, {"1"}), ({"flight_no": "CZ-INTL"}, {"6"}),
            ({"flight_no": "CZ-DOM"}, {"7"}),
        ):
            with self.subTest(params=params):
                result = await self.query(flight_doc_no="123456", **params)
                self.assertEqual(result["total"], len(expected))
                self.assertEqual({item["id"] for item in result["items"]}, expected)

    async def test_entrustment_flight_date_boundaries_pagination_and_null_exclusion(self):
        params = {"start_flight_date": "2026-11-01", "end_flight_date": "2026-11-03", "pageSize": 2}
        first = await self.query(**params)
        self.assertEqual(first["total"], 4)
        self.assertEqual([item["id"] for item in first["items"]], ["7", "6"])
        second = await self.query(**params, page=2)
        self.assertEqual(second["total"], 4)
        self.assertEqual([item["id"] for item in second["items"]], ["1", "2"])
        exact = await self.query(start_flight_date="2026-11-02", end_flight_date="2026-11-02")
        self.assertEqual(exact["total"], 2)
        self.assertEqual([item["id"] for item in exact["items"]], ["7", "2"])
        self.assertEqual(exact["items"][0]["payables"]["intl_air"]["flight_date"], "2026-11-03")
        self.assertEqual(exact["items"][0]["consignor_info"]["flight_date"], "2026-11-02")
        self.assertIsNone(exact["items"][1]["payables"]["intl_air"]["flight_date"])
        self.assertEqual(exact["items"][1]["consignor_info"]["flight_date"], "2026-11-02")
        reversed_dates = await self.query(start_flight_date="2026-11-03", end_flight_date="2026-11-01")
        self.assertEqual(reversed_dates, {"total": 0, "items": [], "page": 1, "pageSize": 10})
        self.assertFalse(self.db.dirty)

    async def test_empty_flight_date_bounds_preserve_existing_compatibility(self):
        for params in ({}, {"start_flight_date": "", "end_flight_date": ""},
                       {"start_flight_date": "  ", "end_flight_date": "bad-date"}):
            with self.subTest(params=params):
                self.assertEqual((await self.query(**params))["total"], 8)
        result = await self.query(start_flight_date="bad-date", end_flight_date="2026-11-02")
        self.assertEqual({x["id"] for x in result["items"]}, {"2", "6", "7"})

    def test_openapi_and_query_schema_describe_international_master_doc(self):
        params = {p["name"]: p for p in self.app.openapi()["paths"]["/api/v1/cost-service/consignments"]["get"]["parameters"]}
        self.assertFalse(params["flight_doc_no"]["required"])
        self.assertIn("主单号", params["flight_doc_no"]["description"])
        self.assertIn("payables.intl_air.flight_doc_no", params["flight_doc_no"]["description"])
        self.assertIn("payables.intl_air.flight_doc_no", CostConsignmentQuery.model_fields["flight_doc_no"].description)


if __name__ == "__main__":
    unittest.main()
