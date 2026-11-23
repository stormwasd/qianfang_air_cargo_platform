import unittest
from unittest.mock import patch

from app.config import settings
from app.services.document_print_service import (
    is_auto_document_after_waybill_enabled,
    is_auto_print_after_waybill_enabled,
    is_post_waybill_automation_enabled,
    prepare_print_tasks,
)


class AutoPrintAfterWaybillConfigTests(unittest.TestCase):
    def test_defaults_keep_existing_auto_print_behavior(self):
        self.assertTrue(is_auto_document_after_waybill_enabled("1"))
        self.assertTrue(is_auto_document_after_waybill_enabled("2"))
        self.assertTrue(
            settings.RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED
        )
        self.assertTrue(
            settings.RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED
        )

    def test_shenzhen_air_print_aliases_follow_shenzhen_switch(self):
        with patch.object(
            settings,
            "RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            for airline in ("1", "深圳航空", "shenzhen_air"):
                with self.subTest(airline=airline):
                    self.assertFalse(is_auto_print_after_waybill_enabled(airline))

    def test_china_southern_air_print_aliases_follow_csa_switch(self):
        with patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            for airline in ("2", "南方航空", "china_southern_air"):
                with self.subTest(airline=airline):
                    self.assertFalse(is_auto_print_after_waybill_enabled(airline))

    def test_airline_print_switches_are_independent(self):
        with patch.object(
            settings,
            "RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ), patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            True,
        ):
            self.assertFalse(is_auto_print_after_waybill_enabled("1"))
            self.assertTrue(is_auto_print_after_waybill_enabled("2"))

    def test_document_switch_falls_back_to_legacy_print_switch(self):
        with patch.object(
            settings,
            "RPA_SHENZHEN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED",
            None,
        ), patch.object(
            settings,
            "RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            self.assertFalse(is_auto_document_after_waybill_enabled("1"))
            self.assertFalse(is_post_waybill_automation_enabled("1"))

    def test_document_and_print_switches_are_independent(self):
        with patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED",
            True,
        ), patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            self.assertTrue(is_auto_document_after_waybill_enabled("2"))
            self.assertFalse(is_auto_print_after_waybill_enabled("2"))
            self.assertTrue(is_post_waybill_automation_enabled("2"))

        with patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED",
            False,
        ), patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            True,
        ):
            self.assertFalse(is_auto_document_after_waybill_enabled("2"))
            self.assertTrue(is_auto_print_after_waybill_enabled("2"))
            self.assertTrue(is_post_waybill_automation_enabled("2"))

    def test_unknown_airline_does_not_auto_print(self):
        self.assertFalse(is_auto_document_after_waybill_enabled("unknown"))
        self.assertFalse(is_auto_print_after_waybill_enabled("unknown"))
        self.assertFalse(is_post_waybill_automation_enabled("unknown"))

    def test_print_check_uses_print_switch_only(self):
        with patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED",
            True,
        ), patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            self.assertFalse(is_auto_print_after_waybill_enabled("2"))

    def test_print_without_document_generation_excludes_file_tasks(self):
        business_config = {
            "shenzhen_air": {
                "print": {
                    "printer_config": [
                        {"document_type": "标签单", "printer_name": "label"},
                        {"document_type": "航司货运主单", "printer_name": "main"},
                    ]
                }
            }
        }
        with patch(
            "app.services.document_print_service.list_waybill_files"
        ) as list_files:
            result = prepare_print_tasks(
                waybill_id=1,
                waybill_number="953-12345678",
                airline="1",
                business_config=business_config,
                include_document_files=False,
            )

        list_files.assert_not_called()
        self.assertEqual(
            [task["type"] for task in result["tasks"]],
            ["shenzhen_air_main_waybill_print"],
        )


if __name__ == "__main__":
    unittest.main()
