"""
账号管理接口
"""
from fastapi import APIRouter, Depends, status
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException, ConflictException
from app.core.response import success_response
from app.utils.response_helpers import model_to_dict, convert_model_list
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.database import get_db
from app.models.user import User
from app.models.department import Department
from app.schemas.user import (
    UserCreate, UserUpdate, UserPasswordUpdate,
    UserResponse, UserListResponse,
    BatchUserStatusUpdate, BatchUserDelete
)
from app.api.deps import require_admin, get_current_active_user
from app.core.security import get_password_hash
from app.core.permissions import validate_permissions
from app.utils.helpers import format_permissions_to_json, parse_json_permissions, convert_id_to_str, convert_ids_to_str

router = APIRouter()


@router.post("", summary="新增账号")
async def create_user(
    user: UserCreate,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    新增账号接口（需要管理员权限）
    
    - **phone**: 手机号（账号）
    - **password**: 密码
    - **name**: 用户姓名
    - **department_ids**: 所属部门ID列表（支持多个部门）
    - **permissions**: 权限列表（运单管理、订舱管理、结算单管理、管理员）
    
    新增账号默认启用
    """
    # 验证权限列表
    if not validate_permissions(user.permissions):
        raise BadRequestException("权限列表包含无效的权限")
    
    # 检查手机号是否已存在
    existing_user = db.query(User).filter(User.phone == user.phone).first()
    if existing_user:
        raise ConflictException("该手机号已被注册")
    
    # 验证部门是否存在
    if user.department_ids:
        # 将字符串ID转换为整数用于查询
        department_ids_int = [int(dept_id) for dept_id in user.department_ids]
        departments = db.query(Department).filter(Department.id.in_(department_ids_int)).all()
        if len(departments) != len(user.department_ids):
            raise NotFoundException("部分部门不存在")
    
    # 创建用户
    new_user = User(
        phone=user.phone,
        password_hash=get_password_hash(user.password),
        name=user.name,
        permissions=format_permissions_to_json(user.permissions),
        is_active=True  # 默认启用
    )
    
    # 关联部门
    if user.department_ids:
        new_user.departments = departments
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # 返回响应（ID转换为字符串）
    user_permissions = parse_json_permissions(new_user.permissions)
    user_data = {
        "id": str(new_user.id),
        "phone": new_user.phone,
        "name": new_user.name,
        "department_ids": [str(dept.id) for dept in new_user.departments],
        "departments": [{"id": str(dept.id), "name": dept.name} for dept in new_user.departments],
        "permissions": user_permissions,
        "is_active": new_user.is_active,
        "created_at": new_user.created_at.isoformat(),
        "updated_at": new_user.updated_at.isoformat()
    }
    return success_response(data=user_data, msg="账号创建成功")


@router.get("", summary="查看已创建账号")
async def get_users(
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    查看已创建账号接口（需要管理员权限）
    
    返回所有账号的列表
    """
    users = db.query(User).options(joinedload(User.departments)).order_by(User.created_at.desc()).all()
    
    user_list = []
    for user in users:
        user_permissions = parse_json_permissions(user.permissions)
        user_dict = {
            "id": str(user.id),
            "phone": user.phone,
            "name": user.name,
            "department_ids": [str(dept.id) for dept in user.departments],
            "departments": [{"id": str(dept.id), "name": dept.name} for dept in user.departments],
            "permissions": user_permissions,
            "is_active": user.is_active,
            "created_at": user.created_at.isoformat(),
            "updated_at": user.updated_at.isoformat()
        }
        user_list.append(user_dict)
    
    return success_response(
        data={"total": len(user_list), "items": user_list},
        msg="查询成功"
    )


@router.put("/{user_id}/status", summary="启用或停用账号")
async def update_user_status(
    user_id: str,
    is_active: bool,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    启用或停用账号接口（需要管理员权限，支持批量）
    
    - **user_id**: 用户ID（字符串格式）
    - **is_active**: 是否启用（true=启用，false=停用）
    """
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise NotFoundException("用户不存在")
    
    user.is_active = is_active
    db.commit()
    
    return success_response(
        data={"user_id": str(user_id), "is_active": is_active},
        msg="操作成功"
    )


@router.put("/batch-status", summary="批量启用或停用账号")
async def batch_update_user_status(
    batch_data: BatchUserStatusUpdate,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    批量启用或停用账号接口（需要管理员权限）
    
    - **user_ids**: 用户ID列表（字符串格式）
    - **is_active**: 是否启用（true=启用，false=停用）
    """
    # 将字符串ID转换为整数用于查询
    user_ids_int = [int(uid) for uid in batch_data.user_ids]
    users = db.query(User).filter(User.id.in_(user_ids_int)).all()
    if len(users) != len(batch_data.user_ids):
        raise BadRequestException("部分用户ID不存在")
    
    for user in users:
        user.is_active = batch_data.is_active
    db.commit()
    
    return success_response(
        data={"count": len(users), "is_active": batch_data.is_active},
        msg="批量操作成功"
    )


@router.put("/password", summary="更新账号密码")
async def update_user_password(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新账号密码接口
    
    - **password**: 新密码
    - **user_id**: 用户ID（可选，管理员更新其他用户密码时使用）
    
    注意：
    - 管理员可以更新所有账号的密码
    - 非管理员只能更新自己账号的密码
    """
    from app.core.permissions import is_admin
    
    user_permissions = parse_json_permissions(current_user.permissions)
    is_user_admin = is_admin(user_permissions)
    
    # 确定要更新密码的用户
    target_user_id = password_data.user_id if password_data.user_id else current_user.id
    
    # 权限检查：非管理员只能更新自己的密码
    if not is_user_admin and target_user_id != current_user.id:
        raise ForbiddenException("无权限更新其他用户的密码")
    
    # 查找目标用户
    target_user = db.query(User).filter(User.id == target_user_id).first()
    if not target_user:
        raise NotFoundException("用户不存在")
    
    # 更新密码
    target_user.password_hash = get_password_hash(password_data.password)
    db.commit()
    
    return success_response(
        data={"user_id": str(target_user_id_int)},
        msg="密码更新成功"
    )


@router.delete("/{user_id}", summary="删除账号")
async def delete_user(
    user_id: str,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    删除账号接口（需要管理员权限）
    
    - **user_id**: 用户ID（字符串格式）
    """
    user_id_int = int(user_id)
    user = db.query(User).filter(User.id == user_id_int).first()
    if not user:
        raise NotFoundException("用户不存在")
    
    # 不能删除自己
    if user.id == current_user.id:
        raise BadRequestException("不能删除自己的账号")
    
    db.delete(user)
    db.commit()
    
    return success_response(
        data={"user_id": str(user_id)},
        msg="账号删除成功"
    )


@router.delete("", summary="批量删除账号")
async def batch_delete_users(
    batch_data: BatchUserDelete,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    批量删除账号接口（需要管理员权限）
    
    - **user_ids**: 用户ID列表（字符串格式）
    """
    # 将字符串ID转换为整数用于查询
    user_ids_int = [int(uid) for uid in batch_data.user_ids]
    
    # 不能删除自己
    if current_user.id in user_ids_int:
        raise BadRequestException("不能删除自己的账号")
    
    users = db.query(User).filter(User.id.in_(user_ids_int)).all()
    if len(users) != len(batch_data.user_ids):
        raise BadRequestException("部分用户ID不存在")
    
    for user in users:
        db.delete(user)
    db.commit()
    
    return success_response(
        data={"count": len(users)},
        msg="批量删除成功"
    )

