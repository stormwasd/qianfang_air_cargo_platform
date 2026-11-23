"""
提货单位管理接口
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from app.database import get_db
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

from app.models.pickup_unit import PickupUnit
from app.schemas.pickup_unit import (
    PickupUnitCreate,
    PickupUnitUpdate,
    PickupUnitResponse,
    PickupUnitListResponse,
    PickupUnitQuery
)

router = APIRouter()

def _format_pickup_response(unit: PickupUnit) -> dict:
    return {
        "id": str(unit.id),
        "pickup_code": unit.pickup_code,
        "pickup_name": unit.pickup_name,
        "contact_person": unit.contact_person,
        "contact_phone": unit.contact_phone,
        "settlement_method": unit.settlement_method,
        "creator_id": str(unit.creator_id),
        "creator_name": unit.creator_name,
        "created_at": format_datetime_china(unit.created_at),
        "updated_at": format_datetime_china(unit.updated_at)
    }

@router.post("", summary="新增提货单位", response_model=ResponseModel[PickupUnitResponse])
async def create_pickup_unit(
    unit_in: PickupUnitCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """新增提货单位"""
    pickup_code = unit_in.pickup_code
    if not pickup_code:
        latest_unit = db.query(PickupUnit).filter(PickupUnit.pickup_code.like("THS%")).order_by(PickupUnit.pickup_code.desc()).first()
        if latest_unit and latest_unit.pickup_code:
            try:
                num = int(latest_unit.pickup_code[3:])
                pickup_code = f"THS{(num + 1):03d}"
            except ValueError:
                pickup_code = "THS001"
        else:
            pickup_code = "THS001"

    new_unit = PickupUnit(
        pickup_code=pickup_code,
        pickup_name=unit_in.pickup_name,
        contact_person=unit_in.contact_person,
        contact_phone=unit_in.contact_phone,
        settlement_method=unit_in.settlement_method,
        creator_id=current_user.id,
        creator_name=current_user.name
    )
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    
    return success_response(data=_format_pickup_response(new_unit), msg="提货单位创建成功")


@router.put("/{unit_id}", summary="编辑提货单位", response_model=ResponseModel[PickupUnitResponse])
async def update_pickup_unit(
    unit_id: str,
    payload: PickupUnitUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """编辑提货单位"""
    unit = db.query(PickupUnit).filter(PickupUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("提货单位不存在")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(unit, key, value)
            
    db.commit()
    db.refresh(unit)
    
    return success_response(data=_format_pickup_response(unit), msg="提货单位更新成功")


@router.get("/{unit_id}", summary="获取提货单位详情", response_model=ResponseModel[PickupUnitResponse])
async def get_pickup_unit(
    unit_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取提货单位详情"""
    unit = db.query(PickupUnit).filter(PickupUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("提货单位不存在")
    
    return success_response(data=_format_pickup_response(unit), msg="查询成功")


@router.delete("/{unit_id}", summary="删除提货单位", response_model=ResponseModel[Any])
async def delete_pickup_unit(
    unit_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除提货单位"""
    unit = db.query(PickupUnit).filter(PickupUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("提货单位不存在")
        
    db.delete(unit)
    db.commit()
    
    return success_response(msg="提货单位删除成功")


@router.get("", summary="获取提货单位列表", response_model=ResponseModel[PickupUnitListResponse])
async def get_pickup_unit_list(
    query: PickupUnitQuery = Depends(),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取提货单位列表"""
    query_obj = db.query(PickupUnit)
    
    if query.pickup_name:
        query_obj = query_obj.filter(PickupUnit.pickup_name.like(f"%{query.pickup_name}%"))
    
    total = query_obj.count()
    
    offset = (query.page - 1) * query.pageSize
    units = query_obj.order_by(PickupUnit.created_at.desc(), PickupUnit.id.desc()).offset(offset).limit(query.pageSize).all()
    
    items = [_format_pickup_response(u) for u in units]
    
    return success_response(data={"total": total, "items": items}, msg="查询成功")
