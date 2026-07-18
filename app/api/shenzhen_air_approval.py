from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional
from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.models.shenzhen_air_approval import ShenzhenAirApprovalData, ShenzhenAirApprovalWideBodyData
from app.schemas.shenzhen_air_approval import ShenzhenAirApprovalListResponse, ShenzhenAirApprovalNarrowItem, ShenzhenAirApprovalWideItem

router = APIRouter()

@router.get("", summary="深航订舱批复跟踪列表")
async def get_shenzhen_air_approvals(
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-03-10"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-03-15"),
    flight_number: Optional[str] = Query(None, description="航班号"),
    cabin_type: int = Query(0, description="仓位类型(0=散仓(非宽体), 1=版/箱/散卡(宽体))"),
    page: int = Query(1, description="页码", ge=1),
    pageSize: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询深航订舱批复数据，支持根据 cabin_type 切换数据源：
    - cabin_type=0 对应 shenzhen_air_approval_data 表
    - cabin_type=1 对应 shenzhen_air_approval_wide_body_data 表
    """
    if cabin_type == 1:
        model = ShenzhenAirApprovalWideBodyData
        schema_class = ShenzhenAirApprovalWideItem
    else:
        model = ShenzhenAirApprovalData
        schema_class = ShenzhenAirApprovalNarrowItem
        
    query = db.query(model)

    filters = []
    if flight_number:
        filters.append(model.flight_number.like(f"%{flight_number}%"))
        
    if flight_date_start:
        filters.append(func.replace(model.flight_date, '/', '-') >= flight_date_start)
    if flight_date_end:
        filters.append(func.replace(model.flight_date, '/', '-') <= f"{flight_date_end} 23:59:59")

    if filters:
        parent_query = db.query(model.id).filter(model.parent_id == None, *filters)
        query = query.filter(
            or_(
                model.id.in_(parent_query),
                model.parent_id.in_(parent_query)
            )
        )

    total = query.count()

    offset = (page - 1) * pageSize
    records = query.order_by(
        func.coalesce(model.parent_id, model.id).desc(),
        model.id.asc()
    ).offset(offset).limit(pageSize).all()

    if not records:
        return success_response(
            data={"total": total, "items": [], "data_update_time": None},
            msg="查询成功"
        )

    items = []
    for record in records:
        record_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
        record_dict["id"] = str(record.id)  
        if record_dict.get("parent_id") is not None:
            record_dict["parent_id"] = str(record_dict["parent_id"])
        
        item_schema = schema_class(**record_dict)
        items.append(item_schema.model_dump(mode="json"))

    data_update_time = None
    if records and hasattr(records[0], 'updated_at') and records[0].updated_at:
        data_update_time = records[0].updated_at.strftime("%Y-%m-%d %H:%M")

    return success_response(
        data={"total": total, "items": items, "data_update_time": data_update_time},
        msg="查询成功"
    )
