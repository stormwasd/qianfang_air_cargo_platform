"""
工具函数
"""
import json
from typing import List, Any, Union, Dict, Optional
from datetime import datetime, timezone, timedelta, date
from app.config import settings


def parse_json_permissions(permissions_str: str) -> List[str]:
    """
    解析JSON格式的权限字符串，返回权限代码列表
    
    支持向后兼容：如果数据库存储的是中文名称，会自动转换为代码
    """
    try:
        permissions = json.loads(permissions_str)
        # 转换为权限代码列表（兼容旧数据中的中文名称）
        return convert_permissions_to_codes(permissions)
    except (json.JSONDecodeError, TypeError):
        return []


def format_permissions_to_json(permissions: List[str]) -> str:
    """
    将权限代码列表格式化为JSON字符串（直接存储权限代码）
    
    Args:
        permissions: 权限代码列表（如 ["admin", "waybill"]）
    
    Returns:
        JSON格式的权限代码字符串（如 '["admin", "waybill"]'）
    """
    # 确保所有权限都是代码格式
    permission_codes = convert_permissions_to_codes(permissions)
    return json.dumps(permission_codes, ensure_ascii=False)


def convert_permission_code_to_name(permission_code: str) -> Optional[str]:
    """
    将权限代码转换为权限名称
    
    Args:
        permission_code: 权限代码（如 "admin", "waybill"）
    
    Returns:
        权限名称（如 "管理员", "运单管理"），如果代码不存在则返回None
    """
    return settings.PERMISSIONS.get(permission_code)


def convert_permission_name_to_code(permission_name: str) -> Optional[str]:
    """
    将权限名称转换为权限代码
    
    Args:
        permission_name: 权限名称（如 "管理员", "运单管理"）
    
    Returns:
        权限代码（如 "admin", "waybill"），如果名称不存在则返回None
    """
    # 创建反向映射
    name_to_code = {name: code for code, name in settings.PERMISSIONS.items()}
    return name_to_code.get(permission_name)


def convert_permissions_to_codes(permissions: List[str]) -> List[str]:
    """
    将权限列表转换为权限代码列表
    
    Args:
        permissions: 权限列表（可能是代码或名称）
    
    Returns:
        权限代码列表
    """
    codes = []
    for perm in permissions:
        # 如果已经是代码，直接使用
        if perm in settings.PERMISSION_CODES:
            codes.append(perm)
        # 如果是名称，转换为代码
        elif perm in settings.PERMISSION_NAMES:
            code = convert_permission_name_to_code(perm)
            if code:
                codes.append(code)
        # 如果都不匹配，尝试作为代码处理（向后兼容）
        else:
            # 尝试查找匹配的代码
            code = convert_permission_name_to_code(perm)
            if code:
                codes.append(code)
            elif perm in settings.PERMISSION_CODES:
                codes.append(perm)
    return codes


def convert_permissions_to_names(permissions: List[str]) -> List[str]:
    """
    将权限代码列表转换为权限名称列表
    
    Args:
        permissions: 权限代码列表
    
    Returns:
        权限名称列表
    """
    names = []
    for perm in permissions:
        # 如果是代码，转换为名称
        if perm in settings.PERMISSION_CODES:
            name = convert_permission_code_to_name(perm)
            if name:
                names.append(name)
        # 如果已经是名称，直接使用（向后兼容）
        elif perm in settings.PERMISSION_NAMES:
            names.append(perm)
    return names


# 中国时区（UTC+8）
CHINA_TIMEZONE = timezone(timedelta(hours=8))


def get_china_now() -> datetime:
    """
    获取当前中国时间（UTC+8，带时区信息）
    
    Returns:
        datetime: 当前中国时间
    """
    return datetime.now(CHINA_TIMEZONE)


def format_datetime_china(dt: Optional[datetime]) -> Optional[str]:
    """
    将datetime格式化为中国时间（UTC+8）ISO格式字符串
    
    Args:
        dt: datetime对象（可以是naive或aware）
    
    Returns:
        str: ISO格式的中国时间字符串（UTC+8），如果dt为None则返回None
    """
    if dt is None:
        return None
    
    # 如果datetime是naive（没有时区信息），假设它是中国时间
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=CHINA_TIMEZONE)
    # 如果datetime有时区信息，转换为中国时间
    else:
        dt = dt.astimezone(CHINA_TIMEZONE)
    
    return dt.isoformat()


def get_china_today() -> date:
    """
    获取当前中国日期（UTC+8）
    
    Returns:
        date: 当前中国日期
    """
    return datetime.now(CHINA_TIMEZONE).date()
