"""两家出港列表客户名称、搜索及暂存/提交的 HTTP + SQL 回归。"""
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.departure_tracking import router
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaLalamoveInformation, CsaProductInformation
from app.models.customer import Customer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.rpa_task import RPATaskLastSuccess
from app.models.transit_loading import ShenzhenAirBookingExport


CUSTOMER_ID = 373379437934284801  # 超过 JavaScript Number 的安全整数范围。


class DepartureCustomerWorkflowTests(unittest.TestCase):
    airlines = (
        ("shenzhen-air", ShenzhenAirDepartureManualData, "booking_export_id"),
        ("china-southern-air", CsaDepartureManualData, "approval_data_id"),
    )

    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def functions(connection, _):
            def substring_index(value, delimiter, count):
                if value is None:
                    return None
                parts = value.split(delimiter)
                return delimiter.join(parts[:count] if count > 0 else parts[count:])
            connection.create_function("substring_index", 3, substring_index)

        for model in (Customer, ShenzhenAirBookingExport, ShenzhenAirBillingTimeContainer,
                      ShenzhenAirDepartureManualData, ChinaSouthernAirApprovalData,
                      CsaDepartureManualData, CsaProductInformation, CsaLalamoveInformation,
                      RPATaskLastSuccess):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([
            Customer(id=CUSTOMER_ID, company_name="晨德通", rate=0, contact_person="", contact_phone=""),
            Customer(id=CUSTOMER_ID + 1, company_name="特殊%_客户", rate=0, contact_person="", contact_phone=""),
        ])
        for record_id in range(1, 8):
            self.db.add(ShenzhenAirBookingExport(
                id=record_id, waybill_number=f"6220000{record_id}", flight_date="2026-10-28",
                billing_flight="ZH1234", routing="SZX-PEK",
            ))
            self.db.add(ChinaSouthernAirApprovalData(
                id=record_id, waybill_number=f"784-2200000{record_id}",
                flight_info="CZ1234 / 2026-10-28 / SZX - PEK",
            ))
        for _, model, foreign_key in self.airlines:
            for record_id, raw in ((1, str(CUSTOMER_ID)), (2, "历史客户"),
                                   (3, str(CUSTOMER_ID + 5)), (4, str(CUSTOMER_ID + 1)),
                                   (5, str(CUSTOMER_ID) + "abc"), (6, "9" * 255)):
                self.db.add(model(id=record_id + 10, **{foreign_key: record_id},
                                  customer_name=raw, audit_status=1))
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/departure-tracking")

        def database():
            yield self.db
        self.app.dependency_overrides[get_db] = database
        self.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=77, name="测试用户")
        self.client = TestClient(self.app)
        self.base = "/api/v1/departure-tracking/"

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def listing(self, airline, **params):
        response = self.client.get(self.base + airline, params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["code"], 0)
        return response.json()["data"]

    def test_display_resolves_large_id_preserves_raw_and_handles_legacy_and_missing(self):
        for airline, _, _ in self.airlines:
            with self.subTest(airline=airline):
                rows = {row["id"]: row for row in self.listing(airline)["items"]}
                self.assertEqual(rows["1"]["actual_customer_name"], "晨德通")
                self.assertEqual(rows["1"]["manual_data"]["customer_name"], str(CUSTOMER_ID))
                self.assertEqual(rows["2"]["actual_customer_name"], "历史客户")
                self.assertEqual(rows["3"]["actual_customer_name"], "")
                self.assertEqual(rows["4"]["actual_customer_name"], "特殊%_客户")
                self.assertEqual(rows["5"]["actual_customer_name"], str(CUSTOMER_ID) + "abc")
                self.assertEqual(rows["6"]["actual_customer_name"], "")
                self.assertEqual(rows["7"]["actual_customer_name"], "")
                self.assertIsNone(rows["7"]["manual_data"])

    def test_name_and_id_search_escape_wildcards_and_apply_before_pagination(self):
        for airline, _, _ in self.airlines:
            for keyword, ids in (("晨德", {"1"}), (str(CUSTOMER_ID), {"1"}),
                                 ("历史", {"2"}), ("%", {"4"}), ("_", {"4"}),
                                 (" 特殊 ", {"4"}), ("不存在", set()),
                                 ("' OR 1=1 --", set())):
                with self.subTest(airline=airline, keyword=keyword):
                    data = self.listing(airline, customer_name=keyword)
                    self.assertEqual(data["total"], len(ids))
                    self.assertEqual({row["id"] for row in data["items"]}, ids)
            self.assertEqual(self.listing(airline, customer_name="  ")["total"], 7)
            for page, expected in ((1, "4"), (2, "2")):
                data = self.listing(airline, customer_name="客户", pageSize=1, page=page,
                                    audit_status=1, flight_date_start="2026-10-28",
                                    flight_date_end="2026-10-28", origin="SZX", destination="PEK")
                self.assertEqual(data["total"], 2)
                self.assertEqual(data["items"][0]["id"], expected)

    def test_draft_submit_reload_partial_save_and_clear(self):
        for airline, model, foreign_key in self.airlines:
            with self.subTest(airline=airline):
                url = self.base + airline + "/audit"
                payload = {foreign_key: "7", "action": "draft", "customer_name": str(CUSTOMER_ID),
                           "packaging_fee": "2", "remark": "测试暂存"}
                response = self.client.post(url, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["msg"], "暂存成功")
                draft = self.db.query(model).filter(getattr(model, foreign_key) == 7).one()
                self.db.refresh(draft)
                self.assertEqual(draft.audit_status, 1)
                self.assertIsNone(draft.auditor_id)
                self.assertIsNone(draft.audit_time)
                data = self.listing(airline, customer_name="晨德通", audit_status=1)
                self.assertEqual(data["total"], 2)
                saved = next(row for row in data["items"] if row["id"] == "7")
                self.assertEqual(saved["actual_customer_name"], "晨德通")
                self.assertEqual(saved["manual_data"]["packaging_fee"], "2")
                response = self.client.post(url, json={foreign_key: "7", "action": "submit"})
                self.assertEqual(response.status_code, 200, response.text)
                self.db.refresh(draft)
                self.assertEqual(draft.audit_status, 2)
                self.assertEqual(draft.customer_name, str(CUSTOMER_ID))
                self.assertEqual(draft.remark, "测试暂存")
                self.assertEqual(draft.auditor_id, 77)
                self.assertEqual(draft.auditor_name, "测试用户")
                self.assertIsNotNone(draft.audit_time)
                data = self.listing(airline, audit_status=2)
                self.assertEqual(data["total"], 1)
                self.assertEqual(data["items"][0]["manual_data"]["audit_status"], 2)
                # 不改变既有语义：已提交记录再次暂存会回到1；未传字段继续保留。
                response = self.client.post(url, json={foreign_key: "7", "action": "draft", "remark": "新暂存"})
                self.assertEqual(response.status_code, 200)
                self.db.refresh(draft)
                self.assertEqual(draft.audit_status, 1)
                self.assertEqual(draft.packaging_fee, "2")
                self.assertEqual(self.listing(airline, audit_status=2)["total"], 0)
                response = self.client.post(url, json={foreign_key: "7", "action": "draft", "customer_name": None})
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("7", {row["id"] for row in self.listing(airline, customer_name="晨德通")["items"]})
                row = next(row for row in self.listing(airline)["items"] if row["id"] == "7")
                self.assertEqual(row["actual_customer_name"], "")
                self.assertIsNone(row["manual_data"]["customer_name"])

    def test_invalid_action_rejected_before_mutation_and_legacy_save_keeps_status(self):
        for airline, model, foreign_key in self.airlines:
            url = self.base + airline
            response = self.client.post(url + "/audit", json={foreign_key: "1", "action": "invalid", "customer_name": "改名"})
            self.assertEqual(response.status_code, 422)
            response = self.client.put(url + "/manual-data", json={foreign_key: "1", "remark": "旧保存接口"})
            self.assertEqual(response.status_code, 200, response.text)
            row = self.db.query(model).filter(getattr(model, foreign_key) == 1).one()
            self.db.refresh(row)
            self.assertEqual(row.audit_status, 1)
            self.assertEqual(row.customer_name, str(CUSTOMER_ID))
            self.assertEqual(row.remark, "旧保存接口")

    def test_customer_rename_and_deletion_change_display_without_rewriting_manual_data(self):
        customer = self.db.get(Customer, CUSTOMER_ID)
        customer.company_name = "新客户名称"
        self.db.commit()
        for airline, _, _ in self.airlines:
            self.assertEqual(self.listing(airline, customer_name="晨德通")["total"], 0)
            row = self.listing(airline, customer_name="新客户名称")["items"][0]
            self.assertEqual(row["actual_customer_name"], "新客户名称")
            self.assertEqual(row["manual_data"]["customer_name"], str(CUSTOMER_ID))
        self.db.delete(customer)
        self.db.commit()
        for airline, _, _ in self.airlines:
            row = self.listing(airline, customer_name=str(CUSTOMER_ID))["items"][0]
            self.assertEqual(row["actual_customer_name"], "")
            self.assertEqual(row["manual_data"]["customer_name"], str(CUSTOMER_ID))

    def test_customer_lookup_is_one_query_per_page_and_empty_page_needs_none(self):
        queries = []

        def capture(_, __, statement, ___, ____, _____):
            if "FROM customers" in statement:
                queries.append(statement)

        event.listen(self.engine, "before_cursor_execute", capture)
        try:
            for airline, _, _ in self.airlines:
                queries.clear()
                self.listing(airline)
                self.assertEqual(len(queries), 1)
                queries.clear()
                self.listing(airline, page=99)
                self.assertEqual(queries, [])
        finally:
            event.remove(self.engine, "before_cursor_execute", capture)


if __name__ == "__main__":
    unittest.main()
