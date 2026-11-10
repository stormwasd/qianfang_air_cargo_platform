"""南航订舱后修改数据开单的校验与提交协议。

变更请求必须由实时订单详情及变更计费结果构建。本模块不使用抓包中的
订单编号、版本或金额，也不将新建订单的 calculateCharge 结果当作变更报价。
"""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation
import math
from typing import Any
from urllib.parse import urlencode

import httpx

from app.services.china_southern_air_service_client import ChinaSouthernAirService
from app.services.china_southern_air_service_client import china_southern_air_service
from app.services.china_southern_air_direct_order import ChinaSouthernAirDirectOrderService as Order
from app.services.china_southern_air_direct_booking import china_southern_air_direct_booking_service


class ChinaSouthernAirDirectChangeError(Exception):
    """区分确定失败与最终提交结果未知，防止调用方盲目重复变更。"""

    def __init__(self, message: str, *, stage: str, outcome_unknown: bool = False,
                 details: dict | None = None):
        super().__init__(message)
        self.stage = stage
        self.outcome_unknown = outcome_unknown
        self.details = {"stage": stage, "outcome_unknown": outcome_unknown, **(details or {})}


class ChinaSouthernAirDirectChangeService:
    BASE_URL = "https://cargo.csair.com/order-center/b2e-change/b2bChangeFlightWeight/"
    FORWARD_URL = BASE_URL + "forward"
    CHANGE_PRICE_URL = BASE_URL + "queryChangePrice"
    CALCULATE_CHARGE_URL = BASE_URL + "calculateCharge"
    LIVING_ANIMAL_URL = "https://cargo.csair.com/order-center/b2e-order/b2eOrder/querylivingAnimalProofByorderId"
    GOODS_NAME_CHECK_URL = (
        "https://cargo.csair.com/order-center/b2e-support/goodsNameCheck/allowedGoodsNameCheck"
    )
    CHECK_CHANGE_URL = (
        "https://cargo.csair.com/order-center/b2e-change/b2bChangeFlightWeight/checkChange"
    )
    CREATE_CHANGE_URL = (
        "https://cargo.csair.com/order-center/b2e-change/b2bChangeFlightWeight/createChange"
    )

    async def _post(self, client: httpx.AsyncClient, url: str, *, headers: dict,
                    payload: dict, stage: str, is_submission: bool = False) -> Any:
        try:
            response = await client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            # 不将异常文本或请求头返回，避免认证信息进入日志/接口响应。
            raise ChinaSouthernAirDirectChangeError(
                "南航变更接口连接失败" + ("，提交结果未知，请先核查南航订单" if is_submission else ""),
                stage=stage, outcome_unknown=is_submission,
            ) from exc

        try:
            body = response.json()
        except ValueError:
            body = None
        if not response.is_success:
            raise ChinaSouthernAirDirectChangeError(
                f"南航变更接口返回 HTTP {response.status_code}", stage=stage,
                outcome_unknown=is_submission and response.status_code >= 500,
                details={"http_status": response.status_code},
            )
        if not isinstance(body, dict):
            raise ChinaSouthernAirDirectChangeError(
                "南航变更接口返回格式异常", stage=stage, outcome_unknown=is_submission,
            )
        if str(body.get("code", "")) not in {"0000", "0"}:
            raise ChinaSouthernAirDirectChangeError(
                ChinaSouthernAirService._response_message(body, "南航变更接口处理失败"),
                stage=stage, details={"upstream_code": body.get("code")},
            )
        return body.get("result")

    @staticmethod
    def _headers(token: str, agent_code: str, order_id: str, cookie: str | None = None) -> dict:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/json;charset=UTF-8",
            "Origin": "https://cargo.csair.com",
            "Referer": "https://cargo.csair.com/tangb2gweb/super-change?" + urlencode({
                "orderId": order_id, "intDom": 0,
            }),
            "User-Agent": "qianfang-air-cargo-platform/1.0",
            "x-customs-user": token,
            "x-customs-userid": agent_code,
        }
        if cookie:
            headers["Cookie"] = cookie
        return headers

    @staticmethod
    def form_values(form_data: dict, business_config: dict) -> tuple[dict, dict]:
        form = deepcopy(form_data)
        for key in ("flight_info", "cargo_info", "contact_info", "other_info", "dangerous_goods_declaration"):
            if form.get(key) is not None and not isinstance(form[key], dict):
                raise ChinaSouthernAirDirectChangeError(f"form_data.{key} 必须为对象", stage="prepare_change")
        contact = form.get("contact_info") or {}
        if contact.get("address") is not None and not isinstance(contact["address"], dict):
            raise ChinaSouthernAirDirectChangeError("form_data.contact_info.address 必须为对象", stage="prepare_change")
        other = form.get("other_info")
        if isinstance(other, dict):
            name = str(other.get("order_contact") or "").strip()
            if "/" in name:
                name, phone = name.split("/", 1)
                other["order_contact"] = name.strip()
                if not str(other.get("contact_phone") or "").strip():
                    other["contact_phone"] = phone.strip()
        cargo = form.get("cargo_info") or {}
        for key in ("quantity", "weight", "booking_volume"):
            raw = cargo.get(key) if isinstance(cargo, dict) else None
            if isinstance(raw, bool):
                raise ChinaSouthernAirDirectChangeError(f"南航变更字段 {key} 必须是数字", stage="prepare_change")
        values = Order.get_form_values(form, business_config)
        if not str(cargo.get("cargo_type_code") or "").strip():
            raise ChinaSouthernAirDirectChangeError("缺少货物类型代码，请重新选择货物类型", stage="prepare_change")
        for key in ("weight", "volume", "piece"):
            value = values[key]
            if value is not None and (not math.isfinite(value) or value <= 0):
                raise ChinaSouthernAirDirectChangeError(f"南航变更字段 {key} 必须大于 0 且为有限数字", stage="prepare_change")
        quantity = float(form["cargo_info"]["quantity"])
        if not quantity.is_integer():
            raise ChinaSouthernAirDirectChangeError("南航变更件数必须为正整数", stage="prepare_change")
        date.fromisoformat(values["flight_date"])
        if values["dangerous_check_required"] and not all((values["agent_check_name"], values["agent_carrier_name"])):
            raise ChinaSouthernAirDirectChangeError("请填写禁止隐瞒危险品声明的检查人和交运人签名", stage="prepare_change")
        if values["selected_fee"] is not None:
            values["selected_fee"] = Order._normalize_selected_fee(values["selected_fee"], values["shipment_type_name"])
        return form, values

    @staticmethod
    def _required_mapping(value: Any, stage: str, label: str) -> dict:
        if not isinstance(value, dict) or not value:
            raise ChinaSouthernAirDirectChangeError(f"南航未返回有效{label}", stage=stage)
        return value

    @staticmethod
    def _select_price(result: dict, product: str) -> dict:
        candidates = []
        for charge in result.get("charge") or []:
            if not isinstance(charge, dict):
                continue
            price = charge.get("flightPriceCalculateResult")
            if not isinstance(price, dict):
                continue
            names = (charge.get("parentProductionName"), price.get("rateName"))
            if product not in names:
                continue
            if all(price.get(key) is not None for key in ("spaceClass", "subSpaceClass", "rateCharge", "weightCharge", "rateClass")):
                candidates.append({**price, "parentProductionName": product})
        if len(candidates) != 1:
            raise ChinaSouthernAirDirectChangeError(
                f"南航变更运价未返回产品“{product}”的唯一可用舱位", stage="query_change_price",
            )
        return candidates[0]

    @staticmethod
    def _apply_fee_selection(charge: dict, selected: dict | None) -> bool:
        """同步分组与扁平费用明细；沿用网页必填单项勾选规则。"""
        changed = False
        target_group_found = False
        selected_names = None
        if selected is not None:
            selected_names = {
                row.get("otherChargeName") for row in selected["serviceCharges"]
                if isinstance(row, dict) and row.get("checked") == "Y"
            }
            if not selected_names:
                raise ChinaSouthernAirDirectChangeError("请至少选择一项出港货邮处理费", stage="calculate_change_charge")
        for group_key, flat_key in (("additionalMainCharges", "additionalCharges"),
                                     ("extensionMainCharges", "extensionCharges")):
            groups = charge.get(group_key) or []
            flat = charge.get(flat_key) or []
            for group in groups:
                rows = group.get("subCharges") or []
                selectable = [row for row in rows if row.get("changeType") != "D"]
                is_selected_group = selected_names is not None and group.get("serviceMainName") == Order.OUTBOUND_HANDLING_FEE_NAME
                if is_selected_group:
                    target_group_found = True
                    available = {row.get("otherChargeName") for row in selectable}
                    if not selected_names <= available:
                        raise ChinaSouthernAirDirectChangeError("所选出港货邮处理费不在南航变更费用列表中", stage="calculate_change_charge")
                for row in selectable:
                    checked = row.get("newChecked")
                    auto_required = group.get("mandatory") == "Y" and len(selectable) == 1
                    if is_selected_group:
                        checked = "Y" if row.get("otherChargeName") in selected_names else "N"
                    elif auto_required:
                        checked = "Y"
                    amount = row.get("newAmount")
                    if (checked == "Y" and row.get("rateUnit") == "TC"
                            and (auto_required or (is_selected_group and row.get("newChecked") != "Y"))):
                        amount = 1
                    for item in [row, *[v for v in flat if v.get("otherChargeCode") == row.get("otherChargeCode")
                                       and v.get("serviceMainName") == group.get("serviceMainName")
                                       and v.get("changeType") == row.get("changeType")]]:
                        if item.get("newChecked") != checked or item.get("newAmount") != amount:
                            item.update(newChecked=checked, newAmount=amount)
                            changed = True
                if group.get("mandatory") == "Y":
                    changed = changed or group.get("newChecked") != "Y"
                    group["newChecked"] = "Y"
        if selected_names is not None and not target_group_found:
            raise ChinaSouthernAirDirectChangeError("南航变更费用列表缺少出港货邮处理费", stage="calculate_change_charge")
        return changed

    async def prepare(self, *, token: str, awb_number: str, form_data: dict,
                      business_config: dict) -> tuple[dict, dict, dict]:
        """按南航 super-change 前端协议获取实时上下文及重新计费。"""
        form, values = self.form_values(form_data, business_config)
        config = Order._direct_order_config(business_config)
        agent = str(config.get("agent_code") or "SZXFED").strip()
        cleaned_token = ChinaSouthernAirService._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirDirectChangeError("南航登录令牌无效，请先刷新南航 Token", stage="prepare_change")
        prefix, separator, suffix = awb_number.partition("-")
        if not separator or not prefix.isdigit() or len(prefix) != 3 or not suffix.isdigit() or len(suffix) != 8:
            raise ChinaSouthernAirDirectChangeError("订舱主单号格式不正确", stage="prepare_change")
        orders = await china_southern_air_service.query_waybill_orders(token=token, awb_no=suffix, customer_no=agent)
        active = [row for row in orders if row.get("status") != "C" and row.get("statusCN") != "已取消"]
        if len(active) != 1 or not str(active[0].get("orderId") or "").startswith("B"):
            raise ChinaSouthernAirDirectChangeError("未找到唯一有效的南航 B2B 订单，请核查主单号", stage="query_change_order")
        order_id = active[0]["orderId"]
        headers = self._headers(cleaned_token, agent, order_id, config.get("cookie"))
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            forward = self._required_mapping(await self._post(
                client, self.FORWARD_URL, headers=headers, payload={"orderId": order_id}, stage="forward_change",
            ), "forward_change", "变更订单上下文")
            payload = deepcopy(forward)
            total = self._required_mapping(payload.get("totalOrderDetail"), "forward_change", "订单详情")
            detail = self._required_mapping(total.get("orderDetailDto"), "forward_change", "订单明细")
            if (detail.get("orderId") != order_id or str(detail.get("awbPrefix")) != prefix
                    or str(detail.get("awbNo")) != suffix or detail.get("agentCode") != agent
                    or detail.get("version") is None):
                raise ChinaSouthernAirDirectChangeError("南航订单编号、主单号、代理或版本不匹配", stage="forward_change")
            animal_proof = await self._post(
                client, self.LIVING_ANIMAL_URL, headers=headers, payload={"orderId": order_id}, stage="query_living_animal",
            )
            living_animal = None
            if animal_proof is not None:
                proof = self._required_mapping(animal_proof, "query_living_animal", "活体动物声明")
                living_animal = {"orderId": order_id, **{f"item{i}": proof.get(f"item{i}", "N") for i in range(1, 8)}}
                living_animal["details"] = [
                    {key: proof.get(f"{key}{i}") for key in ("packageNum", "animalTypeName", "animalNum", "containerNo")}
                    for i in range(1, 5) if proof.get(f"animalTypeName{i}")
                ]
            original_flights = detail.get("orderDetailFlightInfo")
            if not isinstance(original_flights, list) or len(original_flights) != 1:
                raise ChinaSouthernAirDirectChangeError("当前表单仅支持单航段修改数据开单，请使用 RPA 处理多航段订单", stage="forward_change")
            old_flight = original_flights[0]
            dimensions = deepcopy(detail.get("dimensions") or [])
            if old_flight.get("bookId") is None or old_flight.get("segmentId") is None:
                raise ChinaSouthernAirDirectChangeError("南航订单缺少航段标识", stage="forward_change")
            memo_values = {**values, **{
                key: form.get("flight_info", {}).get(key) or values.get("booking_remark") or ""
                for key in ("booking_remark_wide", "booking_remark_narrow")
            }}
            flight = await china_southern_air_direct_booking_service.query_matching_flight(
                token=token, values=memo_values, business_config=business_config,
            )
            new_flight = {key: deepcopy(old_flight.get(key)) for key in (
                "bookId", "segmentId", "bookStatus", "bookUldt", "bookUldp", "bookUldc", "resPlateDtos",
            )}
            new_flight.update(
                dep=values["origin_station"], dest=values["destination"], flightNo=values["flight_number"],
                flightDate=values["flight_date"] + " 00:00:00", carrier=values["flight_number"][:2],
                acType=flight["actype"], bookMemo=flight["bookMemo"],
            )
            new_flight["resPlateDtos"] = new_flight["resPlateDtos"] or []
            cweight = self._required_mapping(await self._post(
                client, ChinaSouthernAirService.CALCULATE_CWEIGHT_URL, headers=headers,
                payload={"depCityCode": values["origin_station"], "weight": values["weight"],
                         "volume": values["volume"] if values["volume"] is not None else "",
                         "change": True, "dimensions": dimensions or None, "channel": "B2B"}, stage="calculate_change_cweight",
            ), "calculate_change_cweight", "计费重量")
            for key in ("volume", "cweight"):
                number = cweight.get(key)
                if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number <= 0:
                    raise ChinaSouthernAirDirectChangeError("南航变更计费重量或体积无效", stage="calculate_change_cweight")
            values["volume"] = cweight["volume"]
            product = Order.effective_product_name(values, business_config)
            rate_code = values["rate_code"]
            price_result = self._required_mapping(await self._post(
                client, self.CHANGE_PRICE_URL, headers=headers, stage="query_change_price", payload={
                    "spaceClassParamMultDto": {
                        "awbNo": suffix, "awbPrefix": prefix, "awbPostfix": detail.get("awbPostfix"),
                        "customerCode": agent, "rateCode": rate_code, "channel": "B",
                        "flights": [{"flightDep": values["origin_station"], "flightDest": values["destination"],
                                     "flightNo": values["flight_number"], "flightDate": values["flight_date"]}],
                    },
                    "orderShipmentCreateDto": {
                        "directTransfer": detail.get("directTransfer"), "rateType": detail.get("rateTypeEn"),
                        "shipmentType": rate_code, "shipmentTypeName": values["shipment_type_name"],
                        "weight": values["weight"], "volume": values["volume"], "dimensions": dimensions or None, "change": True,
                    },
                },
            ), "query_change_price", "变更运价")
            price = self._select_price(price_result, product)
            codes = await Order().resolve_special_cargo_code(token=token, values=values, business_config=business_config)
            production_code = codes["default_code"]
            changed_flight = any(str(old_flight.get(old) or "")[:10] != str(new_flight[new])[:10]
                                 for old, new in (("dep", "dep"), ("dest", "dest"), ("flightNo", "flightNo"), ("flightDate", "flightDate")))
            detail.update(piece=values["piece"], weight=values["weight"], volume=values["volume"],
                          cweight=cweight["cweight"], dimensions=dimensions, bookGrade=price["subSpaceClass"])
            charge = self._required_mapping(payload.get("changeCharge"), "forward_change", "原始变更费用")
            charge.update(rateCharge=price["rateCharge"], weightCharge=price["weightCharge"])
            payload.update(
                changeReason="自愿修改", changeIntent="Y", contactName=values["contact_name"],
                contactPhone=values["contact_phone"], flights=[new_flight], changeOtherDto=None,
                hasChangeFlight="Y" if changed_flight else "N", isChangeWeight="Y", isChangeRate="N",
                spaceClass=price["spaceClass"], subSpaceClass=price["subSpaceClass"],
                parentProductionName=product, productionCode=production_code,
                rateCharge=price["rateCharge"], weightCharge=price["weightCharge"],
            )
            if detail.get("orderStatusCName") == "待审批":
                payload["changeType"] = "B"
            # 费用必须由变更接口计算，保留旧值、差额、附加费和延伸费上下文。
            for _ in range(3):
                charge = self._required_mapping(await self._post(
                    client, self.CALCULATE_CHARGE_URL, headers=headers, payload=payload, stage="calculate_change_charge",
                ), "calculate_change_charge", "变更计费结果")
                if any(charge.get(key) is None for key in ("rateCharge", "weightCharge", "diffTotalCharge")):
                    raise ChinaSouthernAirDirectChangeError("南航变更计费缺少运价、运费或差额", stage="calculate_change_charge")
                payload.update(changeCharge=charge, rateCharge=charge["rateCharge"], weightCharge=charge["weightCharge"])
                payload["isChangeWeight"] = "N"
                if not self._apply_fee_selection(charge, values["selected_fee"]):
                    break
            else:
                raise ChinaSouthernAirDirectChangeError("南航变更费用勾选重新计费未收敛", stage="calculate_change_charge")
            order_payload = Order._build_order_payload(values, config, [])
            contacts = order_payload["orderInfo"]["orderShipmentContact"]
            dangerous = deepcopy((total.get("extendsShipmentInfo") or {}).get("awbDangerouscheckDto") or {})
            if form.get("dangerous_goods_declaration"):
                dangerous.update(order_payload["awbDangerousCheck"])
            extra = total.get("extendsShipmentInfo") or {}
            other = deepcopy(detail.get("orderShipmentContact") or {})
            # 表单只修改其承载的联系人字段，其余证件、通知人、司机信息保留原订单值。
            for key in ("shipperName", "shipperMobile", "shipperState", "shipperCity", "shipperDistrict",
                        "shipperAddress", "shipperCountryCode", "consigneeName", "consigneeMobile",
                        "consigneeAddress", "consigneeCountryCode", "selfPickUp"):
                other[key] = contacts[key]
            other.update(
                agentCode=agent, flgihtDep=values["origin_station"], flightDest=values["destination"],
                goodsInputMethod=config.get("goods_input_method", 0), shipmentTypeName=values["shipment_type_name"],
                goodsCode=values["commodity_code"], goods=values["commodity_name"],
                specialCodes=values["sp_code"], productionCode=production_code, bookGrade=str(price["spaceClass"])[:1],
                rateClass=price["rateClass"], awbDangerousCheck=dangerous,
                dangerousCargoCodes=detail.get("dangerousCargoIDs"),
                awbLithiumBatteryInfomationDto=extra.get("awbLithiumBatteryInfomationDto"),
                awbLithiumBatteryDetailsList=extra.get("lithiumBatteryDetails"),
                changeLithiumBatteryCheckItemsList=extra.get("checkItemslist"),
                attachedFile=detail.get("attachedFile"), treatment=detail.get("treatment"),
                processSituation=detail.get("processSituation"), handlingInfo=(values["handling_info"]
                    if "storage_and_transportation_precautions" in form["cargo_info"] else detail.get("handlingInfo")),
                certificationForTransport=detail.get("certificationForTransport"), coldStorage=detail.get("coldStorage"),
                accountingRule=values["accounting_rule"], accountingInfo=config.get("accounting_info", "文件：限南航承运"),
                contactName=values["contact_name"], contactPhone=values["contact_phone"],
                intent="Y", changeIntent="自愿修改", exchangeRate=1, orderId=order_id,
                payMethod="PP", userId=agent, version=detail["version"],
                actualCweight=extra.get("actualCweight"), chargeDueAgent=extra.get("chargeDueAgent"),
                chargeDueCarrier=extra.get("chargeDueCarrier"), allin=extra.get("allin"),
                tax=(total.get("extendsChargeInfo") or {}).get("tax"), overStandardCus=values["over_standard_cus"],
            )
            other.update(
                consigneeIdType=other.get("consigneeCertType"), driverIdType=other.get("driverCertType"),
                shipperIdType=other.get("shipperCertType"), notify=bool(other.get("notifyName")),
                orderShipmentLiveanimals=living_animal,
            )
            payload["changeOtherDto"] = other
            form["cargo_info"]["booking_volume"] = values["volume"]
            form["cargo_info"]["special_cargo_code"] = codes["platform_code"]
            form["cargo_info"]["storage_and_transportation_precautions"] = other["handlingInfo"]
            return payload, {"intdom": "0", "goodsName": values["commodity_name"],
                             "flightInfos": [{"actype": flight["actype"], "flightno": values["flight_number"]}]}, form

    @staticmethod
    def settlement_calculation(payload: dict) -> dict:
        """适配变更计费的最终金额，差额不得作为最终费用落库。"""
        charge = payload["changeCharge"]
        def number(value):
            result = Decimal(str(value))
            if not result.is_finite():
                raise ValueError("Invalid charge")
            return result
        try:
            total = number(charge["oldTotalCharge"]) + number(charge["diffTotalCharge"])
            extension = charge.get("totalExtensionChargesFee")
            if extension is None:
                extension = sum((number(row["chargeAmount"]) for row in charge.get("extensionCharges") or []
                                 if row.get("newChecked") == "Y" and row.get("chargeAmount") is not None), Decimal(0))
            price = charge.get("flightPriceCalculateResult") or {}
            return {
                "flightPriceCalculateResult": {"norRate": charge.get("norRate", price.get("norRate", ""))},
                "weightCharge": charge["weightCharge"], "oilFee": price.get("oilFee", charge.get("oilFee", "")),
                "totalExtensionCharge": str(extension), "totalCharge": str(total),
                "cweight": payload["totalOrderDetail"]["orderDetailDto"]["cweight"],
            }
        except (KeyError, TypeError, ValueError, InvalidOperation) as exc:
            raise ChinaSouthernAirDirectChangeError("南航变更计费缺少有效的最终费用", stage="calculate_change_charge") from exc

    async def validate_and_submit(self, *, token: str, agent_code: str,
                                  goods_check_payload: dict, change_payload: dict,
                                  cookie: str | None = None) -> dict:
        """顺序校验货名、校验变更、提交同一份变更；任何失败均不继续下一步。

        这里只接收已从真实订单详情及变更计费结果构建的请求体，不接受示例
        模板或从前端透传的订单上下文。不自动重试最终的 createChange。
        """
        stage = "prepare_change"
        cleaned_token = ChinaSouthernAirService._clean_token(token)
        if not cleaned_token:
            raise ChinaSouthernAirDirectChangeError("南航登录令牌无效，请先刷新南航 Token", stage=stage)
        if not isinstance(change_payload, dict) or not isinstance(goods_check_payload, dict):
            raise ChinaSouthernAirDirectChangeError("南航变更请求格式不正确", stage=stage)
        payload = deepcopy(change_payload)
        total_detail = payload.get("totalOrderDetail")
        detail = total_detail.get("orderDetailDto") if isinstance(total_detail, dict) else None
        if not isinstance(detail, dict) or not str(detail.get("orderId") or "").strip():
            raise ChinaSouthernAirDirectChangeError("缺少南航原订单详情", stage=stage)
        if detail.get("version") is None or not isinstance(payload.get("changeCharge"), dict):
            raise ChinaSouthernAirDirectChangeError("缺少南航原订单版本或实时变更计费结果", stage=stage)
        if not str(agent_code or "").strip():
            raise ChinaSouthernAirDirectChangeError("缺少南航代理代码", stage=stage)
        headers = self._headers(cleaned_token, str(agent_code).strip(), detail["orderId"], cookie)
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0)) as client:
            check = await self._post(
                client, self.GOODS_NAME_CHECK_URL, headers=headers,
                payload=deepcopy(goods_check_payload), stage="check_goods_name",
            )
            # 显式 false 才表示无需检查；缺失/类型错误不能当作校验通过。
            if not isinstance(check, dict) or not (
                check.get("needCheck") is False or
                (check.get("needCheck") is True and check.get("checkPass") is True)
            ):
                raise ChinaSouthernAirDirectChangeError("南航货物名称检测未通过", stage="check_goods_name")
            accepted = await self._post(
                client, self.CHECK_CHANGE_URL, headers=headers, payload=payload, stage="check_change",
            )
            if accepted is not True:
                raise ChinaSouthernAirDirectChangeError("南航变化项检查未通过", stage="check_change")
            result = await self._post(
                client, self.CREATE_CHANGE_URL, headers=headers, payload=payload,
                stage="create_change", is_submission=True,
            )
            if not isinstance(result, dict) or result.get("changeStatus") != "F" or result.get("errorMsg"):
                raise ChinaSouthernAirDirectChangeError(
                    "南航变更尚未确认完成，请先核查南航订单后再处理", stage="create_change",
                    outcome_unknown=True,
                    details={
                        key: result.get(key) for key in ("changeId", "changeStatus", "changeStatusName")
                    } if isinstance(result, dict) else None,
                )
            return result


china_southern_air_direct_change_service = ChinaSouthernAirDirectChangeService()
