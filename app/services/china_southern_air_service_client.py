"""南航 B2B 业务接口客户端。"""
from typing import Any, Dict, List

import httpx


class ChinaSouthernAirServiceError(Exception):
    """南航 B2B 接口调用或响应不符合预期。"""


class ChinaSouthernAirService:
    """封装不经过 RPA 的南航 B2B 查询接口。"""

    SERVICE_CHARGE_URL = (
        "https://cargo.csair.com/order-center/b2e-order/b2eOrder/queryServiceCharge"
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
            if (
                isinstance(service_charge, dict)
                and service_charge.get("serviceMainName")
                == self.DEPARTURE_CARGO_MAIL_HANDLING_CHARGE
            ):
                return service_charge

        raise ChinaSouthernAirServiceError("未查询到南航出港货邮处理费选项")


china_southern_air_service = ChinaSouthernAirService()
