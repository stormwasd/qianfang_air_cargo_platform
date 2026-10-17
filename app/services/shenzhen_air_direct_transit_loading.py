"""KingGo HTTP client for direct Shenzhen Airlines transit-loading exports.

The client downloads AwbQueryExport.xlsx from the KingGo export endpoint for
the current Beijing calendar day and stores it in the RPA generated-files
directory, so the existing file watcher and parsing pipeline keep working.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import settings
from app.utils.helpers import get_china_now


class ShenzhenAirDirectTransitLoadingError(RuntimeError):
    """A safe, user-facing direct transit-loading export failure."""


class ShenzhenAirDirectTransitLoadingService:
    ORIGIN = "https://www.kinggo.com"
    EXPORT_PATH = "/awb/query/export/119"
    FILE_PREFIX = "AwbQueryExport"

    BASE_FIELDS = (
        ("pageNum", "1"),
        ("numPerPage", "200"),
        ("orderField", ""),
        ("orderDirection", ""),
        ("awbPrefixQ", ""),
        ("awbNoQ", ""),
        ("eawbFlagQ", "-1"),
        ("depCodeQ", ""),
        ("destCodeQ", ""),
        ("flightNoQ", ""),
        ("billCodeQ", ""),
        ("goodsNameQ", ""),
        ("goodsCodeQ", ""),
        ("custNoQ", ""),
        ("beginTimesQ", "00:00:00"),
        ("endTimesQ", "23:59:59"),
        ("shpInfoQ", ""),
        ("cneInfoQ", ""),
        ("dealCodeQ", ""),
        ("carrierCodeQ", ""),
        ("awbStatusQ", "-1"),
        ("flightDateCheck", "true"),
        ("internationalFlag", "1"),
    )

    def __init__(self, origin=None, output_dir=None):
        self.origin = (origin or settings.SHENZHEN_AIR_KINGGO_API_ORIGIN or self.ORIGIN).rstrip("/")
        raw_dir = output_dir or settings.RPA_GENERATED_FILES_DIR
        raw_path = Path(raw_dir)
        self.output_dir = raw_path if raw_path.is_absolute() else Path.cwd() / raw_path

    @staticmethod
    def _today_text(now=None):
        current = now or get_china_now()
        return current.strftime("%Y-%m-%d")

    def build_query_body(self, now=None):
        today = self._today_text(now)
        fields = []
        inserted = False
        for name, value in self.BASE_FIELDS:
            if name == "beginTimesQ" and not inserted:
                fields.extend((
                    ("operDateBeginQ", today),
                    ("operDateEndQ", today),
                    ("flightDateBeginQ", today),
                    ("flightDateEndQ", today),
                ))
                inserted = True
            fields.append((name, value))
        return urlencode(fields)

    async def _auth(self, path, body):
        har_path = Path(settings.SHENZHEN_AIR_KINGGO_HAR_PATH)
        if not har_path.is_absolute():
            har_path = Path.cwd() / har_path
        try:
            from kinggo_token import generate
            from kinggo_token.har import replay_offline

            extracted = await replay_offline(
                har_path,
                path,
                method="POST",
                body=body,
                channel=None if settings.SHENZHEN_AIR_KINGGO_BROWSER == "chromium" else settings.SHENZHEN_AIR_KINGGO_BROWSER,
                executable_path=settings.SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH,
                require_cookie=True,
            )
            token = generate(path, extracted["config"], digest=extracted["payload"]["requestDigest"])
            signed_url = token["url"]
            cookie = token.get("cookie") or extracted.get("cookie")
        except Exception as exc:
            raise ShenzhenAirDirectTransitLoadingError(
                "KingGo HAR签名/Cookie提取失败（%s）" % type(exc).__name__
            ) from exc
        if not signed_url or not cookie:
            raise ShenzhenAirDirectTransitLoadingError("KingGo HAR中未提取到可用签名或Cookie")
        return signed_url, {"Cookie": cookie}

    def _build_headers(self, auth_headers):
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.ORIGIN,
            "Referer": self.ORIGIN + "/main",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36",
            **auth_headers,
        }

    def _resolve_output_path(self, now=None):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stamp = (now or get_china_now()).strftime("%Y%m%d_%H%M%S")
        return self.output_dir / ("%s_%s.xlsx" % (self.FILE_PREFIX, stamp))

    async def download_export(self, now=None):
        body = self.build_query_body(now)
        signed_url, auth_headers = await self._auth(self.EXPORT_PATH, body)
        canonical = urlsplit(signed_url)
        request_url = self.origin + canonical.path + ("?" + canonical.query if canonical.query else "")
        try:
            async with httpx.AsyncClient(
                timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    request_url, headers=self._build_headers(auth_headers), content=body
                )
        except httpx.HTTPError as exc:
            raise ShenzhenAirDirectTransitLoadingError("KingGo过机装机表下载请求网络异常") from exc
        if not 200 <= response.status_code < 300:
            raise ShenzhenAirDirectTransitLoadingError(
                "KingGo过机装机表下载失败（HTTP %s）" % response.status_code
            )
        content = response.content
        if not content.startswith(b"PK"):
            raise ShenzhenAirDirectTransitLoadingError("KingGo过机装机表下载内容不是有效的xlsx文件")
        output_path = self._resolve_output_path(now)
        output_path.write_bytes(content)
        return output_path


shenzhen_air_direct_transit_loading_service = ShenzhenAirDirectTransitLoadingService()
