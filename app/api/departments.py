"""
部门管理接口
"""
from fastapi import APIRouter, Depends
from app.core.exceptions import ConflictException, NotFoundException
from app.core.response import success_response
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.api.deps import require_admin, get_current_active_user
from app.utils.helpers import format_datetime_china

router = APIRouter()


@router.post("", summary="新建部门")
async def create_department(
    department: DepartmentCreate,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    新建部门接口（需要管理员权限）
    
    - **name**: 部门名称
    """
    existing_department = db.query(Department).filter(
        Department.name == department.name
    ).first()
    
    if existing_department:
        raise ConflictException("部门名称已存在")
    
    new_department = Department(name=department.name)
    db.add(new_department)
    db.commit()
    db.refresh(new_department)
    
    department_data = {
        "id": str(new_department.id),
        "name": new_department.name,
        "created_at": format_datetime_china(new_department.created_at),
        "updated_at": format_datetime_china(new_department.updated_at)
    }
    
    return success_response(data=department_data, msg="部门创建成功")


@router.get("", summary="查看已创建部门列表")
async def get_departments(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查看已创建部门列表接口
    
    返回所有部门的列表
    """
    departments = db.query(Department).order_by(Department.created_at.desc()).all()
    
    department_list = [
        {
            "id": str(dept.id),
            "name": dept.name,
            "created_at": format_datetime_china(dept.created_at),
            "updated_at": format_datetime_china(dept.updated_at)
        }
        for dept in departments
    ]
    
    return success_response(
        data={"total": len(department_list), "items": department_list},
        msg="查询成功"
    )


@router.get("/{department_id}", summary="获取部门详情")
async def get_department(
    department_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取部门详情接口
    
    - **department_id**: 部门ID（字符串格式）
    """
    department_id_int = int(department_id)
    
    department = db.query(Department).filter(Department.id == department_id_int).first()
    if not department:
        raise NotFoundException("部门不存在")
    
    department_data = {
        "id": str(department.id),
        "name": department.name,
        "created_at": format_datetime_china(department.created_at),
        "updated_at": format_datetime_china(department.updated_at)
    }
    
    return success_response(data=department_data, msg="查询成功")


@router.put("/{department_id}", summary="修改部门")
async def update_department(
    department_id: str,
    department: DepartmentUpdate,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    修改部门接口（需要管理员权限）
    
    - **department_id**: 部门ID（字符串格式）
    - **name**: 新的部门名称
    
    注意：
    - 只能修改部门名称
    - 新名称不能与其他部门重复
    """
    department_id_int = int(department_id)
    
    existing_department = db.query(Department).filter(Department.id == department_id_int).first()
    if not existing_department:
        raise NotFoundException("部门不存在")
    
    duplicate_department = db.query(Department).filter(
        Department.name == department.name,
        Department.id != department_id_int
    ).first()
    
    if duplicate_department:
        raise ConflictException("部门名称已存在")
    
    existing_department.name = department.name
    db.commit()
    db.refresh(existing_department)
    
    department_data = {
        "id": str(existing_department.id),
        "name": existing_department.name,
        "created_at": format_datetime_china(existing_department.created_at),
        "updated_at": format_datetime_china(existing_department.updated_at)
    }
    
    return success_response(data=department_data, msg="部门修改成功")


@router.delete("/{department_id}", summary="删除部门")
async def delete_department(
    department_id: str,
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    删除部门接口（需要管理员权限）
    
    - **department_id**: 部门ID（字符串格式）
    
    注意：
    - 删除部门会自动解除该部门与所有用户的关联关系（由数据库CASCADE处理）
    - 删除后，原本只属于该部门的用户将没有部门归属
    """
    department_id_int = int(department_id)
    
    department = db.query(Department).options(joinedload(Department.users)).filter(Department.id == department_id_int).first()
    if not department:
        raise NotFoundException("部门不存在")
    
    user_count = len(department.users) if department.users else 0
    
    db.delete(department)
    db.commit()
    
    return success_response(
        data={
            "department_id": str(department_id),
            "department_name": department.name,
            "affected_users_count": user_count
        },
        msg=f"部门删除成功，已解除 {user_count} 个用户的关联关系" if user_count > 0 else "部门删除成功"
    )

