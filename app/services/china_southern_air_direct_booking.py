"""南航订舱直连接口的数据映射与航班查询服务。"""
import json
from copy import deepcopy
from typing import Any, Dict, List, Optional

import httpx

from app.services.china_southern_air_direct_order import china_southern_air_direct_order_service
from app.services.china_southern_air_service_client import ChinaSouthernAirService


class ChinaSouthernAirDirectBookingError(Exception):
    """南航直连订舱的参数或前置查询错误。"""

    def __init__(
        self,
        message: str,
        *,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.details = deepcopy(details) if details is not None else None


class ChinaSouthernAirDirectBookingService:
    """构造南航订舱请求，并按航班机型选择订舱备注。"""

    FLIGHT_QUERY_URL = (
        "https://cargo.csair.com/order-center/b2e-flight/flight/queryFlightTrc"
    )
    OUTBOUND_HANDLING_FEE_NAME = "出港货邮处理费"
    ALLOWED_HANDLING_FEE_OPTIONS = {
        "贵重物品", "活体动物", "危险品", "鲜活易腐", "鲜活容腐", "普货", "急件快件"
    }

    @staticmethod
    def _required_text(value: Any, field_name: str) -> str:
        text = "" if value is None else str(value).strip()
        if not text:
            raise ChinaSouthernAirDirectBookingError(f"缺少南航订舱必填字段：{field_name}")
        return text

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
        *,
        integer: bool = False,
        allow_empty: bool = False,
        allow_zero: bool = False,
    ) -> Any:
        if allow_empty and (value is None or str(value).strip() == ""):
            return 0
        try:
            number = int(value) if integer else float(value)
        except (TypeError, ValueError) as exc:
            raise ChinaSouthernAirDirectBookingError(
                f"南航订舱字段 {field_name} 必须是数字"
            ) from exc
        if number < 0 or (integer and number == 0 and not allow_zero):
            constraint = "大于 0" if integer else "大于或等于 0"
            raise ChinaSouthernAirDirectBookingError(
                f"南航订舱字段 {field_name} 必须{constraint}"
            )
        return number

    @staticmethod
    def _booking_config(business_config: Dict[str, Any]) -> Dict[str, Any]:
        csa = business_config.get("china_southern_air") or {}
        value = (csa.get("booking") or {}).get("booking_config") or {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _direct_order_config(business_config: Dict[str, Any]) -> Dict[str, Any]:
        csa = business_config.get("china_southern_air") or {}
        value = (csa.get("booking_and_create") or {}).get("direct_order") or {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _business_default(business_config: Dict[str, Any]) -> Dict[str, Any]:
        csa = business_config.get("china_southern_air") or {}
        value = (csa.get("booking_and_create") or {}).get("business_default") or {}
        return value if isinstance(value, dict) else {}

    @classmethod
    def get_form_values(
        cls, form_data: Dict[str, Any], business_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        bookings = form_data.get("bookings")
        if not isinstance(bookings, list) or not bookings or not isinstance(bookings[0], dict):
            raise ChinaSouthernAirDirectBookingError("南航订舱 form_data.bookings 必须包含一条订舱数据")
        item = bookings[0]
        defaults = cls._business_default(business_config)

        product_name = item.get("product_name")
        if isinstance(product_name, list):
            product_name = product_name[0] if product_name else ""
        contact_name = form_data.get("order_contact_name") or defaults.get("order_contact_name")
        contact_phone = form_data.get("order_contact_phone") or defaults.get("order_contact_phone")
        if not contact_phone and contact_name and "/" in str(contact_name):
            contact_name, contact_phone = str(contact_name).split("/", 1)
        selected_fee = cls._required_text(
            form_data.get("outbound_cargo_and_mail_handling_fee_options")
            or item.get("outbound_cargo_and_mail_handling_fee_options"),
            "outbound_cargo_and_mail_handling_fee_options",
        )
        if selected_fee not in cls.ALLOWED_HANDLING_FEE_OPTIONS:
            raise ChinaSouthernAirDirectBookingError(
                "出港货邮处理费选项仅支持：贵重物品、活体动物、危险品、鲜活容腐、普货、急件快件"
            )

        return {
            "origin_station": cls._required_text(item.get("origin_station"), "bookings[0].origin_station").upper(),
            "destination": cls._required_text(item.get("destination"), "bookings[0].destination").upper(),
            "flight_date": cls._required_text(item.get("flight_date"), "bookings[0].flight_date"),
            "flight_number": cls._required_text(item.get("flight_number"), "bookings[0].flight_number").upper(),
            "shipper_unit": cls._required_text(item.get("shipper_unit"), "bookings[0].shipper_unit"),
            "shipment_type_name": cls._required_text(item.get("cargo_type"), "bookings[0].cargo_type"),
            "rate_code": cls._required_text(item.get("cargo_type_code"), "bookings[0].cargo_type_code"),
            "commodity_code": cls._required_text(item.get("cargo_code"), "bookings[0].cargo_code"),
            "commodity_name": cls._required_text(item.get("cargo_name"), "bookings[0].cargo_name"),
            "piece": cls._number(item.get("quantity"), "bookings[0].quantity", integer=True),
            "weight": cls._number(item.get("weight"), "bookings[0].weight"),
            "volume": cls._number(item.get("booking_volume"), "bookings[0].booking_volume", allow_empty=True),
            "product_name": cls._required_text(product_name, "bookings[0].product_name"),
            "over_standard_cus": cls._number(
                item.get("oversized_cargo", 0),
                "bookings[0].oversized_cargo",
                integer=True,
                allow_empty=True,
                allow_zero=True,
            ),
            "sp_code": cls._required_text(item.get("special_cargo_code"), "bookings[0].special_cargo_code"),
            "handling_info": str(item.get("storage_and_transportation_precautions") or "").strip() or None,
            "dangerous_check_required": str(item.get("no_dangerous_goods", "")).strip() == "0",
            "booking_remark_wide": str(item.get("booking_remark_wide") or defaults.get("booking_remark_wide") or "").strip(),
            "booking_remark_narrow": str(item.get("booking_remark_narrow") or defaults.get("booking_remark_narrow") or "").strip(),
            "selected_fee": selected_fee,
            "agent_check_name": cls._required_text(defaults.get("agent_checker_name"), "系统参数.代理公司检查人名称"),
            "agent_carrier_name": cls._required_text(defaults.get("agent_consignor_name"), "系统参数.代理公司交运人名称"),
            "contact_name": cls._required_text(
                contact_name,
                "系统参数.订单联系人名称",
            ),
            "contact_phone": cls._required_text(
                contact_phone,
                "系统参数.订单联系人电话",
            ),
            "accounting_rule": str(
                form_data.get("settlement_file_number") or defaults.get("settlement_file_number") or ""
            ).strip() or None,
        }

    @staticmethod
    def _rules(value: Any, defaults: List[str]) -> List[str]:
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError, json.JSONDecodeError):
                value = [part.strip() for part in value.split(",") if part.strip()]
        if not isinstance(value, list):
            value = defaults
        return [str(item).strip().upper() for item in value if str(item).strip()]

    @classmethod
    def _select_booking_memo(
        cls, aircraft_type: str, values: Dict[str, Any], business_config: Dict[str, Any]
    ) -> str:
        config = cls._booking_config(business_config)
        wide_rules = cls._rules(config.get("wide"), ["35", "33", "74", "77", "78"])
        narrow_rules = cls._rules(config.get("narrow"), ["31", "32", "73", "38", "21"])
        normalized = aircraft_type.strip().upper()
        if any(normalized.startswith(rule) for rule in wide_rules):
            return values["booking_remark_wide"]
        if any(normalized.startswith(rule) for rule in narrow_rules):
            return values["booking_remark_narrow"]
        raise ChinaSouthernAirDirectBookingError(
            f"航班机型 {aircraft_type} 未匹配系统配置中的宽窄体机型规则"
        )

    async def query_matching_flight(
        self, *, token: str, values: Dict[str, Any], business_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        cleaned_token = ChinaSouthernAirService._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirDirectBookingError("南航登录令牌无效，请先刷新南航 Token")
        config = self._direct_order_config(business_config)
        payload = {
            "channel": "B2B",
            "domint": "D",
            "flightdate": values["flight_date"],
            "flightDep": values["origin_station"],
            "flightDest": values["destination"],
            "segId": 1,
            "flightNature": "",
        }
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/booking",
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": cleaned_token,
            "x-customs-userid": str(config.get("agent_code", "SZXFED")),
        }
        if config.get("cookie"):
            headers["Cookie"] = str(config["cookie"])
        try:
            timeout = httpx.Timeout(20.0, connect=5.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(self.FLIGHT_QUERY_URL, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ChinaSouthernAirDirectBookingError(
                f"南航航班机型查询失败（HTTP {exc.response.status_code}）"
            ) from exc
        except httpx.RequestError as exc:
            raise ChinaSouthernAirDirectBookingError("南航航班机型查询服务暂时不可用") from exc
        try:
            response_data = response.json()
        except ValueError as exc:
            raise ChinaSouthernAirDirectBookingError("南航航班机型查询返回了无效数据") from exc
        if not isinstance(response_data, dict):
            raise ChinaSouthernAirDirectBookingError("南航航班机型查询返回格式异常")
        if str(response_data.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirDirectBookingError(
                ChinaSouthernAirService._response_message(response_data, "南航航班机型查询失败")
            )
        flights = response_data.get("result")
        if not isinstance(flights, list):
            raise ChinaSouthernAirDirectBookingError("南航航班机型查询未返回航班列表")
        for flight in flights:
            if not isinstance(flight, dict):
                continue
            if str(flight.get("flightno") or "").strip().upper() != values["flight_number"]:
                continue
            aircraft_type = str(flight.get("actype") or "").strip()
            if not aircraft_type:
                raise ChinaSouthernAirDirectBookingError(
                    f"南航航班 {values['flight_number']} 未返回机型"
                )
            matched = deepcopy(flight)
            matched["actype"] = aircraft_type
            matched["acno"] = str(flight.get("acno") or "").strip()
            matched["bookMemo"] = self._select_booking_memo(
                aircraft_type, values, business_config
            )
            return matched
        raise ChinaSouthernAirDirectBookingError(
            f"南航未查询到航班 {values['flight_number']} 的机型信息"
        )

    @classmethod
    def select_handling_fee(
        cls, service_charges: List[Dict[str, Any]], selected_name: str
    ) -> List[Dict[str, Any]]:
        """在完整费用列表中仅勾选用户指定的出港货邮处理费。"""
        requested_name = selected_name
        selected_name = "鲜活易腐" if selected_name == "鲜活容腐" else selected_name
        result = deepcopy(service_charges)
        found_group = False
        found_option = False
        available_options: List[str] = []
        upstream_group: Optional[Dict[str, Any]] = None
        for group in result:
            if group.get("serviceMainName") != cls.OUTBOUND_HANDLING_FEE_NAME:
                continue
            found_group = True
            upstream_group = deepcopy(group)
            details = group.get("serviceCharges")
            if not isinstance(details, list):
                raise ChinaSouthernAirDirectBookingError("南航出港货邮处理费明细格式异常")
            group["checked"] = "Y"
            for detail in details:
                if not isinstance(detail, dict):
                    continue
                option_name = str(detail.get("otherChargeName") or "").strip()
                if option_name and option_name not in available_options:
                    available_options.append(option_name)
                matched = option_name == selected_name
                detail["checked"] = "Y" if matched else "N"
                found_option = found_option or matched
            break
        if not found_group:
            raise ChinaSouthernAirDirectBookingError(
                "南航费用查询未返回出港货邮处理费",
                details={
                    "selected_option": requested_name,
                    "normalized_selected_option": selected_name,
                    "available_options": [],
                    "upstream_response": {
                        "extServiceCharges": deepcopy(service_charges),
                    },
                },
            )
        if not found_option:
            options_text = "、".join(available_options) if available_options else "无"
            raise ChinaSouthernAirDirectBookingError(
                f"南航出港货邮处理费中没有选项：{requested_name}；当前可选项：{options_text}",
                details={
                    "selected_option": requested_name,
                    "normalized_selected_option": selected_name,
                    "available_options": available_options,
                    "upstream_response": upstream_group,
                },
            )
        return result

    @staticmethod
    def build_calculate_payload(
        values: Dict[str, Any], service_charges: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
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
                    "rateCode": values["rate_code"],
                    "shipmentTypeName": values["shipment_type_name"],
                    "piece": values["piece"],
                    "weight": values["weight"],
                    "volume": values["volume"],
                    "bookGrade": "A",
                    "spaceClass": "A",
                    "subSpaceClass": "A6",
                },
            },
            "extServiceCharges": deepcopy(service_charges),
            "commodityCode": {
                "commoditycode": values["commodity_code"],
                "cname": values["commodity_name"],
            },
        }

    @classmethod
    def build_create_payload(
        cls,
        values: Dict[str, Any],
        business_config: Dict[str, Any],
        *,
        flight: Dict[str, Any],
        number_prefix: str,
        number_suffix: str,
        calculation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        calculated_fees = calculation_result.get("extServiceCharges")
        if not isinstance(calculated_fees, list):
            raise ChinaSouthernAirDirectBookingError("南航费用计算未返回完整的扩展服务费列表")
        config = cls._direct_order_config(business_config)
        carrier = str(config.get("carrier", "CZ"))
        dangerous_value = 1 if values["dangerous_check_required"] else 0
        flight_price = calculation_result.get("flightPriceCalculateResult") or {}
        shipment = {
            "agentCode": str(config.get("agent_code", "SZXFED")),
            "agentIataCode": config.get("agent_iata_code", "08305167"),
            "rateCode": values["rate_code"],
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
            "parentProductionName": values["product_name"],
            "parentProductionNameCn": values["product_name"],
            "rateClass": flight_price.get("rateClass") or config.get("rate_class", "M"),
            "coldStorage": None,
            "spCode": values["sp_code"],
            "attachedFile": None,
            "treatment": None,
            "processSituation": None,
            "handlingInfo": values["handling_info"],
            "dvfCarrier": None,
            "dvfCarrierFee": 0,
            "certificationForTransport": None,
            "rateCharge": calculation_result.get("rateCharge"),
            "weightCharge": calculation_result.get("weightCharge"),
            "publicRateCharge": calculation_result.get("publicRateCharge"),
            "wtVal": config.get("wt_val", "P"),
            "otherChargeStatement": config.get("other_charge_statement", "P"),
            "customsStatusOfGoods": config.get("customs_status_of_goods", "001"),
            "exchangeRate": 1,
            "overStandardCus": values["over_standard_cus"],
        }
        return {
            "resAllInfoList": [{"resDto": {
                "flightDep": values["origin_station"],
                "flightDest": values["destination"],
                "bookFlightno": values["flight_number"],
                "bookFlightdate": values["flight_date"],
                "carrier": carrier,
                "routing": f"{values['origin_station']}{carrier}/{values['destination']}",
                "bookMemo": flight["bookMemo"],
                "acType": flight["actype"],
                "acno": flight.get("acno") or None,
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
                "orderShipment": shipment,
                "listOrderShipmentDim": None,
                "orderShipmentAwb": {
                    "awbprefix": str(number_prefix).rstrip("-"),
                    "awbno": str(number_suffix),
                    "awbpostfix": str(config.get("awb_postfix", "00000000")),
                    "awbNoType": str(config.get("awb_no_type", "BMI")),
                },
                "orderShipmentDangerous": None,
                "orderShipmentContact": {"consigneeName": values["shipper_unit"]},
                "orderShipmentLiveAnimals": None,
            },
            "addServiceCharges": [],
            "extServiceCharges": deepcopy(calculated_fees),
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
        return await china_southern_air_direct_order_service.calculate_charge(
            token=token, payload=payload, business_config=business_config
        )

    async def create_order(
        self, *, token: str, payload: Dict[str, Any], business_config: Dict[str, Any]
    ) -> Any:
        return await china_southern_air_direct_order_service.create_order(
            token=token, payload=payload, business_config=business_config
        )


china_southern_air_direct_booking_service = ChinaSouthernAirDirectBookingService()
