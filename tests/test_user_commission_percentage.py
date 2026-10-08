import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from app.api.users import create_user, get_user, get_users, update_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate


class UserQuery:
    def __init__(self, records):
        self.records = records

    def filter(self, *conditions):
        return self

    def options(self, *options):
        return self

    def order_by(self, *columns):
        return self

    def first(self):
        return self.records[0] if self.records else None

    def all(self):
        return self.records


class UserSession:
    def __init__(self, records=None):
        self.records = list(records or [])
        self.added = None

    def query(self, model):
        return UserQuery(self.records)

    def add(self, record):
        self.added = record

    def commit(self):
        pass

    def refresh(self, record):
        if record.id is None:
            record.id = 1
        now = datetime(2026, 10, 8, 12, 0, 0)
        if record.created_at is None:
            record.created_at = now
        record.updated_at = now


def make_user(commission_percentage=None):
    return User(
        id=1,
        phone="13800138000",
        password_hash="hashed",
        name="张三",
        commission_percentage=commission_percentage,
        permissions='["admin"]',
        is_active=True,
        token_version=0,
        created_at=datetime(2026, 10, 8, 12, 0, 0),
        updated_at=datetime(2026, 10, 8, 12, 0, 0),
    )


class UserCommissionPercentageTests(unittest.IsolatedAsyncioTestCase):
    def create_payload(self, percentage=Decimal("12.50")):
        return UserCreate(
            phone="13800138000",
            password="123456",
            name="张三",
            commission_percentage=percentage,
            department_ids=[],
            permissions=["admin"],
        )

    def test_create_requires_percentage_and_validates_range_and_scale(self):
        base = {
            "phone": "13800138000",
            "password": "123456",
            "name": "张三",
            "permissions": ["admin"],
        }
        for percentage in (Decimal("-0.01"), Decimal("100.01"), Decimal("1.234")):
            with self.subTest(percentage=percentage), self.assertRaises(ValidationError):
                UserCreate.model_validate(
                    {**base, "commission_percentage": percentage}
                )
        with self.assertRaises(ValidationError):
            UserCreate.model_validate(base)

        self.assertEqual(
            UserCreate.model_validate(
                {**base, "commission_percentage": 0}
            ).commission_percentage,
            0,
        )
        self.assertEqual(
            UserCreate.model_validate(
                {**base, "commission_percentage": 100}
            ).commission_percentage,
            100,
        )

    async def test_create_persists_and_returns_percentage(self):
        db = UserSession()

        response = await create_user(self.create_payload(), current_user=None, db=db)

        self.assertEqual(db.added.commission_percentage, Decimal("12.50"))
        self.assertEqual(response.data["commission_percentage"], 12.5)

    async def test_list_and_detail_return_percentage_including_historical_null(self):
        percentage_user = make_user(Decimal("8.25"))
        historical_user = make_user(None)
        historical_user.id = 2
        db = UserSession([percentage_user, historical_user])

        list_response = await get_users(current_user=None, db=db)
        self.assertEqual(
            [item["commission_percentage"] for item in list_response.data["items"]],
            [8.25, None],
        )

        detail_response = await get_user("1", current_user=None, db=UserSession([percentage_user]))
        self.assertEqual(detail_response.data["commission_percentage"], 8.25)

    async def test_update_accepts_zero_and_empty_value_preserves_existing_value(self):
        user = make_user(Decimal("8.25"))

        response = await update_user(
            "1",
            UserUpdate(commission_percentage=0),
            current_user=None,
            db=UserSession([user]),
        )
        self.assertEqual(user.commission_percentage, 0)
        self.assertEqual(response.data["commission_percentage"], 0.0)

        await update_user(
            "1", UserUpdate(name="李四"), current_user=None, db=UserSession([user])
        )
        self.assertEqual(user.commission_percentage, 0)

        await update_user(
            "1",
            UserUpdate(commission_percentage=None),
            current_user=None,
            db=UserSession([user]),
        )
        self.assertEqual(user.commission_percentage, 0)

    def test_model_and_migration_use_nullable_decimal_percentage(self):
        column = User.__table__.columns["commission_percentage"]
        self.assertTrue(column.nullable)
        self.assertEqual(column.type.precision, 5)
        self.assertEqual(column.type.scale, 2)

        migration = (
            Path(__file__).parents[1]
            / "sql"
            / "migration_add_user_commission_percentage.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("ALTER TABLE `users`", migration)
        self.assertIn(
            "`commission_percentage` decimal(5,2) DEFAULT NULL COMMENT '提成百分比'",
            migration,
        )


if __name__ == "__main__":
    unittest.main()
