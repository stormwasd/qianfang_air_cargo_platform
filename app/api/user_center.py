"""
用户中心接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserPasswordUpdate
from app.api.deps import get_current_active_user
from app.core.security import get_password_hash
from app.core.response import success_response
from app.utils.helpers import parse_json_permissions, format_datetime_utc

router = APIRouter()


@router.get("/info", summary="查看当前用户信息")
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查看当前用户信息接口
    
    返回当前登录用户的详细信息
    """
    # 确保加载部门关系
    db.refresh(current_user, ["departments"])
    
    user_permissions = parse_json_permissions(current_user.permissions)
    
    user_data = {
        "id": str(current_user.id),
        "phone": current_user.phone,
        "name": current_user.name,
        "department_ids": [str(dept.id) for dept in current_user.departments],
        "departments": [{"id": str(dept.id), "name": dept.name} for dept in current_user.departments],
        "permissions": user_permissions,
        "is_active": current_user.is_active,
        "created_at": format_datetime_utc(current_user.created_at),
        "updated_at": format_datetime_utc(current_user.updated_at)
    }
    
    return success_response(data=user_data, msg="查询成功")


@router.put("/password", summary="重置当前用户登录密码")
async def reset_current_user_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    重置当前用户登录密码接口
    
    - **password**: 新密码
    
    注意：此接口只能重置当前登录用户自己的密码
    """
    # 更新密码
    current_user.password_hash = get_password_hash(password_data.password)
    db.commit()
    
    return success_response(data=None, msg="密码重置成功")

