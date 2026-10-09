import json
import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.financial_audit import (
    audit_air_financial,
    create_air_financial_audit,
    get_air_financial_audits,
)
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.consignment_note import ConsignmentNote
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.customer import Customer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.transit_loading import ShenzhenAirBookingExport
from app.schemas.financial_audit import (
    AirFinancialAuditCreateRequest,
    AirFinancialAuditDataUpsert,
    AirFinancialAuditQuery,
    PayableRequest,
    ReceivableRequest,
)


class FinancialAuditAgentNameTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        for table in (
            ShenzhenAirBookingExport.__table__,
            ShenzhenAirDepartureManualData.__table__,
            ShenzhenAirBillingTimeContainer.__table__,
            ChinaSouthernAirApprovalData.__table__,
            CsaDepartureManualData.__table__,
            CsaLalamoveInformation.__table__,
            ConsignmentNote.__table__,
            PeerAirDepartureManualData.__table__,
            AirFinancialAuditData.__table__,
            Customer.__table__,
        ):
            table.create(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.user = SimpleNamespace(id=7, name="测试财务")

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def test_rpa_agent_and_stale_override_are_not_business_agent_names(self):
        export = ShenzhenAirBookingExport(
            id=101,
            prefix="479",
            waybill_number="61540426",
            agent="SZXFDH",
            routing="SZX-HFE",
            flight_date="2026-09-30",
        )
        self.db.add(export)
        self.db.add(AirFinancialAuditData(
            id=201,
            source_type="shenzhen_air",
            source_id=export.id,
            payable_data={"agent_name": "SZXFDH"},
        ))
        self.db.commit()

        response = await get_air_financial_audits(
            query=AirFinancialAuditQuery(airline_type="shenzhen_air"),
            db=self.db,
            current_user=self.user,
        )

        item = response.data["items"][0]
        self.assertEqual(item["agent_name"], "")
        self.assertIsNone(item["payable"]["agent_name"])

    async def test_csa_rpa_agent_code_is_not_a_business_agent_name(self):
        approval = ChinaSouthernAirApprovalData(
            id=202,
            flight_info="CZ1234/2026-09-30/SZX-HFE",
            agent_code="SZXFDH",
        )
        self.db.add(approval)
        self.db.commit()

        response = await get_air_financial_audits(
            query=AirFinancialAuditQuery(airline_type="china_southern_air"),
            db=self.db,
            current_user=self.user,
        )

        item = response.data["items"][0]
        self.assertEqual(item["agent_name"], "")
        self.assertIsNone(item["payable"]["agent_name"])

    async def test_consignment_note_company_is_the_canonical_agent_name(self):
        note = ConsignmentNote(
            id=301,
            transport_type="0",
            company_name="新空运公司",
            customer_name="测试客户",
            form_data=json.dumps({"origin_station": "SZX"}),
        )
        self.db.add(note)
        self.db.add(PeerAirDepartureManualData(
            id=302,
            consignment_note_id=note.id,
        ))
        self.db.commit()

        response = await get_air_financial_audits(
            query=AirFinancialAuditQuery(airline_type="peer_air"),
            db=self.db,
            current_user=self.user,
        )

        item = response.data["items"][0]
        self.assertEqual(item["agent_name"], "新空运公司")
        self.assertEqual(item["payable"]["agent_name"], "新空运公司")

    async def test_audit_ignores_rpa_agent_name_from_request(self):
        export = ShenzhenAirBookingExport(id=401, waybill_number="61540427")
        self.db.add(export)
        self.db.commit()

        await audit_air_financial(
            req=AirFinancialAuditDataUpsert(
                source_type="shenzhen_air",
                source_id=str(export.id),
                payable=PayableRequest(agent_name="SZXFDH"),
            ),
            action="save",
            db=self.db,
            current_user=self.user,
        )

        saved = self.db.query(AirFinancialAuditData).filter_by(
            source_type="shenzhen_air",
            source_id=export.id,
        ).one()
        self.assertIsNone(saved.payable_data["agent_name"])

    async def test_audit_uses_consignment_note_company_instead_of_request(self):
        note = ConsignmentNote(
            id=501,
            transport_type="0",
            company_name="新空运公司",
            customer_name="测试客户",
            form_data="{}",
        )
        self.db.add(note)
        self.db.commit()

        await audit_air_financial(
            req=AirFinancialAuditDataUpsert(
                source_type="peer_air",
                source_id=str(note.id),
                payable=PayableRequest(agent_name="错误代理"),
            ),
            action="submit",
            db=self.db,
            current_user=self.user,
        )

        saved = self.db.query(AirFinancialAuditData).filter_by(
            source_type="peer_air",
            source_id=note.id,
        ).one()
        self.assertEqual(saved.payable_data["agent_name"], "新空运公司")

    async def test_manual_financial_record_cannot_create_an_agent_name(self):
        await create_air_financial_audit(
            req=AirFinancialAuditCreateRequest(
                payable=PayableRequest(agent_name="错误代理"),
                receivable=ReceivableRequest(
                    waybill_number="999-12345678",
                    airline="其他航司",
                ),
            ),
            db=self.db,
            current_user=self.user,
        )

        saved = self.db.query(AirFinancialAuditData).one()
        self.assertIsNone(saved.payable_data["agent_name"])


if __name__ == "__main__":
    unittest.main()
