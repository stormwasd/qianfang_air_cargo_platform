"""应收五模块：真实 SQLite/HTTP 验证数据口径、状态隔离、原子性与导出。"""
import json
import unittest
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from sqlalchemy.exc import IntegrityError

from app.api.deps import get_current_active_user
from app.api.financial_audit import build_air_financial_audits
from app.api.reconciliation_receivable import AIR_MODULES, router, set_air_settlement, set_road_settlement
from app.database import get_db
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.consignment_note import ConsignmentNote
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.peer_road_manual_data import PeerRoadDepartureManualData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.schemas.financial_audit import AirFinancialAuditQuery, ReceivableResponse
from tests import test_reconciliation_agent as air_fixture
from tests import test_reconciliation_road_agent as road_fixture


PREFIX = "/api/v1/reconciliation/receivable"


def make_app(test):
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)

    def database():
        yield test.db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_active_user] = lambda: test.user
    return app


class AirReceivableTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        air_fixture.AgentReconciliationTests.setUp(self)
        export = self.db.get(ShenzhenAirBookingExport, 101)
        export.actual_flight = "ZH-ACTUAL"
        manual = self.db.get(ShenzhenAirDepartureManualData, 111)
        manual.door_pickup_company = "旧提货单位"
        self.db.add(AirFinancialAuditData(
            id=501, source_type="shenzhen_air", source_id=101, financial_audit_status=2,
            airline_settlement_status=1, pickup_settlement_status=1,
            delivery_settlement_status=1, agent_settlement_status=1,
            payable_data={"door_pickup_company": "最终提货单位", "delivery_company": "最终派送单位",
                          "door_pickup_fee": "901", "airport_pickup_fee": "902", "delivery_cost": "903"},
            receivable_data={"waybill_number": "479-FINAL", "flight_date": "2026-10-25",
                             "freight": "300", "door_pickup_fee": "11", "airport_pickup_fee": "13",
                             "delivery_fee": "17", "remark": "=1+2", "consignee_phone": "0013800000000"},
        ))
        self.db.commit()
        self.app = make_app(self)
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        air_fixture.AgentReconciliationTests.tearDown(self)

    def url(self, module, suffix=""):
        return f"{PREFIX}/{module.path}/air{suffix}"

    def listing(self, module, **filters):
        response = self.client.get(self.url(module), params=filters)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_four_lists_match_final_fee_desk_receivable_not_payable(self):
        canonical = await build_air_financial_audits(AirFinancialAuditQuery(), self.db, self.user, paginate=False)
        expected = next(row["receivable"] for row in canonical.data["items"] if row["source_id"] == "101")
        for module in AIR_MODULES:
            with self.subTest(module=module.path):
                result = self.listing(module, waybill_numbers="479-FINAL")
                self.assertEqual(result["total"], 1)
                row = result["items"][0]
                self.assertEqual({name: row[name] for name in ReceivableResponse.model_fields}, expected)
                self.assertEqual(row["door_pickup_fee"], "11")
                self.assertEqual(row["airport_pickup_fee"], "13")
                self.assertEqual(row["delivery_fee"], "17")
                self.assertEqual(float(row["total_amount"]), 351)
                self.assertEqual(row["actual_flight_number"], "ZH-ACTUAL")
                self.assertEqual(row["settlement_status"], 0)  # All old payable statuses are 1.
                self.assertNotIn("agent_settlement_status", row)
                self.assertEqual(self.listing(module, waybill_numbers="479-62200552")["total"], 0)

    async def test_final_filters_and_logistics_membership_before_pagination(self):
        for module in AIR_MODULES:
            params = dict(flight_date_start="2026-10-25", flight_date_end="2026-10-25",
                          financial_audit_status=2, customer_name="7", pageSize=1)
            if module.path in ("airline", "air-agent"):
                params["airline"] = "深航"
            else:
                params["actual_flight_number"] = "ACTUAL"
                params["pickup_company" if module.path == "pickup" else "delivery_company"] = "最终"
            result = self.listing(module, **params)
            self.assertEqual(result["total"], 1)
            self.assertEqual(result["items"][0]["source_id"], "101")
            self.assertEqual(self.listing(module, flight_date_end="2026-10-24", financial_audit_status=2)["total"], 0)
        self.assertEqual(self.listing(AIR_MODULES[1], pickup_company="旧提货单位")["total"], 0)
        self.assertEqual(self.listing(AIR_MODULES[1])["total"], 1)
        self.assertEqual(self.listing(AIR_MODULES[2])["total"], 1)
        self.assertEqual(self.listing(AIR_MODULES[0])["total"], 5)

    async def test_missing_date_is_excluded_by_either_date_boundary(self):
        self.db.add(AirFinancialAuditData(
            id=503, source_type="peer_air", source_id=503,
            payable_data={"door_pickup_company": "提货单位", "delivery_company": "派送单位"},
            receivable_data={"waybill_number": "999-UNDATED", "flight_date": None},
        ))
        self.db.commit()
        for module in AIR_MODULES:
            self.assertEqual(self.listing(module, waybill_numbers="999-UNDATED")["total"], 1)
            for boundary in ("flight_date_start", "flight_date_end"):
                self.assertEqual(self.listing(module, waybill_numbers="999-UNDATED",
                                              **{boundary: "2026-10-21"})["total"], 0)

    async def test_settlement_is_independent_across_all_eight_air_categories(self):
        original = self.db.get(AirFinancialAuditData, 501)
        payable, receivable = dict(original.payable_data), dict(original.receivable_data)
        for index, module in enumerate(AIR_MODULES):
            endpoint = self.url(module, "/shenzhen_air/101/settle")
            self.assertEqual(self.client.post(endpoint).status_code, 200)
            self.db.refresh(original)
            timestamp = getattr(original, module.state + "_time")
            self.user = SimpleNamespace(id=8, name="其他财务")
            self.assertEqual(self.client.post(endpoint).status_code, 200)
            self.db.refresh(original)
            self.assertEqual(getattr(original, module.state + "_time"), timestamp)
            self.assertEqual(getattr(original, module.state + "_auditor_name"), "测试财务")
            self.user = SimpleNamespace(id=7, name="测试财务")
            for j, other in enumerate(AIR_MODULES):
                self.assertEqual(getattr(original, other.state + "_status"), int(j <= index))
            self.assertEqual(self.listing(module, settlement_status=1, pageSize=1)["total"], 1)
            self.assertEqual(self.listing(module, settlement_status=0, waybill_numbers="479-FINAL")["total"], 0)
        for module in AIR_MODULES:
            self.assertEqual(self.client.post(self.url(module, "/shenzhen_air/101/cancel-settlement")).status_code, 200)
            self.db.refresh(original)
            for suffix in ("_auditor_id", "_auditor_name", "_time"):
                self.assertIsNone(getattr(original, module.state + suffix))
        self.assertEqual((original.airline_settlement_status, original.pickup_settlement_status,
                          original.delivery_settlement_status, original.agent_settlement_status), (1, 1, 1, 1))
        self.assertEqual(original.financial_audit_status, 2)
        self.assertEqual(original.payable_data, payable)
        self.assertEqual(original.receivable_data, receivable)

    async def test_batch_rejects_invalid_source_atomically_for_every_module(self):
        for module in AIR_MODULES:
            for kind, source_id in (("shenzhen_air", "102"), ("peer_air", "999"), ("peer_air", "401")):
                response = self.client.post(self.url(module, "/batch-settle"), json={"items": [
                    {"source_type": "shenzhen_air", "source_id": "101"},
                    {"source_type": kind, "source_id": source_id},
                ]})
                self.assertEqual(response.status_code, 404, response.text)
                self.db.expire_all()
                self.assertEqual(getattr(self.db.get(AirFinancialAuditData, 501), module.state + "_status"), 0)
            self.assertEqual(self.client.post(self.url(module, "/batch-settle"), json={"items": []}).status_code, 200)
        self.assertEqual(self.db.query(AirFinancialAuditData).count(), 3)

    async def test_multi_source_and_manual_identity_batch_deduplicates(self):
        for module in (AIR_MODULES[0], AIR_MODULES[3]):
            items = [{"source_type": kind, "source_id": str(source_id)} for kind, source_id in (
                ("shenzhen_air", 101), ("china_southern_air", 201), ("peer_air", 301),
                ("shenzhen_air", 401), ("peer_air", 402), ("shenzhen_air", 101),
            )]
            response = self.client.post(self.url(module, "/batch-settle"), json={"items": items})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertIn("5", response.json()["msg"])
            self.assertEqual(self.listing(module, settlement_status=1)["total"], 5)
        self.db.expire_all()
        self.assertEqual(self.db.get(AirFinancialAuditData, 401).source_id, 0)

    async def test_logistics_settle_requires_membership_but_cancel_can_clear_stale_state(self):
        for module in AIR_MODULES[1:3]:
            response = self.client.post(self.url(module, "/china_southern_air/201/settle"))
            self.assertEqual(response.status_code, 400)
            self.assertEqual(self.client.post(self.url(module, "/shenzhen_air/101/settle")).status_code, 200)
        record = self.db.get(AirFinancialAuditData, 501)
        record.payable_data = {}
        record.receivable_data = {}
        manual = self.db.get(ShenzhenAirDepartureManualData, 111)
        manual.door_pickup_company = None
        self.db.commit()
        for module in AIR_MODULES[1:3]:
            self.assertEqual(self.client.post(self.url(module, "/shenzhen_air/101/cancel-settlement")).status_code, 200)
            self.db.refresh(record)
            self.assertEqual(getattr(record, module.state + "_status"), 0)

    async def test_commit_failure_rolls_back_all_new_statuses_and_keeps_json(self):
        for module in AIR_MODULES:
            with patch.object(self.db, "commit", side_effect=IntegrityError("insert", {}, Exception("conflict"))):
                with self.assertRaises(HTTPException) as error:
                    await set_air_settlement(module, {("shenzhen_air", 101)}, self.db, self.user, True)
            self.assertEqual(error.exception.status_code, 409)
            self.db.expire_all()
            record = self.db.get(AirFinancialAuditData, 501)
            self.assertEqual(getattr(record, module.state + "_status"), 0)
            self.assertEqual(record.receivable_data["freight"], "300")

    async def test_each_excel_uses_receivable_text_cells_and_selection_intersection(self):
        for module in AIR_MODULES:
            response = self.client.post(self.url(module, "/export"), json={
                "selected_items": [{"source_type": "shenzhen_air", "source_id": "101"}], "pageSize": 1,
            })
            self.assertEqual(response.status_code, 200, response.text[:200])
            workbook = load_workbook(BytesIO(response.content))
            sheet = workbook.active
            self.assertEqual(sheet.max_row, 2)
            headers = [cell.value for cell in sheet[1]]
            self.assertEqual(sheet.cell(2, headers.index("上门提货费") + 1).value, "11")
            phone = sheet.cell(2, headers.index("收货电话") + 1)
            self.assertEqual(phone.value, "0013800000000")
            self.assertEqual(phone.data_type, "s")
            formula = next(cell for cell in sheet[2] if cell.value == "=1+2")
            self.assertEqual(formula.data_type, "s")
            workbook.close()
            self.assertEqual(self.client.post(self.url(module, "/export"), json={
                "waybill_numbers": "not-found", "selected_items": [{"source_type": "shenzhen_air", "source_id": "101"}],
            }).status_code, 400)

    async def test_export_is_not_limited_to_page_size(self):
        for i in range(1000, 1205):
            self.db.add(AirFinancialAuditData(
                id=i, source_type="peer_air", source_id=i,
                payable_data={"door_pickup_company": "提货单位", "delivery_company": "派送单位"},
                receivable_data={"waybill_number": f"999-{i}", "flight_date": "2026-10-21"},
            ))
        self.db.commit()
        for module in AIR_MODULES:
            response = self.client.post(self.url(module, "/export"), json={"page": 2, "pageSize": 1})
            self.assertEqual(response.status_code, 200)
            workbook = load_workbook(BytesIO(response.content), read_only=True)
            self.assertGreater(len(list(workbook.active.rows)), 205)
            workbook.close()

    async def test_peer_actual_flight_uses_form_and_missing_metadata_falls_back(self):
        note = self.db.get(ConsignmentNote, 301)
        note.form_data = json.dumps({"actual_flight": "CA-ACTUAL"})
        self.db.add(AirFinancialAuditData(id=502, source_type="peer_air", source_id=301,
                                        payable_data={"door_pickup_company": "同行提货"}))
        self.db.commit()
        rows = self.listing(AIR_MODULES[1], actual_flight_number="CA-ACTUAL")["items"]
        self.assertEqual([row["source_id"] for row in rows], ["301"])

    async def test_http_validation_and_all_25_openapi_operations(self):
        spec = self.app.openapi()
        operations = [op for path in spec["paths"].values() for op in path.values()]
        self.assertEqual(len(operations), 25)
        self.assertEqual(len({op["operationId"] for op in operations}), 25)
        for module in AIR_MODULES:
            for params in ({"page": 0}, {"pageSize": 201}, {"settlement_status": 2},
                           {"financial_audit_status": 3}, {"flight_date_start": "invalid"}):
                self.assertEqual(self.client.get(self.url(module), params=params).status_code, 422)
            self.assertEqual(self.client.get(self.url(module), params={
                "flight_date_start": "2026-10-25", "flight_date_end": "2026-10-21",
            }).status_code, 400)
            for suffix in ("/invalid/101/settle", "/shenzhen_air/0/settle", "/shenzhen_air/9223372036854775808/settle"):
                self.assertEqual(self.client.post(self.url(module, suffix)).status_code, 422)
            self.assertEqual(self.client.post(self.url(module, "/batch-settle"), json={"items": [
                {"source_type": "shenzhen_air", "source_id": "9223372036854775808"},
            ]}).status_code, 422)
        self.app.dependency_overrides.pop(get_current_active_user)
        for route in router.routes:
            path = route.path.replace("{source_type}", "shenzhen_air").replace("{source_id}", "101")
            method = next(iter(route.methods)).lower()
            response = getattr(self.client, method)(PREFIX + path)
            self.assertIn(response.status_code, (401, 403), path)


class RoadReceivableTests(unittest.IsolatedAsyncioTestCase):
    add_note = road_fixture.RoadAgentTests.add_note

    def setUp(self):
        road_fixture.RoadAgentTests.setUp(self)
        self.app = make_app(self)
        self.client = TestClient(self.app)
        self.url = PREFIX + "/road-agent/road"

    def tearDown(self):
        self.client.close()
        road_fixture.RoadAgentTests.tearDown(self)

    def listing(self, **filters):
        response = self.client.get(self.url, params={"date_start": "2026-09-21", "date_end": "2026-10-21", **filters})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def test_road_receivable_matches_fee_desk_and_original_state_is_independent(self):
        self.db.add(PeerRoadDepartureManualData(
            id=201, consignment_note_id=101, agent_settlement_status=1, audit_status=1, financial_audit_status=2,
        ))
        self.db.commit()
        rows = self.listing()["items"]
        self.assertEqual(len(rows), 3)
        row = rows[0]
        self.assertEqual(row["settlement_status"], 0)
        self.assertNotIn("agent_settlement_status", row)
        self.assertEqual(row["total_amount"], "300.00")  # Must not recompute as 250+25.
        self.assertEqual(row["rate"], "2.5")
        self.assertEqual(row["chargeable_weight"], "120.00")
        self.assertEqual(self.client.post(self.url + "/101/settle").status_code, 200)
        self.assertEqual(self.listing(settlement_status=1)["total"], 1)
        self.assertEqual(self.listing(settlement_status=0)["total"], 2)
        record = self.db.get(PeerRoadDepartureManualData, 201)
        self.db.refresh(record)
        timestamp = record.receivable_agent_settlement_time
        self.user = SimpleNamespace(id=8, name="别的财务")
        self.assertEqual(self.client.post(self.url + "/101/settle").status_code, 200)
        self.db.refresh(record)
        self.assertEqual(record.receivable_agent_settlement_auditor_name, "测试财务")
        self.assertEqual(record.receivable_agent_settlement_time, timestamp)
        self.assertEqual(self.client.post(self.url + "/101/cancel-settlement").status_code, 200)
        self.db.refresh(record)
        self.assertEqual((record.agent_settlement_status, record.audit_status, record.financial_audit_status), (1, 1, 2))
        self.assertEqual(record.receivable_agent_settlement_status, 0)
        self.assertIsNone(record.receivable_agent_settlement_time)
        self.assertEqual(json.loads(self.db.get(ConsignmentNote, 101).form_data), self.form)

    async def test_missing_rate_total_and_unreviewed_road_remain_readable(self):
        note = self.db.get(ConsignmentNote, 101)
        note.form_data = json.dumps({"quantity": 0, "total_freight": 1, "other_fees": 1})
        self.db.commit()
        row = self.listing()["items"][0]
        self.assertIsNone(row["rate"])
        self.assertIsNone(row["total_amount"])
        self.assertIsNone(row["chargeable_weight"])
        self.assertEqual(row["quantity"], "0")
        self.assertEqual(self.listing(settlement_status=0)["total"], 3)
        self.assertEqual(self.db.query(PeerRoadDepartureManualData).count(), 1)
        self.assertEqual(self.client.post(self.url + "/101/cancel-settlement").status_code, 200)
        self.assertEqual(self.db.query(PeerRoadDepartureManualData).count(), 1)

    async def test_road_receivable_filters_do_not_apply_payable_settlement(self):
        self.db.add(PeerRoadDepartureManualData(
            id=201, consignment_note_id=101, agent_settlement_status=1,
            receivable_agent_settlement_status=0,
        ))
        self.db.get(PeerRoadDepartureManualData, 202).receivable_agent_settlement_status = 1
        self.db.commit()
        self.assertEqual([row["source_id"] for row in self.listing(settlement_status=1)["items"]], ["102"])
        self.assertEqual([row["source_id"] for row in self.listing(settlement_status=0)["items"]], ["101", "103"])
        response = self.client.post(self.url + "/export", json={
            "date_start": "2026-09-21", "date_end": "2026-10-21", "settlement_status": 1,
            "selected_items": [{"source_id": "101"}, {"source_id": "102"}],
        })
        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.active.max_row, 2)
        headers = [cell.value for cell in workbook.active[1]]
        self.assertEqual(workbook.active.cell(2, headers.index("来源ID") + 1).value, "102")
        self.assertEqual(workbook.active.cell(2, headers.index("结算状态") + 1).value, "已结算")
        self.assertEqual(workbook.active.cell(2, headers.index("客户公司名称") + 1).value, "普通客户")
        workbook.close()

    async def test_frontend_same_day_query_and_empty_results(self):
        response = self.client.get(self.url, params={"date_start": "2026-10-22", "date_end": "2026-10-22"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["total"], 1)
        self.assertEqual(response.json()["data"]["items"][0]["source_id"], "105")
        response = self.client.get(self.url, params={"date_start": "2020-01-01", "date_end": "2020-01-01"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"], {"items": [], "total": 0, "page": 1, "pageSize": 10})

    async def test_road_batch_atomic_validation_deduplication_and_rollback(self):
        for invalid in ("999", "106"):
            response = self.client.post(self.url + "/batch-settle", json={"items": [
                {"source_id": "101"}, {"source_id": invalid},
            ]})
            self.assertEqual(response.status_code, 404)
            self.assertEqual(self.listing(settlement_status=1)["total"], 0)
        with patch.object(self.db, "commit", side_effect=IntegrityError("insert", {}, Exception("conflict"))):
            with self.assertRaises(HTTPException) as error:
                set_road_settlement({101, 102}, self.db, self.user, True)
        self.assertEqual(error.exception.status_code, 409)
        self.assertEqual(self.listing(settlement_status=1)["total"], 0)
        response = self.client.post(self.url + "/batch-settle", json={"items": [
            {"source_id": "101"}, {"source_id": "102"}, {"source_id": "101"},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertIn("2", response.json()["msg"])
        self.assertEqual(self.listing(settlement_status=1)["total"], 2)

    async def test_road_search_export_filters_text_cells_and_validation(self):
        self.assertEqual(self.listing(customer_name="测试", destination_city="CG")["total"], 1)
        self.assertEqual(self.listing(customer_name="%")["total"], 1)
        self.assertEqual(self.listing(destination_city="_")["total"], 1)
        note = self.db.get(ConsignmentNote, 101)
        note.form_data = json.dumps({**self.form, "cargo_name": "=1+2"})
        self.db.commit()
        response = self.client.post(self.url + "/export", json={"date_start": None, "date_end": None,
            "selected_items": [{"source_id": "101"}], "pageSize": 1})
        self.assertEqual(response.status_code, 200, response.text[:200])
        workbook = load_workbook(BytesIO(response.content))
        self.assertEqual(workbook.active.max_row, 2)
        headers = [cell.value for cell in workbook.active[1]]
        self.assertEqual(workbook.active.cell(2, headers.index("计费重量") + 1).value, "120.00")
        cells = list(workbook.active[2])
        self.assertEqual(next(cell for cell in cells if cell.value == "=1+2").data_type, "s")
        self.assertEqual(next(cell for cell in cells if cell.value == "0013800000000").data_type, "s")
        workbook.close()
        response = self.client.post(self.url + "/export", json={"customer_name": "不存在"})
        self.assertEqual(response.status_code, 400)
        for params in ({"page": 0}, {"settlement_status": 2}, {"date_start": "bad"}, {"pageSize": 201}):
            self.assertEqual(self.client.get(self.url, params=params).status_code, 422)
        self.assertEqual(self.client.get(self.url, params={"date_start": "2026-10-22", "date_end": "2026-10-21"}).status_code, 400)
        self.assertEqual(self.client.post(self.url + "/0/settle").status_code, 422)


if __name__ == "__main__":
    unittest.main()
