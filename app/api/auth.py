"""
认证相关接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from app.database import get_db
from app.models.user import User
from app.models.config import BusinessConfig
from app.schemas.user import LoginRequest
from app.core.security import verify_password, create_access_token, create_refresh_token, verify_token
from app.core.exceptions import UnauthorizedException, ForbiddenException
from app.core.response import success_response
from app.utils.helpers import parse_json_permissions, format_datetime_china
from app.utils.menu_mapping import generate_menus_by_permissions

router = APIRouter()


class RefreshTokenRequest(BaseModel):
    """刷新token请求"""
    refresh_token: str = Field(..., description="刷新token")


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
            "permissions": ["管理员"],
            "menus": [...],
            "user": {
                "id": "1234567890123456789",
                "phone": "13800000000",
                "name": "张三",
                "department_ids": ["1234567890123456789", "1234567890123456790"],
                "departments": [
                    {"id": "1234567890123456789", "name": "技术部"},
                    {"id": "1234567890123456790", "name": "运营部"}
                ],
                "permissions": ["管理员"],
                "is_active": true,
                "created_at": "2025-01-01T00:00:00",
                "updated_at": "2025-01-01T00:00:00"
            }
        },
        "msg": "登录成功"
    }
    """
    # 查找用户，并加载部门关系
    user = db.query(User).options(joinedload(User.departments)).filter(User.phone == login_data.phone).first()
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
    # 注意：JWT标准要求sub字段必须是字符串
    token_data = {"sub": str(user.id), "phone": user.phone}
    access_token = create_access_token(data=token_data)
    refresh_token = create_refresh_token(data=token_data)
    
    # 解析权限
    permissions = parse_json_permissions(user.permissions)
    
    # 根据权限生成菜单
    menus = generate_menus_by_permissions(permissions)
    
    # 构建用户完整信息（ID转换为字符串）
    user_info = {
        "id": str(user.id),
        "phone": user.phone,
        "name": user.name,
        "department_ids": [str(dept.id) for dept in user.departments],
        "departments": [{"id": str(dept.id), "name": dept.name} for dept in user.departments],
        "permissions": permissions,
        "is_active": user.is_active,
                "created_at": format_datetime_china(user.created_at),
                "updated_at": format_datetime_china(user.updated_at),
    }
    
    # 返回统一格式
    return success_response(
        data={
            "access_token": access_token,
            "refresh_token": refresh_token,
            "has_initialized": has_initialized,
            "permissions": permissions,
            "menus": menus,
            "user": user_info
        },
        msg="登录成功"
    )


@router.post("/refresh", summary="刷新token")
async def refresh_token(
    refresh_data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    刷新token接口
    
    使用refresh_token获取新的access_token和refresh_token
    
    - **refresh_token**: 刷新token
    
    返回格式：
    {
        "code": 0,
        "data": {
            "access_token": "xxx",
            "refresh_token": "xxx"
        },
        "msg": "success"
    }
    """
    # 验证refresh_token
    token_data = verify_token(refresh_data.refresh_token, token_type="refresh")
    if token_data is None:
        # 尝试解码token以获取更详细的错误信息
        try:
            from jose import jwt
            # 不验证签名，只检查payload
            # 注意：即使不验证签名，jwt.decode也需要一个key参数（可以是任意值）
            unverified = jwt.decode(
                refresh_data.refresh_token,
                key="",  # 使用空字符串作为key，因为我们不验证签名
                options={"verify_signature": False, "verify_exp": False}
            )
            # 如果能解码，说明token格式正确，可能是签名或过期问题
            token_type_in_token = unverified.get("type")
            if token_type_in_token != "refresh":
                raise UnauthorizedException(f"token类型错误：期望refresh，实际{token_type_in_token}")
            else:
                # 类型正确，可能是签名或过期问题
                raise UnauthorizedException("无效的refresh_token或token已过期（可能是签名验证失败或token已过期）")
        except Exception:
            # 如果连解码都失败，说明token格式有问题
            raise UnauthorizedException("无效的refresh_token格式")
    
    # 查找用户
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if not user:
        raise UnauthorizedException("用户不存在")
    
    # 检查用户是否启用
    if not user.is_active:
        raise ForbiddenException("用户已被禁用")
    
    # 生成新的token
    # 注意：JWT标准要求sub字段必须是字符串
    new_token_data = {"sub": str(user.id), "phone": user.phone}
    new_access_token = create_access_token(data=new_token_data)
    new_refresh_token = create_refresh_token(data=new_token_data)
    
    # 返回统一格式
    return success_response(
        data={
            "access_token": new_access_token,
            "refresh_token": new_refresh_token
        },
        msg="token刷新成功"
    )

