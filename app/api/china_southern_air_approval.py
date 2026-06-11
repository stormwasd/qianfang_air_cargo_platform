from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.schemas.china_southern_air_approval import ChinaSouthernAirApprovalItem

router = APIRouter()

@router.get("", summary="南航订舱批复跟踪列表")
async def get_china_southern_air_approvals(
    flight_info: Optional[str] = Query(None, description="订舱航班(模糊匹配)"),
    waybill_number: Optional[str] = Query(None, description="运单号"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询南航订舱批复数据
    """
    model = ChinaSouthernAirApprovalData
    query = db.query(model)

    # 1. 航班号查询 (模糊匹配)
    if flight_info:
        query = query.filter(model.flight_info.like(f"%{flight_info}%"))
        
    # 2. 运单号查询
    if waybill_number:
        query = query.filter(model.waybill_number.like(f"%{waybill_number}%"))

    # 计算总数
    total = query.count()

    # 分页查询数据
    offset = (page - 1) * page_size
    records = query.order_by(
        model.id.desc()
    ).offset(offset).limit(page_size).all()

    # 如果当前页没有数据，直接返回
    if not records:
        return success_response(
            data={"total": total, "items": []},
            msg="查询成功"
        )

    # 构造返回列表
    items = []
    for record in records:
        record_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
        record_dict["id"] = str(record.id)  # 转字符串防止精度丢失
        
        # 序列化
        item_schema = ChinaSouthernAirApprovalItem(**record_dict)
        items.append(item_schema.model_dump(mode="json"))

    return success_response(
        data={"total": total, "items": items},
        msg="查询成功"
    )
