"""页面勾选项的持久化、校验、跨台隔离和提交锁定回归。"""
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
DESKS = (
    ("customer-service", "customer_tags", CUSTOMER_TAGS, ConsignmentInfo, ConsignmentRegistration, "consignment-registration"),
    ("cost-service", "expense_tags", EXPENSE_TAGS, CostConsignment, CostRegistration, "cost-registration"),
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
                self.assertIsNone(await self.request("GET", path))
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
            self.db.add(model(id=123, **{key: None}))
            self.db.add(template_model(id=123, **{key: None}))
            self.db.commit()
            self.assertEqual((await self.request("GET", base + "/123"))[key], [])
            self.assertEqual((await self.request("GET", f"/api/v1/{desk}/{registration}"))[key], [])

    async def test_invalid_payloads_rejected_before_any_write(self):
        for desk, key, tags, model, _template, _registration in DESKS:
            base = f"/api/v1/{desk}/consignments/draft"
            invalid_values = ["intl_air", {"intl_air": True}, [1], [True], [None], ["国际空运"], ["unknown"], tags + [tags[0]]]
            if desk == "customer-service":
                invalid_values.extend([["discount_info"], ["sales_commission"]])
            for value in invalid_values:
                with self.subTest(desk=desk, value=value):
                    response = await self.client.post(base, json={key: value})
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertEqual(response.json()["code"], 422)
                    self.assertEqual(self.db.query(model).count(), 0)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_tags_stay_independent_during_both_sync_directions(self):
        customer = await self.request("POST", "/api/v1/customer-service/consignments/draft", {
            "customer_tags": ["intl_air", "customs"],
        })
        record_id = customer["id"]
        customer_path = "/api/v1/customer-service/consignments/" + record_id
        cost_path = "/api/v1/cost-service/consignments/" + record_id
        self.db.add(CostConsignment(id=int(record_id), status=0, expense_tags=["ground", "discount_info"]))
        self.db.commit()
        await self.request("PUT", customer_path, {})
        self.assertEqual((await self.request("GET", cost_path))["expense_tags"], ["ground", "discount_info"])
        await self.request("PUT", cost_path + "/draft", {"expense_tags": EXPENSE_TAGS})
        self.assertEqual((await self.request("GET", customer_path))["customer_tags"], ["intl_air", "customs"])
        await self.request("PUT", cost_path, {"expense_tags": ["sales_commission"]})
        detail = await self.request("GET", customer_path)
        self.assertEqual(detail["customer_tags"], ["intl_air", "customs"])
        self.assertNotIn("expense_tags", detail)
        detail = await self.request("GET", cost_path)
        self.assertEqual(detail["expense_tags"], ["sales_commission"])
        self.assertNotIn("customer_tags", detail)
        cost_created = await self.request("POST", "/api/v1/cost-service/consignments", {"expense_tags": EXPENSE_TAGS})
        detail = await self.request("GET", "/api/v1/customer-service/consignments/" + cost_created["id"])
        self.assertEqual(detail["customer_tags"], [])
        customer_created = await self.request("POST", "/api/v1/customer-service/consignments", {"customer_tags": CUSTOMER_TAGS})
        detail = await self.request("GET", "/api/v1/cost-service/consignments/" + customer_created["id"])
        self.assertEqual(detail["expense_tags"], [])

    async def test_customer_submitted_tags_cannot_bypass_lock_or_clear_business_data(self):
        data = await self.request("POST", "/api/v1/customer-service/consignments", {
            "customer_tags": ["intl_air"], "customer_name": "客户", "pieces": 8,
            "receivables": {"customs_fee": 750},
        })
        path = "/api/v1/customer-service/consignments/" + data["id"]
        before = self.db.query(ConsignmentOperationLog).count()
        for suffix in ("", "/draft"):
            response = await self.client.put(path + suffix, json={"customer_tags": [], "status": 0})
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
        for model_name in ("ConsignmentInfoCreate", "ConsignmentInfoUpdate", "ConsignmentRegistrationSave"):
            field = schemas[model_name]["properties"]["customer_tags"]
            array = next(item for item in field["anyOf"] if item.get("type") == "array")
            self.assertEqual(array["items"]["enum"], CUSTOMER_TAGS)
            self.assertEqual(array["maxItems"], 5)
        for model_name in ("CostConsignmentCreate", "CostConsignmentUpdate", "CostRegistrationSave"):
            field = schemas[model_name]["properties"]["expense_tags"]
            array = next(item for item in field["anyOf"] if item.get("type") == "array")
            self.assertEqual(array["items"]["enum"], EXPENSE_TAGS)
            self.assertEqual(array["maxItems"], 7)
