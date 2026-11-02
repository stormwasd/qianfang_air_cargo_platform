import io
import unittest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

from openpyxl import load_workbook

from app.api.cost_service import export_cost_consignments_to_excel
from app.api.customer_service import export_consignments_to_excel
from app.models.cost_service import CostConsignment
from app.models.customer_service import ConsignmentInfo
from app.schemas.cost_service import CostExportExcelRequest
from app.schemas.customer_service import ExportExcelRequest
from app.services.cost_excel_export import format_submission_status_for_export
from tests.test_cost_excel_export import EXPECTED_CUSTOMER_HEADERS, EXPECTED_COST_HEADERS


class ConsignmentExportStatusTests(unittest.IsolatedAsyncioTestCase):
    async def export(self, endpoint, request_type, records):
        db = MagicMock()
        db.query.return_value.filter.return_value.order_by.return_value.all.return_value = records
        response = await endpoint(
            request_type(ids=["1", "2"]), current_user=None, db=db,
        )
        workbook = load_workbook(io.BytesIO(response.body), data_only=True)
        self.addCleanup(workbook.close)
        return workbook.active

    async def test_both_exports_use_their_own_status_and_preserve_consignment_columns(self):
        fields = {
            "id": 1,
            "create_time": datetime(2026, 9, 14, 10, 20, 30),
            "internal_doc_id": "DOC-1",
            "warehouse_entry_date": date(2026, 9, 13),
            "customer_name": "customer",
            "origin_destination": "SZX-NRT",
            "customs_declaration": "customs",
            "bill_of_lading": "2-0",
            "flight_date": date(2026, 9, 16),
            "flight_no": "MF809",
            "flight_doc_no": "731-90064074",
            "pieces": 36,
            "actual_weight": Decimal("123.25"),
            "chargeable_weight": Decimal("125.00"),
            "volume": Decimal("1.25"),
            "first_leg_weight": Decimal("120.50"),
            "agent": "agent",
            "remark": "remark",
        }
        expected_values = [
            "customer", "2026-09-13", "731-90064074", "SZX-NRT", 36,
            123.25, 125, 1.25, "customs", "直单", "remark",
        ]
        for endpoint, request_type, model, expected_headers, status in (
            (export_consignments_to_excel, ExportExcelRequest, ConsignmentInfo, EXPECTED_CUSTOMER_HEADERS, 1),
            (export_cost_consignments_to_excel, CostExportExcelRequest, CostConsignment, EXPECTED_COST_HEADERS, 0),
        ):
            with self.subTest(endpoint=endpoint.__name__):
                record = model(**fields, status=status)
                second = model(id=2, status=1 - status)
                sheet = await self.export(endpoint, request_type, [record, second])
                self.assertEqual(tuple(c.value for c in sheet[1]), expected_headers)
                self.assertEqual(sheet.max_row, 3)
                self.assertEqual(sheet.max_column, len(expected_headers))
                self.assertEqual(list(sheet.merged_cells.ranges), [])
                self.assertEqual(sheet.cell(2, 1).value, 1)
                self.assertEqual(sheet.cell(3, 1).value, 2)
                self.assertEqual(sheet.cell(2, 2).value, "已提交" if status == 1 else "未提交")
                self.assertEqual(sheet.cell(3, 2).value, "未提交" if status == 1 else "已提交")
                self.assertEqual([sheet.cell(2, c).value for c in range(3, 14)], expected_values)
                self.assertEqual(sheet.cell(2, 1).alignment.horizontal, "center")
                self.assertEqual(record.status, status)

    async def test_empty_result_still_exports_status_headers(self):
        for endpoint, request_type, column_count, header_rows in (
            (export_consignments_to_excel, ExportExcelRequest, 90, 1),
            (export_cost_consignments_to_excel, CostExportExcelRequest, 114, 1),
        ):
            with self.subTest(endpoint=endpoint.__name__):
                sheet = await self.export(endpoint, request_type, [])
                self.assertEqual(sheet["A1"].value, "序号")
                self.assertEqual(sheet.max_column, column_count)
                self.assertEqual(sheet.max_row, header_rows)

    async def test_both_exports_display_voided_status(self):
        for endpoint, request_type, model, data_row, status_column in (
            (export_consignments_to_excel, ExportExcelRequest, ConsignmentInfo, 2, 2),
            (export_cost_consignments_to_excel, CostExportExcelRequest, CostConsignment, 2, 2),
        ):
            with self.subTest(endpoint=endpoint.__name__):
                sheet = await self.export(endpoint, request_type, [model(id=1, status=2)])
                self.assertEqual(sheet.cell(data_row, status_column).value, "作废")
        self.assertEqual(format_submission_status_for_export("2"), "作废")


if __name__ == "__main__":
    unittest.main()
