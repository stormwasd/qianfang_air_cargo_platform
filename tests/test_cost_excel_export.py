import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from openpyxl import Workbook, load_workbook

from app.services.cost_excel_export import (
    COST_EXPORT_HEADERS,
    append_cost_export_headers,
    format_bill_of_lading_for_export,
    format_freight_method_for_export,
    format_submission_status_for_export,
)


class SubmissionStatusExportTests(unittest.TestCase):
    def test_status_labels_preserve_unsubmitted_zero(self):
        for value, expected in (
            (0, "未提交"), (1, "已提交"), (2, "作废"),
            ("0", "未提交"), ("1", "已提交"), ("2", "作废"),
            (None, ""), (3, "3"),
        ):
            with self.subTest(value=value):
                self.assertEqual(format_submission_status_for_export(value), expected)


class CostExcelFreightMethodTests(unittest.TestCase):
    def test_freight_method_codes_are_converted_for_export(self):
        self.assertEqual(format_freight_method_for_export("1"), "实际重量")
        self.assertEqual(format_freight_method_for_export("2"), "计费重量")
        self.assertEqual(format_freight_method_for_export(1), "实际重量")
        self.assertEqual(format_freight_method_for_export(2), "计费重量")

    def test_unknown_freight_method_values_remain_compatible(self):
        self.assertEqual(format_freight_method_for_export(None), "")
        self.assertEqual(format_freight_method_for_export(""), "")
        self.assertEqual(format_freight_method_for_export("3"), "3")


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
        self.assertEqual(format_bill_of_lading_for_export("2-0"), "直单")
        for index in range(2, 10):
            code = f"2-{index}"
            with self.subTest(code=code):
                self.assertEqual(
                    format_bill_of_lading_for_export(code),
                    f"直单（虚拟分单*{index}）",
                )

    def test_removed_direct_split_code_remains_unchanged(self):
        self.assertEqual(format_bill_of_lading_for_export("2-1"), "2-1")

    def test_current_stored_values_are_converted(self):
        expected = {
            "一主多分-0": "一主",
            "一主多分-1": "一主（一）分",
            "一主多分-6": "一主（六）分",
            "一主多分-9": "一主（九）分",
            "直单-0": "直单",
            "直单-2": "直单（虚拟分单*2）",
            "直单-9": "直单（虚拟分单*9）",
            "直单": "直单",
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
        worksheet.cell(row=2, column=8).value = format_bill_of_lading_for_export(
            "一主多分-6"
        )
        worksheet.cell(row=4, column=8).value = format_bill_of_lading_for_export(
            "直单-2"
        )

        self.assertEqual(worksheet.cell(row=2, column=8).value, "一主（六）分")
        self.assertEqual(worksheet.cell(row=2, column=8).data_type, "s")
        self.assertEqual(worksheet.cell(row=4, column=8).value, "直单（虚拟分单*2）")
        self.assertEqual(worksheet.cell(row=4, column=8).data_type, "s")

        with TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "cost-export.xlsx"
            workbook.save(output_path)
            workbook.close()

            exported_workbook = load_workbook(output_path, read_only=True, data_only=True)
            exported_worksheet = exported_workbook.active
            self.assertEqual(exported_worksheet.cell(row=2, column=8).value, "一主（六）分")
            self.assertEqual(exported_worksheet.cell(row=2, column=8).data_type, "s")
            self.assertEqual(
                exported_worksheet.cell(row=4, column=8).value,
                "直单（虚拟分单*2）",
            )
            self.assertEqual(exported_worksheet.cell(row=4, column=8).data_type, "s")
            exported_workbook.close()


class CostExcelLayoutTests(unittest.TestCase):
    def test_removed_intl_air_columns_are_not_exported(self):
        self.assertEqual(len(COST_EXPORT_HEADERS), 117)
        self.assertEqual(COST_EXPORT_HEADERS[0], "状态")
        self.assertNotIn("国空应付-航空公司", COST_EXPORT_HEADERS)
        self.assertNotIn("国空应付-托运日期", COST_EXPORT_HEADERS)
        # 国内空运属于另一业务分组，本次需求不应误删。
        self.assertIn("国空内应付-航空公司", COST_EXPORT_HEADERS)
        self.assertIn("汽运应付-托运日期", COST_EXPORT_HEADERS)
        self.assertIn("国空内应付-托运日期", COST_EXPORT_HEADERS)
        self.assertIn("地面应付-托运日期", COST_EXPORT_HEADERS)

    def test_export_titles_use_product_wording(self):
        expected_headers = {
            "应收-分单费 电报费/底账费",
            "应收-TC费",
            "应收-前置仓费",
            "国空应付-实际重量",
            "国空应付-单价",
            "国空应付-运费计算方式",
            "国空应付-燃油费",
            "国空应付-TC费",
            "国空内应付-实际重量",
            "国空内应付-运费计算方式",
        }
        for header in expected_headers:
            with self.subTest(header=header):
                self.assertIn(header, COST_EXPORT_HEADERS)

        old_headers = {
            "应收-分单费/抵账费/电报费",
            "应收-TC操作费/快件中心过站费",
            "应收-前置仓/国际货站地面费",
            "国空应付-重量",
            "国空应付-费率",
            "国空应付-借单/磁检/燃油/提货费",
            "国空应付-TC/入网/处置费",
            "国空内应付-重量",
        }
        for header in old_headers:
            with self.subTest(header=header):
                self.assertNotIn(header, COST_EXPORT_HEADERS)

    def test_grouped_headers_still_cover_all_columns(self):
        workbook = Workbook()
        worksheet = workbook.active

        headers = append_cost_export_headers(worksheet)

        merged_ranges = {str(item) for item in worksheet.merged_cells.ranges}
        self.assertEqual(len(headers), 117)
        self.assertEqual(worksheet.max_column, 117)
        self.assertEqual(worksheet["A1"].value, "状态")
        self.assertEqual(headers[0], "状态")
        self.assertEqual(merged_ranges, {
            "A1:A3", "B1:R2", "S1:AL2", "AM1:DG1",
            "AM2:BJ2", "BK2:BU2", "BV2:CM2", "CN2:CU2",
            "CV2:DF2", "DG2:DG3", "DH1:DI2", "DJ1:DK2", "DL1:DM2",
        })
        workbook.close()

    def test_every_export_section_keeps_its_expected_boundaries(self):
        expected_boundaries = {
            "应收-单价": 17,
            "应收-运费计算方式": 18,
            "应收-运费": 19,
            "应收-燃油费": 20,
            "国空应付-外发单位": 37,
            "国空应付-单价": 47,
            "国空应付-运费计算方式": 48,
            "国空应付-运费": 49,
            "国空应付-备注": 59,
            "国空应付-小计": 60,
            "汽运应付-托运日期": 61,
            "汽运应付-备注": 70,
            "汽运应付-小计": 71,
            "国空内应付-托运日期": 72,
            "国空内应付-费率": 84,
            "国空内应付-运费计算方式": 85,
            "国空内应付-运费": 86,
            "国空内应付-备注": 88,
            "国空内应付-小计": 89,
            "报关应付-报关日期": 90,
            "报关应付-备注": 96,
            "报关应付-小计": 97,
            "地面应付-托运日期": 98,
            "地面应付-备注": 107,
            "地面应付-小计": 108,
            "应付合计": 109,
            "利润率(%)": 115,
        }

        for header, expected_index in expected_boundaries.items():
            with self.subTest(header=header):
                # 状态为独立首列，其余原有字段整体右移一列。
                self.assertEqual(COST_EXPORT_HEADERS.index(header), expected_index + 1)

    def test_each_payable_subtotal_is_the_last_column_in_its_group(self):
        expected_group_ends = {
            "国空应付-小计": "汽运应付-托运日期",
            "汽运应付-小计": "国空内应付-托运日期",
            "国空内应付-小计": "报关应付-报关日期",
            "报关应付-小计": "地面应付-托运日期",
            "地面应付-小计": "应付合计",
        }

        for subtotal_header, next_header in expected_group_ends.items():
            with self.subTest(subtotal_header=subtotal_header):
                subtotal_index = COST_EXPORT_HEADERS.index(subtotal_header)
                self.assertEqual(
                    COST_EXPORT_HEADERS[subtotal_index + 1],
                    next_header,
                )


if __name__ == "__main__":
    unittest.main()
