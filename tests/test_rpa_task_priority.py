import unittest

from app.config import settings
from app.models.rpa_task import RPATaskType
from app.services.rpa_task_service import TASK_PRIORITY_MAP, rpa_task_service


class _FakeDB:
    def __init__(self):
        self.task = None

    def add(self, task):
        self.task = task

    def commit(self):
        pass

    def refresh(self, task):
        pass


class RpaTaskPriorityTests(unittest.TestCase):
    WAYBILL_TASK_TYPES = (
        RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value,
        RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE.value,
        RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value,
        RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value,
    )

    def test_waybill_task_types_use_dedicated_priority(self):
        for task_type in self.WAYBILL_TASK_TYPES:
            with self.subTest(task_type=task_type):
                self.assertEqual(
                    TASK_PRIORITY_MAP[task_type],
                    settings.RPA_QUEUE_WAYBILL_PRIORITY,
                )

    def test_create_task_resolves_waybill_priority_when_omitted(self):
        for task_type in self.WAYBILL_TASK_TYPES:
            with self.subTest(task_type=task_type):
                db = _FakeDB()
                task = rpa_task_service.create_task(
                    db=db,
                    task_type=task_type,
                    target_type="waybill",
                    target_id=1,
                    params={},
                )
                self.assertEqual(task.priority, settings.RPA_QUEUE_WAYBILL_PRIORITY)

    def test_booking_and_cancel_tasks_keep_default_priority(self):
        for task_type in (
            RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_EXECUTE.value,
            RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value,
        ):
            with self.subTest(task_type=task_type):
                self.assertNotIn(task_type, TASK_PRIORITY_MAP)


if __name__ == "__main__":
    unittest.main()
