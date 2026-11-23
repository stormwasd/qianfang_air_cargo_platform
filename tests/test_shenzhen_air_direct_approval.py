import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

from app.services.shenzhen_air_direct_approval import (
    DIRECT_APPROVAL_SUCCESS_TYPES,
    ShenzhenAirDirectApprovalError,
    ShenzhenAirDirectApprovalService,
)


class _Response:
    status_code = 200
    content = b"PK\x03\x04sanitized-xlsx"


class _AsyncClient:
    requests = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, **kwargs):
        self.requests.append((url, kwargs))
        return _Response()


class DirectApprovalTests(unittest.IsolatedAsyncioTestCase):
    def test_build_query_body_contains_fixed_contract(self):
        body = ShenzhenAirDirectApprovalService.build_query_body("2026/10/19")
        query = parse_qs(body)
        self.assertEqual(query["depCode"], ["SZX"])
        self.assertEqual(query["flightDate"], ["2026-10-19"])
        self.assertEqual(query["agentCode"], ["SZXFDH"])
        self.assertEqual(query["orderType"], ["1"])
        self.assertEqual(query["ss"], ["1"])
        self.assertEqual(query["nn"], ["0"])

    def test_invalid_date_is_rejected(self):
        with self.assertRaises(ShenzhenAirDirectApprovalError):
            ShenzhenAirDirectApprovalService.build_query_body("2026-99-99")

    def test_wide_body_query_omits_order_type_and_keeps_contract_defaults(self):
        query = parse_qs(
            ShenzhenAirDirectApprovalService.build_query_body("2026-10-19", wide_body=True)
        )
        self.assertEqual(query["depCode"], ["SZX"])
        self.assertEqual(query["flightDate"], ["2026-10-19"])
        self.assertEqual(query["agentCode"], ["SZXFDH"])
        self.assertEqual(query["ss"], ["1"])
        self.assertEqual(query["nn"], ["0"])
        self.assertNotIn("orderType", query)

    async def test_download_writes_xlsx_to_generated_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ShenzhenAirDirectApprovalService(
                origin="http://127.0.0.1:4900/kinggo", output_dir=temp_dir
            )
            service._auth = AsyncMock(return_value=(
                "https://www.kinggo.com/agent_order_look/export/125?oOr6SIhu=test",
                {"Cookie": "sid=test"},
            ))
            _AsyncClient.requests = []
            with patch(
                "app.services.shenzhen_air_direct_approval.httpx.AsyncClient",
                _AsyncClient,
            ):
                output_path = await service.download_export(
                    datetime(2026, 10, 19), now=datetime(2026, 10, 19, 8, 0, 0)
                )

            self.assertTrue(output_path.exists())
            self.assertTrue(output_path.name.startswith("订舱查询导出_20261019_"))
            url, kwargs = _AsyncClient.requests[0]
            self.assertTrue(url.startswith("http://127.0.0.1:4900/kinggo/agent_order_look/export/125"))
            self.assertEqual(kwargs["headers"]["Cookie"], "sid=test")
            query = parse_qs(kwargs["content"])
            self.assertEqual(query["flightDate"], ["2026-10-19"])
            service._auth.assert_awaited_once_with(
                "/agent_order_look/export/125", kwargs["content"]
            )

    async def test_wide_body_export_uses_wide_endpoint_and_file_prefix(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = ShenzhenAirDirectApprovalService(
                origin="http://127.0.0.1:4900/kinggo", output_dir=temp_dir
            )
            service._auth = AsyncMock(return_value=(
                "https://www.kinggo.com/agent_order_look_wide/export/858?oOr6SIhu=test",
                {"Cookie": "sid=test"},
            ))
            _AsyncClient.requests = []
            with patch(
                "app.services.shenzhen_air_direct_approval.httpx.AsyncClient",
                _AsyncClient,
            ):
                output_path = await service.download_wide_body_export(
                    datetime(2026, 10, 19), now=datetime(2026, 10, 19, 8, 0, 0)
                )

            self.assertTrue(output_path.name.startswith("宽体机订舱查询与修改导出_20261019_"))
            url, kwargs = _AsyncClient.requests[0]
            self.assertTrue(url.startswith("http://127.0.0.1:4900/kinggo/agent_order_look_wide/export/858"))
            query = parse_qs(kwargs["content"])
            self.assertEqual(query["flightDate"], ["2026-10-19"])
            self.assertNotIn("orderType", query)
            service._auth.assert_awaited_once_with(
                "/agent_order_look_wide/export/858", kwargs["content"]
            )

    async def test_direct_scheduler_downloads_both_reports_for_today_and_tomorrow_without_rpa_tasks(self):
        from app.config import settings
        from app.services.shenzhen_air_approval_scheduler import ShenzhenAirApprovalScheduler

        service = ShenzhenAirApprovalScheduler()
        download_standard = AsyncMock(return_value=Path("standard.xlsx"))
        download_wide = AsyncMock(return_value=Path("wide.xlsx"))
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "direct"), \
             patch.object(settings, "RPA_QUEUE_ENABLED", True), \
             patch.object(service, "_cleanup_pending_direct_switch_tasks"), \
             patch(
                 "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service.download_export",
                 download_standard,
             ), \
             patch(
                 "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service.download_wide_body_export",
                 download_wide,
             ), \
             patch("app.services.tracking_execution_time.record_success_time", return_value=True) as record_success, \
             patch("app.services.shenzhen_air_approval_scheduler.get_china_now", return_value=datetime(2026, 10, 19, 8, 0, 0)):
            await service._enqueue_task()

        self.assertEqual(download_standard.await_count, 2)
        self.assertEqual(download_wide.await_count, 2)
        self.assertEqual(
            [call.args[0].strftime("%Y-%m-%d") for call in download_standard.await_args_list],
            ["2026-10-19", "2026-10-20"],
        )
        self.assertEqual(
            [call.args[0].strftime("%Y-%m-%d") for call in download_wide.await_args_list],
            ["2026-10-19", "2026-10-20"],
        )
        self.assertEqual(
            [call.args[0] for call in record_success.call_args_list],
            [DIRECT_APPROVAL_SUCCESS_TYPES[0]] * 2 + [DIRECT_APPROVAL_SUCCESS_TYPES[1]] * 2,
        )

    async def test_failed_direct_download_does_not_record_success(self):
        from app.services.shenzhen_air_approval_scheduler import ShenzhenAirApprovalScheduler

        download_standard = AsyncMock(side_effect=ShenzhenAirDirectApprovalError("request failed"))
        download_wide = AsyncMock(return_value=Path("wide.xlsx"))
        with patch(
            "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service.download_export",
            download_standard,
        ), patch(
            "app.services.shenzhen_air_direct_approval.shenzhen_air_direct_approval_service.download_wide_body_export",
            download_wide,
        ), patch(
            "app.services.tracking_execution_time.record_success_time",
            return_value=True,
        ) as record_success:
            await ShenzhenAirApprovalScheduler()._download_direct_exports()

        self.assertEqual(download_wide.await_count, 2)
        self.assertEqual(
            [call.args[0] for call in record_success.call_args_list],
            [DIRECT_APPROVAL_SUCCESS_TYPES[1]] * 2,
        )

    async def test_approval_list_uses_mode_specific_success_time(self):
        from app.api.shenzhen_air_approval import get_shenzhen_air_approvals
        from app.config import settings
        from app.models.rpa_task import RPATaskType
        from app.services.tracking_execution_time import RPA_EXECUTION_SUCCESS_TYPES

        db = MagicMock()
        db.query.return_value.count.return_value = 1
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(id=1, updated_at=datetime(2026, 10, 19, 14, 49))
        ]
        last_success = datetime(2026, 10, 20, 9, 15)
        with patch("app.services.rpa_task_service.rpa_task_service.get_last_success_time", return_value=last_success) as get_success:
            for mode, cabin_type, expected_type in (
                ("direct", 0, DIRECT_APPROVAL_SUCCESS_TYPES[0]),
                ("direct", 1, DIRECT_APPROVAL_SUCCESS_TYPES[1]),
                ("rpa", 0, RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.SHENZHEN_AIR_APPROVAL_DATA.value]),
                ("rpa", 1, RPA_EXECUTION_SUCCESS_TYPES[RPATaskType.SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY.value]),
            ):
                with self.subTest(mode=mode, cabin_type=cabin_type), patch.object(
                    settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", mode
                ):
                    result = await get_shenzhen_air_approvals(
                        flight_date_start=None, flight_date_end=None, flight_number=None,
                        cabin_type=cabin_type, page=1, pageSize=10, current_user=None, db=db,
                    )
                    self.assertEqual(result.data["data_update_time"], "2026-10-20 09:15")
                    self.assertEqual(get_success.call_args.args[1], expected_type)

    async def test_direct_list_does_not_fall_back_to_old_rpa_or_record_time(self):
        from app.api.shenzhen_air_approval import get_shenzhen_air_approvals
        from app.config import settings

        db = MagicMock()
        db.query.return_value.count.return_value = 1
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(id=1, updated_at=datetime(2026, 10, 19, 14, 49))
        ]
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "direct"), patch(
            "app.services.rpa_task_service.rpa_task_service.get_last_success_time", return_value=None
        ):
            result = await get_shenzhen_air_approvals(
                flight_date_start=None, flight_date_end=None, flight_number=None,
                cabin_type=0, page=1, pageSize=10, current_user=None, db=db,
            )
            self.assertIsNone(result.data["data_update_time"])

            db.query.return_value.count.return_value = 0
            db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
            result = await get_shenzhen_air_approvals(
                flight_date_start=None, flight_date_end=None, flight_number=None,
                cabin_type=0, page=1, pageSize=10, current_user=None, db=db,
            )
            self.assertEqual(result.data["items"], [])
            self.assertIsNone(result.data["data_update_time"])

    async def test_direct_list_exposes_success_time_for_empty_report(self):
        from app.api.shenzhen_air_approval import get_shenzhen_air_approvals
        from app.config import settings

        db = MagicMock()
        db.query.return_value.count.return_value = 0
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "direct"), patch(
            "app.services.rpa_task_service.rpa_task_service.get_last_success_time",
            return_value=datetime(2026, 10, 20, 9, 15),
        ):
            result = await get_shenzhen_air_approvals(
                flight_date_start=None, flight_date_end=None, flight_number=None,
                cabin_type=0, page=1, pageSize=10, current_user=None, db=db,
            )
            self.assertEqual(result.data["items"], [])
            self.assertEqual(result.data["data_update_time"], "2026-10-20 09:15")

    async def test_rpa_list_does_not_use_business_record_time(self):
        from app.api.shenzhen_air_approval import get_shenzhen_air_approvals
        from app.config import settings

        db = MagicMock()
        db.query.return_value.count.return_value = 1
        db.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [
            SimpleNamespace(id=1, updated_at=datetime(2026, 10, 19, 14, 49))
        ]
        with patch.object(settings, "SHENZHEN_AIR_APPROVAL_EXECUTION_MODE", "rpa"), patch(
            "app.services.rpa_task_service.rpa_task_service.get_last_success_time", return_value=None
        ):
            result = await get_shenzhen_air_approvals(
                flight_date_start=None, flight_date_end=None, flight_number=None,
                cabin_type=0, page=1, pageSize=10, current_user=None, db=db,
            )
            self.assertIsNone(result.data["data_update_time"])


if __name__ == "__main__":
    unittest.main()
