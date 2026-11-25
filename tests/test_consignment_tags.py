"""两组勾选项的持久化、客服流转、费用覆盖和提交锁定回归。"""
import unittest
from copy import deepcopy
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
from app.services.cost_excel_export import (
    CUSTOMER_EXPORT_COLUMNS, COST_EXPORT_COLUMNS, customer_export_values, cost_export_values,
)


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
        await self.request("PUT", "/api/v1/cost-service/consignments/" + data["id"], {})
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

    @staticmethod
    def module_payload(desk):
        payload = {
            "customer_tags": CUSTOMER_TAGS,
            "expense_tags": EXPENSE_TAGS,
            "receivables": {"customs_fee": 750, "total": 1800},
            "payables": {
                group: {"subtotal": index * 10, "remark": f"保留{group}"}
                for index, group in enumerate(CUSTOMER_TAGS, 1)
            },
        }
        payload["payables"]["pay_total"] = 1234.5
        if desk == "cost-service":
            payload.update({
                "discount_info": {"discount_person": "折让人", "discount_rate": 2, "discount_fee": 20},
                "sales_commission": {"commission_amount": 0},
                "operating_info": {"profit": 200, "profit_margin": 10},
            })
        return payload

    def assert_modules(self, data, selected):
        self.assertEqual(set(data["payables"]) & set(CUSTOMER_TAGS), set(selected) & set(CUSTOMER_TAGS))
        self.assertEqual(data["payables"]["pay_total"], 1234.5)
        self.assertEqual(data["receivables"]["customs_fee"], 750)
        self.assertEqual(data["receivables"]["total"], 1800)
        for group in set(selected) & set(CUSTOMER_TAGS):
            self.assertEqual(data["payables"][group]["remark"], f"保留{group}")

    async def test_each_desk_uses_own_tags_for_create_detail_list_save_and_void_responses(self):
        for desk, key, other in (
            ("customer-service", "customer_tags", "expense_tags"),
            ("cost-service", "expense_tags", "customer_tags"),
        ):
            with self.subTest(desk=desk):
                base = f"/api/v1/{desk}/consignments"
                payload = self.module_payload(desk)
                payload[key] = ["intl_air", "ground"]
                # 另一组即使全选也不控制本台返回。
                created = await self.request("POST", base + "/draft", payload)
                self.assert_modules(created, ["intl_air", "ground"])
                self.assertEqual(created[other], payload[other])
                path = f"{base}/{created['id']}"
                for data in (
                    await self.request("GET", path),
                    next(item for item in (await self.request("GET", base))["items"] if item["id"] == created["id"]),
                    await self.request("PUT", path + "/draft", {}),
                    await self.request("PUT", path, {}),
                    await self.request("PUT", path + "/void"),
                ):
                    self.assert_modules(data, ["intl_air", "ground"])
                    if desk == "cost-service":
                        self.assertNotIn("discount_info", data)
                        self.assertNotIn("sales_commission", data)
                        self.assertEqual(data["operating_info"]["profit"], 200)

    async def test_deselect_omitted_modules_preserves_storage_and_reselect_restores_every_module(self):
        for desk, key, model, all_tags in (
            ("customer-service", "customer_tags", ConsignmentInfo, CUSTOMER_TAGS),
            ("cost-service", "expense_tags", CostConsignment, EXPENSE_TAGS),
        ):
            with self.subTest(desk=desk):
                base = f"/api/v1/{desk}/consignments"
                created = await self.request("POST", base + "/draft", self.module_payload(desk))
                path = f"{base}/{created['id']}"
                record = self.db.get(model, int(created["id"]))
                original_snapshot = deepcopy(record.financial_data) if desk == "customer-service" else None
                for tag in all_tags:
                    # 前端只传标签，不传未选中模块的数据。
                    updated = await self.request("PUT", path + "/draft", {key: [tag]})
                    self.assert_modules(updated, [tag])
                    if desk == "cost-service":
                        self.assertEqual("discount_info" in updated, tag == "discount_info")
                        self.assertEqual("sales_commission" in updated, tag == "sales_commission")
                    self.db.expire_all()
                    record = self.db.get(model, int(created["id"]))
                    if desk == "customer-service":
                        self.assertEqual(record.financial_data, original_snapshot)
                    else:
                        self.assertEqual(record.pay_trucking_remark, "保留trucking")
                        self.assertEqual(record.discount_person, "折让人")
                        self.assertEqual(record.commission_amount, 0)
                self.assert_modules(await self.request("PUT", path + "/draft", {key: []}), [])
                self.assert_modules(await self.request("GET", path), [])
                for patch in ({}, {key: None}):
                    self.assert_modules(await self.request("PUT", path + "/draft", patch), [])
                restored = await self.request("PUT", path + "/draft", {key: all_tags})
                self.assert_modules(restored, all_tags)
                if desk == "cost-service":
                    self.assertEqual(restored["discount_info"]["discount_fee"], 20)
                    self.assertEqual(restored["sales_commission"]["commission_amount"], 0)

    async def test_legacy_unset_tags_preserve_all_modules_even_when_other_tags_are_empty(self):
        for desk, key, other, model in (
            ("customer-service", "customer_tags", "expense_tags", ConsignmentInfo),
            ("cost-service", "expense_tags", "customer_tags", CostConsignment),
        ):
            payload = self.module_payload(desk)
            del payload[key]
            payload[other] = []
            base = f"/api/v1/{desk}/consignments"
            created = await self.request("POST", base + "/draft", payload)
            self.assert_modules(created, CUSTOMER_TAGS)
            self.assertEqual(created[key], [])
            record = self.db.get(model, int(created["id"]))
            self.assertIsNone(getattr(record, key))
            path = f"{base}/{created['id']}"
            self.assert_modules(await self.request("PUT", path + "/draft", {key: None}), CUSTOMER_TAGS)
            self.assert_modules(await self.request("PUT", path + "/draft", {key: []}), [])
            self.assert_modules(await self.request("GET", path), [])

    async def test_template_responses_follow_tags_and_keep_unselected_business_data(self):
        for desk, key, registration in (
            ("customer-service", "customer_tags", "consignment-registration"),
            ("cost-service", "expense_tags", "cost-registration"),
        ):
            path = f"/api/v1/{desk}/{registration}"
            self.assertIsNone(await self.request("GET", path))
            payload = self.module_payload(desk)
            payload[key] = ["ground"]
            self.assert_modules(await self.request("PUT", path, payload), ["ground"])
            self.assert_modules(await self.request("GET", path), ["ground"])
            self.assert_modules(await self.request("PUT", path, {key: []}), [])
            self.assert_modules(await self.request("PUT", path, {key: CUSTOMER_TAGS}), CUSTOMER_TAGS)

    async def test_customer_cost_flow_uses_each_saved_tag_set_without_mutating_financial_snapshot(self):
        payload = self.module_payload("customer-service")
        payload["customer_tags"] = ["intl_air", "ground"]
        payload["expense_tags"] = ["trucking"]
        created = await self.request("POST", "/api/v1/customer-service/consignments", payload)
        customer_path = "/api/v1/customer-service/consignments/" + created["id"]
        cost_path = "/api/v1/cost-service/consignments/" + created["id"]
        self.assert_modules(created, ["intl_air", "ground"])
        self.assert_modules(await self.request("GET", cost_path), ["trucking"])
        self.assert_modules(await self.request("PUT", cost_path + "/draft", {"expense_tags": ["customs"]}), ["customs"])
        self.assert_modules(await self.request("GET", customer_path), ["intl_air", "ground"])
        saved = await self.request("PUT", cost_path, {})
        self.assert_modules(saved, ["customs"])
        customer = await self.request("GET", customer_path)
        self.assert_modules(customer, ["intl_air", "ground"])
        self.assertFalse(customer["editable"])
        stored = self.db.get(ConsignmentInfo, int(created["id"]))
        self.assertEqual(stored.financial_data["payables"]["trucking"]["remark"], "保留trucking")
        logs_before = self.db.query(ConsignmentOperationLog).count()
        updated_before = stored.updated_at
        for _ in range(2):
            await self.request("GET", customer_path)
            await self.request("GET", cost_path)
        self.assertFalse(self.db.dirty)
        self.assertEqual(stored.updated_at, updated_before)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), logs_before)

    async def test_filtering_does_not_crop_excel_values_or_stored_data(self):
        for desk, key, model, columns, export in (
            ("customer-service", "customer_tags", ConsignmentInfo, CUSTOMER_EXPORT_COLUMNS, customer_export_values),
            ("cost-service", "expense_tags", CostConsignment, COST_EXPORT_COLUMNS, cost_export_values),
        ):
            payload = self.module_payload(desk)
            payload[key] = []
            created = await self.request("POST", f"/api/v1/{desk}/consignments/draft", payload)
            self.assert_modules(created, [])
            record = self.db.get(model, int(created["id"]))
            before = export(record, 1)
            for group in CUSTOMER_TAGS:
                index = next(i for i, c in enumerate(columns) if c.path == f"payables.{group}.remark")
                self.assertEqual(before[index], f"保留{group}")
            await self.request("GET", f"/api/v1/{desk}/consignments/{created['id']}")
            self.assertEqual(export(record, 1), before)
            self.assertFalse(self.db.dirty)

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
