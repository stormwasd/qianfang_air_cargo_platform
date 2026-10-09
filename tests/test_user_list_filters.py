import unittest
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.users import get_users, router
from app.database import get_db
from app.models.department import Department
from app.models.user import User
from app.models.user_department import user_department


class UserListFilterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Department.__table__.create(self.engine)
        User.__table__.create(self.engine)
        user_department.create(self.engine)
        self.db = Session(self.engine)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)

        departments = [Department(id=1, name="张三部门"), Department(id=2, name="财务部")]
        names = ("张三", "小张", "李四", "提成%账号", "用户_甲", "路径/账号", "路径\\账号")
        self.users = []
        for index, name in enumerate(names, start=1):
            self.users.append(User(
                id=index,
                phone=f"138000000{index:02d}",
                password_hash="hashed",
                name=name,
                commission_percentage=Decimal("12.50") if index == 1 else None,
                permissions='["admin"]',
                is_active=index != 2,
                token_version=0,
                created_at=datetime(2026, 10, 9) + timedelta(minutes=index),
                updated_at=datetime(2026, 10, 9),
            ))
        self.users[0].departments = departments
        self.users[2].departments = [departments[0]]
        self.db.add_all(self.users)
        self.db.commit()

    async def query(self, name=None):
        response = await get_users(current_user=None, db=self.db, name=name)
        return response.data

    async def test_substring_matches_all_users_and_preserves_fields_and_order(self):
        data = await self.query("张")
        self.assertEqual(data["total"], 2)
        self.assertEqual([item["id"] for item in data["items"]], ["2", "1"])
        self.assertFalse(data["items"][0]["is_active"])
        self.assertIsNone(data["items"][0]["commission_percentage"])
        user = data["items"][1]
        self.assertEqual(user["commission_percentage"], 12.5)
        self.assertEqual(user["permissions"], ["admin"])
        self.assertEqual(set(user["department_ids"]), {"1", "2"})
        self.assertEqual(len(user["departments"]), 2)
        self.assertIn("created_at", user)
        self.assertIn("updated_at", user)

    async def test_empty_and_blank_name_keep_full_list(self):
        for name in (None, "", " \t "):
            with self.subTest(name=name):
                data = await self.query(name)
                self.assertEqual(data["total"], 7)
                self.assertEqual([item["id"] for item in data["items"]], list("7654321"))
        self.assertEqual((await self.query("  张 \t"))["total"], 2)

    async def test_wildcards_escape_character_and_backslash_are_literal(self):
        for name, expected_id in (("%", "4"), ("_", "5"), ("/", "6"), ("\\", "7")):
            with self.subTest(name=name):
                data = await self.query(name)
                self.assertEqual(data["total"], 1)
                self.assertEqual(data["items"][0]["id"], expected_id)

    async def test_no_match_and_other_fields_do_not_match(self):
        for name in ("不存在", "13800000001", "财务部", "' OR 1=1 --"):
            with self.subTest(name=name):
                self.assertEqual(await self.query(name), {"total": 0, "items": []})

    async def test_http_query_parameter_and_openapi(self):
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/users")

        async def test_db():
            return self.db

        async def test_admin():
            return self.users[0]

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[require_admin] = test_admin
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/v1/users", params={"name": " 张 "})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["data"]["total"], 2)
            self.assertEqual((await client.get("/api/v1/users")).json()["data"]["total"], 7)
            response = await client.get("/api/v1/users", params={"name": "%"})
            self.assertEqual(response.json()["data"]["total"], 1)

        parameters = app.openapi()["paths"]["/api/v1/users"]["get"]["parameters"]
        parameter = next(item for item in parameters if item["name"] == "name")
        self.assertEqual(parameter["in"], "query")
        self.assertFalse(parameter["required"])


if __name__ == "__main__":
    unittest.main()
