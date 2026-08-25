"""南航接口字段的边界格式转换工具。"""

import re
from typing import Any, List, Optional


_SPECIAL_CARGO_CODE_SEPARATOR = re.compile(r"[,，/]+")


def split_special_cargo_codes(value: Any) -> List[str]:
    """拆分平台或南航格式的特货码，并按大小写不敏感方式去重。"""
    text = "" if value is None else str(value).strip()
    if not text:
        return []

    codes: List[str] = []
    seen = set()
    for raw_code in _SPECIAL_CARGO_CODE_SEPARATOR.split(text):
        code = raw_code.strip()
        if not code:
            continue
        normalized_key = code.casefold()
        if normalized_key in seen:
            continue
        seen.add(normalized_key)
        codes.append(code)
    return codes


def merge_special_cargo_codes(
    default_code: Any,
    user_code: Any,
    *,
    separator: str = ",",
) -> Optional[str]:
    """默认码在前、用户码在后合并，重复码只保留一次。"""
    return separator.join(
        split_special_cargo_codes(
            separator.join(
                str(value)
                for value in (default_code, user_code)
                if value is not None and str(value).strip()
            )
        )
    ) or None


def normalize_special_cargo_code(value: Any) -> Optional[str]:
    """将平台逗号分隔的特货码转换为南航要求的斜杠分隔格式。"""
    return "/".join(split_special_cargo_codes(value)) or None
