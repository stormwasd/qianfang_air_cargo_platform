"""南航出港运单号及订舱状态筛选的 HTTP/SQL 回归。"""
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
from app.models.customer import Customer


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
                      CsaProductInformation, CsaLalamoveInformation, RPATaskLastSuccess, Customer):
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

    def seed_booking_statuses(self):
        values = {
            1: "65294402 ( KK )", 2: "65294350 ( UU )", 3: "65294403(KK)",
            4: None, 5: "KK65294404 (UU)", 6: "UU65294405 (KK)",
            7: "65294406 (KKX)", 8: "65294407 KK", 9: "65294408 (KK) 备注",
            10: "65294409（ UU ）  ", 11: "65294410 (\tkk \n)\r\n",
            12: "65294411 (UU) (XX)", 13: "65294412 (KK) (UU)", 14: "",
        }
        for record_id, value in values.items():
            row = self.db.get(ChinaSouthernAirApprovalData, record_id)
            if row is None:
                row = ChinaSouthernAirApprovalData(
                    id=record_id, waybill_number=f"784-220000{record_id:02d}",
                    flight_info="CZ1234 / 2026-10-23 / SZX - PEK",
                )
                self.db.add(row)
            row.booking_no = value
        self.db.commit()

    def test_booking_status_single_and_multiple_use_final_parenthesized_marker(self):
        self.seed_booking_statuses()
        kk_ids, uu_ids = {"1", "3", "6", "11"}, {"2", "5", "10", "13"}
        for keyword, expected_ids in (("KK", kk_ids), ("UU", uu_ids),
                                      ("KK,UU", kk_ids | uu_ids), ("UU,KK", kk_ids | uu_ids),
                                      (" kk, KK, , uu ", kk_ids | uu_ids)):
            with self.subTest(keyword=keyword):
                data = self.listing(waybill_status=keyword, pageSize=50)
                self.assertEqual(data["total"], len(expected_ids))
                self.assertEqual({row["id"] for row in data["items"]}, expected_ids)
                # 筛选不改动展示给前端的原订舱号。
                for row in data["items"]:
                    self.assertEqual(row["booking_no"], self.db.get(ChinaSouthernAirApprovalData, int(row["id"])).booking_no)

    def test_empty_booking_status_preserves_unfiltered_results(self):
        self.seed_booking_statuses()
        baseline = self.listing(pageSize=50)
        self.assertEqual(baseline["total"], 14)
        for keyword in ("", " ", ", ,"):
            self.assertEqual(self.listing(waybill_status=keyword, pageSize=50), baseline)

    def test_invalid_booking_status_returns_422_instead_of_broadening_query(self):
        for keyword in ("XX", "KK,XX", "KK UU", "KK，UU", "%", "(KK)", "KK|UU", "KK' OR 1=1 --"):
            with self.subTest(keyword=keyword):
                response = self.client.get("/api/v1/departure-tracking/china-southern-air",
                                           params={"waybill_status": keyword})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("仅支持KK、UU", response.json()["detail"])

    def test_booking_status_combines_with_other_filters_before_count_and_pagination(self):
        self.seed_booking_statuses()
        self.db.add(CsaDepartureManualData(id=12, approval_data_id=2, customer_name="客户甲", audit_status=2))
        self.db.commit()
        params = dict(waybill_status="KK,UU", customer_name="客户甲", audit_status=2,
                      waybill_number="777", flight_number="CZ1234", origin="SZX", destination="PEK",
                      flight_date_start="2026-10-23", flight_date_end="2026-10-23", pageSize=1)
        for page, expected_id in ((1, "2"), (2, "1")):
            data = self.listing(**params, page=page)
            self.assertEqual(data["total"], 2)
            self.assertEqual([row["id"] for row in data["items"]], [expected_id])
        self.assertEqual(self.listing(**params, page=3)["items"], [])
        params["waybill_status"] = "KK"
        data = self.listing(**params)
        self.assertEqual(data["total"], 1)
        row = data["items"][0]
        self.assertEqual(row["id"], "1")
        self.assertEqual(row["actual_customer_name"], "客户甲")
        self.assertEqual(row["manual_data"]["audit_status"], 2)
        self.assertEqual(row["product_information"][0]["id"], "21")
        self.assertEqual(row["lalamove_information"][0]["id"], "31")
        params["waybill_status"] = "UU"
        self.assertEqual(self.listing(**params)["items"][0]["id"], "2")
        params["waybill_number"] = "不存在"
        self.assertEqual(self.listing(**params)["total"], 0)

    def test_openapi_describes_booking_status_multi_select_only_for_csa(self):
        paths = self.app.openapi()["paths"]
        parameters = paths["/api/v1/departure-tracking/china-southern-air"]["get"]["parameters"]
        parameter = next(p for p in parameters if p["name"] == "waybill_status")
        self.assertIn("多选", parameter["description"])
        self.assertIn("末尾括号", parameter["description"])
        self.assertFalse(parameter["required"])
        shenzhen = paths["/api/v1/departure-tracking/shenzhen-air"]["get"]["parameters"]
        self.assertNotIn("waybill_status", {p["name"] for p in shenzhen})


if __name__ == "__main__":
    unittest.main()
