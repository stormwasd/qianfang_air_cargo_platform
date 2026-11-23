"""KingGo HTTP client for direct Shenzhen Airlines waybill voiding.

The KingGo query endpoint returns HTML rather than JSON.  The client first
resolves the upstream ``awbId`` from that HTML and then calls the delete
endpoint with a freshly generated signature and Cookie for each request.
"""
from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import settings


class ShenzhenAirDirectWaybillVoidError(RuntimeError):
    """A safe, user-facing direct-void failure.

    ``outcome_unknown`` is set only when the delete request may have reached
    KingGo but its result cannot be confirmed.  Callers must not automatically
    retry that case.
    """

    def __init__(self, message: str, *, outcome_unknown: bool = False):
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


class _WaybillRowParser(HTMLParser):
    """Extract only the fields needed to identify one result row."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self._row: dict[str, str] | None = None
        self._row_depth = 0
        self._cell_name: str | None = None
        self._cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        tag = tag.lower()
        if tag == "tr":
            self._row = {"rel": attrs_dict.get("rel", "")}
            self._row_depth = 1
            return
        if self._row is None:
            return
        if tag == "td":
            self._cell_name = attrs_dict.get("name") or None
            self._cell_text = []
        elif tag == "input" and attrs_dict.get("name", "").lower() == "awbid":
            self._row["awb_id"] = attrs_dict.get("value", "").strip()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._row is None:
            return
        if tag == "td" and self._cell_name:
            text = "".join(self._cell_text).strip()
            if text:
                self._row[self._cell_name.lower()] = text
            self._cell_name = None
            self._cell_text = []
        elif tag == "tr":
            self.rows.append(self._row)
            self._row = None
            self._row_depth = 0

    def handle_data(self, data: str) -> None:
        if self._row is not None and self._cell_name:
            self._cell_text.append(data)


class ShenzhenAirDirectWaybillVoidService:
    ORIGIN = "https://www.kinggo.com"
    PREFIX = "479"
    QUERY_PATH = "/awb/query/index/119?flag=true"
    DELETE_PATH = "/awb/query/delete_awb_info/119"

    QUERY_FIELDS = (
        ("numPerPage", "200"),
        ("awbPrefixQ", PREFIX),
        ("eawbFlagQ", "-1"),
        ("depCodeQ", ""),
        ("destCodeQ", ""),
        ("flightNoQ", ""),
        ("billCodeQ", ""),
        ("goodsNameQ", ""),
        ("goodsCodeQ", ""),
        ("custNoQ", ""),
        ("operDateCheck", "true"),
        ("operDateBeginQ", "1900-10-01"),
        ("beginTimesQ", "00:00:00"),
        ("operDateEndQ", "2099-10-01"),
        ("endTimesQ", "23:59:59"),
        ("shpInfoQ", ""),
        ("cneInfoQ", ""),
        ("dealCodeQ", ""),
        ("carrierCodeQ", ""),
        ("awbStatusQ", "-1"),
        ("internationalFlag", "1"),
    )

    def __init__(self, origin: str | None = None):
        self.origin = (origin or settings.SHENZHEN_AIR_KINGGO_API_ORIGIN or self.ORIGIN).rstrip("/")

    @classmethod
    def normalize_suffix(cls, waybill_number: str) -> str:
        value = str(waybill_number or "").strip()
        if value.startswith(f"{cls.PREFIX}-"):
            value = value[len(cls.PREFIX) + 1:]
        if not re.fullmatch(r"\d{8}", value):
            raise ShenzhenAirDirectWaybillVoidError("运单号格式不正确，深航作废需要8位数字运单号")
        return value

    async def _auth(self, path: str, method: str, body: str) -> tuple[str, dict[str, str]]:
        har_path = Path(settings.SHENZHEN_AIR_KINGGO_HAR_PATH)
        if not har_path.is_absolute():
            har_path = Path.cwd() / har_path
        try:
            from kinggo_token import generate
            from kinggo_token.har import replay_offline

            extracted = await replay_offline(
                har_path,
                path,
                method=method,
                body=body,
                channel=None if settings.SHENZHEN_AIR_KINGGO_BROWSER == "chromium" else settings.SHENZHEN_AIR_KINGGO_BROWSER,
                executable_path=settings.SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH,
                require_cookie=True,
            )
            token = generate(path, extracted["config"], digest=extracted["payload"]["requestDigest"])
            signed_url = token["url"]
            cookie = token.get("cookie") or extracted.get("cookie")
        except Exception as exc:
            raise ShenzhenAirDirectWaybillVoidError(
                f"KingGo HAR签名/Cookie提取失败（{type(exc).__name__}）"
            ) from exc
        if not signed_url or not cookie:
            raise ShenzhenAirDirectWaybillVoidError("KingGo HAR中未提取到可用签名或Cookie")
        return signed_url, {"Cookie": cookie}

    async def _request(self, path: str, *, body: str, accept: str) -> httpx.Response:
        signed_url, auth_headers = await self._auth(path, "POST", body)
        canonical = urlsplit(signed_url)
        request_url = self.origin + canonical.path + (f"?{canonical.query}" if canonical.query else "")
        headers = {
            "Accept": accept,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.ORIGIN,
            "Referer": self.ORIGIN + "/main",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/155.0.0.0 Safari/537.36",
            **auth_headers,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(request_url, headers=headers, content=body)
        except httpx.HTTPError as exc:
            raise ShenzhenAirDirectWaybillVoidError(
                "KingGo深航作废请求网络异常，请核查上游状态后再处理",
                outcome_unknown=path.startswith(self.DELETE_PATH),
            ) from exc
        if not 200 <= response.status_code < 300:
            raise ShenzhenAirDirectWaybillVoidError(
                f"KingGo深航作废请求失败（HTTP {response.status_code}）",
                outcome_unknown=path.startswith(self.DELETE_PATH),
            )
        return response

    @classmethod
    def _find_awb_id(cls, html: str, suffix: str) -> str:
        parser = _WaybillRowParser()
        try:
            parser.feed(html)
            parser.close()
        except Exception as exc:
            raise ShenzhenAirDirectWaybillVoidError("KingGo运单查询返回内容无法解析") from exc
        matches: list[str] = []
        for row in parser.rows:
            if row.get("awbprefix", "").strip() != cls.PREFIX:
                continue
            if row.get("awbno", "").strip() != suffix:
                continue
            rel = row.get("rel", "").strip()
            awb_id = row.get("awb_id", "").strip()
            if not re.fullmatch(r"\d+", rel) or not re.fullmatch(r"\d+", awb_id):
                raise ShenzhenAirDirectWaybillVoidError("KingGo运单查询结果缺少有效上游运单ID")
            if rel != awb_id:
                raise ShenzhenAirDirectWaybillVoidError("KingGo运单查询结果的上游运单ID不一致")
            matches.append(awb_id)
        if not matches:
            raise ShenzhenAirDirectWaybillVoidError("KingGo中未找到对应的深航运单")
        if len(set(matches)) != 1 or len(matches) != 1:
            raise ShenzhenAirDirectWaybillVoidError("KingGo中找到多个相同深航运单，已停止作废")
        return matches[0]

    async def void_waybill(self, waybill_number: str) -> dict[str, str]:
        suffix = self.normalize_suffix(waybill_number)
        query_body = urlencode((*self.QUERY_FIELDS[:2], ("awbNoQ", suffix), *self.QUERY_FIELDS[2:]))
        query_response = await self._request(self.QUERY_PATH, body=query_body, accept="*/*")
        awb_id = self._find_awb_id(query_response.text, suffix)

        delete_path = f"{self.DELETE_PATH}?{urlencode({'awbId': awb_id})}"
        delete_response = await self._request(delete_path, body="", accept="application/json, text/javascript, */*; q=0.01")
        try:
            result: Any = delete_response.json()
        except ValueError as exc:
            raise ShenzhenAirDirectWaybillVoidError(
                "KingGo深航作废返回非JSON结果，请核查上游状态后再处理",
                outcome_unknown=True,
            ) from exc
        if not isinstance(result, dict) or str(result.get("statusCode")) != "200" or result.get("message") != "成功删除":
            raise ShenzhenAirDirectWaybillVoidError(
                "KingGo深航运单作废未确认成功，请核查上游返回",
                outcome_unknown=True,
            )
        return {"awb_id": awb_id, "waybill_number": f"{self.PREFIX}-{suffix}"}


shenzhen_air_direct_waybill_void_service = ShenzhenAirDirectWaybillVoidService()
