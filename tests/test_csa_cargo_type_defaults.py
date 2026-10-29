"""配置、表单持久化与南航请求之间的货物类型配对回归。"""
import copy
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api import config as config_api
from app.api.bookings import create_booking, update_booking
from app.api.deps import get_current_active_user
from app.api.waybills import create_waybill, get_waybill, update_waybill
from app.core.exceptions import BadRequestException
from app.database import get_db
from app.models.booking import Booking
from app.models.config import BusinessConfig
from app.models.dict_option import DictOption
from app.models.dict_type import DictType
from app.models.waybill import Waybill, ShenzhenAirDirectWaybillTask
from app.schemas.booking import BookingCreate, BookingUpdate
from app.schemas.config import BusinessConfigCreate
from app.schemas.waybill import WaybillCreate, WaybillUpdate
from app.services.china_southern_air_direct_booking import ChinaSouthernAirDirectBookingService as BookingClient
from app.services.china_southern_air_direct_order import ChinaSouthernAirDirectOrderService as OrderClient
from app.services.csa_cargo_type_defaults import business_defaults
from tests.test_china_southern_air_booking_volume import (
    _business_config, _direct_booking_form, _direct_order_form,
)


class CargoTypeDefaultsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
        for model in (BusinessConfig, DictType, DictOption, Waybill, Booking, ShenzhenAirDirectWaybillTask):
            model.__table__.create(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = SimpleNamespace(id=1)
        self.db.add(DictType(id=1, name="货物类型", type="nanfang_air_cargo_type", status=1))
        self.db.add_all([
            DictOption(id=index, dict_type_id=1, label=name, value=code, status=1)
            for index, (name, code) in enumerate([
                ("普通货物", "3006"), ("锂电类货物", "3006"), ("危险品", "3002"),
            ], 1)
        ])
        self.db.commit()

    def configuration(self, name="锂电类货物", code="3006"):
        config = _business_config()
        config["shenzhen_air"] = {"booking": {"business_default": {"cargo_code": "044"}}}
        business_defaults(config).update(cargo_type=name)
        if code is not None:
            business_defaults(config)["cargo_type_code"] = code
        return config

    async def save(self, config):
        result = await config_api.save_config(BusinessConfigCreate(config_data=config), self.user, self.db)
        return result.data["config_data"]

    async def test_config_http_round_trip_keeps_distinct_names_with_shared_code(self):
        app = FastAPI()
        app.include_router(config_api.router, prefix="/api/v1/config")
        app.dependency_overrides[get_db] = lambda: self.db
        app.dependency_overrides[get_current_active_user] = lambda: self.user
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            for name in ("普通货物", "锂电类货物"):
                config = self.configuration(name)
                saved = await client.put("/api/v1/config", json={"config_data": config})
                self.assertEqual(saved.status_code, 200)
                queried = await client.get("/api/v1/config")
                self.assertEqual(queried.json()["data"]["config_data"], config)
                self.assertEqual(json.loads(self.db.query(BusinessConfig).one().config_data), config)

    async def test_bad_new_pair_does_not_overwrite_existing_config(self):
        config = self.configuration()
        await self.save(config)
        for name, code in (("普通货物", "3002"), ("", "3006"), ("不存在", "3006"),
                           ("普通货物", {"value": "3006"}), ("普通货物", 3006)):
            with self.subTest(name=name, code=code):
                with self.assertRaises(BadRequestException):
                    await self.save(self.configuration(name, code))
                self.assertEqual(json.loads(self.db.query(BusinessConfig).one().config_data), config)

    async def test_old_name_is_completed_but_unknown_or_code_only_is_not_guessed(self):
        legacy = self.configuration("危险品", None)
        record = BusinessConfig(config_data=json.dumps(legacy, ensure_ascii=False))
        self.db.add(record)
        self.db.commit()
        result = await config_api.get_current_config(self.user, self.db)
        self.assertEqual(business_defaults(result.data["config_data"])["cargo_type_code"], "3002")
        self.assertNotIn("cargo_type_code", business_defaults(json.loads(record.config_data)))
        saved = await self.save(legacy)
        self.assertEqual(business_defaults(saved)["cargo_type_code"], "3002")
        for name in ("3006", "旧名称", ""):
            config = self.configuration(name, None)
            self.assertEqual(await self.save(config), config)

    async def test_disabled_or_duplicate_name_cannot_validate_new_pair(self):
        self.db.get(DictOption, 2).status = 0
        self.db.commit()
        with self.assertRaises(BadRequestException):
            await self.save(self.configuration())
        self.db.get(DictOption, 2).status = 1
        self.db.add(DictOption(id=9, dict_type_id=1, label="锂电类货物", value="3006", status=1))
        self.db.commit()
        with self.assertRaises(BadRequestException):
            await self.save(self.configuration())

    async def test_waybill_create_update_persists_defaults_without_overwriting_selection(self):
        await self.save(self.configuration())
        form = _direct_order_form(1)
        form["cargo_info"].pop("cargo_type")
        form["cargo_info"].pop("cargo_type_code")
        original = copy.deepcopy(form)
        created = await create_waybill(WaybillCreate(form_data=form), self.user, self.db)
        self.assertEqual(form, original)
        waybill_id = created.data["id"]
        detail = await get_waybill(waybill_id, self.user, self.db)
        self.assertEqual(detail.data["form_data"]["cargo_info"]["cargo_type"], "锂电类货物")
        form["cargo_info"]["cargo_type"] = "危险品"
        updated = await update_waybill(waybill_id, WaybillUpdate(form_data=form), self.user, self.db)
        self.assertEqual(updated.data["form_data"]["cargo_info"]["cargo_type_code"], "3002")
        form["cargo_info"].update(cargo_type="普通货物", cargo_type_code="explicit-code")
        updated = await update_waybill(waybill_id, WaybillUpdate(form_data=form), self.user, self.db)
        self.assertEqual(updated.data["form_data"]["cargo_info"], form["cargo_info"])

    async def test_booking_batch_and_update_preserve_each_items_pair(self):
        await self.save(self.configuration("危险品", "3002"))
        form = {"airline": "2", "bookings": [{}, {"cargo_type": "普通货物"},
                {"cargo_type": "锂电类货物", "cargo_type_code": "3006"}]}
        response = await create_booking(BookingCreate(form_data=form), self.user, self.db)
        items = response.data["items"]
        pairs = [item["form_data"]["bookings"][0] for item in items]
        self.assertEqual(pairs, [{"cargo_type": "危险品", "cargo_type_code": "3002"},
                                {"cargo_type": "普通货物", "cargo_type_code": "3006"},
                                {"cargo_type": "锂电类货物", "cargo_type_code": "3006"}])
        updated = await update_booking(items[0]["id"], BookingUpdate(form_data={"airline": "2", "bookings": [{}]}), self.user, self.db)
        self.assertEqual(updated.data["form_data"]["bookings"][0], pairs[0])

    async def test_empty_config_and_other_airline_and_legacy_fallback_remain_compatible(self):
        config = self.configuration("", "")
        await self.save(config)
        form = {"airline": "1", "cargo_info": {"cargo_type": ""}}
        response = await create_waybill(WaybillCreate(form_data=form), self.user, self.db)
        self.assertEqual(response.data["form_data"], form)
        config["china_southern_air"]["booking_and_create"]["direct_order"]["rate_code"] = "legacy"
        form = _direct_order_form(1)
        form["cargo_info"].pop("cargo_type_code")
        self.assertEqual(OrderClient.get_form_values(form, config)["rate_code"], "legacy")

    async def test_code_only_form_is_not_assigned_an_arbitrary_default_name(self):
        await self.save(self.configuration())
        form = {"airline": "2", "cargo_info": {"cargo_type_code": "3006"}}
        created = await create_waybill(WaybillCreate(form_data=form), self.user, self.db)
        self.assertEqual(created.data["form_data"], form)
        # Old code-only configuration also cannot supply a meaningful name.
        await self.save(self.configuration("3006", None))
        created = await create_waybill(WaybillCreate(form_data={"airline": "2", "cargo_info": {}}), self.user, self.db)
        self.assertEqual(created.data["form_data"]["cargo_info"], {})

    async def test_legacy_default_is_completed_for_persistence_and_execution_reads(self):
        config = self.configuration("危险品", None)
        self.db.add(BusinessConfig(config_data=json.dumps(config, ensure_ascii=False)))
        self.db.commit()
        from app.api.bookings import _get_business_config as booking_config
        from app.api.waybills import _get_business_config as waybill_config
        for load in (booking_config, waybill_config):
            self.assertEqual(business_defaults(load(self.db))["cargo_type_code"], "3002")
        created = await create_waybill(WaybillCreate(form_data={"airline": "2", "cargo_info": {}}), self.user, self.db)
        self.assertEqual(created.data["form_data"]["cargo_info"], {"cargo_type": "危险品", "cargo_type_code": "3002"})

    async def test_request_builders_use_new_default_pair_and_keep_explicit_pair(self):
        config = await self.save(self.configuration("危险品", "3002"))
        order_form = _direct_order_form(1)
        order_form["cargo_info"].pop("cargo_type")
        order_form["cargo_info"].pop("cargo_type_code")
        order_form.pop("outbound_cargo_and_mail_handling_fee_options")
        booking_form = _direct_booking_form(1)
        booking_form["bookings"][0].pop("cargo_type")
        booking_form["bookings"][0].pop("cargo_type_code")
        original = copy.deepcopy(order_form)
        values = OrderClient.get_form_values(order_form, config)
        self.assertEqual((values["shipment_type_name"], values["rate_code"]), ("危险品", "3002"))
        self.assertEqual(order_form, original)
        booking_values = BookingClient.get_form_values(booking_form, config)
        self.assertEqual((booking_values["shipment_type_name"], booking_values["rate_code"]), ("危险品", "3002"))
        calculated = OrderClient.build_calculate_payload(order_form, config, service_charges=[])
        created = OrderClient.build_create_payload(order_form, config, number_prefix="784", number_suffix="12345678", calculation_result={"extServiceCharges": []})
        for payload in (calculated, created, BookingClient.build_calculate_payload(booking_values, [])):
            shipment = payload["orderInfo"]["orderShipment"]
            self.assertEqual((shipment["shipmentTypeName"], shipment["rateCode"]), ("危险品", "3002"))
        values = OrderClient.get_form_values(_direct_order_form(1), config)
        self.assertEqual((values["shipment_type_name"], values["rate_code"]), ("普货", "3006"))

    @unittest.skipUnless(os.environ.get("CSA_CARGO_SIM_ORIGIN"), "Local CSA simulation required")
    async def test_saved_config_reaches_real_http_client_for_order_and_booking(self):
        service = OrderClient()
        origin = os.environ["CSA_CARGO_SIM_ORIGIN"].rstrip("/")
        with patch.object(service, "CALCULATE_CHARGE_URL", origin + "/order-center/b2e-order/b2eOrder/calculateCharge"), \
             patch.object(service, "CREATE_ORDER_URL", origin + "/order-center/b2e-order/b2eOrder/createOrder"):
            for name in ("普通货物", "锂电类货物", "危险品"):
                code = "3002" if name == "危险品" else "3006"
                config = await self.save(self.configuration(name, code))
                for kind in ("order", "booking"):
                    if kind == "order":
                        form = _direct_order_form(1)
                        form["cargo_info"].pop("cargo_type")
                        form["cargo_info"].pop("cargo_type_code")
                        form.pop("outbound_cargo_and_mail_handling_fee_options")
                        payload = OrderClient.build_calculate_payload(form, config, service_charges=[])
                    else:
                        form = _direct_booking_form(1)
                        form["bookings"][0].pop("cargo_type")
                        form["bookings"][0].pop("cargo_type_code")
                        values = BookingClient.get_form_values(form, config)
                        payload = BookingClient.build_calculate_payload(values, [])
                    calculated = await service.calculate_charge(token="synthetic-token", payload=payload, business_config=config)
                    self.assertEqual(calculated["observedCargoType"], {"name": name, "code": code})
                    if kind == "order":
                        payload = OrderClient.build_create_payload(form, config, number_prefix="784", number_suffix="12345678", calculation_result=calculated)
                    else:
                        payload = BookingClient.build_create_payload(values, config, flight={"bookMemo": "", "actype": "32K"}, number_prefix="784", number_suffix="12345678", calculation_result=calculated)
                    created = await service.create_order(token="synthetic-token", payload=payload, business_config=config)
                    self.assertEqual(created["observedCargoType"], {"name": name, "code": code})


if __name__ == "__main__":
    unittest.main()
