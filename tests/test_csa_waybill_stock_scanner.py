import asyncio
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.booking import Booking
from app.models.waybill import Waybill
from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.services.china_southern_air_service_client import ChinaSouthernAirService
from app.services.csa_waybill_stock_scanner import (
    get_latest_csa_batch_item_ids,
    orders_indicate_waybill_used,
    synchronize_stock_item_status,
)
from app.utils.helpers import get_china_now


class WaybillOrderResponseTests(unittest.TestCase):
    def test_availability_rule(self):
        self.assertFalse(orders_indicate_waybill_used([]))
        self.assertFalse(
            orders_indicate_waybill_used(
                [{"statusCN": "已取消"}, {"statusCN": " 已取消 "}]
            )
        )
        self.assertTrue(
            orders_indicate_waybill_used(
                [{"statusCN": "已取消"}, {"statusCN": "待交货"}]
            )
        )
        self.assertTrue(orders_indicate_waybill_used([{}]))

    def test_query_paginates_and_uses_suffix(self):
        captured_starts = []

        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        class FakeAsyncClient:
            def __init__(self, **_kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_args):
                return False

            async def post(self, _url, **kwargs):
                start = kwargs["params"]["start"]
                captured_starts.append(start)
                count = 100 if start == 0 else 1
                return FakeResponse(
                    {
                        "code": "0000",
                        "result": {
                            "list": [{"statusCN": "已取消"}] * count,
                            "total": 101,
                        },
                    }
                )

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            FakeAsyncClient,
        ):
            orders = asyncio.run(
                ChinaSouthernAirService().query_waybill_orders(
                    token="token", awb_no="50222885"
                )
            )

        self.assertEqual(len(orders), 101)
        self.assertEqual(captured_starts, [0, 100])


class WaybillStockSynchronizationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        WaybillStock.__table__.create(self.engine)
        WaybillStockBatch.__table__.create(self.engine)
        WaybillStockItem.__table__.create(self.engine)
        Booking.__table__.create(self.engine)
        Waybill.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        stock = WaybillStock(id=1, airline_name="china_southern_air")
        old_batch = WaybillStockBatch(
            id=10,
            stock_id=1,
            claim_date=date(2026, 8, 20),
            first_number="1",
            last_number="1",
            claim_quantity=1,
            number_prefix="784-",
            created_at=datetime(2026, 8, 20, 10, 0, 0),
        )
        latest_batch = WaybillStockBatch(
            id=11,
            stock_id=1,
            claim_date=date(2026, 8, 21),
            first_number="2",
            last_number="3",
            claim_quantity=2,
            number_prefix="784-",
            created_at=datetime(2026, 8, 21, 10, 0, 0),
        )
        self.db.add_all([stock, old_batch, latest_batch])
        self.db.add_all(
            [
                WaybillStockItem(
                    id=101,
                    batch_id=10,
                    claim_date=old_batch.claim_date,
                    number_prefix="784-",
                    number_suffix="00000001",
                    full_number="784-00000001",
                ),
                WaybillStockItem(
                    id=102,
                    batch_id=11,
                    claim_date=latest_batch.claim_date,
                    number_prefix="784-",
                    number_suffix="00000002",
                    full_number="784-00000002",
                    usage_status="1",
                    usage_date=date(2026, 8, 21),
                    is_invalid="1",
                    invalid_reason="南航提示运单号已被使用",
                    updated_at=get_china_now() - timedelta(hours=1),
                ),
                WaybillStockItem(
                    id=103,
                    batch_id=11,
                    claim_date=latest_batch.claim_date,
                    number_prefix="784-",
                    number_suffix="00000003",
                    full_number="784-00000003",
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_only_selects_latest_batch(self):
        batch_id, item_ids = get_latest_csa_batch_item_ids(self.db)
        self.assertEqual(batch_id, 11)
        self.assertEqual(item_ids, [102, 103])

    def test_latest_batch_uses_import_time_before_claim_date(self):
        # 领单日期可以补录/回填，实际导入时间才代表扫描优先级。
        backfilled_batch = WaybillStockBatch(
            id=12,
            stock_id=1,
            claim_date=date(2026, 8, 27),
            first_number="4",
            last_number="4",
            claim_quantity=1,
            number_prefix="784-",
            created_at=datetime(2026, 8, 20, 9, 0, 0),
        )
        self.db.add(backfilled_batch)
        self.db.add(
            WaybillStockItem(
                id=104,
                batch_id=12,
                claim_date=backfilled_batch.claim_date,
                number_prefix="784-",
                number_suffix="00000004",
                full_number="784-00000004",
            )
        )
        self.db.commit()

        batch_id, item_ids = get_latest_csa_batch_item_ids(self.db)
        self.assertEqual(batch_id, 11)
        self.assertEqual(item_ids, [102, 103])

    def test_canceled_order_releases_and_clears_automatic_isolation(self):
        with patch(
            "app.services.csa_waybill_stock_scanner.settings."
            "CHINA_SOUTHERN_AIR_WAYBILL_STOCK_RELEASE_GRACE_SECONDS",
            0,
        ):
            result = synchronize_stock_item_status(
                self.db, 102, is_used_by_csa=False
            )
        self.db.commit()
        item = self.db.query(WaybillStockItem).filter_by(id=102).one()
        self.assertEqual(result, "marked_unused")
        self.assertEqual(item.usage_status, "0")
        self.assertIsNone(item.usage_date)
        self.assertEqual(item.is_invalid, "0")
        self.assertIsNone(item.invalid_reason)

    def test_any_active_order_marks_item_used(self):
        result = synchronize_stock_item_status(self.db, 103, is_used_by_csa=True)
        self.db.commit()
        item = self.db.query(WaybillStockItem).filter_by(id=103).one()
        self.assertEqual(result, "marked_used")
        self.assertEqual(item.usage_status, "1")
        self.assertIsNotNone(item.usage_date)

    def test_executing_booking_prevents_release(self):
        self.db.add(
            Booking(
                id=201,
                form_data="{}",
                booking_status="1",
                booking_time=get_china_now(),
                master_airwaybill_number="784-00000002",
            )
        )
        self.db.commit()
        with patch(
            "app.services.csa_waybill_stock_scanner.settings."
            "CHINA_SOUTHERN_AIR_WAYBILL_STOCK_RELEASE_GRACE_SECONDS",
            0,
        ):
            result = synchronize_stock_item_status(
                self.db, 102, is_used_by_csa=False
            )
        self.assertEqual(result, "protected")


if __name__ == "__main__":
    unittest.main()
