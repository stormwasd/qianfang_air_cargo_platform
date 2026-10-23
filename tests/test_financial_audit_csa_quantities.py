"""南航开单件数、重量的源字段映射及暂存、审核后的展示回归。"""
import copy
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.api.financial_audit import router
from app.database import get_db
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from tests import test_reconciliation_agent as air_fixture


class CsaBillingQuantitiesTests(unittest.TestCase):
    def setUp(self):
        air_fixture.AgentReconciliationTests.setUp(self)
        self.approval = self.db.get(ChinaSouthernAirApprovalData, 201)
        self.approval.booking_pieces = "30"
        self.approval.booking_weight = "300"
        self.approval.billing_qty = "0 / 0 / 0 (30 / 300 / 1.80)"
        self.db.commit()

        app = FastAPI()
        app.include_router(router, prefix="/api/v1/financial-audit")

        def database():
            yield self.db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_active_user] = lambda: self.user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        air_fixture.AgentReconciliationTests.tearDown(self)

    def listing(self, **filters):
        response = self.client.get("/api/v1/financial-audit/air", params=filters)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def southern_item(self):
        result = self.listing(airline_type="china_southern_air")
        return next(row for row in result["items"] if row["source_id"] == "201")

    def assert_billing(self, row, pieces, weight):
        self.assertEqual(row["billing_quantity"], pieces)
        self.assertEqual(row["billing_weight"], weight)
        self.assertEqual(row["payable"]["billing_pieces"], pieces)
        self.assertEqual(row["payable"]["billing_weight"], weight)

    def test_screenshot_values_use_booking_fields_without_changing_other_data(self):
        # Compare the complete response with only the two source fields changed.
        self.approval.booking_pieces = "0"
        self.approval.booking_weight = "0"
        self.db.commit()
        before = self.southern_item()
        self.approval.booking_pieces = "30"
        self.approval.booking_weight = "300"
        self.db.commit()
        after = self.southern_item()
        self.assert_billing(after, "30", "300")
        expected = copy.deepcopy(before)
        expected["billing_quantity"] = "30"
        expected["billing_weight"] = "300"
        expected["payable"]["billing_pieces"] = "30"
        expected["payable"]["billing_weight"] = "300"
        self.assertEqual(after, expected)
        self.assertEqual(after["receivable"]["pieces"], "0")
        self.assertEqual(after["payable"]["chargeable_weight"], "20")
        self.assertEqual(self.approval.billing_qty, "0 / 0 / 0 (30 / 300 / 1.80)")

    def test_zero_blank_and_decimal_source_values_never_fall_back_to_billing_qty(self):
        self.approval.billing_qty = "9 / 90 / 1 (30 / 300 / 1.80)"
        for pieces, weight, expected_pieces, expected_weight in (
            ("30", "300.00", "30", "300.00"),
            ("0", "0", "0", "0"),
            (None, None, "", ""),
            ("", "", "", ""),
            ("30", None, "30", ""),
            (None, "300", "", "300"),
        ):
            with self.subTest(pieces=pieces, weight=weight):
                self.approval.booking_pieces = pieces
                self.approval.booking_weight = weight
                self.db.commit()
                row = self.southern_item()
                self.assert_billing(row, expected_pieces, expected_weight)
                self.assertEqual(row["receivable"]["pieces"], "9")

    def test_historical_saved_quantities_cannot_mask_source_and_reads_do_not_rewrite_json(self):
        for status, stale in ((1, "0"), (2, "99")):
            with self.subTest(status=status):
                saved_payable = {"billing_pieces": stale, "billing_weight": stale,
                                 "air_freight": "123.45", "packaging_fee": "6.70",
                                 "other_fee_remark": "保留人工备注", "chargeable_weight": "21"}
                saved_receivable = {"pieces": "7", "weight": "22", "remark": "应收不变"}
                fa = self.db.get(AirFinancialAuditData, 501)
                if fa is None:
                    fa = AirFinancialAuditData(id=501, source_type="china_southern_air", source_id=201)
                    self.db.add(fa)
                fa.payable_data = copy.deepcopy(saved_payable)
                fa.receivable_data = copy.deepcopy(saved_receivable)
                fa.financial_audit_status = status
                self.db.commit()
                count = self.db.query(AirFinancialAuditData).count()
                row = self.southern_item()
                self.assert_billing(row, "30", "300")
                self.assertEqual(row["financial_audit_status"], status)
                for key in ("air_freight", "packaging_fee", "other_fee_remark", "chargeable_weight"):
                    self.assertEqual(row["payable"][key], saved_payable[key])
                for key, value in saved_receivable.items():
                    self.assertEqual(row["receivable"][key], value)
                self.db.refresh(fa)
                self.assertEqual(fa.payable_data, saved_payable)
                self.assertEqual(fa.receivable_data, saved_receivable)
                self.assertEqual(self.db.query(AirFinancialAuditData).count(), count)

    def test_save_and_submit_round_trip_uses_live_booking_quantities(self):
        for action, expected_status in (("save", 1), ("submit", 2)):
            with self.subTest(action=action):
                response = self.client.post(
                    "/api/v1/financial-audit/air/audit", params={"action": action},
                    json={"source_type": "china_southern_air", "source_id": "201",
                          "payable": {"billing_pieces": 0, "billing_weight": 0,
                                      "other_fee_remark": "原页面暂存", "air_freight": "40"},
                          "receivable": {"pieces": "8", "remark": "保留应收数据"}},
                )
                self.assertEqual(response.status_code, 200, response.text)
                row = self.southern_item()
                self.assert_billing(row, "30", "300")
                self.assertEqual(row["financial_audit_status"], expected_status)
                self.assertEqual(row["payable"]["other_fee_remark"], "原页面暂存")
                self.assertEqual(row["receivable"]["pieces"], "8")
        self.approval.booking_pieces = "31"
        self.approval.booking_weight = "310"
        self.db.commit()
        self.assert_billing(self.southern_item(), "31", "310")

    def test_manual_southern_entries_keep_user_entered_billing_fields(self):
        for source_id in (0, 502):
            with self.subTest(source_id=source_id):
                fa = self.db.get(AirFinancialAuditData, 502)
                if fa is None:
                    fa = AirFinancialAuditData(id=502, source_type="china_southern_air")
                    self.db.add(fa)
                fa.source_id = source_id
                fa.payable_data = {"billing_pieces": "5", "billing_weight": "51.50"}
                fa.receivable_data = {"airline": "南航", "waybill_number": "784-MANUAL",
                                      "flight_date": "2026-10-22"}
                self.db.commit()
                result = self.listing(airline_type="china_southern_air")
                row = next(row for row in result["items"] if row["source_id"] == "502")
                self.assert_billing(row, "5", "51.50")

    def test_shenzhen_and_peer_mappings_and_saved_overrides_are_unchanged(self):
        before = {kind: self.listing(airline_type=kind)
                  for kind in ("shenzhen_air", "peer_air")}
        self.approval.booking_pieces = "999"
        self.approval.booking_weight = "9999"
        self.db.commit()
        for kind, expected in before.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.listing(airline_type=kind), expected)
        for fa_id, kind, source_id in ((503, "shenzhen_air", 101), (504, "peer_air", 301)):
            self.db.add(AirFinancialAuditData(
                id=fa_id, source_type=kind, source_id=source_id,
                payable_data={"billing_pieces": "77", "billing_weight": "770"},
            ))
        self.db.commit()
        for kind, source_id, pieces in (("shenzhen_air", "101", "2"), ("peer_air", "301", "3")):
            with self.subTest(kind=kind):
                row = next(row for row in self.listing(airline_type=kind)["items"]
                           if row["source_id"] == source_id)
                self.assertEqual(row["billing_quantity"], pieces)
                self.assertEqual(row["payable"]["billing_pieces"], "77")
                self.assertEqual(row["payable"]["billing_weight"], "770")


if __name__ == "__main__":
    unittest.main()
