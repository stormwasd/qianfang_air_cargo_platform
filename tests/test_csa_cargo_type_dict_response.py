"""验证已有同步字典直接返回名称/代码对，并兼容通用字典接口。"""
import unittest
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.config import router
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.services.csa_cargo_type_sync import replace_cargo_type_dict_options


class CargoTypeDictionaryResponseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (DictType, DictOption):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add_all([
            DictType(id=1, name="货物类型", type="nanfang_air_cargo_type", status=1),
            DictType(id=2, name="深航货物代码", type="shenzhen_air_cargo_code", status=1),
        ])
        # These records predate the new response fields. No manual option create.
        self.db.add_all([
            DictOption(id=11, dict_type_id=1, label="普通货物", value="3006", status=1),
            DictOption(id=12, dict_type_id=1, label="锂电类货物", value="3006", status=1),
            DictOption(id=13, dict_type_id=1, label="危险品", value="3002", status=0),
            DictOption(id=21, dict_type_id=2, label="配件", value="044", status=1),
        ])
        self.db.commit()
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/config")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=1)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test/api/v1/config/")
        self.addAsyncCleanup(self.client.aclose)

    def assert_cargo_pair(self, item):
        self.assertEqual(item["cargo_type"], item["label"])
        self.assertEqual(item["cargo_type_code"], item["value"])
        self.assertIsInstance(item["cargo_type"], str)
        self.assertIsInstance(item["cargo_type_code"], str)

    async def test_existing_list_and_details_expose_distinct_names_without_db_writes(self):
        response = await self.client.get("dict-options", params={"dict_type": "nanfang_air_cargo_type", "status": 1})
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["total"], 2)
        self.assertEqual({(item["cargo_type"], item["cargo_type_code"]) for item in data["items"]},
                         {("普通货物", "3006"), ("锂电类货物", "3006")})
        for item in data["items"]:
            self.assert_cargo_pair(item)
            detail = await self.client.get("dict-options/" + item["id"])
            self.assertEqual(detail.json()["data"], item)
        self.assertEqual(self.db.query(DictOption).count(), 4)
        self.assertEqual(self.db.get(DictOption, 11).value, "3006")

    async def test_sync_replacement_needs_no_manual_creation_and_new_ids_do_not_matter(self):
        replace_cargo_type_dict_options(self.db, [
            {"label": "贵重物品", "value": "3001"},
            {"label": "活体动物", "value": "3001"},
        ])
        self.db.commit()
        response = await self.client.get("dict-options", params={"dict_type": "nanfang_air_cargo_type"})
        items = response.json()["data"]["items"]
        self.assertEqual([(item["cargo_type"], item["cargo_type_code"]) for item in items],
                         [("贵重物品", "3001"), ("活体动物", "3001")])
        for item in items:
            self.assert_cargo_pair(item)
            self.assertNotIn(item["id"], {"11", "12", "13"})

    async def test_filters_pagination_and_other_dictionary_contract_remain_compatible(self):
        response = await self.client.get("dict-options", params={"dict_type": "nanfang_air_cargo_type", "page": 1, "pageSize": 1, "order": "asc"})
        data = response.json()["data"]
        self.assertEqual(data["total"], 3)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["cargo_type_code"], "3002")
        mixed = (await self.client.get("dict-options")).json()["data"]["items"]
        other = next(item for item in mixed if item["id"] == "21")
        self.assertEqual(set(other), {"id", "dict_type_id", "dict_type", "label", "value", "status", "color_type", "created_at", "updated_at"})
        self.assertEqual((await self.client.get("dict-options/21")).json()["data"], other)
        for item in mixed:
            if item["dict_type"] == "nanfang_air_cargo_type":
                self.assert_cargo_pair(item)

    async def test_create_update_and_type_change_keep_response_fields_consistent(self):
        response = await self.client.post("dict-options", json={"dict_type": "nanfang_air_cargo_type", "label": "急件", "value": "3001"})
        self.assertEqual(response.status_code, 200)
        created = response.json()["data"]
        self.assert_cargo_pair(created)
        path = "dict-options/" + created["id"]
        response = await self.client.put(path, json={"label": "新货物类型", "value": "3011"})
        self.assert_cargo_pair(response.json()["data"])
        self.assertEqual(response.json()["data"]["cargo_type_code"], "3011")
        response = await self.client.put(path, json={"dict_type": "shenzhen_air_cargo_code"})
        self.assertNotIn("cargo_type", response.json()["data"])
        response = await self.client.put(path, json={"dict_type": "nanfang_air_cargo_type"})
        self.assert_cargo_pair(response.json()["data"])

    async def test_code_lookup_remains_ambiguous_for_shared_codes(self):
        response = await self.client.get("dict-options/value-by-key", params={"dict_type": "nanfang_air_cargo_type", "key": "3006"})
        self.assertEqual(response.status_code, 409)
        response = await self.client.get("dict-options/value-by-key", params={"dict_type": "shenzhen_air_cargo_code", "key": "044"})
        self.assertEqual(response.json()["data"]["value"], "配件")


if __name__ == "__main__":
    unittest.main()
