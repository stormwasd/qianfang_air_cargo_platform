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
            pay_intl_air_origin="removed intl origin",
            pay_intl_air_destination="removed intl destination",
            pay_intl_air_flight_doc_no="removed intl document",
            pay_intl_air_flight_no="removed intl flight",
            pay_intl_air_flight_date=date(2026, 9, 16),
            pay_intl_air_pieces=901,
            pay_intl_air_freight_method="removed intl freight method",
            pay_intl_air_remark="removed international remark",
            pay_intl_air_subtotal=Decimal("101.25"),
            pay_trucking_outsource_unit="trucking unit",
            pay_trucking_date=date(2026, 9, 17),
            pay_trucking_pieces=902,
            pay_trucking_volume=Decimal("902.25"),
            pay_trucking_freight_method="体积重",
            pay_trucking_remark="removed trucking remark",
            pay_trucking_subtotal=Decimal("202.50"),
            pay_dom_air_outsource_unit="domestic unit",
            pay_dom_air_date=date(2026, 9, 18),
            pay_dom_air_origin="removed domestic origin",
            pay_dom_air_destination="removed domestic destination",
            pay_dom_air_airline="removed domestic airline",
            pay_dom_air_airline_unit="must not export",
            pay_dom_air_flight_doc_no="removed domestic document",
            pay_dom_air_flight_no="removed domestic flight",
            pay_dom_air_flight_date=date(2026, 9, 21),
            pay_dom_air_pieces=903,
            pay_dom_air_freight_method="removed domestic freight method",
            pay_dom_air_remark="removed domestic remark",
            pay_dom_air_subtotal=Decimal("303.75"),
            pay_customs_date=date(2026, 9, 19),
            pay_customs_agent="customs agent",
            pay_customs_other_fee=Decimal("904.25"),
            pay_customs_remark="customs remark",
            pay_customs_subtotal=Decimal("404.00"),
            pay_ground_date=date(2026, 9, 20),
            pay_ground_outsource_unit="ground unit",
            pay_ground_freight=Decimal("120.00"),
            pay_ground_tc_fee=Decimal("35.50"),
            pay_ground_pickup_fee=Decimal("20.75"),
            pay_ground_other_fee=Decimal("905.25"),
            pay_ground_remark="ground remark",
            pay_ground_subtotal=Decimal("505.25"),
            pay_total=Decimal("1516.75"),
            discount_person="discount person",
            discount_rate=Decimal("7.25"),
            discount_fee=Decimal("88.50"),
            salesperson="salesperson",
            commission_percentage=Decimal("12.50"),
            commission_amount=Decimal("171.39"),
            profit=Decimal("1428.25"),
        )
        zero_record = CostConsignment(
            id=2,
            status=1,
            pay_intl_air_subtotal=0,
            pay_trucking_subtotal=0,
            pay_dom_air_subtotal=0,
            pay_customs_subtotal=0,
            pay_ground_subtotal=0,
            pay_ground_tc_fee=0,
            pay_ground_pickup_fee=0,
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

        self.assertEqual(worksheet.max_column, 114)
        self.assertEqual(worksheet.max_row, 4)
        self.assertEqual([worksheet.cell(row, 1).value for row in range(2, 5)], [1, 2, 3])
        self.assertEqual(worksheet["B2"].value, "未提交")
        self.assertEqual(worksheet["B3"].value, "已提交")
        # 独立坐标校验每个分组末尾，避免同名“应付小计”串列。
        for column, expected in ((55, 101.25), (63, 404), (75, 505.25), (90, 202.5), (105, 303.75)):
            with self.subTest(column=column):
                self.assertEqual(worksheet.cell(1, column).value, "应付小计")
                self.assertEqual(worksheet.cell(2, column).value, expected)
                self.assertEqual(worksheet.cell(2, column).data_type, "n")
                self.assertEqual(worksheet.cell(3, column).value, 0)
                self.assertIsNone(worksheet.cell(4, column).value)
        expected_values = {
            33: "international", 34: "removed intl origin", 35: "removed intl destination",
            36: "removed intl document", 37: "removed intl flight", 38: "2026-09-16", 39: 901,
            54: "removed international remark", 56: "customs agent", 57: "2026-09-19",
            61: 904.25, 62: "customs remark", 64: "ground unit", 65: "2026-09-20",
            67: 120, 68: 35.5, 69: 20.75, 73: 905.25, 74: "ground remark",
            76: "trucking unit", 77: "2026-09-17", 81: 902, 83: 902.25,
            89: "removed trucking remark", 91: "domestic unit", 92: "removed domestic origin",
            93: "removed domestic destination", 94: "removed domestic document",
            95: "removed domestic flight", 96: "2026-09-21", 97: 903,
            104: "removed domestic remark", 106: "discount person", 107: 7.25,
            108: 88.5, 109: "salesperson", 110: 171.39, 112: 1516.75, 113: 1428.25,
        }
        for column, expected in expected_values.items():
            with self.subTest(column=column):
                self.assertEqual(worksheet.cell(2, column).value, expected)
        self.assertEqual(worksheet.cell(1, 85).value, "运费计算方式")
        self.assertEqual(worksheet.cell(2, 85).value, "体积重")
        exported_values = {cell.value for cell in worksheet[2]}
        for excluded in ("2026-09-18", "removed domestic airline", "must not export",
                         "removed intl freight method", "removed domestic freight method", 12.5):
            self.assertNotIn(excluded, exported_values)


if __name__ == "__main__":
    unittest.main()
