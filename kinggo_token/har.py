"""Extract configuration using the original HAR scripts, with all traffic offline."""

from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urljoin, urlsplit

from .generator import (
    Config, _form_query, _request_url, decode_token, encode_payload, generate, inspect_token,
)


def _launch_options(channel: str | None, executable_path: str | None) -> dict[str, Any]:
    """Keep Windows' Edge default; use bundled Chromium on other platforms."""
    options: dict[str, Any] = {"headless": True}
    executable_path = executable_path or os.environ.get("EDGE_EXECUTABLE")
    if executable_path:
        options["executable_path"] = executable_path
    else:
        if channel == "auto":
            channel = "msedge" if sys.platform == "win32" else None
        if channel:
            options["channel"] = channel
    return options


def _launch_error(options: dict[str, Any], error: Exception) -> str:
    if "executable_path" in options:
        hint = ("Check --executable-path / executable_path / EDGE_EXECUTABLE and the browser's system dependencies. "
                "Remove the override to use automatic browser selection.")
    elif options.get("channel") == "msedge":
        hint = ("Install Microsoft Edge, or run 'python -m playwright install chromium' "
                "and select '--browser chromium' (API: channel=None).")
    elif "channel" not in options:
        hint = ("Install Chromium in the same Python environment and OS user: "
                "'python -m playwright install --with-deps chromium'. "
                "On Ubuntu, system dependency installation requires sudo privileges.")
    else:
        hint = f"Install the requested browser channel {options['channel']!r} and its system dependencies."
    return f"Browser launch failed. {hint}\nOriginal error: {error}"


def _entries(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8-sig") as handle:
        return json.load(handle)["log"]["entries"]


def _text(entry: dict[str, Any]) -> str:
    content = entry["response"]["content"]
    text = content.get("text", "")
    if content.get("encoding") == "base64":
        return base64.b64decode(text).decode("utf-8")
    return text


def select_config(token: str, probe: dict[str, Any]) -> dict[str, Any]:
    alphabets = list(dict.fromkeys(a for a in probe["alphabets"] if len(a) == len(set(a)) == 64))
    keys = list(dict.fromkeys(bytes(a).hex() for a in probe["keys"] if len(a) == 16))
    for alphabet in alphabets:
        for key_hex in keys:
            config = {"parameter": "oOr6SIhu", "version": token[0], "alphabet": alphabet, "keyHex": key_hex}
            try:
                decoded = decode_token(token, config)
                metadata = inspect_token(token, config)
                if len(decoded["challenge"]) != 48:
                    continue
                config.update(
                    challengeHex=decoded["challenge"].hex(), contextHex=metadata["contextHex"],
                    sessionTag=metadata["sessionTag"], flags=metadata["flags"],
                    environmentCode=metadata["environmentCode"],
                )
                if encode_payload(decoded["plain"], config) == token:
                    return config
            except (ValueError, IndexError, KeyError):
                continue
    raise ValueError(
        f"Cannot extract verified config: {len(keys)} key candidates, {len(alphabets)} alphabets. "
        + "; ".join(probe.get("errors", []))
    )


async def replay_offline(
    har_path: str | Path, url: str, method: str = "POST", body: str | None = None,
    *, channel: str | None = "auto", executable_path: str | None = None,
    timeout_ms: int = 30000,
) -> dict[str, Any]:
    """Async API suitable for FastAPI. Uses no logged-in browser or outbound requests.

    Browser state is recreated from scripts, not from the user's browser cookies.
    Default channel='auto': Edge on Windows, Playwright Chromium elsewhere.
    Set channel=None to explicitly use Playwright Chromium on any platform.
    """
    if any(character in url for character in "\r\n\t"):
        raise ValueError("Target URL must not contain newlines or tabs; use /awb/sms_alert/getCountSms on one line")

    from playwright.async_api import Error as PlaywrightError, async_playwright

    entries = _entries(har_path)
    main = next((e for e in entries if urlsplit(e["request"]["url"]).path == "/main" and _text(e)), None)
    if main is None:
        raise ValueError("HAR must include /main response content")
    match = re.search(r"<script\b[^>]*src=[\"']([^\"']+)[\"'][^>]*\br=['\"]m['\"]", _text(main), re.I)
    if not match:
        raise ValueError("Protection loader not found in /main")
    main_parts = urlsplit(main["request"]["url"])
    origin = f"{main_parts.scheme}://{main_parts.netloc}"
    loader = match[1]
    loader_url = urljoin(origin, loader)
    # Binary images in a HAR may be base64; decode only the selected scripts.
    by_url = {e["request"]["url"]: e for e in entries
              if e["response"]["content"].get("text")}
    loader_entry = by_url.get(loader_url)
    if loader_entry is None:
        raise ValueError("HAR missing loader script body")
    match = re.search(r"document\.write\([\s\S]*?<script src=['\"]([^'\"]+)['\"]", _text(loader_entry), re.I)
    if not match:
        raise ValueError("Second protection script not found")
    engine_url = urljoin(origin, match[1])
    if engine_url not in by_url:
        raise ValueError("HAR missing engine script body")
    requested_parts, requested_pairs = _request_url(url, "oOr6SIhu")
    requested_url = requested_parts._replace(query=_form_query(requested_pairs)).geturl()
    if f"{requested_parts.scheme}://{requested_parts.netloc}" != origin:
        raise ValueError("Target URL must match HAR origin")
    method = method.upper()
    user_agent = next((h["value"] for h in main["request"]["headers"] if h["name"].lower() == "user-agent"), None)
    permitted = {loader_url, engine_url}
    captured: dict[str, str] | None = None
    page_errors: list[str] = []

    async with async_playwright() as playwright:
        launch_options = _launch_options(channel, executable_path)
        try:
            browser = await playwright.chromium.launch(**launch_options)
        except PlaywrightError as error:
            raise RuntimeError(_launch_error(launch_options, error)) from error
        try:
            context_options: dict[str, Any] = {"service_workers": "block"}
            if user_agent:
                context_options["user_agent"] = user_agent
            context = await browser.new_context(**context_options)
            # Defense in depth: prevent socket connections that request routing doesn't cover.
            async def close_socket(socket: Any) -> None:
                await socket.close()

            await context.route_web_socket("**/*", close_socket)

            async def route_request(route: Any) -> None:
                nonlocal captured
                request = route.request
                request_url = request.url
                if request_url == origin + "/main":
                    html = ('<!doctype html><html><head><script src=' + json.dumps(loader)
                            + ' r="m"></script></head><body></body></html>')
                    await route.fulfill(content_type="text/html;charset=utf-8", body=html)
                elif request_url in permitted:
                    await route.fulfill(content_type="text/javascript;charset=utf-8", body=_text(by_url[request_url]))
                else:
                    parts = urlsplit(request_url)
                    value = dict(parse_qsl(parts.query)).get("oOr6SIhu")
                    if value and parts.path == requested_parts.path and request.method == method:
                        captured = {"url": request_url, "value": value}
                    await route.fulfill(status=200, content_type="text/plain", body="offline")

            await context.route("**/*", route_request)
            page = await context.new_page()
            page.set_default_timeout(timeout_ms)
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            await page.add_init_script(path=str(Path(__file__).with_name("probe.js")))
            await page.goto(origin + "/main")
            await page.evaluate(
                """async ({url,method,body,timeout}) => new Promise((resolve,reject) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open(method,url);
                    xhr.timeout = timeout;
                    xhr.onload = () => resolve(null);
                    xhr.onerror = () => reject(new Error('Offline XHR failed'));
                    xhr.ontimeout = () => reject(new Error('Offline XHR timeout'));
                    xhr.send(body);
                })""",
                {"url": requested_url, "method": method, "body": body, "timeout": timeout_ms},
            )
            if captured is None:
                raise ValueError("Parameter was not generated: " + "; ".join(page_errors))
            probe = await page.evaluate("() => window.__configProbe")
            config = select_config(captured["value"], probe)
            config["source"] = Path(har_path).name
            return {"parameter": config["parameter"], **captured, "config": config,
                    "payload": inspect_token(captured["value"], config), "validation": "offline only"}
        finally:
            await browser.close()


def verify_har(har_path: str | Path, config: Config) -> int:
    count = 0
    for index, entry in enumerate(_entries(har_path)):
        parts = urlsplit(entry["request"]["url"])
        token = dict(parse_qsl(parts.query)).get(config["parameter"])
        if not token:
            continue
        try:
            decoded = decode_token(token, config)
            if encode_payload(decoded["plain"], config) != token:
                raise ValueError("Exact re-encoding mismatch")
            metadata = inspect_token(token, config)
            result = generate(
                entry["request"]["url"], config, flags=metadata["flags"],
                environment_code=metadata["environmentCode"], session_tag=metadata["sessionTag"],
                context_hex=metadata["contextHex"], timestamp_ms=metadata["timestampLow32"],
                random_high=metadata["randomHigh"],
            )
            if result["value"] != token:
                raise ValueError("Request payload reconstruction mismatch")
            count += 1
        except ValueError as error:
            raise ValueError(f"HAR entry {index} ({parts.path}): {error}") from error
    if not count:
        raise ValueError("HAR contains no parameter samples")
    return count
