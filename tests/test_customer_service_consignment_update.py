"""客服接单台委托信息保存与暂存行为测试。"""
import asyncio
from datetime import date
from types import SimpleNamespace
import unittest

from app.api.customer_service import (
    create_consignment,
    update_consignment,
    update_consignment_draft,
)
from app.schemas.customer_service import ConsignmentInfoCreate, ConsignmentInfoUpdate
from app.models.consignment_operation_log import ConsignmentOperationLog


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
        if isinstance(_record, ConsignmentOperationLog):
            self.operation_log = _record
            return
        raise AssertionError("费用登记台记录已存在，不应新增")

    def commit(self):
        self.committed = True

    def refresh(self, record):
        self.refreshed_record = record


class _DraftSession:
    def __init__(self, consignment):
        self.consignment = consignment
        self.committed = False
        self.refreshed_record = None

    def query(self, *_args):
        return _Query(self.consignment)

    def add(self, record):
        if not isinstance(record, ConsignmentOperationLog):
            raise AssertionError("暂存不应创建另一台的单据")
        self.operation_log = record

    def commit(self):
        self.committed = True

    def refresh(self, record):
        self.refreshed_record = record


class _CreateSession:
    def __init__(self):
        self.added_records = []
        self.committed = False
        self.refreshed_record = None

    def add(self, record):
        self.added_records.append(record)

    def flush(self):
        # 模拟数据库在 flush 时生成客服单据 ID，费用单据应复用该 ID。
        self.added_records[0].id = 1

    def query(self, *_args):
        return _Query(None)

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
            status=1,
            creator_id=99,
            created_at=None,
            updated_at=None,
        )
        cost_consignment = SimpleNamespace(
            pay_intl_air_rate=6.8,
            pay_intl_air_outsource_unit="原外发单位",
        )
        session = _Session(consignment, cost_consignment)

        asyncio.run(
            update_consignment(
                payload=payload,
                consignment_id="1",
                current_user=SimpleNamespace(id=100, name="修改人员"),
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
        for field_name in (
            "pay_intl_air_pieces",
            "pay_intl_air_weight",
            "pay_intl_air_chargeable_weight",
            "pay_intl_air_volume",
        ):
            self.assertIsNone(getattr(cost_consignment, field_name))
        self.assertTrue(session.committed)
        self.assertIs(session.refreshed_record, consignment)
        self.assertEqual(consignment.status, 1)
        self.assertEqual(cost_consignment.status, 0)

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
        self.assertEqual(cost_consignment.status, 0)

    def test_zero_remains_a_valid_numeric_value(self):
        consignment, cost_consignment, _session = self._update(
            ConsignmentInfoUpdate(actual_weight=0, chargeable_weight=0)
        )

        self.assertEqual(consignment.actual_weight, 0.0)
        self.assertEqual(consignment.chargeable_weight, 0.0)
        self.assertEqual(cost_consignment.actual_weight, 0.0)
        self.assertEqual(cost_consignment.chargeable_weight, 0.0)
        self.assertEqual(cost_consignment.status, 0)

    def test_save_prefills_cost_international_air_fields(self):
        _consignment, cost_consignment, _session = self._update(
            ConsignmentInfoUpdate(
                pieces=12,
                actual_weight=123.45,
                flight_date="2026-09-08",
                chargeable_weight=130.5,
                flight_no="ZH9001",
                volume=1.234,
                flight_doc_no="479-12345678",
            )
        )

        self.assertEqual(cost_consignment.pay_intl_air_pieces, 12)
        self.assertEqual(cost_consignment.pay_intl_air_weight, 123.45)
        self.assertEqual(cost_consignment.pay_intl_air_flight_date, date(2026, 9, 8))
        self.assertEqual(cost_consignment.pay_intl_air_chargeable_weight, 130.5)
        self.assertEqual(cost_consignment.pay_intl_air_flight_no, "ZH9001")
        self.assertEqual(cost_consignment.pay_intl_air_volume, 1.234)
        self.assertEqual(cost_consignment.pay_intl_air_flight_doc_no, "479-12345678")
        self.assertEqual(cost_consignment.pay_intl_air_rate, 6.8)
        self.assertEqual(cost_consignment.pay_intl_air_outsource_unit, "原外发单位")
        self.assertEqual(cost_consignment.status, 0)

    def test_create_save_prefills_cost_international_air_fields(self):
        session = _CreateSession()

        asyncio.run(
            create_consignment(
                payload=ConsignmentInfoCreate(
                    pieces=8,
                    actual_weight=88.5,
                    flight_date="2026-09-09",
                    chargeable_weight=90.0,
                    flight_no="ZH9002",
                    volume=0.888,
                    flight_doc_no="479-87654321",
                ),
                current_user=SimpleNamespace(id=99, name="创建人员"),
                db=session,
            )
        )

        customer_consignment, cost_consignment, operation_log = session.added_records
        self.assertEqual(operation_log.operation_name, "货主委托信息保存")
        self.assertEqual(operation_log.consignment_id, customer_consignment.id)
        self.assertEqual(operation_log.operator_id, 99)
        self.assertEqual(customer_consignment.status, 1)
        self.assertEqual(cost_consignment.id, customer_consignment.id)
        self.assertEqual(cost_consignment.pay_intl_air_pieces, 8)
        self.assertEqual(cost_consignment.pay_intl_air_weight, 88.5)
        self.assertEqual(cost_consignment.pay_intl_air_flight_date, date(2026, 9, 9))
        self.assertEqual(cost_consignment.pay_intl_air_chargeable_weight, 90.0)
        self.assertEqual(cost_consignment.pay_intl_air_flight_no, "ZH9002")
        self.assertEqual(cost_consignment.pay_intl_air_volume, 0.888)
        self.assertEqual(cost_consignment.pay_intl_air_flight_doc_no, "479-87654321")
        self.assertEqual(cost_consignment.status, 0)
        self.assertTrue(session.committed)
        self.assertIs(session.refreshed_record, customer_consignment)

    def test_draft_update_keeps_cost_data_untouched_and_marks_unsubmitted(self):
        consignment = SimpleNamespace(
            id=1,
            status=1,
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
        session = _DraftSession(consignment)

        asyncio.run(
            update_consignment_draft(
                payload=ConsignmentInfoUpdate(customer_name="草稿客户"),
                consignment_id="1",
                current_user=SimpleNamespace(id=100, name="暂存人员"),
                db=session,
            )
        )

        self.assertEqual(consignment.customer_name, "草稿客户")
        self.assertEqual(consignment.status, 0)
        self.assertTrue(session.committed)
        self.assertIs(session.refreshed_record, consignment)


if __name__ == "__main__":
    unittest.main()
