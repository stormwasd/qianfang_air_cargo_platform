"""Cookie capture selection, persistence and separation from token generation."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from kinggo_token import generate, load_config
from kinggo_token.__main__ import main
from kinggo_token.har import _select_cookie, extract_cookie

TARGET = "/awb/sms_alert/getCountSms"


def entry(cookie=None, *, url=TARGET, method="POST", timestamp="2026-10-14T10:00:00Z", page="page-1"):
    request = {"url": "https://www.kinggo.com" + url, "method": method, "headers": [], "cookies": []}
    if cookie is not None:
        request["headers"].append({"name": "cOoKiE", "value": cookie})
    return {"request": request, "startedDateTime": timestamp, "pageref": page,
            "response": {"content": {}, "headers": [{"name": "Set-Cookie", "value": "responseOnly=ignore; Path=/"}]}}


class CookieTests(unittest.TestCase):
    def test_exact_header_is_preserved_and_latest_target_selected(self):
        latest = entry("sid=new; SameSite=lax; escaped=a%2Fb; sid=second", timestamp="2026-10-14T10:01:00Z")
        latest["request"]["cookies"] = [{"name": "sid", "value": "wrong"}]
        result = _select_cookie([latest, entry("sid=old")], TARGET + "?oOr6SIhu=old", "post")
        self.assertEqual(result["cookie"], "sid=new; SameSite=lax; escaped=a%2Fb; sid=second")
        self.assertEqual(result["cookieSource"]["field"], "request.headers.Cookie")
        self.assertEqual(result["cookieSource"]["match"], "target")

    def test_request_cookie_array_keeps_empty_values_and_duplicate_names(self):
        captured = entry()
        captured["request"]["cookies"] = [
            {"name": "sid", "value": "a=b", "httpOnly": True, "path": "/"},
            {"name": "empty", "value": ""}, {"name": "sid", "value": "path-specific"},
        ]
        result = _select_cookie([captured], TARGET, "POST")
        self.assertEqual(result["cookie"], "sid=a=b; empty=; sid=path-specific")
        self.assertEqual(result["cookieSource"]["field"], "request.cookies")

    def test_missing_cookie_does_not_reuse_old_value_or_response_cookie(self):
        result = _select_cookie([entry("sid=old"), entry(timestamp="2026-10-14T10:01:00Z")], TARGET, "POST")
        self.assertEqual(result["cookie"], "")
        self.assertEqual(result["cookieStatus"], "missing")
        with self.assertRaisesRegex(ValueError, "sensitive data"):
            _select_cookie([entry()], TARGET, "POST", require_cookie=True)

    def test_fallback_is_one_business_request_with_provenance(self):
        other = entry("sid=business", url="/awb/query/index/119")
        asset = entry("sid=asset", url="/static/image.png", timestamp="2026-10-14T10:10:00Z")
        foreign = entry("sid=foreign")
        foreign["request"]["url"] = "https://example.com" + TARGET
        result = _select_cookie([other, asset, foreign], TARGET, "POST")
        self.assertEqual(result["cookie"], "sid=business")
        self.assertIn("another /awb/ request", result["cookieWarning"])

    def test_replay_page_filter_does_not_mix_page_sessions(self):
        result = _select_cookie([entry("sid=one"), entry("sid=two", page="page-2")],
                                TARGET, "POST", page_ref="page-1")
        self.assertEqual(result["cookie"], "sid=one")

    def test_invalid_header_and_cookie_array_values_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "control character"):
            _select_cookie([entry("sid=ok\r\nInjected: yes")], TARGET, "POST")
        malformed = entry()
        malformed["request"]["cookies"] = [{"name": "sid", "value": "a; injected=b"}]
        with self.assertRaises(ValueError):
            _select_cookie([malformed], TARGET, "POST")

    def test_cli_extract_saves_cookie_and_generate_returns_it_without_changing_token(self):
        vectors = json.loads(Path(__file__).with_name("reference_vectors.json").read_text(encoding="utf-8"))
        old_config = vectors[0]["config"]
        fields = _select_cookie([entry("sid=test-only; cargo_agent=test-agent")], TARGET, "POST")
        config = {**old_config, **fields}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            argv = ["kinggo_token", "extract", "capture.har", TARGET, "--output", str(path), "--require-cookie"]
            stream = io.StringIO()
            with patch("sys.argv", argv), contextlib.redirect_stdout(stream), patch(
                "kinggo_token.har.replay_offline", new_callable=AsyncMock,
                return_value={"config": config, **fields},
            ) as replay:
                self.assertEqual(main(), 0)
            self.assertTrue(replay.call_args.kwargs["require_cookie"])
            self.assertEqual(json.loads(stream.getvalue())["cookie"], fields["cookie"])
            options = {"timestamp_ms": 1791949607540, "random_high": 123456}
            previous = generate(TARGET, old_config, **options)
            actual = generate(TARGET, load_config(path), **options)
            for key, value in previous.items():
                self.assertEqual(actual[key], value)
            self.assertEqual(actual["cookie"], fields["cookie"])

    def test_cookie_only_api_and_cli_need_no_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            har = Path(directory) / "capture.har"
            har.write_text(json.dumps({"log": {"entries": [entry("sid=test-only")]}}), encoding="utf-8")
            self.assertEqual(extract_cookie(har, TARGET)["cookie"], "sid=test-only")
            with patch("sys.argv", ["kinggo_token", "cookies", str(har), TARGET]), contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(), 0)
            self.assertEqual(json.loads(out.getvalue())["cookie"], "sid=test-only")

    def test_required_cookie_failure_preserves_existing_config_before_browser_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            har = Path(directory) / "capture.har"
            har.write_text(json.dumps({"log": {"entries": [entry()]}}), encoding="utf-8")
            output = Path(directory) / "config.json"
            output.write_text("old-config", encoding="utf-8")
            argv = ["kinggo_token", "extract", str(har), TARGET, "--output", str(output), "--require-cookie"]
            # Minimal valid script skeleton lets the real replay API reach its pre-browser check.
            pages = [entry(url="/main", method="GET"), entry(url="/loader.js"), entry(url="/engine.js"), entry()]
            pages[0]["response"]["content"] = {"text": '<script src="/loader.js" r="m"></script>'}
            pages[1]["response"]["content"] = {"text": 'document.write("<script src=\'/engine.js\'>")'}
            pages[2]["response"]["content"] = {"text": "engine"}
            with patch("kinggo_token.har._entries", return_value=pages), patch(
                "kinggo_token.har._launch_browser", new_callable=AsyncMock,
            ) as launch, patch("sys.argv", argv), contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(), 1)
                self.assertIn("No Cookie", err.getvalue())
                launch.assert_not_awaited()
            self.assertEqual(output.read_text(encoding="utf-8"), "old-config")


if __name__ == "__main__":
    unittest.main()
