from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.schemas.china_southern_air_approval import ChinaSouthernAirApprovalItem

router = APIRouter()

from sqlalchemy import or_, func

@router.get("", summary="南航订舱批复跟踪列表")
async def get_china_southern_air_approvals(
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-03-10"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-04-20"),
    flight_number: Optional[str] = Query(None, description="航班号"),
    waybill_number: Optional[str] = Query(None, description="运单号，支持多个用逗号分隔"),
    page: int = Query(1, description="页码", ge=1),
    pageSize: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询南航订舱批复数据
    """
    model = ChinaSouthernAirApprovalData
    query = db.query(model)

    # 1. 航班号查询
    if flight_number:
        # 从 flight_info 的第一个部分中匹配航班号，如 CZ3649
        flight_no_str = func.trim(func.substring_index(model.flight_info, ' / ', 1))
        query = query.filter(flight_no_str.like(f"%{flight_number}%"))
        
    # 2. 航班日期区间查询
    if flight_date_start or flight_date_end:
        # 从 flight_info 中截取第二部分作为日期，如 2026-06-10
        date_str = func.trim(func.substring_index(func.substring_index(model.flight_info, ' / ', 2), ' / ', -1))
        if flight_date_start:
            query = query.filter(func.replace(date_str, '/', '-') >= flight_date_start)
        if flight_date_end:
            query = query.filter(func.replace(date_str, '/', '-') <= f"{flight_date_end} 23:59:59")
            
    # 3. 运单号查询 (支持多单号逗号分隔)
    if waybill_number:
        waybills = [w.strip() for w in waybill_number.split(',') if w.strip()]
        if waybills:
            conditions = [model.waybill_number.like(f"%{w}%") for w in waybills]
            query = query.filter(or_(*conditions))

    # 计算总数
    total = query.count()

    # 分页查询数据
    offset = (page - 1) * pageSize
    records = query.order_by(
        model.id.desc()
    ).offset(offset).limit(pageSize).all()

    # 如果当前页没有数据，直接返回
    if not records:
        return success_response(
            data={"total": total, "items": [], "data_update_time": None},
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

    # 提取数据更新时间（第一条记录的 updated_at，格式化到分钟）
    data_update_time = None
    if records and hasattr(records[0], 'updated_at') and records[0].updated_at:
        data_update_time = records[0].updated_at.strftime("%Y-%m-%d %H:%M")

    return success_response(
        data={"total": total, "items": items, "data_update_time": data_update_time},
        msg="查询成功"
    )
