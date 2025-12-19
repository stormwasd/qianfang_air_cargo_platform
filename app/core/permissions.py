"""
权限管理
"""
from app.config import settings

ADMIN_PERMISSION = "管理员"


def is_admin(permissions: list) -> bool:
    """判断是否为管理员"""
    return ADMIN_PERMISSION in permissions


def has_permission(user_permissions: list, required_permission: str) -> bool:
    """检查用户是否拥有指定权限"""
    return required_permission in user_permissions or is_admin(user_permissions)


def validate_permissions(permissions: list) -> bool:
    """验证权限列表是否有效"""
    valid_permissions = set(settings.PERMISSIONS)
    return all(perm in valid_permissions for perm in permissions)

