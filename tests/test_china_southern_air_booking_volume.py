import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.china_southern_air_direct_booking import (
    ChinaSouthernAirDirectBookingService,
)
from app.services.china_southern_air_direct_order import (
    ChinaSouthernAirDirectOrderService,
)
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirService,
    ChinaSouthernAirServiceError,
)


def _business_config():
    return {
        "china_southern_air": {
            "booking_and_create": {
                "direct_order": {"agent_code": "SZXFED"},
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
        "serviceCharges": [
            {"otherChargeName": "普货", "checked": "Y"},
        ],
    }


def _direct_order_form(volume):
    return {
        "airline": "2",
        "flight_info": {
            "origin_station": "SZX",
            "destination": "TAO",
            "flight_date": "2026-08-31",
            "flight_number": "CZ8735",
        },
        "cargo_info": {
            "cargo_type": "普货",
            "cargo_type_code": "3006",
            "cargo_code": "9000",
            "cargo_name": "上衣",
            "quantity": "1",
            "weight": "200",
            "booking_volume": volume,
            "product_name": "南航标运",
            "oversized_cargo": "0",
            "special_cargo_code": "XPS,AKA",
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


def _direct_booking_form(volume):
    return {
        "airline": "2",
        "bookings": [
            {
                "origin_station": "SZX",
                "destination": "TAO",
                "flight_date": "2026-08-31",
                "flight_number": "CZ8735",
                "cargo_type": "普货",
                "cargo_type_code": "3006",
                "cargo_code": "9000",
                "cargo_name": "上衣",
                "quantity": "1",
                "weight": "200",
                "booking_volume": volume,
                "product_name": "南航标运",
                "special_cargo_code": "XPS,AKA",
            }
        ],
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

        async def post(self, url, *, headers, json):
            captured.update({"url": url, "headers": headers, "json": json})
            return httpx.Response(
                status_code,
                json=response_data,
                request=httpx.Request("POST", url),
            )

    return FakeAsyncClient


class ChinaSouthernAirBookingVolumeTests(unittest.IsolatedAsyncioTestCase):
    def test_blank_volume_is_preserved_as_missing_until_execution(self):
        order_values = ChinaSouthernAirDirectOrderService.get_form_values(
            _direct_order_form(""),
            _business_config(),
        )
        booking_values = ChinaSouthernAirDirectBookingService.get_form_values(
            _direct_booking_form(None),
            _business_config(),
        )

        self.assertIsNone(order_values["volume"])
        self.assertIsNone(booking_values["volume"])

    def test_blank_handling_fee_is_optional_and_preserves_upstream_options(self):
        order_form = _direct_order_form(None)
        order_form["outbound_cargo_and_mail_handling_fee_options"] = ""
        order_values = ChinaSouthernAirDirectOrderService.get_form_values(
            order_form,
            _business_config(),
        )
        upstream = [
            {
                "serviceMainName": "出港货邮处理费",
                "checked": "N",
                "serviceCharges": [
                    {"otherChargeName": "普货", "checked": "N"},
                    {"otherChargeName": "危险品", "checked": "Y"},
                ],
            },
            {"serviceMainName": "其他费用", "checked": "Y"},
        ]
        payload = ChinaSouthernAirDirectOrderService.build_calculate_payload(
            order_form,
            _business_config(),
            service_charges=upstream,
            form_values=order_values,
        )
        self.assertEqual(payload["extServiceCharges"], upstream)

        booking_form = _direct_booking_form(None)
        booking_form["outbound_cargo_and_mail_handling_fee_options"] = ""
        booking_values = ChinaSouthernAirDirectBookingService.get_form_values(
            booking_form,
            _business_config(),
        )
        self.assertIsNone(booking_values["selected_fee"])
        booking_upstream = [
            {
                "serviceMainName": "出港货邮处理费",
                "checked": "N",
                "serviceCharges": [
                    {"otherChargeName": "普货", "checked": "N"},
                    {"otherChargeName": "危险品", "checked": "Y"},
                ],
            },
        ]
        booking_payload = ChinaSouthernAirDirectBookingService.build_calculate_payload(
            booking_values,
            booking_upstream,
        )
        self.assertEqual(booking_payload["extServiceCharges"], booking_upstream)

    def test_user_volume_remains_preferred(self):
        order_values = ChinaSouthernAirDirectOrderService.get_form_values(
            _direct_order_form("0.01"),
            _business_config(),
        )
        booking_values = ChinaSouthernAirDirectBookingService.get_form_values(
            _direct_booking_form("0.02"),
            _business_config(),
        )

        self.assertEqual(order_values["volume"], 0.01)
        self.assertEqual(booking_values["volume"], 0.02)

    async def test_calculate_default_volume_uses_required_csa_request(self):
        captured = {}
        response_data = {
            "code": "0000",
            "message": "服务调用成功",
            "result": {"volume": 1.20, "cweight": 200},
        }
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, response_data),
        ):
            volume = await service.calculate_default_volume(
                token=" token-value ",
                origin_station="szx",
                weight=200,
                customer_no="SZXFED",
            )

        self.assertEqual(volume, 1.2)
        self.assertEqual(captured["url"], service.CALCULATE_CWEIGHT_URL)
        self.assertEqual(
            captured["json"],
            {
                "dimensions": None,
                "volume": "",
                "weight": 200,
                "channel": "B2B",
                "depCityCode": "SZX",
            },
        )
        self.assertEqual(captured["headers"]["x-customs-user"], "token-value")
        self.assertEqual(captured["headers"]["x-customs-userid"], "SZXFED")

    async def test_resolver_reuses_batch_cache_and_skips_lookup_when_filled(self):
        service = ChinaSouthernAirService()
        cache = {}
        with patch.object(
            service,
            "calculate_default_volume",
            AsyncMock(return_value=1.2),
        ) as calculate:
            first = await service.resolve_booking_volume(
                token="token",
                origin_station="SZX",
                weight=200,
                volume=None,
                cache=cache,
            )
            second = await service.resolve_booking_volume(
                token="token",
                origin_station="SZX",
                weight=200,
                volume="",
                cache=cache,
            )
            provided = await service.resolve_booking_volume(
                token="token",
                origin_station="SZX",
                weight=200,
                volume=0.03,
                cache=cache,
            )

        self.assertEqual((first, second, provided), (1.2, 1.2, 0.03))
        calculate.assert_awaited_once()

    async def test_upstream_error_contains_safe_calculate_cweight_details(self):
        captured = {}
        response_data = {
            "code": "0001",
            "message": "服务内部异常",
            "detailedMessage": {"message": "体积计算失败"},
            "result": None,
        }
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, response_data),
        ):
            with self.assertRaisesRegex(
                ChinaSouthernAirServiceError,
                "体积计算失败",
            ) as context:
                await service.calculate_default_volume(
                    token="secret-token",
                    origin_station="SZX",
                    weight=200,
                )

        details = context.exception.details
        self.assertEqual(details["stage"], "calculate_cweight")
        self.assertEqual(details["request_data"], captured["json"])
        self.assertEqual(details["upstream_response"], response_data)
        self.assertNotIn("secret-token", str(details))

    def test_resolved_volume_is_used_by_order_and_booking_payloads(self):
        config = _business_config()
        order_values = ChinaSouthernAirDirectOrderService.get_form_values(
            _direct_order_form(None),
            config,
        )
        order_values["volume"] = 1.2
        order_payload = ChinaSouthernAirDirectOrderService.build_create_payload(
            _direct_order_form(None),
            config,
            number_prefix="784-",
            number_suffix="12345678",
            calculation_result={"extServiceCharges": []},
            form_values=order_values,
        )
        order_calculate_payload = (
            ChinaSouthernAirDirectOrderService.build_calculate_payload(
                _direct_order_form(None),
                config,
                service_charges=[_selected_fee()],
                form_values=order_values,
            )
        )

        booking_values = ChinaSouthernAirDirectBookingService.get_form_values(
            _direct_booking_form(None),
            config,
        )
        booking_values["volume"] = 1.3
        booking_payload = ChinaSouthernAirDirectBookingService.build_create_payload(
            booking_values,
            config,
            flight={"bookMemo": "", "actype": "32K"},
            number_prefix="784-",
            number_suffix="87654321",
            calculation_result={"extServiceCharges": []},
        )
        booking_calculate_payload = (
            ChinaSouthernAirDirectBookingService.build_calculate_payload(
                booking_values,
                [_selected_fee()],
            )
        )

        self.assertEqual(
            order_calculate_payload["orderInfo"]["orderShipment"]["volume"],
            1.2,
        )
        self.assertEqual(
            order_payload["orderInfo"]["orderShipment"]["volume"],
            1.2,
        )
        self.assertEqual(
            booking_calculate_payload["orderInfo"]["orderShipment"]["volume"],
            1.3,
        )
        self.assertEqual(
            booking_payload["orderInfo"]["orderShipment"]["volume"],
            1.3,
        )


if __name__ == "__main__":
    unittest.main()
