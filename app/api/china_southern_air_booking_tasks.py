"""Query API for persistent China Southern direct-booking tasks."""
import json

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.china_southern_air_booking_task import (
    ChinaSouthernAirBookingTask,
    ChinaSouthernAirBookingTaskStatus,
)
from app.utils.helpers import format_datetime_china

router = APIRouter()


def _task_data(task: ChinaSouthernAirBookingTask) -> dict:
    try:
        result = json.loads(task.result) if task.result else None
    except (TypeError, ValueError, json.JSONDecodeError):
        result = task.result
    try:
        details = json.loads(task.error_details) if task.error_details else None
    except (TypeError, ValueError, json.JSONDecodeError):
        details = task.error_details
    return {
        "id": str(task.id),
        "batch_id": str(task.batch_id),
        "booking_id": str(task.booking_id),
        "status": task.status,
        "priority": task.priority,
        "result": result,
        "error_message": task.error_message,
        "error_details": details,
        "created_by": str(task.created_by) if task.created_by else None,
        "created_at": format_datetime_china(task.created_at),
        "started_at": format_datetime_china(task.started_at) if task.started_at else None,
        "finished_at": format_datetime_china(task.finished_at) if task.finished_at else None,
    }


@router.get("/{task_id}", summary="查询南航直连订舱任务")
async def get_booking_task(task_id: str, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    try:
        task = db.query(ChinaSouthernAirBookingTask).filter(ChinaSouthernAirBookingTask.id == int(task_id)).first()
    except (TypeError, ValueError):
        task = None
    if not task:
        raise NotFoundException("南航直连订舱任务不存在")
    return success_response(data=_task_data(task), msg="查询成功")


@router.get("", summary="查询南航直连订舱任务列表")
async def get_booking_tasks(
    batch_id: str = Query(None, description="批量执行批次ID"),
    booking_id: str = Query(None, description="订舱ID"),
    status: str = Query(None, description="任务状态（pending/running/success/failed）"),
    page: int = Query(1, ge=1),
    pageSize: int = Query(10, ge=1, le=200),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        batch_value = int(batch_id) if batch_id else None
        booking_value = int(booking_id) if booking_id else None
    except (TypeError, ValueError):
        raise BadRequestException("batch_id和booking_id必须是数字")
    query = db.query(ChinaSouthernAirBookingTask)
    if batch_value:
        query = query.filter(ChinaSouthernAirBookingTask.batch_id == batch_value)
    if booking_value:
        query = query.filter(ChinaSouthernAirBookingTask.booking_id == booking_value)
    if status:
        valid = {ChinaSouthernAirBookingTaskStatus.PENDING, ChinaSouthernAirBookingTaskStatus.RUNNING, ChinaSouthernAirBookingTaskStatus.SUCCESS, ChinaSouthernAirBookingTaskStatus.FAILED}
        if status not in valid:
            raise BadRequestException("任务状态无效")
        query = query.filter(ChinaSouthernAirBookingTask.status == status)
    total = query.count()
    tasks = query.order_by(ChinaSouthernAirBookingTask.created_at.desc()).offset((page - 1) * pageSize).limit(pageSize).all()
    return success_response(data={"total": total, "page": page, "pageSize": pageSize, "list": [_task_data(t) for t in tasks]}, msg="查询成功")
