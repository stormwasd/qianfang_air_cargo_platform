"""
工具函数
"""
import json
from typing import List, Any, Union, Dict, Optional
from datetime import datetime, timezone


def parse_json_permissions(permissions_str: str) -> List[str]:
    """解析JSON格式的权限字符串"""
    try:
        return json.loads(permissions_str)
    except (json.JSONDecodeError, TypeError):
        return []


def format_permissions_to_json(permissions: List[str]) -> str:
    """将权限列表格式化为JSON字符串"""
    return json.dumps(permissions, ensure_ascii=False)


def get_utc_now() -> datetime:
    """
    获取当前UTC时间（带时区信息）
    
    Returns:
        datetime: 当前UTC时间
    """
    return datetime.now(timezone.utc)


def format_datetime_utc(dt: Optional[datetime]) -> Optional[str]:
    """
    将datetime格式化为UTC ISO格式字符串
    
    Args:
        dt: datetime对象（可以是naive或aware）
    
    Returns:
        str: ISO格式的UTC时间字符串，如果dt为None则返回None
    """
    if dt is None:
        return None
    
    # 如果datetime是naive（没有时区信息），假设它是UTC时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    # 如果datetime有时区信息，转换为UTC
    else:
        dt = dt.astimezone(timezone.utc)
    
    return dt.isoformat()

