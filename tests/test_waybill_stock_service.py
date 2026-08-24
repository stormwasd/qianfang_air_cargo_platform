import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.waybill_stock import WaybillStockItem
from app.services.waybill_stock_service import (
    WaybillStockConsistencyError,
    confirm_stock_item_used,
)


class ConfirmStockItemUsedTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        WaybillStockItem.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.db.add(
            WaybillStockItem(
                id=1,
                batch_id=1,
                claim_date=date(2026, 8, 24),
                number_prefix="784-",
                number_suffix="50222896",
                full_number="784-50222896",
                usage_status="0",
                is_abnormal="1",
                is_invalid="0",
                usage_date=None,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_confirms_successful_number_as_used(self):
        item = confirm_stock_item_used(
            self.db,
            1,
            expected_full_number="784-50222896",
        )
        self.db.commit()
        self.db.refresh(item)

        self.assertEqual(item.usage_status, "1")
        self.assertIsNotNone(item.usage_date)

    def test_confirmation_is_idempotent(self):
        confirm_stock_item_used(
            self.db,
            1,
            expected_full_number="784-50222896",
        )
        self.db.commit()
        item = confirm_stock_item_used(
            self.db,
            1,
            expected_full_number="784-50222896",
        )

        self.assertEqual(item.usage_status, "1")

    def test_rejects_mismatched_business_number(self):
        with self.assertRaisesRegex(
            WaybillStockConsistencyError,
            "单号库记录与业务单号不一致",
        ):
            confirm_stock_item_used(
                self.db,
                1,
                expected_full_number="784-00000000",
            )

        item = self.db.query(WaybillStockItem).filter_by(id=1).one()
        self.assertEqual(item.usage_status, "0")

    def test_rejects_missing_stock_item(self):
        with self.assertRaisesRegex(WaybillStockConsistencyError, "单号库记录不存在"):
            confirm_stock_item_used(self.db, 999)


if __name__ == "__main__":
    unittest.main()
