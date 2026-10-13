import json
import unittest
from pathlib import Path

from kinggo_token.generator import (
    decode_token, encode_payload, generate, inspect_token, length_bytes, read_length,
)

VECTORS = json.loads(Path(__file__).with_name("reference_vectors.json").read_text(encoding="utf-8"))


class NodeCompatibilityTests(unittest.TestCase):
    def test_har_samples_decrypt_and_reconstruct_exactly(self):
        for group in VECTORS:
            config = group["config"]
            for sample in group["samples"]:
                with self.subTest(source=group["source"], url=sample["url"]):
                    metadata = inspect_token(sample["token"], config)
                    self.assertEqual(metadata, sample["metadata"])
                    decoded = decode_token(sample["token"], config)
                    self.assertEqual(encode_payload(decoded["plain"], config), sample["token"])
                    result = generate(
                        sample["url"], config, timestamp_ms=metadata["timestampLow32"],
                        random_high=metadata["randomHigh"], flags=metadata["flags"],
                        environment_code=metadata["environmentCode"],
                        session_tag=metadata["sessionTag"], context_hex=metadata["contextHex"],
                    )
                    self.assertEqual(result["value"], sample["token"])

    def test_deterministic_generation_matches_node_including_urls(self):
        for group in VECTORS:
            for sample in group["generated"]:
                options = sample["options"]
                with self.subTest(source=group["source"], url=options["url"]):
                    actual = generate(options["url"], group["config"],
                                      timestamp_ms=options["timestampMs"], random_high=options["randomHigh"])
                    self.assertEqual(actual, sample["result"])

    def test_corruption_and_wrong_session_are_rejected(self):
        token = VECTORS[0]["samples"][0]["token"]
        config = VECTORS[0]["config"]
        character = "q" if token[20] != "q" else "r"
        with self.assertRaisesRegex(ValueError, "CRC32 mismatch"):
            decode_token(token[:20] + character + token[21:], config)
        with self.assertRaises(ValueError):
            decode_token(token, VECTORS[1]["config"])

    def test_new_tokens_roundtrip_and_time_wraps_at_uint32(self):
        config = VECTORS[0]["config"]
        tokens = {generate("/awb/sms_alert/getCountSms", config)["value"] for _ in range(10)}
        self.assertEqual(len(tokens), 10)
        for token in tokens:
            inspect_token(token, config)
        result = generate("/awb/sms_alert/getCountSms", config, timestamp_ms=2**32 + 1, random_high=0)
        self.assertEqual(inspect_token(result["value"], config)["timestampLow32"], 1)

    def test_protocol_length_boundaries(self):
        # Actual binary boundary vectors for the variable-length envelope encoding.
        cases = {127:"7f",128:"8080",16383:"bfff",16384:"c04000",
                 2097151:"dfffff",2097152:"e0200000",268435455:"efffffff",
                 268435456:"f010000000",4294967295:"f0ffffffff"}
        for length, expected in cases.items():
            with self.subTest(length=length):
                encoded = length_bytes(length)
                self.assertEqual(encoded.hex(), expected)
                self.assertEqual(read_length(encoded,0), (length,len(encoded)))

    def test_unsupported_urls_and_invalid_inputs_fail(self):
        config = VECTORS[0]["config"]
        for url in ["https://example.com/api", "/example?name=%E4%B8%AD", "/example?tilde=~"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                generate(url,config)
        with self.assertRaises(ValueError):
            generate("/awb/sms_alert/getCountSms",config,random_high=1000000)


if __name__ == "__main__":
    unittest.main()
