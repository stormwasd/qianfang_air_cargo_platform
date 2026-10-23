"""南航出港运单号模糊筛选的 HTTP/SQL 回归。"""
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
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaLalamoveInformation, CsaProductInformation
from app.models.rpa_task import RPATaskLastSuccess


def substring_index(value, delimiter, count):
    """SQLite 测试环境补齐现有日期筛选依赖的 MySQL 函数。"""
    if value is None:
        return None
    parts = value.split(delimiter)
    return delimiter.join(parts[:count] if count > 0 else parts[count:]) if count else ""


class CsaDepartureWaybillSearchTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
        )

        @event.listens_for(self.engine, "connect")
        def install_functions(connection, _):
            connection.create_function("substring_index", 3, substring_index)

        for model in (ChinaSouthernAirApprovalData, CsaDepartureManualData,
                      CsaProductInformation, CsaLalamoveInformation, RPATaskLastSuccess):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.db.add_all([
            ChinaSouthernAirApprovalData(id=1, waybill_number="784-22007775",
                                        flight_info="CZ1234 / 2026-10-23 / SZX - PEK"),
            ChinaSouthernAirApprovalData(id=2, waybill_number="784-22007776",
                                        flight_info="CZ1234 / 2026-10-23 / SZX - PEK"),
            ChinaSouthernAirApprovalData(id=3, waybill_number="784-22009999",
                                        flight_info="CZ1234 / 2026-10-24 / SZX - PEK"),
            ChinaSouthernAirApprovalData(id=4, waybill_number=None,
                                        flight_info="CZ1234 / 2026-10-23 / SZX - PEK"),
            CsaDepartureManualData(id=11, approval_data_id=1, customer_name="客户甲", audit_status=2),
            CsaProductInformation(id=21, approval_data_id=1, pieces="30"),
            CsaLalamoveInformation(id=31, approval_data_id=1, pieces="20"),
        ])
        self.db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/departure-tracking")

        def database():
            yield self.db

        app.dependency_overrides[get_db] = database
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=7, name="测试")
        self.client = TestClient(app)
        self.app = app

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def listing(self, **params):
        response = self.client.get("/api/v1/departure-tracking/china-southern-air", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["code"], 0)
        self.assertEqual(payload["msg"], "查询成功")
        return payload["data"]

    def test_complete_number_suffix_and_middle_substring(self):
        for keyword, expected_ids in (("784-22007775", {"1"}), ("7775", {"1"}),
                                      ("2200777", {"1", "2"}), ("784-", {"1", "2", "3"})):
            with self.subTest(keyword=keyword):
                data = self.listing(waybill_number=keyword)
                self.assertEqual(data["total"], len(expected_ids))
                self.assertEqual({row["id"] for row in data["items"]}, expected_ids)

    def test_multiple_keywords_or_trim_empty_and_overlapping_matches(self):
        for keyword in (" 7775, 7776, ,7775 ", "784-22007775,7776", "2200777,7775"):
            with self.subTest(keyword=keyword):
                data = self.listing(waybill_number=keyword)
                self.assertEqual(data["total"], 2)
                self.assertEqual([row["id"] for row in data["items"]], ["2", "1"])

    def test_empty_keywords_keep_existing_unfiltered_behavior(self):
        baseline = self.listing()
        self.assertEqual(baseline["total"], 4)
        for keyword in ("", " ", ", ,"):
            self.assertEqual(self.listing(waybill_number=keyword), baseline)

    def test_date_filters_are_anded_with_all_keywords_before_pagination(self):
        params = {"waybill_number": "777,9999", "flight_date_start": "2026-10-23",
                  "flight_date_end": "2026-10-23", "pageSize": 1}
        for page, expected_id in ((1, "2"), (2, "1")):
            data = self.listing(**params, page=page)
            self.assertEqual(data["total"], 2)
            self.assertEqual([row["id"] for row in data["items"]], [expected_id])
        self.assertEqual(self.listing(**params, page=3)["items"], [])

    def test_manual_filters_and_nested_data_preserved(self):
        baseline = self.listing(waybill_number="784-22007775")
        data = self.listing(waybill_number="777", customer_name="客户甲", audit_status=2,
                            flight_number="CZ1234", origin="SZX", destination="PEK")
        self.assertEqual(data, baseline)
        row = data["items"][0]
        self.assertEqual(row["product_information"][0]["id"], "21")
        self.assertEqual(row["lalamove_information"][0]["id"], "31")
        self.assertEqual(row["manual_data"]["audit_status"], 2)

    def test_special_characters_are_literal_and_no_match_returns_empty_list(self):
        for record_id, number in ((5, "784-22%007775"), (6, "784-22_007775"),
                                  (7, "784-22/007775"), (8, "784-22'007775")):
            self.db.add(ChinaSouthernAirApprovalData(id=record_id, waybill_number=number))
        self.db.commit()
        for keyword, expected_id in (("%", "5"), ("_", "6"), ("/", "7"), ("'", "8")):
            with self.subTest(keyword=keyword):
                data = self.listing(waybill_number=keyword)
                self.assertEqual(data["total"], 1)
                self.assertEqual(data["items"][0]["id"], expected_id)
        for keyword in ("does-not-exist", "' OR 1=1 --"):
            data = self.listing(waybill_number=keyword)
            self.assertEqual(data, {"total": 0, "items": [], "data_update_time": None})

    def test_openapi_describes_fuzzy_search_and_pagination_validation_unchanged(self):
        operation = self.app.openapi()["paths"]["/api/v1/departure-tracking/china-southern-air"]["get"]
        parameter = next(p for p in operation["parameters"] if p["name"] == "waybill_number")
        self.assertIn("模糊", parameter["description"])
        self.assertIn("任意一个", parameter["description"])
        for params in ({"page": 0}, {"pageSize": 501}):
            response = self.client.get("/api/v1/departure-tracking/china-southern-air", params=params)
            self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
