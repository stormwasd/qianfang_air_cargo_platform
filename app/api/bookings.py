"""
订舱管理接口
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from app.core.response import success_response
from app.database import get_db
from app.models.booking import Booking, BookingStatus, InvoiceStatus
from app.schemas.booking import (
    BookingCreate, BookingQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()


@router.post("", summary="确认订舱信息并提交")
async def create_booking(
    booking: BookingCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认订舱信息并提交接口
    
    - **form_data**: 表单数据（JSON格式），前端可以传入任意字段
    - 自动设置booking_time为当前时间（中国时间）
    - 订舱状态默认为"未执行"
    - 开单状态默认为"未开单"
    - master_airwaybill_number初始为null，由RPA后续写入
    """
    # 将form_data转换为JSON字符串
    form_data_json = json.dumps(booking.form_data, ensure_ascii=False)
    
    # 获取当前时间（中国时间）作为订舱时间
    booking_time = get_china_now()
    
    new_booking = Booking(
        form_data=form_data_json,
        booking_time=booking_time,
        booking_status=BookingStatus.NOT_EXECUTED.value,
        invoice_status=InvoiceStatus.NOT_INVOICED.value
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    # 解析form_data JSON
    form_data_dict = json.loads(new_booking.form_data)
    
    booking_data = {
        "id": str(new_booking.id),
        "form_data": form_data_dict,
        "booking_status": new_booking.booking_status,
        "invoice_status": new_booking.invoice_status,
        "booking_time": format_datetime_china(new_booking.booking_time),
        "master_airwaybill_number": new_booking.master_airwaybill_number,
        "created_at": format_datetime_china(new_booking.created_at),
        "updated_at": format_datetime_china(new_booking.updated_at)
    }
    
    return success_response(data=booking_data, msg="订舱信息提交成功")


@router.get("", summary="订舱列表")
async def get_bookings(
    query: BookingQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    订舱列表接口（支持筛选）
    
    查询参数：
    - **airline**: 航司（模糊搜索，从form_data JSON中提取，如：南方航空、深圳航空）
    - **booking_status**: 订舱状态筛选（未执行、执行中、执行失败）
    - **invoice_status**: 开单状态筛选（未开单、成功）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    
    支持多条件组合筛选，航司从form_data JSON中提取进行模糊搜索
    """
    # 构建查询
    query_obj = db.query(Booking)
    
    # 订舱状态筛选
    if query.booking_status:
        query_obj = query_obj.filter(
            Booking.booking_status == query.booking_status
        )
    
    # 开单状态筛选
    if query.invoice_status:
        query_obj = query_obj.filter(
            Booking.invoice_status == query.invoice_status
        )
    
    # 从form_data JSON中提取航司字段进行模糊搜索
    # 使用MySQL的JSON函数进行搜索（MySQL 5.7+支持）
    if query.airline:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Booking.form_data, JSON), 
                    "$.airline"
                ),
                func.CHAR
            ).like(f"%{query.airline}%")
        )
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    bookings = query_obj.order_by(
        Booking.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    booking_list = []
    for booking in bookings:
        # 解析form_data JSON
        form_data_dict = json.loads(booking.form_data)
        
        booking_list.append({
            "id": str(booking.id),
            "form_data": form_data_dict,
            "booking_status": booking.booking_status,
            "invoice_status": booking.invoice_status,
            "booking_time": format_datetime_china(booking.booking_time),
            "master_airwaybill_number": booking.master_airwaybill_number,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": booking_list},
        msg="查询成功"
    )

