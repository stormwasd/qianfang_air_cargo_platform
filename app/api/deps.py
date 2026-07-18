"""
API依赖项：认证、权限检查等
使用统一的异常处理
"""
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.user import User
from app.core.security import verify_token
from app.core.permissions import is_admin
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.utils.helpers import parse_json_permissions

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前登录用户"""
    token = credentials.credentials
    token_data = verify_token(token, token_type="access")
    if token_data is None:
        raise UnauthorizedException("无效的token或token已过期")
    
    user = db.query(User).options(joinedload(User.departments)).filter(User.id == token_data.user_id).first()
    if user is None:
        raise UnauthorizedException("用户不存在")
    
    if token_data.token_version != user.token_version:
        raise UnauthorizedException("token已失效，请重新登录")
    
    if not user.is_active:
        raise UnauthorizedException("用户已被禁用")
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise UnauthorizedException("用户已被禁用")
    return current_user


def require_admin(current_user: User = Depends(get_current_active_user)) -> User:
    """要求管理员权限"""
    user_permissions = parse_json_permissions(current_user.permissions)
    if not is_admin(user_permissions):
        raise ForbiddenException("需要管理员权限")
    return current_user


def require_permission(permission_code: str):
    """
    权限校验工厂函数
    
    生成一个 FastAPI 依赖项，校验当前用户是否拥有指定权限代码或管理员权限。
    
    Args:
        permission_code: 权限代码（如 "bill", "robot"）
    
    Returns:
        FastAPI依赖函数
    
    Usage:
        @router.get("", dependencies=[Depends(require_permission("robot"))])
        或
        current_user = Depends(require_permission("robot"))
    """
    from app.core.permissions import has_permission
    
    def _check_permission(current_user: User = Depends(get_current_active_user)) -> User:
        user_permissions = parse_json_permissions(current_user.permissions)
        if not has_permission(user_permissions, permission_code):
            raise ForbiddenException(f"需要「{permission_code}」权限或管理员权限")
        return current_user
    
    return _check_permission

