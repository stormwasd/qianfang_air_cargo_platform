import unittest
from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.services.waybill_stock_service import (
    WaybillStockConsistencyError,
    confirm_stock_item_used,
    reserve_available_stock_item,
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


class ReserveAvailableStockItemTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        WaybillStock.__table__.create(self.engine)
        WaybillStockBatch.__table__.create(self.engine)
        WaybillStockItem.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.db.add(WaybillStock(id=10, airline_name="china_southern_air"))
        self.db.add_all([
            WaybillStockBatch(
                id=100,
                stock_id=10,
                claim_date=date(2026, 9, 1),
                first_number="10000001",
                last_number="10000002",
                claim_quantity=2,
                number_prefix="784-",
            ),
            WaybillStockBatch(
                id=200,
                stock_id=10,
                claim_date=date(2026, 9, 15),
                first_number="20000001",
                last_number="20000003",
                claim_quantity=3,
                number_prefix="784-",
            ),
        ])
        self.db.add_all([
            self._item(1, 100, "10000001"),
            self._item(2, 100, "10000002"),
            self._item(3, 200, "20000001", usage_status="1"),
            self._item(4, 200, "20000002", is_abnormal="0"),
            self._item(5, 200, "20000003"),
        ])
        self.db.commit()

    @staticmethod
    def _item(item_id, batch_id, suffix, **overrides):
        values = {
            "id": item_id,
            "batch_id": batch_id,
            "claim_date": date(2026, 9, 15),
            "number_prefix": "784-",
            "number_suffix": suffix,
            "full_number": f"784-{suffix}",
            "usage_status": "0",
            "is_abnormal": "1",
            "is_invalid": "0",
        }
        values.update(overrides)
        return WaybillStockItem(**values)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_reserves_available_item_from_latest_batch(self):
        item = reserve_available_stock_item(self.db, "china_southern_air")
        self.db.commit()

        self.assertEqual(item.id, 5)
        self.assertEqual(item.usage_status, "1")
        self.assertIsNotNone(item.usage_date)

    def test_falls_back_to_older_batch(self):
        latest = self.db.query(WaybillStockItem).filter_by(id=5).one()
        latest.is_invalid = "1"
        self.db.commit()

        item = reserve_available_stock_item(self.db, "china_southern_air")

        self.assertEqual(item.id, 1)

    def test_returns_none_only_when_no_eligible_item_exists(self):
        self.db.query(WaybillStockItem).update({WaybillStockItem.usage_status: "1"})
        self.db.commit()

        item = reserve_available_stock_item(self.db, "china_southern_air")

        self.assertIsNone(item)


if __name__ == "__main__":
    unittest.main()
