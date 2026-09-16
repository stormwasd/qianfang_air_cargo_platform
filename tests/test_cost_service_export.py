import io
import unittest
from datetime import date
from decimal import Decimal

from openpyxl import load_workbook

from app.api.cost_service import export_cost_consignments_to_excel
from app.models.cost_service import CostConsignment
from app.schemas.cost_service import CostExportExcelRequest


class ExportQuery:
    def __init__(self, records):
        self.records = records

    def filter(self, *conditions):
        return self

    def order_by(self, *columns):
        return self

    def all(self):
        return self.records


class ExportSession:
    def __init__(self, records):
        self.records = records

    def query(self, model):
        return ExportQuery(self.records)


class CostServiceExportTests(unittest.IsolatedAsyncioTestCase):
    async def test_subtotal_values_follow_their_group_headers_in_saved_export(self):
        record = CostConsignment(
            id=1,
            status=0,
            pay_intl_air_outsource_unit="international",
            pay_intl_air_flight_doc_no="731-90064074",
            pay_intl_air_flight_no="MF809",
            pay_intl_air_flight_date=date(2026, 9, 16),
            pay_intl_air_pieces=36,
            pay_intl_air_remark="international remark",
            pay_intl_air_subtotal=Decimal("101.25"),
            pay_trucking_date=date(2026, 9, 17),
            pay_trucking_remark="trucking remark",
            pay_trucking_subtotal=Decimal("202.50"),
            pay_dom_air_date=date(2026, 9, 18),
            pay_dom_air_airline="domestic airline",
            pay_dom_air_airline_unit="must not export",
            pay_dom_air_flight_doc_no="domestic document",
            pay_dom_air_remark="domestic remark",
            pay_dom_air_subtotal=Decimal("303.75"),
            pay_customs_date=date(2026, 9, 19),
            pay_customs_remark="customs remark",
            pay_customs_subtotal=Decimal("404.00"),
            pay_ground_date=date(2026, 9, 20),
            pay_ground_remark="ground remark",
            pay_ground_subtotal=Decimal("505.25"),
            pay_total=Decimal("1516.75"),
            discount_person="discount person",
        )
        zero_record = CostConsignment(
            id=2,
            status=1,
            pay_intl_air_subtotal=0,
            pay_trucking_subtotal=0,
            pay_dom_air_subtotal=0,
            pay_customs_subtotal=0,
            pay_ground_subtotal=0,
        )
        blank_record = CostConsignment(id=3)
        response = await export_cost_consignments_to_excel(
            CostExportExcelRequest(ids=["1", "2", "3"]),
            current_user=None,
            db=ExportSession([record, zero_record, blank_record]),
        )
        workbook = load_workbook(io.BytesIO(response.body), data_only=True)
        worksheet = workbook.active
        self.addCleanup(workbook.close)

        self.assertEqual(worksheet.max_column, 116)
        self.assertEqual(worksheet.max_row, 6)
        self.assertEqual(worksheet["A1"].value, "状态")
        self.assertEqual(worksheet["A4"].value, "未提交")
        self.assertEqual(worksheet["A5"].value, "已提交")
        for subtotal_cell, expected in {
            "BJ": 101.25,
            "BR": 404.00,
            "CC": 505.25,
            "CN": 202.50,
            "DE": 303.75,
        }.items():
            with self.subTest(subtotal_cell=subtotal_cell):
                self.assertEqual(worksheet[f"{subtotal_cell}3"].value, "小计")
                self.assertEqual(worksheet[f"{subtotal_cell}4"].value, expected)
                self.assertEqual(worksheet[f"{subtotal_cell}4"].data_type, "n")
                self.assertEqual(worksheet[f"{subtotal_cell}5"].value, 0)
                self.assertIsNone(worksheet[f"{subtotal_cell}6"].value)

        expected_adjacent_values = {
            "AM4": "international",
            "AP4": "731-90064074",
            "AQ4": "MF809",
            "AR4": "2026-09-16",
            "AS4": 36,
            "BI4": "international remark",
            "BK4": "2026-09-19",
            "BQ4": "customs remark",
            "BS4": "2026-09-20",
            "CB4": "ground remark",
            "CD4": "2026-09-17",
            "CM4": "trucking remark",
            "CO4": "2026-09-18",
            "CS4": "domestic airline",
            "CT4": "domestic document",
            "DD4": "domestic remark",
            "DF4": 1516.75,
            "DG4": "discount person",
        }
        for cell, expected in expected_adjacent_values.items():
            with self.subTest(cell=cell):
                self.assertEqual(worksheet[cell].value, expected)

        self.assertNotIn("航空单位", [cell.value for cell in worksheet[3]])
        self.assertNotIn("must not export", [cell.value for cell in worksheet[4]])


if __name__ == "__main__":
    unittest.main()
