"""地面操作费用的接口、数据库与跨台同步回归测试。"""
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import httpx
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.api import cost_service, customer_service
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment, CostRegistration
from app.models.customer_service import ConsignmentInfo
from app.schemas.customer_service import ConsignmentInfoUpdate


class CostGroundFeeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for model in (CostRegistration, CostConsignment, ConsignmentInfo, ConsignmentOperationLog):
            model.__table__.create(self.engine)
        self.db = Session(self.engine, autoflush=False)
        self.addCleanup(self.engine.dispose)
        self.addCleanup(self.db.close)
        self.user = SimpleNamespace(id=100, name="费用人员")
        self.app = FastAPI()
        self.app.include_router(cost_service.router, prefix="/api/v1/cost-service")
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.app.dependency_overrides[get_current_active_user] = lambda: self.user

    def assert_ground(self, data, *, tc=35.5, pickup=20.75):
        ground = data["payables"]["ground"]
        self.assertEqual(ground["freight"], 120)
        self.assertEqual(ground["tc_fee"], tc)
        self.assertEqual(ground["pickup_fee"], pickup)

    async def test_template_and_all_consignment_routes_persist_and_return_ground_fees(self):
        payload = {"payables": {"ground": {
            "freight": 120, "tc_fee": 35.5, "pickup_fee": 20.75,
        }}}
        base = "/api/v1/cost-service"
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
        ) as client:
            response = await client.put(base + "/cost-registration", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            self.assert_ground(response.json()["data"])
            response = await client.get(base + "/cost-registration")
            self.assert_ground(response.json()["data"])
            self.assertEqual(self.db.query(CostRegistration).one().pay_ground_tc_fee, Decimal("35.50"))

            for suffix in ("", "/draft"):
                response = await client.post(base + "/consignments" + suffix, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                data = response.json()["data"]
                self.assert_ground(data)
                record_id = int(data["id"])
                path = base + "/consignments/" + data["id"]
                self.db.expire_all()
                record = self.db.get(CostConsignment, record_id)
                self.assertEqual(record.pay_ground_tc_fee, Decimal("35.50"))
                self.assertEqual(record.pay_ground_pickup_fee, Decimal("20.75"))
                response = await client.get(path)
                self.assert_ground(response.json()["data"])
                response = await client.get(base + "/consignments")
                self.assertEqual(response.status_code, 200, response.text)
                item = next(item for item in response.json()["data"]["items"] if int(item["id"]) == record_id)
                self.assert_ground(item)
                if not suffix:
                    await customer_service.update_consignment(
                        ConsignmentInfoUpdate(customer_name="客户保存"), str(record_id),
                        current_user=self.user, db=self.db,
                    )
                    response = await client.get(path)
                    self.assert_ground(response.json()["data"])

                response = await client.put(path + "/draft", json={"payables": {"ground": {
                    "tc_fee": 0, "pickup_fee": 0,
                }}})
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_ground(response.json()["data"], tc=0, pickup=0)
                response = await client.put(path, json={"payables": {"ground": {
                    "tc_fee": None, "pickup_fee": None,
                }}})
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_ground(response.json()["data"], tc=0, pickup=0)
                await customer_service.update_consignment(
                    ConsignmentInfoUpdate(customer_name="客户修改"), str(record_id),
                    current_user=self.user, db=self.db,
                )
                response = await client.get(path)
                self.assert_ground(response.json()["data"], tc=0, pickup=0)
                response = await client.put(path + "/void")
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_ground(response.json()["data"], tc=0, pickup=0)

    async def test_legacy_payload_creates_null_ground_fees(self):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app), base_url="http://test",
        ) as client:
            for method, path in (("PUT", "/cost-registration"), ("POST", "/consignments"),
                                 ("POST", "/consignments/draft")):
                response = await client.request(method, "/api/v1/cost-service" + path, json={
                    "payables": {"ground": {"freight": 120}},
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assert_ground(response.json()["data"], tc=None, pickup=None)

    def test_openapi_exposes_optional_nullable_ground_fees_for_all_write_routes(self):
        spec = self.app.openapi()
        ground = spec["components"]["schemas"]["PayableGround"]
        for field in ("tc_fee", "pickup_fee"):
            self.assertNotIn(field, ground.get("required", []))
            self.assertEqual(ground["properties"][field]["anyOf"], [{"type": "number"}, {"type": "null"}])
        for schema_name in ("CostRegistrationSave", "CostConsignmentCreate", "CostConsignmentUpdate"):
            schema = spec["components"]["schemas"][schema_name]
            self.assertIn({"$ref": "#/components/schemas/PayablesInfo"}, schema["properties"]["payables"]["anyOf"])

    def test_models_and_database_scripts_define_both_nullable_money_columns(self):
        root = Path(__file__).parents[1]
        scripts = [
            (root / "sql" / name).read_text(encoding="utf-8")
            for name in ("migration_create_cost_service_consignments.sql", "migration_add_cost_ground_fees.sql")
        ]
        for field, title in (("tc_fee", "TC费"), ("pickup_fee", "提货费")):
            for model in (CostRegistration, CostConsignment):
                column = model.__table__.columns["pay_ground_" + field]
                self.assertTrue(column.nullable)
                self.assertEqual((column.type.precision, column.type.scale), (10, 2))
            declaration = f"`pay_ground_{field}` decimal(10,2) DEFAULT NULL COMMENT '地面操作-{title}'"
            for script in scripts:
                self.assertEqual(script.count(declaration), 2)
        self.assertIn("ALTER TABLE `cost_registrations`", scripts[1])
        self.assertIn("ALTER TABLE `cost_consignments`", scripts[1])
        self.assertNotIn("DROP", scripts[1])
        self.assertNotIn("RENAME", scripts[1])


if __name__ == "__main__":
    unittest.main()
