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
        for model in (ConsignmentInfo, ConsignmentRegistration, CostConsignment, CostRegistration, ConsignmentOperationLog):
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
        before = self.db.query(ConsignmentOperationLog).count()
        for suffix in ("", "/draft"):
            response = await self.client.put(path + suffix, json={"customer_name": "非法覆盖", "status": 0})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertEqual(response.json(), {
                "code": 409, "data": None,
                "msg": "已提交的委托信息不能修改或暂存，请在费用登记台维护",
            })
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)
        self.assertEqual(self.db.get(ConsignmentInfo, record_id).customer_name, "客户")
        await self.request("PUT", "/cost/consignments/" + str(record_id), {
            "receivables": {"fuel_rate": 1.23}, "payables": {"trucking": {"destination_city": "北京", "freight_method": "体积重"}},
        })
        detail = await self.request("GET", path)
        self.assertEqual(detail["receivables"]["fuel_rate"], 1.23)
        self.assertEqual(detail["payables"]["trucking"]["destination_city"], "北京")
        self.assertEqual(detail["status"], 1)
        self.assertEqual(detail["payables"]["trucking"]["freight_method"], "体积重")

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
        for base, count, ground_pickup_column in (("/customer", 90, 61), ("/cost", 114, 69)):
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
            self.assertIsNone(sheet.cell(2, 3).value)
            if base == "/cost":
                self.assertEqual(sheet.cell(2, 15).value, "计费重量")
                self.assertEqual(sheet.cell(2, 32).value, 987.65)
                self.assertEqual(sheet.cell(2, 111).value, 987.65)
            else:
                self.assertEqual(titles.count("运费计算方式"), 1)
                self.assertEqual(sheet.cell(2, 75).value, "计费重")
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
            ("/cost", 114, 85, methods), ("/customer", 90, 75, methods[::-1]),
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
                    self.assertEqual(sheet.cell(row, 15).value, "计费重量")
                    self.assertEqual([sheet.cell(row, c).value for c in range(84, 91)],
                                     [2, method or None, 123.45, 0, 7.89, f"费用汽运-{row - 1}", 777.77])
                    self.assertEqual(sheet.cell(row, 91).value, "费用国内代理")
                    self.assertEqual([sheet.cell(row, c).value for c in range(110, 115)],
                                     [12.34, 1000, 777.77, 222.23, 22.22])
                else:
                    self.assertEqual([sheet.cell(row, c).value for c in range(74, 80)],
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
            ("/customer", "CUSTOMER", [4, 3, 2, 1], 29, 14, 11.11),
            ("/cost", "COST", [2, 4, 1, 3], 33, 17, 22.22),
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
            self.assertEqual([sheet.cell(row, 5).value for row in range(2, 6)],
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
        for base, count, empty_status in (("/customer", 90, 422), ("/cost", 114, 400)):
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
