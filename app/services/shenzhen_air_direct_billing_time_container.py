"""KingGo client for Shenzhen Airlines billing-time/container details."""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
import time
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import settings


class ShenzhenAirDirectBillingTimeContainerError(RuntimeError):
    """A safe, user-facing direct KingGo failure."""


class _GetWayTableParser(HTMLParser):
    """Read table rows below ``#getWay`` without trusting page scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._depth = 0
        self._get_way_depth: int | None = None
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if tag == "div" and attrs_dict.get("id", "").lower() == "getway":
            self._get_way_depth = self._depth + 1
        self._depth += 1
        if self._get_way_depth is None:
            return
        if tag == "tr":
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._get_way_depth is not None:
            if tag == "td" and self._row is not None and self._cell is not None:
                self._row.append(" ".join("".join(self._cell).split()))
                self._cell = None
            elif tag == "tr" and self._row is not None:
                if self._row:
                    self.rows.append(self._row)
                self._row = None
        closing_depth = self._depth
        self._depth = max(0, self._depth - 1)
        if closing_depth == self._get_way_depth:
            self._get_way_depth = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


class ShenzhenAirDirectBillingTimeContainerService:
    ORIGIN = "https://www.kinggo.com"
    PATH = "/awb/query/getaway"
    PREFIX = "479"

    def __init__(self, origin: str | None = None) -> None:
        self.origin = (origin or settings.SHENZHEN_AIR_KINGGO_API_ORIGIN or self.ORIGIN).rstrip("/")

    @classmethod
    def build_path(cls, awb_number: str, routing: str, flight_date: str, now_ms: int | None = None) -> str:
        suffix = str(awb_number or "").strip()
        if suffix.startswith(cls.PREFIX + "-"):
            suffix = suffix[len(cls.PREFIX) + 1:]
        if not re.fullmatch(r"\d{8}", suffix):
            raise ShenzhenAirDirectBillingTimeContainerError("深航运单号必须为8位数字")
        route = re.sub(r"\s*-\s*", "-", str(routing or "").strip())
        date = str(flight_date or "").strip().replace("/", "-")[:10]
        if not route or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ShenzhenAirDirectBillingTimeContainerError("深航计飞数据缺少有效航程或航班日期")
        query = {
            "awbPrefix": cls.PREFIX,
            "awbNo": suffix,
            "depCode": route,
            "flightDate": date,
            "nti": "119",
            "historyCheck": "false",
            "_": str(now_ms if now_ms is not None else time.time_ns() // 1_000_000),
        }
        return cls.PATH + "?" + urlencode(query)

    @staticmethod
    def parse_rows(content: str) -> list[list[str]]:
        parser = _GetWayTableParser()
        try:
            parser.feed(content)
            parser.close()
        except Exception as exc:
            raise ShenzhenAirDirectBillingTimeContainerError("深航计飞数据HTML解析失败") from exc
        rows: list[list[str]] = []
        for row in parser.rows:
            if len(row) < 9:
                continue
            first = row[0].strip()
            if not first.isdigit() or "合计" in row[1]:
                continue
            rows.append(row[:9])
        return rows

    async def _auth(self, path: str) -> tuple[str, dict[str, str]]:
        har_path = Path(settings.SHENZHEN_AIR_KINGGO_HAR_PATH)
        if not har_path.is_absolute():
            har_path = Path.cwd() / har_path
        try:
            from kinggo_token import generate
            from kinggo_token.har import replay_offline

            extracted = await replay_offline(
                har_path,
                path,
                method="GET",
                body=None,
                channel=None if settings.SHENZHEN_AIR_KINGGO_BROWSER == "chromium" else settings.SHENZHEN_AIR_KINGGO_BROWSER,
                executable_path=settings.SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH,
                require_cookie=True,
            )
            token = generate(path, extracted["config"], digest=extracted["payload"]["requestDigest"])
            signed_url = token.get("url")
            cookie = token.get("cookie") or extracted.get("cookie")
        except Exception as exc:
            raise ShenzhenAirDirectBillingTimeContainerError(
                "KingGo HAR签名/Cookie提取失败（%s）" % type(exc).__name__
            ) from exc
        if not signed_url or not cookie:
            raise ShenzhenAirDirectBillingTimeContainerError("KingGo HAR中未提取到可用签名或Cookie")
        return signed_url, {"Cookie": cookie}

    async def fetch_rows(self, awb_number: str, routing: str, flight_date: str) -> list[list[str]]:
        path = self.build_path(awb_number, routing, flight_date)
        signed_url, auth_headers = await self._auth(path)
        canonical = urlsplit(signed_url)
        request_url = self.origin + canonical.path + ("?" + canonical.query if canonical.query else "")
        headers = {
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.ORIGIN + "/main",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0.0.0 Safari/537.36",
            **auth_headers,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(request_url, headers=headers)
        except httpx.HTTPError as exc:
            raise ShenzhenAirDirectBillingTimeContainerError("KingGo计飞集装器请求网络异常") from exc
        if not 200 <= response.status_code < 300:
            raise ShenzhenAirDirectBillingTimeContainerError(
                "KingGo计飞集装器请求失败（HTTP %s）" % response.status_code
            )
        rows = self.parse_rows(response.text)
        if not rows:
            raise ShenzhenAirDirectBillingTimeContainerError("KingGo未返回有效计飞集装器数据")
        return rows


shenzhen_air_direct_billing_time_container_service = ShenzhenAirDirectBillingTimeContainerService()
