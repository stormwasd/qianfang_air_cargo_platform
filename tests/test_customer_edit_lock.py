"""费用成功提交才锁定客服；覆盖历史迁移、失败回滚及重复保存。"""
import io
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from openpyxl import load_workbook
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.api import customer_service, cost_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.main import register_exception_handlers
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.customer_service import ConsignmentInfo, ConsignmentRegistration


class CustomerEditLockTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (ConsignmentInfo, ConsignmentRegistration, CostConsignment, CostRegistration, ConsignmentOperationLog):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        app = FastAPI()
        register_exception_handlers(app)
        app.include_router(customer_service.router, prefix="/customer")
        app.include_router(cost_service.router, prefix="/cost")

        async def test_db():
            try:
                yield self.db
            except Exception:
                self.db.rollback()
                raise

        async def test_user():
            return SimpleNamespace(id=99, name="操作员")

        app.dependency_overrides[get_db] = test_db
        app.dependency_overrides[get_current_active_user] = test_user
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test",
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        self.db.close()
        self.engine.dispose()

    async def request(self, method, path, payload=None):
        response = await self.client.request(method, path, json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["data"]

    async def create(self, base="/customer", draft=False):
        data = await self.request("POST", base + "/consignments" + ("/draft" if draft else ""), {})
        return data["id"]

    async def test_saved_customer_remains_editable_until_cost_save_and_never_unlocks_on_cost_draft(self):
        record_id = await self.create()
        customer_path = "/customer/consignments/" + record_id
        cost_path = "/cost/consignments/" + record_id
        customer = await self.request("GET", customer_path)
        self.assertEqual((customer["status"], customer["editable"]), (1, True))
        for pieces in (2, 3):
            saved = await self.request("PUT", customer_path, {
                "pieces": pieces, "customer_tags": ["intl_air"], "expense_tags": ["ground"],
                "receivables": {"customs_fee": 750}, "flight_date": "2026-11-09",
            })
            self.assertTrue(saved["editable"])
            cost = await self.request("GET", cost_path)
            self.assertEqual((cost["status"], cost["consignor_info"]["pieces"]), (0, pieces))
            self.assertEqual(cost["payables"]["intl_air"]["flight_date"], "2026-11-09")
        # 客服暂存不回写费用；费用暂存不锁客服。
        saved = await self.request("PUT", customer_path + "/draft", {"pieces": 4})
        self.assertEqual((saved["status"], saved["editable"]), (0, True))
        self.assertEqual((await self.request("GET", cost_path))["consignor_info"]["pieces"], 3)
        await self.request("PUT", cost_path + "/draft", {"consignor_info": {"pieces": 5}})
        self.assertTrue((await self.request("GET", customer_path))["editable"])
        await self.request("PUT", cost_path, {})
        self.db.expire_all()
        customer = await self.request("GET", customer_path)
        self.assertEqual((customer["status"], customer["editable"], customer["pieces"]), (1, False, 5))
        await self.request("PUT", cost_path + "/draft", {"consignor_info": {"pieces": 6}})
        self.assertFalse((await self.request("GET", customer_path))["editable"])
        before = self.db.query(ConsignmentOperationLog).count()
        for suffix in ("", "/draft"):
            response = await self.client.put(customer_path + suffix, json={
                "pieces": 999, "customer_tags": [], "expense_tags": [],
                "editable": True, "edit_locked": False, "status": 0,
            })
            self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)
        self.assertEqual((await self.request("GET", customer_path))["pieces"], 5)
        self.assertEqual((await self.request("GET", cost_path))["consignor_info"]["pieces"], 6)

    async def test_only_successful_cost_commit_locks_and_failed_save_can_retry(self):
        record_id = await self.create()
        customer_path = "/customer/consignments/" + record_id
        cost_path = "/cost/consignments/" + record_id
        before = self.db.query(ConsignmentOperationLog).count()
        with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
            response = await self.client.put(cost_path, json={"consignor_info": {"pieces": 100}})
        self.assertEqual(response.status_code, 500)
        self.db.expire_all()
        self.assertTrue((await self.request("GET", customer_path))["editable"])
        self.assertEqual((await self.request("GET", cost_path))["status"], 0)
        self.assertIsNone((await self.request("GET", customer_path))["pieces"])
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), before)
        self.assertTrue((await self.request("PUT", customer_path, {"pieces": 8}))["editable"])
        await self.request("PUT", cost_path, {})
        self.assertFalse((await self.request("GET", customer_path))["editable"])

    async def test_customer_save_failure_does_not_consume_edit_or_sync_data(self):
        record_id = await self.create(draft=True)
        customer_path = "/customer/consignments/" + record_id
        with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
            response = await self.client.put(customer_path, json={"pieces": 100})
        self.assertEqual(response.status_code, 500)
        detail = await self.request("GET", customer_path)
        self.assertEqual((detail["status"], detail["editable"], detail["pieces"]), (0, True, None))
        self.assertIsNone(self.db.get(CostConsignment, int(record_id)))
        self.assertTrue((await self.request("PUT", customer_path, {"pieces": 8}))["editable"])
        self.assertTrue((await self.request("PUT", customer_path, {"pieces": 9}))["editable"])

    async def test_validation_failure_and_cost_template_save_do_not_lock_customer(self):
        record_id = await self.create()
        cost_path = "/cost/consignments/" + record_id
        response = await self.client.put(cost_path, json={"customer_tags": ["invalid"]})
        self.assertEqual(response.status_code, 422)
        await self.request("PUT", "/cost/cost-registration", {"consignor_info": {"pieces": 10}})
        await self.request("PUT", "/customer/consignment-registration", {"pieces": 20})
        self.assertTrue((await self.request("GET", "/customer/consignments/" + record_id))["editable"])

    async def test_cost_origin_create_and_draft_submit_both_lock_customer(self):
        for draft in (False, True):
            record_id = await self.create(base="/cost", draft=draft)
            if draft:
                self.assertIsNone(self.db.get(ConsignmentInfo, int(record_id)))
                await self.request("PUT", "/cost/consignments/" + record_id, {})
            self.assertFalse((await self.request("GET", "/customer/consignments/" + record_id))["editable"])
            self.assertTrue(self.db.get(ConsignmentInfo, int(record_id)).edit_locked)

    async def test_legacy_submission_status_is_independent_from_edit_lock_in_list_and_export(self):
        self.db.add_all([
            ConsignmentInfo(id=1, status=1, edit_locked=False),
            ConsignmentInfo(id=2, status=1, edit_locked=True),
            ConsignmentInfo(id=3, status=2, edit_locked=False),
            ConsignmentInfo(id=4, status=0, edit_locked=True),
        ])
        self.db.commit()
        listing = await self.request("GET", "/customer/consignments?status=1")
        self.assertEqual({i["id"]: i["editable"] for i in listing["items"]}, {"1": True, "2": False})
        for record_id, expected in ((1, True), (2, False), (3, False), (4, False)):
            self.assertEqual((await self.request("GET", f"/customer/consignments/{record_id}"))["editable"], expected)
        self.assertTrue((await self.request("PUT", "/customer/consignments/1/draft", {}))["editable"])
        for record_id in (2, 3, 4):
            self.assertEqual((await self.client.put(f"/customer/consignments/{record_id}/draft", json={})).status_code, 409)
        response = await self.client.post("/customer/consignments/export-excel", json={"ids": ["2"]})
        workbook = load_workbook(io.BytesIO(response.content))
        self.addCleanup(workbook.close)
        self.assertEqual(workbook.active.max_column, 94)
        self.assertEqual(workbook.active["B2"].value, "已提交")
        self.assertNotIn("editable", [c.value for c in workbook.active[1]])

    async def test_voided_editable_flag_and_guards_remain_effective(self):
        record_id = await self.create()
        await self.request("PUT", f"/cost/consignments/{record_id}/void")
        self.assertFalse((await self.request("GET", f"/customer/consignments/{record_id}"))["editable"])
        for base in ("/customer", "/cost"):
            for suffix in ("", "/draft"):
                response = await self.client.put(f"{base}/consignments/{record_id}{suffix}", json={})
                self.assertEqual(response.status_code, 409)

    async def test_customer_and_cost_saves_lock_existing_rows_in_same_order(self):
        record_id = await self.create()
        locked_tables = []

        def collect_locks(execute_state):
            statement = execute_state.statement
            if execute_state.is_select and statement._for_update_arg is not None:
                locked_tables.extend(table.name for table in statement.get_final_froms())

        event.listen(self.db, "do_orm_execute", collect_locks)
        try:
            await self.request("PUT", f"/customer/consignments/{record_id}", {})
            self.assertEqual(locked_tables, ["consignment_infos", "cost_consignments"])
            locked_tables.clear()
            await self.request("PUT", f"/cost/consignments/{record_id}", {})
            self.assertEqual(locked_tables, ["consignment_infos", "cost_consignments"])
        finally:
            event.remove(self.db, "do_orm_execute", collect_locks)

    def test_migration_backfills_only_evidenced_cost_submissions_without_reordering(self):
        old_time = datetime(2026, 10, 1, 8)
        for record_id in range(1, 6):
            self.db.add(ConsignmentInfo(id=record_id, status=1, updated_at=old_time))
        self.db.add_all([
            CostConsignment(id=1, status=0),  # 仅客服提交，解锁。
            CostConsignment(id=2, status=1),  # 历史费用已提交，锁定。
            CostConsignment(id=3, status=0),  # 费用保存后又暂存，有日志仍锁定。
            CostConsignment(id=4, status=0),  # 只有费用暂存日志，不锁。
        ])
        for record_id, source, action in ((1, "customer_service", "save"), (3, "cost_service", "save"), (4, "cost_service", "draft")):
            self.db.add(ConsignmentOperationLog(
                consignment_id=record_id, source=source, action=action,
                operation_name="历史操作", operator_id=99, operator_name="操作员",
            ))
        self.db.commit()
        script = (Path(__file__).resolve().parents[1] / "sql/migration_add_customer_edit_lock.sql").read_text(encoding="utf-8")
        backfill = script[script.index("UPDATE `consignment_infos`"):]
        self.db.execute(text(backfill))
        self.db.commit()
        self.db.expire_all()
        self.assertEqual([self.db.get(ConsignmentInfo, i).edit_locked for i in range(1, 6)], [False, True, True, False, False])
        self.assertTrue(all(self.db.get(ConsignmentInfo, i).updated_at == old_time for i in range(1, 6)))
        self.assertTrue(all(self.db.get(ConsignmentInfo, i).status == 1 for i in range(1, 6)))
        self.db.execute(text(backfill))  # 回填可重跑，不解开已有锁。
        self.db.commit()
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 3)


if __name__ == "__main__":
    unittest.main()
