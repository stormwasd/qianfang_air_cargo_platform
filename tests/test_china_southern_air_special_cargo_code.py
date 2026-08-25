import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.china_southern_air_booking_excel import (
    ChinaSouthernAirBookingExcelService,
)
from app.services.china_southern_air_direct_booking import (
    ChinaSouthernAirDirectBookingService,
)
from app.services.china_southern_air_direct_order import (
    ChinaSouthernAirDirectOrderService,
)
from app.services.china_southern_air_field_utils import (
    merge_special_cargo_codes,
    normalize_special_cargo_code,
)
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirService,
    ChinaSouthernAirServiceError,
)


def _business_config(parent_production_name="南航快运"):
    return {
        "china_southern_air": {
            "booking_and_create": {
                "direct_order": {
                    "agent_code": "SZXFED",
                    "parent_production_name": parent_production_name,
                },
                "business_default": {
                    "agent_checker_name": "检查人",
                    "agent_consignor_name": "交运人",
                    "order_contact_name": "联系人",
                    "order_contact_phone": "13800138000",
                },
            }
        }
    }


def _selected_fee():
    return {
        "serviceMainName": "出港货邮处理费",
        "checked": "Y",
        "serviceCharges": [{"otherChargeName": "普通货物", "checked": "Y"}],
    }


def _direct_order_form(special_cargo_code="GEN", product_name="南航快运"):
    return {
        "airline": "2",
        "flight_info": {
            "origin_station": "SZX",
            "destination": "TAO",
            "flight_date": "2026-08-31",
            "flight_number": "CZ8735",
        },
        "cargo_info": {
            "cargo_type": "普通货物",
            "cargo_type_code": "3006",
            "cargo_code": "9000",
            "cargo_name": "上衣",
            "quantity": "1",
            "weight": "200",
            "booking_volume": "1.2",
            "product_name": product_name,
            "special_cargo_code": special_cargo_code,
        },
        "contact_info": {
            "consignee": "李四",
            "consignee_phone": "13800138000",
            "shipper": "张三",
            "shipper_phone": "18979681111",
            "address": {
                "region": "江西省/吉安市/万安县",
                "detail": "科技园南区",
            },
        },
        "dangerous_goods_declaration": {},
        "other_info": {
            "order_contact": "陈xx",
            "contact_phone": "18979681112",
        },
        "outbound_cargo_and_mail_handling_fee_options": _selected_fee(),
    }


def _direct_booking_form(special_cargo_code="GEN", product_name="南航快运"):
    return {
        "airline": "2",
        "bookings": [{
            "origin_station": "SZX",
            "destination": "TAO",
            "flight_date": "2026-08-31",
            "flight_number": "CZ8735",
            "cargo_type": "普通货物",
            "cargo_type_code": "3006",
            "cargo_code": "9000",
            "cargo_name": "上衣",
            "quantity": "1",
            "weight": "200",
            "booking_volume": "1.2",
            "product_name": product_name,
            "special_cargo_code": special_cargo_code,
        }],
        "outbound_cargo_and_mail_handling_fee_options": "普货",
    }


def _fake_async_client(captured, response_data, status_code=200):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def post(self, url, *, params, headers, content):
            captured.update({
                "url": url,
                "params": params,
                "headers": headers,
                "content": content,
            })
            return httpx.Response(
                status_code,
                json=response_data,
                request=httpx.Request("POST", url),
            )

    return FakeAsyncClient


class ChinaSouthernAirSpecialCargoCodeTests(unittest.IsolatedAsyncioTestCase):
    def test_merge_keeps_default_first_and_deduplicates_case_insensitively(self):
        self.assertEqual(
            merge_special_cargo_codes("XPS", "xps,GEN/AKA"),
            "XPS,GEN,AKA",
        )
        self.assertEqual(
            normalize_special_cargo_code("XPS,GEN,AKA"),
            "XPS/GEN/AKA",
        )

    async def test_query_uses_required_csa_parameters_and_token(self):
        captured = {}
        response_data = {
            "code": "0000",
            "message": "服务调用成功",
            "result": {"subCode": "XPS", "subProductName": "快运"},
        }
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, response_data),
        ):
            sub_code = await service.query_default_special_cargo_code(
                token=" token-value ",
                origin_station="szx",
                destination="tao",
                shipment_type="普通货物",
                product_name="南航快运",
            )

        self.assertEqual(sub_code, "XPS")
        self.assertEqual(captured["url"], service.SHIPMENT_SUB_PRODUCT_CODE_URL)
        self.assertEqual(
            captured["params"],
            {
                "dest": "TAO",
                "origin": "SZX",
                "shipmentType": "普通货物",
                "channel": "B",
                "productName": "南航快运",
                "directTransfer": "D",
                "customerno": "SZXFED",
            },
        )
        self.assertEqual(captured["headers"]["x-customs-user"], "token-value")
        self.assertEqual(captured["headers"]["x-customs-userid"], "SZXFED")
        self.assertEqual(captured["content"], b"")

    async def test_resolver_merges_user_code_and_reuses_request_cache(self):
        service = ChinaSouthernAirService()
        cache = {}
        with patch.object(
            service,
            "query_default_special_cargo_code",
            AsyncMock(return_value="XPS"),
        ) as query:
            first = await service.resolve_special_cargo_code(
                token="token",
                origin_station="SZX",
                destination="TAO",
                shipment_type="普通货物",
                product_name="南航快运",
                user_special_cargo_code="GEN",
                cache=cache,
            )
            second = await service.resolve_special_cargo_code(
                token="token",
                origin_station="SZX",
                destination="TAO",
                shipment_type="普通货物",
                product_name="南航快运",
                user_special_cargo_code="XPS,AKA",
                cache=cache,
            )
            default_only = await service.resolve_special_cargo_code(
                token="token",
                origin_station="SZX",
                destination="TAO",
                shipment_type="普通货物",
                product_name="南航快运",
                user_special_cargo_code=None,
                cache=cache,
            )

        self.assertEqual(first["platform_code"], "XPS,GEN")
        self.assertEqual(first["csa_code"], "XPS/GEN")
        self.assertEqual(second["platform_code"], "XPS,AKA")
        self.assertEqual(default_only["platform_code"], "XPS")
        self.assertEqual(default_only["csa_code"], "XPS")
        query.assert_awaited_once()

    def test_direct_booking_allows_blank_user_special_cargo_code(self):
        values = ChinaSouthernAirDirectBookingService.get_form_values(
            _direct_booking_form(""),
            _business_config(),
        )
        self.assertIsNone(values["sp_code"])

    async def test_query_error_exposes_safe_request_context(self):
        captured = {}
        response_data = {
            "code": "0001",
            "message": "服务内部异常",
            "detailedMessage": {"message": "未查询到默认特货码"},
            "result": None,
        }
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, response_data),
        ):
            with self.assertRaisesRegex(
                ChinaSouthernAirServiceError,
                "未查询到默认特货码",
            ) as context:
                await service.query_default_special_cargo_code(
                    token="secret-token",
                    origin_station="SZX",
                    destination="TAO",
                    shipment_type="普通货物",
                    product_name="南航快运",
                )

        details = context.exception.details
        self.assertEqual(details["stage"], "query_shipment_sub_product_code")
        self.assertEqual(details["request_data"], captured["params"])
        self.assertEqual(details["upstream_response"], response_data)
        self.assertNotIn("secret-token", str(details))

    async def test_order_resolver_uses_effective_product_and_updates_csa_code(self):
        config = _business_config(parent_production_name="南航标运")
        values = ChinaSouthernAirDirectOrderService.get_form_values(
            _direct_order_form("GEN", product_name=""),
            config,
        )
        service = ChinaSouthernAirDirectOrderService()

        with patch(
            "app.services.china_southern_air_direct_order."
            "china_southern_air_service.resolve_special_cargo_code",
            AsyncMock(return_value={
                "default_code": "XPS",
                "platform_code": "XPS,GEN",
                "csa_code": "XPS/GEN",
            }),
        ) as resolve:
            result = await service.resolve_special_cargo_code(
                token="token",
                values=values,
                business_config=config,
            )

        self.assertEqual(result["platform_code"], "XPS,GEN")
        self.assertEqual(values["sp_code"], "XPS/GEN")
        self.assertEqual(resolve.await_args.kwargs["product_name"], "南航标运")

    def test_resolved_code_reaches_both_order_and_booking_create_payloads(self):
        config = _business_config()
        order_values = ChinaSouthernAirDirectOrderService.get_form_values(
            _direct_order_form("GEN"),
            config,
        )
        order_values["sp_code"] = "XPS/GEN"
        order_payload = ChinaSouthernAirDirectOrderService.build_create_payload(
            _direct_order_form("GEN"),
            config,
            number_prefix="784-",
            number_suffix="12345678",
            calculation_result={"extServiceCharges": []},
            form_values=order_values,
        )

        booking_values = ChinaSouthernAirDirectBookingService.get_form_values(
            _direct_booking_form("GEN"),
            config,
        )
        booking_values["sp_code"] = "XPS/GEN"
        booking_payload = ChinaSouthernAirDirectBookingService.build_create_payload(
            booking_values,
            config,
            flight={"bookMemo": "", "actype": "32K"},
            number_prefix="784-",
            number_suffix="87654321",
            calculation_result={"extServiceCharges": []},
        )

        for payload in (order_payload, booking_payload):
            self.assertEqual(
                payload["orderInfo"]["orderShipment"]["spCode"],
                "XPS/GEN",
            )
            self.assertEqual(payload["productionCode"], "XPS/GEN")

    def test_excel_allows_blank_user_special_cargo_code(self):
        row = {
            "origin_station": "SZX",
            "destination": "TAO",
            "flight_date": "2026-08-31",
            "shipper_unit": "客户A",
            "cargo_type": "普通货物",
            "cargo_code": "9000",
            "flight_number": "CZ8735",
            "cargo_name": "上衣",
            "quantity": "1",
            "weight": "200",
            "special_cargo_code": "",
            "outbound_cargo_and_mail_handling_fee_options": "普货",
        }

        form_data = ChinaSouthernAirBookingExcelService._build_form_data(
            row,
            row_number=4,
            cargo_type_codes={"普通货物": "3006"},
            allowed_fee_options=["普货"],
        )

        self.assertEqual(
            form_data["bookings"][0]["special_cargo_code"],
            "",
        )


if __name__ == "__main__":
    unittest.main()
