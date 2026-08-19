"""南航直连接口的费用计算与开单服务。"""
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx

from app.services.china_southern_air_service_client import ChinaSouthernAirService


class ChinaSouthernAirDirectOrderError(Exception):
    """南航直连开单接口错误，并描述单号是否仍可安全归还。"""

    def __init__(
        self,
        message: str,
        *,
        number_is_used: bool = False,
        outcome_unknown: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.number_is_used = number_is_used
        self.outcome_unknown = outcome_unknown
        self.details = deepcopy(details) if details is not None else None


class ChinaSouthernAirDirectOrderService:
    """封装南航 B2B 的 calculateCharge 与 createOrder 调用。"""

    CALCULATE_CHARGE_URL = (
        "https://cargo.csair.com/order-center/b2e-order/b2eOrder/calculateCharge"
    )
    CREATE_ORDER_URL = (
        "https://cargo.csair.com/order-center/b2e-order/b2eOrder/createOrder"
    )
    OUTBOUND_HANDLING_FEE_NAME = "出港货邮处理费"

    @staticmethod
    def _upstream_error_details(
        *,
        is_create: bool,
        upstream_response: Any = None,
        http_status: Optional[int] = None,
        network_error: Optional[str] = None,
        request_context: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """构造可安全返回给调用方的南航错误上下文，不包含请求头或认证信息。"""
        details: Dict[str, Any] = {
            "stage": "create_order" if is_create else "calculate_charge",
            "upstream_response": deepcopy(upstream_response),
        }
        if http_status is not None:
            details["http_status"] = http_status
        if network_error:
            details["network_error"] = network_error
        if request_context:
            details["request_context"] = deepcopy(request_context)
        if request_data is not None:
            details["request_data"] = deepcopy(request_data)
        return details

    @staticmethod
    def _diagnostic_request_context(payload: Dict[str, Any]) -> Dict[str, Any]:
        """仅提取排查南航联系人校验所需的最终请求字段。"""
        order_info = payload.get("orderInfo")
        if not isinstance(order_info, dict):
            return {}
        order = order_info.get("order")
        if not isinstance(order, dict):
            return {}
        return {
            field: order.get(field)
            for field in ("contactName", "contactPhone")
            if field in order
        }

    @staticmethod
    def _response_body(response: httpx.Response) -> Any:
        """优先保留南航原始 JSON；非 JSON 响应则保留完整文本。"""
        try:
            return response.json()
        except (ValueError, TypeError):
            return response.text

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ChinaSouthernAirDirectOrderError(f"缺少南航开单必填字段：{field_name}")
        return text

    @classmethod
    def _number(cls, value: Any, field_name: str, *, integer: bool = False) -> Any:
        try:
            number = int(value) if integer else float(value)
        except (TypeError, ValueError) as exc:
            raise ChinaSouthernAirDirectOrderError(
                f"南航开单字段 {field_name} 必须是数字"
            ) from exc
        if number < 0 or (integer and number == 0):
            constraint = "大于 0" if integer else "大于或等于 0"
            raise ChinaSouthernAirDirectOrderError(
                f"南航开单字段 {field_name} 必须{constraint}"
            )
        return number

    @staticmethod
    def _region_parts(region: Any) -> tuple[str, str, str]:
        if isinstance(region, list):
            parts = region
        elif isinstance(region, str):
            parts = region.split("/")
        else:
            parts = []
        normalized = [str(part).strip() for part in parts]
        return (
            normalized[0] if len(normalized) > 0 else "",
            normalized[1] if len(normalized) > 1 else "",
            normalized[2] if len(normalized) > 2 else "",
        )

    @classmethod
    def _get_form_values(cls, form_data: Dict[str, Any]) -> Dict[str, Any]:
        flight_info = form_data.get("flight_info") or {}
        cargo_info = form_data.get("cargo_info") or {}
        contact_info = form_data.get("contact_info") or {}
        address = contact_info.get("address") or {}
        other_info = form_data.get("other_info") or {}
        dangerous = form_data.get("dangerous_goods_declaration") or {}

        if not all(isinstance(item, dict) for item in (
            flight_info, cargo_info, contact_info, address, other_info, dangerous
        )):
            raise ChinaSouthernAirDirectOrderError("南航开单 form_data 的对象字段格式不正确")

        province, city, district = cls._region_parts(address.get("region"))
        no_hidden_dangerous_goods = str(dangerous.get("no_hidden_dangerous_goods", "")).strip()

        selected_fee = form_data.get("outbound_cargo_and_mail_handling_fee_options")
        if not isinstance(selected_fee, dict):
            raise ChinaSouthernAirDirectOrderError(
                "缺少出港货邮处理费选项，请先查询并选择费用选项"
            )
        if selected_fee.get("serviceMainName") != cls.OUTBOUND_HANDLING_FEE_NAME:
            raise ChinaSouthernAirDirectOrderError("出港货邮处理费选项数据不正确")
        if not isinstance(selected_fee.get("serviceCharges"), list):
            raise ChinaSouthernAirDirectOrderError("出港货邮处理费选项明细格式不正确")

        return {
            "origin_station": cls._required_text(flight_info.get("origin_station"), "flight_info.origin_station").upper(),
            "destination": cls._required_text(flight_info.get("destination"), "flight_info.destination").upper(),
            "flight_date": cls._required_text(flight_info.get("flight_date"), "flight_info.flight_date"),
            "flight_number": cls._required_text(flight_info.get("flight_number"), "flight_info.flight_number").upper(),
            "booking_remark": flight_info.get("booking_remark") or None,
            "shipment_type_name": cls._required_text(cargo_info.get("cargo_type"), "cargo_info.cargo_type"),
            # 新版 form_data 直接携带南航货物类型代码；为空时由构建请求处兼容
            # 历史运单，继续回退到既有业务参数配置。
            "rate_code": str(cargo_info.get("cargo_type_code") or "").strip() or None,
            "commodity_code": cls._required_text(cargo_info.get("cargo_code"), "cargo_info.cargo_code"),
            "commodity_name": cls._required_text(cargo_info.get("cargo_name"), "cargo_info.cargo_name"),
            "piece": cls._number(cargo_info.get("quantity"), "cargo_info.quantity", integer=True),
            "weight": cls._number(cargo_info.get("weight"), "cargo_info.weight"),
            "volume": cls._number(cargo_info.get("booking_volume", 0), "cargo_info.booking_volume"),
            "sp_code": str(cargo_info.get("special_cargo_code") or "").strip() or None,
            "handling_info": str(cargo_info.get("storage_and_transportation_precautions") or "").strip() or None,
            "over_standard_cus": int(str(cargo_info.get("oversized_cargo", "0")).strip() or "0"),
            "consignee_name": cls._required_text(contact_info.get("consignee"), "contact_info.consignee"),
            "consignee_mobile": cls._required_text(contact_info.get("consignee_phone"), "contact_info.consignee_phone"),
            "shipper_name": cls._required_text(contact_info.get("shipper"), "contact_info.shipper"),
            "shipper_mobile": cls._required_text(contact_info.get("shipper_phone"), "contact_info.shipper_phone"),
            "shipper_state": cls._required_text(province, "contact_info.address.region[0]"),
            "shipper_city": cls._required_text(city, "contact_info.address.region[1]"),
            "shipper_district": cls._required_text(district, "contact_info.address.region[2]"),
            "shipper_address": cls._required_text(address.get("detail"), "contact_info.address.detail"),
            "contact_name": cls._required_text(other_info.get("order_contact"), "other_info.order_contact"),
            "contact_phone": cls._required_text(other_info.get("contact_phone"), "other_info.contact_phone"),
            "accounting_rule": str(other_info.get("settlement_file_number") or "").strip() or None,
            "dangerous_check_required": no_hidden_dangerous_goods == "0",
            "agent_check_name": str(dangerous.get("agent_checker_signature") or "").strip() or None,
            "agent_carrier_name": str(dangerous.get("agent_consignor_signature") or "").strip() or None,
            "selected_fee": deepcopy(selected_fee),
        }

    @classmethod
    def get_form_values(
        cls,
        form_data: Dict[str, Any],
        business_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """解析并校验南航运单表单，供费用选项查询与请求构建复用。"""
        values = cls._get_form_values(form_data)
        if business_config is not None:
            config = cls._direct_order_config(business_config)
            values["rate_code"] = cls._required_text(
                values["rate_code"] or config.get("rate_code", "3006"),
                "cargo_info.cargo_type_code",
            )
        return values

    @staticmethod
    def _direct_order_config(business_config: Dict[str, Any]) -> Dict[str, Any]:
        china_southern_air = business_config.get("china_southern_air") or {}
        booking_and_create = china_southern_air.get("booking_and_create") or {}
        config = booking_and_create.get("direct_order") or {}
        return config if isinstance(config, dict) else {}

    @staticmethod
    def _response_indicates_used_number(response_text: str) -> bool:
        text = response_text.lower()
        return (
            ("单号" in text and ("已使用" in text or "已被使用" in text or "已经使用" in text))
            or ("运单号" in text and ("已使用" in text or "已被使用" in text or "已经使用" in text))
            or ("awb" in text and ("used" in text or "exist" in text))
        )

    @classmethod
    def build_calculate_payload(
        cls,
        form_data: Dict[str, Any],
        business_config: Dict[str, Any],
        *,
        service_charges: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        values = cls._get_form_values(form_data)
        config = cls._direct_order_config(business_config)
        if service_charges is None:
            service_charges = config.get("calculate_ext_service_charges")
        if not isinstance(service_charges, list) or not service_charges:
            raise ChinaSouthernAirDirectOrderError(
                "南航费用计算缺少完整的扩展服务费列表"
            )
        if not all(isinstance(item, dict) for item in service_charges):
            raise ChinaSouthernAirDirectOrderError(
                "南航费用计算扩展服务费列表格式不正确"
            )

        ext_service_charges = deepcopy(service_charges)
        selected_fee = cls._normalize_selected_fee(
            values["selected_fee"], values["shipment_type_name"]
        )
        for index, group in enumerate(ext_service_charges):
            if group.get("serviceMainName") == cls.OUTBOUND_HANDLING_FEE_NAME:
                ext_service_charges[index] = selected_fee
                break
        else:
            raise ChinaSouthernAirDirectOrderError(
                "南航完整费用列表中缺少出港货邮处理费"
            )

        return cls._build_calculate_payload(values, config, ext_service_charges)

    @classmethod
    def _normalize_selected_fee(
        cls, selected_fee: Dict[str, Any], shipment_type_name: str
    ) -> Dict[str, Any]:
        """确保出港货邮处理费分组及实际选中的子项带有 checked=Y。"""
        normalized = deepcopy(selected_fee)
        details = normalized.get("serviceCharges")
        if not isinstance(details, list):
            raise ChinaSouthernAirDirectOrderError("出港货邮处理费选项明细格式不正确")

        checked_items = [
            detail
            for detail in details
            if isinstance(detail, dict)
            and str(detail.get("checked") or "").strip().upper() == "Y"
        ]
        if not checked_items:
            matched_item = next(
                (
                    detail
                    for detail in details
                    if isinstance(detail, dict)
                    and str(detail.get("otherChargeName") or "").strip()
                    == shipment_type_name
                ),
                None,
            )
            if matched_item is None:
                available_options = [
                    str(detail.get("otherChargeName") or "").strip()
                    for detail in details
                    if isinstance(detail, dict)
                    and str(detail.get("otherChargeName") or "").strip()
                ]
                options_text = "、".join(available_options) if available_options else "无"
                raise ChinaSouthernAirDirectOrderError(
                    "出港货邮处理费未勾选具体选项，且无法根据货物类型"
                    f"“{shipment_type_name}”自动匹配；当前可选项：{options_text}"
                )
            matched_item["checked"] = "Y"

        normalized["checked"] = "Y"
        return normalized

    @staticmethod
    def _build_calculate_payload(
        values: Dict[str, Any], config: Dict[str, Any], ext_service_charges: list
    ) -> Dict[str, Any]:
        """严格按南航 calculateCharge 接口所需的最小结构构造请求。"""
        return {
            "resAllInfoList": [{"resDto": {
                "flightDep": values["origin_station"],
                "flightDest": values["destination"],
                "bookFlightno": values["flight_number"],
                "bookFlightdate": values["flight_date"],
            }}],
            "orderInfo": {
                "order": {},
                "orderShipment": {
                    "rateCode": values["rate_code"] or config.get("rate_code", "3006"),
                    "shipmentTypeName": values["shipment_type_name"],
                    "piece": values["piece"],
                    "weight": values["weight"],
                    "volume": values["volume"],
                    "bookGrade": config.get("book_grade", "A"),
                    "spaceClass": config.get("space_class", "A"),
                    "subSpaceClass": config.get("sub_space_class", "A6"),
                },
            },
            "extServiceCharges": deepcopy(ext_service_charges),
        }

    @classmethod
    def build_create_payload(
        cls,
        form_data: Dict[str, Any],
        business_config: Dict[str, Any],
        *,
        number_prefix: str,
        number_suffix: str,
        calculation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        values = cls._get_form_values(form_data)
        config = cls._direct_order_config(business_config)
        calculated_fees = calculation_result.get("extServiceCharges")
        if not isinstance(calculated_fees, list):
            raise ChinaSouthernAirDirectOrderError("南航费用计算未返回完整的扩展服务费列表")

        payload = cls._build_order_payload(values, config, calculated_fees)
        shipment = payload["orderInfo"]["orderShipment"]
        flight_price = calculation_result.get("flightPriceCalculateResult") or {}
        shipment.update({
            "rateCharge": calculation_result.get("rateCharge"),
            "weightCharge": calculation_result.get("weightCharge"),
            "publicRateCharge": calculation_result.get("publicRateCharge"),
            "rateClass": flight_price.get("rateClass") or shipment["rateClass"],
        })
        payload["orderInfo"]["orderShipmentAwb"] = {
            "awbprefix": str(number_prefix).rstrip("-"),
            "awbno": str(number_suffix),
            "awbpostfix": str(config.get("awb_postfix", "00000000")),
            "awbNoType": str(config.get("awb_no_type", "BMI")),
        }
        return payload

    @classmethod
    def _build_order_payload(
        cls, values: Dict[str, Any], config: Dict[str, Any], ext_service_charges: list
    ) -> Dict[str, Any]:
        carrier = str(config.get("carrier", "CZ"))
        agent_code = str(config.get("agent_code", "SZXFED"))
        dangerous_value = 1 if values["dangerous_check_required"] else 0
        return {
            "resAllInfoList": [{"resDto": {
                "flightDep": values["origin_station"],
                "flightDest": values["destination"],
                "bookFlightno": values["flight_number"],
                "bookFlightdate": values["flight_date"],
                "carrier": carrier,
                "routing": f"{values['origin_station']}{carrier}/{values['destination']}",
                "bookMemo": values["booking_remark"],
                "acType": config.get("ac_type", "32K"),
                "acno": config.get("ac_no", "B6912"),
            }}],
            "orderShipmentPlateDtoList": None,
            "listOrderLog": [],
            "orderInfo": {
                "order": {
                    "payChannel": config.get("pay_channel", "H"),
                    "settlementMode": config.get("settlement_mode", "POST"),
                    "payMethod": config.get("pay_method", "PP"),
                    "bigCustomerNo": config.get("big_customer_no"),
                    "contactName": values["contact_name"],
                    "contactPhone": values["contact_phone"],
                    "checkFile": config.get("check_file", "N"),
                    "directTransfer": config.get("direct_transfer", "D"),
                    "channel": config.get("channel", "B"),
                },
                "orderShipment": {
                    "agentCode": agent_code,
                    "agentIataCode": config.get("agent_iata_code", "08305167"),
                    "rateCode": values["rate_code"] or config.get("rate_code", "3006"),
                    "shipmentTypeName": values["shipment_type_name"],
                    "accountingRule": values["accounting_rule"],
                    "accountingInfo": config.get("accounting_info", "文件：限南航承运"),
                    "piece": values["piece"],
                    "weight": values["weight"],
                    "volume": values["volume"],
                    "goodsInputMethod": config.get("goods_input_method", 0),
                    "bookGrade": config.get("book_grade", "A"),
                    "spaceClass": config.get("space_class", "A"),
                    "subSpaceClass": config.get("sub_space_class", "A6"),
                    "parentProductionName": config.get("parent_production_name", "南航快运"),
                    "parentProductionNameCn": config.get("parent_production_name_cn", "南航快运"),
                    "rateClass": config.get("rate_class", "M"),
                    "coldStorage": None,
                    "spCode": values["sp_code"],
                    "attachedFile": None,
                    "treatment": None,
                    "processSituation": None,
                    "handlingInfo": values["handling_info"],
                    "dvfCarrier": None,
                    "dvfCarrierFee": 0,
                    "certificationForTransport": None,
                    "wtVal": config.get("wt_val", "P"),
                    "otherChargeStatement": config.get("other_charge_statement", "P"),
                    "customsStatusOfGoods": config.get("customs_status_of_goods", "001"),
                    "exchangeRate": 1,
                    "overStandardCus": values["over_standard_cus"],
                },
                "listOrderShipmentDim": None,
                "orderShipmentAwb": None,
                "orderShipmentDangerous": None,
                "orderShipmentContact": {
                    "shipperAddress": values["shipper_address"],
                    "shipperAccount": None,
                    "shipperCity": values["shipper_city"],
                    "shipperCountry": None,
                    "shipperCountryCode": str(
                        config.get("shipper_country_code") or "CN"
                    ).strip().upper(),
                    "shipperDistrict": values["shipper_district"],
                    "shipperEmail": None,
                    "shipperIdno": None,
                    "shipperMobile": values["shipper_mobile"],
                    "shipperName": values["shipper_name"],
                    "shipperState": values["shipper_state"],
                    "shipperTelephone": None,
                    "shipperZipcode": None,
                    "shipperCertType": None,
                    "driverIdno": None,
                    "driverMobile": None,
                    "driverName": None,
                    "driverSame": None,
                    "driverTelephone": None,
                    "driverCertType": None,
                    "consigneeAccount": None,
                    "consigneeAddress": str(
                        config.get("consignee_address") or "机场自提"
                    ).strip(),
                    "consigneeCity": None,
                    "consigneeCountry": None,
                    "consigneeCountryCode": str(
                        config.get("consignee_country_code") or "CN"
                    ).strip().upper(),
                    "consigneeDistrict": None,
                    "consigneeEmail": None,
                    "consigneeIdno": None,
                    "consigneeMobile": values["consignee_mobile"],
                    "consigneeName": values["consignee_name"],
                    "consigneeState": None,
                    "consigneeTelephone": None,
                    "consigneeZipcode": None,
                    "consigneeCertType": None,
                    "selfPickUp": "N",
                    "notifyAddress": None,
                    "notifyCity": None,
                    "notifyContactId": None,
                    "notifyCountryCode": None,
                    "notifyEmail": None,
                    "notifyMobile": None,
                    "notifyName": None,
                    "notifyState": None,
                    "notifyTelephone": None,
                    "notifyZipcode": None,
                    "orderId": None,
                },
                "orderShipmentLiveAnimals": None,
            },
            "addServiceCharges": [],
            "extServiceCharges": deepcopy(ext_service_charges),
            "commodityCode": {
                "commoditycode": values["commodity_code"],
                "cname": values["commodity_name"],
            },
            "awbLithiumBatteryDetailsList": None,
            "awbLithiumBatteryInfomation": None,
            "awbDangerousCheck": {
                "isdeterminedgoods": dangerous_value,
                "noundeclaredangerous": dangerous_value,
                "isleaked": dangerous_value,
                "isclear": dangerous_value,
                "nohiddendangerous": dangerous_value,
                "agentcheckname": values["agent_check_name"],
                "agentcarriername": values["agent_carrier_name"],
            },
            "productionCode": values["sp_code"],
            "lithiumBatteryCheckItemsList": None,
        }

    async def calculate_charge(
        self, *, token: str, payload: Dict[str, Any], business_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = await self._post(
            self.CALCULATE_CHARGE_URL, token, payload, business_config, is_create=False
        )
        if not isinstance(result, dict):
            raise ChinaSouthernAirDirectOrderError("南航费用计算未返回计算结果")
        return result

    async def create_order(
        self, *, token: str, payload: Dict[str, Any], business_config: Dict[str, Any]
    ) -> Any:
        return await self._post(
            self.CREATE_ORDER_URL, token, payload, business_config, is_create=True
        )

    async def _post(
        self,
        url: str,
        token: str,
        payload: Dict[str, Any],
        business_config: Dict[str, Any],
        *,
        is_create: bool,
    ) -> Any:
        config = self._direct_order_config(business_config)
        request_context = self._diagnostic_request_context(payload)
        # calculateCharge 与 createOrder 都可能返回只有简短提示的业务错误。
        # 保留最终 JSON 请求体用于排查字段映射；认证信息仅存在于 headers，
        # 不会进入错误详情。
        request_data = payload
        cleaned_token = ChinaSouthernAirService._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirDirectOrderError("南航登录令牌无效，请先刷新南航 Token")

        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "Sensitive-Information": "Sensitive",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": str(config.get("agent_code", "SZXFED")),
        }
        if config.get("cookie"):
            headers["Cookie"] = str(config["cookie"])

        try:
            timeout = httpx.Timeout(30.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            upstream_response = self._response_body(exc.response)
            response_text = (
                json.dumps(upstream_response, ensure_ascii=False, default=str).lower()
                if not isinstance(upstream_response, str)
                else upstream_response.lower()
            )
            number_is_used = is_create and self._response_indicates_used_number(response_text)
            raise ChinaSouthernAirDirectOrderError(
                f"南航{'开单' if is_create else '费用计算'}失败（HTTP {exc.response.status_code}）",
                number_is_used=number_is_used,
                outcome_unknown=is_create and exc.response.status_code >= 500,
                details=self._upstream_error_details(
                    is_create=is_create,
                    http_status=exc.response.status_code,
                    upstream_response=upstream_response,
                    request_context=request_context,
                    request_data=request_data,
                ),
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirDirectOrderError(
                f"南航{'开单' if is_create else '费用计算'}服务暂时不可用",
                outcome_unknown=is_create,
                details=self._upstream_error_details(
                    is_create=is_create,
                    network_error=str(exc),
                    request_context=request_context,
                    request_data=request_data,
                ),
            ) from exc

        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirDirectOrderError(
                f"南航{'开单' if is_create else '费用计算'}服务返回无效数据",
                outcome_unknown=is_create,
                details=self._upstream_error_details(
                    is_create=is_create,
                    http_status=response.status_code,
                    upstream_response=response.text,
                    request_context=request_context,
                    request_data=request_data,
                ),
            ) from exc

        if not isinstance(response_data, dict):
            raise ChinaSouthernAirDirectOrderError(
                f"南航{'开单' if is_create else '费用计算'}服务返回格式异常",
                outcome_unknown=is_create,
                details=self._upstream_error_details(
                    is_create=is_create,
                    http_status=response.status_code,
                    upstream_response=response_data,
                    request_context=request_context,
                    request_data=request_data,
                ),
            )
        if str(response_data.get("code", "")) in {"0000", "0"}:
            return response_data.get("result")

        message = ChinaSouthernAirService._response_message(
            response_data, "南航接口处理失败"
        )
        response_text = json.dumps(response_data, ensure_ascii=False).lower()
        number_is_used = is_create and self._response_indicates_used_number(response_text)
        raise ChinaSouthernAirDirectOrderError(
            message,
            number_is_used=number_is_used,
            details=self._upstream_error_details(
                is_create=is_create,
                http_status=response.status_code,
                upstream_response=response_data,
                request_context=request_context,
                request_data=request_data,
            ),
        )


china_southern_air_direct_order_service = ChinaSouthernAirDirectOrderService()
