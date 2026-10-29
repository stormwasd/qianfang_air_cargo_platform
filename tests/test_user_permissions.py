"""用户权限编辑回归，覆盖真实认证依赖、持久化和 JWT 版本失效。"""
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.users import router
from app.config import settings
from app.core.exceptions import BaseAPIException
from app.core.permissions import normalize_user_permissions, validate_permissions
from app.core.security import create_access_token
from app.database import get_db
from app.models.department import Department
from app.models.user import User
from app.models.user_department import user_department
from app.utils.helpers import parse_json_permissions
from app.utils.menu_mapping import generate_menus_by_permissions


SCREENSHOT_CODES = ["waybill", "bill", "customer", "agent", "finance", "smart_tracking", "account"]
REPORTED_CODES = ["waybill", "bill", "account", "robot", "customer", "system", "agency", "finance", "smart_tracking"]


class UserPermissionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for table in (User.__table__, Department.__table__, user_department):
            table.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add(Department(id=1, name="业务前台"))
        self.db.add_all([
            User(id=1, phone="13800000001", name="管理员", password_hash="unused", permissions='["admin"]', token_version=0, is_active=True),
            User(id=2, phone="13800000002", name="待修改用户", password_hash="unused", permissions='["waybill"]', token_version=0, is_active=True),
        ])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(router, prefix="/api/v1/users")
        self.app.dependency_overrides[get_db] = lambda: self.db

        @self.app.exception_handler(BaseAPIException)
        async def handle_error(request, exc):
            return JSONResponse(status_code=exc.status_code, content={"code": exc.status_code, "data": exc.data, "msg": exc.detail})

        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)
        self.admin_headers = self.headers(1)

    def headers(self, user_id):
        user = self.db.get(User, user_id)
        token = create_access_token({"sub": str(user.id), "phone": user.phone, "token_version": user.token_version})
        return {"Authorization": "Bearer " + token}

    async def test_reported_agency_payload_saves_canonical_agent_and_menus(self):
        expected = ["agent" if code == "agency" else code for code in REPORTED_CODES]
        for input_values in (REPORTED_CODES, expected):
            with self.subTest(values=input_values):
                response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={"permissions": input_values})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["data"]["permissions"], expected)
                self.assertEqual(json.loads(self.db.get(User, 2).permissions), expected)
        # Changing representation alone does not invalidate the login again.
        self.assertEqual(self.db.get(User, 2).token_version, 1)
        menus = generate_menus_by_permissions(expected)
        self.assertEqual({item["name"] for item in menus}, {settings.PERMISSIONS[code] for code in expected})

    async def test_create_uses_same_normalization_and_list_detail_return_codes(self):
        with patch("app.api.users.get_password_hash", return_value="synthetic-hash"):
            response = await self.client.post("/api/v1/users", headers=self.admin_headers, json={
                "phone": "13800000003", "password": "synthetic-password", "name": "新增用户",
                "department_ids": ["1"], "permissions": [" agency ", "agent", "smart_tracking", " bill "],
            })
        self.assertEqual(response.status_code, 200, response.text)
        user_id = response.json()["data"]["id"]
        expected = ["agent", "smart_tracking", "bill"]
        self.assertEqual(response.json()["data"]["permissions"], expected)
        for endpoint in (user_id, ""):
            response = await self.client.get(f"/api/v1/users/{endpoint}" if endpoint else "/api/v1/users", headers=self.admin_headers)
            data = response.json()["data"]
            if endpoint == "":
                data = next(item for item in data["items"] if item["id"] == user_id)
            self.assertEqual(data["permissions"], expected)
        self.assertEqual(json.loads(self.db.get(User, int(user_id)).permissions), expected)

    async def test_unknown_permissions_report_value_and_do_not_partially_modify_user(self):
        for value in ("smartTracking", "智能跟单", "账号管理/account", "agencies", "", " "):
            with self.subTest(value=value):
                response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={
                    "name": "不应保存", "department_ids": ["1"], "permissions": ["waybill", "agency", value],
                })
                self.assertEqual(response.status_code, 400)
                self.assertIn("权限列表包含无效的权限", response.json()["msg"])
                self.assertIn(json.dumps([value], ensure_ascii=False), response.json()["msg"])
                # No pending ORM mutations can be accidentally committed later.
                self.assertFalse(self.db.dirty)
                self.db.commit()
                user = self.db.get(User, 2)
                self.assertEqual((user.name, user.permissions, user.token_version), ("待修改用户", '["waybill"]', 0))
                self.assertEqual(user.departments, [])

    async def test_invalid_create_never_creates_partial_account(self):
        response = await self.client.post("/api/v1/users", headers=self.admin_headers, json={
            "phone": "13800000003", "password": "synthetic-password", "name": "新增用户",
            "permissions": ["agency", "unsupported"],
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.db.query(User).count(), 2)

    async def test_empty_omitted_and_null_have_distinct_semantics(self):
        for payload in ({"name": "仅改名称"}, {"permissions": None}):
            response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json=payload)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["permissions"], ["waybill"])
            self.assertEqual(self.db.get(User, 2).token_version, 0)
        response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={"permissions": []})
        self.assertEqual(response.json()["data"]["permissions"], [])
        self.assertEqual(self.db.get(User, 2).token_version, 1)

    async def test_reorder_duplicates_and_existing_chinese_storage_do_not_force_logout(self):
        self.db.get(User, 2).permissions = '["代理管理", "单号库", "单号库"]'
        self.db.commit()
        response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={"permissions": [" bill ", "agency", "agent"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.get(User, 2).token_version, 0)
        self.assertEqual(json.loads(self.db.get(User, 2).permissions), ["bill", "agent"])

    async def test_real_permission_change_invalidates_old_jwt_and_admin_guard_is_preserved(self):
        self.db.get(User, 2).permissions = '["admin"]'
        self.db.commit()
        old_headers = self.headers(2)
        self.assertEqual((await self.client.get("/api/v1/users/2", headers=old_headers)).status_code, 200)
        response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={"permissions": ["customer"]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.db.get(User, 2).token_version, 1)
        self.assertEqual((await self.client.get("/api/v1/users/2", headers=old_headers)).status_code, 401)
        # New valid token still cannot use the admin-only editing endpoint.
        response = await self.client.put("/api/v1/users/1", headers=self.headers(2), json={"permissions": ["admin", "agency"]})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.db.get(User, 1).permissions, '["admin"]')
        response = await self.client.put("/api/v1/users/2", json={"permissions": ["admin", "agency"]})
        self.assertIn(response.status_code, (401, 403))

    async def test_object_options_and_scalar_input_are_rejected_by_schema(self):
        for value in ([{"label": "主单管理", "value": "waybill"}], "waybill", [123]):
            response = await self.client.put("/api/v1/users/2", headers=self.admin_headers, json={"permissions": value})
            self.assertEqual(response.status_code, 422)

    def test_all_existing_codes_and_only_explicit_legacy_alias_are_supported(self):
        codes = list(settings.PERMISSION_CODES)
        self.assertEqual(normalize_user_permissions(codes), codes)
        self.assertEqual(normalize_user_permissions(SCREENSHOT_CODES), SCREENSHOT_CODES)
        self.assertEqual(normalize_user_permissions(["agency", "agent", " agency "]), ["agent"])
        for invalid in ("agencies", "Agency", "代理管理", "administrator"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                normalize_user_permissions([invalid])
        self.assertTrue(validate_permissions(codes))
        self.assertFalse(validate_permissions(REPORTED_CODES))
        self.assertFalse(validate_permissions(["主单管理"]))
        self.assertEqual(parse_json_permissions('["admin"]'), ["admin"])


if __name__ == "__main__":
    unittest.main()
