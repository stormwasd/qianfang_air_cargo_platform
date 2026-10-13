"""Byte-compatible port of the verified generate.cjs implementation."""

from __future__ import annotations

import base64
import json
import re
import secrets
import struct
import time
import zlib
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

STANDARD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
ORIGIN = "https://www.kinggo.com"
Config = Mapping[str, Any]


def load_config(path: str | Path) -> dict[str, Any]:
    """Read an extracted config; never fall back to a stale captured session."""
    with Path(path).open(encoding="utf-8-sig") as handle:
        config = json.load(handle)
    _crypto_config(config)
    if len(bytes.fromhex(config["challengeHex"])) < 16:
        raise ValueError("challengeHex must contain at least 16 bytes")
    return config


def _crypto_config(config: Config) -> tuple[bytes, str, str]:
    key = bytes.fromhex(config["keyHex"])
    alphabet = config["alphabet"]
    version = config["version"]
    if len(key) != 16:
        raise ValueError("keyHex must contain a 16-byte AES key")
    if len(alphabet) != 64 or len(set(alphabet)) != 64:
        raise ValueError("alphabet must contain 64 distinct characters")
    if not isinstance(version, str) or not version:
        raise ValueError("version must be a non-empty string")
    return key, alphabet, version


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def _uint32(value: int) -> bytes:
    return struct.pack(">I", value & 0xFFFFFFFF)


def length_bytes(value: int) -> bytes:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise ValueError("Invalid length")
    if value <= 127:
        return bytes([value])
    if value <= 16383:
        return bytes([(value >> 8) | 128, value & 255])
    if value <= 2097151:
        return bytes([(value >> 16) | 192, (value >> 8) & 255, value & 255])
    if value <= 268435455:
        return bytes([(value >> 24) | 224, (value >> 16) & 255, (value >> 8) & 255, value & 255])
    return b"\xf0" + _uint32(value)


def read_length(data: bytes, position: int) -> tuple[int, int]:
    if position >= len(data):
        raise ValueError("Truncated length")
    first = data[position]
    position += 1
    if first < 128:
        return first, position
    count = 1 if first < 192 else 2 if first < 224 else 3 if first < 240 else 4
    if position + count > len(data):
        raise ValueError("Truncated length")
    value = first & {1: 63, 2: 31, 3: 15, 4: 0}[count]
    for byte in data[position:position + count]:
        value = value * 256 + byte
    return value, position + count


def _sized(data: bytes) -> bytes:
    return length_bytes(len(data)) + data


def _xor_prefix(data: bytes, challenge: bytes) -> bytes:
    if len(data) < 16:
        return data
    if len(challenge) < 16:
        raise ValueError("Challenge is too short")
    return bytes(data[i] ^ challenge[i] for i in range(16)) + data[16:]


def encode_payload(payload: bytes, config: Config) -> str:
    key, alphabet, version = _crypto_config(config)
    challenge = bytes.fromhex(config["challengeHex"])
    mixed = _xor_prefix(bytes(payload), challenge)
    padder = padding.PKCS7(128).padder()
    padded = padder.update(mixed) + padder.finalize()
    encryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    envelope = b"\x01\x00" + _sized(challenge) + _sized(ciphertext)
    binary = _uint32(crc32(envelope)) + envelope
    encoded = base64.b64encode(binary).decode("ascii").rstrip("=")
    return version + encoded.translate(str.maketrans(STANDARD_ALPHABET, alphabet))


def decode_token(token: str, config: Config) -> dict[str, Any]:
    key, alphabet, version = _crypto_config(config)
    if not token.startswith(version):
        raise ValueError("Unsupported token version")
    encoded = token[len(version):]
    if any(character not in alphabet for character in encoded):
        raise ValueError("Invalid token character")
    standard = encoded.translate(str.maketrans(alphabet, STANDARD_ALPHABET))
    binary = base64.b64decode(standard + "=" * (-len(standard) % 4), validate=True)
    if len(binary) < 8 or int.from_bytes(binary[:4], "big") != crc32(binary[4:]):
        raise ValueError("CRC32 mismatch")
    if binary[4:6] != b"\x01\x00":
        raise ValueError("Unsupported envelope layout")
    size, position = read_length(binary, 6)
    if position + size > len(binary):
        raise ValueError("Invalid challenge length")
    challenge = binary[position:position + size]
    size, position = read_length(binary, position + size)
    ciphertext = binary[position:position + size]
    if len(ciphertext) != size or position + size != len(binary) or not size or size % 16:
        raise ValueError("Invalid envelope length")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(bytes(16))).decryptor()
    padded = decryptor.update(ciphertext) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plain = _xor_prefix(unpadder.update(padded) + unpadder.finalize(), challenge)
    return {"plain": plain, "challenge": challenge, "ciphertext": ciphertext,
            "checksum": int.from_bytes(binary[:4], "big")}


def _form_query(pairs: list[tuple[str, str]]) -> str:
    # WHATWG URLSearchParams used by Node also escapes '~', while urllib keeps it.
    return urlencode(pairs, safe="*").replace("~", "%7E")


def _request_url(url: str, parameter: str) -> tuple[Any, list[tuple[str, str]]]:
    parts = urlsplit(urljoin(ORIGIN + "/", url))
    if (parts.scheme, parts.netloc) != ("https", "www.kinggo.com"):
        raise ValueError("Target URL must use https://www.kinggo.com")
    # WHATWG URL normalizes dot segments before computing the digest.
    segments: list[str] = []
    pathname = parts.path or "/"
    for segment in pathname.split("/"):
        if segment == "..":
            if len(segments) > 1:
                segments.pop()
        elif segment != ".":
            segments.append(segment)
    if pathname.endswith(("/.", "/..")):
        segments.append("")
    pathname = quote("/".join(segments) or "/", safe="/%:@!$&'()*+,;=-._~")
    pairs = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != parameter]
    return parts._replace(path=pathname), pairs


def request_digest(url: str, parameter: str = "oOr6SIhu") -> int:
    """Verified empty-body ASCII branch; encoded/non-ASCII inputs fail explicitly."""
    parts, pairs = _request_url(url, parameter)
    canonical = parts.path + _form_query(pairs)
    if re.search(r"[^\x20-\x7e]|%", canonical):
        raise ValueError("Use original-script replay for encoded or non-ASCII URLs")
    return crc32(canonical.upper().encode("utf-8"))


def build_request_payload(
    url: str, config: Config, *, timestamp_ms: int | None = None,
    random_high: int | None = None, flags: int | None = None,
    environment_code: int | None = None, session_tag: int | None = None,
    context_hex: str | None = None, digest: int | None = None,
) -> bytes:
    timestamp_ms = time.time_ns() // 1_000_000 if timestamp_ms is None else timestamp_ms
    random_high = secrets.randbelow(1_000_000) if random_high is None else random_high
    if type(timestamp_ms) is not int or abs(timestamp_ms) > 2**53 - 1:
        raise ValueError("timestamp_ms must be a JavaScript-safe integer")
    if type(random_high) is not int or not 0 <= random_high < 1_000_000:
        raise ValueError("random_high must be in [0, 1000000)")
    flags = config["flags"] if flags is None else flags
    environment_code = config["environmentCode"] if environment_code is None else environment_code
    session_tag = config["sessionTag"] if session_tag is None else session_tag
    context_hex = config["contextHex"] if context_hex is None else context_hex
    digest = request_digest(url, config["parameter"]) if digest is None else digest
    fields = (
        _uint32(flags) + struct.pack(">H", environment_code) + _uint32(session_tag)
        + _uint32(random_high) + _uint32(timestamp_ms) + _uint32(digest)
        + _sized(bytes.fromhex(context_hex))
    )
    return b"\x0b" + _sized(fields)


def generate(url: str, config: Config, **options: Any) -> dict[str, Any]:
    """Return value, signed URL and payloadHex. No network request is sent."""
    payload = build_request_payload(url, config, **options)
    value = encode_payload(payload, config)
    parts, _ = _request_url(url, config["parameter"])
    # Match URLSearchParams.set(): replace in place, remove duplicates, or append.
    pairs = []
    replaced = False
    for key, old_value in parse_qsl(parts.query, keep_blank_values=True):
        if key == config["parameter"]:
            if not replaced:
                pairs.append((key, value))
                replaced = True
        else:
            pairs.append((key, old_value))
    if not replaced:
        pairs.append((config["parameter"], value))
    signed_url = urlunsplit(parts._replace(query=_form_query(pairs)))
    return {"parameter": config["parameter"], "value": value, "url": signed_url,
            "payloadHex": payload.hex()}


def inspect_token(token: str, config: Config) -> dict[str, Any]:
    decoded = decode_token(token, config)
    plain = decoded["plain"]
    size, position = read_length(plain, 1)
    if not plain or plain[0] != 11 or size != len(plain) - position or size < 23:
        raise ValueError("Unsupported request payload layout")
    fields = plain[position:]
    context_size, context_position = read_length(fields, 22)
    if context_position + context_size != len(fields):
        raise ValueError("Invalid context length")
    return {
        "type": plain[0], "length": size, "flags": int.from_bytes(fields[:4], "big"),
        "environmentCode": int.from_bytes(fields[4:6], "big"),
        "sessionTag": int.from_bytes(fields[6:10], "big"),
        "randomHigh": int.from_bytes(fields[10:14], "big"),
        "timestampLow32": int.from_bytes(fields[14:18], "big"),
        "requestDigest": int.from_bytes(fields[18:22], "big"),
        "contextHex": fields[context_position:].hex(), "checksum": decoded["checksum"],
        "payloadHex": plain.hex(),
    }
