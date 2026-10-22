import json
import unittest
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.security import create_access_token
from app.database import get_db
from app.main import create_application
from app.models.department import Department
from app.models.user import User
from app.models.user_department import user_department


class SalespersonOptionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Department.__table__.create(self.engine)
        User.__table__.create(self.engine)
        user_department.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.users = []
        names = ("张三", "小张", "提成%账号", "用户_甲", "路径/账号", "路径\\账号")
        percentages = (Decimal("12.50"), None, Decimal("0"), Decimal("100"), None, None)
        for index, (name, percentage) in enumerate(zip(names, percentages), start=1):
            self.users.append(User(
                id=260819415803760640 + index,
                phone=f"138000000{index:02d}",
                password_hash="hashed",
                name=name,
                commission_percentage=percentage,
                permissions='["expense_registration"]',
                is_active=index != 2,
                token_version=0,
                created_at=datetime(2026, 10, 9) + timedelta(minutes=index),
                updated_at=datetime(2026, 10, 9),
            ))
        self.db.add_all(self.users)
        self.db.commit()
        self.caller = self.users[0]
        self.app = create_application()

        async def test_db():
            return self.db

        # Keep the real JWT, active-user and permission checks in the HTTP path.
        self.app.dependency_overrides[get_db] = test_db

    def client(self):
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test"
        )

    def headers(self):
        token = create_access_token({
            "sub": str(self.caller.id),
            "phone": self.caller.phone,
            "token_version": self.caller.token_version,
        })
        return {"Authorization": f"Bearer {token}"}

    async def test_returns_only_option_fields_and_preserves_candidate_range(self):
        async with self.client() as client:
            response = await client.get("/api/v1/users/salespersons", headers=self.headers())
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["code"], 0)
        self.assertEqual(body["data"]["total"], 6)
        items = body["data"]["items"]
        self.assertEqual([item["id"] for item in items], [str(u.id) for u in reversed(self.users)])
        for item in items:
            self.assertEqual(set(item), {"id", "name", "commission_percentage"})
            self.assertIsInstance(item["id"], str)
        by_name = {item["name"]: item for item in items}
        self.assertEqual(by_name["张三"]["commission_percentage"], 12.5)
        self.assertIsNone(by_name["小张"]["commission_percentage"])
        self.assertEqual(by_name["提成%账号"]["commission_percentage"], 0)
        self.assertEqual(by_name["用户_甲"]["commission_percentage"], 100)

    async def test_name_search_preserves_literal_matching_and_blank_behavior(self):
        cases = (
            (None, 6, None), ("", 6, None), (" \t ", 6, None),
            (" 张 \t", 2, ["小张", "张三"]),
            ("%", 1, ["提成%账号"]), ("_", 1, ["用户_甲"]),
            ("/", 1, ["路径/账号"]), ("\\", 1, ["路径\\账号"]),
            ("不存在", 0, []), ("13800000001", 0, []), ("' OR 1=1 --", 0, []),
        )
        async with self.client() as client:
            for name, total, expected_names in cases:
                with self.subTest(name=name):
                    params = {} if name is None else {"name": name}
                    response = await client.get(
                        "/api/v1/users/salespersons", params=params, headers=self.headers()
                    )
                    self.assertEqual(response.status_code, 200)
                    data = response.json()["data"]
                    self.assertEqual(data["total"], total)
                    if expected_names is not None:
                        self.assertEqual([item["name"] for item in data["items"]], expected_names)

    async def test_expense_admin_and_legacy_permissions_are_allowed(self):
        async with self.client() as client:
            for permissions in (
                ["expense_registration"], ["admin"], ["cost_service"],
                ["费用登记台"], ["管理员"],
                ["customer_service", "organizational_management", "system", "expense_registration"],
            ):
                with self.subTest(permissions=permissions):
                    self.caller.permissions = json.dumps(permissions, ensure_ascii=False)
                    self.db.commit()
                    response = await client.get("/api/v1/users/salespersons", headers=self.headers())
                    self.assertEqual(response.status_code, 200)

    async def test_other_permissions_do_not_grant_access(self):
        async with self.client() as client:
            for permissions in ([], ["customer_service"], ["organizational_management", "system"]):
                with self.subTest(permissions=permissions):
                    self.caller.permissions = json.dumps(permissions)
                    self.db.commit()
                    response = await client.get("/api/v1/users/salespersons", headers=self.headers())
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(response.json(), {
                        "code": 403,
                        "data": None,
                        "msg": "需要「expense_registration」权限或管理员权限",
                    })

    async def test_authentication_disabled_user_and_stale_token_are_enforced(self):
        path = "/api/v1/users/salespersons"
        async with self.client() as client:
            self.assertEqual((await client.get(path)).status_code, 403)
            response = await client.get(path, headers={"Authorization": "Bearer invalid"})
            self.assertEqual(response.status_code, 401)
            headers = self.headers()
            self.caller.is_active = False
            self.db.commit()
            self.assertEqual((await client.get(path, headers=headers)).status_code, 401)
            self.caller.is_active = True
            self.caller.token_version += 1
            self.db.commit()
            self.assertEqual((await client.get(path, headers=headers)).status_code, 401)

    async def test_existing_account_list_and_detail_keep_admin_requirement(self):
        async with self.client() as client:
            for path in ("/api/v1/users", f"/api/v1/users/{self.caller.id}"):
                self.assertEqual((await client.get(path, headers=self.headers())).status_code, 403)
            self.caller.permissions = '["admin"]'
            self.db.commit()
            response = await client.get("/api/v1/users", headers=self.headers())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["total"], 6)
            self.assertIn("phone", response.json()["data"]["items"][0])
            response = await client.get(f"/api/v1/users/{self.caller.id}", headers=self.headers())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["phone"], self.caller.phone)

    def test_openapi_exposes_search_auth_and_restricted_response_schema(self):
        schema = self.app.openapi()
        operation = schema["paths"]["/api/v1/users/salespersons"]["get"]
        self.assertEqual(operation["security"], [{"HTTPBearer": []}])
        parameter = next(item for item in operation["parameters"] if item["name"] == "name")
        self.assertFalse(parameter["required"])
        response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
        self.assertIn("SalespersonListResponse", response_schema["$ref"])
        properties = schema["components"]["schemas"]["SalespersonOption"]["properties"]
        self.assertEqual(set(properties), {"id", "name", "commission_percentage"})
        self.assertIn({"type": "null"}, properties["commission_percentage"]["anyOf"])
        self.assertIn({"type": "number"}, properties["commission_percentage"]["anyOf"])


if __name__ == "__main__":
    unittest.main()
