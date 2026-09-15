"""使用隔离数据库验证跨台操作记录、同步与事务边界。"""
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service, customer_service
from app.api.deps import get_current_active_user
from app.core.exceptions import BadRequestException, ConflictException, NotFoundException
from app.database import get_db
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment
from app.models.customer_service import ConsignmentInfo
from app.schemas.cost_service import CostBatchDeleteRequest, CostConsignmentCreate, CostConsignmentUpdate
from app.schemas.customer_service import (
    BatchDeleteRequest,
    ConsignmentInfoCreate,
    ConsignmentInfoUpdate,
    ConsignmentSubmissionStatus,
)
from app.services.consignment_operation_log import get_consignment_operations


class ConsignmentOperationLogTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (ConsignmentInfo, CostConsignment, ConsignmentOperationLog):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.customer = SimpleNamespace(id=100, name="客服甲")
        self.cost_user = SimpleNamespace(id=200, name="费用乙")

    async def create(self, *, cost=False, draft=False):
        if cost:
            endpoint = cost_service.create_cost_consignment_draft if draft else cost_service.create_cost_consignment
            payload = CostConsignmentCreate(consignor_info={"customer_name": "原客户", "pieces": 8})
            operator = self.cost_user
        else:
            endpoint = customer_service.create_consignment_draft if draft else customer_service.create_consignment
            payload = ConsignmentInfoCreate(customer_name="原客户", pieces=8)
            operator = self.customer
        response = await endpoint(payload, current_user=operator, db=self.db)
        return int(response.data["id"])

    def logs(self, record_id):
        return self.db.query(ConsignmentOperationLog).filter_by(consignment_id=record_id).order_by(
            ConsignmentOperationLog.operated_at, ConsignmentOperationLog.id,
        ).all()

    async def test_cross_desk_history_follows_real_operator_without_duplicate_sync_events(self):
        record_id = await self.create()
        customer = self.db.get(ConsignmentInfo, record_id)
        cost = self.db.get(CostConsignment, record_id)
        self.assertEqual((customer.status, cost.status), (1, 0))
        await cost_service.update_cost_consignment_draft(
            CostConsignmentUpdate(consignor_info={"customer_name": "费用草稿"}),
            str(record_id), current_user=self.cost_user, db=self.db,
        )
        self.assertEqual(customer.customer_name, "原客户")
        await cost_service.update_cost_consignment(
            CostConsignmentUpdate(consignor_info={"customer_name": "费用保存"}),
            str(record_id), current_user=self.cost_user, db=self.db,
        )
        self.assertEqual((customer.status, cost.status), (1, 1))
        self.assertEqual(customer.customer_name, "费用保存")
        await customer_service.update_consignment_draft(
            ConsignmentInfoUpdate(customer_name="客服草稿"), str(record_id),
            current_user=self.customer, db=self.db,
        )
        self.assertEqual(cost.customer_name, "费用保存")
        await customer_service.update_consignment(
            ConsignmentInfoUpdate(customer_name="客服保存"), str(record_id),
            current_user=self.customer, db=self.db,
        )
        self.assertEqual((customer.status, cost.status), (1, 0))
        self.assertEqual(cost.customer_name, "客服保存")
        logs = self.logs(record_id)
        self.assertEqual([r.operation_name for r in logs], [
            "货主委托信息保存", "费用信息暂存", "费用信息保存", "货主委托信息暂存", "货主委托信息保存",
        ])
        self.assertEqual([r.operator_id for r in logs], [100, 200, 200, 100, 100])
        self.customer.name = "改名后的客服"
        customer_result = await customer_service.get_consignment_operation_logs(
            str(record_id), page=1, pageSize=20, current_user=self.customer, db=self.db,
        )
        cost_result = await cost_service.get_cost_consignment_operation_logs(
            str(record_id), page=1, pageSize=20, current_user=self.cost_user, db=self.db,
        )
        self.assertEqual(customer_result.data, cost_result.data)
        self.assertEqual(customer_result.data["total"], 5)
        item = customer_result.data["items"][0]
        self.assertEqual(item["operator_name"], "客服甲")
        self.assertEqual(item["operator_id"], "100")
        self.assertEqual(item["consignment_id"], str(record_id))
        self.assertTrue(item["operated_at"].endswith("+08:00"))
        self.assertIsInstance(item["id"], str)

    async def test_new_drafts_only_exist_in_source_and_log_once(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost, draft=True)
                source_model, other_model = (CostConsignment, ConsignmentInfo) if cost else (ConsignmentInfo, CostConsignment)
                self.assertEqual(self.db.get(source_model, record_id).status, 0)
                self.assertIsNone(self.db.get(other_model, record_id))
                logs = self.logs(record_id)
                self.assertEqual(len(logs), 1)
                self.assertEqual(logs[0].operation_name, "费用信息暂存" if cost else "货主委托信息暂存")
                # 共用时间线即使目标台尚未同步创建，也可从两入口查看。
                self.assertEqual(get_consignment_operations(self.db, str(record_id), page=1, page_size=20).total, 1)

    async def test_cost_create_save_and_customer_draft_save_record_real_actions(self):
        cost_id = await self.create(cost=True)
        self.assertEqual(self.db.get(ConsignmentInfo, cost_id).status, 1)
        self.assertEqual(self.logs(cost_id)[0].operation_name, "费用信息保存")
        customer_id = await self.create(draft=True)
        await customer_service.update_consignment(
            ConsignmentInfoUpdate(pieces=10), str(customer_id), current_user=self.customer, db=self.db,
        )
        self.assertEqual(self.db.get(CostConsignment, customer_id).pay_intl_air_pieces, 10)
        self.assertEqual([r.action for r in self.logs(customer_id)], ["draft", "save"])
        cost_draft_id = await self.create(cost=True, draft=True)
        await cost_service.update_cost_consignment(
            CostConsignmentUpdate(consignor_info={"pieces": 12}), str(cost_draft_id),
            current_user=self.cost_user, db=self.db,
        )
        customer_record = self.db.get(ConsignmentInfo, cost_draft_id)
        self.assertEqual((customer_record.pieces, customer_record.status), (12, 1))
        self.assertEqual([r.operation_name for r in self.logs(cost_draft_id)], ["费用信息暂存", "费用信息保存"])

    async def test_void_synchronizes_existing_counterpart_and_records_real_operator_once(self):
        self.assertEqual(ConsignmentSubmissionStatus.VOIDED.value, 2)
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost)
                endpoint = cost_service.void_cost_consignment if cost else customer_service.void_consignment
                operator = self.cost_user if cost else self.customer
                response = await endpoint(str(record_id), current_user=operator, db=self.db)

                self.assertEqual(response.data["status"], 2)
                self.assertEqual(self.db.get(ConsignmentInfo, record_id).status, 2)
                self.assertEqual(self.db.get(CostConsignment, record_id).status, 2)
                logs = self.logs(record_id)
                self.assertEqual([record.action for record in logs], ["save", "void"])
                self.assertEqual(
                    logs[-1].operation_name,
                    "费用信息作废" if cost else "货主委托信息作废",
                )
                self.assertEqual(logs[-1].operator_id, operator.id)

                with self.assertRaises(ConflictException):
                    await endpoint(str(record_id), current_user=operator, db=self.db)
                self.assertEqual([record.action for record in self.logs(record_id)], ["save", "void"])

                if cost:
                    update_calls = (
                        (cost_service.update_cost_consignment, CostConsignmentUpdate()),
                        (cost_service.update_cost_consignment_draft, CostConsignmentUpdate()),
                    )
                else:
                    update_calls = (
                        (customer_service.update_consignment, ConsignmentInfoUpdate()),
                        (customer_service.update_consignment_draft, ConsignmentInfoUpdate()),
                    )
                for update_endpoint, payload in update_calls:
                    with self.assertRaises(ConflictException):
                        await update_endpoint(payload, str(record_id), current_user=operator, db=self.db)

    async def test_void_source_only_draft_does_not_create_missing_counterpart(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost, draft=True)
                source_model, other_model = (
                    (CostConsignment, ConsignmentInfo) if cost else (ConsignmentInfo, CostConsignment)
                )
                endpoint = cost_service.void_cost_consignment if cost else customer_service.void_consignment
                operator = self.cost_user if cost else self.customer

                await endpoint(str(record_id), current_user=operator, db=self.db)

                self.assertEqual(self.db.get(source_model, record_id).status, 2)
                self.assertIsNone(self.db.get(other_model, record_id))
                self.assertEqual([record.action for record in self.logs(record_id)], ["draft", "void"])

    async def test_void_and_operation_log_are_rolled_back_together(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost)
                endpoint = cost_service.void_cost_consignment if cost else customer_service.void_consignment
                operator = self.cost_user if cost else self.customer
                original_statuses = (
                    self.db.get(ConsignmentInfo, record_id).status,
                    self.db.get(CostConsignment, record_id).status,
                )
                with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
                    with self.assertRaises(RuntimeError):
                        await endpoint(str(record_id), current_user=operator, db=self.db)
                self.db.rollback()

                self.assertEqual(
                    (
                        self.db.get(ConsignmentInfo, record_id).status,
                        self.db.get(CostConsignment, record_id).status,
                    ),
                    original_statuses,
                )
                self.assertEqual([record.action for record in self.logs(record_id)], ["save"])

    async def test_physical_delete_after_void_removes_voided_counterpart_and_keeps_history(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost)
                void_endpoint = cost_service.void_cost_consignment if cost else customer_service.void_consignment
                delete_endpoint = cost_service.delete_cost_consignment if cost else customer_service.delete_consignment
                operator = self.cost_user if cost else self.customer
                await void_endpoint(str(record_id), current_user=operator, db=self.db)
                await delete_endpoint(str(record_id), current_user=operator, db=self.db)

                self.assertIsNone(self.db.get(ConsignmentInfo, record_id))
                self.assertIsNone(self.db.get(CostConsignment, record_id))
                self.assertEqual([record.action for record in self.logs(record_id)], ["save", "void", "delete"])

    async def test_business_sync_and_log_are_rolled_back_together_on_commit_failure(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                record_id = await self.create(cost=cost)
                endpoint = cost_service.update_cost_consignment if cost else customer_service.update_consignment
                payload = CostConsignmentUpdate(consignor_info={"customer_name": "失败修改"}) if cost else ConsignmentInfoUpdate(customer_name="失败修改")
                with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
                    with self.assertRaises(RuntimeError):
                        await endpoint(payload, str(record_id), current_user=self.cost_user if cost else self.customer, db=self.db)
                self.db.rollback()
                self.assertEqual(self.db.get(ConsignmentInfo, record_id).customer_name, "原客户")
                self.assertEqual(self.db.get(CostConsignment, record_id).customer_name, "原客户")
                self.assertEqual(len(self.logs(record_id)), 1)

    async def test_new_records_sync_and_logs_are_rolled_back_together(self):
        for cost in (False, True):
            for draft in (False, True):
                with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
                    with self.assertRaises(RuntimeError):
                        await self.create(cost=cost, draft=draft)
                self.db.rollback()
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)
        self.assertEqual(self.db.query(ConsignmentInfo).count(), 0)
        self.assertEqual(self.db.query(CostConsignment).count(), 0)

    async def test_single_deletion_retains_history_and_preserves_draft_sync_rules(self):
        for cost in (False, True):
            for draft in (False, True):
                with self.subTest(cost=cost, draft=draft):
                    record_id = await self.create(cost=cost)
                    source_model, other_model = (CostConsignment, ConsignmentInfo) if cost else (ConsignmentInfo, CostConsignment)
                    if draft:
                        self.db.get(source_model, record_id).status = 0
                        self.db.commit()
                    endpoint = cost_service.delete_cost_consignment if cost else customer_service.delete_consignment
                    await endpoint(str(record_id), current_user=self.cost_user if cost else self.customer, db=self.db)
                    self.assertIsNone(self.db.get(source_model, record_id))
                    if draft:
                        self.assertIsNotNone(self.db.get(other_model, record_id))
                    else:
                        self.assertIsNone(self.db.get(other_model, record_id))
                    self.assertEqual(self.logs(record_id)[-1].operation_name, "费用信息删除" if cost else "货主委托信息删除")
                    self.assertEqual(get_consignment_operations(self.db, str(record_id), page=1, page_size=20).total, 2)

    async def test_batch_delete_logs_only_existing_source_records_once(self):
        for cost in (False, True):
            with self.subTest(cost=cost):
                saved_id = await self.create(cost=cost)
                draft_id = await self.create(cost=cost, draft=True)
                voided_id = await self.create(cost=cost)
                void_endpoint = cost_service.void_cost_consignment if cost else customer_service.void_consignment
                operator = self.cost_user if cost else self.customer
                await void_endpoint(str(voided_id), current_user=operator, db=self.db)
                request_type = CostBatchDeleteRequest if cost else BatchDeleteRequest
                endpoint = cost_service.batch_delete_cost_consignments if cost else customer_service.batch_delete_consignments
                response = await endpoint(
                    request_type(ids=[str(saved_id), str(draft_id), str(voided_id), str(saved_id), "999"]),
                    current_user=operator, db=self.db,
                )
                self.assertEqual(response.data["deleted_count"], 3)
                self.assertEqual([r.action for r in self.logs(saved_id)], ["save", "delete"])
                self.assertEqual([r.action for r in self.logs(draft_id)], ["draft", "delete"])
                self.assertEqual([r.action for r in self.logs(voided_id)], ["save", "void", "delete"])
                self.assertIsNone(self.db.get(ConsignmentInfo, voided_id))
                self.assertIsNone(self.db.get(CostConsignment, voided_id))
                self.assertEqual(self.logs(999), [])

    async def test_stable_pagination_empty_history_and_invalid_ids(self):
        fixed_time = datetime(2026, 9, 14, 15, 0, 0)
        with patch("app.services.consignment_operation_log.get_china_now", return_value=fixed_time):
            record_id = await self.create(draft=True)
            await customer_service.update_consignment_draft(
                ConsignmentInfoUpdate(), str(record_id), current_user=self.customer, db=self.db,
            )
        first = get_consignment_operations(self.db, str(record_id), page=1, page_size=1)
        second = get_consignment_operations(self.db, str(record_id), page=2, page_size=1)
        self.assertEqual(first.total, 2)
        self.assertGreater(int(first.items[0].id), int(second.items[0].id))
        self.assertEqual(first.items[0].operated_at, "2026-09-14T15:00:00+08:00")
        self.assertEqual(get_consignment_operations(self.db, str(record_id), page=3, page_size=1).items, [])
        self.db.add(ConsignmentInfo(id=10))
        self.db.commit()
        self.assertEqual(get_consignment_operations(self.db, "10", page=1, page_size=20).total, 0)
        with self.assertRaises(NotFoundException):
            get_consignment_operations(self.db, "999", page=1, page_size=20)
        for invalid in ("abc", "0", "-1", str(2 ** 63)):
            with self.subTest(invalid=invalid), self.assertRaises(BadRequestException):
                get_consignment_operations(self.db, invalid, page=1, page_size=20)

    async def test_deletions_and_logs_rollback_together(self):
        for cost in (False, True):
            for batch in (False, True):
                with self.subTest(cost=cost, batch=batch):
                    record_id = await self.create(cost=cost)
                    if batch:
                        endpoint = cost_service.batch_delete_cost_consignments if cost else customer_service.batch_delete_consignments
                        request_type = CostBatchDeleteRequest if cost else BatchDeleteRequest
                        arg = request_type(ids=[str(record_id)])
                    else:
                        endpoint = cost_service.delete_cost_consignment if cost else customer_service.delete_consignment
                        arg = str(record_id)
                    with patch.object(self.db, "commit", side_effect=RuntimeError("模拟提交失败")):
                        with self.assertRaises(RuntimeError):
                            await endpoint(arg, current_user=self.cost_user if cost else self.customer, db=self.db)
                    self.db.rollback()
                    self.assertIsNotNone(self.db.get(ConsignmentInfo, record_id))
                    self.assertIsNotNone(self.db.get(CostConsignment, record_id))
                    self.assertEqual(len(self.logs(record_id)), 1)

    async def test_failed_modifications_and_deletions_leave_no_history(self):
        for endpoint, arg in (
            (customer_service.update_consignment, ConsignmentInfoUpdate()),
            (customer_service.update_consignment_draft, ConsignmentInfoUpdate()),
            (cost_service.update_cost_consignment, CostConsignmentUpdate()),
            (cost_service.update_cost_consignment_draft, CostConsignmentUpdate()),
        ):
            with self.assertRaises(NotFoundException):
                await endpoint(arg, "999", current_user=self.customer, db=self.db)
        for endpoint in (customer_service.delete_consignment, cost_service.delete_cost_consignment):
            with self.assertRaises(NotFoundException):
                await endpoint("999", current_user=self.customer, db=self.db)
        self.assertEqual(self.db.query(ConsignmentOperationLog).count(), 0)

    async def test_http_routes_authentication_pagination_and_response_schema(self):
        record_id = await self.create()
        app = FastAPI()
        app.include_router(customer_service.router, prefix="/api/v1/customer-service")
        app.include_router(cost_service.router, prefix="/api/v1/cost-service")

        async def test_db():
            return self.db

        async def test_user():
            return self.cost_user

        app.dependency_overrides[get_db] = test_db
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for source in ("customer-service", "cost-service"):
                path = f"/api/v1/{source}/consignments/{record_id}/operation-logs"
                unauthorized = await client.get(path)
                self.assertEqual(unauthorized.status_code, 403)
                app.dependency_overrides[get_current_active_user] = test_user
                response = await client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"]["items"][0]["operator_name"], "客服甲")
                self.assertEqual(response.json()["data"]["pageSize"], 20)
                for query in ("page=0", "pageSize=0", "pageSize=101", "pageSize=abc"):
                    self.assertEqual((await client.get(path + "?" + query)).status_code, 422)
                app.dependency_overrides.pop(get_current_active_user)

            for source in ("customer-service", "cost-service"):
                void_record_id = await self.create(cost=source == "cost-service")
                path = f"/api/v1/{source}/consignments/{void_record_id}/void"
                self.assertEqual((await client.put(path)).status_code, 403)
                app.dependency_overrides[get_current_active_user] = test_user
                response = await client.put(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["data"]["status"], 2)
                list_path = f"/api/v1/{source}/consignments"
                voided_list = await client.get(list_path + "?status=2")
                self.assertEqual(voided_list.status_code, 200)
                self.assertGreaterEqual(voided_list.json()["data"]["total"], 1)
                self.assertTrue(all(item["status"] == 2 for item in voided_list.json()["data"]["items"]))
                self.assertEqual((await client.get(list_path + "?status=3")).status_code, 422)
                self.assertEqual((await client.put(path)).status_code, 409)
                app.dependency_overrides.pop(get_current_active_user)


if __name__ == "__main__":
    unittest.main()
