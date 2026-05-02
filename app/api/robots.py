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
from app.models.robot import Robot
from app.models.rpa_task import RPATaskType
from app.schemas.robot import RobotCreateOrUpdate, RobotListQuery
from app.api.deps import require_permission
from app.utils.helpers import format_datetime_china
from app.utils.robot_crypto import decrypt_robot_id

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

        logger.info("修改机器人成功: id=%s, name=%s", robot.id, robot.name)
        return success_response(data=_format_robot_response(robot), msg="机器人修改成功")

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

        logger.info("新增机器人成功: id=%s, name=%s", robot.id, robot.name)
        return success_response(data=_format_robot_response(robot), msg="机器人新增成功")


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

    robot_list = [_format_robot_response(r) for r in robots]

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
        "DOCUMENT_PRINT": "单据打印",
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


# ======================== 响应格式化工具 ========================

def _format_robot_response(robot: Robot) -> dict:
    """格式化机器人响应数据"""
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

    return {
        "id": str(robot.id),
        "robot_id": robot.robot_id,
        "name": robot.name,
        "location": robot.location,
        "task_permissions": task_permissions,
        "extra_config": extra_config,
        "status": robot.status,
        "created_at": format_datetime_china(robot.created_at),
        "updated_at": format_datetime_china(robot.updated_at),
    }
