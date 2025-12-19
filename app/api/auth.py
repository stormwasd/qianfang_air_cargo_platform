"""
认证相关接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.config import BusinessConfig
from app.schemas.user import LoginRequest
from app.core.security import verify_password, create_access_token, create_refresh_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.response import success_response
from app.utils.helpers import parse_json_permissions

router = APIRouter()


@router.post("/login", summary="用户登录")
async def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    用户登录接口
    
    - **phone**: 手机号（11位）
    - **password**: 登录密码
    
    返回格式：
    {
        "code": 0,
        "data": {
            "access_token": "xxx",
            "refresh_token": "xxx",
            "has_initialized": false,
            "permissions": ["管理员"]
        },
        "msg": "success"
    }
    """
    # 查找用户
    user = db.query(User).filter(User.phone == login_data.phone).first()
    if not user:
        raise UnauthorizedException("手机号或密码错误")
    
    # 验证密码
    if not verify_password(login_data.password, user.password_hash):
        raise UnauthorizedException("手机号或密码错误")
    
    # 检查用户是否启用
    if not user.is_active:
        raise ForbiddenException("用户已被禁用")
    
    # 检查是否已初始化配置
    has_initialized = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == user.id
    ).first() is not None
    
    # 生成token
    token_data = {"sub": user.id, "phone": user.phone}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    # 解析权限
    permissions = parse_json_permissions(user.permissions)
    
    # 返回统一格式
    return success_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "has_initialized": has_initialized,
            "permissions": permissions
        },
        msg="登录成功"
    )

