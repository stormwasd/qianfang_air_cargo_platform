import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.robot import Robot, TaskProcess
from app.models.rpa_task import RPATask, RPATaskType
from app.services.rpa_service import RPAService
from app.services.rpa_worker import RPAWorker
from app.services.shenzhen_air_get_har_scheduler import (
    DEFAULT_PARAMS,
    ShenzhenAirGetHarScheduler,
)


class ShenzhenAirGetHarSchedulerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Robot.__table__.create(self.engine)
        TaskProcess.__table__.create(self.engine)
        RPATask.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_enqueues_only_permitted_active_robot_and_deduplicates(self):
        task_type = RPATaskType.SHENZHEN_AIR_GET_HAR.value
        self.db.add(TaskProcess(
            id=1,
            task_name=task_type,
            chinese_name="深航获取har",
            process_detail_uuid="9d55ee2fbd0460f44c1dd1c47f5f7e32",
            version="0.0.2",
            process_param=json.dumps(DEFAULT_PARAMS),
        ))
        self.db.add_all([
            Robot(
                id=11,
                robot_id="encrypted-11",
                name="有权限机器人",
                location="shenzhen_air",
                task_permissions=json.dumps([task_type]),
                status=1,
            ),
            Robot(
                id=12,
                robot_id="encrypted-12",
                name="无权限机器人",
                location="shenzhen_air",
                task_permissions="[]",
                status=1,
            ),
            Robot(
                id=13,
                robot_id="encrypted-13",
                name="停用机器人",
                location="shenzhen_air",
                task_permissions=json.dumps([task_type]),
                status=0,
            ),
        ])
        self.db.commit()

        scheduler = ShenzhenAirGetHarScheduler()
        with patch(
            "app.services.shenzhen_air_get_har_scheduler.SessionLocal",
            return_value=self.db,
        ):
            await scheduler._enqueue_tasks()
            await scheduler._enqueue_tasks()

        tasks = self.db.query(RPATask).all()
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task.task_type, task_type)
        self.assertEqual(task.target_type, "shenzhen_air_get_har")
        self.assertEqual(task.target_id, 11)
        self.assertEqual(task.robot_id, 11)
        self.assertEqual(task.location, "shenzhen_air")
        self.assertEqual(json.loads(task.params), DEFAULT_PARAMS)

    def test_invalid_process_params_fall_back_to_safe_default(self):
        process = SimpleNamespace(process_param="not-json")
        self.assertEqual(
            ShenzhenAirGetHarScheduler._load_process_params(process),
            DEFAULT_PARAMS,
        )


class ShenzhenAirGetHarWorkerTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_job_without_queue_and_completes_on_success(self):
        worker = RPAWorker(robot_db_id=11, robot_name="测试机器人")
        task = SimpleNamespace(
            id=101,
            task_type=RPATaskType.SHENZHEN_AIR_GET_HAR.value,
            job_uuid="job-uuid",
            params=json.dumps(DEFAULT_PARAMS),
        )
        db_marker = object()
        create_job = AsyncMock(return_value={
            "works": [{"workUuid": "work-uuid"}],
        })
        query_status = AsyncMock(return_value={
            "records": [{
                "workUuid": "work-uuid",
                "status": 5,
                "statusDesc": "成功",
            }],
        })
        update_work_uuid = Mock(return_value=True)
        complete_task = Mock(return_value=True)

        with patch(
            "app.services.rpa_worker.rpa_service.create_shenzhen_air_get_har",
            new=create_job,
        ), patch(
            "app.services.rpa_worker.rpa_service.query_shenzhen_air_waybill_status",
            new=query_status,
        ), patch(
            "app.services.rpa_worker.rpa_task_service.update_task_work_uuid",
            new=update_work_uuid,
        ), patch(
            "app.services.rpa_worker.rpa_task_service.complete_task",
            new=complete_task,
        ):
            await worker._execute_shenzhen_air_get_har(db_marker, task)

        create_job.assert_awaited_once_with(
            system_url="https://www.kinggo.com/main",
            job_uuid="job-uuid",
        )
        update_work_uuid.assert_called_once_with(db_marker, 101, "work-uuid")
        query_status.assert_awaited_once_with(job_uuid="job-uuid")
        complete_task.assert_called_once_with(db_marker, 101, True)


class ShenzhenAirGetHarRPAServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_request_only_sends_system_url(self):
        response = Mock()
        response.raise_for_status = Mock()
        response.json.return_value = {
            "code": 0,
            "data": {"works": [{"workUuid": "work-uuid"}]},
        }
        client = MagicMock()
        client.post = AsyncMock(return_value=response)
        client_context = MagicMock()
        client_context.__aenter__ = AsyncMock(return_value=client)
        client_context.__aexit__ = AsyncMock(return_value=None)

        service = RPAService()
        with patch(
            "app.services.rpa_service.httpx.AsyncClient",
            return_value=client_context,
        ) as async_client:
            result = await service.create_shenzhen_air_get_har(
                system_url="https://www.kinggo.com/main",
                job_uuid="job-uuid",
            )

        async_client.assert_called_once_with(timeout=30.0)
        request_url = client.post.await_args.args[0]
        request_kwargs = client.post.await_args.kwargs
        self.assertTrue(request_url.endswith("/openAPI/v2/job/operation"))
        self.assertEqual(
            request_kwargs["json"],
            {
                "jobUuid": "job-uuid",
                "operation": 1,
                "inputParam": {
                    "system_url": "https://www.kinggo.com/main",
                },
            },
        )
        self.assertEqual(result, {"works": [{"workUuid": "work-uuid"}]})


if __name__ == "__main__":
    unittest.main()
