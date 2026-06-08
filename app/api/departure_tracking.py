from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List
from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.schemas.departure_tracking import ShenzhenAirDepartureListResponse, ShenzhenAirDepartureItem, ShenzhenAirBillingTimeContainerDTO

router = APIRouter()

@router.get("/shenzhen-air", summary="深航出港列表")
async def get_shenzhen_air_departures(
    waybill_number: Optional[str] = Query(None, description="运单号，多个用逗号隔开"),
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-03-10"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-03-15"),
    flight_number: Optional[str] = Query(None, description="航班号"),
    page: int = Query(1, description="页码", ge=1),
    page_size: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询深航出港列表，主表为 shenzhen_air_booking_exports，附带 shenzhen_air_billing_time_containers 数据。
    """
    query = db.query(ShenzhenAirBookingExport)

    # 1. 航班号查询
    if flight_number:
        query = query.filter(
            or_(
                ShenzhenAirBookingExport.billing_flight.like(f"%{flight_number}%"),
                ShenzhenAirBookingExport.actual_flight.like(f"%{flight_number}%")
            )
        )
        
    # 2. 航班日期区间查询
    if flight_date_start:
        query = query.filter(ShenzhenAirBookingExport.flight_date >= flight_date_start)
    if flight_date_end:
        query = query.filter(ShenzhenAirBookingExport.flight_date <= flight_date_end)

    # 3. 运单号多单号查询
    if waybill_number:
        waybill_numbers = [wn.strip() for wn in waybill_number.split(",") if wn.strip()]
        if waybill_numbers:
            query = query.filter(ShenzhenAirBookingExport.waybill_number.in_(waybill_numbers))

    # 计算总数
    total = query.count()

    # 分页查询主表数据，修复由于 created_at 相同导致的分页乱序问题
    offset = (page - 1) * page_size
    exports = query.order_by(
        ShenzhenAirBookingExport.creation_time.desc(), 
        ShenzhenAirBookingExport.id.desc()
    ).offset(offset).limit(page_size).all()

    # 如果当前页没有数据，直接返回
    if not exports:
        return success_response(
            data={"total": total, "items": []},
            msg="查询成功"
        )

    # 4. 提取当前页的所有主表单号的后8位，用于批量查询从表
    # 主表的运单号通常格式为 479-12345678 或 12345678
    # 从表的运单号明确为 waybill_number_8 (12345678)
    waybill_8_list = []
    export_by_wb8 = {}  # 记录后8位与主表实体的对应关系，用于组装
    
    for export in exports:
        if export.waybill_number:
            wb8 = export.waybill_number[-8:] if len(export.waybill_number) >= 8 else export.waybill_number
            waybill_8_list.append(wb8)
            # 建立映射表
            if wb8 not in export_by_wb8:
                export_by_wb8[wb8] = []
            export_by_wb8[wb8].append(export)

    # 5. 批量查询关联的从表数据
    containers = []
    if waybill_8_list:
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.waybill_number_8.in_(waybill_8_list)
        ).all()

    # 6. 在内存中组装数据
    # 按主表对象的ID初始化空列表
    containers_by_export_id = {export.id: [] for export in exports}
    
    for container in containers:
        wb8 = container.waybill_number_8
        if wb8 in export_by_wb8:
            for matched_export in export_by_wb8[wb8]:
                containers_by_export_id[matched_export.id].append(container)

    # 构造返回列表
    items = []
    for export in exports:
        export_dict = {k: v for k, v in export.__dict__.items() if not k.startswith('_')}
        export_dict["id"] = str(export.id)  # 转字符串防止精度丢失
        
        # 使用 Pydantic 严格按照 Schema 定义的顺序和类型进行序列化
        item_schema = ShenzhenAirDepartureItem(**export_dict)
        
        # 组装子表数据
        containers_data = []
        for c in containers_by_export_id[export.id]:
            c_dict = {k: v for k, v in c.__dict__.items() if not k.startswith('_')}
            c_dict["id"] = str(c.id)
            containers_data.append(ShenzhenAirBillingTimeContainerDTO(**c_dict))
            
        item_schema.billing_time_containers = containers_data
        
        # 转换为字典，保持键顺序一致
        items.append(item_schema.model_dump(mode="json"))

    return success_response(
        data={"total": total, "items": items},
        msg="查询成功"
    )
