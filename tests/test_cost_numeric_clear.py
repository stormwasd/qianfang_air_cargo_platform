"""费用数值清空的持久化、返回、同步、导出和回滚回归。"""
import io
import unittest
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service, customer_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.main import register_exception_handlers
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.customer_service import ConsignmentInfo
from app.schemas.cost_service import CostRegistrationSave
from app.models.user import User
from app.services.consignment_financial import FINANCIAL_FIELD_MAP
from app.services.cost_excel_export import COST_EXPORT_COLUMNS


def numeric_fields():
    """遍历公开的可空数值叶字段，避免只覆盖截图中的单一报关费。"""
    result = []
    schema = CostRegistrationSave
    for path, fields in FINANCIAL_FIELD_MAP.items():
        section = schema
        for key in path.split("."):
            section = next(t for t in section.model_fields[key].annotation.__args__ if t is not type(None))
        for name, column in fields.items():
            if any(t in (int, float) for t in getattr(section.model_fields[name].annotation, "__args__", ())):
                result.append((path + "." + name, column))
    result.extend(("consignor_info." + name, name) for name in (
        "pieces", "actual_weight", "chargeable_weight", "volume", "first_leg_weight",
    ))
    result.extend((
        ("discount_info.discount_rate", "discount_rate"),
        ("discount_info.discount_fee", "discount_fee"),
        ("sales_commission.commission_amount", "commission_amount"),
        ("operating_info.profit", "profit"),
        ("operating_info.profit_margin", "profit_margin"),
    ))
    return result


def put_path(data, path, value):
    parts = path.split(".")
    for key in parts[:-1]:
        data = data.setdefault(key, {})
    data[parts[-1]] = value


def get_path(data, path):
    for key in path.split("."):
        data = data[key]
    return data


class CostNumericClearTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (CostConsignment, CostRegistration, ConsignmentInfo, ConsignmentOperationLog, User):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(cost_service.router, prefix="/cost")
        app.include_router(customer_service.router, prefix="/customer")

        async def test_db():
            try:
                yield self.db
            except Exception:
                self.db.rollback()
                raise

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=99, name="费用操作员")
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def request(self, method, path, body=None):
        response = await self.client.request(method, path, json=body)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], 0)
        return response.json()["data"]

    async def test_reported_customs_fee_clear_persists_in_save_detail_list_customer_and_excel(self):
        self.db.add_all([
            CostConsignment(id=1, status=0, receivable_customs_fee=33, receivable_consumables_fee=2,
                            receivable_total=118, pay_total=0, profit=118),
            ConsignmentInfo(id=1, status=1, edit_locked=False,
                            financial_data={"receivables": {"customs_fee": 33}}),
        ])
        self.db.commit()
        path = "/cost/consignments/1"
        saved = await self.request("PUT", path, {"receivables": {"customs_fee": None}})
        self.assertIsNone(saved["receivables"]["customs_fee"])
        self.assertEqual(saved["receivables"]["consumables_fee"], 2)
        # 本次修复只保存前端传值，不重算合计和利润。
        self.assertEqual(saved["receivables"]["total"], 118)
        self.assertEqual(saved["operating_info"]["profit"], 118)
        self.db.expire_all()
        self.assertIsNone(self.db.get(CostConsignment, 1).receivable_customs_fee)
        self.assertIsNone((await self.request("GET", path))["receivables"]["customs_fee"])
        listing = await self.request("GET", "/cost/consignments")
        self.assertIsNone(listing["items"][0]["receivables"]["customs_fee"])
        customer = await self.request("GET", "/customer/consignments/1")
        self.assertIsNone(customer["receivables"]["customs_fee"])
        self.assertFalse(customer["editable"])
        response = await self.client.post("/cost/consignments/export-excel", json={"ids": ["1"]})
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(io.BytesIO(response.content))
        column = next(i for i, c in enumerate(COST_EXPORT_COLUMNS, 1) if c.path == "receivables.customs_fee")
        self.assertIsNone(workbook.active.cell(2, column).value)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 1)

    async def test_all_numeric_leaf_fields_preserve_omitted_clear_null_and_save_zero(self):
        fields = numeric_fields()
        self.assertGreater(len(fields), 80)
        payload = {}
        for path, _ in fields:
            put_path(payload, path, 4)
        payload.update({"customer_tags": ["ground"], "expense_tags": [
            "intl_air", "customs", "ground", "trucking", "dom_air", "discount_info", "sales_commission",
        ]})
        payload["consignor_info"].update({"flight_no": "CZ1234", "flight_date": "2026-11-26", "remark": "保留备注"})
        created = await self.request("POST", "/cost/consignments/draft", payload)
        path = "/cost/consignments/" + created["id"]
        for body in ({}, {"consignor_info": {}, "receivables": {}, "payables": {"ground": {}}},
                     {"consignor_info": None, "receivables": None, "payables": None,
                      "discount_info": None, "sales_commission": None, "operating_info": None}):
            data = await self.request("PUT", path + "/draft", body)
            for leaf, column in fields:
                with self.subTest(leaf=leaf, body=body):
                    self.assertEqual(get_path(data, leaf), 4)
                    self.assertEqual(getattr(self.db.get(CostConsignment, int(created["id"])), column), 4)
        for value, suffix in ((None, "/draft"), (0, ""), (7, "/draft"), (None, "")):
            body = {}
            for leaf, _ in fields:
                put_path(body, leaf, value)
            data = await self.request("PUT", path + suffix, body)
            self.db.expire_all()
            stored = self.db.get(CostConsignment, int(created["id"]))
            for leaf, column in fields:
                with self.subTest(leaf=leaf, value=value):
                    self.assertEqual(get_path(data, leaf), value)
                    self.assertEqual(getattr(stored, column), value)
            self.assertEqual(stored.flight_date, date(2026, 11, 26))
            self.assertEqual(stored.flight_no, "CZ1234")
            self.assertEqual(stored.remark, "保留备注")

    async def test_template_clear_and_direct_creation_share_numeric_contract(self):
        for method, target in (("PUT", "/cost/cost-registration"), ("POST", "/cost/consignments"),
                               ("POST", "/cost/consignments/draft")):
            created = await self.request(method, target, {"receivables": {"customs_fee": 33, "total": 100}})
            path = target if method == "PUT" else "/cost/consignments/" + created["id"] + "/draft"
            await self.request("PUT", path, {"receivables": {"customs_fee": None}})
            detail_path = target if method == "PUT" else "/cost/consignments/" + created["id"]
            result = await self.request("GET", detail_path)
            self.assertIsNone(result["receivables"]["customs_fee"])
            self.assertEqual(result["receivables"]["total"], 100)
        for suffix in ("", "/draft"):
            created = await self.request("POST", "/cost/consignments" + suffix, {"receivables": {"customs_fee": None}})
            self.assertIsNone(created["receivables"]["customs_fee"])

    async def test_omitted_or_null_module_and_tag_changes_do_not_clear_hidden_values(self):
        created = await self.request("POST", "/cost/consignments/draft", {
            "expense_tags": ["customs"], "payables": {"customs": {"customs_fee": 33, "subtotal": 50}},
            "receivables": {"customs_fee": 33},
        })
        path = "/cost/consignments/" + created["id"]
        for body in ({"expense_tags": []}, {"payables": None}, {"payables": {}},
                     {"payables": {"customs": None}}, {"payables": {"customs": {}}}):
            result = await self.request("PUT", path + "/draft", body)
            self.assertNotIn("customs", result["payables"])
            self.assertEqual(self.db.get(CostConsignment, int(created["id"])).pay_customs_fee, 33)
        await self.request("PUT", path + "/draft", {"payables": {"customs": {"customs_fee": None}}})
        restored = await self.request("PUT", path + "/draft", {"expense_tags": ["customs"]})
        self.assertIsNone(restored["payables"]["customs"]["customs_fee"])
        self.assertEqual(restored["payables"]["customs"]["subtotal"], 50)
        self.assertEqual(restored["receivables"]["customs_fee"], 33)

    async def test_failed_clear_rolls_back_value_customer_snapshot_lock_and_log(self):
        self.db.add_all([
            CostConsignment(id=1, status=0, receivable_customs_fee=33),
            ConsignmentInfo(id=1, status=1, edit_locked=False,
                            financial_data={"receivables": {"customs_fee": 33}}),
        ])
        self.db.commit()
        snapshot = deepcopy(self.db.get(ConsignmentInfo, 1).financial_data)
        with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
            response = await self.client.put("/cost/consignments/1", json={"receivables": {"customs_fee": None}})
        self.assertEqual(response.status_code, 500)
        self.db.expire_all()
        self.assertEqual(self.db.get(CostConsignment, 1).receivable_customs_fee, 33)
        self.assertEqual(self.db.get(ConsignmentInfo, 1).financial_data, snapshot)
        self.assertFalse(self.db.get(ConsignmentInfo, 1).edit_locked)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        result = await self.request("PUT", "/cost/consignments/1", {"receivables": {"customs_fee": None}})
        self.assertIsNone(result["receivables"]["customs_fee"])

    async def test_invalid_numeric_empty_string_does_not_write_and_salesperson_percentage_is_preserved(self):
        self.db.add(CostConsignment(id=1, status=0, receivable_customs_fee=33,
                                    salesperson="张三", commission_percentage=12.5, commission_amount=88))
        self.db.commit()
        response = await self.client.put("/cost/consignments/1", json={"receivables": {"customs_fee": ""}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.get(CostConsignment, 1).receivable_customs_fee, 33)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        saved = await self.request("PUT", "/cost/consignments/1/draft", {
            "sales_commission": {"commission_amount": None, "salesperson": None},
        })
        self.assertIsNone(saved["sales_commission"]["commission_amount"])
        self.assertEqual(saved["sales_commission"]["salesperson"], "张三")
        self.assertEqual(saved["sales_commission"]["commission_percentage"], 12.5)

    def test_clearing_one_numeric_leaf_does_not_clear_any_other_numeric_value(self):
        fields = numeric_fields()
        for model in (CostConsignment, CostRegistration):
            for leaf, column in fields:
                with self.subTest(model=model.__name__, leaf=leaf):
                    record = model(**{name: 4 for _, name in fields})
                    body = {}
                    put_path(body, leaf, None)
                    cost_service._apply_cost_payload(record, CostRegistrationSave.model_validate(body))
                    self.assertIsNone(getattr(record, column))
                    for _, other in fields:
                        if other != column:
                            self.assertEqual(getattr(record, other), 4, other)


if __name__ == "__main__":
    unittest.main()
