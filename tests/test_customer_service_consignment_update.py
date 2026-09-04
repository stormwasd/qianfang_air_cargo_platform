"""客服接单台委托信息修改行为测试。"""
import asyncio
from types import SimpleNamespace
import unittest

from app.api.customer_service import update_consignment
from app.schemas.customer_service import ConsignmentInfoUpdate


class _Query:
    def __init__(self, record):
        self.record = record

    def filter(self, *_args):
        return self

    def first(self):
        return self.record


class _Session:
    def __init__(self, consignment, cost_consignment):
        self._records = [consignment, cost_consignment]
        self.committed = False
        self.refreshed_record = None

    def query(self, *_args):
        return _Query(self._records.pop(0))

    def add(self, _record):
        raise AssertionError("费用登记台记录已存在，不应新增")

    def commit(self):
        self.committed = True

    def refresh(self, record):
        self.refreshed_record = record


class CustomerServiceConsignmentUpdateTests(unittest.TestCase):
    def _update(self, payload):
        consignment = SimpleNamespace(
            id=1,
            create_time=None,
            internal_doc_id="DOC-001",
            warehouse_entry_date=None,
            customer_name="客户A",
            origin_destination="SZX-TPE",
            customs_declaration=None,
            bill_of_lading=None,
            flight_date=None,
            flight_no=None,
            flight_doc_no=None,
            pieces=39,
            actual_weight=500.0,
            chargeable_weight=601.0,
            volume=3.61,
            first_leg_weight=450.0,
            agent="代理A",
            remark=None,
            creator_id=99,
            created_at=None,
            updated_at=None,
        )
        cost_consignment = SimpleNamespace()
        session = _Session(consignment, cost_consignment)

        asyncio.run(
            update_consignment(
                payload=payload,
                consignment_id="1",
                current_user=None,
                db=session,
            )
        )
        return consignment, cost_consignment, session

    def test_explicit_null_clears_numeric_fields_and_syncs_cost_record(self):
        consignment, cost_consignment, session = self._update(
            ConsignmentInfoUpdate(
                pieces=None,
                actual_weight=None,
                chargeable_weight=None,
                volume=None,
                first_leg_weight=None,
            )
        )

        for field_name in (
            "pieces",
            "actual_weight",
            "chargeable_weight",
            "volume",
            "first_leg_weight",
        ):
            self.assertIsNone(getattr(consignment, field_name))
            self.assertIsNone(getattr(cost_consignment, field_name))
        self.assertTrue(session.committed)
        self.assertIs(session.refreshed_record, consignment)

    def test_omitted_numeric_fields_keep_existing_values(self):
        consignment, cost_consignment, _session = self._update(
            ConsignmentInfoUpdate(customer_name="客户B")
        )

        self.assertEqual(consignment.pieces, 39)
        self.assertEqual(consignment.actual_weight, 500.0)
        self.assertEqual(consignment.chargeable_weight, 601.0)
        self.assertEqual(consignment.volume, 3.61)
        self.assertEqual(consignment.first_leg_weight, 450.0)
        self.assertEqual(cost_consignment.actual_weight, 500.0)

    def test_zero_remains_a_valid_numeric_value(self):
        consignment, cost_consignment, _session = self._update(
            ConsignmentInfoUpdate(actual_weight=0, chargeable_weight=0)
        )

        self.assertEqual(consignment.actual_weight, 0.0)
        self.assertEqual(consignment.chargeable_weight, 0.0)
        self.assertEqual(cost_consignment.actual_weight, 0.0)
        self.assertEqual(cost_consignment.chargeable_weight, 0.0)


if __name__ == "__main__":
    unittest.main()
