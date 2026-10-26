"""取消业务审核后的跨费用登记台、应收及应付完整流程回归。"""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import (
    consignment_notes, financial_audit, reconciliation_agent, reconciliation_airline,
    reconciliation_delivery, reconciliation_pickup, reconciliation_receivable,
    reconciliation_road_agent,
)
from app.api.deps import get_current_active_user
from app.database import get_db
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.peer_road_manual_data import PeerRoadDepartureManualData
from app.schemas.financial_audit import AirFinancialAuditQuery
from tests import test_reconciliation_agent as air_fixture
from tests import test_reconciliation_road_agent as road_fixture


ROOT = "/api/v1"


def make_client(test):
    app = FastAPI()
    for router, prefix in (
        (financial_audit.router, "/financial-audit"),
        (consignment_notes.router, "/consignment-notes"),
        (reconciliation_airline.router, "/reconciliation/airline"),
        (reconciliation_pickup.router, "/reconciliation/pickup"),
        (reconciliation_delivery.router, "/reconciliation/delivery"),
        (reconciliation_agent.router, "/reconciliation/air-agent"),
        (reconciliation_road_agent.router, "/reconciliation/road-agent"),
        (reconciliation_receivable.router, "/reconciliation/receivable"),
    ):
        app.include_router(router, prefix=ROOT + prefix)

    def database():
        yield test.db

    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_active_user] = lambda: test.user
    return TestClient(app)


# The legacy logistics routes put actions directly under their module path.
AIR_ROUTES = [
    (f"{ROOT}/reconciliation/{name}/air",
     f"{ROOT}/reconciliation/{name}" + ("" if name in ("pickup", "delivery") else "/air"))
    for name in ("airline", "pickup", "delivery", "air-agent")
] + [
    (f"{ROOT}/reconciliation/receivable/{name}/air", f"{ROOT}/reconciliation/receivable/{name}/air")
    for name in ("airline", "pickup", "delivery", "air-agent")
]


class AirFinancialWorkflowTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        air_fixture.AgentReconciliationTests.setUp(self)
        # Source data exists but no business audit has ever been saved.
        for model in (ShenzhenAirDepartureManualData, CsaDepartureManualData, PeerAirDepartureManualData):
            self.db.query(model).delete()
        self.db.commit()
        self.client = make_client(self)

    def tearDown(self):
        self.client.close()
        air_fixture.AgentReconciliationTests.tearDown(self)

    def audit(self, kind, source_id, action):
        response = self.client.post(f"{ROOT}/financial-audit/air/audit", params={"action": action}, json={
            "source_type": kind, "source_id": str(source_id),
            "payable": {"door_pickup_company": "财务提货单位", "delivery_company": "财务派送单位",
                        "door_pickup_fee": "11", "delivery_cost": "12", "airport_pickup_fee": "13"},
        })
        self.assertEqual(response.status_code, 200, response.text)

    def assert_visibility(self, kind, source_id, visible):
        for listing, _ in AIR_ROUTES:
            with self.subTest(listing=listing, kind=kind, source_id=source_id, visible=visible):
                response = self.client.get(listing)
                self.assertEqual(response.status_code, 200, response.text)
                keys = {(row["source_type"], row["source_id"]) for row in response.json()["data"]["items"]}
                self.assertEqual((kind, str(source_id)) in keys, visible)

    async def test_fee_desk_ignores_business_filter_without_mutating_historical_statuses(self):
        self.db.add(ShenzhenAirDepartureManualData(id=111, booking_export_id=101, audit_status=1))
        self.db.add(CsaDepartureManualData(id=211, approval_data_id=201, audit_status=0))
        self.db.commit()
        for status in (0, 1, 2):
            query = AirFinancialAuditQuery(audit_status=status)
            result = await financial_audit.build_air_financial_audits(
                query, self.db, self.user, paginate=False, allow_peer_without_departure_audit=True,
            )
            rows = {(row["source_type"], row["source_id"]): row for row in result.data["items"]}
            for kind, source_id in (("shenzhen_air", "101"), ("china_southern_air", "201"), ("peer_air", "301")):
                self.assertIn((kind, source_id), rows)
            self.assertEqual(rows[("shenzhen_air", "101")]["audit_status"], 1)
            self.assertEqual(rows[("china_southern_air", "201")]["audit_status"], 0)
            self.assertEqual(query.audit_status, status)

    async def test_all_air_sources_save_submit_and_historical_cancellation_without_business_audit(self):
        for kind, source_id in (("shenzhen_air", 101), ("china_southern_air", 201), ("peer_air", 301)):
            self.assert_visibility(kind, source_id, False)
            for _, action_root in AIR_ROUTES:
                response = self.client.post(f"{action_root}/{kind}/{source_id}/settle")
                self.assertEqual(response.status_code, 400, response.text)
            self.audit(kind, source_id, "save")
            self.assert_visibility(kind, source_id, False)
            for _, action_root in AIR_ROUTES:
                response = self.client.post(action_root + "/export", json={
                    "selected_items": [{"source_type": kind, "source_id": str(source_id)}],
                })
                self.assertEqual(response.status_code, 400, response.text)
            self.audit(kind, source_id, "submit")
            self.assert_visibility(kind, source_id, True)
            for _, action_root in AIR_ROUTES:
                response = self.client.post(f"{action_root}/{kind}/{source_id}/settle")
                self.assertEqual(response.status_code, 200, response.text)
                response = self.client.post(action_root + "/export", json={
                    "selected_items": [{"source_type": kind, "source_id": str(source_id)}],
                })
                self.assertEqual(response.status_code, 200, response.text)
            # A later fee-desk save removes admission but must not trap historical settlements.
            self.audit(kind, source_id, "save")
            self.assert_visibility(kind, source_id, False)
            for _, action_root in AIR_ROUTES:
                response = self.client.post(f"{action_root}/{kind}/{source_id}/cancel-settlement")
                self.assertEqual(response.status_code, 200, response.text)
            record = self.db.query(AirFinancialAuditData).filter_by(source_type=kind, source_id=source_id).one()
            for state in ("airline", "pickup", "delivery", "agent"):
                for prefix in ("", "receivable_"):
                    self.assertEqual(getattr(record, prefix + state + "_settlement_status"), 0)
        for model in (ShenzhenAirDepartureManualData, CsaDepartureManualData, PeerAirDepartureManualData):
            self.assertEqual(self.db.query(model).count(), 0)

    async def test_all_air_batches_reject_unapproved_atomically_even_when_business_approved(self):
        self.audit("shenzhen_air", 101, "submit")
        self.db.add(ShenzhenAirDepartureManualData(id=112, booking_export_id=102, audit_status=2))
        self.db.commit()
        for _, action_root in AIR_ROUTES:
            response = self.client.post(action_root + "/batch-settle", json={"items": [
                {"source_type": "shenzhen_air", "source_id": "101"},
                {"source_type": "shenzhen_air", "source_id": "102"},
            ]})
            self.assertEqual(response.status_code, 400, response.text)
        self.db.expire_all()
        record = self.db.query(AirFinancialAuditData).filter_by(source_type="shenzhen_air", source_id=101).one()
        for state in ("airline", "pickup", "delivery", "agent"):
            for prefix in ("", "receivable_"):
                self.assertEqual(getattr(record, prefix + state + "_settlement_status"), 0)

    async def test_manual_fee_desk_records_require_financial_approval(self):
        record = self.db.get(AirFinancialAuditData, 401)  # legacy source_id=0
        record.financial_audit_status = 0
        self.db.commit()
        for name in ("airline", "air-agent"):
            for prefix in ("", "receivable/"):
                root = f"{ROOT}/reconciliation/{prefix}{name}/air"
                self.assertEqual(self.client.post(root + "/shenzhen_air/401/settle").status_code, 400)
                keys = {row["source_id"] for row in self.client.get(root).json()["data"]["items"]}
                self.assertNotIn("401", keys)
        self.audit("shenzhen_air", 401, "submit")
        self.assertEqual(self.client.post(f"{ROOT}/reconciliation/air-agent/air/shenzhen_air/401/settle").status_code, 200)
        self.db.refresh(record)
        self.assertEqual(record.source_id, 0)


class RoadFinancialWorkflowTests(unittest.IsolatedAsyncioTestCase):
    add_note = road_fixture.RoadAgentTests.add_note

    def setUp(self):
        road_fixture.RoadAgentTests.setUp(self)
        self.db.query(PeerRoadDepartureManualData).delete()
        self.db.commit()
        self.client = make_client(self)
        self.roots = [f"{ROOT}/reconciliation/{prefix}road-agent/road" for prefix in ("", "receivable/")]
        self.dates = {"date_start": "2026-10-21", "date_end": "2026-10-21"}

    def tearDown(self):
        self.client.close()
        road_fixture.RoadAgentTests.tearDown(self)

    def audit(self, action):
        response = self.client.post(f"{ROOT}/consignment-notes/financial/audit", params={"action": action},
                                    json={"consignment_note_id": "101"})
        self.assertEqual(response.status_code, 200, response.text)

    def assert_visibility(self, visible):
        for root in self.roots:
            response = self.client.get(root, params=self.dates)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["data"]["total"], int(visible))

    async def test_road_save_submit_cancel_and_batch_gate_on_both_sides(self):
        for action in (None, "save", "submit"):
            if action:
                self.audit(action)
            approved = action == "submit"
            self.assert_visibility(approved)
            for root in self.roots:
                response = self.client.post(root + "/101/settle")
                self.assertEqual(response.status_code, 200 if approved else 400, response.text)
                response = self.client.post(root + "/export", json=self.dates)
                self.assertEqual(response.status_code, 200 if approved else 400, response.text)
        record = self.db.query(PeerRoadDepartureManualData).filter_by(consignment_note_id=101).one()
        self.assertEqual(record.audit_status, 0)
        self.assertEqual(record.agent_settlement_status, 1)
        self.assertEqual(record.receivable_agent_settlement_status, 1)
        # Saving an already approved road note preserves financial approval (existing API rule).
        self.audit("save")
        self.assert_visibility(True)
        record.financial_audit_status = 1
        self.db.add(PeerRoadDepartureManualData(consignment_note_id=102, audit_status=2))
        self.db.commit()
        self.assert_visibility(False)
        for root in self.roots:
            self.assertEqual(self.client.post(root + "/101/cancel-settlement").status_code, 200)
        record.financial_audit_status = 2
        self.db.commit()
        for root in self.roots:
            response = self.client.post(root + "/batch-settle", json={"items": [{"source_id": "101"}, {"source_id": "102"}]})
            self.assertEqual(response.status_code, 400, response.text)
        self.db.refresh(record)
        self.assertEqual(record.agent_settlement_status, 0)
        self.assertEqual(record.receivable_agent_settlement_status, 0)
        self.assertEqual(record.audit_status, 0)
        self.assertEqual(self.db.query(PeerRoadDepartureManualData).count(), 2)
