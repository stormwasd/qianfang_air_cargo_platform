"""南航原订舱变更协议及接口状态，全部使用合成订单和本地依赖。"""
from contextlib import ExitStack
from copy import deepcopy
import asyncio
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import bookings as api
from app.api.deps import get_current_active_user
from app.database import get_db
from app.main import register_exception_handlers
from app.models.booking import Booking
from app.models.config import BusinessConfig
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.models.nanhang_token import NanHangToken
from app.models.rpa_task import RPATask, RPATaskType
from app.models.settlement import Settlement
from app.models.waybill import Waybill
from app.services import china_southern_air_direct_change as change
from app.services.china_southern_air_service_client import ChinaSouthernAirServiceError
from app.utils.helpers import get_china_now
from tests.test_china_southern_air_booking_volume import _business_config, _direct_order_form

Client = change.ChinaSouthernAirDirectChangeService
Error = change.ChinaSouthernAirDirectChangeError
REAL_ASYNC_CLIENT = httpx.AsyncClient


def form():
    result = _direct_order_form("0.2")
    result.pop("outbound_cargo_and_mail_handling_fee_options")
    result["cargo_info"].update(weight=0.5, quantity=3, special_cargo_code="AKA")
    result["other_info"].update(order_contact="订单联系人/13800138000", contact_phone="")
    return result


def charge():
    return {
        "rateCharge": 50, "weightCharge": 50, "norRate": 6,
        "oldTotalCharge": 206, "diffTotalCharge": -154.55, "otherChargeFee": 1.45,
        "flightPriceCalculateResult": {"oilFee": 1},
        "additionalMainCharges": [], "additionalCharges": [],
        "extensionMainCharges": [],
        "extensionCharges": [{"newChecked": "Y", "chargeAmount": 0.45}],
    }


def fee_charge(*, unit="KG", checked="Y", amount=None, charge_amount=0.45):
    result = charge()
    row = {
        "serviceMainName": "出港货邮处理费", "otherChargeCode": "PU", "otherChargeName": "普货",
        "rateUnit": unit, "changeType": "U", "newChecked": checked, "newAmount": amount,
        "chargeAmount": charge_amount,
    }
    # CSA's group newChecked is a UI-only marker and need not be returned.
    result["extensionMainCharges"] = [{"serviceMainName": "出港货邮处理费", "mandatory": "Y", "subCharges": [deepcopy(row)]}]
    result["extensionCharges"] = [deepcopy(row)]
    return result


def forward():
    return {
        "totalOrderDetail": {
            "orderDetailDto": {
                "orderId": "B-SYNTHETIC", "awbPrefix": "784", "awbNo": "12345670",
                "awbPostfix": "00000000", "agentCode": "SZXFED", "version": 17,
                "directTransfer": "D", "rateTypeEn": "SPY", "orderStatusCName": "待审批",
                "piece": 9, "weight": 99, "volume": 0.6, "cweight": 100,
                "handlingInfo": "原始储运注意事项", "orderShipmentContact": {
                    "notifyName": "原通知人", "driverName": "原司机", "shipperCertType": "ID",
                    "shipperIdno": "synthetic-id", "shipperName": "原托运人", "shipperMobile": "13800138001",
                    "shipperState": "广东省", "shipperCity": "深圳市", "shipperDistrict": "宝安区",
                    "shipperAddress": "原货站", "consigneeName": "原收货人", "consigneeMobile": "13800138002",
                },
                "orderDetailFlightInfo": [{
                    "bookId": 987654, "segmentId": 1, "bookStatus": "KK", "dep": "SZX", "dest": "TAO",
                    "flightNo": "CZ8735", "flightDate": "2026-08-31 00:00:00", "acType": "32N",
                    "bookMemo": "原备注", "resPlateDtos": None,
                }],
            },
            "extendsShipmentInfo": {"awbDangerouscheckDto": {"version": 4, "agentcheckname": "原检查人"}},
            "extendsChargeInfo": None,
        },
        "changeCharge": charge(), "changeType": "S", "version": 8,
    }


def price():
    return {"charge": [{"parentProductionName": "南航标运", "flightPriceCalculateResult": {
        "spaceClass": "A", "subSpaceClass": "A7", "rateCharge": 50, "weightCharge": 50, "rateClass": "M",
    }}]}


class ProtocolFixture:
    def __init__(self):
        self.requests = []
        self.forward = forward()
        self.charge = charge()
        self.overrides = {}

    def handler(self, request):
        name = request.url.path.rsplit("/", 1)[-1]
        payload = json.loads(request.content)
        self.requests.append((name, payload))
        if name in self.overrides:
            override = self.overrides[name]
            if isinstance(override, Exception):
                raise override
            return httpx.Response(**override)
        if name == "saveContactAndLiveAnimals":
            self.forward["totalOrderDetail"]["orderDetailDto"].update(
                orderShipmentContact=deepcopy(payload["orderShipmentContact"]), version=18,
            )
            self.forward["version"] = 9
            return httpx.Response(200, json={"code": "0000", "result": {"MESSAGE": "保存成功"}})
        results = {
            "forward": self.forward, "calculateCWeight": {"volume": 0.01, "cweight": 1},
            "querylivingAnimalProofByorderId": None,
            "queryChangePrice": price(), "calculateCharge": self.charge,
            "allowedGoodsNameCheck": {"needCheck": True, "checkPass": True},
            "checkChange": True, "createChange": {"changeStatus": "F", "changeId": "S-SYNTHETIC"},
        }
        return httpx.Response(200, json={"code": "0000", "result": deepcopy(results[name])})

    def patch(self, stack):
        stack.enter_context(patch.object(change.httpx, "AsyncClient", side_effect=lambda **kwargs:
            REAL_ASYNC_CLIENT(transport=httpx.MockTransport(self.handler), **kwargs)))


def patch_prerequisites(stack):
    stack.enter_context(patch.object(change.china_southern_air_service, "query_waybill_orders", new=AsyncMock(return_value=[
        {"orderId": "B-SYNTHETIC", "status": "T"},
    ])))
    stack.enter_context(patch.object(change.china_southern_air_direct_booking_service, "query_matching_flight",
                                     new=AsyncMock(return_value={"actype": "32N", "bookMemo": "窄体备注"})))

    async def special(**kwargs):
        kwargs["values"]["sp_code"] = "XPS/AKA"
        return {"default_code": "XPS", "platform_code": "XPS,AKA", "csa_code": "XPS/AKA"}
    stack.enter_context(patch.object(change.Order, "resolve_special_cargo_code", new=AsyncMock(side_effect=special)))


class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def prepare(self, fixture):
        with ExitStack() as stack:
            patch_prerequisites(stack)
            fixture.patch(stack)
            return await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())

    async def submit(self, fixture, payload=None):
        if payload is None:
            payload, goods, _ = await self.prepare(fixture)
        else:
            goods = {"intdom": "0", "goodsName": "上衣", "flightInfos": []}
        with ExitStack() as stack:
            fixture.patch(stack)
            return await Client().validate_and_submit(token="synthetic-token", agent_code="SZXFED", goods_check_payload=goods, change_payload=payload)

    async def test_whole_sequence_preserves_identity_uses_live_charge_and_maps_form(self):
        fixture = ProtocolFixture()
        original = deepcopy(fixture.forward)
        payload, goods, submitted = await self.prepare(fixture)
        detail = payload["totalOrderDetail"]["orderDetailDto"]
        self.assertEqual((detail["version"], payload["version"], payload["flights"][0]["bookId"]), (17, 8, 987654))
        self.assertEqual(payload["flights"][0]["flightDate"], "2026-08-31 00:00:00")
        self.assertEqual(payload["flights"][0]["bookMemo"], "窄体备注")
        self.assertEqual((detail["piece"], detail["weight"], detail["volume"], detail["cweight"]), (3, 0.5, 0.01, 1))
        self.assertEqual(detail["bookGrade"], "A7")
        self.assertEqual(payload["changeType"], "B")
        self.assertEqual((payload["productionCode"], payload["changeOtherDto"]["specialCodes"]), ("XPS", "XPS/AKA"))
        other = payload["changeOtherDto"]
        self.assertEqual((other["consigneeName"], other["shipperName"]), ("李四", "张三"))
        self.assertEqual((other["contactName"], other["contactPhone"]), ("订单联系人", "13800138000"))
        self.assertEqual((other["notifyName"], other["driverName"], other["notify"]), ("原通知人", "原司机", True))
        self.assertEqual(other["handlingInfo"], "原始储运注意事项")
        self.assertEqual(other["awbDangerousCheck"]["version"], 4)
        self.assertEqual(submitted["cargo_info"]["booking_volume"], 0.01)
        self.assertEqual(goods["flightInfos"], [{"actype": "32N", "flightno": "CZ8735"}])
        self.assertEqual(fixture.forward, original)
        self.assertEqual(fixture.requests[0], ("forward", {"orderId": "B-SYNTHETIC"}))
        calculation = next(body for name, body in fixture.requests if name == "calculateCharge")
        self.assertIsNone(calculation["changeOtherDto"])
        self.assertEqual(calculation["isChangeWeight"], "Y")
        result = await self.submit(fixture, payload)
        self.assertEqual(result["changeStatus"], "F")
        self.assertEqual([name for name, _ in fixture.requests], ["forward", "querylivingAnimalProofByorderId", "calculateCWeight", "queryChangePrice", "calculateCharge", "allowedGoodsNameCheck", "checkChange", "createChange"])
        self.assertEqual(fixture.requests[-1][1], fixture.requests[-2][1])
        self.assertEqual(Client.settlement_calculation(payload)["totalCharge"], "51.45")
        self.assertEqual(Client.settlement_calculation(payload)["totalExtensionCharge"], "0.45")

    async def test_prerequisite_failures_stop_before_submit(self):
        for stage in ("forward", "querylivingAnimalProofByorderId", "calculateCWeight", "queryChangePrice", "calculateCharge"):
            with self.subTest(stage=stage):
                fixture = ProtocolFixture()
                fixture.overrides[stage] = {"status_code": 200, "json": {"code": "ERROR", "message": "合成业务拒绝"}}
                with self.assertRaises(Error):
                    await self.prepare(fixture)
                self.assertEqual(fixture.requests[-1][0], stage)

    async def test_missing_contacts_are_saved_from_edited_form_then_context_is_refreshed(self):
        fixture = ProtocolFixture()
        original = fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"]
        original["consigneeMobile"] = " "
        payload, _, _ = await self.prepare(fixture)
        names = [name for name, _ in fixture.requests]
        self.assertEqual(names[:3], ["forward", "saveContactAndLiveAnimals", "forward"])
        saved = fixture.requests[1][1]
        self.assertEqual(list(saved), ["orderShipmentContact"])
        contact = saved["orderShipmentContact"]
        self.assertEqual(contact["orderId"], "B-SYNTHETIC")
        self.assertEqual((contact["consigneeName"], contact["consigneeMobile"]), ("李四", "13800138000"))
        self.assertEqual((contact["shipperName"], contact["shipperMobile"]), ("张三", "18979681111"))
        self.assertEqual((contact["shipperState"], contact["shipperCity"], contact["shipperDistrict"], contact["shipperAddress"]),
                         ("江西省", "吉安市", "万安县", "科技园南区"))
        self.assertEqual((contact["consigneeAddress"], contact["selfPickUp"]), ("机场自提", "Y"))
        for key in ("notifyName", "driverName", "shipperCertType", "shipperIdno"):
            self.assertEqual(contact[key], original[key])
        self.assertEqual(payload["totalOrderDetail"]["orderDetailDto"]["version"], 18)
        self.assertEqual(payload["version"], 9)
        calc = next(body for name, body in fixture.requests if name == "calculateCharge")
        self.assertEqual(calc["totalOrderDetail"]["orderDetailDto"]["version"], 18)
        self.assertEqual((await self.submit(fixture, payload))["changeStatus"], "F")
        self.assertEqual(sum(name == "saveContactAndLiveAnimals" for name, _ in fixture.requests), 1)

    async def test_each_required_contact_field_and_absent_group_trigger_save(self):
        for key in Client.REQUIRED_CONTACT_FIELDS:
            with self.subTest(key=key):
                fixture = ProtocolFixture()
                fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"][key] = "  "
                await self.prepare(fixture)
                self.assertEqual(fixture.requests[1][0], "saveContactAndLiveAnimals")
        for empty in (None, {}):
            fixture = ProtocolFixture()
            fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = empty
            await self.prepare(fixture)
            self.assertEqual(fixture.requests[1][0], "saveContactAndLiveAnimals")

    async def test_contact_save_failures_stop_without_calculation_or_invoice(self):
        failures = [
            {"status_code": 200, "json": {"code": "0001", "message": "合成保存拒绝"}},
            {"status_code": 500, "json": {}},
            {"status_code": 200, "text": "not-json"},
            {"status_code": 200, "json": {"code": "0000", "result": None}},
            httpx.ReadTimeout("synthetic"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                fixture = ProtocolFixture()
                fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = None
                fixture.overrides["saveContactAndLiveAnimals"] = failure
                with self.assertRaises(Error) as ctx:
                    await self.prepare(fixture)
                self.assertEqual(ctx.exception.stage, "save_change_contacts")
                self.assertFalse(ctx.exception.outcome_unknown)  # No invoice submission yet.
                self.assertEqual([n for n, _ in fixture.requests], ["forward", "saveContactAndLiveAnimals"])

    async def test_save_success_with_incomplete_refresh_stops_before_calculation(self):
        fixture = ProtocolFixture()
        fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = None
        fixture.overrides["saveContactAndLiveAnimals"] = {"status_code": 200, "json": {"code": "0000", "result": {"MESSAGE": "保存成功"}}}
        with self.assertRaises(Error) as ctx:
            await self.prepare(fixture)
        self.assertEqual(ctx.exception.stage, "verify_change_contacts")
        self.assertEqual([n for n, _ in fixture.requests], ["forward", "saveContactAndLiveAnimals", "forward"])

    async def test_refresh_revalidates_order_identity_after_save(self):
        fixture = ProtocolFixture()
        fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = None
        handler = fixture.handler
        def wrong_identity(request):
            response = handler(request)
            if request.url.path.endswith("/saveContactAndLiveAnimals"):
                fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderId"] = "B-WRONG"
            return response
        fixture.handler = wrong_identity
        with self.assertRaises(Error) as ctx:
            await self.prepare(fixture)
        self.assertEqual(ctx.exception.stage, "refresh_change_context")
        self.assertEqual(fixture.requests[-1][0], "forward")

    async def test_invalid_original_context_never_saves_contacts(self):
        for invalid in ({"orderDetailFlightInfo": []}, {"orderShipmentContact": []}, {"version": None}):
            fixture = ProtocolFixture()
            fixture.forward["totalOrderDetail"]["orderDetailDto"].update(invalid)
            with self.assertRaises(Error):
                await self.prepare(fixture)
            self.assertEqual([n for n, _ in fixture.requests], ["forward"])

    async def test_state_rejection_does_not_trigger_contact_save_or_resubmit(self):
        fixture = ProtocolFixture()
        fixture.overrides["createChange"] = {"status_code": 200, "json": {"code": "0001", "message": "当前状态的订单不允许修改!"}}
        with self.assertRaisesRegex(Error, "当前状态的订单不允许修改"):
            await self.submit(fixture)
        names = [n for n, _ in fixture.requests]
        self.assertNotIn("saveContactAndLiveAnimals", names)
        self.assertEqual(names.count("createChange"), 1)

    async def test_existing_animal_declaration_is_requeried_and_preserved(self):
        fixture = ProtocolFixture()
        fixture.overrides["querylivingAnimalProofByorderId"] = {"status_code": 200, "json": {"code": "0000", "result": {
            "item1": "Y", "animalTypeName1": "合成动物", "containerNo1": 2, "animalNum1": 3, "packageNum1": 1,
        }}}
        payload, _, _ = await self.prepare(fixture)
        declaration = payload["changeOtherDto"]["orderShipmentLiveanimals"]
        self.assertEqual(declaration["item1"], "Y")
        self.assertEqual(declaration["orderId"], "B-SYNTHETIC")
        self.assertEqual(declaration["details"], [{"animalTypeName": "合成动物", "containerNo": 2, "animalNum": 3, "packageNum": 1}])

    async def test_required_fee_is_recalculated_and_snapshot_context_is_preserved(self):
        fixture = ProtocolFixture()
        row = {"otherChargeCode": "PU", "otherChargeName": "普货", "rateUnit": "TC", "changeType": "N", "newChecked": "N"}
        fixture.charge["extensionMainCharges"] = [{"serviceMainName": "出港货邮处理费", "mandatory": "Y", "newChecked": "Y", "subCharges": [deepcopy(row)]}]
        fixture.charge["extensionCharges"] = [{**row, "serviceMainName": "出港货邮处理费"}]
        # Model a provider that returns the user's normalized choices on the second calculation.
        handler = fixture.handler
        def calculate(request):
            if request.url.path.endswith("/calculateCharge") and any(n == "calculateCharge" for n, _ in fixture.requests):
                fixture.charge = json.loads(request.content)["changeCharge"]
                fixture.charge["extensionCharges"][0]["chargeAmount"] = 0.45
            return handler(request)
        fixture.handler = calculate
        payload, _, _ = await self.prepare(fixture)
        calls = [body for name, body in fixture.requests if name == "calculateCharge"]
        self.assertEqual(len(calls), 2)
        self.assertEqual([body["isChangeWeight"] for body in calls], ["Y", "N"])
        self.assertEqual(payload["changeCharge"]["extensionCharges"][0]["newChecked"], "Y")

    async def test_calculated_fee_without_group_marker_does_not_recalculate(self):
        fixture = ProtocolFixture()
        fixture.charge = fee_charge()
        payload, _, _ = await self.prepare(fixture)
        self.assertEqual(sum(name == "calculateCharge" for name, _ in fixture.requests), 1)
        self.assertEqual(payload["changeCharge"]["extensionMainCharges"][0]["newChecked"], "Y")
        self.assertEqual(payload["changeCharge"]["extensionCharges"][0]["chargeAmount"], 0.45)

    async def test_calculated_tc_string_and_numeric_amounts_are_equivalent(self):
        fixture = ProtocolFixture()
        fixture.charge = fee_charge(unit="TC", amount=1)
        fixture.charge["extensionMainCharges"][0]["subCharges"][0]["newAmount"] = "1.00"
        payload, _, _ = await self.prepare(fixture)
        self.assertEqual(sum(name == "calculateCharge" for name, _ in fixture.requests), 1)
        self.assertEqual(payload["changeCharge"]["extensionCharges"][0]["newAmount"], 1)

    async def test_group_only_stale_child_flag_uses_calculated_flat_selection(self):
        fixture = ProtocolFixture()
        fixture.charge = fee_charge(unit="TC", amount=7)
        group = fixture.charge["extensionMainCharges"][0]
        group["mandatory"] = "N"
        group["subCharges"][0].update(newChecked="N", newAmount=None)
        payload, _, _ = await self.prepare(fixture)
        self.assertEqual(sum(name == "calculateCharge" for name, _ in fixture.requests), 1)
        self.assertEqual(payload["changeCharge"]["extensionCharges"][0]["newAmount"], 7)
        self.assertEqual(payload["changeCharge"]["extensionMainCharges"][0]["subCharges"][0]["newChecked"], "Y")

    async def test_required_selected_but_unpriced_fee_stops_before_submit_with_diagnostics(self):
        fixture = ProtocolFixture()
        fixture.charge = fee_charge(charge_amount=None)
        fixture.charge["extensionMainCharges"][0]["newChecked"] = "Y"
        with self.assertRaises(Error) as ctx:
            await self.prepare(fixture)
        self.assertEqual(ctx.exception.stage, "calculate_change_charge")
        self.assertFalse(ctx.exception.outcome_unknown)
        self.assertEqual(sum(name == "calculateCharge" for name, _ in fixture.requests), 3)
        self.assertEqual(ctx.exception.details["fee_selection_issues"][0]["other_charge_code"], "PU")
        self.assertNotIn("createChange", [name for name, _ in fixture.requests])

    async def test_reject_mismatched_identity_and_multiple_segments_and_product(self):
        for mutate in (
            lambda f: f.forward["totalOrderDetail"]["orderDetailDto"].update(awbNo="87654321"),
            lambda f: f.forward["totalOrderDetail"]["orderDetailDto"]["orderDetailFlightInfo"].append({}),
            lambda f: f.overrides.update(queryChangePrice={"status_code": 200, "json": {"code": "0000", "result": {"charge": []}}}),
        ):
            fixture = ProtocolFixture()
            mutate(fixture)
            with self.assertRaises(Error):
                await self.prepare(fixture)
            self.assertNotIn("createChange", [name for name, _ in fixture.requests])

    async def test_goods_and_change_checks_fail_closed(self):
        for stage, response in (("allowedGoodsNameCheck", {"needCheck": True, "checkPass": False}),
                                ("allowedGoodsNameCheck", {}), ("checkChange", False)):
            fixture = ProtocolFixture()
            fixture.overrides[stage] = {"status_code": 200, "json": {"code": "0000", "result": response}}
            with self.assertRaises(Error) as ctx:
                await self.submit(fixture)
            self.assertFalse(ctx.exception.outcome_unknown)
            self.assertEqual(fixture.requests[-1][0], stage)
        fixture = ProtocolFixture()
        fixture.overrides["allowedGoodsNameCheck"] = {"status_code": 200, "json": {"code": "0000", "result": {"needCheck": False}}}
        self.assertEqual((await self.submit(fixture))["changeStatus"], "F")

    async def test_create_failure_vs_unknown_never_retries(self):
        for response, unknown in (
            ({"status_code": 200, "json": {"code": "ERROR", "message": "变更拒绝"}}, False),
            ({"status_code": 500, "text": "error"}, True),
            ({"status_code": 200, "text": "not json"}, True),
            ({"status_code": 200, "json": {"code": "0000", "result": {"changeStatus": "P", "changeId": "S-SYNTHETIC"}}}, True),
            (httpx.ReadTimeout("synthetic timeout"), True),
        ):
            fixture = ProtocolFixture()
            fixture.overrides["createChange"] = response
            with self.assertRaises(Error) as ctx:
                await self.submit(fixture)
            self.assertEqual(ctx.exception.outcome_unknown, unknown)
            self.assertEqual([n for n, _ in fixture.requests].count("createChange"), 1)

    def test_invalid_form_does_not_change_shared_new_order_parser(self):
        for raw in (1.5, True, "nan", 0):
            data = form()
            data["cargo_info"]["quantity"] = raw
            with self.assertRaises(Exception):
                Client.form_values(data, _business_config())
        data = form()
        Client.form_values(data, _business_config())
        self.assertEqual(data["other_info"]["contact_phone"], "")

    def test_fee_selection_normalizes_only_required_and_explicit_items(self):
        fee = {"otherChargeCode": "PU", "otherChargeName": "普货", "rateUnit": "TC", "changeType": "N", "newChecked": "N", "chargeAmount": 0.45}
        result = charge()
        result["extensionMainCharges"] = [{"serviceMainName": "出港货邮处理费", "mandatory": "Y", "subCharges": [deepcopy(fee)]}]
        result["extensionCharges"] = [{**fee, "serviceMainName": "出港货邮处理费"}]
        optional = {**fee, "otherChargeCode": "OPTIONAL", "newChecked": "Y", "newAmount": 7}
        result["extensionMainCharges"].append({"serviceMainName": "其他费用", "mandatory": "N", "subCharges": [deepcopy(optional)]})
        result["extensionCharges"].append({**optional, "serviceMainName": "其他费用"})
        self.assertTrue(Client._apply_fee_selection(result, None))
        self.assertEqual((result["extensionCharges"][0]["newChecked"], result["extensionCharges"][0]["newAmount"]), ("Y", 1))
        self.assertEqual(result["extensionCharges"][1]["newAmount"], 7)
        self.assertFalse(Client._apply_fee_selection(result, None))

    def test_deleted_fees_are_untouched_and_not_counted_as_selectable(self):
        result = fee_charge()
        deleted = {**result["extensionCharges"][0], "otherChargeCode": "OLD", "changeType": "D", "newChecked": "N"}
        result["extensionMainCharges"][0]["subCharges"].insert(0, deepcopy(deleted))
        result["extensionCharges"].insert(0, deepcopy(deleted))
        self.assertFalse(Client._apply_fee_selection(result, None))
        self.assertEqual(result["extensionCharges"][0], deleted)

    def test_selected_fee_toggle_requires_calculation_and_keeps_other_optional_amounts(self):
        result = fee_charge(checked="N", charge_amount=None)
        group = result["extensionMainCharges"][0]
        alternative = {**result["extensionCharges"][0], "otherChargeName": "加急", "otherChargeCode": "FAST", "newChecked": "Y", "chargeAmount": 2}
        group["subCharges"].append(deepcopy(alternative))
        result["extensionCharges"].append(deepcopy(alternative))
        selected = {"serviceCharges": [{"otherChargeName": "普货", "checked": "Y"}]}
        issues = []
        self.assertTrue(Client._apply_fee_selection(result, selected, issues=issues))
        self.assertEqual([row["newChecked"] for row in result["extensionCharges"]], ["Y", "N"])
        self.assertEqual([row["reason"] for row in issues], ["selection_changed", "selection_changed"])

    def test_group_without_matching_flat_fee_fails_instead_of_submitting_unpriced_choice(self):
        result = fee_charge()
        result["extensionCharges"] = []
        with self.assertRaises(Error) as ctx:
            Client._apply_fee_selection(result, None)
        self.assertEqual(ctx.exception.details["other_charge_code"], "PU")

    def test_optional_group_missing_marker_and_kg_null_amount_do_not_trigger_calculation(self):
        result = fee_charge(amount=None)
        result["extensionCharges"][0]["newAmount"] = ""
        group = result["extensionMainCharges"][0]
        group["subCharges"][0]["newAmount"] = 0
        group["mandatory"] = "N"
        self.assertFalse(Client._apply_fee_selection(result, None))
        self.assertEqual(group["subCharges"][0]["newAmount"], "")


class ChangeAPITests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (Booking, Waybill, Settlement, BusinessConfig, NanHangToken, DictType, DictOption, RPATask):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.original = {"airline": "2", "bookings": [{"consignee": "旧联系人"}]}
        self.booking = Booking(id=101, form_data=json.dumps(self.original), booking_time=get_china_now(),
                               booking_status="3", invoice_status="0", master_airwaybill_number="784-12345670",
                               has_complete_contact_info=False)
        self.db.add_all([self.booking, BusinessConfig(config_data=json.dumps(_business_config())), NanHangToken(token="synthetic-token")])
        self.db.commit()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(api.settings, "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_EXECUTION_MODE", "direct"))
        self.automation = self.stack.enter_context(patch("app.services.document_print_service.is_post_waybill_automation_enabled", return_value=True))
        self.postprocess = self.stack.enter_context(patch("app.api.waybills._post_process_china_southern_air_waybill", new=AsyncMock()))
        patch_prerequisites(self.stack)
        self.fixture = ProtocolFixture()
        self.fixture.patch(self.stack)
        app = FastAPI()
        app.include_router(api.router, prefix="/api/v1/bookings")
        register_exception_handlers(app)
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=1)
        self.client = REAL_ASYNC_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def call(self, data=None):
        return await self.client.post("/api/v1/bookings/101/invoice-with-data", json=data or form())

    async def test_success_and_duplicate_preserve_booking_snapshot_sync_waybill_settlement(self):
        response = await self.call({"form_data": form()})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()["data"]
        self.assertEqual((data["execution_mode"], data["invoice_status"], data["task_id"]), ("direct", "3", None))
        self.assertFalse(data["has_complete_contact_info"])
        self.assertEqual(data["form_data"], self.original)
        self.db.refresh(self.booking)
        self.assertEqual(json.loads(self.booking.form_data), self.original)
        waybill = self.db.query(Waybill).one()
        self.assertEqual((waybill.waybill_number, waybill.airline_record_status), ("784-12345670", "3"))
        self.assertEqual(json.loads(waybill.form_data)["contact_info"]["consignee"], "李四")
        settlement = json.loads(self.db.query(Settlement).one().form_data)
        self.assertEqual(settlement["master_total_cost"], "51.45")
        self.assertEqual(settlement["chargeable_weight"], 1)
        self.assertEqual(self.db.query(RPATask).count(), 0)
        self.postprocess.assert_awaited_once()
        duplicate = await self.call()
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual([n for n, _ in self.fixture.requests].count("createChange"), 1)

    async def test_unknown_keeps_claim_and_blocks_both_invoice_routes_and_cancel(self):
        self.fixture.overrides["createChange"] = httpx.ReadTimeout("synthetic")
        response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        self.assertTrue(response.json()["data"]["outcome_unknown"])
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "1")
        for route in ("invoice-with-data", "direct-invoice", "cancel"):
            response = await self.client.post(f"/api/v1/bookings/101/{route}", json=form())
            self.assertEqual(response.status_code, 400, response.text)
        self.assertEqual(self.db.query(Waybill).count(), 0)

    async def test_missing_live_contacts_are_saved_even_when_booking_snapshot_is_true(self):
        self.booking.has_complete_contact_info = True
        self.db.commit()
        self.fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = None
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"]["has_complete_contact_info"])
        names = [n for n, _ in self.fixture.requests]
        self.assertEqual(names[:3], ["forward", "saveContactAndLiveAnimals", "forward"])
        self.assertEqual(names.count("createChange"), 1)
        self.assertEqual(json.loads(self.booking.form_data), self.original)

    async def test_save_failure_marks_invoice_failed_and_retry_checks_live_contacts_again(self):
        self.fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = None
        self.fixture.overrides["saveContactAndLiveAnimals"] = httpx.ReadTimeout("synthetic")
        response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        data = response.json()["data"]
        self.assertEqual((data["stage"], data["invoice_status"], data["outcome_unknown"]), ("save_change_contacts", "2", False))
        self.assertIn("尚未提交开单", response.json()["msg"])
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "2")
        self.assertEqual(self.db.query(Waybill).count(), 0)
        self.assertEqual(self.db.query(Settlement).count(), 0)
        self.assertNotIn("createChange", [n for n, _ in self.fixture.requests])
        # A timed-out contact save may have succeeded upstream; retry must read first.
        self.fixture.forward["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"] = forward()["totalOrderDetail"]["orderDetailDto"]["orderShipmentContact"]
        self.fixture.requests.clear()
        self.fixture.overrides.clear()
        self.assertEqual((await self.call()).status_code, 200)
        self.assertNotIn("saveContactAndLiveAnimals", [n for n, _ in self.fixture.requests])
        self.assertFalse(self.booking.has_complete_contact_info)

    async def test_claim_is_committed_before_network_and_competing_request_is_rejected(self):
        entered, release = asyncio.Event(), asyncio.Event()
        prepare = change.china_southern_air_direct_change_service.prepare
        async def paused(**kwargs):
            entered.set()
            await release.wait()
            return await prepare(**kwargs)
        with patch.object(change.china_southern_air_direct_change_service, "prepare", new=AsyncMock(side_effect=paused)):
            running = asyncio.create_task(self.call())
            try:
                await asyncio.wait_for(entered.wait(), timeout=3)
                with sessionmaker(bind=self.engine)() as observer:
                    self.assertEqual(observer.get(Booking, 101).invoice_status, "1")
                competing = await self.call()
                self.assertEqual(competing.status_code, 400, competing.text)
            finally:
                release.set()
            response = await running
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([n for n, _ in self.fixture.requests].count("createChange"), 1)

    async def test_definite_failure_sets_failed_and_allows_retry(self):
        self.fixture.overrides["checkChange"] = {"status_code": 200, "json": {"code": "0000", "result": False}}
        response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "2")
        self.fixture.overrides.clear()
        self.assertEqual((await self.call()).status_code, 200)

    async def test_missing_group_marker_completes_instead_of_returning_400(self):
        self.fixture.charge = fee_charge()
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(sum(name == "calculateCharge" for name, _ in self.fixture.requests), 1)
        self.assertEqual(response.json()["data"]["invoice_status"], "3")

    async def test_real_fee_not_priced_returns_diagnostics_and_failed_state_without_submit(self):
        self.fixture.charge = fee_charge(charge_amount=None)
        response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        data = response.json()["data"]
        self.assertEqual(data["stage"], "calculate_change_charge")
        self.assertFalse(data["outcome_unknown"])
        self.assertEqual(data["fee_selection_issues"][0]["reason"], "required_fee_not_priced")
        self.assertEqual(data["calculation_attempts"], 3)
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "2")
        self.assertNotIn("createChange", [name for name, _ in self.fixture.requests])

    async def test_no_token_or_bad_form_does_not_claim_or_call_upstream(self):
        self.db.query(NanHangToken).delete()
        self.db.commit()
        response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "0")
        self.assertEqual(self.fixture.requests, [])

    async def test_disabled_automation_still_records_waybill_but_no_settlement_or_print(self):
        self.automation.return_value = False
        response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.db.query(Waybill).count(), 1)
        self.assertEqual(self.db.query(Settlement).count(), 0)
        self.postprocess.assert_not_awaited()

    async def test_secondary_settlement_failure_keeps_success(self):
        with patch("app.api.waybills._create_china_southern_air_settlement", side_effect=ValueError("synthetic")):
            response = await self.call()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["data"]["warnings"])
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "3")

    async def test_local_persistence_failure_does_not_release_claim(self):
        commit = self.db.commit
        count = 0
        def fail_success_commit():
            nonlocal count
            count += 1
            if count == 2:
                raise ValueError("synthetic DB failure after remote success")
            return commit()
        with patch.object(self.db, "commit", side_effect=fail_success_commit):
            response = await self.call()
        self.assertEqual(response.status_code, 500, response.text)
        self.assertTrue(response.json()["data"]["upstream_completed"])
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "1")
        self.assertEqual(self.db.query(Waybill).count(), 0)

    async def test_pending_rpa_or_cancel_blocks_direct_before_any_http(self):
        for task_type in (RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA,
                          RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE,
                          RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL):
            with patch("app.services.rpa_task_service.rpa_task_service.get_pending_task_for_target", side_effect=lambda *args, **kw:
                       SimpleNamespace(id=123) if kw["task_type"] == task_type.value else None):
                response = await self.call()
            self.assertEqual(response.status_code, 400, response.text)
            self.assertEqual(self.fixture.requests, [])

    async def test_early_service_failure_sets_failed_without_exposing_internal_exception(self):
        with patch.object(change.china_southern_air_service, "query_waybill_orders", new=AsyncMock(side_effect=ChinaSouthernAirServiceError("合成查询错误"))):
            response = await self.call()
        self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(self.booking)
        self.assertEqual(self.booking.invoice_status, "2")

    async def test_rpa_mode_preserves_old_queue_and_does_not_require_token(self):
        self.db.query(NanHangToken).delete()
        config = self.db.query(BusinessConfig).one()
        data = json.loads(config.config_data)
        data["china_southern_air"]["booking_and_create"]["china_southern_air_login"] = {
            "system_url": "https://example.invalid", "system_account": "synthetic", "login_password": "synthetic",
        }
        config.config_data = json.dumps(data)
        self.db.commit()
        with patch.object(api.settings, "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_EXECUTION_MODE", "rpa"):
            response = await self.call({"form_data": form()})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIsNotNone(response.json()["data"]["task_id"])
        task = self.db.query(RPATask).one()
        self.assertEqual(task.task_type, RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value)
        self.assertEqual(json.loads(task.params)["waybill_number_8"], "12345670")
        self.assertEqual(self.fixture.requests, [])

    async def test_cancelled_order_or_existing_waybill_blocks_before_upstream(self):
        self.booking.booking_cancel_status = "3"
        self.db.commit()
        self.assertEqual((await self.call()).status_code, 400)
        self.booking.booking_cancel_status = "0"
        self.db.add(Waybill(waybill_number="784-12345670", form_data="{}", booking_date=get_china_now().date(), airline_record_status="3"))
        self.db.commit()
        self.assertEqual((await self.call()).status_code, 400)
        self.assertEqual(self.fixture.requests, [])


@unittest.skipUnless(os.environ.get("CSA_CHANGE_SIMULATION_URL"), "Local Postman simulation required")
class ChangeHTTPSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_contacts_saved_and_refreshed_over_real_http(self):
        base = os.environ["CSA_CHANGE_SIMULATION_URL"].rstrip("/")
        async with REAL_ASYNC_CLIENT() as control:
            for scenario, failure_stage in (("contacts-missing", None), ("contacts-save-rejected", "save_change_contacts"),
                                             ("contacts-save-stale", "verify_change_contacts")):
                await control.post(base + "/__reset", json={"scenario": scenario})
                with ExitStack() as stack:
                    patch_prerequisites(stack)
                    for attr in ("FORWARD_URL", "SAVE_CONTACT_URL", "LIVING_ANIMAL_URL", "CHANGE_PRICE_URL", "CALCULATE_CHARGE_URL", "GOODS_NAME_CHECK_URL", "CHECK_CHANGE_URL", "CREATE_CHANGE_URL"):
                        stack.enter_context(patch.object(Client, attr, base + httpx.URL(getattr(Client, attr)).path))
                    stack.enter_context(patch.object(change.ChinaSouthernAirService, "CALCULATE_CWEIGHT_URL", base + "/calculateCWeight"))
                    if failure_stage:
                        with self.assertRaises(Error) as ctx:
                            await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())
                        self.assertEqual(ctx.exception.stage, failure_stage)
                        self.assertFalse(ctx.exception.outcome_unknown)
                    else:
                        payload, goods, _ = await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())
                        self.assertEqual((payload["totalOrderDetail"]["orderDetailDto"]["version"], payload["version"]), (18, 9))
                        result = await Client().validate_and_submit(token="synthetic-token", agent_code="SZXFED", goods_check_payload=goods, change_payload=payload)
                        self.assertEqual(result["changeStatus"], "F")
                trace = (await control.get(base + "/__requests")).json()
                names = [row["name"] for row in trace]
                self.assertEqual(names[:2], ["forward", "saveContactAndLiveAnimals"])
                self.assertEqual(names.count("saveContactAndLiveAnimals"), 1)
                self.assertEqual(names.count("createChange"), 0 if failure_stage else 1)
                if failure_stage:
                    self.assertNotIn("calculateCharge", names)
                else:
                    self.assertEqual(names[:3], ["forward", "saveContactAndLiveAnimals", "forward"])

    async def test_group_marker_and_amount_representation_over_real_http(self):
        base = os.environ["CSA_CHANGE_SIMULATION_URL"].rstrip("/")
        async with REAL_ASYNC_CLIENT() as control:
            for scenario in ("group-marker-omitted", "tc-string-amount", "required-fee-unpriced"):
                await control.post(base + "/__reset", json={"scenario": scenario})
                with ExitStack() as stack:
                    patch_prerequisites(stack)
                    for attr in ("FORWARD_URL", "SAVE_CONTACT_URL", "LIVING_ANIMAL_URL", "CHANGE_PRICE_URL", "CALCULATE_CHARGE_URL", "GOODS_NAME_CHECK_URL", "CHECK_CHANGE_URL", "CREATE_CHANGE_URL"):
                        stack.enter_context(patch.object(Client, attr, base + httpx.URL(getattr(Client, attr)).path))
                    stack.enter_context(patch.object(change.ChinaSouthernAirService, "CALCULATE_CWEIGHT_URL", base + "/calculateCWeight"))
                    if scenario == "required-fee-unpriced":
                        with self.assertRaises(Error) as ctx:
                            await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())
                        self.assertEqual(ctx.exception.details["fee_selection_issues"][0]["reason"], "required_fee_not_priced")
                    else:
                        payload, goods, _ = await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())
                        result = await Client().validate_and_submit(token="synthetic-token", agent_code="SZXFED", goods_check_payload=goods, change_payload=payload)
                        self.assertEqual(result["changeStatus"], "F")
                trace = (await control.get(base + "/__requests")).json()
                self.assertEqual(sum(row["name"] == "calculateCharge" for row in trace), 3 if scenario == "required-fee-unpriced" else 1)
                self.assertEqual(sum(row["name"] == "createChange" for row in trace), 0 if scenario == "required-fee-unpriced" else 1)

    async def test_real_http_sequence_success_and_failure_boundaries(self):
        base = os.environ["CSA_CHANGE_SIMULATION_URL"].rstrip("/")
        async with REAL_ASYNC_CLIENT() as control:
            for scenario, expected_unknown, final in (("success", False, "createChange"), ("goods-rejected", False, "allowedGoodsNameCheck"),
                                                       ("check-rejected", False, "checkChange"), ("create-500", True, "createChange")):
                await control.post(base + "/__reset", json={"scenario": scenario})
                with ExitStack() as stack:
                    patch_prerequisites(stack)
                    for attr in ("FORWARD_URL", "SAVE_CONTACT_URL", "LIVING_ANIMAL_URL", "CHANGE_PRICE_URL", "CALCULATE_CHARGE_URL", "GOODS_NAME_CHECK_URL", "CHECK_CHANGE_URL", "CREATE_CHANGE_URL"):
                        stack.enter_context(patch.object(Client, attr, base + httpx.URL(getattr(Client, attr)).path))
                    stack.enter_context(patch.object(change.ChinaSouthernAirService, "CALCULATE_CWEIGHT_URL", base + "/calculateCWeight"))
                    payload, goods, _ = await Client().prepare(token="synthetic-token", awb_number="784-12345670", form_data=form(), business_config=_business_config())
                    if scenario == "success":
                        result = await Client().validate_and_submit(token="synthetic-token", agent_code="SZXFED", goods_check_payload=goods, change_payload=payload)
                        self.assertEqual(result["changeStatus"], "F")
                    else:
                        with self.assertRaises(Error) as ctx:
                            await Client().validate_and_submit(token="synthetic-token", agent_code="SZXFED", goods_check_payload=goods, change_payload=payload)
                        self.assertEqual(ctx.exception.outcome_unknown, expected_unknown)
                trace = (await control.get(base + "/__requests")).json()
                self.assertEqual(trace[-1]["name"], final)
                self.assertLessEqual(sum(row["name"] == "createChange" for row in trace), 1)
