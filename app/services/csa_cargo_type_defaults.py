"""南航默认货物类型的名称、代码配对及旧配置兼容。"""
from copy import deepcopy
import json

from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException
from app.models.config import BusinessConfig
from app.models.dict_option import DictOption
from app.models.dict_type import DictType


def business_defaults(config: dict) -> dict:
    node = config
    for key in ("china_southern_air", "booking_and_create", "business_default"):
        node = node.get(key) if isinstance(node, dict) else None
    return node if isinstance(node, dict) else {}


def _text(value) -> str:
    return str(value or "").strip()


def _codes_by_name(db: Session, names: set[str]) -> dict:
    if not names:
        return {}
    rows = (db.query(DictOption.label, DictOption.value)
            .join(DictType, DictOption.dict_type_id == DictType.id)
            .filter(DictType.type == "nanfang_air_cargo_type", DictType.status == 1,
                    DictOption.status == 1, DictOption.label.in_(names)).all())
    codes = {}
    duplicates = set()
    for label, code in rows:
        if label in codes:
            duplicates.add(label)
        codes[label] = _text(code)
    # Never pick an arbitrary entry from an ambiguous name.
    return {name: code for name, code in codes.items() if name not in duplicates and code}


def normalize_config_cargo_type(config: dict, db: Session, *, validate: bool = False) -> dict:
    """兼容仅有名称的配置；新提交的名称/代码必须与启用字典成对匹配。"""
    result = deepcopy(config)
    defaults = business_defaults(result)
    if not defaults:
        return result
    name = _text(defaults.get("cargo_type"))
    code = _text(defaults.get("cargo_type_code"))
    if code and not validate:
        return result
    if validate:
        for key in ("cargo_type", "cargo_type_code"):
            if defaults.get(key) is not None and not isinstance(defaults[key], str):
                raise BadRequestException(f"南航默认货物类型 {key} 必须是字符串")
        if code and not name:
            raise BadRequestException("南航默认货物类型代码必须同时提供货物类型名称")
    expected = _codes_by_name(db, {name}).get(name) if name else None
    if validate and code and expected != code:
        raise BadRequestException("南航默认货物类型名称与代码未匹配启用的数据字典，请重新选择货物类型")
    if name and expected and not code:
        defaults["cargo_type"] = name
        defaults["cargo_type_code"] = expected
    elif code and validate:
        defaults["cargo_type"] = name
        defaults["cargo_type_code"] = code
    # Unknown legacy names/codes are preserved, never reverse-map a shared code.
    return result


def apply_item_defaults(item: dict, config: dict) -> bool:
    """仅补缺失字段；代码只随相同名称使用，不能借给另一种货物。"""
    defaults = business_defaults(config)
    name, code = _text(item.get("cargo_type")), _text(item.get("cargo_type_code"))
    default_name = _text(defaults.get("cargo_type"))
    default_code = _text(defaults.get("cargo_type_code"))
    changed = False
    if not name and not code and default_name and not default_name.isdecimal():
        item["cargo_type"] = name = default_name
        changed = True
    if name and not code and name == default_name and default_code:
        item["cargo_type_code"] = default_code
        changed = True
    return changed


def fill_form_cargo_type_defaults(form: dict, db: Session, *, resolve_codes: bool = True) -> bool:
    """保存时填入默认类型，批量按名称补码；不影响其他航司或用户已填字段。"""
    if str(form.get("airline") or "").strip() not in {"2", "南方航空", "china_southern_air"}:
        return False
    items = form.get("bookings") if "bookings" in form else [form.get("cargo_info")]
    if not isinstance(items, list):
        return False
    missing = [item for item in items if isinstance(item, dict)
               and not _text(item.get("cargo_type_code"))]
    if not missing:
        return False
    record = db.query(BusinessConfig).first()
    if record:
        config = normalize_config_cargo_type(json.loads(record.config_data), db)
    else:
        config = {}
    changed = False
    for item in missing:
        changed = apply_item_defaults(item, config) or changed
    if resolve_codes:
        names = {_text(item.get("cargo_type")) for item in missing
                 if _text(item.get("cargo_type")) and not _text(item.get("cargo_type_code"))}
        codes = _codes_by_name(db, names)
        for item in missing:
            code = codes.get(_text(item.get("cargo_type")))
            if code and not _text(item.get("cargo_type_code")):
                item["cargo_type_code"] = code
                changed = True
    return changed
