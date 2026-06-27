"""
派送单位管理接口
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from app.database import get_db
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

from app.models.delivery_unit import DeliveryUnit
from app.schemas.delivery_unit import (
    DeliveryUnitCreate,
    DeliveryUnitUpdate,
    DeliveryUnitResponse,
    DeliveryUnitListResponse,
    DeliveryUnitQuery
)

router = APIRouter()

def _format_delivery_response(unit: DeliveryUnit) -> dict:
    return {
        "id": str(unit.id),
        "delivery_code": unit.delivery_code,
        "delivery_name": unit.delivery_name,
        "contact_person": unit.contact_person,
        "contact_phone": unit.contact_phone,
        "settlement_method": unit.settlement_method,
        "creator_id": str(unit.creator_id),
        "creator_name": unit.creator_name,
        "created_at": format_datetime_china(unit.created_at),
        "updated_at": format_datetime_china(unit.updated_at)
    }

@router.post("", summary="新增派送单位", response_model=ResponseModel[DeliveryUnitResponse])
async def create_delivery_unit(
    unit_in: DeliveryUnitCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """新增派送单位"""
    delivery_code = unit_in.delivery_code
    if not delivery_code:
        # 获取当前最大的派送单位编码
        latest_unit = db.query(DeliveryUnit).filter(DeliveryUnit.delivery_code.like("PSS%")).order_by(DeliveryUnit.delivery_code.desc()).first()
        if latest_unit and latest_unit.delivery_code:
            try:
                # 提取末尾的数字部分
                num = int(latest_unit.delivery_code[3:])
                delivery_code = f"PSS{(num + 1):03d}"
            except ValueError:
                delivery_code = "PSS001"
        else:
            delivery_code = "PSS001"

    new_unit = DeliveryUnit(
        delivery_code=delivery_code,
        delivery_name=unit_in.delivery_name,
        contact_person=unit_in.contact_person,
        contact_phone=unit_in.contact_phone,
        settlement_method=unit_in.settlement_method,
        creator_id=current_user.id,
        creator_name=current_user.name
    )
    db.add(new_unit)
    db.commit()
    db.refresh(new_unit)
    
    return success_response(data=_format_delivery_response(new_unit), msg="派送单位创建成功")


@router.put("/{unit_id}", summary="编辑派送单位", response_model=ResponseModel[DeliveryUnitResponse])
async def update_delivery_unit(
    unit_id: str,
    payload: DeliveryUnitUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """编辑派送单位"""
    unit = db.query(DeliveryUnit).filter(DeliveryUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("派送单位不存在")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(unit, key, value)
            
    db.commit()
    db.refresh(unit)
    
    return success_response(data=_format_delivery_response(unit), msg="派送单位更新成功")


@router.get("/{unit_id}", summary="获取派送单位详情", response_model=ResponseModel[DeliveryUnitResponse])
async def get_delivery_unit(
    unit_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取派送单位详情"""
    unit = db.query(DeliveryUnit).filter(DeliveryUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("派送单位不存在")
    
    return success_response(data=_format_delivery_response(unit), msg="查询成功")


@router.delete("/{unit_id}", summary="删除派送单位", response_model=ResponseModel[Any])
async def delete_delivery_unit(
    unit_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除派送单位"""
    unit = db.query(DeliveryUnit).filter(DeliveryUnit.id == int(unit_id)).first()
    if not unit:
        raise NotFoundException("派送单位不存在")
        
    db.delete(unit)
    db.commit()
    
    return success_response(msg="派送单位删除成功")


@router.get("", summary="获取派送单位列表", response_model=ResponseModel[DeliveryUnitListResponse])
async def get_delivery_unit_list(
    query: DeliveryUnitQuery = Depends(),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取派送单位列表"""
    query_obj = db.query(DeliveryUnit)
    
    if query.delivery_name:
        query_obj = query_obj.filter(DeliveryUnit.delivery_name.like(f"%{query.delivery_name}%"))
    
    total = query_obj.count()
    
    offset = (query.page - 1) * query.pageSize
    units = query_obj.order_by(DeliveryUnit.created_at.desc(), DeliveryUnit.id.desc()).offset(offset).limit(query.pageSize).all()
    
    items = [_format_delivery_response(u) for u in units]
    
    return success_response(data={"total": total, "items": items}, msg="查询成功")
