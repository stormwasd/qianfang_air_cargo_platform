import unittest
from datetime import date, datetime

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service
from app.models.cost_service import CostConsignment
from app.schemas.cost_service import CostConsignmentSortField, CostConsignmentSortOrder


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
                customer_name="航班日期匹配",
            ),
            CostConsignment(
                id=2,
                create_time=datetime(2026, 9, 2, 8, 0),
                warehouse_entry_date=date(2026, 9, 20),
                flight_date=date(2026, 9, 21),
                customer_name="仅进仓日期匹配",
            ),
            CostConsignment(
                id=3,
                create_time=datetime(2026, 9, 3, 8, 0),
                warehouse_entry_date=date(2026, 9, 20),
                flight_date=date(2026, 9, 20),
                customer_name="两个日期均匹配",
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

        self.assertEqual(ids, {"1", "3"})

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

    async def test_flight_date_supports_independent_one_sided_bounds(self):
        self.assertEqual(
            await self.query_ids(start_flight_date="2026-09-21"),
            {"2", "4"},
        )
        self.assertEqual(
            await self.query_ids(end_flight_date="2026-09-20"),
            {"1", "3"},
        )

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


if __name__ == "__main__":
    unittest.main()
