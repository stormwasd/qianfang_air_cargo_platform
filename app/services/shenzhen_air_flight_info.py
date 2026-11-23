"""Download complete KingGo flight tables and persist only changed segments."""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from html.parser import HTMLParser
import logging
import math
import re
import threading
import time
from urllib.parse import urlencode, urlsplit

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.shenzhen_air_flight_info import ShenzhenAirFlightInfo
from app.services.shenzhen_air_direct_approval import (
    ShenzhenAirDirectApprovalError, shenzhen_air_direct_approval_service,
)
from app.utils.helpers import get_china_now

logger = logging.getLogger(__name__)


class FlightInfoError(RuntimeError):
    """A flight-table failure with safe, structured diagnostic information."""

    REASONS = {
        "invalid_pagination": "KingGo航班表分页信息无效",
        "invalid_headers": "KingGo未返回有效航班表（可能登录失效或列结构改变）",
        "missing_pagination": "KingGo航班表缺少有效分页信息",
        "invalid_columns": "KingGo航班表列数改变，已停止同步",
        "invalid_flight_or_route": "KingGo航班表航班号或航程无效",
        "invalid_date": "KingGo航班表日期无效",
        "request_failed": "KingGo航班表请求失败",
        "total_changed": "KingGo翻页期间总数发生变化，下轮重试",
        "date_mismatch": "KingGo航班表返回日期与查询日期不匹配，下轮重试",
        "duplicate_segment": "KingGo分页出现重复航段，下轮重试",
        "incomplete_pages": "KingGo航班表分页不完整，已保留旧数据",
        "empty_page": "KingGo航班表分页提前结束",
        "page_limit": "KingGo航班表超过分页上限，已保留旧数据",
        "save_date_mismatch": "航班同步日期不匹配",
    }

    def __init__(self, reason: str, **context):
        # Keep legacy exception messages usable, but never log an arbitrary
        # message that may contain a signed URL, Cookie or response content.
        self.reason_code = reason if reason in self.REASONS else "unknown"
        self.safe_reason = self.REASONS.get(reason, "KingGo航班表请求或校验失败")
        self.context = context
        super().__init__(self.REASONS.get(reason, reason))


def normalize_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value).strip().replace("/", "-")[:10], "%Y-%m-%d").date()


def segment_key(row):
    return (row["flight_date"], row["flight_number"], row["origin"], row["destination"])


def is_valid_kinggo_flight_number(flight: str) -> bool:
    """Validate a trimmed, uppercase KingGo identifier without rewriting it.

    Keep the existing 2-character carrier + 1..5-character suffix length limit,
    but allow mixed ASCII letters/digits such as ZHT2F8 and ZH30CU. KingGo's
    identifiers are not limited to conventional numeric flight suffixes.
    """
    return re.fullmatch(r"[A-Z0-9]{3,7}", flight) is not None


class _FlightTableParser(HTMLParser):
    """Read text only; never execute the scripts in KingGo's HTML response."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows = []
        self.headers = []
        self.total = None
        self.page_size = None
        self._row = None
        self._cell = None
        self._heading = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div" and "pagination" in attrs.get("class", "").split():
            try:
                self.total = int(attrs["totalcount"])
                self.page_size = int(attrs["numperpage"])
            except (KeyError, ValueError):
                raise FlightInfoError("invalid_pagination")
        if tag == "tr" and attrs.get("target") == "flight_info_id":
            self._row = {"kinggo_id": attrs.get("rel"), "cells": []}
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "th":
            self._heading = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)
        if self._heading is not None:
            self._heading.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self._row["cells"].append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None
        elif tag == "th" and self._heading is not None:
            self.headers.append("".join(self._heading).strip())
            self._heading = None


VALUE_COLUMNS = (
    "area", "takeoff_time", "arrival_time", "actual_departure_time",
    "actual_arrival_time", "aircraft_number", "aircraft_type", "body_type",
    "status", "total_weight", "total_volume", "control_weight", "control_volume",
    "free_weight", "cargo_flag",
)


def parse_flight_page(html: str):
    parser = _FlightTableParser()
    parser.feed(html)
    parser.close()
    expected_headers = [
        "序号", "日期", "航班号", "航程", "区域", "起飞", "到达", "实际起飞", "实际到达",
        "飞机号", "机型", "宽/窄", "状态", "总重量", "总体积", "控制重量", "控制体积", "开放重量", "货机", "详情",
    ]
    if parser.headers != expected_headers:
        mismatch = next((index for index, (expected, actual) in enumerate(
            zip(expected_headers, parser.headers), start=1
        ) if expected != actual), min(len(expected_headers), len(parser.headers)) + 1)
        raise FlightInfoError(
            "invalid_headers", expected_columns=len(expected_headers),
            actual_columns=len(parser.headers), header_mismatch_column=mismatch,
        )
    if parser.total is None or parser.total < 0 or not parser.page_size or parser.page_size < 1:
        raise FlightInfoError("missing_pagination", actual_total=parser.total, page_size=parser.page_size)
    rows = []
    for row_index, entry in enumerate(parser.rows, start=1):
        cells = entry["cells"]
        if len(cells) != 20:
            raise FlightInfoError("invalid_columns", row_index=row_index,
                                  expected_columns=20, actual_columns=len(cells))
        route = cells[3].strip().upper().split("-")
        flight = cells[2].strip().upper()
        valid_flight = is_valid_kinggo_flight_number(flight)
        valid_route = len(route) == 2 and all(
            re.fullmatch(r"[A-Z]{3}", port) for port in route
        )
        if not valid_flight or not valid_route:
            raise FlightInfoError(
                "invalid_flight_or_route", row_index=row_index,
                invalid_fields=",".join(field for field, valid in (
                    ("flight_number", valid_flight), ("routing", valid_route)
                ) if not valid),
            )
        try:
            flight_date = normalize_date(cells[1])
        except ValueError as exc:
            raise FlightInfoError("invalid_date", row_index=row_index, flight_number=flight) from exc
        row = dict(zip(VALUE_COLUMNS, (v or None for v in cells[4:19])))
        row.update(flight_date=flight_date, flight_number=flight,
                   origin=route[0], destination=route[1], kinggo_id=entry["kinggo_id"])
        rows.append(row)
    return rows, parser.total, parser.page_size


class KingGoFlightInfoClient:
    PATH = "/flight_info/index/92?flag=true"
    MAX_PAGES = 100

    async def fetch(self, flight_date: date) -> list[dict]:
        all_rows = {}
        total = None
        page = 1
        async with httpx.AsyncClient(
            timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS
        ) as client:
            while page <= self.MAX_PAGES:
                fields = [
                    ("flightNoQ", ""), ("carrierCodeQ", ""),
                    ("flightDateStart", flight_date.isoformat()),
                    ("flightDateEnd", flight_date.isoformat()),
                    ("depCodeQ", ""), ("destCodeQ", ""), ("flightStatusStrQ", "1"),
                    ("areaTypeQ", "D"), ("planeCodeQ", ""), ("planeTypeQ", ""),
                    ("pageNum", str(page)), ("numPerPage", "200"),
                ]
                if flight_date < get_china_now().date():
                    fields.append(("historyCheck", "true"))
                body = urlencode(fields)
                # Reuse the established HAR signing path, including the exact
                # POST body digest. A fresh Cookie/signature is used per page.
                signed_url, auth = await shenzhen_air_direct_approval_service._auth(self.PATH, body)
                url = urlsplit(signed_url)
                origin = settings.SHENZHEN_AIR_KINGGO_API_ORIGIN.rstrip("/")
                headers = shenzhen_air_direct_approval_service._build_headers(auth)
                headers["X-Requested-With"] = "XMLHttpRequest"
                try:
                    response = await client.post(origin + url.path + "?" + url.query,
                                                 headers=headers, content=body)
                    response.raise_for_status()
                except httpx.HTTPError as exc:
                    context = {"page": page, "request_error_type": type(exc).__name__}
                    if isinstance(exc, httpx.HTTPStatusError):
                        context["http_status"] = exc.response.status_code
                    raise FlightInfoError("request_failed", **context) from exc
                try:
                    rows, count, size = parse_flight_page(response.text)
                except FlightInfoError as exc:
                    exc.context.update(page=page, http_status=response.status_code)
                    raise
                if total is not None and count != total:
                    raise FlightInfoError("total_changed", page=page, expected_total=total,
                                          actual_total=count, collected_count=len(all_rows), page_rows=len(rows))
                total = count
                for row_index, row in enumerate(rows, start=1):
                    if row["flight_date"] != flight_date:
                        raise FlightInfoError("date_mismatch", page=page, row_index=row_index,
                                              flight_number=row["flight_number"], returned_date=row["flight_date"].isoformat())
                    if segment_key(row) in all_rows:
                        raise FlightInfoError("duplicate_segment", page=page, row_index=row_index,
                                              flight_number=row["flight_number"], origin=row["origin"],
                                              destination=row["destination"], collected_count=len(all_rows))
                    all_rows[segment_key(row)] = row
                if page >= max(1, math.ceil(total / size)):
                    if len(all_rows) != total:
                        raise FlightInfoError("incomplete_pages", page=page, page_size=size,
                                              expected_total=total, collected_count=len(all_rows), page_rows=len(rows))
                    return list(all_rows.values())
                if not rows:
                    raise FlightInfoError("empty_page", page=page, page_size=size,
                                          expected_total=total, collected_count=len(all_rows), page_rows=0)
                page += 1
        raise FlightInfoError("page_limit", page=self.MAX_PAGES, max_pages=self.MAX_PAGES,
                              expected_total=total, collected_count=len(all_rows))


def save_changed_flights(db, flight_date: date, rows: list[dict]) -> tuple[int, int]:
    """Single transaction; no DELETE and no UPDATE for identical business data."""
    existing = {
        (r.flight_date, r.flight_number, r.origin, r.destination): r
        for r in db.query(ShenzhenAirFlightInfo).filter_by(flight_date=flight_date).all()
    }
    inserted = updated = 0
    now = get_china_now()
    for row_index, values in enumerate(rows, start=1):
        if values["flight_date"] != flight_date:
            raise FlightInfoError("save_date_mismatch", row_index=row_index)
        key = segment_key(values)
        record = existing.get(key)
        if record is None:
            record = ShenzhenAirFlightInfo(**values, created_at=now, updated_at=now)
            db.add(record)
            existing[key] = record
            inserted += 1
        elif any(getattr(record, k) != v for k, v in values.items()):
            for key, value in values.items():
                setattr(record, key, value)
            record.updated_at = now
            updated += 1
    db.flush()
    return inserted, updated


class ShenzhenAirFlightInfoSync:
    """One process-wide lock also works across the existing thread event loops."""

    def __init__(self):
        self._lock = threading.Lock()
        self._success = {}
        self._attempt = {}
        self._stop = threading.Event()
        self._thread = None
        self.client = KingGoFlightInfoClient()

    async def ensure_fresh(self, flight_date: date) -> bool:
        if not settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED:
            return False
        if not self._lock.acquire(blocking=False):
            return False  # A running round will publish atomically on commit.
        try:
            now = time.monotonic()
            if now - self._success.get(flight_date, -float("inf")) < settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_INTERVAL_SECONDS:
                return True
            if now - self._attempt.get(flight_date, -float("inf")) < settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_RETRY_SECONDS:
                return False
            self._attempt[flight_date] = now
            stage = "fetch"
            try:
                # Bound the whole paginated fetch, especially during startup.
                rows = await asyncio.wait_for(self.client.fetch(flight_date), timeout=120)
                stage = "persist"
                db = SessionLocal()
                try:
                    inserted, updated = save_changed_flights(db, flight_date, rows)
                    db.commit()
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
                self._success[flight_date] = time.monotonic()
                logger.info("深航KingGo航班同步完成 date=%s count=%s inserted=%s updated=%s",
                            flight_date, len(rows), inserted, updated)
                return True
            except Exception as exc:
                self._attempt[flight_date] = time.monotonic()
                # Log only our fixed reasons and validated diagnostic fields.
                # Raw exception strings/tracebacks may expose HAR credentials,
                # signed URLs, HTML bodies or database connection details.
                if isinstance(exc, FlightInfoError):
                    reason = exc.safe_reason
                    details = {"reason_code": exc.reason_code, **exc.context}
                elif isinstance(exc, ShenzhenAirDirectApprovalError):
                    reason = "KingGo HAR签名或Cookie准备失败"
                    details = {"reason_code": "auth_failed"}
                elif stage == "fetch" and isinstance(exc, TimeoutError):
                    reason = "KingGo航班表整轮同步超时"
                    details = {"reason_code": "sync_timeout", "timeout_seconds": 120}
                else:
                    reason = "KingGo航班表入库失败" if stage == "persist" else "KingGo航班表获取失败"
                    details = {"reason_code": "persist_failed" if stage == "persist" else "fetch_failed"}
                if exc.__cause__ is not None:
                    details["cause_type"] = type(exc.__cause__).__name__
                logger.warning(
                    "深航KingGo航班同步失败 date=%s error_type=%s stage=%s reason=%s %s；保留旧数据",
                    flight_date, type(exc).__name__, stage, reason,
                    " ".join(f"{key}={value}" for key, value in details.items()),
                )
                return False
        finally:
            self._lock.release()

    def start(self):
        if not settings.SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="szx-flight-info-sync", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        asyncio.run(self._main())

    async def _main(self):
        while not self._stop.is_set():
            await self.ensure_fresh(get_china_now().date())
            # Check due time frequently, including when the Beijing date rolls over.
            await asyncio.to_thread(self._stop.wait, 5)


shenzhen_air_flight_info_sync = ShenzhenAirFlightInfoSync()
