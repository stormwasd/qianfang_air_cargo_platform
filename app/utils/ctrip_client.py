import asyncio
import logging
import random
import re
import string
import time
from datetime import date, datetime
from typing import Dict, Optional, Set, Tuple
from urllib.parse import urlsplit

import httpx

from app.config import settings


logger = logging.getLogger(__name__)


class CtripProxyError(RuntimeError):
    """Raised when no usable Ctrip proxy can complete the request."""


def _rand_str(n: int = 12) -> str:
    """生成指定长度的随机字符串。"""
    chars = string.ascii_letters + string.digits
    return "".join(random.choice(chars) for _ in range(n))


class CtripClient:
    """
    携程航班接口客户端。

    - 动态 GUID 缓存
    - 5 分钟 TTL 航班结果缓存
    - 异步 Semaphore 并发控制
    - 可选接入 jhao104/proxy_pool；坏代理会从代理池删除并自动换 IP
    """

    GUID_TTL = 30 * 60
    CACHE_TTL = 5 * 60
    REQUEST_TIMEOUT = 15.0

    def __init__(
        self,
        *,
        proxy_enabled: Optional[bool] = None,
        proxy_pool_url: Optional[str] = None,
        proxy_max_attempts: Optional[int] = None,
        proxy_pool_timeout: Optional[float] = None,
    ):
        self.proxy_enabled = (
            settings.CTRIP_PROXY_ENABLED
            if proxy_enabled is None
            else proxy_enabled
        )
        self.proxy_pool_url = (
            proxy_pool_url or settings.CTRIP_PROXY_POOL_URL
        ).rstrip("/")
        self.proxy_max_attempts = (
            settings.CTRIP_PROXY_MAX_ATTEMPTS
            if proxy_max_attempts is None
            else proxy_max_attempts
        )
        self.proxy_pool_timeout = (
            settings.CTRIP_PROXY_POOL_TIMEOUT_SECONDS
            if proxy_pool_timeout is None
            else proxy_pool_timeout
        )

        self._guid: Optional[str] = None
        self._guid_ts: float = 0.0
        self._locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._semaphores: Dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}
        self._clients: Dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}
        self._proxy_pool_clients: Dict[
            asyncio.AbstractEventLoop, httpx.AsyncClient
        ] = {}

        # GUID 必须与出口 IP 绑定，不能把直连或其他代理取得的 GUID 混用。
        self._proxy_guids: Dict[str, Tuple[float, str]] = {}

        # (flight_no, flight_date, routing) -> (timestamp, data_dict)
        self._cache: Dict[
            Tuple[str, str, str], Tuple[float, Dict[str, str]]
        ] = {}

    @property
    def lock(self) -> asyncio.Lock:
        """根据当前 event loop 动态获取或创建直连 GUID 锁。"""
        loop = asyncio.get_running_loop()
        if loop not in self._locks:
            self._locks[loop] = asyncio.Lock()
        return self._locks[loop]

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """限制单 event loop 内对携程 API 的最大并发请求数。"""
        loop = asyncio.get_running_loop()
        if loop not in self._semaphores:
            self._semaphores[loop] = asyncio.Semaphore(5)
        return self._semaphores[loop]

    def _get_client(self) -> httpx.AsyncClient:
        """每个 event loop 共享一个直连 httpx 连接池。"""
        loop = asyncio.get_running_loop()
        if loop not in self._clients or self._clients[loop].is_closed:
            self._clients[loop] = httpx.AsyncClient(
                timeout=self.REQUEST_TIMEOUT,
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                ),
            )
        return self._clients[loop]

    def _get_proxy_pool_client(self) -> httpx.AsyncClient:
        """代理池 API 自身始终直连，不能再套用代理池中的代理。"""
        loop = asyncio.get_running_loop()
        client = self._proxy_pool_clients.get(loop)
        if client is None or client.is_closed:
            client = httpx.AsyncClient(
                timeout=self.proxy_pool_timeout,
                limits=httpx.Limits(
                    max_keepalive_connections=5,
                    max_connections=10,
                ),
                trust_env=False,
            )
            self._proxy_pool_clients[loop] = client
        return client

    def _make_proxy_client(self, proxy_url: str) -> httpx.AsyncClient:
        """创建仅用于一次携程查询的代理会话。"""
        return httpx.AsyncClient(
            proxies=proxy_url,
            timeout=self.REQUEST_TIMEOUT,
            limits=httpx.Limits(
                max_keepalive_connections=1,
                max_connections=2,
            ),
            trust_env=False,
        )

    def _is_guid_valid(self) -> bool:
        if not self._guid:
            return False
        return (time.time() - self._guid_ts) < self.GUID_TTL

    @staticmethod
    def _proxy_guid_is_valid(entry: Optional[Tuple[float, str]]) -> bool:
        return bool(entry and (time.time() - entry[0]) < CtripClient.GUID_TTL)

    async def _fetch_guid(
        self, client: Optional[httpx.AsyncClient] = None
    ) -> str:
        """向携程 createclientid 接口请求一个新的 GUID。"""
        url = "https://m.ctrip.com/restapi/soa2/10290/createclientid"
        params = {
            "systemcode": "09",
            "createtype": "3",
            "contentType": "json",
        }
        headers = {
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "origin": "https://flights.ctrip.com",
            "referer": "https://flights.ctrip.com/",
            "locale": "zh-CN",
            "x-ctx-locale": "zh-CN",
        }
        response = await (client or self._get_client()).get(
            url,
            params=params,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()
        guid = data.get("ClientID") if isinstance(data, dict) else None
        if not guid:
            raise ValueError("createclientid 返回数据缺少 ClientID")
        return str(guid)

    async def _ensure_guid(self) -> str:
        """确保直连模式有一个可用 GUID。"""
        if self._is_guid_valid():
            return self._guid  # type: ignore[return-value]

        async with self.lock:
            if self._is_guid_valid():
                return self._guid  # type: ignore[return-value]
            self._guid = await self._fetch_guid()
            self._guid_ts = time.time()
            logger.info("Ctrip GUID refreshed")
            return self._guid

    async def _ensure_proxy_guid(
        self,
        proxy: str,
        client: httpx.AsyncClient,
    ) -> str:
        """获取并缓存与指定代理出口绑定的 GUID。"""
        entry = self._proxy_guids.get(proxy)
        if self._proxy_guid_is_valid(entry):
            return entry[1]

        # GUID 刷新频率很低，复用单 loop 锁可避免按代理永久累积 Lock 对象。
        async with self.lock:
            now = time.time()
            self._proxy_guids = {
                key: value
                for key, value in self._proxy_guids.items()
                if (now - value[0]) < self.GUID_TTL
            }
            entry = self._proxy_guids.get(proxy)
            if self._proxy_guid_is_valid(entry):
                return entry[1]
            guid = await self._fetch_guid(client)
            self._proxy_guids[proxy] = (now, guid)
            logger.info("Ctrip GUID refreshed via proxy %s", self._proxy_label(proxy))
            return guid

    def _invalidate_guid(self) -> None:
        self._guid = None
        self._guid_ts = 0.0

    def _invalidate_proxy_guid(self, proxy: str) -> None:
        self._proxy_guids.pop(proxy, None)

    @staticmethod
    def _normalize_proxy(proxy: str) -> str:
        """把 proxy_pool 的 host:port 结果规范化为 httpx 可用 URL。"""
        value = str(proxy or "").strip()
        if not value:
            raise ValueError("代理池返回了空代理")
        proxy_url = value if "://" in value else f"http://{value}"
        try:
            parsed = urlsplit(proxy_url)
            port = parsed.port
        except ValueError as exc:
            raise ValueError("代理池返回的代理端口无效") from exc
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or port is None
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
        ):
            raise ValueError("代理池返回的代理格式无效")
        return proxy_url

    @staticmethod
    def _proxy_label(proxy: str) -> str:
        """生成不包含代理认证密码的日志标签。"""
        try:
            parsed = urlsplit(proxy if "://" in proxy else f"http://{proxy}")
            return f"{parsed.hostname}:{parsed.port}"
        except (TypeError, ValueError):
            return "<invalid-proxy>"

    @staticmethod
    def _error_summary(exc: Exception) -> str:
        """避免 httpx 默认错误文本反复输出 MDN 链接。"""
        if isinstance(exc, httpx.HTTPStatusError):
            response = exc.response
            request = response.request
            return (
                f"HTTP {response.status_code} "
                f"{request.method} {request.url.host}{request.url.path}"
            )
        message = str(exc).strip()
        return f"{type(exc).__name__}: {message}" if message else type(exc).__name__

    @staticmethod
    def _is_proxy_failure(exc: Exception) -> bool:
        """区分代理/IP 故障与不应淘汰代理的上游接口错误。"""
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code in {
                403,
                407,
                408,
                425,
                429,
                430,
                502,
                503,
                504,
            }
        return isinstance(exc, (httpx.TransportError, ValueError))

    async def _acquire_proxy(self, excluded: Set[str]) -> Tuple[str, str]:
        """从 proxy_pool 获取一个本次尚未尝试过的代理。"""
        client = self._get_proxy_pool_client()
        selection_attempts = max(3, self.proxy_max_attempts * 2)
        last_error: Optional[Exception] = None
        for _ in range(selection_attempts):
            saw_candidate = False
            # 优先使用上游已标记为支持 HTTPS 的代理。若该集合为空，再从
            # HTTP 候选中取值，并由真实携程请求验证其 CONNECT 能力。
            for params in ({"type": "https"}, None):
                try:
                    response = await client.get(
                        f"{self.proxy_pool_url}/get/",
                        params=params,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    raw_proxy = (
                        str(payload.get("proxy", "")).strip()
                        if isinstance(payload, dict)
                        else ""
                    )
                    if not raw_proxy:
                        continue
                    saw_candidate = True
                    if raw_proxy in excluded:
                        continue
                    return raw_proxy, self._normalize_proxy(raw_proxy)
                except Exception as exc:
                    last_error = exc
                    break
            if last_error:
                break
            if not saw_candidate:
                raise CtripProxyError("代理池当前没有可用候选代理")
        if last_error:
            raise CtripProxyError(
                f"访问代理池失败：{self._error_summary(last_error)}"
            ) from last_error
        raise CtripProxyError("代理池当前没有新的可用候选代理")

    async def _delete_proxy(self, proxy: str) -> None:
        """从 proxy_pool 删除经携程实测不可用的代理。"""
        self._invalidate_proxy_guid(proxy)
        try:
            response = await self._get_proxy_pool_client().get(
                f"{self.proxy_pool_url}/delete/",
                params={"proxy": proxy},
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Failed to delete Ctrip proxy %s from pool: %s",
                self._proxy_label(proxy),
                self._error_summary(exc),
            )

    async def _request_flight_detail(
        self,
        client: httpx.AsyncClient,
        guid: str,
        flight_no: str,
        flight_date: str,
        d_port: str,
        a_port: str,
    ) -> dict:
        """用指定会话和 GUID 调用携程航班详情接口。"""
        now_ms = int(time.time() * 1000)
        vid_rand = _rand_str(12)
        vid = f"{now_ms}.{vid_rand}"
        bfa = f"1.{now_ms}.{vid_rand}.1.{now_ms}.{now_ms}.1.1.0"
        trace_id = f"{guid}-{now_ms}-{random.randint(100000, 999999)}"

        url = "https://m.ctrip.com/restapi/soa2/14566/FlightVarDetailSearchV2"
        params = {
            "_fxpcqlniredt": guid,
            "x-traceID": trace_id,
        }
        headers = {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "cookieorigin": "https://flights.ctrip.com",
            "locale": "zh-CN",
            "origin": "https://flights.ctrip.com",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://flights.ctrip.com/",
            "sec-ch-ua": (
                '\"Google Chrome\";v=\"150\", \"Chromium\";v=\"150\", '
                '\"Not)A;Brand\";v=\"24\"'
            ),
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '\"Windows\"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/150.0.0.0 Safari/537.36"
            ),
            "x-ctx-locale": "zh-CN",
            "x-ctx-wclient-req": _rand_str(32),
        }
        cookies = {
            "GUID": guid,
            "UBT_VID": vid,
            "_bfa": bfa,
        }
        payload = {
            "fltItem": {
                "aPort": a_port,
                "dPort": d_port,
                "fltno": flight_no,
                "queryDate": flight_date,
            },
            "head": {
                "cid": guid,
                "ctok": "",
                "cver": "1.0",
                "lang": "01",
                "sid": "8888",
                "syscode": "09",
                "auth": "",
                "xsid": "",
                "extension": [
                    {"name": "i18n.locale", "value": "zh_CN"},
                    {"name": "source", "value": "online"},
                ],
                "Locale": "zh-CN",
                "Language": "",
                "Currency": "",
                "ClientID": guid,
            },
        }
        response = await client.post(
            url,
            params=params,
            headers=headers,
            cookies=cookies,
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("携程航班详情接口返回的不是 JSON 对象")
        return data

    @staticmethod
    def _extract_times(data: dict) -> Optional[Dict[str, str]]:
        if not data:
            return None
        detail_item = data.get("detailItem") or {}
        basic_item_info = detail_item.get("basicItemInfo") or {}
        d_item_info = basic_item_info.get("dItemInfo") or {}
        date_time_record = d_item_info.get("dateTimeForRecord") or {}
        return {
            "planned_time": date_time_record.get("plannedDateTime"),
            "ready_time": date_time_record.get("ReadyDateTime"),
            "actual_time": date_time_record.get("actualDateTime"),
        }

    async def _query_direct(
        self,
        flight_no: str,
        flight_date: str,
        d_port: str,
        a_port: str,
    ) -> Optional[Dict[str, str]]:
        """保留原有直连模式的两次 GUID 刷新重试行为。"""
        client = self._get_client()
        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                guid = await self._ensure_guid()
                data = await self._request_flight_detail(
                    client,
                    guid,
                    flight_no,
                    flight_date,
                    d_port,
                    a_port,
                )
                ack = (data.get("ResponseStatus") or {}).get("Ack", "")
                if ack == "Success":
                    return self._extract_times(data)
                if attempt == 0:
                    logger.warning(
                        "Ctrip API Ack=%s for %s %s, refreshing GUID and retrying",
                        ack,
                        flight_no,
                        flight_date,
                    )
                    self._invalidate_guid()
                    continue
                return None
            except Exception as exc:
                last_error = exc
                if attempt == 0:
                    logger.warning(
                        "Ctrip request failed for %s %s (attempt 1), "
                        "refreshing GUID and retrying: %s",
                        flight_no,
                        flight_date,
                        self._error_summary(exc),
                    )
                    self._invalidate_guid()
                    continue
        if last_error:
            raise last_error
        return None

    async def _query_via_proxy_pool(
        self,
        flight_no: str,
        flight_date: str,
        d_port: str,
        a_port: str,
    ) -> Optional[Dict[str, str]]:
        """逐个代理查询；网络/HTTP/非法响应失败时删除并换下一个 IP。"""
        attempted: Set[str] = set()
        last_error: Optional[Exception] = None

        for proxy_attempt in range(1, self.proxy_max_attempts + 1):
            raw_proxy, proxy_url = await self._acquire_proxy(attempted)
            attempted.add(raw_proxy)
            client: Optional[httpx.AsyncClient] = None
            try:
                client = self._make_proxy_client(proxy_url)
                # Ack 失败通常是 GUID 失效，并不等同于代理失效；同一代理仅刷新一次。
                for guid_attempt in range(2):
                    guid = await self._ensure_proxy_guid(raw_proxy, client)
                    data = await self._request_flight_detail(
                        client,
                        guid,
                        flight_no,
                        flight_date,
                        d_port,
                        a_port,
                    )
                    ack = (data.get("ResponseStatus") or {}).get("Ack", "")
                    if ack == "Success":
                        return self._extract_times(data)
                    if guid_attempt == 0:
                        logger.warning(
                            "Ctrip API Ack=%s via proxy %s for %s %s; "
                            "refreshing GUID once",
                            ack,
                            self._proxy_label(raw_proxy),
                            flight_no,
                            flight_date,
                        )
                        self._invalidate_proxy_guid(raw_proxy)
                        continue
                    return None
            except Exception as exc:
                if not self._is_proxy_failure(exc):
                    raise
                last_error = exc
                await self._delete_proxy(raw_proxy)
                logger.warning(
                    "Ctrip proxy %s failed for %s %s (proxy attempt %s/%s); "
                    "deleted and switching IP: %s",
                    self._proxy_label(raw_proxy),
                    flight_no,
                    flight_date,
                    proxy_attempt,
                    self.proxy_max_attempts,
                    self._error_summary(exc),
                )
            finally:
                if client is not None:
                    try:
                        await client.aclose()
                    except Exception as exc:
                        logger.debug(
                            "Failed to close Ctrip proxy client %s: %s",
                            self._proxy_label(raw_proxy),
                            self._error_summary(exc),
                        )

        if last_error:
            raise CtripProxyError(
                f"{self.proxy_max_attempts} 个携程代理均请求失败，最后错误："
                f"{self._error_summary(last_error)}"
            ) from last_error
        raise CtripProxyError("没有可用的携程代理")

    async def get_flight_times(
        self,
        flight_no: str,
        flight_date: str,
        routing: str,
        force_refresh: bool = False,
    ) -> Optional[Dict[str, str]]:
        """
        获取航班预飞、计飞和实飞时间。

        代理功能关闭时保持原有直连行为；开启时从 proxy_pool 获取 HTTPS
        代理，并在 430、超时、连接失败或非法响应后删除坏代理并换 IP。
        """
        if not flight_no or not routing or not flight_date:
            return None

        flight_no_clean = str(flight_no).strip().upper()
        if isinstance(flight_date, (datetime, date)):
            flight_date_clean = flight_date.strftime("%Y-%m-%d")
        else:
            flight_date_text = str(flight_date).strip().replace("/", "-")
            date_match = re.match(r"^(\d{4}-\d{1,2}-\d{1,2})", flight_date_text)
            if not date_match:
                logger.warning("Invalid flight date for Ctrip query: %r", flight_date)
                return None
            try:
                flight_date_clean = datetime.strptime(
                    date_match.group(1), "%Y-%m-%d"
                ).strftime("%Y-%m-%d")
            except ValueError:
                logger.warning("Invalid flight date for Ctrip query: %r", flight_date)
                return None

        routing_parts = [part.strip().upper() for part in str(routing).split("-")]
        if len(routing_parts) != 2 or not all(routing_parts):
            logger.warning("Invalid routing for Ctrip query: %r", routing)
            return None
        routing_clean = "-".join(routing_parts)
        d_port, a_port = routing_parts

        cache_key = (flight_no_clean, flight_date_clean, routing_clean)
        if not force_refresh and cache_key in self._cache:
            ts, cached_data = self._cache[cache_key]
            if (time.time() - ts) < self.CACHE_TTL:
                return cached_data

        async with self.semaphore:
            if not force_refresh and cache_key in self._cache:
                ts, cached_data = self._cache[cache_key]
                if (time.time() - ts) < self.CACHE_TTL:
                    return cached_data

            try:
                if self.proxy_enabled:
                    result = await self._query_via_proxy_pool(
                        flight_no_clean,
                        flight_date_clean,
                        d_port,
                        a_port,
                    )
                else:
                    result = await self._query_direct(
                        flight_no_clean,
                        flight_date_clean,
                        d_port,
                        a_port,
                    )
            except Exception as exc:
                logger.error(
                    "Ctrip request failed for %s %s: %s",
                    flight_no_clean,
                    flight_date_clean,
                    self._error_summary(exc),
                )
                if not force_refresh and cache_key in self._cache:
                    return self._cache[cache_key][1]
                return None

            if result is not None:
                self._cache[cache_key] = (time.time(), result)
            return result


ctrip_client = CtripClient()
