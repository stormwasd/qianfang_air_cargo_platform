"""南航订舱收发货人的启用规则、配置映射及页面/Excel 一致性。"""
import copy
import json
import os
import unittest
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from openpyxl import load_workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import bookings as booking_api
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.booking import Booking
from app.models.config import BusinessConfig
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.services.china_southern_air_booking_excel import (
    ChinaSouthernAirBookingExcelError,
    ChinaSouthernAirBookingExcelService as Excel,
)
from app.services.china_southern_air_direct_booking import (
    ChinaSouthernAirDirectBookingError,
    ChinaSouthernAirDirectBookingService as Direct,
)
from app.services.china_southern_air_direct_order import ChinaSouthernAirDirectOrderService
from tests.test_china_southern_air_booking_volume import _business_config, _direct_booking_form


TEMPLATE = Path(__file__).resolve().parents[1] / "documents/china_southern_air/南航订舱模板.xlsx"


def configuration():
    config = _business_config()
    config["china_southern_air"]["booking_and_create"]["business_default"].update({
        "shipper": " 配置托运公司 ",
        "phone": " 075512345678 ",
        "address": {"region": " 广东省 / 深圳市 / 宝安区 ", "detail": " 机场货站2号港 "},
        # 不能用配置中的默认收货人补齐未填信息。
        "consignee": "默认收货人",
        "consignee_phone": "13900000000",
    })
    return config


def form(consignee=" 收货人甲 ", phone=" 013800138000 "):
    result = _direct_booking_form("1.2")
    result["bookings"][0].update(consignee=consignee, consignee_phone=phone)
    return result


def payload(data, config):
    values = Direct.get_form_values(data, config)
    return Direct.build_create_payload(
        values, config, flight={"bookMemo": "", "actype": "320"},
        calculation_result={"extServiceCharges": []}, number_prefix="784", number_suffix="12345670",
    )


def excel_content(rows, missing_headers=()):
    workbook = load_workbook(TEMPLATE)
    try:
        sheet = workbook.worksheets[0]
        headers = {Excel._normalized_header(c.value): c.column for c in sheet[2] if c.value}
        for row_number, values in enumerate(rows, 4):
            for header, value in values.items():
                sheet.cell(row_number, headers[header], value)
        for header in missing_headers:
            sheet.cell(2, headers[header]).value = None
        stream = BytesIO()
        workbook.save(stream)
        return stream.getvalue()
    finally:
        workbook.close()


def excel_row(consignee="收货人甲", phone="013800138000"):
    return {
        "始发站": "SZX", "到达站": "TAO", "航班日期": "2026-11-06",
        "客户名称": "客户公司", "货物类型": "普货", "货物代码": "9000",
        "航班号": "CZ8735", "货物名称": "上衣", "件数": "2", "重量(kg)": "100",
        "收货人": consignee, "收货人手机号": phone,
    }


def parse(content):
    return Excel.parse(content, cargo_type_codes={"普货": "3006"}, allowed_fee_options=Direct.ALLOWED_HANDLING_FEE_OPTIONS)


class BookingContactTests(unittest.TestCase):
    def test_complete_recipient_maps_configured_shipper_and_airport_pickup(self):
        data, config = form(), configuration()
        # 表单中的客户名、托运人字段不能覆盖指定的系统配置来源。
        data["bookings"][0].update(shipper_unit="客户公司", shipper="表单托运人", shipper_phone="其他手机")
        originals = copy.deepcopy((data, config))
        request = payload(data, config)
        self.assertEqual(request["orderInfo"]["orderShipmentContact"], {
            "shipperName": "配置托运公司", "shipperMobile": "075512345678",
            "shipperState": "广东省", "shipperCity": "深圳市", "shipperDistrict": "宝安区",
            "shipperAddress": "机场货站2号港", "shipperCountryCode": "CN",
            "consigneeName": "收货人甲", "consigneeMobile": "013800138000",
            "consigneeCountryCode": "CN", "consigneeAddress": "机场自提", "selfPickUp": "Y",
        })
        self.assertEqual(request["orderInfo"]["order"]["contactName"], "联系人")
        self.assertEqual(request["orderInfo"]["order"]["contactPhone"], "13800138000")
        self.assertEqual((data, config), originals)

    def test_either_blank_recipient_disables_contacts_without_validating_shipper(self):
        for name, phone in ((None, None), ("甲", None), (None, "123"), (" ", "123"), ("甲", "\t")):
            with self.subTest(name=name, phone=phone):
                config = _business_config()  # 无托运人配置仍可正常执行。
                config["china_southern_air"]["booking_and_create"]["business_default"].update(
                    consignee="配置收货人", consignee_phone="123", address="无效地址",
                )
                self.assertIsNone(payload(form(name, phone), config)["orderInfo"]["orderShipmentContact"])
        self.assertIsNone(payload(_direct_booking_form("1.2"), _business_config())["orderInfo"]["orderShipmentContact"])

    def test_list_region_and_direct_order_overrides_are_respected(self):
        config = configuration()
        node = config["china_southern_air"]["booking_and_create"]
        node["business_default"]["address"]["region"] = [" 广东省 ", " 深圳市 ", " 宝安区 "]
        node["direct_order"].update(shipper_country_code=" cn ", consignee_country_code=" hk ",
                                    consignee_address="指定自提地址", self_pick_up=" y ")
        contact = payload(form(), config)["orderInfo"]["orderShipmentContact"]
        self.assertEqual((contact["shipperState"], contact["shipperCity"], contact["shipperDistrict"]),
                         ("广东省", "深圳市", "宝安区"))
        self.assertEqual(contact["shipperCountryCode"], "CN")
        self.assertEqual(contact["consigneeCountryCode"], "HK")
        self.assertEqual(contact["consigneeAddress"], "指定自提地址")
        self.assertEqual(contact["selfPickUp"], "Y")

    def test_incomplete_shipper_configuration_disables_whole_contact_group(self):
        for key in ("shipper", "phone", "address"):
            with self.subTest(key=key):
                config = configuration()
                config["china_southern_air"]["booking_and_create"]["business_default"].pop(key)
                self.assertIsNone(payload(form(), config)["orderInfo"]["orderShipmentContact"])
        for region in (None, "广东省/深圳市", ["广东省", "", "宝安区"], "广东省/深圳市/ "):
            with self.subTest(region=region):
                config = configuration()
                config["china_southern_air"]["booking_and_create"]["business_default"]["address"]["region"] = region
                self.assertIsNone(payload(form(), config)["orderInfo"]["orderShipmentContact"])
        config = configuration()
        config["china_southern_air"]["booking_and_create"]["business_default"]["address"]["detail"] = " "
        self.assertIsNone(payload(form(), config)["orderInfo"]["orderShipmentContact"])

    def test_contacts_only_change_the_shipment_contact_object(self):
        enabled = payload(form(), configuration())
        disabled = payload(form("甲", ""), configuration())
        enabled["orderInfo"]["orderShipmentContact"] = None
        self.assertEqual(enabled, disabled)

    def test_excel_rows_apply_contact_rule_independently_and_keep_phone_as_text(self):
        rows = parse(excel_content([
            excel_row(" 甲 ", " 013800138000 "), excel_row("乙", None),
            excel_row(None, "123"), excel_row(None, None), excel_row("丙", 13800138000),
        ]))
        self.assertEqual(len(rows), 5)
        for index, row in enumerate(rows):
            request = payload(row["form_data"], configuration())
            self.assertEqual(request["orderInfo"]["orderShipmentContact"] is not None, index in (0, 4))
        self.assertEqual(rows[0]["form_data"]["bookings"][0]["consignee_phone"], "013800138000")
        self.assertEqual(rows[4]["form_data"]["bookings"][0]["consignee_phone"], "13800138000")

    def test_old_templates_missing_either_or_both_columns_remain_compatible(self):
        for missing in (("收货人",), ("收货人手机号",), ("收货人", "收货人手机号")):
            with self.subTest(missing=missing):
                row = parse(excel_content([excel_row()], missing))[0]
                self.assertIsNone(payload(row["form_data"], _business_config())["orderInfo"]["orderShipmentContact"])

    def test_recipient_only_row_is_not_silently_ignored(self):
        with self.assertRaises(ChinaSouthernAirBookingExcelError) as error:
            parse(excel_content([{"收货人": "甲"}]))
        self.assertIn("缺少必填数据", error.exception.errors[0]["message"])


class BookingContactApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (Booking, BusinessConfig, DictType, DictOption):
            model.__table__.create(engine)
        self.db = sessionmaker(bind=engine)()
        self.addCleanup(engine.dispose)
        self.addCleanup(self.db.close)
        self.db.add(DictType(id=1, name="货物类型", type="nanfang_air_cargo_type", status=1))
        self.db.add(DictOption(id=1, dict_type_id=1, label="普货", value="3006", status=1))
        self.db.commit()
        app = FastAPI()
        app.include_router(booking_api.router, prefix="/api/v1/bookings")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: SimpleNamespace(id=1)
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        self.addAsyncCleanup(self.client.aclose)

    async def test_page_batch_create_update_and_detail_preserve_per_row_recipients(self):
        data = form("甲", "013800138000")
        data["bookings"].append(form("乙", "")['bookings'][0])
        response = await self.client.post("/api/v1/bookings", json={"form_data": data})
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 2)
        for index, item in enumerate(items):
            self.assertEqual(item["form_data"]["bookings"], [data["bookings"][index]])
        booking_id = items[0]["id"]
        updated = form("新收货人", "01000123456")
        response = await self.client.put(f"/api/v1/bookings/{booking_id}", json={"form_data": updated})
        self.assertEqual(response.status_code, 200, response.text)
        response = await self.client.get(f"/api/v1/bookings/{booking_id}")
        saved = response.json()["data"]["form_data"]
        self.assertEqual(saved["bookings"][0]["consignee_phone"], "01000123456")
        self.assertEqual(json.loads(self.db.get(Booking, int(booking_id)).form_data), saved)
        self.assertEqual(payload(saved, configuration())["orderInfo"]["orderShipmentContact"]["consigneeName"], "新收货人")

    async def test_download_and_import_keep_new_columns_and_partial_recipient(self):
        response = await self.client.get("/api/v1/bookings/china-southern-air/template")
        self.assertEqual(response.status_code, 200, response.text if response.status_code != 200 else "")
        workbook = load_workbook(BytesIO(response.content))
        try:
            self.assertEqual((workbook.active["U2"].value, workbook.active["V2"].value), ("收货人", "收货人手机号"))
        finally:
            workbook.close()
        content = excel_content([excel_row(), excel_row("仅姓名", None)])
        response = await self.client.post("/api/v1/bookings/china-southern-air/import-excel",
                                          files={"file": ("bookings.xlsx", content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
        self.assertEqual(response.status_code, 200, response.text)
        items = response.json()["data"]["items"]
        self.assertEqual(len(items), 2)
        for index, item in enumerate(items):
            saved = json.loads(self.db.get(Booking, int(item["id"])).form_data)
            self.assertEqual(saved, item["form_data"])
            self.assertEqual(payload(saved, configuration())["orderInfo"]["orderShipmentContact"] is not None, index == 0)


@unittest.skipUnless(os.environ.get("CSA_CONTACT_SIMULATION_URL"), "Run with the local Postman simulation URL")
class BookingContactSimulationTests(unittest.IsolatedAsyncioTestCase):
    async def test_excel_and_page_contacts_reach_create_order_over_http(self):
        target = os.environ["CSA_CONTACT_SIMULATION_URL"].rstrip('/')
        forms = [form(), form("甲", ""), form(None, "123"), _direct_booking_form("1.2")]
        forms.extend(row["form_data"] for row in parse(excel_content([excel_row(), excel_row("甲", None)])))
        for data in forms:
            data["bookings"][0]["cargo_type"] = "普通货物"
            request = payload(data, configuration())
            with patch.object(ChinaSouthernAirDirectOrderService, "CREATE_ORDER_URL",
                              target + "/order-center/b2e-order/b2eOrder/createOrder"):
                result = await Direct().create_order(token="synthetic-test-token", payload=request, business_config=configuration())
            self.assertEqual(result["observedShipmentContact"], request["orderInfo"]["orderShipmentContact"])
