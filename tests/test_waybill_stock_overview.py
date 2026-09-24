import unittest
from datetime import date, datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.waybill_stocks import get_waybill_stock_overview
from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem


class WaybillStockOverviewTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        WaybillStock.__table__.create(self.engine)
        WaybillStockBatch.__table__.create(self.engine)
        WaybillStockItem.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.db.add_all([
            WaybillStock(
                id=10,
                airline_name="china_southern_air",
                total_authorized_count=100,
            ),
            WaybillStock(
                id=20,
                airline_name="shenzhen_air",
                total_authorized_count=50,
            ),
        ])
        self.db.add_all([
            WaybillStockBatch(
                id=100,
                stock_id=10,
                claim_date=date(2026, 9, 20),
                first_number="10000000",
                last_number="10000000",
                claim_quantity=1,
                number_prefix="784-",
                created_at=datetime(2026, 9, 20, 9, 0),
            ),
            WaybillStockBatch(
                id=200,
                stock_id=10,
                claim_date=date(2026, 9, 10),
                first_number="20000000",
                last_number="20000000",
                claim_quantity=1,
                number_prefix="784-",
                created_at=datetime(2026, 9, 24, 9, 0),
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_returns_latest_business_claim_date_and_null_without_batches(self):
        response = await get_waybill_stock_overview(
            airline_name=None,
            current_user=None,
            db=self.db,
        )

        overview_by_airline = {
            item["airline_name"]: item
            for item in response.data
        }

        self.assertEqual(
            overview_by_airline["china_southern_air"]["last_claim_date"],
            "2026-09-20",
        )
        self.assertIsNone(
            overview_by_airline["shenzhen_air"]["last_claim_date"]
        )
        self.assertEqual(
            overview_by_airline["china_southern_air"]["claimed_count"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
