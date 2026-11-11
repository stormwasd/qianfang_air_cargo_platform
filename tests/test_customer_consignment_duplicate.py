"""客服国际空运主单号30天查重、事务回滚和并发保存回归。"""
import asyncio
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, event
from sqlalchemy.dialects import mysql
from sqlalchemy.orm import Session

from app.api import customer_service, cost_service
from app.api.deps import get_current_active_user
from app.core.exceptions import ConflictException
from app.database import get_db
from app.main import register_exception_handlers
from app.models.consignment_number_guard import ConsignmentNumberGuard
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.customer_service import ConsignmentInfo, ConsignmentRegistration
from app.schemas.customer_service import ConsignmentInfoCreate
from app.utils.helpers import CHINA_TIMEZONE


MODELS = (ConsignmentInfo, ConsignmentRegistration, CostConsignment, CostRegistration,
          ConsignmentOperationLog, ConsignmentNumberGuard)
NUMBER = "784-12345678"


def payload(number=NUMBER):
    return {"payables": {"intl_air": {"flight_doc_no": number}}}


class CustomerConsignmentDuplicateTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = datetime(2026, 11, 11, 10, 30, tzinfo=CHINA_TIMEZONE)
        self.clock_patch = patch("app.services.consignment_duplicate.get_china_now", return_value=self.now)
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)

        def stamp_created_at(_mapper, _connection, record):
            if record.created_at is None:
                record.created_at = self.now.replace(tzinfo=None)

        event.listen(ConsignmentInfo, "before_insert", stamp_created_at)
        self.addCleanup(event.remove, ConsignmentInfo, "before_insert", stamp_created_at)
        self.engine = create_engine("sqlite:///:memory:")
        for model in MODELS:
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(customer_service.router, prefix="/api/v1/customer-service")
        app.include_router(cost_service.router, prefix="/api/v1/cost-service")

        async def test_db():
            try:
                yield self.db
            except Exception:
                self.db.rollback()
                raise

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=99, name="操作员")
        self.app = app
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
        )
        self.base = "/api/v1/customer-service/consignments"

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    def seed(self, record_id=1, number=NUMBER, *, age=1, status=0, **fields):
        record = ConsignmentInfo(
            id=record_id, financial_data=payload(number), status=status,
            created_at=self.now.replace(tzinfo=None) - timedelta(days=age), **fields,
        )
        self.db.add(record)
        self.db.commit()
        return record

    def counts(self):
        return tuple(self.db.query(model).count() for model in MODELS)

    def assert_duplicate(self, response):
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(response.json(), {"code": 409, "data": None, "msg": "该运单已存在"})

    async def test_both_create_routes_reject_recent_draft_saved_and_voided_without_writing(self):
        for state in (0, 1, 2):
            self.seed(record_id=state + 1, number=f"NO-{state}", status=state)
        before = self.counts()
        for state in (0, 1, 2):
            for suffix in ("", "/draft"):
                self.assert_duplicate(await self.client.post(self.base + suffix, json=payload(f"NO-{state}")))
                self.assertEqual(self.counts(), before)

    async def test_successful_create_draft_then_repeat_create_is_rejected(self):
        for suffix, number in (("", "SAVED"), ("/draft", "DRAFT")):
            created = await self.client.post(self.base + suffix, json=payload(number))
            self.assertEqual(created.status_code, 200, created.text)
            data = created.json()["data"]
            self.assertEqual(data["payables"]["intl_air"]["flight_doc_no"], number)
            self.assertTrue(data["editable"])
            before = self.counts()
            for retry_suffix in ("", "/draft"):
                self.assert_duplicate(await self.client.post(self.base + retry_suffix, json=payload(number)))
            self.assertEqual(self.counts(), before)

    async def test_cutoff_inclusive_uses_created_at_not_business_or_updated_dates(self):
        boundary = self.seed(number="BOUNDARY", age=30,
                             create_time=datetime(2020, 1, 1), flight_date=datetime(2020, 1, 1).date())
        self.assert_duplicate(await self.client.post(self.base, json=payload("BOUNDARY")))
        boundary.created_at -= timedelta(seconds=1)
        boundary.updated_at = self.now.replace(tzinfo=None)
        self.db.commit()
        created = await self.client.post(self.base, json={"create_time": "2020-01-01 00:00:00", **payload("BOUNDARY")})
        self.assertEqual(created.status_code, 200, created.text)
        # 新记录制单时间虽很旧，创建时间在窗口内，不能通过手填旧日期绕过。
        self.assert_duplicate(await self.client.post(self.base + "/draft", json=payload("BOUNDARY")))

    async def test_only_customer_international_number_is_checked(self):
        self.db.add_all([
            ConsignmentInfo(id=1, flight_doc_no=NUMBER, bill_of_lading=NUMBER, internal_doc_id=NUMBER,
                            financial_data={"payables": {"dom_air": {"flight_doc_no": NUMBER},
                                                         "trucking": {"flight_doc_no": NUMBER}}}),
            CostConsignment(id=2, pay_intl_air_flight_doc_no=NUMBER),
            ConsignmentRegistration(id=3, financial_data=payload(NUMBER)),
        ])
        self.db.commit()
        response = await self.client.post(self.base + "/draft", json=payload())
        self.assertEqual(response.status_code, 200, response.text)
        self.assert_duplicate(await self.client.post(self.base, json=payload()))

    async def test_empty_missing_and_null_do_not_trigger_duplicate_check_or_fallback(self):
        self.seed()
        for values in ({}, {"payables": None}, {"payables": {}}, {"payables": {"intl_air": None}},
                       payload(None), payload(""), payload("   "), {"flight_doc_no": NUMBER}):
            for suffix in ("", "/draft"):
                response = await self.client.post(self.base + suffix, json=values)
                self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.query(ConsignmentNumberGuard).count(), 0)

    async def test_exact_match_trims_spaces_ignores_letter_case_and_preserves_storage(self):
        self.seed(number="  AbC-001%_  ")
        for number in ("abc-001%_", " ABC-001%_ "):
            self.assert_duplicate(await self.client.post(self.base + "/draft", json=payload(number)))
        for number in ("ABC-001", "ABC001%_", "ABC-1%_", "AbC-001%_2"):
            created = await self.client.post(self.base + "/draft", json=payload(number))
            self.assertEqual(created.status_code, 200, created.text)
            self.assertEqual(created.json()["data"]["payables"]["intl_air"]["flight_doc_no"], number)
        self.assertEqual(self.db.get(ConsignmentInfo, 1).financial_data, payload("  AbC-001%_  "))
        self.seed(record_id=2, number="ß-001")
        self.assert_duplicate(await self.client.post(self.base + "/draft", json=payload("ß-001")))

    async def test_update_excludes_self_and_rejects_number_change_before_any_sync_or_log(self):
        self.seed(record_id=1, number="OLD", status=1)
        self.seed(record_id=2, number="TAKEN")
        for suffix in ("", "/draft"):
            saved = await self.client.put(self.base + "/1" + suffix, json=payload("OLD"))
            self.assertEqual(saved.status_code, 200, saved.text)
            before = self.counts()
            self.assert_duplicate(await self.client.put(self.base + "/1" + suffix, json={
                "pieces": 99, "receivables": {"first_leg_fee": 123}, **payload("TAKEN"),
            }))
            self.assertEqual(self.counts(), before)
            self.db.expire_all()
            self.assertEqual(self.db.get(ConsignmentInfo, 1).financial_data, payload("OLD"))
            self.assertIsNone(self.db.get(ConsignmentInfo, 1).pieces)
            self.assertEqual(self.db.get(CostConsignment, 1).pay_intl_air_flight_doc_no, "OLD")

    async def test_empty_draft_cannot_fill_existing_number_and_unrelated_edits_remain_allowed(self):
        self.seed(number=NUMBER)
        created = await self.client.post(self.base + "/draft", json={})
        path = self.base + "/" + created.json()["data"]["id"]
        for suffix in ("", "/draft"):
            self.assert_duplicate(await self.client.put(path + suffix, json=payload()))
        self.assertEqual((await self.client.put(path + "/draft", json={"pieces": 2})).status_code, 200)
        # 历史重复不妨碍只改备注；明确再次提交重复号码时才触发校验。
        self.seed(record_id=2, number=NUMBER)
        self.assertEqual((await self.client.put(self.base + "/2/draft", json={"remark": "其他字段"})).status_code, 200)
        self.assert_duplicate(await self.client.put(self.base + "/2/draft", json=payload()))

    async def test_not_found_voided_locked_and_validation_errors_keep_original_priority(self):
        self.seed()
        self.seed(record_id=2, number="OTHER", edit_locked=True)
        self.seed(record_id=3, number="VOID", status=2)
        for suffix in ("", "/draft"):
            missing = await self.client.put(self.base + "/999" + suffix, json=payload())
            self.assertEqual(missing.status_code, 404)
            for record_id, expected in ((2, "费用登记台已保存提交"), (3, "已作废")):
                response = await self.client.put(self.base + f"/{record_id}" + suffix, json=payload())
                self.assertEqual(response.status_code, 409)
                self.assertIn(expected, response.json()["msg"])
        before = self.counts()
        invalid = await self.client.post(self.base, json={"payables": {"intl_air": {"flight_doc_no": []}}})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(self.counts(), before)

    async def test_templates_and_cost_writes_keep_existing_behavior(self):
        self.seed()
        for path in ("/api/v1/customer-service/consignment-registration", "/api/v1/cost-service/cost-registration"):
            response = await self.client.put(path, json=payload())
            self.assertEqual(response.status_code, 200, response.text)
        for suffix in ("", "/draft"):
            response = await self.client.post("/api/v1/cost-service/consignments" + suffix, json=payload())
            self.assertEqual(response.status_code, 200, response.text)

    async def test_failed_commit_rolls_back_guard_and_does_not_consume_number(self):
        before = self.counts()
        with patch.object(self.db, "commit", side_effect=RuntimeError("模拟数据库提交失败")):
            failed = await self.client.post(self.base, json=payload())
        self.assertEqual(failed.status_code, 500)
        self.assertEqual(self.counts(), before)
        retry = await self.client.post(self.base, json=payload())
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assert_duplicate(await self.client.post(self.base, json=payload()))

    def test_openapi_declares_exact_duplicate_response_on_all_four_write_routes(self):
        paths = self.app.openapi()["paths"]
        for suffix, method in (("", "post"), ("/draft", "post"),
                               ("/{consignment_id}", "put"), ("/{consignment_id}/draft", "put")):
            sample = paths[self.base + suffix][method]["responses"]["409"]["content"]["application/json"]["example"]
            self.assertEqual((sample["code"], sample["msg"]), (409, "该运单已存在"))
            # FastAPI生成OpenAPI时会剔除示例中的None，实际HTTP响应由上面的用例完整断言。
            self.assertIsNone(sample.get("data"))

    def test_duplicate_read_uses_fresh_snapshot_json_parameter_binding_without_range_locks(self):
        statements = []
        order = []

        def capture(state):
            if state.is_select:
                statements.append(state.statement)
                order.append("read")
            elif state.is_insert:
                order.append("guard")

        def transaction_ended(_session, _transaction):
            order.append("snapshot-ended")

        self.db.query(ConsignmentInfo.id).first()  # 模拟认证或状态预检查已建立读快照。
        event.listen(self.db, "do_orm_execute", capture)
        event.listen(self.db, "after_transaction_end", transaction_ended)
        try:
            from app.services.consignment_duplicate import ensure_customer_intl_number_available
            ensure_customer_intl_number_available(self.db, ConsignmentInfoCreate(**payload()))
        finally:
            event.remove(self.db, "do_orm_execute", capture)
            event.remove(self.db, "after_transaction_end", transaction_ended)
            self.db.rollback()
        self.assertEqual(order, ["snapshot-ended", "guard", "read"])
        sql = str(statements[0].compile(dialect=mysql.dialect()))
        self.assertNotIn("FOR UPDATE", sql)
        self.assertIn("JSON_EXTRACT", sql)
        self.assertIn("consignment_infos.created_at >=", sql)
        self.assertNotIn(NUMBER, sql)

    def test_mysql_guard_is_transactional_upsert_and_string_equality_is_binary(self):
        from sqlalchemy import select
        from app.services.consignment_duplicate import ensure_customer_intl_number_available

        db = MagicMock(spec=Session)
        db.new, db.dirty, db.deleted = set(), set(), set()
        db.get_bind.return_value.dialect.name = "mysql"
        query = db.query.return_value
        query.filter.return_value = query
        query.first.return_value = None
        ensure_customer_intl_number_available(db, ConsignmentInfoCreate(**payload()))
        db.rollback.assert_called_once()
        db.commit.assert_not_called()
        statement = db.execute.call_args.args[0]
        guard_sql = str(statement.compile(dialect=mysql.dialect()))
        self.assertIn("ON DUPLICATE KEY UPDATE", guard_sql)
        self.assertIn("sha2(upper(", guard_sql)
        sql = str(select(ConsignmentInfo.id).where(*query.filter.call_args.args).compile(dialect=mysql.dialect()))
        self.assertIn("COLLATE utf8mb4_bin", sql)
        self.assertNotIn("FOR UPDATE", sql)

    def test_guard_refuses_to_discard_pending_business_changes(self):
        from app.services.consignment_duplicate import ensure_customer_intl_number_available

        pending = ConsignmentInfo(id=999)
        self.db.add(pending)
        with self.assertRaisesRegex(RuntimeError, "业务写入前"):
            ensure_customer_intl_number_available(self.db, ConsignmentInfoCreate(**payload()))
        self.assertIn(pending, self.db.new)
        self.db.rollback()

    async def test_simultaneous_same_number_creates_allow_only_one_transaction(self):
        with tempfile.TemporaryDirectory() as directory:
            engine = create_engine("sqlite:///" + (Path(directory) / "concurrent.db").as_posix(),
                                   connect_args={"timeout": 10, "check_same_thread": False})
            for model in MODELS:
                model.__table__.create(engine)
            barrier = threading.Barrier(2)

            def create(suffix):
                with Session(engine, autoflush=False) as db:
                    barrier.wait(timeout=5)
                    endpoint = customer_service.create_consignment_draft if suffix else customer_service.create_consignment
                    try:
                        asyncio.run(endpoint(
                            payload=ConsignmentInfoCreate(**payload()),
                            current_user=SimpleNamespace(id=99, name="并发操作员"), db=db,
                        ))
                        return 200
                    except ConflictException as exc:
                        db.rollback()
                        self.assertEqual(exc.detail, "该运单已存在")
                        return 409

            try:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    tasks = [pool.submit(create, suffix) for suffix in ("", "/draft")]
                    self.assertEqual(sorted(task.result(timeout=15) for task in tasks), [200, 409])
                with Session(engine) as db:
                    self.assertEqual(db.query(ConsignmentInfo).count(), 1)
                    self.assertEqual(db.query(ConsignmentOperationLog).count(), 1)
            finally:
                engine.dispose()


if __name__ == "__main__":
    unittest.main()
