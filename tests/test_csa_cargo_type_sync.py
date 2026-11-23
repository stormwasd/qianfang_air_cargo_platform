import asyncio
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.models.nanhang_token import NanHangToken
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirService,
    ChinaSouthernAirServiceError,
)
from app.services.csa_cargo_type_sync import (
    CARGO_TYPE_DICT_TYPE,
    CsaCargoTypeSyncScheduler,
    CsaCargoTypeSyncError,
    _load_latest_nanhang_token,
    replace_cargo_type_dict_options,
)


class ShipmentTypeResponseTests(unittest.TestCase):
    def test_normalizes_all_names_and_keeps_duplicate_codes(self):
        result = ChinaSouthernAirService.normalize_shipment_types(
            {
                "code": "0000",
                "message": "服务调用成功",
                "result": [
                    {"shipmentTypeName": "贵重物品", "shipmentType": "3001"},
                    {"shipmentTypeName": "活体动物", "shipmentType": "3001"},
                    {"shipmentTypeName": "普通货物", "shipmentType": "3006"},
                ],
            }
        )

        self.assertEqual(
            result,
            [
                {"label": "贵重物品", "value": "3001"},
                {"label": "活体动物", "value": "3001"},
                {"label": "普通货物", "value": "3006"},
            ],
        )

    def test_rejects_empty_success_result(self):
        with self.assertRaises(ChinaSouthernAirServiceError):
            ChinaSouthernAirService.normalize_shipment_types(
                {"code": "0000", "result": []}
            )

    def test_identifies_upstream_token_rejection(self):
        with self.assertRaisesRegex(
            ChinaSouthernAirServiceError,
            "南航接口拒绝Token：获取Token为空，可能已过期或失效",
        ):
            ChinaSouthernAirService.normalize_shipment_types(
                {
                    "code": "0001",
                    "message": "服务内部异常",
                    "detailedMessage": {"message": "获取Token为空"},
                    "result": None,
                }
            )

    def test_query_uses_cleaned_token_as_x_customs_user(self):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "code": "0000",
                    "result": [
                        {"shipmentTypeName": "普通货物", "shipmentType": "3006"}
                    ],
                }

        class FakeAsyncClient:
            def __init__(self, **kwargs):
                captured["client_kwargs"] = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, traceback):
                return False

            async def post(self, url, **kwargs):
                captured["url"] = url
                captured["request_kwargs"] = kwargs
                return FakeResponse()

        service = ChinaSouthernAirService()
        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            FakeAsyncClient,
        ):
            result = asyncio.run(
                service.query_shipment_types(token=' "token-value\\r\\n" ')
            )

        self.assertEqual(result, [{"label": "普通货物", "value": "3006"}])
        self.assertEqual(
            captured["request_kwargs"]["headers"]["x-customs-user"],
            "token-value",
        )
        self.assertEqual(
            captured["request_kwargs"]["headers"]["x-customs-userid"],
            "SZXFED",
        )
        self.assertEqual(captured["request_kwargs"]["content"], b"")


class CargoTypeDictionaryReplacementTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        DictType.__table__.create(self.engine)
        DictOption.__table__.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()

        self.dict_type = DictType(
            id=1,
            name="南航货物类型",
            type=CARGO_TYPE_DICT_TYPE,
            status=1,
        )
        self.db.add(self.dict_type)
        self.db.add(
            DictOption(
                id=11,
                dict_type_id=1,
                label="旧货物类型",
                value="old",
                status=1,
            )
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_replaces_options_and_preserves_shared_values(self):
        count = replace_cargo_type_dict_options(
            self.db,
            [
                {"label": "贵重物品", "value": "3001"},
                {"label": "活体动物", "value": "3001"},
                {"label": "普通货物", "value": "3006"},
            ],
        )
        self.db.commit()

        options = (
            self.db.query(DictOption)
            .filter(DictOption.dict_type_id == self.dict_type.id)
            .order_by(DictOption.label.asc())
            .all()
        )
        self.assertEqual(count, 3)
        self.assertEqual(
            [(item.label, item.value, item.status) for item in options],
            [
                ("普通货物", "3006", 1),
                ("活体动物", "3001", 1),
                ("贵重物品", "3001", 1),
            ],
        )

    def test_empty_options_do_not_delete_existing_dictionary(self):
        with self.assertRaises(CsaCargoTypeSyncError):
            replace_cargo_type_dict_options(self.db, [])

        existing = self.db.query(DictOption).filter(DictOption.id == 11).one()
        self.assertEqual(existing.label, "旧货物类型")


class NanHangTokenSelectionTests(unittest.TestCase):
    def test_uses_latest_non_empty_token(self):
        engine = create_engine("sqlite:///:memory:")
        NanHangToken.__table__.create(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        db.add_all(
            [
                NanHangToken(
                    id=1,
                    robot_id=1,
                    token="older-token",
                    created_at=datetime(2026, 8, 20, 10, 0, 0),
                    updated_at=datetime(2026, 8, 20, 10, 0, 0),
                ),
                NanHangToken(
                    id=2,
                    robot_id=2,
                    token="latest-token",
                    created_at=datetime(2026, 8, 21, 10, 0, 0),
                    updated_at=datetime(2026, 8, 21, 10, 0, 0),
                ),
            ]
        )
        db.commit()
        db.close()

        try:
            with patch(
                "app.services.csa_cargo_type_sync.SessionLocal",
                TestSession,
            ):
                self.assertEqual(_load_latest_nanhang_token(), "latest-token")
        finally:
            engine.dispose()

    def test_reports_no_locally_usable_token(self):
        engine = create_engine("sqlite:///:memory:")
        NanHangToken.__table__.create(engine)
        TestSession = sessionmaker(bind=engine)
        db = TestSession()
        db.add(
            NanHangToken(
                id=1,
                robot_id=1,
                token=" \\r\\n ",
                created_at=datetime(2026, 8, 21, 10, 0, 0),
                updated_at=datetime(2026, 8, 21, 10, 0, 0),
            )
        )
        db.commit()
        db.close()

        try:
            with patch(
                "app.services.csa_cargo_type_sync.SessionLocal",
                TestSession,
            ):
                with self.assertRaisesRegex(
                    CsaCargoTypeSyncError,
                    "nanhang_token 中没有可用Token",
                ):
                    _load_latest_nanhang_token()
        finally:
            engine.dispose()


class CargoTypeSyncSchedulerLoggingTests(unittest.IsolatedAsyncioTestCase):
    async def test_logs_each_attempt_and_success_schedule(self):
        scheduler = CsaCargoTypeSyncScheduler()

        async def stop_after_first_run(_delay_seconds):
            scheduler._stop_event.set()

        with patch(
            "app.services.csa_cargo_type_sync.sync_csa_cargo_types_once",
            AsyncMock(return_value=3),
        ), patch.object(
            scheduler,
            "_wait_until_next_run",
            side_effect=stop_after_first_run,
        ), self.assertLogs("uvicorn.error", level="INFO") as captured:
            await scheduler._async_main()

        logs = "\n".join(captured.output)
        self.assertIn("开始同步南航货物类型", logs)
        self.assertIn("同步成功", logs)
        self.assertIn("共写入 3 个货物类型", logs)

    async def test_logs_failure_and_retry_schedule(self):
        scheduler = CsaCargoTypeSyncScheduler()

        async def stop_after_first_run(_delay_seconds):
            scheduler._stop_event.set()

        with patch(
            "app.services.csa_cargo_type_sync.sync_csa_cargo_types_once",
            AsyncMock(side_effect=CsaCargoTypeSyncError("测试失败")),
        ), patch.object(
            scheduler,
            "_wait_until_next_run",
            side_effect=stop_after_first_run,
        ), self.assertLogs("uvicorn.error", level="INFO") as captured:
            await scheduler._async_main()

        logs = "\n".join(captured.output)
        self.assertIn("开始同步南航货物类型", logs)
        self.assertIn("同步未完成：测试失败", logs)
        self.assertIn("秒后重试", logs)


if __name__ == "__main__":
    unittest.main()
