"""客服财务录入快照及两台之间的字段映射。"""
from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal

from app.schemas.cost_service import (
    ReceivablesInfo, PayablesInfo, PayableIntlAir, PayableCustoms,
    PayableGround, PayableTrucking, PayableDomAir,
)


ADDITIONAL_COST_FIELDS = {
    "receivables": {
        "buy_order_fee": "receivable_buy_order_fee",
        "document_fee": "receivable_document_fee",
        "fuel_rate": "receivable_fuel_rate",
        "fuel_weight_method": "receivable_fuel_weight_method",
        "tc_rate": "receivable_tc_rate",
        "front_warehouse_rate": "receivable_front_warehouse_rate",
        "remark": "receivable_remark"
    },
    "payables.intl_air": {
        "buy_order_fee": "pay_intl_air_buy_order_fee",
        "document_fee": "pay_intl_air_document_fee",
        "fuel_rate": "pay_intl_air_fuel_rate",
        "fuel_weight_method": "pay_intl_air_fuel_weight_method",
        "tc_rate": "pay_intl_air_tc_rate",
        "front_warehouse_rate": "pay_intl_air_front_warehouse_rate"
    },
    "payables.customs": {
        "buy_order_fee": "pay_customs_buy_order_fee",
        "document_fee": "pay_customs_document_fee"
    },
    "payables.ground": {
        "tc_rate": "pay_ground_tc_rate"
    },
    "payables.trucking": {
        "flight_doc_no": "pay_trucking_flight_doc_no",
        "origin_city": "pay_trucking_origin_city",
        "destination_city": "pay_trucking_destination_city"
    },
    "payables.dom_air": {
        "volume": "pay_dom_air_volume"
    }
}


def merge_financial_payload(record, payload):
    """分组缺省或null不擦除旧值；缺省叶字段保留，显式null清空。"""
    data = deepcopy(getattr(record, "financial_data", None) or {})

    def merge(target, patch):
        for key, value in patch.items():
            if isinstance(value, dict):
                child = target.setdefault(key, {})
                merge(child, value)
            elif value is not None or key not in ("receivables", "payables", *PAYABLE_GROUPS):
                target[key] = value

    patch = payload.model_dump(mode="json", exclude_unset=True, include={"receivables", "payables"})
    merge(data, patch)
    record.financial_data = data


PAYABLE_GROUPS = ("intl_air", "customs", "ground", "trucking", "dom_air")


def format_financial_data(record):
    data = getattr(record, "financial_data", None) or {}
    return {
        "receivables": ReceivablesInfo.model_validate(data.get("receivables") or {}).model_dump(mode="json"),
        "payables": PayablesInfo.model_validate(data.get("payables") or {}).model_dump(mode="json"),
    }


def financial_snapshot(record):
    """费用保存后回写财务展示快照，不开放客服端重新编辑。"""
    result = {}
    for path, fields in FINANCIAL_FIELD_MAP.items():
        section = result
        for key in path.split("."):
            section = section.setdefault(key, {})
        for name, column in fields.items():
            value = getattr(record, column, None)
            if isinstance(value, (date, datetime)):
                value = value.strftime("%Y-%m-%d")
            elif isinstance(value, Decimal):
                value = float(value)
            section[name] = value
    return result


def sync_financial_to_cost(source, target, parse_date):
    """只覆盖客服实际填写过的字段，未填写的费用数据继续保留。"""
    data = getattr(source, "financial_data", None) or {}
    for path, fields in FINANCIAL_FIELD_MAP.items():
        section = data
        for key in path.split("."):
            section = section.get(key) or {}
        for name, column in fields.items():
            if name in section:
                value = section[name]
                if column.endswith(("_date", "_flight_date")):
                    value = parse_date(value)
                setattr(target, column, value)


# Public JSON paths to existing database columns; all three consumers use this map.
FINANCIAL_SCHEMAS = {
    "receivables": (ReceivablesInfo, "receivable_", "应收款项"),
    "payables.intl_air": (PayableIntlAir, "pay_intl_air_", "国际空运"),
    "payables.customs": (PayableCustoms, "pay_customs_", "报关"),
    "payables.ground": (PayableGround, "pay_ground_", "地面操作"),
    "payables.trucking": (PayableTrucking, "pay_trucking_", "汽运"),
    "payables.dom_air": (PayableDomAir, "pay_dom_air_", "国内空运"),
}
FINANCIAL_FIELD_MAP = {
    path: {name: prefix + name for name in schema.model_fields}
    for path, (schema, prefix, _label) in FINANCIAL_SCHEMAS.items()
}
FINANCIAL_FIELD_MAP["receivables"].update({
    "unit_price": "unit_price", "freight_method": "freight_method",
    "receivable_fuel_fee": "receivable_fuel_fee",
})
FINANCIAL_FIELD_MAP["payables.customs"]["customs_fee"] = "pay_customs_fee"
FINANCIAL_FIELD_MAP["payables"] = {"pay_total": "pay_total"}


# Keep the remaining original Excel columns and append required detail columns.
LEGACY_COST_EXPORT_COLUMNS = frozenset({
    'actual_weight',
    'agent',
    'bill_of_lading',
    'chargeable_weight',
    'commission_amount',
    'create_time',
    'customer_name',
    'customs_declaration',
    'discount_fee',
    'discount_person',
    'discount_rate',
    'first_leg_weight',
    'flight_date',
    'flight_doc_no',
    'flight_no',
    'freight_method',
    'origin_destination',
    'pay_customs_agent',
    'pay_customs_continuation_sheet_fee',
    'pay_customs_fee',
    'pay_customs_inspection_delete_fee',
    'pay_customs_other_fee',
    'pay_customs_subtotal',
    'pay_dom_air_chargeable_weight',
    'pay_dom_air_freight',
    'pay_dom_air_other_fee',
    'pay_dom_air_outsource_unit',
    'pay_dom_air_rate',
    'pay_dom_air_subtotal',
    'pay_dom_air_weight',
    'pay_ground_chargeable_weight',
    'pay_ground_freight',
    'pay_ground_lading_express_fee',
    'pay_ground_other_fee',
    'pay_ground_outsource_unit',
    'pay_ground_pallet_exit_fee',
    'pay_ground_pickup_fee',
    'pay_ground_rate',
    'pay_ground_security_customs_fee',
    'pay_ground_subtotal',
    'pay_ground_tc_fee',
    'pay_intl_air_borrow_magnetic_fuel_pickup_fee',
    'pay_intl_air_chargeable_weight',
    'pay_intl_air_consumables_fee',
    'pay_intl_air_continuation_sheet_fee',
    'pay_intl_air_customs_fee',
    'pay_intl_air_freight',
    'pay_intl_air_front_warehouse',
    'pay_intl_air_lading_fee',
    'pay_intl_air_other_fee',
    'pay_intl_air_outsource_unit',
    'pay_intl_air_rate',
    'pay_intl_air_split_fee',
    'pay_intl_air_subtotal',
    'pay_intl_air_tc_network_disposal_fee',
    'pay_intl_air_volume',
    'pay_intl_air_weight',
    'pay_total',
    'pay_trucking_doc_fee',
    'pay_trucking_freight',
    'pay_trucking_other_fee',
    'pay_trucking_outsource_unit',
    'pay_trucking_subtotal',
    'pay_trucking_unit_price',
    'pay_trucking_weight',
    'pieces',
    'profit',
    'profit_margin',
    'receivable_consumables_fee',
    'receivable_continuation_sheet_fee',
    'receivable_customs_fee',
    'receivable_customs_inspection_fee',
    'receivable_doc_make_fee',
    'receivable_doc_split_fee',
    'receivable_first_leg_fee',
    'receivable_freight',
    'receivable_fuel_fee',
    'receivable_lading_info_fee',
    'receivable_magnetic_security_fee',
    'receivable_pallet_packing_fee',
    'receivable_probe_fee',
    'receivable_skid_fee',
    'receivable_split_offset_telex_fee',
    'receivable_tc_express_fee',
    'receivable_total',
    'receivable_warehouse_ground_fee',
    'remark',
    'salesperson',
    'unit_price',
    'volume',
    'warehouse_entry_date',
})

FINANCIAL_EXPORT_FIELDS = tuple(
    (path, name, column, label, schema.model_fields[name].description.split(" (")[0].split("：")[0])
    for path, (schema, _prefix, label) in FINANCIAL_SCHEMAS.items()
    for name, column in FINANCIAL_FIELD_MAP[path].items()
)
COST_EXTRA_EXPORT_FIELDS = tuple(
    field for field in FINANCIAL_EXPORT_FIELDS
    if field[2] not in LEGACY_COST_EXPORT_COLUMNS
    and field[2] not in {"pay_dom_air_date", "pay_dom_air_airline", "pay_dom_air_airline_unit"}
)


def financial_export_values(record):
    data = format_financial_data(record)
    result = []
    from app.services.cost_excel_export import format_freight_method_for_export
    for path, name, _column, _label, _title in FINANCIAL_EXPORT_FIELDS:
        section = data
        for key in path.split("."):
            section = section.get(key) or {}
        value = section.get(name)
        if name in ("freight_method", "fuel_weight_method"):
            value = format_freight_method_for_export(value)
        result.append(value)
    result.append(data["payables"]["pay_total"])
    return result


def cost_extra_export_values(record):
    from app.services.cost_excel_export import format_freight_method_for_export
    result = []
    for _path, name, column, _label, _title in COST_EXTRA_EXPORT_FIELDS:
        value = getattr(record, column, None)
        if name in ("freight_method", "fuel_weight_method"):
            value = format_freight_method_for_export(value)
        elif isinstance(value, (date, datetime)):
            value = value.strftime("%Y-%m-%d")
        elif isinstance(value, Decimal):
            value = float(value)
        result.append(value)
    return result
