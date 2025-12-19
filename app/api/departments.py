"""
部门管理接口
"""
from fastapi import APIRouter, Depends
from app.core.exceptions import ConflictException
from app.core.response import success_response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.department import Department
from app.schemas.department import DepartmentCreate
from app.api.deps import require_admin

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
    # 检查部门名称是否已存在
    existing_department = db.query(Department).filter(
        Department.name == department.name
    ).first()
    
    if existing_department:
        raise ConflictException("部门名称已存在")
    
    # 创建部门
    new_department = Department(name=department.name)
    db.add(new_department)
    db.commit()
    db.refresh(new_department)
    
    department_data = {
        "id": new_department.id,
        "name": new_department.name,
        "created_at": new_department.created_at.isoformat(),
        "updated_at": new_department.updated_at.isoformat()
    }
    
    return success_response(data=department_data, msg="部门创建成功")


@router.get("", summary="查看已创建部门")
async def get_departments(
    current_user = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    查看已创建部门接口（需要管理员权限）
    
    返回所有部门的列表
    """
    departments = db.query(Department).order_by(Department.created_at.desc()).all()
    
    department_list = [
        {
            "id": dept.id,
            "name": dept.name,
            "created_at": dept.created_at.isoformat(),
            "updated_at": dept.updated_at.isoformat()
        }
        for dept in departments
    ]
    
    return success_response(
        data={"total": len(department_list), "items": department_list},
        msg="查询成功"
    )

