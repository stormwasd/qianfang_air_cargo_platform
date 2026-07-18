"""
机器人管理接口
包含：新增或修改机器人、机器人列表、任务权限列表
"""
import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException, ConflictException
from app.core.response import success_response
from app.database import get_db
from app.models.robot import Robot, TaskProcess, RobotJob, RobotQueue
from app.models.rpa_task import RPATaskType
from app.schemas.robot import RobotCreateOrUpdate, RobotListQuery, TaskProcessCreateUpdate, TaskProcessResponse
from app.api.deps import require_permission
from app.utils.helpers import format_datetime_china
from app.utils.robot_crypto import decrypt_robot_id
from app.services.robot_job_service import robot_job_service

logger = logging.getLogger(__name__)

router = APIRouter()



@router.post("", summary="新增或修改机器人")
async def create_or_update_robot(
    payload: RobotCreateOrUpdate,
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """
    新增或修改机器人接口（需要robot权限或管理员权限）

    通过是否传入 `id` 字段区分新增和修改：
    - 不传 `id`：新增机器人
    - 传入 `id`：修改已有机器人

    参数说明：
    - **id**: 机器人记录ID（可选，传入则为修改操作）
    - **robot_id**: 机器人ID（加密后的字符串，使用 robot_id_encrypt_tool.py 生成）
    - **name**: 机器人名称
    - **location**: 机器人所在位置
    - **location_required**: 是否启用location区域限制（可选，1=开启，0=关闭，默认1）
    - **task_permissions**: 可执行任务权限列表（如 ["SHENZHEN_AIR_WAYBILL_EXECUTE", "FILE_PRINT"]）
    - **extra_config**: 机器人其他配置（可选，包含深航账号密码、打印机服务、唐翼程序地址）
    - **status**: 机器人状态（可选，1=启用，0=未启用，默认1）
    """
    try:
        decrypt_robot_id(payload.robot_id)
    except ValueError:
        raise BadRequestException("机器人ID无效，请使用加密工具生成正确的机器人ID")

    extra_config_json = None
    if payload.extra_config:
        extra_config_json = json.dumps(
            payload.extra_config.model_dump(exclude_none=False),
            ensure_ascii=False,
        )

    task_permissions_json = json.dumps(payload.task_permissions, ensure_ascii=False)

    if payload.id:
        robot = db.query(Robot).filter(Robot.id == int(payload.id)).first()
        if not robot:
            raise NotFoundException("机器人记录不存在")

        if payload.robot_id != robot.robot_id:
            existing = db.query(Robot).filter(
                Robot.robot_id == payload.robot_id,
                Robot.id != int(payload.id),
            ).first()
            if existing:
                raise ConflictException("该机器人ID已被其他机器人使用")

        await robot_job_service.cleanup_robot(db, robot)

        robot.robot_id = payload.robot_id
        robot.name = payload.name
        robot.location = payload.location
        if payload.location_required is not None:
            robot.location_required = payload.location_required
        robot.task_permissions = task_permissions_json
        robot.extra_config = extra_config_json
        if payload.status is not None:
            robot.status = payload.status

        db.commit()
        db.refresh(robot)

        await robot_job_service.sync_robot_jobs(db, robot)

        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.sync_workers()

        logger.info("修改机器人成功: id=%s, name=%s", robot.id, robot.name)
        return success_response(data=_format_robot_response(robot, db), msg="机器人修改成功")

    else:
        existing = db.query(Robot).filter(Robot.robot_id == payload.robot_id).first()
        if existing:
            raise ConflictException("该机器人ID已存在")

        robot = Robot(
            robot_id=payload.robot_id,
            name=payload.name,
            location=payload.location,
            location_required=payload.location_required if payload.location_required is not None else 1,
            task_permissions=task_permissions_json,
            extra_config=extra_config_json,
            status=payload.status if payload.status is not None else 1,
        )
        db.add(robot)
        db.commit()
        db.refresh(robot)

        await robot_job_service.sync_robot_jobs(db, robot)

        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.sync_workers()

        logger.info("新增机器人成功: id=%s, name=%s", robot.id, robot.name)
        return success_response(data=_format_robot_response(robot, db), msg="机器人新增成功")


@router.get("", summary="机器人列表")
async def get_robots(
    query: RobotListQuery = Depends(),
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """
    获取机器人列表（需要robot权限或管理员权限）

    参数说明：
    - **status**: 机器人状态筛选（可选，0=未启用，1=启用）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    """
    query_obj = db.query(Robot)

    if query.status is not None:
        query_obj = query_obj.filter(Robot.status == query.status)

    total = query_obj.count()

    offset = (query.page - 1) * query.pageSize
    robots = query_obj.order_by(
        Robot.created_at.desc(), Robot.id.desc()
    ).offset(offset).limit(query.pageSize).all()

    robot_list = [_format_robot_response(r, db) for r in robots]

    return success_response(
        data={"total": total, "items": robot_list},
        msg="查询成功",
    )


@router.get("/task-types", summary="任务权限列表")
async def get_task_types(
    current_user=Depends(require_permission("robot")),
):
    """
    获取可分配的任务权限类型列表（需要robot权限或管理员权限）

    返回 rpa_tasks 表中 RPATaskType 枚举的所有任务类型及其中文描述。
    前端在配置机器人可执行任务权限时使用此接口获取可选项。
    """
    task_type_descriptions = {
        "SHENZHEN_AIR_WAYBILL_EXECUTE": "深航开单",
        "SHENZHEN_AIR_WAYBILL_VOID": "深航作废",
        "SHENZHEN_AIR_BILLING_TIME_CONTAINER": "深航计飞时间-集装器数据获取",
        "SHENZHEN_AIR_TRANSIT_LOADING": "深航过机-装机数据获取",
        "SHENZHEN_AIR_APPROVAL_DATA": "深航订舱-批复数据获取",
        "SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY": "深航订舱-批复数据获取-宽体",
        "CHINA_SOUTHERN_AIR_BOOKING_EXECUTE": "南航订舱",
        "CHINA_SOUTHERN_AIR_BOOKING_CANCEL": "南航退舱",
        "CHINA_SOUTHERN_AIR_DIRECT_INVOICE": "南航直接开单",
        "CHINA_SOUTHERN_AIR_WAYBILL_VOID": "南航作废",
        "CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE": "南航新增运单",
        "CHINA_SOUTHERN_AIR_APPROVAL_DATA": "南航订舱-批复数据获取",
        "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA": "南航修改数据后开单",
        "FILE_PRINT": "制单文件打印",
        "SHENZHEN_AIR_MAIN_WAYBILL_PRINT": "深航货运主单打印",
        "CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT": "南航货运主单打印",
        "CHINA_SOUTHERN_AIR_SECURITY_PRINT": "南航货运安检申报单打印",
        "CHINA_SOUTHERN_AIR_LABEL_PRINT": "南航标签单打印",
        "CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING": "南航订舱-本站货物+货拉数据获取",
        "SHENZHEN_AIR_KEEP_LOGIN": "深航保持登录",
        "CHINA_SOUTHERN_AIR_KEEP_LOGIN": "南航保持登录",
        "TANGYI_KEEP_LOGIN": "唐翼保持登录",
    }

    task_types = []
    for task_type in RPATaskType:
        task_types.append({
            "value": task_type.value,
            "label": task_type.value,
            "description": task_type_descriptions.get(task_type.value, task_type.value),
        })

    return success_response(data=task_types, msg="查询成功")



@router.get("/task-processes", summary="获取所有任务流程配置")
async def get_task_processes(
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """获取所有任务流程配置列表"""
    processes = db.query(TaskProcess).order_by(TaskProcess.task_name.asc()).all()
    return success_response(data=[_format_task_process_response(p) for p in processes])


@router.post("/task-processes", summary="维护任务流程配置")
async def create_or_update_task_process(
    payload: TaskProcessCreateUpdate,
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """
    新增或修改任务流程配置。
    如果 `process_detail_uuid` 发生变化，会自动触发所有关联机器人的 Job 重建。
    """
    process = db.query(TaskProcess).filter(TaskProcess.task_name == payload.task_name).first()
    
    param_json = json.dumps(payload.process_param, ensure_ascii=False) if payload.process_param else None
    uuid_changed = False
    
    if process:
        if process.process_detail_uuid != payload.process_detail_uuid:
            uuid_changed = True
            
        process.chinese_name = payload.chinese_name
        process.process_detail_uuid = payload.process_detail_uuid
        process.version = payload.version
        process.process_param = param_json
        db.commit()
        db.refresh(process)
        msg = "任务流程配置更新成功"
    else:
        process = TaskProcess(
            task_name=payload.task_name,
            chinese_name=payload.chinese_name,
            process_detail_uuid=payload.process_detail_uuid,
            version=payload.version,
            process_param=param_json
        )
        db.add(process)
        db.commit()
        db.refresh(process)
        msg = "任务流程配置新增成功"
        uuid_changed = True 

    if uuid_changed:
        logger.info(f"任务流程 UUID 发生变化，触发机器人 Job 重建: task_name={payload.task_name}")
        await robot_job_service.sync_all_robots_for_process(db, payload.task_name)

    return success_response(data=_format_task_process_response(process), msg=msg)


@router.delete("/task-processes/{task_name}", summary="删除任务流程配置")
async def delete_task_process(
    task_name: str,
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """删除任务流程配置"""
    process = db.query(TaskProcess).filter(TaskProcess.task_name == task_name).first()
    if not process:
        raise NotFoundException("任务流程配置不存在")
    
    db.delete(process)
    db.commit()
    return success_response(msg="删除成功")


@router.get("/{robot_id}", summary="机器人详情")
async def get_robot_detail(
    robot_id: str,
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """
    获取机器人详情
    """
    try:
        robot_id_int = int(robot_id)
    except ValueError:
        raise BadRequestException("机器人ID格式错误")

    robot = db.query(Robot).filter(Robot.id == robot_id_int).first()
    if not robot:
        raise NotFoundException("机器人不存在")

    return success_response(data=_format_robot_response(robot, db), msg="查询成功")


@router.delete("/{robot_id}", summary="删除机器人")
async def delete_robot(
    robot_id: str,
    current_user=Depends(require_permission("robot")),
    db: Session = Depends(get_db),
):
    """
    删除机器人（需要robot权限或管理员权限）
    
    删除流程：
    1. 远程调用 RPA 接口删除该机器人的所有 Job
    2. 删除本地 robot_jobs 记录
    3. 删除本地 robot_queues 记录
    4. 删除 robots 表记录
    5. 停止对应的 Worker 线程
    """
    try:
        robot_id_int = int(robot_id)
    except ValueError:
        raise BadRequestException("机器人ID格式错误")

    robot = db.query(Robot).filter(Robot.id == robot_id_int).first()
    if not robot:
        raise NotFoundException("机器人不存在")

    robot_name = robot.name

    await robot_job_service.cleanup_robot(db, robot)

    db.delete(robot)
    db.commit()

    from app.services.rpa_worker import rpa_worker_manager
    rpa_worker_manager.sync_workers()

    logger.info("删除机器人成功: id=%s, name=%s", robot_id_int, robot_name)
    return success_response(msg=f"机器人 {robot_name} 删除成功")




def _format_robot_response(robot: Robot, db: Session) -> dict:
    """格式化机器人响应数据，包含每个任务对应的 jobUUID"""
    task_permissions = []
    if robot.task_permissions:
        try:
            task_permissions = json.loads(robot.task_permissions)
        except (json.JSONDecodeError, TypeError):
            task_permissions = []

    extra_config = None
    if robot.extra_config:
        try:
            extra_config = json.loads(robot.extra_config)
        except (json.JSONDecodeError, TypeError):
            extra_config = None

    jobs = db.query(RobotJob).filter(RobotJob.robot_id == robot.id).all()
    job_mapping = {j.task_name: j.job_uuid for j in jobs}
    job_name_mapping = {j.task_name: j.job_name for j in jobs if j.job_name}

    queues = db.query(RobotQueue).filter(RobotQueue.robot_id == robot.id).all()
    queue_mapping = {}
    for q in queues:
        if q.task_name not in queue_mapping:
            queue_mapping[q.task_name] = {}
        queue_mapping[q.task_name][q.queue_key] = q.queue_name

    return {
        "id": str(robot.id),
        "robot_id": robot.robot_id,
        "name": robot.name,
        "location": robot.location,
        "location_required": robot.location_required,
        "task_permissions": task_permissions,
        "job_mapping": job_mapping, 
        "job_name_mapping": job_name_mapping, 
        "queue_mapping": queue_mapping, 
        "extra_config": extra_config,
        "status": robot.status,
        "created_at": format_datetime_china(robot.created_at),
        "updated_at": format_datetime_china(robot.updated_at),
    }


def _format_task_process_response(process: TaskProcess) -> dict:
    """格式化任务流程响应"""
    param = None
    if process.process_param:
        try:
            param = json.loads(process.process_param)
        except:
            param = None
            
    return {
        "id": str(process.id),
        "task_name": process.task_name,
        "chinese_name": process.chinese_name,
        "process_detail_uuid": process.process_detail_uuid,
        "version": process.version,
        "process_param": param,
        "created_at": format_datetime_china(process.created_at),
        "updated_at": format_datetime_china(process.updated_at),
    }
