import time
import unittest
from unittest.mock import AsyncMock, MagicMock

import httpx

from app.utils.ctrip_client import CtripClient, CtripProxyError


def _success_response():
    return {
        "ResponseStatus": {"Ack": "Success"},
        "detailItem": {
            "basicItemInfo": {
                "dItemInfo": {
                    "dateTimeForRecord": {
                        "plannedDateTime": "2026-09-18 10:00:00",
                        "ReadyDateTime": "2026-09-18 10:15:00",
                        "actualDateTime": "2026-09-18 10:20:00",
                    }
                }
            }
        },
    }


def _http_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request(
        "GET",
        "https://m.ctrip.com/restapi/soa2/10290/createclientid",
    )
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"HTTP {status_code}",
        request=request,
        response=response,
    )


class _FakeProxyClient:
    def __init__(self):
        self.aclose = AsyncMock()


class CtripClientProxyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.client = CtripClient(
            proxy_enabled=True,
            proxy_pool_url="http://proxy-pool:5010/",
            proxy_max_attempts=3,
            proxy_pool_timeout=1.0,
        )

    async def test_430_deletes_bad_proxy_and_switches_to_next_ip(self):
        proxy_clients = [_FakeProxyClient(), _FakeProxyClient()]
        self.client._acquire_proxy = AsyncMock(
            side_effect=[
                ("1.1.1.1:8000", "http://1.1.1.1:8000"),
                ("2.2.2.2:9000", "http://2.2.2.2:9000"),
            ]
        )
        self.client._make_proxy_client = MagicMock(side_effect=proxy_clients)
        self.client._ensure_proxy_guid = AsyncMock(
            side_effect=[_http_error(430), "guid-from-second-proxy"]
        )
        self.client._request_flight_detail = AsyncMock(
            return_value=_success_response()
        )
        self.client._delete_proxy = AsyncMock()

        result = await self.client._query_via_proxy_pool(
            "ZH9505", "2026-09-18", "SZX", "SHA"
        )

        self.assertEqual(result["ready_time"], "2026-09-18 10:15:00")
        self.client._delete_proxy.assert_awaited_once_with("1.1.1.1:8000")
        self.assertEqual(self.client._acquire_proxy.await_count, 2)
        self.assertEqual(
            self.client._request_flight_detail.await_args.args[1],
            "guid-from-second-proxy",
        )
        proxy_clients[0].aclose.assert_awaited_once()
        proxy_clients[1].aclose.assert_awaited_once()

    async def test_ack_failure_refreshes_guid_without_deleting_proxy(self):
        proxy_client = _FakeProxyClient()
        self.client._acquire_proxy = AsyncMock(
            return_value=("3.3.3.3:8080", "http://3.3.3.3:8080")
        )
        self.client._make_proxy_client = MagicMock(return_value=proxy_client)
        self.client._ensure_proxy_guid = AsyncMock(
            side_effect=["old-guid", "new-guid"]
        )
        self.client._request_flight_detail = AsyncMock(
            side_effect=[
                {"ResponseStatus": {"Ack": "Failure"}},
                _success_response(),
            ]
        )
        self.client._delete_proxy = AsyncMock()

        result = await self.client._query_via_proxy_pool(
            "ZH9503", "2026-09-18", "SZX", "PEK"
        )

        self.assertEqual(result["actual_time"], "2026-09-18 10:20:00")
        self.client._delete_proxy.assert_not_awaited()
        self.assertEqual(self.client._ensure_proxy_guid.await_count, 2)
        self.assertNotIn("3.3.3.3:8080", self.client._proxy_guids)

    async def test_non_proxy_http_error_does_not_empty_proxy_pool(self):
        proxy_client = _FakeProxyClient()
        self.client._acquire_proxy = AsyncMock(
            return_value=("7.7.7.7:8080", "http://7.7.7.7:8080")
        )
        self.client._make_proxy_client = MagicMock(return_value=proxy_client)
        self.client._ensure_proxy_guid = AsyncMock(
            side_effect=_http_error(404)
        )
        self.client._delete_proxy = AsyncMock()

        with self.assertRaises(httpx.HTTPStatusError):
            await self.client._query_via_proxy_pool(
                "ZH9503", "2026-09-18", "SZX", "PEK"
            )

        self.client._delete_proxy.assert_not_awaited()
        self.assertEqual(self.client._acquire_proxy.await_count, 1)
        proxy_client.aclose.assert_awaited_once()

    async def test_guid_is_cached_per_proxy(self):
        proxy_client = _FakeProxyClient()
        self.client._fetch_guid = AsyncMock(return_value="proxy-guid")

        first = await self.client._ensure_proxy_guid(
            "4.4.4.4:8080", proxy_client
        )
        second = await self.client._ensure_proxy_guid(
            "4.4.4.4:8080", proxy_client
        )

        self.assertEqual(first, "proxy-guid")
        self.assertEqual(second, "proxy-guid")
        self.client._fetch_guid.assert_awaited_once_with(proxy_client)

    async def test_empty_https_set_falls_back_to_http_proxy_candidate(self):
        request = httpx.Request("GET", "http://proxy-pool:5010/get/")
        no_https_proxy = httpx.Response(
            200,
            json={"code": 0, "src": "no proxy"},
            request=request,
        )
        http_candidate = httpx.Response(
            200,
            json={"proxy": "6.6.6.6:8080", "https": False},
            request=request,
        )
        pool_client = MagicMock()
        pool_client.get = AsyncMock(
            side_effect=[no_https_proxy, http_candidate]
        )
        self.client._get_proxy_pool_client = MagicMock(
            return_value=pool_client
        )

        raw_proxy, proxy_url = await self.client._acquire_proxy(set())

        self.assertEqual(raw_proxy, "6.6.6.6:8080")
        self.assertEqual(proxy_url, "http://6.6.6.6:8080")
        self.assertEqual(
            pool_client.get.await_args_list[0].kwargs["params"],
            {"type": "https"},
        )
        self.assertIsNone(pool_client.get.await_args_list[1].kwargs["params"])

    async def test_completely_empty_pool_fails_after_two_lookups(self):
        request = httpx.Request("GET", "http://proxy-pool:5010/get/")
        no_proxy = httpx.Response(
            200,
            json={"code": 0, "src": "no proxy"},
            request=request,
        )
        pool_client = MagicMock()
        pool_client.get = AsyncMock(return_value=no_proxy)
        self.client._get_proxy_pool_client = MagicMock(
            return_value=pool_client
        )

        with self.assertRaisesRegex(CtripProxyError, "没有可用候选代理"):
            await self.client._acquire_proxy(set())

        self.assertEqual(pool_client.get.await_count, 2)

    async def test_all_proxy_failures_fall_back_to_expired_cache(self):
        cache_key = ("ZH9505", "2026-09-18", "SZX-SHA")
        stale = {
            "planned_time": "old-planned",
            "ready_time": "old-ready",
            "actual_time": None,
        }
        self.client._cache[cache_key] = (time.time() - 3600, stale)
        self.client._query_via_proxy_pool = AsyncMock(
            side_effect=CtripProxyError("no usable proxy")
        )

        result = await self.client.get_flight_times(
            "zh9505", "2026/9/18 00:00:00", " szx - sha "
        )

        self.assertIs(result, stale)

    async def test_success_is_normalized_and_cached_for_existing_callers(self):
        expected = {
            "planned_time": "planned",
            "ready_time": "ready",
            "actual_time": None,
        }
        self.client._query_via_proxy_pool = AsyncMock(return_value=expected)

        first = await self.client.get_flight_times(
            " zh9505 ", "2026/9/18 00:00:00", " szx - sha "
        )
        second = await self.client.get_flight_times(
            "ZH9505", "2026-09-18", "SZX-SHA"
        )

        self.assertIs(first, expected)
        self.assertIs(second, expected)
        self.client._query_via_proxy_pool.assert_awaited_once_with(
            "ZH9505", "2026-09-18", "SZX", "SHA"
        )

    def test_proxy_normalization_and_log_redaction(self):
        proxy = "user:secret@5.5.5.5:3128"
        self.assertEqual(
            self.client._normalize_proxy(proxy),
            "http://user:secret@5.5.5.5:3128",
        )
        self.assertEqual(self.client._proxy_label(proxy), "5.5.5.5:3128")


class CtripClientDirectCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_proxy_keeps_direct_path(self):
        client = CtripClient(proxy_enabled=False)
        expected = {
            "planned_time": "planned",
            "ready_time": "ready",
            "actual_time": None,
        }
        client._query_direct = AsyncMock(return_value=expected)
        client._query_via_proxy_pool = AsyncMock()

        result = await client.get_flight_times(
            "ZH9505", "2026-09-18", "SZX-SHA", force_refresh=True
        )

        self.assertEqual(result, expected)
        client._query_direct.assert_awaited_once()
        client._query_via_proxy_pool.assert_not_awaited()
