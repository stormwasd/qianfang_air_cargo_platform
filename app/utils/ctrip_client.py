import time
import random
import string
import asyncio
import httpx
from typing import Optional, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


def _rand_str(n: int = 12) -> str:
    """生成指定长度的随机字符串"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(n))


class CtripClient:
    """
    携程航班接口客户端（增强版）
    - 动态 GUID 缓存
    - 5分钟 TTL 内存缓存（高性能、防频繁刷接口及限流）
    - 异步 Semaphore 并发控制
    - 多 EventLoop 安全锁与 HTTP Client 复用
    """

    GUID_TTL = 30 * 60  # GUID 有效期 30 分钟
    CACHE_TTL = 5 * 60  # 航班时间查询结果缓存 5 分钟

    def __init__(self):
        self._guid: Optional[str] = None
        self._guid_ts: float = 0.0
        self._locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}
        self._semaphores: Dict[asyncio.AbstractEventLoop, asyncio.Semaphore] = {}
        self._clients: Dict[asyncio.AbstractEventLoop, httpx.AsyncClient] = {}
        
        # 航班时间结果缓存: (flight_no, flight_date, routing) -> (timestamp, data_dict)
        self._cache: Dict[Tuple[str, str, str], Tuple[float, Dict[str, str]]] = {}

    @property
    def lock(self) -> asyncio.Lock:
        """根据当前的 event loop 动态获取或创建锁"""
        loop = asyncio.get_running_loop()
        if loop not in self._locks:
            self._locks[loop] = asyncio.Lock()
        return self._locks[loop]

    @property
    def semaphore(self) -> asyncio.Semaphore:
        """限制单 loop 内对携程 API 的最大并发请求数（如最多 5 个并发）"""
        loop = asyncio.get_running_loop()
        if loop not in self._semaphores:
            self._semaphores[loop] = asyncio.Semaphore(5)
        return self._semaphores[loop]

    def _get_client(self) -> httpx.AsyncClient:
        """每个 event loop 共享一个 httpx.AsyncClient 连接池"""
        loop = asyncio.get_running_loop()
        if loop not in self._clients or self._clients[loop].is_closed:
            self._clients[loop] = httpx.AsyncClient(timeout=15.0, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20))
        return self._clients[loop]

    def _is_guid_valid(self) -> bool:
        """判断当前缓存的 GUID 是否仍然有效"""
        if not self._guid:
            return False
        return (time.time() - self._guid_ts) < self.GUID_TTL

    async def _fetch_guid(self) -> str:
        """向携程 createclientid 接口请求一个新的 GUID"""
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
        client = self._get_client()
        resp = await client.get(url, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        guid = data.get("ClientID")
        if not guid:
            raise ValueError(f"createclientid 返回数据缺少 ClientID: {data}")
        return guid

    async def _ensure_guid(self) -> str:
        """确保有一个可用的 GUID，过期或缺失时自动刷新"""
        if self._is_guid_valid():
            return self._guid  # type: ignore

        async with self.lock:
            if self._is_guid_valid():
                return self._guid  # type: ignore
            self._guid = await self._fetch_guid()
            self._guid_ts = time.time()
            logger.info("Ctrip GUID refreshed: %s", self._guid)
            return self._guid

    def _invalidate_guid(self):
        """标记当前 GUID 已失效，下次请求时会重新获取"""
        self._guid = None
        self._guid_ts = 0.0

    async def get_flight_times(
        self, flight_no: str, flight_date: str, routing: str,
        force_refresh: bool = False
    ) -> Optional[Dict[str, str]]:
        """
        获取航班的各维度的起飞时间（具备 5 分钟内存 TTL 缓存及并发保护）

        :param flight_no: 航班号 (例如: ZH9947)
        :param flight_date: 航班日期 (例如: 2026-06-12)
        :param routing: 航程 (例如: SZX-HFE)
        :param force_refresh: 是否跳过本地缓存并强制请求携程（实飞轮询使用）
        :return: 包含 planned_time(预飞时间)、ready_time(计飞时间)、
                 actual_time(实飞时间) 的字典，获取失败返回 None
        """
        if not flight_no or not routing:
            return None

        flight_no_clean = flight_no.strip().upper()
        routing_clean = routing.strip().upper()
        flight_date_clean = flight_date.strip()

        ports = routing_clean.split("-") if routing_clean else []
        if len(ports) != 2:
            return None
        d_port, a_port = ports[0], ports[1]

        cache_key = (flight_no_clean, flight_date_clean, routing_clean)
        now_ts = time.time()

        # 1. 优先查 5 分钟 TTL 内存缓存
        if not force_refresh and cache_key in self._cache:
            ts, cached_data = self._cache[cache_key]
            if (now_ts - ts) < self.CACHE_TTL:
                return cached_data

        # 2. 并发限流控制
        async with self.semaphore:
            # 二次检查缓存
            if not force_refresh and cache_key in self._cache:
                ts, cached_data = self._cache[cache_key]
                if (now_ts - ts) < self.CACHE_TTL:
                    return cached_data

            for attempt in range(2):
                try:
                    guid = await self._ensure_guid()

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
                            '"Google Chrome";v="150", "Chromium";v="150", '
                            '"Not)A;Brand";v="24"'
                        ),
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
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
                            "fltno": flight_no_clean,
                            "queryDate": flight_date_clean,
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

                    client = self._get_client()
                    response = await client.post(
                        url,
                        params=params,
                        headers=headers,
                        cookies=cookies,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if not data:
                        return None

                    resp_status = data.get("ResponseStatus") or {}
                    ack = resp_status.get("Ack", "")
                    if ack != "Success":
                        if attempt == 0:
                            logger.warning(
                                "Ctrip API Ack=%s for %s %s, refreshing GUID and retrying",
                                ack, flight_no_clean, flight_date_clean,
                            )
                            self._invalidate_guid()
                            continue
                        return None

                    detail_item = data.get("detailItem") or {}
                    basic_item_info = detail_item.get("basicItemInfo") or {}
                    d_item_info = basic_item_info.get("dItemInfo") or {}
                    date_time_record = d_item_info.get("dateTimeForRecord") or {}

                    planned_time = date_time_record.get("plannedDateTime")
                    ready_time = date_time_record.get("ReadyDateTime")
                    actual_time = date_time_record.get("actualDateTime")

                    res = {
                        "planned_time": planned_time,
                        "ready_time": ready_time,
                        "actual_time": actual_time,
                    }
                    
                    # 缓存有效查询结果
                    self._cache[cache_key] = (time.time(), res)
                    return res

                except Exception as e:
                    if attempt == 0:
                        logger.warning(
                            "Ctrip request failed for %s %s (attempt 1), "
                            "refreshing GUID and retrying: %s",
                            flight_no_clean, flight_date_clean, e,
                        )
                        self._invalidate_guid()
                        continue
                    logger.error(
                        "Ctrip request failed for %s %s (attempt 2): %s",
                        flight_no_clean, flight_date_clean, e,
                    )
                    # 如果发生异常但存在过期缓存，作为降级策略返回
                    if not force_refresh and cache_key in self._cache:
                        return self._cache[cache_key][1]
                    return None

        return None


ctrip_client = CtripClient()
