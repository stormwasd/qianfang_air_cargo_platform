import asyncio
import importlib
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings, settings
from app.services.wechat_alert_config import (
    WechatAlertScene,
    is_wechat_alert_enabled,
    should_send_wechat_alert,
)


class WechatAlertConfigTests(unittest.TestCase):
    SCENE_SWITCHES = (
        (
            WechatAlertScene.SHENZHEN_AIR_APPROVAL,
            "WECHAT_ALERT_SHENZHEN_AIR_APPROVAL_ENABLED",
        ),
        (
            WechatAlertScene.SHENZHEN_AIR_DEPARTURE,
            "WECHAT_ALERT_SHENZHEN_AIR_DEPARTURE_ENABLED",
        ),
        (
            WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE,
            "WECHAT_ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_ENABLED",
        ),
        (
            WechatAlertScene.SHENZHEN_AIR_LOADING,
            "WECHAT_ALERT_SHENZHEN_AIR_LOADING_ENABLED",
        ),
        (
            WechatAlertScene.CHINA_SOUTHERN_AIR_LOADING,
            "WECHAT_ALERT_CHINA_SOUTHERN_AIR_LOADING_ENABLED",
        ),
        (
            WechatAlertScene.SHENZHEN_AIR_DEPARTURE_STATUS,
            "WECHAT_ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_ENABLED",
        ),
        (
            WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE_STATUS,
            "WECHAT_ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_ENABLED",
        ),
    )

    def test_all_switches_default_to_enabled_for_backward_compatibility(self):
        default_settings = Settings(_env_file=None)
        self.assertTrue(default_settings.WECHAT_ALERT_ENABLED)
        for _, switch_name in self.SCENE_SWITCHES:
            self.assertTrue(getattr(default_settings, switch_name), switch_name)

    def test_master_switch_disables_every_scene(self):
        with patch.object(settings, "WECHAT_ALERT_ENABLED", False):
            for scene, _ in self.SCENE_SWITCHES:
                self.assertFalse(is_wechat_alert_enabled(scene), scene)

    def test_each_scene_switch_only_controls_its_scene(self):
        with patch.object(settings, "WECHAT_ALERT_ENABLED", True):
            for scene, switch_name in self.SCENE_SWITCHES:
                with self.subTest(scene=scene):
                    with patch.object(settings, switch_name, False):
                        self.assertFalse(is_wechat_alert_enabled(scene))

                    with patch.object(settings, switch_name, True):
                        self.assertTrue(is_wechat_alert_enabled(scene))

    def test_send_guard_returns_false_when_master_switch_is_off(self):
        with patch.object(settings, "WECHAT_ALERT_ENABLED", False):
            self.assertFalse(
                should_send_wechat_alert(
                    WechatAlertScene.SHENZHEN_AIR_APPROVAL,
                    log_prefix="[Test]",
                )
            )

    def test_every_sender_is_wired_to_its_scene_switch(self):
        project_root = Path(__file__).resolve().parents[1]
        sender_scenes = {
            "app/services/shenzhen_air_approval_alert.py":
                "WechatAlertScene.SHENZHEN_AIR_APPROVAL",
            "app/services/shenzhen_air_departure_alert.py":
                "WechatAlertScene.SHENZHEN_AIR_DEPARTURE",
            "app/services/csa_departure_alert.py":
                "WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE",
            "app/services/shenzhen_air_loading_alert.py":
                "WechatAlertScene.SHENZHEN_AIR_LOADING",
            "app/services/csa_loading_alert.py":
                "WechatAlertScene.CHINA_SOUTHERN_AIR_LOADING",
            "app/services/shenzhen_air_departure_status_alert.py":
                "WechatAlertScene.SHENZHEN_AIR_DEPARTURE_STATUS",
            "app/services/csa_departure_status_alert.py":
                "WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE_STATUS",
        }

        for relative_path, scene_name in sender_scenes.items():
            with self.subTest(relative_path=relative_path):
                source = (project_root / relative_path).read_text(encoding="utf-8")
                self.assertIn("should_send_wechat_alert(", source)
                self.assertIn(scene_name, source)

    def test_disabled_guard_prevents_http_for_every_sender(self):
        sender_specs = (
            (
                "app.services.shenzhen_air_approval_alert",
                "shenzhen_air_approval_alert",
                "_send_wechat_message",
            ),
            (
                "app.services.shenzhen_air_departure_alert",
                "shenzhen_air_departure_alert_manager",
                "_send_wechat_msg",
            ),
            (
                "app.services.csa_departure_alert",
                "csa_departure_alert_manager",
                "_send_wechat_msg",
            ),
            (
                "app.services.shenzhen_air_loading_alert",
                "shenzhen_air_loading_alert_manager",
                "_send_wechat_msg",
            ),
            (
                "app.services.csa_loading_alert",
                "csa_loading_alert_manager",
                "_send_wechat_msg",
            ),
            (
                "app.services.shenzhen_air_departure_status_alert",
                "shenzhen_air_departure_status_alert",
                "_send_wechat_message",
            ),
            (
                "app.services.csa_departure_status_alert",
                "csa_departure_status_alert",
                "_send_wechat_message",
            ),
        )

        for module_name, service_name, method_name in sender_specs:
            with self.subTest(module_name=module_name):
                module = importlib.import_module(module_name)
                service = getattr(module, service_name)
                send_method = getattr(service, method_name)
                with (
                    patch.object(
                        module,
                        "should_send_wechat_alert",
                        return_value=False,
                    ),
                    patch.object(module.httpx, "AsyncClient") as http_client,
                ):
                    asyncio.run(send_method("test message"))
                    http_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
