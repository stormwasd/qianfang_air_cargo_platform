"""隔离数据库验证客户新增录入、完整流转、提交锁定及下载内容。"""
import io
import unittest
from copy import deepcopy
from decimal import Decimal
from datetime import date, datetime
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import customer_service, cost_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.consignment_number_guard import ConsignmentNumberGuard
from app.models.customer_service import ConsignmentInfo, ConsignmentRegistration
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.services.consignment_financial import FINANCIAL_FIELD_MAP
from app.main import register_exception_handlers


FINANCIAL = {
    "receivables": {
        "buy_order_fee": 300, "document_fee": 150, "customs_fee": 750,
        "fuel_rate": 0.65, "fuel_weight_method": "1", "receivable_fuel_fee": 65,
        "tc_rate": 0.3, "tc_express_fee": 36, "front_warehouse_rate": 0.2,
        "warehouse_ground_fee": 24, "remark": "应收单独备注",
    },
    "payables": {
        "intl_air": {
            "outsource_unit": "国际代理", "weight": 105, "flight_doc_no": "999-00000001",
            "buy_order_fee": 280, "document_fee": 140, "customs_fee": 700,
            "fuel_rate": 0.5, "fuel_weight_method": "2", "borrow_magnetic_fuel_pickup_fee": 60,
            "tc_rate": 0.25, "tc_network_disposal_fee": 30,
            "front_warehouse_rate": 0.1, "front_warehouse": 12,
            "flight_date": "2026-10-30", "remark": "国际备注",
        },
        "customs": {"agent": "报关代理", "buy_order_fee": 260, "document_fee": 130, "customs_fee": 650},
        "ground": {"rate": 0.12, "freight": 14.4, "tc_rate": 0.15, "tc_fee": 18, "pickup_fee": 0},
        "trucking": {"flight_doc_no": "ROAD-001", "origin_city": "广州", "destination_city": "深圳", "weight": 120, "freight_method": "计费重"},
        "dom_air": {"volume": 1.234},
        "pay_total": 1784.4,
    },
}


class ConsignmentFinancialFieldsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (ConsignmentInfo, ConsignmentRegistration, CostConsignment, CostRegistration, ConsignmentOperationLog, ConsignmentNumberGuard):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(customer_service.router, prefix="/customer")
        app.include_router(cost_service.router, prefix="/cost")

        async def get_test_db():
            return self.db

        async def get_test_user():
            return SimpleNamespace(id=99, name="操作员")

        app.dependency_overrides[get_db] = get_test_db
        app.dependency_overrides[get_current_active_user] = get_test_user
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def request(self, method, path, payload=None):
        response = await self.client.request(method, path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_entrustment_flight_no_templates_and_create_routes_sync_international(self):
        for base, template in (("/customer", "/consignment-registration"), ("/cost", "/cost-registration")):
            body = {"flight_no": "CZ1001"} if base == "/customer" else {"consignor_info": {"flight_no": "CZ1001"}}
            body.update({"payables": {
                "intl_air": {"flight_no": "旧国际航班", "remark": "保留国际备注"},
                "dom_air": {"flight_no": "MU2002"},
            }})
            for method, path in (("PUT", base + template),
                                 ("POST", base + "/consignments/draft"),
                                 ("POST", base + "/consignments")):
                result = await self.request(method, path, body)
                saved_path = path if method == "PUT" else base + "/consignments/" + result["id"]
                self.db.expire_all()
                for data in (result, await self.request("GET", saved_path)):
                    info = data if base == "/customer" else data["consignor_info"]
                    self.assertEqual(info["flight_no"], "CZ1001")
                    self.assertEqual(data["payables"]["intl_air"]["flight_no"], "CZ1001")
                    self.assertEqual(data["payables"]["intl_air"]["remark"], "保留国际备注")
                    self.assertEqual(data["payables"]["dom_air"]["flight_no"], "MU2002")
                if method == "POST":
                    counterpart = CostConsignment if base == "/customer" else ConsignmentInfo
                    if path.endswith("/draft"):
                        self.assertIsNone(self.db.get(counterpart, int(result["id"])))
                    else:
                        other_base = "/cost" if base == "/customer" else "/customer"
                        other = await self.request("GET", other_base + "/consignments/" + result["id"])
                        info = other["consignor_info"] if other_base == "/cost" else other
                        self.assertEqual(info["flight_no"], "CZ1001")
                        self.assertEqual(other["payables"]["intl_air"]["flight_no"], "CZ1001")

    async def test_entrustment_flight_no_partial_sync_priority_empty_null_and_independent_edit(self):
        for base in ("/customer", "/cost"):
            def body(flight_no):
                return {"flight_no": flight_no} if base == "/customer" else {"consignor_info": {"flight_no": flight_no}}

            def both(top, international):
                return {**body(top), "payables": {"intl_air": {"flight_no": international}}}

            created = await self.request("POST", base + "/consignments/draft", body("CZ1001"))
            path = base + "/consignments/" + created["id"]
            for patch, expected_top, expected_international in (
                ({}, "CZ1001", "CZ1001"),
                ({"payables": {"intl_air": {"flight_no": "MU2002"}}}, "CZ1001", "MU2002"),
                (both(None, "MU2003"), "CZ1001", "MU2003"),
                (both("CZ1002", "旧页面提交的国际值"), "CZ1002", "CZ1002"),
                (both("", "旧页面提交的国际值"), "", ""),
                (body(None), "", ""),
                ({"payables": None}, "", ""),
                ({**body("CZ1003"), "payables": {"intl_air": None}}, "CZ1003", "CZ1003"),
            ):
                result = await self.request("PUT", path + "/draft", patch)
                self.db.expire_all()
                detail = await self.request("GET", path)
                listing = await self.request("GET", base + "/consignments")
                item = next(item for item in listing["items"] if item["id"] == created["id"])
                for data in (result, detail, item):
                    info = data if base == "/customer" else data["consignor_info"]
                    self.assertEqual(info["flight_no"], expected_top)
                    self.assertEqual(data["payables"]["intl_air"]["flight_no"], expected_international)
            result = await self.request("PUT", path, body("CZ1004"))
            self.assertEqual(result["payables"]["intl_air"]["flight_no"], "CZ1004")

    async def test_entrustment_flight_no_cross_desk_draft_save_and_lock_preserve_other_fields(self):
        created = await self.request("POST", "/customer/consignments/draft", {
            "flight_no": "CZ1001", "first_leg_weight": 123.45,
            "receivables": {"first_leg_fee": 78.9, "total": 999},
            "payables": {"intl_air": {"flight_doc_no": "784-12345678", "flight_date": "2026-11-11"}},
        })
        customer_path = "/customer/consignments/" + created["id"]
        cost_path = "/cost/consignments/" + created["id"]
        await self.request("PUT", customer_path, {"flight_no": "CZ1002"})
        cost = await self.request("GET", cost_path)
        self.assertEqual(cost["consignor_info"]["flight_no"], "CZ1002")
        self.assertEqual(cost["payables"]["intl_air"]["flight_no"], "CZ1002")
        await self.request("PUT", cost_path + "/draft", {"consignor_info": {"flight_no": "CZ1003"}})
        customer = await self.request("GET", customer_path)
        self.assertTrue(customer["editable"])
        self.assertEqual(customer["flight_no"], "CZ1002")
        self.assertEqual(customer["payables"]["intl_air"]["flight_no"], "CZ1002")
        await self.request("PUT", cost_path, {})
        self.db.expire_all()
        customer = await self.request("GET", customer_path)
        self.assertEqual(customer["flight_no"], "CZ1003")
        self.assertEqual(customer["payables"]["intl_air"]["flight_no"], "CZ1003")
        self.assertFalse(customer["editable"])
        self.assertEqual(customer["first_leg_weight"], 123.45)
        self.assertEqual(customer["receivables"]["first_leg_fee"], 78.9)
        self.assertEqual(customer["receivables"]["total"], 999)
        self.assertEqual(customer["payables"]["intl_air"]["flight_doc_no"], "784-12345678")
        self.assertEqual(customer["payables"]["intl_air"]["flight_date"], "2026-11-11")
        before = self.db.query(ConsignmentOperationLog).count()
        rejected = await self.client.put(customer_path, json={"flight_no": "锁定后禁止覆盖"})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)

    async def test_legacy_flight_numbers_export_without_backfill_or_overwriting_groups(self):
        for record_id, number in ((1, "CZ-HISTORY"), (2, None)):
            self.db.add(ConsignmentInfo(
                id=record_id, status=1, flight_no=number,
                financial_data={"payables": {"intl_air": {"flight_no": "CZ-CUSTOMER-INTL"}}},
            ))
            self.db.add(CostConsignment(
                id=record_id, status=1, flight_no=number,
                pay_intl_air_flight_no="CZ-COST-INTL", pay_dom_air_flight_no="MU-DOM",
            ))
        self.db.commit()
        for base, count, intl_column, intl_number in (
            ("/customer", 94, 37, "CZ-CUSTOMER-INTL"), ("/cost", 118, 41, "CZ-COST-INTL"),
        ):
            for record_id, number in ((1, "CZ-HISTORY"), (2, None)):
                detail = await self.request("GET", base + "/consignments/" + str(record_id))
                info = detail if base == "/customer" else detail["consignor_info"]
                self.assertEqual(info["flight_no"], number or "")
                self.assertEqual(detail["payables"]["intl_air"]["flight_no"], intl_number)
                response = await self.client.post(base + "/consignments/export-excel", json={"ids": [str(record_id)]})
                self.assertEqual(response.status_code, 200, response.text)
                workbook = load_workbook(io.BytesIO(response.content), data_only=False)
                self.addCleanup(workbook.close)
                sheet = workbook.active
                self.assertEqual(sheet.max_column, count)
                self.assertEqual([sheet.cell(1, c).value for c in (8, 9, 10)], ["航班日期", "航班号", "主单号"])
                self.assertEqual(sheet["I2"].value, number)
                self.assertEqual(sheet.cell(1, intl_column).value, "航班号")
                self.assertEqual(sheet.cell(2, intl_column).value, intl_number)
        self.assertFalse(self.db.dirty)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_customer_flight_no_sync_supports_legacy_null_financial_groups(self):
        for record_id, snapshot in enumerate((None, {"payables": None}, {"payables": {"intl_air": None}}), 1):
            self.db.add(ConsignmentInfo(id=record_id, status=0, financial_data=snapshot))
        self.db.commit()
        for record_id in range(1, 4):
            result = await self.request("PUT", f"/customer/consignments/{record_id}/draft", {"flight_no": "CZ1001"})
            self.db.expire_all()
            detail = await self.request("GET", f"/customer/consignments/{record_id}")
            for data in (result, detail):
                self.assertEqual(data["flight_no"], "CZ1001")
                self.assertEqual(data["payables"]["intl_air"]["flight_no"], "CZ1001")

    async def test_first_leg_weight_customer_cost_sync_and_lock_without_recalculation(self):
        created = await self.request("POST", "/customer/consignments/draft", {
            "first_leg_weight": 120.5, "actual_weight": 180, "chargeable_weight": 200,
            "receivables": {"first_leg_fee": 123.45, "total": 999},
        })
        record_id = int(created["id"])
        customer_path = "/customer/consignments/" + created["id"]
        cost_path = "/cost/consignments/" + created["id"]
        self.assertEqual(created["first_leg_weight"], 120.5)
        self.assertIsNone(self.db.get(CostConsignment, record_id))
        await self.request("PUT", customer_path + "/draft", {"remark": "仅修改备注"})
        self.assertEqual((await self.request("GET", customer_path))["first_leg_weight"], 120.5)
        cleared = await self.request("PUT", customer_path + "/draft", {"first_leg_weight": None})
        self.assertIsNone(cleared["first_leg_weight"])
        await self.request("PUT", customer_path, {"first_leg_weight": 0})
        self.assertEqual(self.db.get(CostConsignment, record_id).first_leg_weight, Decimal("0.00"))
        await self.request("PUT", customer_path, {"first_leg_weight": 120.5})
        self.db.expire_all()
        self.assertEqual((await self.request("GET", cost_path))["consignor_info"]["first_leg_weight"], 120.5)
        await self.request("PUT", cost_path + "/draft", {"consignor_info": {"first_leg_weight": 321.09}})
        self.assertEqual((await self.request("GET", customer_path))["first_leg_weight"], 120.5)
        await self.request("PUT", cost_path, {"operating_info": {"profit": 88}})
        self.db.expire_all()
        customer = await self.request("GET", customer_path)
        self.assertEqual(customer["first_leg_weight"], 321.09)
        self.assertFalse(customer["editable"])
        for base in ("/customer", "/cost"):
            listing = await self.request("GET", base + "/consignments")
            item = next(item for item in listing["items"] if item["id"] == created["id"])
            info = item if base == "/customer" else item["consignor_info"]
            self.assertEqual(info["first_leg_weight"], 321.09)
            self.assertEqual(info["actual_weight"], 180)
            self.assertEqual(info["chargeable_weight"], 200)
            self.assertEqual(item["receivables"]["first_leg_fee"], 123.45)
            self.assertEqual(item["receivables"]["total"], 999)
        self.assertEqual(self.db.get(CostConsignment, record_id).profit, Decimal("88.00"))
        rejected = await self.client.put(customer_path, json={"first_leg_weight": 1})
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(self.db.get(ConsignmentInfo, record_id).first_leg_weight, Decimal("321.09"))

    async def test_first_leg_weight_templates_direct_creates_and_existing_null_semantics(self):
        for base, template in (("/customer", "/consignment-registration"), ("/cost", "/cost-registration")):
            def body(value):
                info = {"first_leg_weight": value}
                return info if base == "/customer" else {"consignor_info": info}

            def weight(data):
                return (data if base == "/customer" else data["consignor_info"])["first_leg_weight"]

            await self.request("PUT", base + template, body(12.34))
            self.db.expire_all()
            self.assertEqual(weight(await self.request("GET", base + template)), 12.34)
            for suffix in ("", "/draft"):
                created = await self.request("POST", base + "/consignments" + suffix, body(12.34))
                path = base + "/consignments/" + created["id"]
                self.assertEqual(weight(created), 12.34)
                self.db.expire_all()
                self.assertEqual(weight(await self.request("GET", path)), 12.34)
                unchanged = await self.request("PUT", path + "/draft", {})
                self.assertEqual(weight(unchanged), 12.34)
                result = await self.request("PUT", path + "/draft", body(None))
                # 客服显式null清空；费用既有数值字段null保留。导出补列不改变旧契约。
                self.assertEqual(weight(result), None if base == "/customer" else 12.34)
                result = await self.request("PUT", path, body(0))
                self.assertEqual(weight(result), 0)
                if base == "/cost":
                    customer = await self.request("GET", "/customer/consignments/" + created["id"])
                    self.assertEqual(customer["first_leg_weight"], 0)
                    self.assertFalse(customer["editable"])

    async def test_first_leg_weight_historical_detail_list_excel_read_own_values_without_writes(self):
        customer_weights = (Decimal("120.50"), 0, None)
        cost_weights = (0, None, Decimal("321.09"))
        for record_id, (customer_weight, cost_weight) in enumerate(zip(customer_weights, cost_weights), 1):
            self.db.add(ConsignmentInfo(
                id=record_id, status=1, created_at=datetime(2020, 1, 1),
                first_leg_weight=customer_weight, bill_of_lading="2-0", remark="客服备注",
                financial_data={"receivables": {"first_leg_fee": 45.67}},
            ))
            self.db.add(CostConsignment(
                id=record_id, status=1, created_at=datetime(2020, 1, 1),
                first_leg_weight=cost_weight, bill_of_lading="2-0", remark="费用备注",
                receivable_first_leg_fee=89.01,
            ))
        self.db.commit()
        for base, weights, column_count, fee_column, fee in (
            ("/customer", customer_weights, 94, 32, 45.67),
            ("/cost", cost_weights, 118, 35, 89.01),
        ):
            listing = await self.request("GET", base + "/consignments")
            items = {item["id"]: item for item in listing["items"]}
            for record_id, expected in enumerate(weights, 1):
                detail = await self.request("GET", base + "/consignments/" + str(record_id))
                for data in (detail, items[str(record_id)]):
                    info = data if base == "/customer" else data["consignor_info"]
                    self.assertEqual(info["first_leg_weight"], float(expected) if expected is not None else None)
                response = await self.client.post(base + "/consignments/export-excel", json={"ids": [str(record_id)]})
                self.assertEqual(response.status_code, 200, response.text)
                workbook = load_workbook(io.BytesIO(response.content), data_only=False)
                self.addCleanup(workbook.close)
                sheet = workbook.active
                self.assertEqual(sheet.max_column, column_count)
                self.assertEqual([sheet.cell(1, c).value for c in (7, 15, 16)], ["提单", "一程重量", "备注"])
                self.assertEqual(sheet["G2"].value, "直单")
                self.assertEqual(sheet["O2"].value, float(expected) if expected is not None else None)
                if expected is not None:
                    self.assertEqual(sheet["O2"].data_type, "n")
                self.assertEqual(sheet["P2"].value, "客服备注" if base == "/customer" else "费用备注")
                self.assertEqual(sheet.cell(2, fee_column).value, fee)
                self.assertFalse(any(cell.data_type == "f" for cell in sheet[2]))
        self.assertFalse(self.db.dirty)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_first_leg_fee_customer_edits_cost_sync_and_successful_cost_save_lock(self):
        created = await self.request("POST", "/customer/consignments/draft", {
            "first_leg_weight": 12, "receivables": {"first_leg_fee": 123.45, "total": 900},
        })
        record_id = int(created["id"])
        customer_path = "/customer/consignments/" + created["id"]
        cost_path = "/cost/consignments/" + created["id"]
        self.assertEqual(created["receivables"]["first_leg_fee"], 123.45)
        self.assertIsNone(self.db.get(CostConsignment, record_id))
        await self.request("PUT", customer_path + "/draft", {"receivables": {"consumables_fee": 7}})
        self.assertEqual((await self.request("GET", customer_path))["receivables"]["first_leg_fee"], 123.45)
        # 客服显式null清空快照，0是有效金额，客服反复保存继续流转。
        cleared = await self.request("PUT", customer_path + "/draft", {"receivables": {"first_leg_fee": None}})
        self.assertIsNone(cleared["receivables"]["first_leg_fee"])
        saved = await self.request("PUT", customer_path, {"receivables": {"first_leg_fee": 0}})
        self.assertTrue(saved["editable"])
        self.assertEqual(self.db.get(CostConsignment, record_id).receivable_first_leg_fee, Decimal("0.00"))
        await self.request("PUT", customer_path, {"receivables": {"first_leg_fee": 123.45}})
        self.assertEqual((await self.request("GET", cost_path))["receivables"]["first_leg_fee"], 123.45)
        # 费用暂存不回写，正常保存才回写并锁客服；不据金额重算合计/利润。
        await self.request("PUT", cost_path + "/draft", {"receivables": {"first_leg_fee": 678.9}})
        self.assertEqual((await self.request("GET", customer_path))["receivables"]["first_leg_fee"], 123.45)
        await self.request("PUT", cost_path, {"operating_info": {"profit": 88}})
        customer = await self.request("GET", customer_path)
        self.assertEqual(customer["receivables"]["first_leg_fee"], 678.9)
        self.assertEqual(customer["receivables"]["total"], 900)
        self.assertEqual(customer["first_leg_weight"], 12)
        self.assertFalse(customer["editable"])
        for base in ("/customer", "/cost"):
            listing = await self.request("GET", base + "/consignments")
            self.assertEqual(listing["items"][0]["receivables"]["first_leg_fee"], 678.9)
        response = await self.client.put(customer_path, json={"receivables": {"first_leg_fee": 1}})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.get(CostConsignment, record_id).profit, Decimal("88.00"))

    async def test_first_leg_fee_templates_cost_create_and_partial_update_compatibility(self):
        for path in ("/customer/consignment-registration", "/cost/cost-registration"):
            await self.request("PUT", path, {"receivables": {"first_leg_fee": 12.34}})
            self.assertEqual((await self.request("GET", path))["receivables"]["first_leg_fee"], 12.34)
            await self.request("PUT", path, {"receivables": {"consumables_fee": 7}})
            self.assertEqual((await self.request("GET", path))["receivables"]["first_leg_fee"], 12.34)
        for suffix in ("", "/draft"):
            created = await self.request("POST", "/cost/consignments" + suffix, {
                "receivables": {"first_leg_fee": 45.67, "total": 100},
            })
            path = "/cost/consignments/" + created["id"]
            self.assertEqual(created["receivables"]["first_leg_fee"], 45.67)
            # 费用已有数值字段沿用null保留规则，不能因本次导出变更而改变。
            for patch in ({}, {"receivables": {}}, {"receivables": {"first_leg_fee": None}}):
                saved = await self.request("PUT", path + "/draft", patch)
                self.assertEqual(saved["receivables"]["first_leg_fee"], 45.67)
            saved = await self.request("PUT", path, {"receivables": {"first_leg_fee": 0}})
            self.assertEqual(saved["receivables"]["first_leg_fee"], 0)
            self.assertEqual(saved["receivables"]["total"], 100)
            customer = await self.request("GET", "/customer/consignments/" + created["id"])
            self.assertEqual(customer["receivables"]["first_leg_fee"], 0)
            self.assertFalse(customer["editable"])

    async def test_first_leg_fee_excel_column_values_and_desk_storage_are_independent(self):
        for record_id, customer_fee, cost_fee in ((1, 0, 78.9), (2, 12.34, 0), (3, None, None), (4, None, None)):
            self.db.add(ConsignmentInfo(
                id=record_id, status=0,
                financial_data=None if record_id == 4 else {"receivables": {
                    "first_leg_fee": customer_fee, "consumables_fee": 2,
                }},
            ))
            self.db.add(CostConsignment(
                id=record_id, status=0, receivable_first_leg_fee=cost_fee,
                receivable_consumables_fee=3, receivable_total=99,
            ))
        self.db.commit()
        for base, column, count, expected in (
            ("/customer", 32, 94, (0, 12.34, None, None)),
            ("/cost", 35, 118, (78.9, 0, None, None)),
        ):
            for record_id, fee in enumerate(expected, 1):
                response = await self.client.post(base + "/consignments/export-excel", json={"ids": [str(record_id)]})
                self.assertEqual(response.status_code, 200, response.text)
                workbook = load_workbook(io.BytesIO(response.content), data_only=False)
                self.addCleanup(workbook.close)
                sheet = workbook.active
                self.assertEqual(sheet.max_column, count)
                self.assertEqual(sheet.max_row, 2)
                self.assertEqual(sheet.cell(1, column - 1).value, "应收耗材费")
                self.assertEqual(sheet.cell(1, column).value, "一程费用")
                self.assertEqual(sheet.cell(1, column + 1).value,
                                 "国际空运代理名称" if base == "/customer" else "应收合计")
                self.assertEqual(sheet.cell(2, column).value, fee)
                if fee is not None:
                    self.assertEqual(sheet.cell(2, column).data_type, "n")
                self.assertEqual(len(sheet.merged_cells.ranges), 0)
        self.assertFalse(self.db.dirty)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_customer_draft_partial_clear_submit_lock_and_cost_reverse_sync(self):
        data = await self.request("POST", "/customer/consignments/draft", {
            "customer_name": "客户", "actual_weight": 100, "customs_declaration": "1买单+3单证", **FINANCIAL,
        })
        record_id = int(data["id"])
        self.assertIsNone(self.db.get(CostConsignment, record_id))
        path = "/customer/consignments/" + data["id"]
        data = await self.request("PUT", path + "/draft", {
            "receivables": {"fuel_rate": 0, "remark": None}, "payables": {"ground": {"tc_fee": None}},
        })
        self.assertEqual(data["receivables"]["buy_order_fee"], 300)
        self.assertEqual(data["receivables"]["fuel_rate"], 0)
        self.assertIsNone(data["receivables"]["remark"])
        data = await self.request("PUT", path, {})
        self.assertEqual(data["status"], 1)
        cost = self.db.get(CostConsignment, record_id)
        self.assertEqual(cost.status, 0)
        self.assertEqual(cost.actual_weight, Decimal("100.00"))
        self.assertEqual(cost.pay_intl_air_weight, Decimal("105.00"))
        self.assertEqual(cost.pay_intl_air_flight_doc_no, "999-00000001")
        self.assertEqual(cost.pay_dom_air_volume, Decimal("1.234"))
        self.assertEqual(cost.pay_trucking_freight_method, "计费重")
        self.assertEqual(cost.receivable_customs_fee, Decimal("750.00"))
        self.assertEqual(cost.receivable_fuel_fee, Decimal("65.00"))  # 不随后端费率 0 回算。
        self.assertTrue(data["editable"])
        await self.request("PUT", "/cost/consignments/" + str(record_id), {
            "receivables": {"fuel_rate": 1.23}, "payables": {"trucking": {"destination_city": "北京", "freight_method": "体积重"}},
        })
        detail = await self.request("GET", path)
        self.assertEqual(detail["receivables"]["fuel_rate"], 1.23)
        self.assertEqual(detail["payables"]["trucking"]["destination_city"], "北京")
        self.assertEqual(detail["status"], 1)
        self.assertEqual(detail["payables"]["trucking"]["freight_method"], "体积重")

        before = self.db.query(ConsignmentOperationLog).count()
        for suffix in ("", "/draft"):
            response = await self.client.put(path + suffix, json={"customer_name": "非法覆盖", "status": 0})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json(), {
                "code": 409, "data": None,
                "msg": "费用登记台已保存提交，客服委托信息不能修改或暂存，请在费用登记台维护",
            })
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)
        self.assertEqual(self.db.get(ConsignmentInfo, record_id).customer_name, "客户")

    async def test_templates_and_cost_create_draft_update_list_void_return_new_fields(self):
        for base, payload in (("/customer", FINANCIAL), ("/cost", FINANCIAL)):
            registration = "/consignment-registration" if base == "/customer" else "/cost-registration"
            await self.request("PUT", base + registration, payload)
            result = await self.request("GET", base + registration)
            self.assertEqual(result["receivables"]["fuel_rate"], 0.65)
            self.assertEqual(result["payables"]["trucking"]["origin_city"], "广州")
            self.assertEqual(result["payables"]["trucking"]["freight_method"], "计费重")
        for suffix in ("", "/draft"):
            result = await self.request("POST", "/cost/consignments" + suffix, FINANCIAL)
            record_id = result["id"]
            path = "/cost/consignments/" + record_id
            self.assertEqual(result["payables"]["dom_air"]["volume"], 1.234)
            self.assertEqual(result["payables"]["trucking"]["freight_method"], "计费重")
            if not suffix:
                customer = await self.request("GET", "/customer/consignments/" + record_id)
                self.assertEqual(customer["payables"]["customs"]["buy_order_fee"], 260)
                self.assertEqual(customer["payables"]["trucking"]["freight_method"], "计费重")
            result = await self.request("PUT", path + "/draft", {"receivables": {"fuel_rate": None}})
            self.assertIsNone(result["receivables"]["fuel_rate"])
            self.assertEqual(result["payables"]["trucking"]["freight_method"], "计费重")
            self.assertEqual(result["receivables"]["buy_order_fee"], 300)
            result = await self.request("PUT", path, {"receivables": {"fuel_rate": 0}})
            self.assertEqual(result["receivables"]["fuel_rate"], 0)
            result = await self.request("GET", "/cost/consignments")
            self.assertTrue(any(item["id"] == record_id and item["receivables"]["fuel_rate"] == 0
                                and item["payables"]["trucking"]["freight_method"] == "计费重" for item in result["items"]))
            result = await self.request("PUT", path + "/void")
            self.assertEqual(result["status"], 2)
            self.assertEqual(result["payables"]["ground"]["tc_rate"], 0.15)
            self.assertEqual(result["payables"]["trucking"]["freight_method"], "计费重")

    async def test_trucking_method_partial_updates_clear_and_preserve_saved_amounts(self):
        for base, template in (("/cost", "/cost-registration"), ("/customer", "/consignment-registration")):
            initial = {"payables": {"trucking": {
                "freight_method": "计费重", "unit_price": 2, "weight": 100, "freight": 123.45,
            }}}
            data = await self.request("PUT", base + template, initial)
            self.assertEqual(data["payables"]["trucking"]["freight_method"], "计费重")
            for patch, expected in (
                ({}, "计费重"), ({"payables": None}, "计费重"),
                ({"payables": {"trucking": None}}, "计费重"),
                ({"payables": {"trucking": {"remark": "只改备注"}}}, "计费重"),
                ({"payables": {"trucking": {"freight_method": "前端自定义值"}}}, "前端自定义值"),
                ({"payables": {"trucking": {"freight_method": ""}}}, ""),
                ({"payables": {"trucking": {"freight_method": None}}}, None),
            ):
                result = await self.request("PUT", base + template, patch)
                detail = await self.request("GET", base + template)
                self.assertEqual(result["payables"]["trucking"]["freight_method"], expected)
                self.assertEqual(detail["payables"]["trucking"]["freight_method"], expected)
                self.assertEqual(detail["payables"]["trucking"]["freight"], 123.45)
            data = await self.request("POST", base + "/consignments/draft", initial)
            path = base + "/consignments/" + data["id"]
            for patch, expected in (
                ({"payables": {"trucking": {"freight_method": "体积重"}}}, "体积重"),
                ({"payables": {"trucking": {"doc_fee": 10}}}, "体积重"),
                ({"payables": {"trucking": {"freight_method": None}}}, None),
                ({"payables": {"trucking": {"freight_method": ""}}}, ""),
            ):
                result = await self.request("PUT", path + "/draft", patch)
                self.assertEqual(result["payables"]["trucking"]["freight_method"], expected)
                self.assertEqual(result["payables"]["trucking"]["freight"], 123.45)
                self.db.expire_all()  # 重读数据库，防止仅响应带值却没有持久化。
                detail = await self.request("GET", path)
                self.assertEqual(detail["payables"]["trucking"]["freight_method"], expected)
            submitted = await self.request("PUT", path, {"payables": {"trucking": {"freight_method": "体积重"}}})
            self.assertEqual(submitted["payables"]["trucking"]["freight_method"], "体积重")
            listing = await self.request("GET", base + "/consignments")
            self.assertEqual(next(x for x in listing["items"] if x["id"] == data["id"])["payables"]["trucking"]["freight_method"], "体积重")

    async def test_trucking_method_flow_preserves_missing_and_distinguishes_null_and_draft(self):
        for trucking, expected in (({}, "费用已填"), ({"freight_method": None}, None),
                                   ({"freight_method": ""}, ""), ({"freight_method": "计费重"}, "计费重")):
            data = await self.request("POST", "/customer/consignments/draft", {"payables": {"trucking": trucking}})
            record_id = int(data["id"])
            self.db.add(CostConsignment(
                id=record_id, status=0, pay_trucking_freight_method="费用已填",
                freight_method="应收方式", pay_intl_air_freight_method="国际方式",
                pay_dom_air_freight_method="国内方式", pay_trucking_freight=123.45,
            ))
            self.db.commit()
            customer_path = "/customer/consignments/" + data["id"]
            cost_path = "/cost/consignments/" + data["id"]
            await self.request("PUT", customer_path, {})
            cost = await self.request("GET", cost_path)
            self.assertEqual(cost["payables"]["trucking"]["freight_method"], expected)
            self.assertEqual(cost["payables"]["trucking"]["freight"], 123.45)
            self.assertEqual(cost["receivables"]["freight_method"], "应收方式")
            self.assertEqual(cost["payables"]["intl_air"]["freight_method"], "国际方式")
            self.assertEqual(cost["payables"]["dom_air"]["freight_method"], "国内方式")
            customer_before = await self.request("GET", customer_path)
            await self.request("PUT", cost_path + "/draft", {"payables": {"trucking": {"freight_method": "体积重"}}})
            customer_after = await self.request("GET", customer_path)
            self.assertEqual(customer_after["payables"]["trucking"]["freight_method"],
                             customer_before["payables"]["trucking"]["freight_method"])
            await self.request("PUT", cost_path, {"payables": {"trucking": {"freight_method": None}}})
            customer_after = await self.request("GET", customer_path)
            self.assertIsNone(customer_after["payables"]["trucking"]["freight_method"])
            self.assertEqual(customer_after["status"], 1)

    async def test_trucking_method_validation_is_atomic_and_legacy_records_return_null(self):
        for base, model in (("/cost", CostConsignment), ("/customer", ConsignmentInfo)):
            data = await self.request("POST", base + "/consignments/draft", {})
            self.assertIsNone(data["payables"]["trucking"]["freight_method"])
            path = base + "/consignments/" + data["id"]
            logs_before = self.db.query(ConsignmentOperationLog).count()
            for invalid in ("x" * 51, 1, ["计费重"], {"value": "体积重"}):
                response = await self.client.put(path, json={"payables": {"trucking": {"freight_method": invalid}}})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.db.get(model, int(data["id"])).status, 0)
                self.assertEqual(self.db.query(ConsignmentOperationLog).count(), logs_before)
            for value in ("1", "2", "x" * 50):
                result = await self.request("PUT", path + "/draft", {"payables": {"trucking": {"freight_method": value}}})
                self.assertEqual(result["payables"]["trucking"]["freight_method"], value)

    async def test_export_requested_fields_with_numeric_zero_blank_and_weight_labels(self):
        payload = deepcopy(FINANCIAL)
        payload["receivables"].update({"fuel_rate": 0, "freight_method": "2", "total": 987.65})
        result = await self.request("POST", "/customer/consignments", payload)
        for base, count, ground_pickup_column in (("/customer", 94, 65), ("/cost", 118, 73)):
            response = await self.client.post(base + "/consignments/export-excel", json={"ids": [result["id"]]})
            self.assertEqual(response.status_code, 200, response.text)
            workbook = load_workbook(io.BytesIO(response.content), data_only=True)
            self.addCleanup(workbook.close)
            sheet = workbook.active
            self.assertEqual(sheet.max_column, count)
            self.assertEqual(sheet.max_row, 2)
            titles = [cell.value for cell in sheet[1]]
            values = [cell.value for cell in sheet[2]]
            for expected in ("广州", "ROAD-001", 1.234):
                self.assertIn(expected, values)
            self.assertNotIn("燃油费率", titles)
            self.assertNotIn("燃油费取重方式", titles)
            self.assertEqual(sheet.cell(2, ground_pickup_column).value, 0)
            self.assertEqual(sheet.cell(2, ground_pickup_column).data_type, "n")
            self.assertIsNone(sheet.cell(2, 4).value)
            if base == "/cost":
                self.assertEqual(sheet.cell(2, 18).value, "计费重量")
                self.assertEqual(sheet.cell(2, 36).value, 987.65)
                self.assertEqual(sheet.cell(2, 115).value, 987.65)
            else:
                self.assertEqual(titles.count("运费计算方式"), 1)
                self.assertEqual(sheet.cell(2, 79).value, "计费重")
                self.assertNotIn("应付小计", titles)
                self.assertNotIn("应收合计", titles)
            detail = await self.request("GET", base + "/consignments/" + result["id"])
            self.assertEqual(detail["receivables"]["fuel_rate"], 0)
            self.assertEqual(detail["receivables"]["buy_order_fee"], 300)

    async def test_both_exports_include_raw_trucking_method_and_keep_adjacent_columns(self):
        methods = ("计费重", "体积重", "1", "2", None, "")
        for i, method in enumerate(methods, 1):
            self.db.add(CostConsignment(
                id=i, status=0, freight_method="2", flight_date=date(2026, 11, i),
                pay_trucking_unit_price=2, pay_trucking_weight=100, pay_trucking_volume=1.2,
                pay_trucking_freight_method=method, pay_trucking_freight=123.45,
                pay_trucking_doc_fee=0, pay_trucking_other_fee=7.89,
                pay_trucking_remark=f"费用汽运-{i}", pay_trucking_subtotal=777.77,
                pay_dom_air_outsource_unit="费用国内代理", commission_amount=12.34,
                receivable_total=1000, pay_total=777.77, profit=222.23, profit_margin=22.22,
            ))
            # 两台使用不同值，以核对导出读取各自存储，且不发生回写。
            self.db.add(ConsignmentInfo(
                id=i, status=0, create_time=datetime(2026, 11, len(methods) + 1 - i),
                financial_data={"payables": {
                    "trucking": {"freight_method": methods[-i], "volume": 1.234,
                                 "doc_fee": 0, "other_fee": 9.87, "remark": f"客服汽运-{i}"},
                    "dom_air": {"outsource_unit": "客服国内代理"},
                }},
            ))
        self.db.commit()
        for base, count, column, expected_methods in (
            ("/cost", 118, 89, methods), ("/customer", 94, 79, methods[::-1]),
        ):
            response = await self.client.post(base + "/consignments/export-excel", json={"ids": [str(i) for i in range(1, 7)]})
            self.assertEqual(response.status_code, 200, response.text)
            workbook = load_workbook(io.BytesIO(response.content), data_only=False)
            self.addCleanup(workbook.close)
            sheet = workbook.active
            self.assertEqual(sheet.max_column, count)
            self.assertEqual(sheet.max_row, 7)
            self.assertEqual(sheet.cell(1, column).value, "运费计算方式")
            self.assertEqual(sheet.cell(1, column - 1).value, "单价" if base == "/cost" else "体积")
            self.assertEqual(sheet.cell(1, column + 1).value, "运费" if base == "/cost" else "制单费")
            self.assertFalse(sheet.merged_cells.ranges)
            for row, method in enumerate(expected_methods, 2):
                cell = sheet.cell(row, column)
                self.assertEqual(cell.value, method or None)
                if method:
                    self.assertEqual(cell.data_type, "s")  # 字符串编码1/2原样，不转换为应收选项。
                if base == "/cost":
                    self.assertEqual(sheet.cell(row, 18).value, "计费重量")
                    self.assertEqual([sheet.cell(row, c).value for c in range(88, 95)],
                                     [2, method or None, 123.45, 0, 7.89, f"费用汽运-{row - 1}", 777.77])
                    self.assertEqual(sheet.cell(row, 95).value, "费用国内代理")
                    self.assertEqual([sheet.cell(row, c).value for c in range(114, 119)],
                                     [12.34, 1000, 777.77, 222.23, 22.22])
                else:
                    self.assertEqual([sheet.cell(row, c).value for c in range(78, 84)],
                                     [1.234, method or None, 0, 9.87, f"客服汽运-{row - 1}", "客服国内代理"])
        self.assertFalse(self.db.dirty)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        for i, method in enumerate(methods, 1):
            record = self.db.get(CostConsignment, i)
            self.assertEqual(record.pay_trucking_freight_method, method)
            self.assertEqual(record.pay_trucking_freight, Decimal("123.45"))
            self.assertEqual(record.pay_trucking_subtotal, Decimal("777.77"))
            self.assertEqual(record.status, 0)

    async def test_exports_preserve_desk_sorting_storage_and_read_only_behavior(self):
        for i in range(1, 5):
            self.db.add(ConsignmentInfo(
                id=i, status=(1, 0, 2, 1)[i - 1], customer_tags=[], expense_tags=[],
                create_time=datetime(2026, 11, i), flight_doc_no=f"CUSTOMER-{i}",
                financial_data={"receivables": {"lading_info_fee": 11.11},
                                "payables": {"intl_air": {"outsource_unit": "客服国际代理"}}},
            ))
            self.db.add(CostConsignment(
                id=i, status=(0, 1, 2, 1)[i - 1], customer_tags=[], expense_tags=[],
                flight_date={1: date(2026, 11, 3), 2: date(2026, 11, 1),
                             3: None, 4: date(2026, 11, 1)}[i],
                flight_doc_no=f"COST-{i}", receivable_lading_info_fee=22.22,
                pay_intl_air_outsource_unit="费用国际代理",
            ))
        self.db.commit()
        for base, prefix, expected_order, agent_column, fee_column, fee in (
            ("/customer", "CUSTOMER", [4, 3, 2, 1], 33, 17, 11.11),
            ("/cost", "COST", [2, 4, 1, 3], 37, 20, 22.22),
        ):
            response = await self.client.post(base + "/consignments/export-excel", json={
                "ids": ["3", "999", "1", "2", "4", "2"],
            })
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.headers["content-type"],
                             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            filename_prefix = "consignment_export_" if base == "/customer" else "cost_consignment_export_"
            self.assertTrue(response.headers["content-disposition"].startswith("attachment; filename=" + filename_prefix))
            self.assertEqual(response.headers["access-control-expose-headers"], "Content-Disposition")
            workbook = load_workbook(io.BytesIO(response.content), data_only=True)
            self.addCleanup(workbook.close)
            sheet = workbook.active
            self.assertEqual(sheet.max_row, 5)
            self.assertEqual([sheet.cell(row, 1).value for row in range(2, 6)], [1, 2, 3, 4])
            self.assertEqual([sheet.cell(row, 10).value for row in range(2, 6)],
                             [f"{prefix}-{i}" for i in expected_order])
            for row in range(2, 6):
                self.assertEqual(sheet.cell(row, agent_column).value,
                                 "客服国际代理" if base == "/customer" else "费用国际代理")
                self.assertEqual(sheet.cell(row, fee_column).value, fee)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        self.assertFalse(self.db.dirty)
        self.assertEqual([self.db.get(ConsignmentInfo, i).status for i in range(1, 5)], [1, 0, 2, 1])
        self.assertEqual([self.db.get(CostConsignment, i).status for i in range(1, 5)], [0, 1, 2, 1])

    async def test_export_validation_and_no_matching_ids_keep_existing_behavior(self):
        for base, count, empty_status in (("/customer", 94, 422), ("/cost", 118, 400)):
            for payload, expected in (({}, 422), ({"ids": []}, empty_status),
                                      ({"ids": ["abc"]}, 400), ({"ids": [1]}, 422)):
                response = await self.client.post(base + "/consignments/export-excel", json=payload)
                self.assertEqual(response.status_code, expected, response.text)
                self.assertEqual(response.json()["code"], expected)
            response = await self.client.post(base + "/consignments/export-excel", json={"ids": ["999"]})
            self.assertEqual(response.status_code, 200, response.text)
            workbook = load_workbook(io.BytesIO(response.content))
            self.addCleanup(workbook.close)
            self.assertEqual(workbook.active.max_row, 1)
            self.assertEqual(workbook.active.max_column, count)

    async def test_legacy_entrustment_dates_survive_detail_list_and_excel_without_backfill(self):
        # 模拟历史记录：只有委托日期、三处日期不同、委托日期为空。
        for record_id, entrustment_date in ((1, date(2026, 9, 1)), (2, date(2026, 9, 2)), (3, None)):
            self.db.add(ConsignmentInfo(
                id=record_id, status=1, flight_date=entrustment_date,
                warehouse_entry_date=date(2026, 8, 31), flight_doc_no=f"CUSTOMER-{record_id}",
                financial_data=None if record_id == 1 else {"payables": {
                    "intl_air": {"flight_date": "2026-09-10"},
                    "dom_air": {"flight_date": "2026-09-11"},
                }},
            ))
            self.db.add(CostConsignment(
                id=record_id, status=1, flight_date=entrustment_date,
                warehouse_entry_date=date(2026, 8, 31), flight_doc_no=f"COST-{record_id}",
                pay_intl_air_flight_date=None if record_id == 1 else date(2026, 9, 10),
                pay_dom_air_flight_date=None if record_id == 1 else date(2026, 9, 11),
            ))
        self.db.commit()
        for base, intl_column, domestic_column, count in (
            ("/customer", 38, 88, 94), ("/cost", 42, 100, 118),
        ):
            listing = await self.request("GET", base + "/consignments")
            items = {item["id"]: item for item in listing["items"]}
            for record_id, expected in ((1, "2026-09-01"), (2, "2026-09-02"), (3, None)):
                detail = await self.request("GET", f"{base}/consignments/{record_id}")
                for data in (detail, items[str(record_id)]):
                    info = data if base == "/customer" else data["consignor_info"]
                    self.assertEqual(info["flight_date"], expected)
                response = await self.client.post(base + "/consignments/export-excel", json={"ids": [str(record_id)]})
                self.assertEqual(response.status_code, 200, response.text)
                workbook = load_workbook(io.BytesIO(response.content), data_only=True)
                self.addCleanup(workbook.close)
                sheet = workbook.active
                self.assertEqual(sheet.max_column, count)
                self.assertEqual([sheet.cell(1, c).value for c in (3, 8, 9, 10)], ["进仓日期", "航班日期", "航班号", "主单号"])
                self.assertEqual(sheet.cell(2, 3).value, "2026-08-31")
                self.assertEqual(sheet.cell(2, 8).value, expected)
                self.assertEqual(sheet.cell(2, 10).value, f"{'CUSTOMER' if base == '/customer' else 'COST'}-{record_id}")
                self.assertEqual(sheet.cell(2, 8).alignment.horizontal, "center")
                for column, date_value in ((intl_column, "2026-09-10"), (domestic_column, "2026-09-11")):
                    self.assertEqual(sheet.cell(1, column).value, "航班日期")
                    self.assertEqual(sheet.cell(2, column).value, None if record_id == 1 else date_value)
        self.assertFalse(self.db.dirty)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        self.db.expire_all()
        self.assertEqual(self.db.get(ConsignmentInfo, 1).flight_date, date(2026, 9, 1))
        self.assertIsNone(self.db.get(ConsignmentInfo, 1).financial_data)
        self.assertIsNone(self.db.get(CostConsignment, 1).pay_intl_air_flight_date)

    async def test_entrustment_date_edit_and_existing_customer_submission_sync(self):
        for base, template in (("/customer", "/consignment-registration"), ("/cost", "/cost-registration")):
            def payload(value):
                return {"flight_date": value} if base == "/customer" else {"consignor_info": {"flight_date": value}}

            await self.request("PUT", base + template, payload("2026-11-01"))
            saved = await self.request("GET", base + template)
            self.assertEqual((saved if base == "/customer" else saved["consignor_info"])["flight_date"], "2026-11-01")
            created = await self.request("POST", base + "/consignments/draft", payload("2026-11-01"))
            path = base + "/consignments/" + created["id"]
            await self.request("PUT", path + "/draft", payload("2026-11-02"))
            self.db.expire_all()
            detail = await self.request("GET", path)
            self.assertEqual((detail if base == "/customer" else detail["consignor_info"])["flight_date"], "2026-11-02")
            await self.request("PUT", path, {})
            customer = await self.request("GET", "/customer/consignments/" + created["id"])
            self.assertEqual(customer["flight_date"], "2026-11-02")
            if base == "/customer":
                cost = await self.request("GET", "/cost/consignments/" + created["id"])
                self.assertEqual(cost["consignor_info"]["flight_date"], "2026-11-02")
                self.assertEqual(cost["payables"]["intl_air"]["flight_date"], "2026-11-02")
                response = await self.client.put(path, json=payload("2026-11-03"))
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["data"]["editable"])
        # 客服明确录入国际日期时，继续沿用原有分组字段优先规则。
        created = await self.request("POST", "/customer/consignments", {
            "flight_date": "2026-11-04", "payables": {"intl_air": {"flight_date": "2026-11-05"}},
        })
        cost = await self.request("GET", "/cost/consignments/" + created["id"])
        self.assertEqual(cost["consignor_info"]["flight_date"], "2026-11-04")
        self.assertEqual(cost["payables"]["intl_air"]["flight_date"], "2026-11-05")

    async def test_invalid_weight_method_rejected_and_legacy_payload_remains_supported(self):
        response = await self.client.post("/customer/consignments", json={"receivables": {"fuel_weight_method": "3"}})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.query(ConsignmentInfo).count(), 0)
        data = await self.request("POST", "/customer/consignments", {"pieces": 8, "actual_weight": 10})
        self.assertIsNone(data["receivables"]["fuel_rate"])
        self.assertEqual(self.db.get(CostConsignment, int(data["id"])).pay_intl_air_pieces, 8)

    def test_every_public_financial_field_maps_to_a_real_column(self):
        for path, fields in FINANCIAL_FIELD_MAP.items():
            for name, column in fields.items():
                self.assertIn(column, CostConsignment.__table__.columns, (path, name))
