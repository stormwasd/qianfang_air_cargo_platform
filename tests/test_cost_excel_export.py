import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook, load_workbook

from app.services.cost_excel_export import format_bill_of_lading_for_export


class CostExcelBillOfLadingTests(unittest.TestCase):
    def test_master_split_codes_are_converted(self):
        expected = {
            "1-0": "一主",
            "1-1": "一主（一）分",
            "1-2": "一主（二）分",
            "1-3": "一主（三）分",
            "1-4": "一主（四）分",
            "1-5": "一主（五）分",
            "1-6": "一主（六）分",
            "1-7": "一主（七）分",
            "1-8": "一主（八）分",
            "1-9": "一主（九）分",
        }
        for code, label in expected.items():
            with self.subTest(code=code):
                self.assertEqual(format_bill_of_lading_for_export(code), label)

    def test_direct_waybill_codes_are_converted(self):
        expected = {"2-0": "直单（虚拟分单）"}
        expected.update(
            {
                f"2-{index}": f"直单（虚拟分单*{index}）"
                for index in range(1, 10)
            }
        )
        for code, label in expected.items():
            with self.subTest(code=code):
                self.assertEqual(format_bill_of_lading_for_export(code), label)

    def test_current_stored_values_are_converted(self):
        expected = {
            "一主多分-0": "一主",
            "一主多分-1": "一主（一）分",
            "一主多分-6": "一主（六）分",
            "一主多分-9": "一主（九）分",
            "直单-0": "直单（虚拟分单）",
            "直单-1": "直单（虚拟分单*1）",
            "直单-3": "直单（虚拟分单*3）",
            "直单-9": "直单（虚拟分单*9）",
        }
        for stored_value, label in expected.items():
            with self.subTest(stored_value=stored_value):
                self.assertEqual(
                    format_bill_of_lading_for_export(stored_value),
                    label,
                )

    def test_empty_unknown_and_real_waybill_values_remain_compatible(self):
        self.assertEqual(format_bill_of_lading_for_export(None), "")
        self.assertEqual(format_bill_of_lading_for_export(""), "")
        self.assertEqual(format_bill_of_lading_for_export("3-1"), "3-1")
        self.assertEqual(
            format_bill_of_lading_for_export("784-98766543"),
            "784-98766543",
        )

    def test_both_export_layouts_write_converted_values_as_text(self):
        workbook = Workbook()
        worksheet = workbook.active
        worksheet.cell(row=2, column=7).value = format_bill_of_lading_for_export(
            "一主多分-6"
        )
        worksheet.cell(row=4, column=7).value = format_bill_of_lading_for_export(
            "直单-3"
        )

        self.assertEqual(worksheet.cell(row=2, column=7).value, "一主（六）分")
        self.assertEqual(worksheet.cell(row=2, column=7).data_type, "s")
        self.assertEqual(worksheet.cell(row=4, column=7).value, "直单（虚拟分单*3）")
        self.assertEqual(worksheet.cell(row=4, column=7).data_type, "s")

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cost-export.xlsx"
            workbook.save(output_path)
            workbook.close()

            exported_workbook = load_workbook(output_path, read_only=True, data_only=True)
            exported_worksheet = exported_workbook.active
            self.assertEqual(exported_worksheet.cell(row=2, column=7).value, "一主（六）分")
            self.assertEqual(exported_worksheet.cell(row=2, column=7).data_type, "s")
            self.assertEqual(
                exported_worksheet.cell(row=4, column=7).value,
                "直单（虚拟分单*3）",
            )
            self.assertEqual(exported_worksheet.cell(row=4, column=7).data_type, "s")
            exported_workbook.close()


if __name__ == "__main__":
    unittest.main()
