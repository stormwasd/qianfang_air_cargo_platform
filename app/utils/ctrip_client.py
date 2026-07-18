import time
import random
import string
import asyncio
import httpx
from typing import Optional, Dict
import logging

logger = logging.getLogger(__name__)


def _rand_str(n: int = 12) -> str:
    """生成指定长度的随机字符串"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(n))


class CtripClient:
    """携程航班接口客户端（动态 GUID 缓存版）"""

    GUID_TTL = 30 * 60

    def __init__(self):
        self._guid: Optional[str] = None
        self._guid_ts: float = 0.0  
        self._locks: Dict[asyncio.AbstractEventLoop, asyncio.Lock] = {}

    @property
    def lock(self) -> asyncio.Lock:
        """根据当前的 event loop 动态获取或创建锁，防止多事件循环并发访问报错"""
        loop = asyncio.get_running_loop()
        if loop not in self._locks:
            self._locks[loop] = asyncio.Lock()
        return self._locks[loop]


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
        async with httpx.AsyncClient(timeout=10.0) as client:
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
        self, flight_no: str, flight_date: str, routing: str
    ) -> Optional[Dict[str, str]]:
        """
        获取航班的各维度的起飞时间

        :param flight_no: 航班号 (例如: ZH9947)
        :param flight_date: 航班日期 (例如: 2026-06-12)
        :param routing: 航程 (例如: SZX-HFE)
        :return: 包含 planned_time(预飞时间)、ready_time(计飞时间)、
                 actual_time(实飞时间) 的字典，获取失败返回 None
        """
        if not flight_no or not routing:
            return None

        ports = routing.split("-") if routing else []
        if len(ports) != 2:
            return None
        d_port, a_port = ports[0], ports[1]

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

                async with httpx.AsyncClient(timeout=20.0) as client:
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
                            ack, flight_no, flight_date,
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

                return {
                    "planned_time": planned_time,
                    "ready_time": ready_time,
                    "actual_time": actual_time,
                }

            except Exception as e:
                if attempt == 0:
                    logger.warning(
                        "Ctrip request failed for %s %s (attempt 1), "
                        "refreshing GUID and retrying: %s",
                        flight_no, flight_date, e,
                    )
                    self._invalidate_guid()
                    continue
                logger.error(
                    "Ctrip request failed for %s %s (attempt 2): %s",
                    flight_no, flight_date, e,
                )
                return None

        return None  


ctrip_client = CtripClient()
