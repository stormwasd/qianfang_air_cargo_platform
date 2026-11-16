"""两台列表的代理与主单号范围、条件组合及分页契约。"""
import unittest
from datetime import date, datetime
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service, customer_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.cost_service import CostConsignment
from app.models.customer_service import ConsignmentInfo
from app.schemas.cost_service import CostConsignmentQuery
from app.schemas.customer_service import ConsignmentInfoQuery


class ConsignmentSearchContract:
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        # 只创建本台表：客服草稿不要求存在费用单，也不读取另一台数据。
        self.model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        agents = (
            ("intl_air", "outsource_unit", "国际北京翼速"),
            ("customs", "agent", "报关北京翼速"),
            ("ground", "outsource_unit", "地面北京翼速"),
            ("trucking", "outsource_unit", "汽运北京翼速"),
            ("dom_air", "outsource_unit", "国内北京翼速"),
        )
        for index, (group, field, name) in enumerate(agents, start=1):
            payables = {group: {field: name}}
            doc_no = None
            if index == 1:
                doc_no = "TOP-731-90161013"
            elif index == 2:
                payables["intl_air"] = {"flight_doc_no": "INTL-731-90161013"}
            elif index == 3:
                payables["dom_air"] = {"flight_doc_no": "DOM-731-90161013"}
            elif index == 4:
                payables["trucking"]["flight_doc_no"] = "ROAD-731-90161013"
            else:
                doc_no = "ALL-731-90161013"
                for section in ("intl_air", "dom_air", "trucking"):
                    payables.setdefault(section, {})["flight_doc_no"] = doc_no
                # 同票多处代理命中只能计数一次。
                payables["intl_air"]["outsource_unit"] = "国际北京翼速"
            self.add_record(
                index, payables=payables, flight_doc_no=doc_no,
                status=0 if index == 1 else 2 if index == 5 else 1,
            )
        self.add_record(
            6, agent="北京翼速", bill_of_lading="731-90161013",
            internal_doc_id="731-90161013", remark="北京翼速 731-90161013",
        )
        self.add_record(7, payables=None)
        self.add_record(8, payables={})
        self.add_record(9, payables={group: None for group, _, _ in agents})
        self.add_record(10, payables={
            group: {field: None, **({"flight_doc_no": None} if group in ("intl_air", "dom_air", "trucking") else {})}
            for group, field, _ in agents
        })
        self.add_record(11, payables={"intl_air": {
            "outsource_unit": "AbC'_%/航司", "flight_doc_no": "AbC'_%/尾号",
        }})
        self.db.commit()
        app = FastAPI()
        app.include_router(self.router, prefix=self.prefix)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=99)
        self.app = app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    def add_record(self, index, *, payables=None, **values):
        record = self.model(
            id=index, customer_name="客户A" if index < 4 else "客户B",
            create_time=datetime(2026, 11, index), warehouse_entry_date=date(2026, 11, index),
            **values,
        )
        if self.model is ConsignmentInfo:
            record.financial_data = {"payables": payables} if payables is not None else None
        elif payables:
            # 测试独立定义公共字段与费用存储的对应关系。
            for group, data in payables.items():
                for field, value in (data or {}).items():
                    setattr(record, f"pay_{group}_{field}", value)
        self.db.add(record)

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def query(self, **params):
        response = await self.client.get(f"{self.prefix}/consignments", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], 0)
        return response.json()["data"]

    async def assert_ids(self, expected, **params):
        result = await self.query(**params)
        self.assertEqual(result["total"], len(expected))
        self.assertEqual({item["id"] for item in result["items"]}, {str(i) for i in expected})

    async def test_all_five_payable_agent_inputs_are_searchable(self):
        for keyword, expected in (
            ("国际北京翼速", {1, 5}), ("报关北京翼速", {2}), ("地面北京翼速", {3}),
            ("汽运北京翼速", {4}), ("国内北京翼速", {5}), ("  北京翼速  ", {1, 2, 3, 4, 5}),
        ):
            with self.subTest(keyword=keyword):
                await self.assert_ids(expected, agent=keyword)
        # id6仅委托代理及备注命中，必须排除。

    async def test_all_four_master_doc_inputs_are_searchable(self):
        for keyword, expected in (
            ("TOP-", {1}), ("INTL-", {2}), ("DOM-", {3}), ("ROAD-", {4}),
            ("ALL-", {5}), (" 731-90161013 ", {1, 2, 3, 4, 5}),
        ):
            with self.subTest(keyword=keyword):
                await self.assert_ids(expected, flight_doc_no=keyword)
        # id6仅提单、内部ID及备注命中，必须排除。

    async def test_agent_and_master_doc_are_independent_and_combined_with_other_filters(self):
        await self.assert_ids({2}, agent="报关北京翼速", flight_doc_no="INTL-")
        await self.assert_ids(set(), agent="报关北京翼速", flight_doc_no="ROAD-")
        await self.assert_ids({1, 2, 3}, agent="北京翼速", flight_doc_no="731", customer_name="客户A")
        for status, expected in ((0, {1}), (1, {2, 3, 4}), (2, {5})):
            await self.assert_ids(expected, agent="北京翼速", flight_doc_no="731", status=status)
        bounds = {"start_date": "2026-11-02", "end_date": "2026-11-03"} if self.model is ConsignmentInfo else {
            "start_warehouse_date": "2026-11-02", "end_warehouse_date": "2026-11-03",
        }
        await self.assert_ids({2, 3}, agent="北京翼速", flight_doc_no="731", **bounds)

    async def test_pagination_counts_distinct_records_after_both_or_filters(self):
        params = {"agent": "北京翼速", "flight_doc_no": "731", "pageSize": 2}
        for page, expected in ((1, [5, 4]), (2, [3, 2]), (3, [1])):
            result = await self.query(**params, page=page)
            self.assertEqual(result["total"], 5)
            self.assertEqual([item["id"] for item in result["items"]], [str(i) for i in expected])
        result = await self.query(**params, sort_order="asc")
        self.assertEqual([item["id"] for item in result["items"]], ["1", "2"])

    async def test_empty_filters_and_missing_or_null_json_fields(self):
        for params in ({}, {"agent": "", "flight_doc_no": ""}, {"agent": " \t ", "flight_doc_no": " \t "}):
            self.assertEqual((await self.query(**params))["total"], 11)
        for field in ("agent", "flight_doc_no"):
            for keyword in ("null", "不存在", "' OR 1=1 --"):
                with self.subTest(field=field, keyword=keyword):
                    self.assertEqual(await self.query(**{field: keyword}), {
                        "total": 0, "items": [], "page": 1, "pageSize": 10,
                    })

    async def test_case_insensitivity_and_existing_wildcard_semantics(self):
        for field in ("agent", "flight_doc_no"):
            for keyword in ("abc", "_", "%", "'_%/", "  aBc  "):
                with self.subTest(field=field, keyword=keyword):
                    expected = {1, 2, 3, 4, 5, 11} if self.model is CostConsignment and keyword in ("_", "%") else {11}
                    await self.assert_ids(expected, **{field: keyword})

    async def test_search_does_not_modify_values_or_edit_locks(self):
        result = await self.query(agent="报关北京翼速", flight_doc_no="INTL-")
        item = result["items"][0]
        top = item if self.model is ConsignmentInfo else item["consignor_info"]
        self.assertIn(top["flight_doc_no"], (None, ""))
        self.assertEqual(item["payables"]["intl_air"]["flight_doc_no"], "INTL-731-90161013")
        self.assertEqual(item["payables"]["customs"]["agent"], "报关北京翼速")
        self.assertEqual(item["status"], 1)
        self.assertIsNone(self.db.get(self.model, 2).flight_doc_no)
        self.assertFalse(self.db.dirty)
        self.assertFalse(self.db.new)

    def test_openapi_and_query_schema_describe_both_optional_filters(self):
        parameters = {p["name"]: p for p in self.app.openapi()["paths"][f"{self.prefix}/consignments"]["get"]["parameters"]}
        for name in ("agent", "flight_doc_no"):
            self.assertFalse(parameters[name]["required"])
            self.assertIsNone(self.query_schema.model_fields[name].default)
            self.assertEqual(parameters[name]["description"], self.query_schema.model_fields[name].description)
        for group in ("intl_air", "dom_air", "trucking"):
            self.assertIn(f"payables.{group}.flight_doc_no", parameters["flight_doc_no"]["description"])
        for group in ("国际空运", "报关", "地面操作", "汽运", "国内空运"):
            self.assertIn(group, parameters["agent"]["description"])


class CustomerConsignmentSearchTests(ConsignmentSearchContract, unittest.IsolatedAsyncioTestCase):
    model = ConsignmentInfo
    router = customer_service.router
    prefix = "/api/v1/customer-service"
    query_schema = ConsignmentInfoQuery


class CostConsignmentSearchTests(ConsignmentSearchContract, unittest.IsolatedAsyncioTestCase):
    model = CostConsignment
    router = cost_service.router
    prefix = "/api/v1/cost-service"
    query_schema = CostConsignmentQuery


if __name__ == "__main__":
    unittest.main()
