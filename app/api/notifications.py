"""
通知管理接口
"""
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.response import success_response
from app.core.exceptions import BadRequestException, NotFoundException
from app.database import get_db
from app.models.waybill import Waybill
from app.models.booking import Booking
from app.models.rpa_task import RPATask, RPATaskStatus
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

router = APIRouter()


# 航空公司数据字典映射
AIRLINE_NAME_MAP = {
    "1": "深圳航空",
    "2": "南方航空"
}


def _extract_waybill_notification_data(waybill: Waybill, is_exception: bool = False) -> dict:
    """
    从运单中提取通知所需的数据
    
    Args:
        waybill: 运单对象
        is_exception: 是否为异常任务
    
    Returns:
        通知数据字典
    """
    # 解析form_data
    form_data = json.loads(waybill.form_data)
    
    # 获取航空公司
    airline = form_data.get("airline", "")
    airline_name = AIRLINE_NAME_MAP.get(airline, "未知航空公司")
    
    # 获取航班信息
    flight_info = form_data.get("flight_info", {})
    flight_number = flight_info.get("flight_number", "")
    
    # 获取货物信息
    cargo_info = form_data.get("cargo_info", {})
    quantity = cargo_info.get("quantity", "")
    weight = cargo_info.get("weight", "")
    
    # 获取货物类型和客户名称（根据航空公司不同，字段位置不同）
    # 深航：货物类型 = cargo_info.cargo_name，客户名称 = shipper_consignee_info.shipper_unit
    # 南航：货物类型 = cargo_info.cargo_type，客户名称 = contact_info.shipper_unit
    cargo_type = ""
    customer_name = ""
    if airline == "1":  # 深航
        cargo_type = cargo_info.get("cargo_name", "")
        shipper_consignee_info = form_data.get("shipper_consignee_info", {})
        customer_name = shipper_consignee_info.get("shipper_unit", "")
    elif airline == "2":  # 南航
        cargo_type = cargo_info.get("cargo_type", "")
        contact_info = form_data.get("contact_info", {})
        customer_name = contact_info.get("shipper_unit", "")
    
    # 构建通知数据
    notification_data = {
        "id": str(waybill.id),
        "task_type": "开单",
        "source_table": "waybills",
        "airline": airline,
        "airline_name": airline_name,
        "flight_number": flight_number,
        "task_date": waybill.booking_date.isoformat() if waybill.booking_date else None,
        "customer_name": customer_name,
        "quantity": str(quantity) if quantity else "",
        "weight": str(weight) if weight else "",
        "cargo_type": cargo_type
    }
    
    # 如果是异常任务，添加异常时间
    if is_exception:
        notification_data["exception_time"] = format_datetime_china(waybill.updated_at)
    else:
        notification_data["exception_time"] = None
    
    return notification_data


def _extract_booking_notification_data(booking: Booking, is_exception: bool = False) -> dict:
    """
    从订舱中提取通知所需的数据
    
    Args:
        booking: 订舱对象
        is_exception: 是否为异常任务
    
    Returns:
        通知数据字典
    """
    # 解析form_data
    form_data = json.loads(booking.form_data)
    
    # 获取航空公司
    airline = form_data.get("airline", "")
    airline_name = AIRLINE_NAME_MAP.get(airline, "未知航空公司")
    
    # 获取bookings数组中的第一个元素
    bookings_list = form_data.get("bookings", [])
    booking_item = bookings_list[0] if bookings_list and len(bookings_list) > 0 else {}
    
    # 获取航班号
    flight_number = booking_item.get("flight_number", "")
    
    # 获取数量、重量、货物类型
    # 订舱只有南航，货物类型字段为 cargo_type
    quantity = booking_item.get("quantity", "")
    weight = booking_item.get("weight", "")
    cargo_type = booking_item.get("cargo_type", "")
    
    # 订舱没有客户名称
    customer_name = ""
    
    # 构建通知数据
    notification_data = {
        "id": str(booking.id),
        "task_type": "订舱",
        "source_table": "bookings",
        "airline": airline,
        "airline_name": airline_name,
        "flight_number": flight_number,
        "task_date": format_datetime_china(booking.booking_time) if booking.booking_time else None,
        "customer_name": customer_name,
        "quantity": str(quantity) if quantity else "",
        "weight": str(weight) if weight else "",
        "cargo_type": cargo_type
    }
    
    # 如果是异常任务，添加异常时间
    if is_exception:
        notification_data["exception_time"] = format_datetime_china(booking.updated_at)
    else:
        notification_data["exception_time"] = None
    
    return notification_data


@router.get("", summary="获取通知数据")
async def get_notifications(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取通知数据接口
    
    此接口用于小铃铛通知功能，返回待执行任务和异常任务的数据。
    
    **待执行任务**：
    - waybills表中 airline_record_status = "0"（未开单）的数据
    - bookings表中 booking_status = "0"（未执行）的数据
    
    **异常任务**：
    - waybills表中 airline_record_status = "2"（失败）的数据
    - bookings表中 booking_status = "2"（失败）的数据
    
    返回的任务详情包括：
    - 航空公司
    - 任务类型（开单/订舱）
    - 航班号
    - 开单或订舱日期
    - 客户名称（仅开单有，订舱为空）
    - 数量
    - 重量
    - 货物类型
    - 异常时间（仅异常任务有，取自 updated_at 字段）
    
    返回数据按创建时间倒序排列（最新的在前面）
    """
    # ============ 获取待执行任务 ============
    
    # 查询待执行的运单（airline_record_status = "0"）
    pending_waybills = db.query(Waybill).filter(
        Waybill.airline_record_status == "0"
    ).order_by(Waybill.created_at.desc()).all()
    
    # 查询待执行的订舱（booking_status = "0"）
    pending_bookings = db.query(Booking).filter(
        Booking.booking_status == "0"
    ).order_by(Booking.created_at.desc()).all()
    
    # 提取待执行任务的通知数据
    pending_tasks_list = []
    
    # 处理待执行运单
    for waybill in pending_waybills:
        notification_data = _extract_waybill_notification_data(waybill, is_exception=False)
        pending_tasks_list.append(notification_data)
    
    # 处理待执行订舱
    for booking in pending_bookings:
        notification_data = _extract_booking_notification_data(booking, is_exception=False)
        pending_tasks_list.append(notification_data)
    
    # ============ 获取异常任务 ============
    
    # 查询异常的运单（airline_record_status = "2"）
    exception_waybills = db.query(Waybill).filter(
        Waybill.airline_record_status == "2"
    ).order_by(Waybill.created_at.desc()).all()
    
    # 查询异常的订舱（booking_status = "2"）
    exception_bookings = db.query(Booking).filter(
        Booking.booking_status == "2"
    ).order_by(Booking.created_at.desc()).all()
    
    # 提取异常任务的通知数据
    exception_tasks_list = []
    
    # 处理异常运单
    for waybill in exception_waybills:
        notification_data = _extract_waybill_notification_data(waybill, is_exception=True)
        exception_tasks_list.append(notification_data)
    
    # 处理异常订舱
    for booking in exception_bookings:
        notification_data = _extract_booking_notification_data(booking, is_exception=True)
        exception_tasks_list.append(notification_data)
    
    # ============ 构建响应数据 ============
    response_data = {
        "pending_tasks": {
            "total": len(pending_tasks_list),
            "items": pending_tasks_list
        },
        "exception_tasks": {
            "total": len(exception_tasks_list),
            "items": exception_tasks_list
        }
    }
    
    return success_response(data=response_data, msg="查询成功")


@router.get("/summary", summary="获取通知数量摘要")
async def get_notification_summary(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取通知数量摘要接口
    
    此接口用于小铃铛显示未读数量，只返回待执行任务和异常任务的数量，不返回详细数据。
    
    返回：
    - pending_count: 待执行任务数量
    - exception_count: 异常任务数量
    - total_count: 总数量
    """
    # 统计待执行的运单数量
    pending_waybill_count = db.query(Waybill).filter(
        Waybill.airline_record_status == "0"
    ).count()
    
    # 统计待执行的订舱数量
    pending_booking_count = db.query(Booking).filter(
        Booking.booking_status == "0"
    ).count()
    
    # 统计异常的运单数量
    exception_waybill_count = db.query(Waybill).filter(
        Waybill.airline_record_status == "2"
    ).count()
    
    # 统计异常的订舱数量
    exception_booking_count = db.query(Booking).filter(
        Booking.booking_status == "2"
    ).count()
    
    # 计算总数
    pending_count = pending_waybill_count + pending_booking_count
    exception_count = exception_waybill_count + exception_booking_count
    total_count = pending_count + exception_count
    
    response_data = {
        "pending_count": pending_count,
        "exception_count": exception_count,
        "total_count": total_count
    }
    
    return success_response(data=response_data, msg="查询成功")


@router.delete("/cancel-task", summary="取消等待中的队列任务")
async def cancel_pending_task(
    id: str = Query(..., description="任务目标ID（waybill_id 或 booking_id）"),
    source_table: str = Query(..., description="来源表（waybills 或 bookings）"),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取消等待中的队列任务接口
    
    此接口用于取消通知列表中等待执行的任务。
    
    **参数说明**：
    - **id**: 任务目标ID，即通知接口返回的 id 字段（waybill_id 或 booking_id）
    - **source_table**: 来源表，即通知接口返回的 source_table 字段
      - "waybills": 运单（开单任务）
      - "bookings": 订舱（订舱任务）
    
    **执行逻辑**：
    1. 根据 source_table 确定目标类型（waybill/booking）
    2. 查找 rpa_tasks 表中对应的 pending 状态的任务
    3. 删除找到的任务
    
    **注意事项**：
    - 只能取消 pending（等待中）状态的任务
    - running（执行中）状态的任务无法取消
    - 如果没有找到等待中的任务，会返回提示信息
    
    返回：
    - deleted_count: 删除的任务数量
    - deleted_task_ids: 删除的任务ID列表
    """
    # 验证 source_table 参数
    if source_table not in ["waybills", "bookings"]:
        raise BadRequestException("source_table 参数无效，必须是 'waybills' 或 'bookings'")
    
    # 根据 source_table 确定 target_type
    # waybills -> waybill
    # bookings -> booking
    target_type = "waybill" if source_table == "waybills" else "booking"
    
    # 转换 id 为整数
    try:
        target_id = int(id)
    except ValueError:
        raise BadRequestException("id 参数无效，必须是数字")
    
    # 查找对应的 pending 状态的 RPA 任务
    pending_tasks = db.query(RPATask).filter(
        RPATask.target_type == target_type,
        RPATask.target_id == target_id,
        RPATask.status == RPATaskStatus.PENDING.value
    ).all()
    
    # 如果没有找到待执行的任务
    if not pending_tasks:
        # 检查是否有执行中的任务
        running_tasks = db.query(RPATask).filter(
            RPATask.target_type == target_type,
            RPATask.target_id == target_id,
            RPATask.status == RPATaskStatus.RUNNING.value
        ).all()
        
        if running_tasks:
            raise BadRequestException("该任务正在执行中，无法取消")
        
        return success_response(
            data={"deleted_count": 0, "deleted_task_ids": []},
            msg="没有找到等待中的队列任务"
        )
    
    # 删除找到的任务
    deleted_task_ids = []
    for task in pending_tasks:
        deleted_task_ids.append(str(task.id))
        db.delete(task)
    
    db.commit()
    
    return success_response(
        data={
            "deleted_count": len(deleted_task_ids),
            "deleted_task_ids": deleted_task_ids
        },
        msg=f"成功取消 {len(deleted_task_ids)} 个等待中的队列任务"
    )

