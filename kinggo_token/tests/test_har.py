"""Opt-in integration: original browser scripts versus the Python generator."""

import json
import os
import tempfile
import unittest
from pathlib import Path

from kinggo_token import generate
from kinggo_token.har import replay_offline, verify_har

HAR_PATHS = [path for path in os.environ.get("KINGGO_TEST_HARS", "").split(os.pathsep) if path]


@unittest.skipUnless(HAR_PATHS, "Set KINGGO_TEST_HARS to local HAR paths")
class OfflineReplayTests(unittest.IsolatedAsyncioTestCase):
    async def test_extract_reproduce_browser_token_and_all_har_samples(self):
        for path in HAR_PATHS:
            with self.subTest(har=path):
                # Include non-text base64 content as found in normal browser HARs.
                har = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                for entry in har["log"]["entries"]:
                    if "/awb/sms_alert/getCountSms" in entry["request"]["url"]:
                        entry["request"]["headers"].append({"name": "Cookie", "value": "sid=synthetic-test-only"})
                har["log"]["entries"].append({
                    "request": {"url": "https://www.kinggo.com/test-image.png"},
                    "response": {"content": {"encoding": "base64", "text": "/wAB"}},
                })
                with tempfile.TemporaryDirectory() as directory:
                    augmented = Path(directory) / "capture.har"
                    augmented.write_text(json.dumps(har), encoding="utf-8")
                    result = await replay_offline(augmented, "/awb/sms_alert/getCountSms")
                payload = result["payload"]
                self.assertEqual(result["cookie"], "sid=synthetic-test-only")
                self.assertEqual(result["config"]["cookie"], result["cookie"])
                regenerated = generate(
                    result["url"], result["config"], timestamp_ms=payload["timestampLow32"],
                    random_high=payload["randomHigh"], flags=payload["flags"],
                    environment_code=payload["environmentCode"],
                    session_tag=payload["sessionTag"], context_hex=payload["contextHex"],
                )
                self.assertEqual(regenerated["value"], result["value"])
                self.assertEqual(regenerated["cookie"], result["cookie"])
                self.assertGreater(verify_har(path, result["config"]), 0)


if __name__ == "__main__":
    unittest.main()
