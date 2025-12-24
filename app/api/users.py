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
from app.utils.helpers import format_permissions_to_json, parse_json_permissions, format_datetime_china

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
    - **permissions**: 权限列表（权限代码：waybill-运单管理、booking-订舱管理、settlement-结算单管理、admin-管理员）
    
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
        "created_at": format_datetime_china(new_user.created_at),
        "updated_at": format_datetime_china(new_user.updated_at)
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
            "created_at": format_datetime_china(user.created_at),
            "updated_at": format_datetime_china(user.updated_at)
        }
        user_list.append(user_dict)
    
    return success_response(
        data={"total": len(user_list), "items": user_list},
        msg="查询成功"
    )


@router.get("/{user_id}", summary="获取账号详情")
async def get_user(
    user_id: str,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    获取账号详情接口（需要管理员权限）
    
    - **user_id**: 用户ID（字符串格式）
    """
    # 将字符串ID转换为整数用于查询
    user_id_int = int(user_id)
    
    # 查询用户是否存在，并加载关联的部门
    user = db.query(User).options(joinedload(User.departments)).filter(User.id == user_id_int).first()
    if not user:
        raise NotFoundException("用户不存在")
    
    # 解析权限
    user_permissions = parse_json_permissions(user.permissions)
    
    user_data = {
        "id": str(user.id),
        "phone": user.phone,
        "name": user.name,
        "department_ids": [str(dept.id) for dept in user.departments],
        "departments": [{"id": str(dept.id), "name": dept.name} for dept in user.departments],
        "permissions": user_permissions,
        "is_active": user.is_active,
        "created_at": format_datetime_china(user.created_at),
        "updated_at": format_datetime_china(user.updated_at)
    }
    
    return success_response(data=user_data, msg="查询成功")


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


@router.put("/{user_id}", summary="修改用户信息")
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    修改用户信息接口（需要管理员权限）
    
    - **user_id**: 用户ID（字符串格式）
    - **phone**: 手机号（可选）
    - **password**: 密码（可选）
    - **name**: 用户姓名（可选）
    - **department_ids**: 所属部门ID列表（可选）
    - **permissions**: 权限列表（可选）
    
    注意：
    - 所有字段都是可选的，传入值的就修改该用户属性，没传值的就保留原值
    - 如果修改了权限，该用户的JWT将失效，需要重新登录
    """
    # 将字符串ID转换为整数用于查询
    target_user_id_int = int(user_id)
    
    # 查找目标用户
    target_user = db.query(User).options(joinedload(User.departments)).filter(User.id == target_user_id_int).first()
    if not target_user:
        raise NotFoundException("用户不存在")
    
    # 记录原始权限（用于判断权限是否变更）
    original_permissions = parse_json_permissions(target_user.permissions)
    
    # 更新手机号（如果提供）
    if user_update.phone is not None:
        # 检查新手机号是否与其他用户重复
        existing_user = db.query(User).filter(User.phone == user_update.phone, User.id != target_user_id_int).first()
        if existing_user:
            raise ConflictException("该手机号已被其他用户使用")
        target_user.phone = user_update.phone
    
    # 更新密码（如果提供）
    if user_update.password is not None:
        target_user.password_hash = get_password_hash(user_update.password)
    
    # 更新用户姓名（如果提供）
    if user_update.name is not None:
        target_user.name = user_update.name
    
    # 更新部门（如果提供）
    if user_update.department_ids is not None:
        if user_update.department_ids:
            # 验证部门是否存在
            department_ids_int = [int(dept_id) for dept_id in user_update.department_ids]
            departments = db.query(Department).filter(Department.id.in_(department_ids_int)).all()
            if len(departments) != len(user_update.department_ids):
                raise NotFoundException("部分部门不存在")
            target_user.departments = departments
        else:
            # 空列表表示清空部门关联
            target_user.departments = []
    
    # 更新权限（如果提供）
    permissions_changed = False
    if user_update.permissions is not None:
        # 验证权限列表
        if not validate_permissions(user_update.permissions):
            raise BadRequestException("权限列表包含无效的权限")
        
        # 检查权限是否变更
        new_permissions = sorted(user_update.permissions)
        if sorted(original_permissions) != new_permissions:
            permissions_changed = True
        
        target_user.permissions = format_permissions_to_json(user_update.permissions)
    
    # 如果权限变更，递增token_version使JWT失效
    if permissions_changed:
        target_user.token_version = (target_user.token_version or 0) + 1
    
    db.commit()
    db.refresh(target_user)
    
    # 返回响应（ID转换为字符串）
    user_permissions = parse_json_permissions(target_user.permissions)
    user_data = {
        "id": str(target_user.id),
        "phone": target_user.phone,
        "name": target_user.name,
        "department_ids": [str(dept.id) for dept in target_user.departments],
        "departments": [{"id": str(dept.id), "name": dept.name} for dept in target_user.departments],
        "permissions": user_permissions,
        "is_active": target_user.is_active,
        "created_at": format_datetime_china(target_user.created_at),
        "updated_at": format_datetime_china(target_user.updated_at)
    }
    
    msg = "用户信息修改成功"
    if permissions_changed:
        msg += "，由于权限已变更，该用户的JWT已失效，需要重新登录"
    
    return success_response(data=user_data, msg=msg)


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

