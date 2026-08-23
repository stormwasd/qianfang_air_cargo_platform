import unittest
from unittest.mock import patch

from app.config import settings
from app.services.document_print_service import is_auto_print_after_waybill_enabled


class AutoPrintAfterWaybillConfigTests(unittest.TestCase):
    def test_defaults_keep_existing_auto_print_behavior(self):
        self.assertTrue(
            settings.RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED
        )
        self.assertTrue(
            settings.RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED
        )

    def test_shenzhen_air_aliases_follow_shenzhen_switch(self):
        with patch.object(
            settings,
            "RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            for airline in ("1", "深圳航空", "shenzhen_air"):
                with self.subTest(airline=airline):
                    self.assertFalse(is_auto_print_after_waybill_enabled(airline))

    def test_china_southern_air_aliases_follow_csa_switch(self):
        with patch.object(
            settings,
            "RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED",
            False,
        ):
            for airline in ("2", "南方航空", "china_southern_air"):
                with self.subTest(airline=airline):
                    self.assertFalse(is_auto_print_after_waybill_enabled(airline))

    def test_airline_switches_are_independent(self):
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

    def test_unknown_airline_does_not_auto_print(self):
        self.assertFalse(is_auto_print_after_waybill_enabled("unknown"))


if __name__ == "__main__":
    unittest.main()
