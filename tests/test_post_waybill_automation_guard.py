import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.rpa_worker import RPAWorker


class _FakeDB:
    def __init__(self):
        self.added = []
        self.commit_count = 0

    def add(self, value):
        self.added.append(value)

    def commit(self):
        self.commit_count += 1


class PostWaybillAutomationGuardTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.worker = RPAWorker(robot_db_id=1, robot_name="测试机器人")
        self.worker._cleanup_queues = AsyncMock()

    async def test_shenzhen_air_keeps_waybill_number_and_skips_follow_up_chain(self):
        db = _FakeDB()
        waybill = SimpleNamespace(
            id=101,
            waybill_number=None,
            airline_record_status="3",
            rpa_queue_uuids="{}",
        )
        queues_info = {
            "waybill_number": {
                "queueUUID": "waybill-number-queue",
            }
        }

        with patch(
            "app.services.rpa_worker.is_post_waybill_automation_enabled",
            return_value=False,
        ), patch(
            "app.services.rpa_worker.rpa_service.get_shenzhen_air_waybill_number",
            new=AsyncMock(return_value="12345678"),
        ), patch(
            "app.services.rpa_worker.rpa_service.format_shenzhen_air_waybill_number",
            return_value="953-12345678",
        ):
            await self.worker._process_shenzhen_air_waybill_success(
                db,
                waybill,
                queues_info,
                {},
            )

        self.assertEqual(waybill.waybill_number, "953-12345678")
        self.assertEqual(waybill.airline_record_status, "3")
        self.assertIsNone(waybill.rpa_queue_uuids)
        self.assertEqual(db.added, [])
        self.worker._cleanup_queues.assert_awaited_once_with(queues_info)

    async def test_china_southern_air_waybill_skips_follow_up_chain(self):
        await self._assert_china_southern_air_follow_up_is_skipped(
            "_process_china_southern_air_waybill_success",
            SimpleNamespace(id=201, rpa_queue_uuids="{}"),
        )

    async def test_china_southern_air_direct_invoice_skips_follow_up_chain(self):
        await self._assert_china_southern_air_follow_up_is_skipped(
            "_process_china_southern_air_direct_invoice_success",
            SimpleNamespace(id=202, rpa_queue_uuids="{}"),
        )

    async def test_china_southern_air_invoice_with_data_skips_follow_up_chain(self):
        await self._assert_china_southern_air_follow_up_is_skipped(
            "_process_china_southern_air_invoice_with_data_success",
            SimpleNamespace(id=203, rpa_queue_uuids="{}"),
        )

    async def _assert_china_southern_air_follow_up_is_skipped(
        self,
        method_name,
        target,
    ):
        db = _FakeDB()
        queues_info = {
            "rate": {
                "queueUUID": "rate-queue",
            }
        }
        method = getattr(self.worker, method_name)

        with patch(
            "app.services.rpa_worker.is_post_waybill_automation_enabled",
            return_value=False,
        ), patch(
            "app.services.rpa_worker.rpa_service.get_china_southern_air_waybill_number",
            new=AsyncMock(),
        ) as get_queue_data:
            await method(db, target, queues_info, {})

        get_queue_data.assert_not_awaited()
        self.assertIsNone(target.rpa_queue_uuids)
        self.assertEqual(db.added, [])
        self.worker._cleanup_queues.assert_awaited_once_with(queues_info)


if __name__ == "__main__":
    unittest.main()
