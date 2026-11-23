"""KingGo HTTP client for direct Shenzhen Airlines approval exports."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import settings
from app.utils.helpers import get_china_now
from app.services.tracking_execution_time import DIRECT_APPROVAL_SUCCESS_TYPES


class ShenzhenAirDirectApprovalError(RuntimeError):
    """A safe, user-facing direct approval export failure."""


class ShenzhenAirDirectApprovalService:
    ORIGIN = "https://www.kinggo.com"
    EXPORT_PATH = "/agent_order_look/export/125"
    WIDE_BODY_EXPORT_PATH = "/agent_order_look_wide/export/858"
    FILE_PREFIX = "订舱查询导出"
    WIDE_BODY_FILE_PREFIX = "宽体机订舱查询与修改导出"

    BASE_FIELDS = (
        ("pageNum", ""),
        ("numPerPage", ""),
        ("orderField", ""),
        ("orderDirection", ""),
        ("flightNo", ""),
        ("depCode", "SZX"),
        ("destCode", ""),
        ("flightDate", ""),
        ("agentCode", "SZXFDH"),
        ("remark", ""),
        ("orderType", "1"),
        ("ss", "1"),
        ("nn", "0"),
    )

    def __init__(self, origin: str | None = None, output_dir: str | None = None):
        self.origin = (origin or settings.SHENZHEN_AIR_KINGGO_API_ORIGIN or self.ORIGIN).rstrip("/")
        raw_dir = output_dir or settings.RPA_GENERATED_FILES_DIR
        raw_path = Path(raw_dir)
        self.output_dir = raw_path if raw_path.is_absolute() else Path.cwd() / raw_path

    @staticmethod
    def normalize_flight_date(value: str | datetime) -> str:
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        result = str(value or "").strip().replace("/", "-")[:10]
        try:
            return datetime.strptime(result, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError as exc:
            raise ShenzhenAirDirectApprovalError("深航批复导出日期必须为YYYY-MM-DD") from exc

    @classmethod
    def build_query_body(cls, flight_date: str | datetime, wide_body: bool = False) -> str:
        date_text = cls.normalize_flight_date(flight_date)
        fields = [
            (name, date_text if name == "flightDate" else value)
            for name, value in cls.BASE_FIELDS
            if not (wide_body and name == "orderType")
        ]
        return urlencode(fields)

    async def _auth(self, path: str, body: str) -> tuple[str, dict[str, str]]:
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
            signed_url = token.get("url")
            cookie = token.get("cookie") or extracted.get("cookie")
        except Exception as exc:
            raise ShenzhenAirDirectApprovalError(
                "KingGo HAR签名/Cookie提取失败（%s）" % type(exc).__name__
            ) from exc
        if not signed_url or not cookie:
            raise ShenzhenAirDirectApprovalError("KingGo HAR中未提取到可用签名或Cookie")
        return signed_url, {"Cookie": cookie}

    def _build_headers(self, auth_headers: dict[str, str]) -> dict[str, str]:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.ORIGIN,
            "Referer": self.ORIGIN + "/main",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0.0.0 Safari/537.36",
            **auth_headers,
        }

    def _resolve_output_path(self, flight_date: str | datetime, file_prefix: str, now=None) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        date_text = self.normalize_flight_date(flight_date).replace("-", "")
        stamp = (now or get_china_now()).strftime("%Y%m%d_%H%M%S_%f")
        return self.output_dir / f"{file_prefix}_{date_text}_{stamp}.xlsx"

    async def download_export(self, flight_date: str | datetime, now=None) -> Path:
        return await self._download_export(
            flight_date, self.EXPORT_PATH, self.FILE_PREFIX, wide_body=False, now=now
        )

    async def download_wide_body_export(self, flight_date: str | datetime, now=None) -> Path:
        return await self._download_export(
            flight_date,
            self.WIDE_BODY_EXPORT_PATH,
            self.WIDE_BODY_FILE_PREFIX,
            wide_body=True,
            now=now,
        )

    async def _download_export(
        self,
        flight_date: str | datetime,
        path: str,
        file_prefix: str,
        wide_body: bool,
        now=None,
    ) -> Path:
        body = self.build_query_body(flight_date, wide_body=wide_body)
        signed_url, auth_headers = await self._auth(path, body)
        canonical = urlsplit(signed_url)
        request_url = self.origin + canonical.path + ("?" + canonical.query if canonical.query else "")
        try:
            async with httpx.AsyncClient(
                timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS
            ) as client:
                response = await client.post(
                    request_url,
                    headers=self._build_headers(auth_headers),
                    content=body,
                )
        except httpx.HTTPError as exc:
            report_type = "宽体批复表" if wide_body else "批复表"
            raise ShenzhenAirDirectApprovalError(f"KingGo深航{report_type}下载请求网络异常") from exc
        if not 200 <= response.status_code < 300:
            report_type = "宽体批复表" if wide_body else "批复表"
            raise ShenzhenAirDirectApprovalError(
                f"KingGo深航{report_type}下载失败（HTTP {response.status_code}）"
            )
        if not response.content.startswith(b"PK"):
            report_type = "宽体批复表" if wide_body else "批复表"
            raise ShenzhenAirDirectApprovalError(f"KingGo深航{report_type}下载内容不是有效的xlsx文件")
        output_path = self._resolve_output_path(flight_date, file_prefix, now)
        output_path.write_bytes(response.content)
        return output_path


shenzhen_air_direct_approval_service = ShenzhenAirDirectApprovalService()
