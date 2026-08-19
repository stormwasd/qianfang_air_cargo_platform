"""南航接口字段的边界格式转换工具。"""

import re
from typing import Any, Optional


_SPECIAL_CARGO_CODE_SEPARATOR = re.compile(r"[,，/]+")


def normalize_special_cargo_code(value: Any) -> Optional[str]:
    """将平台逗号分隔的特货码转换为南航要求的斜杠分隔格式。"""
    text = "" if value is None else str(value).strip()
    if not text:
        return None

    codes = [
        code.strip()
        for code in _SPECIAL_CARGO_CODE_SEPARATOR.split(text)
        if code.strip()
    ]
    return "/".join(codes) or None
