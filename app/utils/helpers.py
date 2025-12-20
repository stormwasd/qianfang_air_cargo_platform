"""
工具函数
"""
import json
from typing import List, Any, Union, Dict


def parse_json_permissions(permissions_str: str) -> List[str]:
    """解析JSON格式的权限字符串"""
    try:
        return json.loads(permissions_str)
    except (json.JSONDecodeError, TypeError):
        return []


def format_permissions_to_json(permissions: List[str]) -> str:
    """将权限列表格式化为JSON字符串"""
    return json.dumps(permissions, ensure_ascii=False)

