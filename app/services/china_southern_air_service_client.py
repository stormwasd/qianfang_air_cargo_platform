"""南航 B2B 业务接口客户端。"""
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx

from app.services.china_southern_air_field_utils import (
    merge_special_cargo_codes,
    normalize_special_cargo_code,
)


class ChinaSouthernAirServiceError(Exception):
    """南航 B2B 接口调用或响应不符合预期，并保留安全的诊断信息。"""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.details = deepcopy(details) if details is not None else None


class ChinaSouthernAirService:
    """封装不经过 RPA 的南航 B2B 查询接口。"""

    SHIPMENT_TYPE_URL = (
        "https://cargo.csair.com/order-center/b2e-support/cesStaticdata/"
        "listShipmentTypeByChannelandOrigin"
    )
    SERVICE_CHARGE_URL = (
        "https://cargo.csair.com/order-center/b2e-order/b2eOrder/queryServiceCharge"
    )
    CALCULATE_CWEIGHT_URL = (
        "https://cargo.csair.com/order-center/b2e-order/b2eOrder/calculateCWeight"
    )
    SHIPMENT_SUB_PRODUCT_CODE_URL = (
        "https://cargo.csair.com/order-center/b2e-support/cesStaticdata/"
        "queryShipmentSubProductCode"
    )
    FLIGHT_PRICE_URL = (
        "https://cargo.csair.com/order-center/b2e-flight/"
        "cesB2eFlightPrice/queryB2eFlightPrice"
    )
    DEPARTURE_CARGO_MAIL_HANDLING_CHARGE = "出港货邮处理费"

    @staticmethod
    def _clean_token(token: Any) -> str:
        """兼容 RPA 入库时可能遗留的转义换行或包裹引号。"""
        text = "" if token is None else str(token)
        for _ in range(3):
            previous = text
            text = text.replace("\\r", "").replace("\\n", "").replace("\\t", "")
            text = text.replace("\r", "").replace("\n", "").replace("\t", "")
            text = text.strip().strip('"').strip("'").strip("\\").strip()
            if text == previous:
                break
        return text

    @staticmethod
    def _response_message(response_data: Dict[str, Any], fallback: str) -> str:
        """优先展示南航 detailedMessage 中真正的业务错误。"""
        if not isinstance(response_data, dict):
            return fallback
        detailed = response_data.get("detailedMessage")
        if isinstance(detailed, dict):
            detailed = detailed.get("message") or detailed.get("detailedMessage")
        if detailed:
            return str(detailed)
        return str(response_data.get("message") or fallback)

    @staticmethod
    def normalize_shipment_types(response_data: Any) -> List[Dict[str, str]]:
        """校验南航货物类型响应并转换为数据字典的 label/value 列表。"""
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirServiceError("南航货物类型服务返回格式异常")
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            upstream_message = ChinaSouthernAirService._response_message(
                response_data,
                "南航货物类型查询失败",
            )
            if "获取Token为空" in upstream_message:
                upstream_message = (
                    "南航接口拒绝Token：获取Token为空，可能已过期或失效"
                )
            raise ChinaSouthernAirServiceError(
                upstream_message
            )

        result = response_data.get("result")
        if not isinstance(result, list) or not result:
            raise ChinaSouthernAirServiceError("南航货物类型服务未返回可用数据")

        normalized: List[Dict[str, str]] = []
        seen_labels: Dict[str, str] = {}
        for index, item in enumerate(result):
            if not isinstance(item, dict):
                raise ChinaSouthernAirServiceError(
                    f"南航货物类型第 {index + 1} 项格式异常"
                )
            label = str(item.get("shipmentTypeName") or "").strip()
            value = str(item.get("shipmentType") or "").strip()
            if not label or not value:
                raise ChinaSouthernAirServiceError(
                    f"南航货物类型第 {index + 1} 项缺少 shipmentTypeName 或 shipmentType"
                )

            previous_value = seen_labels.get(label)
            if previous_value is not None:
                if previous_value != value:
                    raise ChinaSouthernAirServiceError(
                        f"南航货物类型名称“{label}”对应了多个不同代码"
                    )
                # 完全相同的重复项只写入一次，避免破坏按 label 查询的唯一性。
                continue

            seen_labels[label] = value
            normalized.append({"label": label, "value": value})

        return normalized

    async def query_shipment_types(
        self,
        *,
        token: str,
        origin: str = "SZX",
        destination: str = "TAO",
        channel: str = "B",
        direct_transfer: str = "D",
        customer_no: str = "SZXFED",
    ) -> List[Dict[str, str]]:
        """查询南航货物类型，并返回可直接覆盖数据字典的选项。"""
        cleaned_token = self._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirServiceError("南航登录令牌无效，请先刷新南航 Token")

        params = {
            "origin": origin,
            "dest": destination,
            "channel": channel,
            "directTransfer": direct_transfer,
            "customerno": customer_no,
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": customer_no,
        }

        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.SHIPMENT_TYPE_URL,
                    params=params,
                    headers=headers,
                    content=b"",
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = self._response_message(exc.response.json(), "")
            except (ValueError, TypeError):
                detail = exc.response.text.strip()
            suffix = f"：{detail}" if detail else ""
            raise ChinaSouthernAirServiceError(
                f"南航货物类型查询失败（HTTP {exc.response.status_code}）{suffix}"
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirServiceError("南航货物类型服务暂时不可用") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirServiceError("南航货物类型服务返回了无效数据") from exc
        return self.normalize_shipment_types(response_data)

    async def query_service_charges(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        flight_number: str,
        flight_date: str,
        cargo_type: str,
        cargo_name: str,
    ) -> List[Dict[str, Any]]:
        """查询并返回南航完整的扩展服务费列表。"""
        cleaned_token = self._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirServiceError("南航登录令牌无效，请先刷新南航 Token")

        payload = {
            "resAllInfoList": [{"resDto": {
                "flightDep": origin_station,
                "flightDest": destination,
                "bookFlightno": flight_number,
                "bookFlightdate": flight_date,
            }}],
            "routing": f"{origin_station}/{destination}",
            "shipmentType": cargo_type,
            "shipmentTypeName": cargo_name,
            "channel": "B2B",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
        }

        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.SERVICE_CHARGE_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = self._response_message(exc.response.json(), "")
            except (ValueError, TypeError):
                detail = exc.response.text.strip()
            suffix = f"：{detail}" if detail else ""
            raise ChinaSouthernAirServiceError(
                f"南航出港货邮处理费查询失败（HTTP {exc.response.status_code}）{suffix}"
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirServiceError("南航出港货邮处理费服务暂时不可用") from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirServiceError("南航出港货邮处理费服务返回了无效数据") from exc
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirServiceError("南航出港货邮处理费服务返回格式异常")
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirServiceError(
                self._response_message(response_data, "南航出港货邮处理费查询失败")
            )

        result = response_data.get("result")
        service_charges = result.get("extServiceCharges") if isinstance(result, dict) else None
        if not isinstance(service_charges, list):
            raise ChinaSouthernAirServiceError("南航出港货邮处理费服务未返回完整费用选项")
        if not all(isinstance(item, dict) for item in service_charges):
            raise ChinaSouthernAirServiceError("南航出港货邮处理费服务返回的费用选项格式异常")
        return service_charges

    async def calculate_default_volume(
        self,
        *,
        token: str,
        origin_station: str,
        weight: Any,
        customer_no: str = "SZXFED",
        cookie: Optional[str] = None,
    ) -> float:
        """按南航计费重量接口计算未填写时使用的默认订舱体积。"""
        cleaned_token = self._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirServiceError("南航登录令牌无效，请先刷新南航 Token")

        payload = {
            "dimensions": None,
            "volume": "",
            "weight": weight,
            "channel": "B2B",
            "depCityCode": str(origin_station or "").strip().upper(),
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": str(customer_no or "SZXFED").strip(),
        }
        if cookie:
            headers["Cookie"] = str(cookie)

        def error_details(
            *,
            upstream_response: Any = None,
            http_status: Optional[int] = None,
            network_error: Optional[str] = None,
        ) -> Dict[str, Any]:
            details: Dict[str, Any] = {
                "stage": "calculate_cweight",
                "request_data": deepcopy(payload),
            }
            if upstream_response is not None:
                details["upstream_response"] = deepcopy(upstream_response)
            if http_status is not None:
                details["http_status"] = http_status
            if network_error:
                details["network_error"] = network_error
            return details

        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.CALCULATE_CWEIGHT_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                upstream_response = exc.response.json()
            except (ValueError, TypeError):
                upstream_response = exc.response.text
            raise ChinaSouthernAirServiceError(
                f"南航默认订舱体积计算失败（HTTP {exc.response.status_code}）",
                details=error_details(
                    upstream_response=upstream_response,
                    http_status=exc.response.status_code,
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirServiceError(
                "南航默认订舱体积计算服务暂时不可用",
                details=error_details(network_error=str(exc)),
            ) from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirServiceError(
                "南航默认订舱体积计算服务返回了无效数据",
                details=error_details(
                    upstream_response=response.text,
                    http_status=response.status_code,
                ),
            ) from exc
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirServiceError(
                "南航默认订舱体积计算服务返回格式异常",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirServiceError(
                self._response_message(response_data, "南航默认订舱体积计算失败"),
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )

        result = response_data.get("result")
        raw_volume = result.get("volume") if isinstance(result, dict) else None
        try:
            if isinstance(raw_volume, bool):
                raise ValueError
            volume = float(raw_volume)
        except (TypeError, ValueError) as exc:
            raise ChinaSouthernAirServiceError(
                "南航默认订舱体积计算未返回有效 volume",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            ) from exc
        if volume <= 0:
            raise ChinaSouthernAirServiceError(
                "南航默认订舱体积计算返回的 volume 必须大于 0",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )
        return volume

    async def resolve_booking_volume(
        self,
        *,
        token: str,
        origin_station: str,
        weight: Any,
        volume: Any,
        customer_no: str = "SZXFED",
        cookie: Optional[str] = None,
        cache: Optional[Dict[Any, float]] = None,
    ) -> Any:
        """用户已填写则原样返回，否则查询南航默认体积；缓存仅限调用方当前请求。"""
        if volume is not None and not (
            isinstance(volume, str) and not volume.strip()
        ):
            return volume

        cache_key = (
            str(customer_no or "SZXFED").strip(),
            str(origin_station or "").strip().upper(),
            str(weight),
        )
        if cache is not None and cache_key in cache:
            return cache[cache_key]

        resolved = await self.calculate_default_volume(
            token=token,
            origin_station=origin_station,
            weight=weight,
            customer_no=customer_no,
            cookie=cookie,
        )
        if cache is not None:
            cache[cache_key] = resolved
        return resolved

    async def query_default_special_cargo_code(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        shipment_type: str,
        product_name: str,
        cookie: Optional[str] = None,
    ) -> str:
        """查询南航当前航线、货物类型和产品对应的默认特货码。"""
        cleaned_token = self._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirServiceError("南航登录令牌无效，请先刷新南航 Token")

        params = {
            "dest": str(destination or "").strip().upper(),
            "origin": str(origin_station or "").strip().upper(),
            "shipmentType": str(shipment_type or "").strip(),
            "channel": "B",
            "productName": str(product_name or "").strip(),
            "directTransfer": "D",
            "customerno": "SZXFED",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": "SZXFED",
        }
        if cookie:
            headers["Cookie"] = str(cookie)

        def error_details(
            *,
            upstream_response: Any = None,
            http_status: Optional[int] = None,
            network_error: Optional[str] = None,
        ) -> Dict[str, Any]:
            details: Dict[str, Any] = {
                "stage": "query_shipment_sub_product_code",
                "request_data": deepcopy(params),
            }
            if upstream_response is not None:
                details["upstream_response"] = deepcopy(upstream_response)
            if http_status is not None:
                details["http_status"] = http_status
            if network_error:
                details["network_error"] = network_error
            return details

        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.SHIPMENT_SUB_PRODUCT_CODE_URL,
                    params=params,
                    headers=headers,
                    content=b"",
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                upstream_response = exc.response.json()
            except (ValueError, TypeError):
                upstream_response = exc.response.text
            raise ChinaSouthernAirServiceError(
                f"南航默认特货码查询失败（HTTP {exc.response.status_code}）",
                details=error_details(
                    upstream_response=upstream_response,
                    http_status=exc.response.status_code,
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirServiceError(
                "南航默认特货码查询服务暂时不可用",
                details=error_details(network_error=str(exc)),
            ) from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirServiceError(
                "南航默认特货码查询服务返回了无效数据",
                details=error_details(
                    upstream_response=response.text,
                    http_status=response.status_code,
                ),
            ) from exc
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirServiceError(
                "南航默认特货码查询服务返回格式异常",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirServiceError(
                self._response_message(response_data, "南航默认特货码查询失败"),
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )

        result = response_data.get("result")
        sub_code = result.get("subCode") if isinstance(result, dict) else None
        normalized_sub_code = merge_special_cargo_codes(sub_code, None)
        if not normalized_sub_code:
            raise ChinaSouthernAirServiceError(
                "南航默认特货码查询未返回有效 subCode",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )
        return normalized_sub_code

    async def resolve_special_cargo_code(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        shipment_type: str,
        product_name: str,
        user_special_cargo_code: Any,
        cookie: Optional[str] = None,
        cache: Optional[Dict[Any, str]] = None,
    ) -> Dict[str, str]:
        """查询默认特货码并与用户码合并，返回平台格式和南航格式。"""
        cache_key = (
            str(origin_station or "").strip().upper(),
            str(destination or "").strip().upper(),
            str(shipment_type or "").strip(),
            str(product_name or "").strip(),
        )
        if cache is not None and cache_key in cache:
            default_code = cache[cache_key]
        else:
            default_code = await self.query_default_special_cargo_code(
                token=token,
                origin_station=origin_station,
                destination=destination,
                shipment_type=shipment_type,
                product_name=product_name,
                cookie=cookie,
            )
            if cache is not None:
                cache[cache_key] = default_code

        platform_code = merge_special_cargo_codes(
            default_code,
            user_special_cargo_code,
        )
        csa_code = normalize_special_cargo_code(platform_code)
        if not platform_code or not csa_code:
            raise ChinaSouthernAirServiceError("南航特货码合并结果为空")
        return {
            "default_code": default_code,
            "platform_code": platform_code,
            "csa_code": csa_code,
        }

    async def query_flight_price_cabin_class(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        flight_number: str,
        flight_date: str,
        shipment_type_code: str,
        shipment_type_name: str,
        weight: Any,
        volume: Any,
        product_name: str,
        cookie: Optional[str] = None,
    ) -> Dict[str, str]:
        """查询产品对应的南航运价舱位，并返回 createOrder 所需舱位字段。"""
        cleaned_token = self._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirServiceError("南航登录令牌无效，请先刷新南航 Token")

        expected_product_name = str(product_name or "").strip()
        if not expected_product_name:
            raise ChinaSouthernAirServiceError("南航运价舱位查询缺少有效产品名称")

        payload = {
            "spaceClassParamMultDto": {
                "channel": "B",
                "customerCode": "SZXFED",
                "flights": [{
                    "flightDep": str(origin_station or "").strip().upper(),
                    "flightDest": str(destination or "").strip().upper(),
                    "flightNo": str(flight_number or "").strip().upper(),
                    "flightDate": str(flight_date or "").strip(),
                }],
                "rateCode": str(shipment_type_code or "").strip(),
            },
            "orderShipmentCreateDto": {
                "shipmentTypeName": str(shipment_type_name or "").strip(),
                "shipmentType": str(shipment_type_code or "").strip(),
                "weight": weight,
                "volume": volume,
                "dimensions": None,
                "rateType": "SPY",
            },
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": "SZXFED",
        }
        if cookie:
            headers["Cookie"] = str(cookie)

        def error_details(
            *,
            upstream_response: Any = None,
            http_status: Optional[int] = None,
            network_error: Optional[str] = None,
            available_products: Optional[List[str]] = None,
        ) -> Dict[str, Any]:
            details: Dict[str, Any] = {
                "stage": "query_b2e_flight_price",
                "request_data": deepcopy(payload),
                "expected_product_name": expected_product_name,
            }
            if available_products is not None:
                details["available_product_names"] = deepcopy(available_products)
            if upstream_response is not None:
                details["upstream_response"] = deepcopy(upstream_response)
            if http_status is not None:
                details["http_status"] = http_status
            if network_error:
                details["network_error"] = network_error
            return details

        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    self.FLIGHT_PRICE_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            try:
                upstream_response = exc.response.json()
            except (ValueError, TypeError):
                upstream_response = exc.response.text
            raise ChinaSouthernAirServiceError(
                f"南航运价舱位查询失败（HTTP {exc.response.status_code}）",
                details=error_details(
                    upstream_response=upstream_response,
                    http_status=exc.response.status_code,
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirServiceError(
                "南航运价舱位查询服务暂时不可用",
                details=error_details(network_error=str(exc)),
            ) from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirServiceError(
                "南航运价舱位查询服务返回了无效数据",
                details=error_details(
                    upstream_response=response.text,
                    http_status=response.status_code,
                ),
            ) from exc
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirServiceError(
                "南航运价舱位查询服务返回格式异常",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirServiceError(
                self._response_message(response_data, "南航运价舱位查询失败"),
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                ),
            )

        result = response_data.get("result")
        charges = result.get("charge") if isinstance(result, dict) else None
        if not isinstance(charges, list) or not charges:
            raise ChinaSouthernAirServiceError(
                "南航运价舱位查询未返回可用 charge",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                    available_products=[],
                ),
            )

        available_products: List[str] = []
        matched_cabins: List[Dict[str, str]] = []
        matched_product_found = False
        expected_key = expected_product_name.casefold()
        for charge in charges:
            if not isinstance(charge, dict):
                continue
            flight_price = charge.get("flightPriceCalculateResult")
            if not isinstance(flight_price, dict):
                continue
            parent_product_name = str(charge.get("parentProductionName") or "").strip()
            rate_name = str(flight_price.get("rateName") or "").strip()
            candidate_names = [
                name for name in (parent_product_name, rate_name) if name
            ]
            for candidate_name in candidate_names:
                if candidate_name not in available_products:
                    available_products.append(candidate_name)
            if not any(name.casefold() == expected_key for name in candidate_names):
                continue
            matched_product_found = True

            space_class = str(flight_price.get("spaceClass") or "").strip()
            sub_space_class = str(flight_price.get("subSpaceClass") or "").strip()
            if not space_class or not sub_space_class:
                continue
            matched_cabins.append({
                "book_grade": space_class,
                "space_class": space_class,
                "sub_space_class": sub_space_class,
                "product_name": parent_product_name or rate_name,
            })

        if not matched_cabins:
            options_text = "、".join(available_products) if available_products else "无"
            if matched_product_found:
                message = (
                    f"南航运价舱位中的产品“{expected_product_name}”"
                    "未返回有效 spaceClass 或 subSpaceClass"
                )
            else:
                message = (
                    f"南航运价舱位中没有产品“{expected_product_name}”；"
                    f"当前可选产品：{options_text}"
                )
            raise ChinaSouthernAirServiceError(
                message,
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                    available_products=available_products,
                ),
            )

        cabin_pairs = {
            (item["space_class"], item["sub_space_class"])
            for item in matched_cabins
        }
        if len(cabin_pairs) != 1:
            raise ChinaSouthernAirServiceError(
                f"南航运价舱位为产品“{expected_product_name}”返回了多个不同舱位",
                details=error_details(
                    upstream_response=response_data,
                    http_status=response.status_code,
                    available_products=available_products,
                ),
            )
        return matched_cabins[0]

    async def resolve_flight_price_cabin_class(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        flight_number: str,
        flight_date: str,
        shipment_type_code: str,
        shipment_type_name: str,
        weight: Any,
        volume: Any,
        product_name: str,
        cookie: Optional[str] = None,
        cache: Optional[Dict[Any, Dict[str, str]]] = None,
    ) -> Dict[str, str]:
        """查询并按当前批量请求维度复用产品舱位结果。"""
        cache_key = (
            str(origin_station or "").strip().upper(),
            str(destination or "").strip().upper(),
            str(flight_number or "").strip().upper(),
            str(flight_date or "").strip(),
            str(shipment_type_code or "").strip(),
            str(shipment_type_name or "").strip(),
            str(weight),
            str(volume),
            str(product_name or "").strip(),
        )
        if cache is not None and cache_key in cache:
            return deepcopy(cache[cache_key])

        resolved = await self.query_flight_price_cabin_class(
            token=token,
            origin_station=origin_station,
            destination=destination,
            flight_number=flight_number,
            flight_date=flight_date,
            shipment_type_code=shipment_type_code,
            shipment_type_name=shipment_type_name,
            weight=weight,
            volume=volume,
            product_name=product_name,
            cookie=cookie,
        )
        if cache is not None:
            cache[cache_key] = deepcopy(resolved)
        return resolved

    async def query_departure_cargo_mail_handling_charge(
        self,
        *,
        token: str,
        origin_station: str,
        destination: str,
        flight_number: str,
        flight_date: str,
        cargo_type: str,
        cargo_name: str,
    ) -> Dict[str, Any]:
        """查询并返回南航「出港货邮处理费」的单个费用组选项。"""
        service_charges = await self.query_service_charges(
            token=token,
            origin_station=origin_station,
            destination=destination,
            flight_number=flight_number,
            flight_date=flight_date,
            cargo_type=cargo_type,
            cargo_name=cargo_name,
        )

        for service_charge in service_charges:
            service_main_name = str(service_charge.get("serviceMainName") or "").strip()
            if service_main_name == self.DEPARTURE_CARGO_MAIL_HANDLING_CHARGE:
                return service_charge

        service_main_names = [
            str(item.get("serviceMainName") or "").strip()
            for item in service_charges
        ]
        raise ChinaSouthernAirServiceError(
            "未查询到南航出港货邮处理费选项",
            details={
                "stage": "select_departure_cargo_mail_handling_charge",
                "expected_service_main_name": self.DEPARTURE_CARGO_MAIL_HANDLING_CHARGE,
                "available_service_main_names": service_main_names,
                "upstream_response": {
                    "extServiceCharges": service_charges,
                },
            },
        )


china_southern_air_service = ChinaSouthernAirService()
