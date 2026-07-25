"""
权限管理
"""
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

