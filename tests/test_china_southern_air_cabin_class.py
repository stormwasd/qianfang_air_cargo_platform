import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.services.china_southern_air_direct_order import (
    ChinaSouthernAirDirectOrderService,
)
from app.services.china_southern_air_direct_booking import (
    ChinaSouthernAirDirectBookingService,
)
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirService,
    ChinaSouthernAirServiceError,
)


def _flight_price_response():
    return {
        "code": "0000",
        "message": "服务调用成功",
        "result": {
            "charge": [
                {
                    "parentProductionName": "南航快运",
                    "flightPriceCalculateResult": {
                        "spaceClass": "A",
                        "subSpaceClass": "A6",
                        "rateName": "南航快运",
                    },
                },
                {
                    "parentProductionName": "南航标运",
                    "flightPriceCalculateResult": {
                        "spaceClass": "B",
                        "subSpaceClass": "B6",
                        "rateName": "南航标运",
                    },
                },
            ],
        },
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
            captured.update({
                "url": url,
                "headers": headers,
                "json": json,
            })
            return httpx.Response(
                status_code,
                json=response_data,
                request=httpx.Request("POST", url),
            )

    return FakeAsyncClient


class ChinaSouthernAirCabinClassTests(unittest.IsolatedAsyncioTestCase):
    async def test_query_uses_final_volume_and_selects_matching_product(self):
        captured = {}
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, _flight_price_response()),
        ):
            cabin = await service.query_flight_price_cabin_class(
                token=" token-value ",
                origin_station="szx",
                destination="lhw",
                flight_number="cz3649",
                flight_date="2026-08-27",
                shipment_type_code="3006",
                shipment_type_name="普通货物",
                weight=300,
                volume=1.8,
                product_name="南航标运",
            )

        self.assertEqual(
            cabin,
            {
                "book_grade": "B",
                "space_class": "B",
                "sub_space_class": "B6",
                "product_name": "南航标运",
            },
        )
        self.assertEqual(captured["url"], service.FLIGHT_PRICE_URL)
        self.assertEqual(captured["headers"]["x-customs-user"], "token-value")
        self.assertEqual(captured["headers"]["x-customs-userid"], "SZXFED")
        self.assertEqual(
            captured["json"],
            {
                "spaceClassParamMultDto": {
                    "channel": "B",
                    "customerCode": "SZXFED",
                    "flights": [{
                        "flightDep": "SZX",
                        "flightDest": "LHW",
                        "flightNo": "CZ3649",
                        "flightDate": "2026-08-27",
                    }],
                    "rateCode": "3006",
                },
                "orderShipmentCreateDto": {
                    "shipmentTypeName": "普通货物",
                    "shipmentType": "3006",
                    "weight": 300,
                    "volume": 1.8,
                    "dimensions": None,
                    "rateType": "SPY",
                },
            },
        )

    async def test_query_rejects_missing_product_and_exposes_options(self):
        captured = {}
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, _flight_price_response()),
        ):
            with self.assertRaisesRegex(
                ChinaSouthernAirServiceError,
                "没有产品“南航特运”",
            ) as context:
                await service.query_flight_price_cabin_class(
                    token="secret-token",
                    origin_station="SZX",
                    destination="LHW",
                    flight_number="CZ3649",
                    flight_date="2026-08-27",
                    shipment_type_code="3006",
                    shipment_type_name="普通货物",
                    weight=300,
                    volume=1.8,
                    product_name="南航特运",
                )

        details = context.exception.details
        self.assertEqual(details["stage"], "query_b2e_flight_price")
        self.assertEqual(details["expected_product_name"], "南航特运")
        self.assertEqual(
            details["available_product_names"],
            ["南航快运", "南航标运"],
        )
        self.assertNotIn("secret-token", str(details))

    async def test_query_rejects_matching_product_with_empty_cabin(self):
        captured = {}
        response_data = _flight_price_response()
        response_data["result"]["charge"][1]["flightPriceCalculateResult"][
            "subSpaceClass"
        ] = None
        service = ChinaSouthernAirService()

        with patch(
            "app.services.china_southern_air_service_client.httpx.AsyncClient",
            _fake_async_client(captured, response_data),
        ):
            with self.assertRaisesRegex(
                ChinaSouthernAirServiceError,
                "未返回有效 spaceClass 或 subSpaceClass",
            ):
                await service.query_flight_price_cabin_class(
                    token="token",
                    origin_station="SZX",
                    destination="LHW",
                    flight_number="CZ3649",
                    flight_date="2026-08-27",
                    shipment_type_code="3006",
                    shipment_type_name="普通货物",
                    weight=300,
                    volume=1.8,
                    product_name="南航标运",
                )

    async def test_resolver_reuses_request_cache(self):
        service = ChinaSouthernAirService()
        cache = {}
        with patch.object(
            service,
            "query_flight_price_cabin_class",
            AsyncMock(return_value={
                "book_grade": "B",
                "space_class": "B",
                "sub_space_class": "B6",
                "product_name": "南航标运",
            }),
        ) as query:
            kwargs = {
                "token": "token",
                "origin_station": "SZX",
                "destination": "LHW",
                "flight_number": "CZ3649",
                "flight_date": "2026-08-27",
                "shipment_type_code": "3006",
                "shipment_type_name": "普通货物",
                "weight": 300,
                "volume": 1.8,
                "product_name": "南航标运",
                "cache": cache,
            }
            first = await service.resolve_flight_price_cabin_class(**kwargs)
            second = await service.resolve_flight_price_cabin_class(**kwargs)

        self.assertEqual(first, second)
        query.assert_awaited_once()

    async def test_direct_order_resolver_updates_all_create_order_fields(self):
        service = ChinaSouthernAirDirectOrderService()
        values = {
            "origin_station": "SZX",
            "destination": "LHW",
            "flight_number": "CZ3649",
            "flight_date": "2026-08-27",
            "rate_code": "3006",
            "shipment_type_name": "普通货物",
            "weight": 300,
            "volume": 1.8,
            "product_name": "南航标运",
        }
        business_config = {
            "china_southern_air": {
                "booking_and_create": {"direct_order": {}}
            }
        }

        with patch(
            "app.services.china_southern_air_direct_order."
            "china_southern_air_service.resolve_flight_price_cabin_class",
            AsyncMock(return_value={
                "book_grade": "B",
                "space_class": "B",
                "sub_space_class": "B6",
                "product_name": "南航标运",
            }),
        ) as query:
            await service.resolve_cabin_class(
                token="token",
                values=values,
                business_config=business_config,
            )

        self.assertEqual(values["book_grade"], "B")
        self.assertEqual(values["space_class"], "B")
        self.assertEqual(values["sub_space_class"], "B6")
        self.assertEqual(query.await_args.kwargs["volume"], 1.8)
        self.assertEqual(query.await_args.kwargs["product_name"], "南航标运")

    def test_resolved_cabin_is_used_by_both_calculate_payloads(self):
        values = {
            "origin_station": "SZX",
            "destination": "LHW",
            "flight_number": "CZ3649",
            "flight_date": "2026-08-27",
            "rate_code": "3006",
            "shipment_type_name": "普通货物",
            "piece": 30,
            "weight": 300,
            "volume": 1.8,
            "book_grade": "B",
            "space_class": "B",
            "sub_space_class": "B6",
            "commodity_code": "9000",
            "commodity_name": "服装",
        }
        charges = [{
            "serviceMainName": "出港货邮处理费",
            "checked": "Y",
            "serviceCharges": [],
        }]

        order_payload = ChinaSouthernAirDirectOrderService._build_calculate_payload(
            values,
            {},
            charges,
        )
        booking_payload = ChinaSouthernAirDirectBookingService.build_calculate_payload(
            values,
            charges,
        )

        for payload in (order_payload, booking_payload):
            shipment = payload["orderInfo"]["orderShipment"]
            self.assertEqual(shipment["bookGrade"], "B")
            self.assertEqual(shipment["spaceClass"], "B")
            self.assertEqual(shipment["subSpaceClass"], "B6")


if __name__ == "__main__":
    unittest.main()
