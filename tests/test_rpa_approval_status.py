import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.services.rpa_worker import RPAWorker
from app.models.rpa_task import RPATaskType


class RPAApprovalStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_shenzhen_approval_status_5_completes_task(self):
        worker = RPAWorker(robot_db_id=1, robot_name="测试机器人")
        task = SimpleNamespace(
            id=123, job_uuid="job-uuid",
            task_type=RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value,
        )
        db = object()
        status_response = {"records": [{"workUuid": "work-uuid", "status": 5}]}

        with (
            patch(
                "app.services.rpa_worker.rpa_service.query_shenzhen_air_waybill_status",
                new=AsyncMock(return_value=status_response),
            ),
            patch(
                "app.services.rpa_worker.rpa_service.extract_status_from_query_response",
                return_value={"status": 5},
            ),
            patch(
                "app.services.rpa_worker.rpa_task_service.complete_task"
            ) as complete_task,
            patch("app.services.rpa_worker.record_rpa_execution_success") as record_success,
            patch(
                "app.services.rpa_worker.rpa_task_service.timeout_task"
            ) as timeout_task,
            patch(
                "app.services.rpa_worker.settings.RPA_POLL_MAX_COUNT", 1
            ),
            patch(
                "app.services.rpa_worker.settings.RPA_POLL_INTERVAL", 0
            ),
        ):
            await worker._poll_shenzhen_air_approval_data_status(
                db=db, task=task, work_uuid="work-uuid"
            )

        complete_task.assert_called_once_with(db, 123, True)
        record_success.assert_called_once_with(task.task_type, {"status": 5})
        timeout_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
