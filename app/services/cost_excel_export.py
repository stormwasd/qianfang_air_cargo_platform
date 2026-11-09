"""两台 Excel 导出的有序列定义及展示转换。"""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Dict

from app.services.consignment_financial import FINANCIAL_FIELD_MAP, format_financial_data


BILL_OF_LADING_EXPORT_LABELS: Dict[str, str] = {
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
    "2-0": "直单",
    "2-2": "直单（虚拟分单*2）",
    "2-3": "直单（虚拟分单*3）",
    "2-4": "直单（虚拟分单*4）",
    "2-5": "直单（虚拟分单*5）",
    "2-6": "直单（虚拟分单*6）",
    "2-7": "直单（虚拟分单*7）",
    "2-8": "直单（虚拟分单*8）",
    "2-9": "直单（虚拟分单*9）",
}

BILL_OF_LADING_STORED_PREFIXES: Dict[str, str] = {
    "一主多分": "1",
    "直单": "2",
}

FREIGHT_METHOD_EXPORT_LABELS: Dict[str, str] = {
    "1": "实际重量",
    "2": "计费重量",
}

SUBMISSION_STATUS_EXPORT_LABELS: Dict[object, str] = {
    0: "未提交",
    1: "已提交",
    2: "作废",
    "0": "未提交",
    "1": "已提交",
    "2": "作废",
}


def format_freight_method_for_export(value: object) -> str:
    """将运费计算方式编码转换为 Excel 展示名称，未知值保持原样。"""
    if value is None:
        return ""
    raw_value = str(value).strip()
    return FREIGHT_METHOD_EXPORT_LABELS.get(raw_value, str(value))


def format_submission_status_for_export(value: object) -> str:
    """显示单据自身状态，空值留空，未知值原样保留。"""
    if value is None:
        return ""
    return SUBMISSION_STATUS_EXPORT_LABELS.get(value, str(value))


def format_bill_of_lading_for_export(value: object) -> str:
    """将前端提单编码转换为页面展示名称，未知值保持原样。"""
    if value is None:
        return ""

    raw_value = str(value)
    lookup_key = raw_value.strip()
    label = BILL_OF_LADING_EXPORT_LABELS.get(lookup_key)
    if label is not None:
        return label

    # 新增、修改接口会原样保存 bill_of_lading。当前前端也可能提交
    # “一主多分-6”或“直单-0”，需与“1-6”或“2-0”采用同一展示规则。
    # 仅转换已知前缀，避免误改真实运单号或其他未知业务值。
    prefix, separator, sequence = lookup_key.rpartition("-")
    code_prefix = BILL_OF_LADING_STORED_PREFIXES.get(prefix.strip())
    sequence = sequence.strip()
    if separator and code_prefix and sequence.isdigit():
        normalized_key = f"{code_prefix}-{int(sequence)}"
        label = BILL_OF_LADING_EXPORT_LABELS.get(normalized_key)
        if label is not None:
            return label

    return raw_value


@dataclass(frozen=True)
class ExportColumn:
    title: str
    # 客服财务快照使用的路径；基础字段不带分组前缀。
    path: str
    cost_attribute: str


def _columns(group, fields):
    """显式定义产品列顺序；费用字段复用已验证的持久化映射。"""
    return tuple(
        ExportColumn(title, f"{group}.{name}" if group else name,
                     FINANCIAL_FIELD_MAP[group][name] if group else name)
        for title, name in fields
    )


_BASIC = _columns("", (
    ("序号", "sequence"), ("状态", "status"), ("客户名称", "customer_name"),
    ("进仓日期", "warehouse_entry_date"), ("航班日期", "flight_date"),
    ("主单号", "flight_doc_no"),
    ("始发站-目的站", "origin_destination"), ("件数", "pieces"),
    ("实际重量", "actual_weight"), ("计费重量", "chargeable_weight"),
    ("体积", "volume"), ("报关", "customs_declaration"),
    ("提单", "bill_of_lading"), ("备注", "remark"),
))
_RECEIVABLES = _columns("receivables", (
    ("应收提单费/信息录入费", "lading_info_fee"),
    ("应收分单费 电报费/底账费", "split_offset_telex_fee"),
    ("应收报关费", "customs_fee"), ("应收续页费", "continuation_sheet_fee"),
    ("应收海关查验费", "customs_inspection_fee"),
    ("应收磁检费/安检费", "magnetic_security_fee"),
    ("应收燃油费", "receivable_fuel_fee"), ("应收TC费", "tc_express_fee"),
    ("应收前置仓费", "warehouse_ground_fee"), ("应收制单费", "doc_make_fee"),
    ("应收制单分单费", "doc_split_fee"), ("应收垫板费", "skid_fee"),
    ("应收打板/装箱费", "pallet_packing_fee"), ("应收探板费", "probe_fee"),
    ("应收耗材费", "consumables_fee"),
))
_INTL_AIR = _columns("payables.intl_air", (
    ("国际空运代理名称", "outsource_unit"), ("始发站", "origin"),
    ("到达站", "destination"), ("主单号", "flight_doc_no"),
    ("航班号", "flight_no"), ("航班日期", "flight_date"), ("件数", "pieces"),
    ("实际重量", "weight"), ("体积", "volume"), ("计费重量", "chargeable_weight"),
    ("提单费", "lading_fee"), ("单价", "rate"), ("运费", "freight"),
    ("分单", "split_fee"), ("燃油费", "borrow_magnetic_fuel_pickup_fee"),
    ("TC费", "tc_network_disposal_fee"), ("报关费", "customs_fee"),
    ("续页费", "continuation_sheet_fee"), ("耗材费", "consumables_fee"),
    ("前置仓费", "front_warehouse"), ("其他费用", "other_fee"),
    ("备注", "remark"), ("应付小计", "subtotal"),
))
_CUSTOMS = _columns("payables.customs", (
    ("报关代理名称", "agent"), ("报关日期", "date"), ("报关费", "customs_fee"),
    ("续页费", "continuation_sheet_fee"), ("查验费/删单费", "inspection_delete_fee"),
    ("其他费用", "other_fee"), ("备注", "remark"), ("应付小计", "subtotal"),
))
_GROUND = _columns("payables.ground", (
    ("地面操作代理名称", "outsource_unit"), ("操作日期", "date"),
    ("计费重量", "chargeable_weight"), ("前置仓费", "freight"), ("TC费", "tc_fee"),
    ("提货费", "pickup_fee"), ("提单费", "lading_express_fee"),
    ("安检费/报关费", "security_customs_fee"), ("打板费/退场费", "pallet_exit_fee"),
    ("其他费用", "other_fee"), ("备注", "remark"), ("应付小计", "subtotal"),
))
_TRUCKING = _columns("payables.trucking", (
    ("汽运代理名称", "outsource_unit"), ("托运日期", "date"),
    ("主单号", "flight_doc_no"), ("始发城市", "origin_city"),
    ("目的城市", "destination_city"), ("件数", "pieces"),
    ("计费重量", "weight"), ("体积", "volume"), ("单价", "unit_price"),
    ("运费计算方式", "freight_method"), ("运费", "freight"),
    ("制单费", "doc_fee"), ("其他费用", "other_fee"),
    ("备注", "remark"), ("应付小计", "subtotal"),
))
_DOM_AIR = _columns("payables.dom_air", (
    ("国内空运代理名称", "outsource_unit"), ("始发站", "origin"),
    ("到达站", "destination"), ("主单号", "flight_doc_no"),
    ("航班号", "flight_no"), ("航班日期", "flight_date"), ("件数", "pieces"),
    ("实际重量", "weight"), ("计费重量", "chargeable_weight"), ("体积", "volume"),
    ("单价", "rate"), ("运费", "freight"), ("其他费用", "other_fee"),
    ("备注", "remark"), ("应付小计", "subtotal"),
))
_RECEIVABLE_TOTAL = _columns("receivables", (("应收合计", "total"),))
_COST_SUMMARY = (
    *_columns("", (
        ("折让人", "discount_person"), ("费率", "discount_rate"),
        ("折让费", "discount_fee"), ("业务员", "salesperson"),
        ("提成金额", "commission_amount"),
    )),
    *_RECEIVABLE_TOTAL,
    *_columns("payables", (("应付合计", "pay_total"),)),
    *_columns("", (("利润", "profit"), ("利润率%", "profit_margin"))),
)


def _customer_payables(columns):
    # 客服新表头不包含单价、运费及分组小计，其余业务列与费用台一致。
    return tuple(c for c in columns if c.title not in {"单价", "运费", "应付小计"})


CUSTOMER_EXPORT_COLUMNS = (
    *_BASIC, *_RECEIVABLES,
    *_customer_payables(_INTL_AIR), *_customer_payables(_CUSTOMS),
    *_customer_payables(_GROUND), *_customer_payables(_TRUCKING),
    *_customer_payables(_DOM_AIR),
)
COST_EXPORT_COLUMNS = (
    *_BASIC,
    *_columns("receivables", (
        ("运费费率", "unit_price"), ("运费计算方式", "freight_method"), ("运费", "freight"),
    )),
    *_RECEIVABLES, *_RECEIVABLE_TOTAL,
    *_INTL_AIR, *_CUSTOMS, *_GROUND, *_TRUCKING, *_DOM_AIR, *_COST_SUMMARY,
)
CUSTOMER_EXPORT_HEADERS = tuple(c.title for c in CUSTOMER_EXPORT_COLUMNS)
COST_EXPORT_HEADERS = tuple(c.title for c in COST_EXPORT_COLUMNS)


def _export_value(column, value):
    if column.path == "status":
        return format_submission_status_for_export(value)
    if column.path == "bill_of_lading":
        return format_bill_of_lading_for_export(value)
    if column.path == "receivables.freight_method":
        return format_freight_method_for_export(value)
    if value is None:
        return ""
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    return value


def customer_export_values(record, sequence):
    """客服财务列取该单据自己的快照，缺省分组留空。"""
    financial = format_financial_data(record)
    values = []
    for column in CUSTOMER_EXPORT_COLUMNS:
        if column.path == "sequence":
            value = sequence
        elif "." not in column.path:
            value = getattr(record, column.path, None)
        else:
            value = financial
            for key in column.path.split("."):
                value = (value or {}).get(key)
        values.append(_export_value(column, value))
    return values


def cost_export_values(record, sequence):
    """费用列直接取自身持久化字段，不重算金额或回查客服记录。"""
    return [
        _export_value(c, sequence if c.path == "sequence" else getattr(record, c.cost_attribute, None))
        for c in COST_EXPORT_COLUMNS
    ]
