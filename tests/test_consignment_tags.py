"""两组勾选项的持久化、客服流转、费用覆盖和提交锁定回归。"""
import unittest
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service, customer_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.main import register_exception_handlers
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.customer_service import ConsignmentInfo, ConsignmentRegistration


CUSTOMER_TAGS = ["intl_air", "customs", "ground", "trucking", "dom_air"]
EXPENSE_TAGS = CUSTOMER_TAGS + ["discount_info", "sales_commission"]
DESKS = tuple(
    (desk, key, tags, model, template, registration)
    for desk, model, template, registration in (
        ("customer-service", ConsignmentInfo, ConsignmentRegistration, "consignment-registration"),
        ("cost-service", CostConsignment, CostRegistration, "cost-registration"),
    )
    for key, tags in (("customer_tags", CUSTOMER_TAGS), ("expense_tags", EXPENSE_TAGS))
)


class ConsignmentTagTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (ConsignmentInfo, ConsignmentRegistration, CostConsignment, CostRegistration, ConsignmentOperationLog):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(customer_service.router, prefix="/api/v1/customer-service")
        app.include_router(cost_service.router, prefix="/api/v1/cost-service")

        async def test_db():
            return self.db

        async def test_user():
            return SimpleNamespace(id=99, name="操作员", permissions=["admin"])

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_active_user] = test_user
        self.app = app
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def request(self, method, path, payload=None):
        response = await self.client.request(method, path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_templates_round_trip_omission_null_and_clear(self):
        for desk, key, tags, _model, template_model, registration in DESKS:
            with self.subTest(desk=desk):
                path = f"/api/v1/{desk}/{registration}"
                # 两组标签属于同一模板；分别保存互不清空。
                data = await self.request("PUT", path, {key: tags})
                self.assertEqual(data[key], tags)
                self.db.expire_all()
                self.assertEqual(getattr(self.db.get(template_model, int(data["id"])), key), tags)
                self.assertEqual((await self.request("GET", path))[key], tags)
                self.assertEqual((await self.request("PUT", path, {}))[key], tags)
                self.assertEqual((await self.request("PUT", path, {key: None}))[key], tags)
                self.assertEqual((await self.request("PUT", path, {key: []}))[key], [])
                self.assertEqual((await self.request("GET", path))[key], [])

    async def test_draft_create_update_submit_detail_list_and_void(self):
        for desk, key, tags, model, _template, _registration in DESKS:
            with self.subTest(desk=desk):
                base = f"/api/v1/{desk}/consignments"
                data = await self.request("POST", base + "/draft", {key: tags})
                record_id = data["id"]
                path = f"{base}/{record_id}"
                self.assertEqual(data[key], tags)
                self.assertEqual(data["status"], 0)
                self.db.expire_all()
                self.assertEqual(getattr(self.db.get(model, int(record_id)), key), tags)
                self.assertEqual((await self.request("GET", path))[key], tags)
                self.assertEqual((await self.request("PUT", path + "/draft", {}))[key], tags)
                self.assertEqual((await self.request("PUT", path + "/draft", {key: None}))[key], tags)
                data = await self.request("PUT", path + "/draft", {key: ["ground", "intl_air", "ground"]})
                self.assertEqual(data[key], ["ground", "intl_air"])
                self.assertEqual((await self.request("PUT", path + "/draft", {key: []}))[key], [])
                data = await self.request("PUT", path, {key: tags})
                self.assertEqual((data["status"], data[key]), (1, tags))
                items = (await self.request("GET", base))["items"]
                self.assertEqual(next(item for item in items if item["id"] == record_id)[key], tags)
                data = await self.request("PUT", path + "/void")
                self.assertEqual((data["status"], data[key]), (2, tags))
                for suffix in ("", "/draft"):
                    response = await self.client.put(path + suffix, json={key: []})
                    self.assertEqual(response.status_code, 409, response.text)
                self.assertEqual((await self.request("GET", path))[key], tags)

    async def test_create_save_and_legacy_null_tags_return_top_level_arrays(self):
        for desk, key, tags, model, template_model, registration in DESKS:
            base = f"/api/v1/{desk}/consignments"
            data = await self.request("POST", base, {key: tags})
            self.assertEqual(data[key], tags)
            self.assertEqual((await self.request("GET", base + "/" + data["id"]))[key], tags)
            data = await self.request("POST", base, {})
            self.assertEqual(data[key], [])
            if self.db.get(model, 123) is None:
                self.db.add(model(id=123))
            if self.db.query(template_model).first() is None:
                self.db.add(template_model(id=123))
            self.db.commit()
            self.assertEqual((await self.request("GET", base + "/123"))[key], [])
            self.assertEqual((await self.request("GET", f"/api/v1/{desk}/{registration}"))[key], [])

    async def test_invalid_payloads_rejected_before_any_write(self):
        for desk, key, tags, model, _template, _registration in DESKS:
            base = f"/api/v1/{desk}/consignments/draft"
            invalid_values = ["intl_air", {"intl_air": True}, [1], [True], [None], ["国际空运"], ["unknown"], tags + [tags[0]]]
            if key == "customer_tags":
                invalid_values.extend([["discount_info"], ["sales_commission"]])
            for value in invalid_values:
                with self.subTest(desk=desk, value=value):
                    response = await self.client.post(base, json={key: value})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(response.json()["code"], 422)
                    self.assertEqual(self.db.query(model).count(), 0)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_customer_both_tags_flow_to_cost_then_cost_can_override_without_reverse_write(self):
        payload = {"customer_tags": ["intl_air", "customs"], "expense_tags": ["ground", "discount_info"]}
        customer = await self.request("POST", "/api/v1/customer-service/consignments/draft", payload)
        record_id = customer["id"]
        customer_path = "/api/v1/customer-service/consignments/" + record_id
        cost_path = "/api/v1/cost-service/consignments/" + record_id
        self.assertIsNone(self.db.get(CostConsignment, int(record_id)))
        await self.request("PUT", customer_path, {})
        detail = await self.request("GET", cost_path)
        for key, tags in payload.items():
            self.assertEqual(detail[key], tags)
        # 费用可修改两个字段，暂存不回写客服。
        changed = {"customer_tags": ["trucking"], "expense_tags": ["sales_commission"]}
        detail = await self.request("PUT", cost_path + "/draft", changed)
        self.db.expire_all()
        for key, tags in changed.items():
            self.assertEqual(detail[key], tags)
            self.assertEqual(getattr(self.db.get(CostConsignment, int(record_id)), key), tags)
        # 费用保存和之后的只读查询均不重置费用覆盖值，客服仍是提交快照。
        await self.request("PUT", cost_path, {})
        for key in payload:
            self.assertEqual((await self.request("GET", customer_path))[key], payload[key])
            self.assertEqual((await self.request("GET", cost_path))[key], changed[key])
        await self.request("PUT", cost_path, {"customer_tags": [], "expense_tags": []})
        detail = await self.request("GET", cost_path)
        self.assertEqual((detail["customer_tags"], detail["expense_tags"]), ([], []))
        self.assertEqual((await self.request("GET", customer_path))["customer_tags"], payload["customer_tags"])

    async def test_saved_new_customer_copies_each_tag_by_name(self):
        customer = await self.request("POST", "/api/v1/customer-service/consignments", {
            "customer_tags": CUSTOMER_TAGS, "expense_tags": EXPENSE_TAGS,
        })
        detail = await self.request("GET", "/api/v1/cost-service/consignments/" + customer["id"])
        self.assertEqual(detail["customer_tags"], CUSTOMER_TAGS)
        self.assertEqual(detail["expense_tags"], EXPENSE_TAGS)
        # 不把customer_tags自动映射成expense_tags，两者保留各自含义。
        customer = await self.request("POST", "/api/v1/customer-service/consignments", {"customer_tags": CUSTOMER_TAGS})
        detail = await self.request("GET", "/api/v1/cost-service/consignments/" + customer["id"])
        self.assertEqual(detail["customer_tags"], CUSTOMER_TAGS)
        self.assertEqual(detail["expense_tags"], [])

    async def test_submit_preserves_absent_tag_and_applies_explicit_empty_tag(self):
        customer = await self.request("POST", "/api/v1/customer-service/consignments/draft", {"expense_tags": []})
        record_id = int(customer["id"])
        self.db.add(CostConsignment(id=record_id, status=0, customer_tags=["ground"], expense_tags=["discount_info"]))
        self.db.commit()
        await self.request("PUT", "/api/v1/customer-service/consignments/" + str(record_id), {"customer_tags": None})
        detail = await self.request("GET", "/api/v1/cost-service/consignments/" + str(record_id))
        self.assertEqual(detail["customer_tags"], ["ground"])
        self.assertEqual(detail["expense_tags"], [])

    async def test_cost_first_creation_and_draft_submission_initialize_customer_tags(self):
        for suffix in ("", "/draft"):
            payload = {"customer_tags": ["dom_air"], "expense_tags": ["sales_commission"]}
            cost = await self.request("POST", "/api/v1/cost-service/consignments" + suffix, payload)
            if suffix:
                self.assertIsNone(self.db.get(ConsignmentInfo, int(cost["id"])))
                await self.request("PUT", "/api/v1/cost-service/consignments/" + cost["id"], {})
            detail = await self.request("GET", "/api/v1/customer-service/consignments/" + cost["id"])
            for key, tags in payload.items():
                self.assertEqual(detail[key], tags)

    async def test_cost_single_field_override_preserves_other_field_and_clear_survives_reads(self):
        data = await self.request("POST", "/api/v1/customer-service/consignments", {
            "customer_tags": ["customs"], "expense_tags": ["discount_info"],
        })
        cost_path = "/api/v1/cost-service/consignments/" + data["id"]
        await self.request("PUT", cost_path + "/draft", {"customer_tags": ["ground"]})
        detail = await self.request("GET", cost_path)
        self.assertEqual((detail["customer_tags"], detail["expense_tags"]), (["ground"], ["discount_info"]))
        detail = await self.request("PUT", cost_path, {"customer_tags": None, "expense_tags": []})
        self.assertEqual((detail["customer_tags"], detail["expense_tags"]), (["ground"], []))
        self.db.expire_all()
        for _ in range(2):
            detail = await self.request("GET", cost_path)
            self.assertEqual((detail["customer_tags"], detail["expense_tags"]), (["ground"], []))
        items = (await self.request("GET", "/api/v1/cost-service/consignments"))["items"]
        item = next(item for item in items if item["id"] == data["id"])
        self.assertEqual((item["customer_tags"], item["expense_tags"]), (["ground"], []))

    async def test_cost_rejects_one_invalid_tag_field_without_saving_other_field(self):
        data = await self.request("POST", "/api/v1/customer-service/consignments", {
            "customer_tags": ["customs"], "expense_tags": ["ground"],
        })
        path = "/api/v1/cost-service/consignments/" + data["id"]
        count = self.db.query(ConsignmentOperationLog).count()
        result = await self.client.put(path + "/draft", json={
            "customer_tags": ["discount_info"], "expense_tags": ["sales_commission"],
        })
        self.assertEqual(result.status_code, 422)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), count)
        detail = await self.request("GET", path)
        self.assertEqual((detail["customer_tags"], detail["expense_tags"]), (["customs"], ["ground"]))

    async def test_customer_submitted_tags_cannot_bypass_lock_or_clear_business_data(self):
        data = await self.request("POST", "/api/v1/customer-service/consignments", {
            "customer_tags": ["intl_air"], "customer_name": "客户", "pieces": 8,
            "receivables": {"customs_fee": 750},
        })
        path = "/api/v1/customer-service/consignments/" + data["id"]
        before = self.db.query(ConsignmentOperationLog).count()
        for suffix in ("", "/draft"):
            response = await self.client.put(path + suffix, json={"customer_tags": [], "expense_tags": [], "status": 0})
            self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)
        detail = await self.request("GET", path)
        self.assertEqual((detail["status"], detail["customer_tags"]), (1, ["intl_air"]))
        self.assertEqual(detail["receivables"]["customs_fee"], 750)
        cost_path = "/api/v1/cost-service/consignments/" + data["id"]
        detail = await self.request("PUT", cost_path + "/draft", {"expense_tags": []})
        self.assertEqual(detail["consignor_info"]["pieces"], 8)
        self.assertEqual(detail["receivables"]["customs_fee"], 750)

    def test_openapi_exposes_tags_at_request_top_level_with_fixed_options(self):
        schemas = self.app.openapi()["components"]["schemas"]
        for model_name in (
            "ConsignmentInfoCreate", "ConsignmentInfoUpdate", "ConsignmentRegistrationSave",
            "CostConsignmentCreate", "CostConsignmentUpdate", "CostRegistrationSave",
        ):
            for key, tags, limit in (("customer_tags", CUSTOMER_TAGS, 5), ("expense_tags", EXPENSE_TAGS, 7)):
                field = schemas[model_name]["properties"][key]
                array = next(item for item in field["anyOf"] if item.get("type") == "array")
                self.assertEqual(array["items"]["enum"], tags)
                self.assertEqual(array["maxItems"], limit)
