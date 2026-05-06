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
from app.models.robot import Robot, TaskProcess, RobotJob
from app.models.rpa_task import RPATaskType
from app.schemas.robot import RobotCreateOrUpdate, RobotListQuery, TaskProcessCreateUpdate, TaskProcessResponse
from app.api.deps import require_permission
from app.utils.helpers import format_datetime_china
from app.utils.robot_crypto import decrypt_robot_id
from app.services.robot_job_service import robot_job_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================== 接口实现 ========================

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
    - **task_permissions**: 可执行任务权限列表（如 ["SHENZHEN_AIR_WAYBILL_EXECUTE", "DOCUMENT_PRINT"]）
    - **extra_config**: 机器人其他配置（可选，包含深航账号密码、打印机服务、唐翼程序地址）
    - **status**: 机器人状态（可选，1=启用，0=未启用，默认1）
    """
    # 验证加密的robot_id是否可解密（确保是合法的加密ID）
    try:
        decrypt_robot_id(payload.robot_id)
    except ValueError:
        raise BadRequestException("机器人ID无效，请使用加密工具生成正确的机器人ID")

    # 序列化 extra_config
    extra_config_json = None
    if payload.extra_config:
        extra_config_json = json.dumps(
            payload.extra_config.model_dump(exclude_none=False),
            ensure_ascii=False,
        )

    # 序列化 task_permissions
    task_permissions_json = json.dumps(payload.task_permissions, ensure_ascii=False)

    if payload.id:
        # ========== 修改模式 ==========
        robot = db.query(Robot).filter(Robot.id == int(payload.id)).first()
        if not robot:
            raise NotFoundException("机器人记录不存在")

        # 如果修改了 robot_id，检查唯一性
        if payload.robot_id != robot.robot_id:
            existing = db.query(Robot).filter(
                Robot.robot_id == payload.robot_id,
                Robot.id != int(payload.id),
            ).first()
            if existing:
                raise ConflictException("该机器人ID已被其他机器人使用")

        # 更新字段
        robot.robot_id = payload.robot_id
        robot.name = payload.name
        robot.location = payload.location
        robot.task_permissions = task_permissions_json
        robot.extra_config = extra_config_json
        if payload.status is not None:
            robot.status = payload.status

        db.commit()
        db.refresh(robot)

        # 异步/后台同步生成 RPA Job（这里先简单同步执行，后续可考虑使用 BackgroundTasks）
        await robot_job_service.sync_robot_jobs(db, robot)

        logger.info("修改机器人成功: id=%s, name=%s", robot.id, robot.name)
        return success_response(data=_format_robot_response(robot, db), msg="机器人修改成功")

    else:
        # ========== 新增模式 ==========
        # 检查 robot_id 唯一性
        existing = db.query(Robot).filter(Robot.robot_id == payload.robot_id).first()
        if existing:
            raise ConflictException("该机器人ID已存在")

        robot = Robot(
            robot_id=payload.robot_id,
            name=payload.name,
            location=payload.location,
            task_permissions=task_permissions_json,
            extra_config=extra_config_json,
            status=payload.status if payload.status is not None else 1,
        )
        db.add(robot)
        db.commit()
        db.refresh(robot)

        # 异步/后台同步生成 RPA Job
        await robot_job_service.sync_robot_jobs(db, robot)

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
    - **pageSize**: 每页数量（默认10，最大100）
    """
    query_obj = db.query(Robot)

    # 状态筛选
    if query.status is not None:
        query_obj = query_obj.filter(Robot.status == query.status)

    # 总数
    total = query_obj.count()

    # 分页（按创建时间倒序）
    offset = (query.page - 1) * query.page_size
    robots = query_obj.order_by(
        Robot.created_at.desc()
    ).offset(offset).limit(query.page_size).all()

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
    # 任务类型中文描述映射
    task_type_descriptions = {
        "SHENZHEN_AIR_WAYBILL_EXECUTE": "深航开单",
        "SHENZHEN_AIR_WAYBILL_VOID": "深航作废",
        "CHINA_SOUTHERN_AIR_BOOKING_EXECUTE": "南航订舱",
        "CHINA_SOUTHERN_AIR_BOOKING_CANCEL": "南航退舱",
        "CHINA_SOUTHERN_AIR_DIRECT_INVOICE": "南航直接开单",
        "CHINA_SOUTHERN_AIR_WAYBILL_VOID": "南航作废",
        "CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE": "南航新增运单",
        "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA": "南航修改数据后开单",
        "FILE_PRINT": "制单文件打印",
        "SHENZHEN_AIR_MAIN_WAYBILL_PRINT": "深航货运主单打印",
        "CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT": "南航货运主单打印",
        "CHINA_SOUTHERN_AIR_SECURITY_PRINT": "南航货运安检申报单打印",
        "CHINA_SOUTHERN_AIR_LABEL_PRINT": "南航标签单打印",
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


# ======================== 任务流程配置管理 (TaskProcess) ========================

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
        # 检查 UUID 是否变化
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
        uuid_changed = True # 新增也视为变化，触发初始同步（虽然新流程可能还没机器人关联）

    # 如果 UUID 变化，同步所有机器人
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



# ======================== 响应格式化工具 ========================

def _format_robot_response(robot: Robot, db: Session) -> dict:
    """格式化机器人响应数据，包含每个任务对应的 jobUUID"""
    # 解析 task_permissions
    task_permissions = []
    if robot.task_permissions:
        try:
            task_permissions = json.loads(robot.task_permissions)
        except (json.JSONDecodeError, TypeError):
            task_permissions = []

    # 解析 extra_config
    extra_config = None
    if robot.extra_config:
        try:
            extra_config = json.loads(robot.extra_config)
        except (json.JSONDecodeError, TypeError):
            extra_config = None

    # 获取 Job 映射
    jobs = db.query(RobotJob).filter(RobotJob.robot_id == robot.id).all()
    job_mapping = {j.task_name: j.job_uuid for j in jobs}

    return {
        "id": str(robot.id),
        "robot_id": robot.robot_id,
        "name": robot.name,
        "location": robot.location,
        "task_permissions": task_permissions,
        "job_mapping": job_mapping, # 返回 task_name -> jobUUID 的映射
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
