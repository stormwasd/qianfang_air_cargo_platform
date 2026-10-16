"""
RPA任务队列API接口
"""
import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.core.response import success_response
from app.core.exceptions import NotFoundException
from app.database import get_db
from app.models.rpa_task import RPATask, RPATaskStatus
from app.models.waybill import ShenzhenAirDirectWaybillTask
from app.services.rpa_task_service import rpa_task_service
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

router = APIRouter()


@router.get("/{task_id}", summary="查询RPA或深航直连开单任务状态")
async def get_task_status(
    task_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询单个RPA或深航直连开单任务的状态
    
    - **task_id**: 任务ID（字符串格式）
    
    返回任务的详细信息，包括：
    - 任务状态（pending/running/success/failed/timeout；深航直连另有unknown待核查状态）
    - 目标类型和ID
    - RPA workUuid
    - 创建时间、开始时间、完成时间
    """
    try:
        parsed_task_id = int(task_id)
    except (TypeError, ValueError):
        raise NotFoundException("任务不存在")
    task = rpa_task_service.get_task_by_id(db, parsed_task_id)
    if not task:
        direct_task = db.query(ShenzhenAirDirectWaybillTask).filter(
            ShenzhenAirDirectWaybillTask.id == parsed_task_id
        ).first()
        if not direct_task:
            raise NotFoundException("任务不存在或已完成")
        try:
            direct_result = json.loads(direct_task.result) if direct_task.result else None
        except (TypeError, json.JSONDecodeError):
            direct_result = direct_task.result
        return success_response(data={
            "id": str(direct_task.id), "task_type": "SHENZHEN_AIR_WAYBILL_EXECUTE",
            "target_type": "waybill", "target_id": str(direct_task.waybill_id),
            "status": direct_task.status, "priority": direct_task.priority,
            "work_uuid": None, "job_uuid": None, "result": direct_result,
            "error_message": direct_task.error_message,
            "created_by": str(direct_task.created_by) if direct_task.created_by else None,
            "created_at": format_datetime_china(direct_task.created_at),
            "started_at": format_datetime_china(direct_task.started_at) if direct_task.started_at else None,
            "finished_at": format_datetime_china(direct_task.finished_at) if direct_task.finished_at else None,
            "execution_mode": "direct",
            "stage": direct_task.stage,
            "candidate_waybill_number": direct_task.candidate_waybill_number,
        }, msg="查询成功")
    
    result_data = None
    if task.result:
        try:
            result_data = json.loads(task.result)
        except:
            result_data = task.result
    
    task_data = {
        "id": str(task.id),
        "task_type": task.task_type,
        "target_type": task.target_type,
        "target_id": str(task.target_id),
        "status": task.status,
        "priority": task.priority,
        "work_uuid": task.work_uuid,
        "job_uuid": task.job_uuid,
        "result": result_data,
        "error_message": task.error_message,
        "created_by": str(task.created_by) if task.created_by else None,
        "created_at": format_datetime_china(task.created_at),
        "started_at": format_datetime_china(task.started_at) if task.started_at else None,
        "finished_at": format_datetime_china(task.finished_at) if task.finished_at else None
    }
    
    return success_response(data=task_data, msg="查询成功")


@router.get("", summary="查询RPA任务列表")
async def get_tasks(
    task_type: str = Query(None, description="任务类型"),
    target_type: str = Query(None, description="目标类型（waybill/booking）"),
    target_id: str = Query(None, description="目标ID"),
    status: str = Query(None, description="任务状态（pending/running/success/failed/timeout）"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(10, ge=1, le=200, description="每页数量"),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    分页查询RPA任务列表
    
    查询参数：
    - **task_type**: 任务类型（可选）
    - **target_type**: 目标类型（可选，waybill/booking）
    - **target_id**: 目标ID（可选）
    - **status**: 任务状态（可选，pending/running/success/failed/timeout）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    """
    try:
        parsed_target_id = int(target_id) if target_id else None
    except (TypeError, ValueError):
        from app.core.exceptions import BadRequestException
        raise BadRequestException("target_id必须是数字")

    result = rpa_task_service.get_tasks_list(
        db=db,
        task_type=task_type,
        target_type=target_type,
        target_id=parsed_target_id,
        status=status,
        page=page,
        pageSize=pageSize
    )
    
    tasks_data = []
    for task in result["items"]:
        result_data = None
        if task.result:
            try:
                result_data = json.loads(task.result)
            except:
                result_data = task.result
        
        tasks_data.append({
            "id": str(task.id),
            "task_type": task.task_type,
            "target_type": task.target_type,
            "target_id": str(task.target_id),
            "status": task.status,
            "priority": task.priority,
            "work_uuid": task.work_uuid,
            "error_message": task.error_message,
            "created_at": format_datetime_china(task.created_at),
            "started_at": format_datetime_china(task.started_at) if task.started_at else None,
            "finished_at": format_datetime_china(task.finished_at) if task.finished_at else None
        })
    
    return success_response(
        data={
            "total": result["total"],
            "page": result["page"],
            "pageSize": result["pageSize"],
            "list": tasks_data
        },
        msg="查询成功"
    )


@router.get("/stats/queue", summary="获取队列统计信息")
async def get_queue_stats(
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取RPA任务队列的统计信息
    
    返回：
    - pending_count: 待执行任务数
    - running_count: 执行中任务数
    - worker_count: Worker数量
    - queue_enabled: 队列是否启用
    """
    stats = rpa_task_service.get_queue_stats(db)
    
    return success_response(data=stats, msg="查询成功")


@router.delete("/{task_id}", summary="取消/删除RPA任务")
async def delete_task(
    task_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    取消或删除RPA任务
    
    - **task_id**: 任务ID（字符串格式）
    
    注意：只能删除pending状态的任务，running状态的任务无法取消
    """
    task = rpa_task_service.get_task_by_id(db, int(task_id))
    if not task:
        raise NotFoundException("任务不存在")
    
    if task.status == RPATaskStatus.RUNNING.value:
        from app.core.exceptions import BadRequestException
        raise BadRequestException("执行中的任务无法取消")
    
    rpa_task_service.delete_task(db, int(task_id))
    
    return success_response(data=None, msg="任务已删除")

