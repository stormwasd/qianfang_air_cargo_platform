"""派送单位可选联系方式的 HTTP 和数据库回归。"""
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.delivery_units import router
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.delivery_unit import DeliveryUnit


class DeliveryUnitTests(unittest.TestCase):
    prefix = "/api/v1/delivery-units"

    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        DeliveryUnit.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.app = FastAPI()
        self.app.include_router(router, prefix=self.prefix)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=7, name="测试用户")
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()
        self.db.close()
        self.engine.dispose()

    def create(self, **contacts):
        response = self.client.post(self.prefix, json={
            "delivery_name": "测试派送单位", "settlement_method": 1, **contacts,
        })
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    def test_create_accepts_omitted_empty_null_and_individually_missing_contacts(self):
        for values in ({}, {"contact_person": "", "contact_phone": ""},
                       {"contact_person": None, "contact_phone": None},
                       {"contact_person": "张三"}, {"contact_phone": "0013800000000"}):
            with self.subTest(values=values):
                data = self.create(**values)
                record = self.db.get(DeliveryUnit, int(data["id"]))
                for name in ("contact_person", "contact_phone"):
                    self.assertEqual(data[name], values.get(name) or "")
                    self.assertEqual(getattr(record, name), data[name])
                self.assertEqual(data["creator_id"], "7")
                self.assertTrue(data["delivery_code"].startswith("PSS"))

    def test_update_preserves_omitted_contacts_and_allows_independent_clearing(self):
        data = self.create(contact_person="张三", contact_phone="0013800000000")
        url = self.prefix + "/" + data["id"]
        for payload, person, phone in (
            ({"delivery_name": "已修改"}, "张三", "0013800000000"),
            ({"contact_person": None}, "", "0013800000000"),
            ({"contact_phone": ""}, "", ""),
            ({"contact_person": "李四", "contact_phone": "00123"}, "李四", "00123"),
            ({"contact_phone": None}, "李四", ""),
            ({"contact_person": ""}, "", ""),
        ):
            with self.subTest(payload=payload):
                response = self.client.put(url, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                result = response.json()["data"]
                self.assertEqual((result["contact_person"], result["contact_phone"]), (person, phone))
                self.db.expire_all()
                record = self.db.get(DeliveryUnit, int(data["id"]))
                self.assertEqual((record.contact_person, record.contact_phone), (person, phone))

    def test_empty_contacts_work_in_detail_and_filtered_list(self):
        data = self.create()
        detail = self.client.get(self.prefix + "/" + data["id"])
        listing = self.client.get(self.prefix, params={"delivery_name": "测试派送", "pageSize": 1})
        for response in (detail, listing):
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(listing.json()["data"]["total"], 1)
        self.assertEqual(listing.json()["data"]["items"][0], detail.json()["data"])
        self.assertEqual(detail.json()["data"]["contact_phone"], "")

    def test_existing_required_fields_lengths_and_types_remain_validated(self):
        valid = {"delivery_name": "测试派送单位", "settlement_method": 1}
        for payload in ({"settlement_method": 1}, {"delivery_name": "测试派送单位"},
                        {**valid, "delivery_name": ""}, {**valid, "contact_person": "人" * 51},
                        {**valid, "contact_phone": "1" * 21}, {**valid, "contact_phone": 13800000000}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.prefix, json=payload).status_code, 422)
        data = self.create(contact_person="人" * 50, contact_phone="1" * 20)
        for payload in ({"contact_person": "人" * 51}, {"contact_phone": "1" * 21}):
            self.assertEqual(self.client.put(self.prefix + "/" + data["id"], json=payload).status_code, 422)

    def test_openapi_contacts_optional_and_authentication_still_required(self):
        schemas = self.client.get("/openapi.json").json()["components"]["schemas"]
        for name in ("DeliveryUnitCreate", "DeliveryUnitUpdate"):
            self.assertNotIn("contact_person", schemas[name].get("required", []))
            self.assertNotIn("contact_phone", schemas[name].get("required", []))
        del self.app.dependency_overrides[get_current_active_user]
        for method, path, payload in (("POST", "", {"delivery_name": "测试", "settlement_method": 1}),
                                      ("PUT", "/1", {"contact_phone": None}),
                                      ("GET", "", None), ("GET", "/1", None)):
            self.assertIn(self.client.request(method, self.prefix + path, json=payload).status_code, (401, 403))


if __name__ == "__main__":
    unittest.main()
