import io
import unittest

from openpyxl import Workbook, load_workbook

from app.services.cost_excel_export import (
    COST_EXPORT_HEADERS,
    CUSTOMER_EXPORT_HEADERS,
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

        output = io.BytesIO()
        workbook.save(output)
        workbook.close()
        output.seek(0)

        exported_workbook = load_workbook(output, read_only=True, data_only=True)
        exported_worksheet = exported_workbook.active
        self.assertEqual(exported_worksheet.cell(row=2, column=8).value, "一主（六）分")
        self.assertEqual(exported_worksheet.cell(row=2, column=8).data_type, "s")
        self.assertEqual(
            exported_worksheet.cell(row=4, column=8).value,
            "直单（虚拟分单*2）",
        )
        self.assertEqual(exported_worksheet.cell(row=4, column=8).data_type, "s")
        exported_workbook.close()
        output.close()


# 独立保留客户提供的完整表头，防止实现与测试同时遗漏或错序。
EXPECTED_CUSTOMER_HEADERS = tuple("序号|状态|客户名称|进仓日期|主单号|始发站-目的站|件数|实际重量|计费重量|体积|报关|提单|备注|应收提单费/信息录入费|应收分单费 电报费/底账费|应收报关费|应收续页费|应收海关查验费|应收磁检费/安检费|应收燃油费|应收TC费|应收前置仓费|应收制单费|应收制单分单费|应收垫板费|应收打板/装箱费|应收探板费|应收耗材费|国际空运代理名称|始发站|到达站|主单号|航班号|航班日期|件数|实际重量|体积|计费重量|提单费|分单|燃油费|TC费|报关费|续页费|耗材费|前置仓费|其他费用|备注|报关代理名称|报关日期|报关费|续页费|查验费/删单费|其他费用|备注|地面操作代理名称|操作日期|计费重量|前置仓费|TC费|提货费|提单费|安检费/报关费|打板费/退场费|其他费用|备注|汽运代理名称|托运日期|主单号|始发城市|目的城市|件数|计费重量|体积|运费计算方式|制单费|其他费用|备注|国内空运代理名称|始发站|到达站|主单号|航班号|航班日期|件数|实际重量|计费重量|体积|其他费用|备注".split("|"))
EXPECTED_COST_HEADERS = tuple("序号|状态|客户名称|进仓日期|主单号|始发站-目的站|件数|实际重量|计费重量|体积|报关|提单|备注|运费费率|运费计算方式|运费|应收提单费/信息录入费|应收分单费 电报费/底账费|应收报关费|应收续页费|应收海关查验费|应收磁检费/安检费|应收燃油费|应收TC费|应收前置仓费|应收制单费|应收制单分单费|应收垫板费|应收打板/装箱费|应收探板费|应收耗材费|应收合计|国际空运代理名称|始发站|到达站|主单号|航班号|航班日期|件数|实际重量|体积|计费重量|提单费|单价|运费|分单|燃油费|TC费|报关费|续页费|耗材费|前置仓费|其他费用|备注|应付小计|报关代理名称|报关日期|报关费|续页费|查验费/删单费|其他费用|备注|应付小计|地面操作代理名称|操作日期|计费重量|前置仓费|TC费|提货费|提单费|安检费/报关费|打板费/退场费|其他费用|备注|应付小计|汽运代理名称|托运日期|主单号|始发城市|目的城市|件数|计费重量|体积|单价|运费计算方式|运费|制单费|其他费用|备注|应付小计|国内空运代理名称|始发站|到达站|主单号|航班号|航班日期|件数|实际重量|计费重量|体积|单价|运费|其他费用|备注|应付小计|折让人|费率|折让费|业务员|提成金额|应收合计|应付合计|利润|利润率%".split("|"))


class CostExcelLayoutTests(unittest.TestCase):
    def test_headers_match_customer_contract_exactly(self):
        self.assertEqual(CUSTOMER_EXPORT_HEADERS, EXPECTED_CUSTOMER_HEADERS)
        self.assertEqual(COST_EXPORT_HEADERS, EXPECTED_COST_HEADERS)
        self.assertEqual(len(CUSTOMER_EXPORT_HEADERS), 90)
        self.assertEqual(len(COST_EXPORT_HEADERS), 114)


if __name__ == "__main__":
    unittest.main()
