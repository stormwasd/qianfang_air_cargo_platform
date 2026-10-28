"""KingGo HTTP client for direct Shenzhen Airlines waybill creation."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import time
from typing import Any, Callable
from urllib.parse import quote, quote_plus, urlencode, urlsplit

import httpx

from app.config import settings
from app.utils.helpers import get_china_today


class ShenzhenAirDirectWaybillError(RuntimeError):
    def __init__(self, message: str, *, outcome_unknown: bool = False, details: dict | None = None):
        super().__init__(message)
        self.outcome_unknown = outcome_unknown
        self.details = dict(details or {})


def _safe_upstream_text(value: Any, sensitive_values=(), limit: int = 512) -> str | None:
    """Keep bounded business messages, never dump objects, HTML or credentials."""
    if not isinstance(value, (str, int, float, bool)):
        return None
    text = str(value)
    if len(text) > 8192:
        return "[上游提示过长，已省略]"
    if re.search(r"<\s*(?:!doctype|html|body|script)\b", text, re.I):
        return "[HTML内容已省略]"
    # Upstream messages can echo submitted contacts or a signed URL. Redact
    # before truncation so a cut-off secret cannot evade replacement.
    for secret in sorted({str(v) for v in sensitive_values if v}, key=len, reverse=True):
        for representation in {secret, quote(secret, safe=""), quote_plus(secret)}:
            text = text.replace(representation, "[已隐藏]")
    text = re.sub(r"https?://[^\s<>\"']+", "[URL已隐藏]", text, flags=re.I)
    text = re.sub(
        r"(?<![A-Za-z0-9_])(?:cookie|set-cookie|authorization)\b\s*[\"']?\s*[:=][^\r\n]*",
        "[认证信息已隐藏]", text, flags=re.I,
    )
    text = re.sub(
        r"(?<![A-Za-z0-9_])(?:password|passwd|token|access_token|signature|oOr6SIhu)\b[\"']?\s*[:=]\s*[\"']?[^\s,;\"'&}]+",
        "[凭据已隐藏]", text, flags=re.I,
    )
    text = re.sub(r"(?<![0-9])1[3-9][0-9]{9}(?![0-9])|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[联系方式已隐藏]", text)
    text = " ".join("".join(ch if ch.isprintable() else " " for ch in text).split())
    return text[:limit] + ("…" if len(text) > limit else "") if text else None


class ShenzhenAirDirectWaybillService:
    ORIGIN = "https://www.kinggo.com"
    PREFIX = "479"
    ENDPOINTS = {
        "number": "/awb/inland/get_awb_no",
        "bill": "/awb/inland/get_bill_info_by_code",
        "flight": "/awb/inland/get_flight_no",
        "costs": "/awb/inland/computational_costs?nti=90",
        "check": "/awb/inland/check_awb?nti=90",
        "submit": "/awb/inland/submit_awb?nti=90",
    }
    COST_FIELDS = (
        "insuranceValue", "insuranceRate", "insuranceFee", "oilRate", "oilFee",
        "manageRate", "manageFee", "deliveryRate", "deliveryFee", "floorRate",
        "floorFee", "delayRate", "delayFee", "sundryRate", "sundryFee",
        "otherTotalFee", "depOtherFee", "firstFee",
    )
    BILL_FIELDS = (
        "billCode", "awbType", "cabinType", "dealCode", "ldcFlag", "aliasCode",
        "aug", "feeModel", "fastFreightFlag", "cabinTypeName",
    )

    def __init__(self, origin: str | None = None):
        self.origin = (origin or settings.SHENZHEN_AIR_KINGGO_API_ORIGIN or self.ORIGIN).rstrip("/")

    @staticmethod
    def diagnostic_values(values: dict) -> dict:
        """Whitelist identifiers and numbers from the immutable task snapshot."""
        result = {}
        if not isinstance(values, dict):
            return result
        for key in ("flight_number", "flight_date", "origin_station", "destination", "quantity",
                    "weight", "chargeable_weight", "freight_code", "cargo_code"):
            value = str(values.get(key, ""))
            pattern = r"[0-9]+(?:\.[0-9]+)?" if key in {"quantity", "weight", "chargeable_weight"} else r"[A-Za-z0-9_.-]+"
            if len(value) <= 32 and re.fullmatch(pattern, value):
                result[key] = value
        return result

    @staticmethod
    def _text(value: Any, name: str, *, required: bool = True) -> str:
        result = "" if value is None else str(value).strip()
        if required and not result:
            raise ShenzhenAirDirectWaybillError(f"深航开单缺少必填字段：{name}")
        return result

    @staticmethod
    def _decimal(value: Any, name: str, *, required: bool = True) -> Decimal:
        if value in (None, "") and not required:
            return Decimal("0")
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ShenzhenAirDirectWaybillError(f"深航开单字段 {name} 必须为数字") from exc
        if not number.is_finite() or number < 0:
            raise ShenzhenAirDirectWaybillError(f"深航开单字段 {name} 必须为非负有限数字")
        return number

    @classmethod
    def get_form_values(cls, form_data: dict, business_config: dict) -> dict:
        if not isinstance(form_data, dict) or not isinstance(business_config, dict):
            raise ShenzhenAirDirectWaybillError("深航运单表单或业务配置格式不正确")
        flight = form_data.get("flight_info") or {}
        contacts = form_data.get("shipper_consignee_info") or {}
        cargo = form_data.get("cargo_info") or {}
        defaults = business_config
        for key in ("shenzhen_air", "booking", "business_default"):
            if not isinstance(defaults, dict):
                raise ShenzhenAirDirectWaybillError("深航业务默认配置格式不正确")
            defaults = defaults.get(key) or {}
        if not all(isinstance(item, dict) for item in (flight, contacts, cargo, defaults)):
            raise ShenzhenAirDirectWaybillError("深航运单表单或业务默认配置格式不正确")
        values = {
            "origin_station": cls._text(flight.get("origin_station") or defaults.get("origin_station"), "始发站").upper(),
            "destination": cls._text(flight.get("destination"), "目的站").upper(),
            "flight_date": cls._text(flight.get("flight_date"), "航班日期"),
            "flight_number": cls._text(flight.get("flight_number"), "航班号").upper(),
            "shipper_info": cls._text(contacts.get("shipper_info") or defaults.get("shipper_info"), "发货人"),
            "consignee_info": cls._text(contacts.get("consignee_info"), "收货人"),
            "quantity": cls._text(cargo.get("quantity"), "件数"),
            "weight": cls._text(cargo.get("weight"), "重量"),
            "chargeable_weight": cls._text(cargo.get("chargeable_weight"), "计费重量"),
            "freight_code": cls._text(cargo.get("freight_code") or defaults.get("freight_code"), "货运代码"),
            "cargo_code": cls._text(cargo.get("cargo_code") or defaults.get("cargo_code"), "货物代码"),
            "cargo_name": cls._text(cargo.get("cargo_name") or defaults.get("cargo_name"), "货物名称"),
            "package": cls._text(cargo.get("package") or defaults.get("package"), "包装类型"),
            "waybill_type": cls._text(flight.get("waybill_type") or defaults.get("waybill_type"), "运单类型", required=False),
        }
        try:
            date.fromisoformat(values["flight_date"])
            for key in ("quantity", "weight", "chargeable_weight"):
                if cls._decimal(values[key], key) <= 0:
                    raise ShenzhenAirDirectWaybillError(f"深航开单字段 {key} 必须大于0")
        except ValueError as exc:
            raise ShenzhenAirDirectWaybillError("航班日期格式必须为 YYYY-MM-DD") from exc
        if cls._decimal(values["quantity"], "件数") % 1:
            raise ShenzhenAirDirectWaybillError("深航开单件数必须为正整数")
        if any(not re.fullmatch(r"[A-Z]{3}", values[key]) for key in ("origin_station", "destination")):
            raise ShenzhenAirDirectWaybillError("始发站和目的站必须为机场三字码")
        if not re.fullmatch(r"[A-Z0-9]{2}\d{3,4}", values["flight_number"]):
            raise ShenzhenAirDirectWaybillError("航班号格式不正确")
        return values

    async def _auth(self, path: str, method: str, body: str | None) -> tuple[str, dict[str, str]]:
        har_path = Path(settings.SHENZHEN_AIR_KINGGO_HAR_PATH)
        if not har_path.is_absolute():
            har_path = Path.cwd() / har_path
        try:
            from kinggo_token import generate
            from kinggo_token.har import replay_offline
            extracted = await replay_offline(
                har_path, path, method=method, body=body,
                channel=None if settings.SHENZHEN_AIR_KINGGO_BROWSER == "chromium" else settings.SHENZHEN_AIR_KINGGO_BROWSER,
                executable_path=settings.SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH,
                require_cookie=True,
            )
            # Preserve the digest computed by the original protection script for
            # the exact method, URL and encoded body; regenerate fresh metadata.
            token = generate(path, extracted["config"], digest=extracted["payload"]["requestDigest"])
        except Exception as exc:
            raise ShenzhenAirDirectWaybillError(f"KingGo HAR签名/Cookie提取失败（{type(exc).__name__}）") from exc
        cookie = token.get("cookie") or extracted.get("cookie")
        if not cookie:
            raise ShenzhenAirDirectWaybillError("KingGo HAR中未提取到可用Cookie")
        return token["url"], {"Cookie": cookie}

    async def _request(self, name: str, fields: dict[str, Any] | None = None,
                       before_send: Callable[[], None] | None = None) -> Any:
        path = self.ENDPOINTS[name]
        method = "GET" if name == "number" else "POST"
        started = time.monotonic()
        details = {"stage": name, "endpoint": path.split("?", 1)[0], "method": method}

        def failure(message, reason):
            return ShenzhenAirDirectWaybillError(
                message, outcome_unknown=name == "submit",
                details={**details, "reason_code": reason,
                         "elapsed_ms": round((time.monotonic() - started) * 1000)},
            )
        if name == "number":
            separator = "&" if "?" in path else "?"
            path += separator + urlencode({
                "inlandAwbType": "0", "awbPrefix": self.PREFIX,
                "_": str(time.time_ns() // 1_000_000),
            })
            body = None
        else:
            body = urlencode([(key, "" if value is None else str(value)) for key, value in (fields or {}).items()])
        try:
            signed_url, auth_headers = await self._auth(path, method, body)
        except ShenzhenAirDirectWaybillError as exc:
            exc.details.update(details, reason_code="auth_failed",
                               elapsed_ms=round((time.monotonic() - started) * 1000))
            raise
        headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": self.ORIGIN, "Referer": self.ORIGIN + "/main",
            "X-Requested-With": "XMLHttpRequest",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/153.0.0.0 Safari/537.36",
            **auth_headers,
        }
        try:
            async with httpx.AsyncClient(timeout=settings.SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS) as client:
                canonical = urlsplit(signed_url)
                request_url = self.origin + canonical.path + ("?" + canonical.query if canonical.query else "")
                if before_send:
                    before_send()
                response = await client.request(method, request_url, headers=headers, content=body if method == "POST" else None)
        except httpx.HTTPError as exc:
            details["request_error_type"] = type(exc).__name__
            raise failure(
                f"KingGo {name} 请求网络异常：{type(exc).__name__}", "network_error"
            ) from exc
        details["http_status"] = response.status_code
        try:
            result = response.json()
            details["response_type"] = type(result).__name__
        except ValueError:
            result = None
            details["response_type"] = "non_json"
        business_rejected = isinstance(result, dict) and "retCode" in result and str(result.get("retCode")) != "100"
        if 200 <= response.status_code < 300 and details["response_type"] != "non_json" and not business_rejected:
            return result  # Successful calls need no diagnostic text processing.
        # These are the only free-form response fields retained. Never save the
        # raw response, result object, signed URL, headers or complete form.
        sensitive = [str(v) for k, v in (fields or {}).items()
                     if k in {"shpInfo", "cneInfo", "shpTelNo", "cneTelNo", "remindPhone",
                              "pickTelNo", "agentSname", "newAgentSname", "cneAddr"} and v]
        sensitive.extend(str(v) for k, v in (fields or {}).items()
                         if k in {"agentId", "agentCode", "operId", "shpCustNo", "cneCustNo"}
                         and v and len(str(v)) >= 3)
        for value in auth_headers.values():
            sensitive.append(value)
            sensitive.extend(part.split("=", 1)[1].strip() for part in value.split(";")
                             if "=" in part and len(part.split("=", 1)[1].strip()) >= 3)
        request_summary = {}
        for key in ("pieces", "weight", "chargeWeight", "aviationRate", "aviationFee", "totalFee"):
            value = str((fields or {}).get(key, ""))
            if len(value) <= 32 and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
                request_summary[key] = value
        if request_summary:
            details["request_summary"] = request_summary
        def retain_message(payload, prefix):
            if isinstance(payload, dict):
                for key in ("msg", "message", "errorMsg", "retMsg"):
                    message = _safe_upstream_text(payload.get(key), sensitive)
                    if message:
                        details[prefix] = message
                        details[prefix + "_field"] = key
                        break
            else:
                message = _safe_upstream_text(payload, sensitive)
                if message:
                    details[prefix] = message

        if isinstance(result, dict):
            code = _safe_upstream_text(result.get("retCode"), sensitive, limit=64)
            if code is not None:
                details["upstream_ret_code"] = code
            retain_message(result, "upstream_message")
            retain_message(result.get("result"), "upstream_result_message")
        if not 200 <= response.status_code < 300:
            raise failure(
                f"KingGo {name} 请求失败（HTTP {response.status_code}）", "http_error"
            )
        if details["response_type"] == "non_json":
            raise failure(f"KingGo {name} 返回非JSON响应", "invalid_json")
        if business_rejected:
            raise failure(
                f"KingGo {name} 业务失败，请核查上游业务参数或登录状态", "business_rejected"
            )
        return result

    @staticmethod
    def _bill_result(response: Any) -> dict:
        result = response.get("result") if isinstance(response, dict) and str(response.get("retCode")) == "100" else None
        if not isinstance(result, dict):
            raise ShenzhenAirDirectWaybillError("KingGo运单信息接口返回格式异常",
                                               details={"stage": "bill", "reason_code": "invalid_result"})
        return result

    @staticmethod
    def validate_configuration() -> None:
        required_identity = {
            "SHENZHEN_AIR_KINGGO_AGENT_NAME": settings.SHENZHEN_AIR_KINGGO_AGENT_NAME,
            "SHENZHEN_AIR_KINGGO_AGENT_ID": settings.SHENZHEN_AIR_KINGGO_AGENT_ID,
            "SHENZHEN_AIR_KINGGO_AGENT_CODE": settings.SHENZHEN_AIR_KINGGO_AGENT_CODE,
            "SHENZHEN_AIR_KINGGO_OPER_ID": settings.SHENZHEN_AIR_KINGGO_OPER_ID,
            "SHENZHEN_AIR_KINGGO_PICK_TEL_NO": settings.SHENZHEN_AIR_KINGGO_PICK_TEL_NO,
            "SHENZHEN_AIR_KINGGO_CNE_ADDR": settings.SHENZHEN_AIR_KINGGO_CNE_ADDR,
        }
        missing_identity = [key for key, value in required_identity.items() if not str(value).strip()]
        if missing_identity:
            raise ShenzhenAirDirectWaybillError(
                "请先配置当前KingGo账号开单身份字段：" + ", ".join(missing_identity)
            )
        if bool(settings.SHENZHEN_AIR_KINGGO_CABIN_TYPE) != bool(settings.SHENZHEN_AIR_KINGGO_CABIN_TYPE_NAME):
            raise ShenzhenAirDirectWaybillError("固定舱位代码和名称必须同时配置")
        if not Path(settings.SHENZHEN_AIR_KINGGO_HAR_PATH).is_file():
            raise ShenzhenAirDirectWaybillError("KingGo HAR文件不存在，请先配置HAR文件")

    async def create_waybill(self, values: dict, *, before_submit: Callable[[str], None]) -> dict:
        self.validate_configuration()
        number_result = await self._request("number")
        suffix = number_result.get("result") if isinstance(number_result, dict) else None
        if (not isinstance(number_result, dict) or str(number_result.get("retCode")) != "100"
                or not re.fullmatch(r"\d{8}", str(suffix))):
            raise ShenzhenAirDirectWaybillError("KingGo未返回有效运单号",
                                               details={"stage": "number", "reason_code": "invalid_result"})
        awb_number = str(suffix)

        lookup = {
            "depCode": values["origin_station"], "destCode": values["destination"],
            "billCode": values["freight_code"], "awbType": "0",
            "flightDate": values["flight_date"], "flightNo": values["flight_number"],
            "transCity": "", "awbPrefix": self.PREFIX,
        }
        bill = self._bill_result(await self._request("bill", lookup))
        for field in self.BILL_FIELDS:
            if field not in bill:
                raise ShenzhenAirDirectWaybillError(f"KingGo运单信息缺少字段：{field}",
                                                   details={"stage": "bill", "reason_code": "missing_field", "field": field})

        flight_rows = await self._request("flight", {
            "depCode": values["origin_station"], "destCode": values["destination"],
            "flightDate": values["flight_date"],
        })
        if not isinstance(flight_rows, list):
            raise ShenzhenAirDirectWaybillError("KingGo航班列表返回格式异常",
                                               details={"stage": "flight", "reason_code": "invalid_result"})
        matched = [row for row in flight_rows if isinstance(row, dict)
                   and str(row.get("flightNo", "")).upper() == values["flight_number"]
                   and str(row.get("flightDate", values["flight_date"]))[:10] == values["flight_date"]
                   and str(row.get("depCode", values["origin_station"])).upper() == values["origin_station"]
                   and str(row.get("destCode", values["destination"])).upper() == values["destination"]]
        if len(matched) != 1:
            raise ShenzhenAirDirectWaybillError("KingGo航班列表中未找到唯一匹配的航班",
                                               details={"stage": "flight", "reason_code": "flight_match_failed", "match_count": len(matched)})
        takeoff = matched[0].get("takeoffTime")
        carrier = self._text(matched[0].get("carrierCode"), "航班承运人代码")
        if not re.fullmatch(r"\d{4}", str(takeoff)):
            raise ShenzhenAirDirectWaybillError("匹配航班缺少有效起飞时间",
                                               details={"stage": "flight", "reason_code": "invalid_takeoff_time"})

        cost_response = await self._request("costs", {
            "awbType": bill["awbType"], "depCode": values["origin_station"],
            "destCode": values["destination"], "flightDate": values["flight_date"],
            "flightNo": values["flight_number"], "chargeWeight": values["chargeable_weight"],
            "custNo": "", "billCode": bill["billCode"], "insuranceValue": "0",
            "agentType": settings.SHENZHEN_AIR_KINGGO_AGENT_TYPE,
            "transCity": "", "feeModel": bill["feeModel"],
        })
        if not isinstance(cost_response, dict):
            raise ShenzhenAirDirectWaybillError("KingGo费用接口返回格式异常",
                                               details={"stage": "costs", "reason_code": "invalid_result"})
        costs = cost_response
        for field in ("aviationFee", "aviationRate", *self.COST_FIELDS):
            if field not in costs:
                raise ShenzhenAirDirectWaybillError(f"KingGo费用接口缺少字段：{field}",
                                                   details={"stage": "costs", "reason_code": "missing_field", "field": field})
            self._decimal(costs[field], field)

        cabin_code = settings.SHENZHEN_AIR_KINGGO_CABIN_TYPE or str(bill["cabinType"])
        cabin_name = settings.SHENZHEN_AIR_KINGGO_CABIN_TYPE_NAME or str(bill["cabinTypeName"])
        total_fee = self._decimal(costs["otherTotalFee"], "otherTotalFee") + self._decimal(costs["aviationFee"], "aviationFee")
        operation_date = get_china_today().isoformat()
        fields = {
            "awbId": "", "awbStatus": "", "cneSign": "", "printFlag": "", "checkFlag": "",
            "njNnFlag": "", "awbType": "", "sourceId": "", "takeOffTime": takeoff,
            "pageSource": "agentEdit", "checkBargainFlag": "", "awbTempFlag": "",
            "eawbFlag": "1", "inlandAwbType": "0", "awbPrefix": self.PREFIX, "awbNo": awb_number,
            "depCode": values["origin_station"], "destCode": values["destination"],
            "flightDate": values["flight_date"], "flightNo": values["flight_number"],
            "carrierCode": carrier, "transCity": "", "transDate": values["flight_date"],
            "transFlightNo": "", "transCarrierCode": "", "shpCustNo": "", "newAgentSname": "",
            "shpInfo": values["shipper_info"], "shpTelNo": "", "cneCustNo": "",
            "cneInfo": values["consignee_info"], "cneTelNo": "", "remindPhone": "",
            "pieces": values["quantity"], "weight": values["weight"], "chargeWeight": values["chargeable_weight"],
            "billCode": bill["billCode"], "aliasCode": values["freight_code"], "aug": bill["aug"],
            "ldcFlag": bill["ldcFlag"], "feeModel": bill["feeModel"], "billType": "1",
            "fastFreightFlag": bill["fastFreightFlag"], "dealCode": bill["dealCode"],
            "cabinTypeName": cabin_name, "cabinType": cabin_code, "oldCabinType": bill["cabinType"],
            "actualCabin": "", "goodsCode": values["cargo_code"], "goodsName": values["cargo_name"],
            "packName": values["package"], "packId": "", "bargainRate": "", "bargainPrice": "",
            "bargainFee": "", "nodeId": "", "procId": "", "procActualName": "", "bargainRemark": "",
            "formerRate": costs["aviationRate"], "aviationRate": costs["aviationRate"],
            "formerFee": costs["aviationFee"], "bargainFlagV": costs.get("bargainFlag", 0),
            "aviationFee": costs["aviationFee"],
            **{field: costs[field] for field in self.COST_FIELDS if field not in {"depOtherFee", "firstFee"}},
            "depOtherFee": costs["depOtherFee"], "firstAddFee": "",
            "otherAgencyFeeStr": "",
            "totalFee": format(total_fee, "f"), "payType": settings.SHENZHEN_AIR_KINGGO_PAY_TYPE,
            "realAmount": "", "template": "1", "transNote": values["cargo_name"], "settleNote": "",
            "cellmodel": "", "brandno": "", "equipmodel": "", "checkcompany": "", "packType": "",
            "reportNo": "", "isButtonCell": "", "carrier": "", "ldcName": "", "ldcSign": "", "battId": "",
            "agentType": settings.SHENZHEN_AIR_KINGGO_AGENT_TYPE,
            "agentSname": settings.SHENZHEN_AIR_KINGGO_AGENT_NAME,
            "agentId": settings.SHENZHEN_AIR_KINGGO_AGENT_ID,
            "agentCode": settings.SHENZHEN_AIR_KINGGO_AGENT_CODE,
            "operDate": operation_date, "cneAddr": settings.SHENZHEN_AIR_KINGGO_CNE_ADDR,
            "operId": settings.SHENZHEN_AIR_KINGGO_OPER_ID,
            "pickTelNo": settings.SHENZHEN_AIR_KINGGO_PICK_TEL_NO,
            "tlicellCellinfos": "[]",
        }
        checked = await self._request("check", fields)
        if not isinstance(checked, dict) or str(checked.get("retCode")) != "100":
            raise ShenzhenAirDirectWaybillError("KingGo运单检查未成功",
                                               details={"stage": "check", "reason_code": "invalid_result"})
        submitted = await self._request("submit", fields, before_send=lambda: before_submit(f"{self.PREFIX}-{awb_number}"))
        result = submitted.get("result") if isinstance(submitted, dict) else None
        submitted_number = result.get("awbNo") if isinstance(result, dict) else None
        if (not isinstance(result, dict) or str(submitted.get("retCode")) != "100"
                or str(submitted_number) != awb_number or not result.get("awbId")):
            raise ShenzhenAirDirectWaybillError(
                "KingGo提交结果未确认，请核查运单后再操作", outcome_unknown=True,
                details={"stage": "submit", "reason_code": "unconfirmed_result"},
            )
        return {
            "waybill_number": f"{self.PREFIX}-{submitted_number}",
            "awb_id": str(result.get("awbId") or ""),
            "aviation_rate": costs["aviationRate"],
            "aviation_fee": costs["aviationFee"],
            "delivery_fee": costs["deliveryFee"],
        }


shenzhen_air_direct_waybill_service = ShenzhenAirDirectWaybillService()
