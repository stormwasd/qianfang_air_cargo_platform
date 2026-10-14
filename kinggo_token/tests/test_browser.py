"""Cross-platform browser selection and actionable CLI startup errors."""

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from kinggo_token.__main__ import main
from kinggo_token.har import _launch_error, _launch_options, check_browser, replay_offline


class BrowserSelectionTests(unittest.TestCase):
    def test_defaults_and_explicit_browser_choices(self):
        with patch.dict(os.environ, {}, clear=True):
            for platform, expected in [("win32", "msedge"), ("linux", None), ("darwin", None)]:
                with self.subTest(platform=platform), patch("kinggo_token.har.sys.platform", platform):
                    self.assertEqual(_launch_options("auto", None).get("channel"), expected)
                    self.assertEqual(_launch_options(None, None), {"headless": True})
                    self.assertEqual(_launch_options("msedge", None), {"headless": True, "channel": "msedge"})

    def test_executable_overrides_and_environment_precedence(self):
        with patch.dict(os.environ, {"EDGE_EXECUTABLE": "/opt/custom-edge"}):
            self.assertEqual(_launch_options("auto", None),
                             {"headless": True, "executable_path": "/opt/custom-edge"})
            self.assertEqual(_launch_options("msedge", "/opt/explicit-browser"),
                             {"headless": True, "executable_path": "/opt/explicit-browser"})

    def test_launch_errors_identify_the_selected_browser(self):
        self.assertIn("install --with-deps chromium", _launch_error({"headless": True}, RuntimeError("missing")))
        self.assertIn("--browser chromium", _launch_error({"channel": "msedge"}, RuntimeError("missing")))
        self.assertIn("EDGE_EXECUTABLE", _launch_error({"executable_path": "/bad"}, RuntimeError("missing")))

    def test_cli_passes_browser_selection_and_preserves_config_on_failure(self):
        for arguments, expected in [([], "auto"), (["--browser", "chromium"], None),
                                    (["--browser", "msedge"], "msedge")]:
            with self.subTest(arguments=arguments), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "config.json"
                output.write_text("previous config", encoding="utf-8")
                argv = ["kinggo_token", "extract", "capture.har", "/awb/sms_alert/getCountSms",
                        "--output", str(output), *arguments]
                stream = io.StringIO()
                with patch("sys.argv", argv), contextlib.redirect_stderr(stream), patch(
                    "kinggo_token.har.replay_offline", new_callable=AsyncMock,
                    side_effect=RuntimeError("Browser launch failed"),
                ) as replay:
                    self.assertEqual(main(), 1)
                self.assertEqual(replay.call_args.kwargs["channel"], expected)
                self.assertIn("Error: Browser launch failed", stream.getvalue())
                self.assertNotIn("Traceback", stream.getvalue())
                self.assertEqual(output.read_text(encoding="utf-8"), "previous config")
                self.assertFalse(output.with_suffix(".json.tmp").exists())


class InvalidUrlTests(unittest.IsolatedAsyncioTestCase):
    async def test_embedded_newline_is_rejected_before_har_or_browser_access(self):
        with self.assertRaisesRegex(ValueError, "newlines"):
            await replay_offline("nonexistent.har", "/ \nawb/sms_alert/getCountSms")


class BrowserSmokeCheckTests(unittest.IsolatedAsyncioTestCase):
    async def test_smoke_check_closes_browser_on_success_and_failure(self):
        for javascript_result in [2, 0]:
            with self.subTest(javascript_result=javascript_result):
                page = SimpleNamespace(evaluate=AsyncMock(return_value=javascript_result))
                browser = SimpleNamespace(new_page=AsyncMock(return_value=page),
                                          close=AsyncMock(), version="test-version")
                playwright = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))
                manager = AsyncMock()
                manager.__aenter__.return_value = playwright
                with patch("playwright.async_api.async_playwright", return_value=manager), patch.dict(os.environ, {}, clear=True):
                    if javascript_result == 2:
                        self.assertEqual(await check_browser(channel=None),
                                         {"status": "PASS", "headless": True, "browserVersion": "test-version"})
                    else:
                        with self.assertRaisesRegex(RuntimeError, "smoke check failed"):
                            await check_browser(channel=None)
                playwright.chromium.launch.assert_awaited_once_with(headless=True)
                browser.close.assert_awaited_once()

    async def test_missing_browser_provides_install_hint(self):
        from playwright.async_api import Error

        playwright = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(side_effect=Error("missing"))))
        manager = AsyncMock()
        manager.__aenter__.return_value = playwright
        with patch("playwright.async_api.async_playwright", return_value=manager), patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "install --with-deps chromium"):
                await check_browser(channel=None)


if __name__ == "__main__":
    unittest.main()
