"""
权限管理
"""
import json

from app.config import settings

ADMIN_PERMISSION_CODE = "admin"
ADMIN_PERMISSION_NAME = settings.PERMISSIONS.get(ADMIN_PERMISSION_CODE, "管理员")


def is_admin(permissions: list) -> bool:
    """
    判断是否为管理员
    
    Args:
        permissions: 权限列表（可能是代码或名称）
    
    Returns:
        是否为管理员
    """
    return ADMIN_PERMISSION_CODE in permissions or ADMIN_PERMISSION_NAME in permissions


def has_permission(user_permissions: list, required_permission: str) -> bool:
    """
    检查用户是否拥有指定权限
    
    Args:
        user_permissions: 用户权限列表（可能是代码或名称）
        required_permission: 需要的权限（代码或名称）
    
    Returns:
        是否拥有权限
    """
    return required_permission in user_permissions or is_admin(user_permissions)


def validate_permissions(permissions: list) -> bool:
    """
    验证权限列表是否有效（仅接受标准权限代码）
    
    Args:
        permissions: 权限列表（权限代码）
    
    Returns:
        是否所有权限都有效
    """
    valid_codes = set(settings.PERMISSION_CODES)
    return all(perm in valid_codes for perm in permissions)


def normalize_user_permissions(permissions: list[str]) -> list[str]:
    """用户管理写入边界：兼容 agency 旧值，拒绝未知值，统一为去重代码。"""
    valid_codes = set(settings.PERMISSION_CODES)
    aliases = {"agency": "agent"}
    codes = []
    invalid = []
    seen = set()
    for permission in permissions:
        value = permission.strip()
        code = aliases.get(value, value)
        if code not in valid_codes:
            invalid.append(permission)
        elif code not in seen:
            seen.add(code)
            codes.append(code)
    if invalid:
        # Do not silently discard unsupported permissions and save a partial set.
        raise ValueError("权限列表包含无效的权限：" + json.dumps(invalid, ensure_ascii=False))
    return codes

