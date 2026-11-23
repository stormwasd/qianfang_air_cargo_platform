"""订舱完整联系人标记：成功快照、响应一致性、失败和重试，不拦截直接开单。"""
import copy
import json
import os
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import bookings as api
from app.api import china_southern_air_booking_tasks as tasks_api
from app.api.deps import get_current_active_user
from app.database import get_db
from app.main import register_exception_handlers
from app.models.booking import Booking
from app.models.china_southern_air_booking_task import ChinaSouthernAirBookingTask as Task
from app.models.config import BusinessConfig
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.models.nanhang_token import NanHangToken
from app.models.rpa_task import RPATask, RPATaskType
from app.schemas.booking import BookingExecuteItem
from app.services.china_southern_air_direct_order import ChinaSouthernAirDirectOrderError, ChinaSouthernAirDirectOrderService
from app.services.direct_booking_worker import DirectBookingWorker
from app.utils.helpers import get_china_now
from tests.test_china_southern_air_booking_contacts import configuration, form, excel_content, excel_row
from tests.test_china_southern_air_booking_volume import _direct_order_form


class BookingContactFlagTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (Booking, BusinessConfig, DictType, DictOption, RPATask, Task, NanHangToken):
            model.__table__.create(self.engine)
        self.factory = sessionmaker(bind=self.engine)
        self.db = self.factory()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        config = configuration()
        config["china_southern_air"]["booking_and_create"]["china_southern_air_login"] = {
            "system_url": "https://example.invalid/booking", "system_account": "test", "login_password": "test",
        }
        self.config = BusinessConfig(config_data=json.dumps(config, ensure_ascii=False))
        settings_patch = patch.multiple(
            api.settings, CHINA_SOUTHERN_AIR_BOOKING_EXECUTION_MODE="direct",
            CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_EXECUTION_MODE="rpa",
            CHINA_SOUTHERN_AIR_DIRECT_BOOKING_QUEUE_ENABLED=True,
        )
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.booking = Booking(id=101, form_data=json.dumps(form(), ensure_ascii=False),
                               booking_time=get_china_now(), booking_status="0", invoice_status="0")
        self.db.add_all([self.config, self.booking])
        self.db.commit()
        self.app = FastAPI()
        self.app.include_router(api.router, prefix="/api/v1/bookings")
        self.app.include_router(tasks_api.router, prefix="/api/v1/china-southern-air-booking-tasks")
        register_exception_handlers(self.app)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=1)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    def prepare_execution(self, data=None, previous_flag=False):
        self.booking.form_data = json.dumps(data or form(), ensure_ascii=False)
        self.booking.has_complete_contact_info = previous_flag
        self.booking.booking_status = "0"
        self.db.commit()

    async def run_booking(self, *, config=None, create_error=None, live_http=False):
        """隔离前置查询和库存；成功/失败标记通过真实执行函数和真实数据库事务写入。"""
        request_contact = []
        service = api.china_southern_air_direct_booking_service

        async def create(**kwargs):
            with self.factory() as observer:
                during = observer.get(Booking, 101)
                self.assertFalse(during.has_complete_contact_info)
                self.assertEqual(during.booking_status, "1")
            request_contact.append(copy.deepcopy(kwargs["payload"]["orderInfo"]["orderShipmentContact"]))
            if create_error:
                raise create_error

        async def resolve_codes(**kwargs):
            kwargs["values"]["sp_code"] = "XPS/AKA"
            return {"platform_code": "XPS,AKA", "upstream_code": "XPS/AKA"}

        with ExitStack() as stack:
            stack.enter_context(patch.object(service, "resolve_volume", new=AsyncMock(return_value=1.2)))
            stack.enter_context(patch.object(service, "resolve_cabin_class", new=AsyncMock(return_value={})))
            stack.enter_context(patch.object(service, "resolve_special_cargo_code", new=AsyncMock(side_effect=resolve_codes)))
            stack.enter_context(patch.object(service, "query_matching_flight", new=AsyncMock(return_value={"bookMemo": "", "actype": "320"})))
            stack.enter_context(patch.object(api.china_southern_air_service, "query_service_charges", new=AsyncMock(return_value=[{
                "serviceMainName": "出港货邮处理费", "checked": "Y",
                "serviceCharges": [{"otherChargeName": "普货", "checked": "Y"}],
            }])))
            stack.enter_context(patch.object(service, "calculate_charge", new=AsyncMock(return_value={"extServiceCharges": []})))
            self.reserve = stack.enter_context(patch.object(api, "_reserve_china_southern_air_booking_stock_item", return_value=SimpleNamespace(
                id=9, full_number="784-12345670", number_prefix="784", number_suffix="12345670")))
            stack.enter_context(patch.object(api, "confirm_stock_item_used"))
            self.release = stack.enter_context(patch.object(api, "_release_china_southern_air_booking_stock_item"))
            self.isolate = stack.enter_context(patch.object(api, "_isolate_china_southern_air_booking_stock_item"))
            if live_http:
                stack.enter_context(patch.object(ChinaSouthernAirDirectOrderService, "CREATE_ORDER_URL",
                    os.environ["CSA_CONTACT_SIMULATION_URL"].rstrip('/') + "/order-center/b2e-order/b2eOrder/createOrder"))
            else:
                stack.enter_context(patch.object(service, "create_order", new=AsyncMock(side_effect=create)))
            await api._execute_china_southern_air_direct_booking(
                self.db, booking_id=101, form_data=json.loads(self.booking.form_data),
                business_config=config or json.loads(self.config.config_data), token="synthetic-test-token",
            )
        self.db.refresh(self.booking)
        return request_contact

    async def test_success_sets_true_only_after_complete_contact_was_sent(self):
        contact = (await self.run_booking())[0]
        self.assertEqual(contact["shipperName"], "配置托运公司")
        self.assertEqual(contact["consigneeName"], "收货人甲")
        with self.factory() as observer:
            saved = observer.get(Booking, 101)
            self.assertTrue(saved.has_complete_contact_info)
            self.assertEqual(saved.booking_status, "3")
        # 配置后续变化不会改变已成功提交的快照。
        self.config.config_data = "{}"
        self.db.commit()
        detail = await self.client.get("/api/v1/bookings/101")
        self.assertTrue(detail.json()["data"]["has_complete_contact_info"])

    async def test_missing_recipient_still_books_with_false_flag_and_no_contacts(self):
        for name, phone in ((None, None), ("甲", ""), ("", "123"), ("甲", " ")):
            with self.subTest(name=name, phone=phone):
                self.prepare_execution(form(name, phone), previous_flag=True)
                self.assertEqual(await self.run_booking(), [None])
                self.assertFalse(self.booking.has_complete_contact_info)
                self.assertEqual(self.booking.booking_status, "3")

    async def test_create_failure_does_not_leave_true_flag(self):
        for uncertain in (False, True):
            with self.subTest(uncertain=uncertain):
                self.prepare_execution(previous_flag=True)
                with self.assertRaises(api.ChinaSouthernAirDirectBookingError):
                    await self.run_booking(create_error=ChinaSouthernAirDirectOrderError("模拟失败", outcome_unknown=uncertain))
                self.db.refresh(self.booking)
                self.assertFalse(self.booking.has_complete_contact_info)
                self.assertEqual(self.booking.booking_status, "2")
                self.assertEqual(self.isolate.called, uncertain)

    async def test_incomplete_shipper_still_books_without_contacts(self):
        changes = [
            ("shipper", None), ("shipper", " "), ("phone", None), ("phone", "\t"),
            ("address", None), ("address", {"region": "广东省/深圳市/宝安区"}),
            ("address", {"region": "广东省/深圳市", "detail": "机场货站"}),
            ("address", {"region": ["广东省", "", "宝安区"], "detail": "机场货站"}),
        ]
        for key, value in changes:
            with self.subTest(key=key, value=value):
                config = configuration()
                config["china_southern_air"]["booking_and_create"]["business_default"][key] = value
                self.prepare_execution(previous_flag=True)
                self.assertEqual(await self.run_booking(config=config), [None])
                self.assertFalse(self.booking.has_complete_contact_info)
                self.assertEqual(self.booking.booking_status, "3")

    async def test_existing_success_is_not_overwritten_by_failure_or_duplicate_execution(self):
        await self.run_booking()
        with self.assertRaises(api.ChinaSouthernAirDirectBookingError):
            await self.run_booking()
        api._fail_china_southern_air_direct_booking(self.db, 101, "后续异常")
        self.db.refresh(self.booking)
        self.assertTrue(self.booking.has_complete_contact_info)
        self.assertEqual(self.booking.booking_status, "3")

    async def test_read_only_default_and_page_create_update_and_excel_response(self):
        self.assertFalse(self.booking.has_complete_contact_info)
        request = form()
        response = await self.client.post("/api/v1/bookings", json={"form_data": request, "has_complete_contact_info": True})
        self.assertEqual(response.status_code, 200, response.text)
        item = response.json()["data"]["items"][0]
        self.assertIs(item["has_complete_contact_info"], False)
        response = await self.client.put("/api/v1/bookings/101", json={"form_data": request, "has_complete_contact_info": True})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(response.json()["data"]["has_complete_contact_info"], False)
        self.db.add(DictType(id=1, name="货物类型", type="nanfang_air_cargo_type", status=1))
        self.db.add(DictOption(id=1, dict_type_id=1, label="普货", value="3006", status=1))
        self.db.commit()
        response = await self.client.post("/api/v1/bookings/china-southern-air/import-excel", files={
            "file": ("bookings.xlsx", excel_content([excel_row()]), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIs(response.json()["data"]["items"][0]["has_complete_contact_info"], False)
        # 数据库默认值同样覆盖不经过 ORM default 的写入。
        self.db.execute(text("INSERT INTO bookings (id,form_data,booking_status,invoice_status,booking_time,booking_cancel_status,created_at,updated_at) VALUES (102,'{}','0','0',CURRENT_TIMESTAMP,'0',CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)"))
        self.db.commit()
        self.assertFalse(self.db.get(Booking, 102).has_complete_contact_info)

    async def test_list_detail_preview_and_action_responses_return_persisted_flag(self):
        await self.run_booking()
        for path in ("/api/v1/bookings/101", "/api/v1/bookings/101/waybill-form"):
            result = await self.client.get(path)
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIs(result.json()["data"]["has_complete_contact_info"], True)
        result = await self.client.get("/api/v1/bookings")
        self.assertIs(result.json()["data"]["items"][0]["has_complete_contact_info"], True)
        for path in ("direct-invoice", "cancel"):
            result = await self.client.post(f"/api/v1/bookings/101/{path}")
            self.assertEqual(result.status_code, 200, result.text)
            self.assertIs(result.json()["data"]["has_complete_contact_info"], True)
            if path == "cancel":
                cancel_task = self.db.query(RPATask).filter(
                    RPATask.task_type == RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value,
                ).one()
                self.assertEqual(cancel_task.priority, api.settings.RPA_QUEUE_WAYBILL_PRIORITY)
        self.db.query(RPATask).delete()
        self.db.commit()
        result = await self.client.post("/api/v1/bookings/101/invoice-with-data", json=_direct_order_form("1.2"))
        self.assertEqual(result.status_code, 200, result.text)
        self.assertIs(result.json()["data"]["has_complete_contact_info"], True)

    async def test_direct_invoice_no_longer_blocks_missing_contacts_and_keeps_existing_guards(self):
        self.booking.master_airwaybill_number = "784-12345670"
        self.booking.form_data = json.dumps(form(None, None))
        config = json.loads(self.config.config_data)
        config["china_southern_air"]["booking_and_create"]["business_default"] = {}
        self.config.config_data = json.dumps(config)
        self.db.commit()
        result = await self.client.post("/api/v1/bookings/101/direct-invoice")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["data"]["has_complete_contact_info"])
        self.assertEqual(self.db.query(RPATask).one().task_type, RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value)
        duplicate = await self.client.post("/api/v1/bookings/101/direct-invoice")
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("已有待执行或执行中的开单任务", duplicate.json()["msg"])

    async def test_form_changes_invalidate_flag_but_identical_save_keeps_it(self):
        await self.run_booking()
        current = json.loads(self.booking.form_data)
        result = await self.client.put("/api/v1/bookings/101", json={"form_data": current})
        self.assertTrue(result.json()["data"]["has_complete_contact_info"])
        current["bookings"][0]["consignee"] = "新收货人"
        result = await self.client.put("/api/v1/bookings/101", json={"form_data": current})
        self.assertFalse(result.json()["data"]["has_complete_contact_info"])

    async def test_execute_results_return_actual_database_flags_and_invalid_ids_are_safe(self):
        await self.run_booking()
        items = [BookingExecuteItem(booking_id=x, success=False) for x in ("101", "404", "bad", str(2**70))]
        api._fill_booking_contact_flags(self.db, items)
        self.assertEqual([x.has_complete_contact_info for x in items], [True, False, False, False])
        response = await self.client.post("/api/v1/bookings/execute", json={"booking_ids": ["101", "bad"]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"]["items"][0]["has_complete_contact_info"])
        self.assertFalse(response.json()["data"]["items"][1]["has_complete_contact_info"])

    async def test_update_can_still_repair_invalid_stored_form_data(self):
        self.booking.form_data = "invalid-json"
        self.booking.has_complete_contact_info = True
        self.db.commit()
        result = await self.client.put("/api/v1/bookings/101", json={"form_data": form()})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["data"]["has_complete_contact_info"])

    async def test_worker_success_task_result_contains_snapshot(self):
        task = Task(id=1001, batch_id=1000, booking_id=101, params='{"booking_id":101}', status="running", priority=1)
        self.db.add_all([task, NanHangToken(token="synthetic-test-token")])
        self.db.commit()
        worker = DirectBookingWorker(0)

        async def execute(db, **kwargs):
            record = db.get(Booking, kwargs["booking_id"])
            record.booking_status = "3"
            record.has_complete_contact_info = True
            db.commit()

        with patch.object(worker, "_claim_task", return_value=1001), \
             patch("app.services.direct_booking_worker.SessionLocal", self.factory), \
             patch.object(api, "_execute_china_southern_air_direct_booking", new=AsyncMock(side_effect=execute)):
            self.assertTrue(await worker._process_one())
        self.db.expire_all()
        for path in ("/api/v1/china-southern-air-booking-tasks/1001", "/api/v1/china-southern-air-booking-tasks"):
            result = await self.client.get(path)
            self.assertEqual(result.status_code, 200, result.text)
            data = result.json()["data"]
            if "list" in data:
                data = data["list"][0]
            self.assertIs(data["result"]["has_complete_contact_info"], True)

    async def test_execute_waits_for_worker_and_returns_final_contact_flag(self):
        async def finish_pending_tasks(_delay):
            with self.factory() as worker_db:
                record = worker_db.get(Booking, 101)
                self.assertFalse(record.has_complete_contact_info)
                record.booking_status = "3"
                record.has_complete_contact_info = True
                worker_db.query(Task).filter(Task.booking_id == 101).one().status = "success"
                worker_db.commit()

        self.prepare_execution(previous_flag=True)
        with patch.object(api.asyncio, "sleep", new=AsyncMock(side_effect=finish_pending_tasks)):
            result = await self.client.post("/api/v1/bookings/execute", json={"booking_ids": ["101"]})
        self.assertEqual(result.status_code, 200, result.text)
        data = result.json()["data"]
        self.assertEqual(data["success_count"], 1)
        self.assertTrue(data["items"][0]["success"])
        self.assertTrue(data["items"][0]["has_complete_contact_info"])

    async def test_rpa_enqueue_clears_unverified_contact_flag(self):
        self.prepare_execution(previous_flag=True)
        required = (
            "address_of_the_application_executable_file_tangyi", "system_account", "login_password",
            "system_url", "origin_station", "destination", "flight_date", "flight_number",
            "cargo_type", "cargo_code", "cargo_name", "quantity", "weight", "special_cargo_code",
        )
        with patch.multiple(api.settings, CHINA_SOUTHERN_AIR_BOOKING_EXECUTION_MODE="rpa", RPA_QUEUE_ENABLED=True), \
             patch.object(api, "_extract_china_southern_air_params", return_value=dict.fromkeys(required, "test")):
            result = await self.client.post("/api/v1/bookings/execute", json={"booking_ids": ["101"]})
        self.assertEqual(result.status_code, 200, result.text)
        item = result.json()["data"]["items"][0]
        self.assertTrue(item["success"])
        self.assertFalse(item["has_complete_contact_info"])
        self.db.refresh(self.booking)
        self.assertFalse(self.booking.has_complete_contact_info)

    @unittest.skipUnless(os.environ.get("CSA_CONTACT_SIMULATION_URL"), "Local Postman simulation required")
    async def test_snapshot_after_real_http_create_order(self):
        for name, phone, missing_shipper, expected in (
            ("甲", "013800138000", False, True), ("甲", "", False, False),
            ("甲", "013800138000", True, False),
        ):
            data = form(name, phone)
            data["bookings"][0]["cargo_type"] = "普通货物"
            self.prepare_execution(data)
            config = configuration()
            if missing_shipper:
                config["china_southern_air"]["booking_and_create"]["business_default"]["address"]["detail"] = " "
            await self.run_booking(config=config, live_http=True)
            self.assertEqual(self.booking.has_complete_contact_info, expected)
