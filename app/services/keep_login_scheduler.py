"""
保持登录调度器（多机器人版）

作用：
1. 定期扫描所有启用的机器人
2. 对每台机器人，检查其 task_permissions 中的保持登录权限
3. 为有保持登录权限的机器人创建 RPATask（若当前没有 pending/running）
4. 使用机器人专属的 job_uuid（从 robot_jobs 表获取）
5. 设置 robot_id 使任务只能被对应机器人的 Worker 消费

注意：该调度流程不涉及机器人端队列数据（不创建/读取/删除RPA队列）。
"""

import json
import asyncio
import threading
import traceback
from typing import Any, Dict, Optional

from app.config import settings
from app.database import SessionLocal
from app.models.config import BusinessConfig
from app.models.robot import Robot, RobotJob
from app.models.rpa_task import RPATaskType
from app.services.rpa_task_service import rpa_task_service


KEEP_LOGIN_TARGET_TYPE = "keep_login"

# 保持登录任务类型到凭据配置路径的映射
KEEP_LOGIN_CONFIG_MAP = {
    RPATaskType.SHENZHEN_AIR_KEEP_LOGIN.value: {
        "config_path": ["shenzhen_air", "booking", "shenzhen_air_login"],
        "interval_attr": "RPA_SHENZHEN_AIR_KEEP_LOGIN_INTERVAL_SECONDS",
    },
    RPATaskType.CHINA_SOUTHERN_AIR_KEEP_LOGIN.value: {
        "config_path": ["china_southern_air", "booking_and_create", "china_southern_air_login"],
        "interval_attr": "RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_INTERVAL_SECONDS",
    },
    RPATaskType.TANGYI_KEEP_LOGIN.value: {
        "config_path": ["china_southern_air", "booking_and_create", "tangi_login"],
        "fallback_path": ["china_southern_air", "booking_and_create", "china_southern_air_login"],
        "interval_attr": "RPA_TANGYI_KEEP_LOGIN_INTERVAL_SECONDS",
    },
}


def _get_business_config_dict(db_session) -> Dict[str, Any]:
    """读取 BusinessConfig.config_data 并解析为 dict。"""
    config = db_session.query(BusinessConfig).first()
    if not config or not config.config_data:
        return {}
    try:
        return json.loads(config.config_data)
    except Exception:
        return {}


def _load_creds_from_path(business_config: Dict[str, Any], config_path: list, fallback_path: list = None) -> Dict[str, str]:
    """
    根据配置路径从 business_config 中读取凭据。
    支持 fallback_path 回退读取（用于唐翼兼容策略）。
    """
    node = business_config
    for key in config_path:
        node = node.get(key, {})
    
    system_account = node.get("system_account", "")
    login_password = node.get("login_password", "")
    
    # fallback：如果主路径没有凭据，尝试回退路径
    if (not system_account or not login_password) and fallback_path:
        fb_node = business_config
        for key in fallback_path:
            fb_node = fb_node.get(key, {})
        system_account = system_account or fb_node.get("system_account", "")
        login_password = login_password or fb_node.get("login_password", "")
    
    return {
        "system_account": system_account,
        "login_password": login_password,
    }


class KeepLoginScheduler:
    """
    全局保持登录调度器（多机器人版）
    
    工作流程：
    1. 每隔一定时间扫描所有启用的机器人
    2. 对每台机器人，检查其 task_permissions 中的保持登录类型
    3. 为每个匹配的 (机器人, 保持登录类型) 组合检查是否已有 pending/running 任务
    4. 若没有，则创建新任务，指定 robot_id 使其只被该机器人消费
    """

    def __init__(self):
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("[KeepLoginScheduler] 已启动保持登录调度器（多机器人版）")

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(self._async_main())
        finally:
            loop.close()

    async def _async_main(self) -> None:
        """主循环：定期扫描机器人并创建保持登录任务"""
        while not self._stop_event.is_set():
            if not settings.RPA_KEEP_LOGIN_ENABLED:
                await asyncio.sleep(10)
                continue

            try:
                await self._scan_and_enqueue()
            except Exception as e:
                print(f"[KeepLoginScheduler] 扫描创建保持登录任务失败: {repr(e)}\n{traceback.format_exc()}")

            # 使用最短的保持登录间隔作为扫描间隔
            scan_interval = self._get_min_interval()
            remaining = scan_interval
            while remaining > 0 and not self._stop_event.is_set():
                step = min(5, remaining)
                await asyncio.sleep(step)
                remaining -= step

    def _get_min_interval(self) -> int:
        """获取最短的保持登录间隔（用作扫描周期）"""
        intervals = []
        for cfg in KEEP_LOGIN_CONFIG_MAP.values():
            val = getattr(settings, cfg["interval_attr"], None)
            if val and val > 0:
                intervals.append(val)
        return min(intervals) if intervals else 60

    async def _scan_and_enqueue(self) -> None:
        """扫描所有启用机器人，为有保持登录权限的创建任务"""
        db = SessionLocal()
        try:
            business_config = _get_business_config_dict(db)
            robots = db.query(Robot).filter(Robot.status == 1).all()

            for robot in robots:
                try:
                    permissions = json.loads(robot.task_permissions) if robot.task_permissions else []
                except (json.JSONDecodeError, TypeError):
                    continue

                for task_type_value, cfg in KEEP_LOGIN_CONFIG_MAP.items():
                    if task_type_value not in permissions:
                        continue

                    # 检查间隔是否已配置
                    interval = getattr(settings, cfg["interval_attr"], None)
                    if not interval or interval <= 0:
                        continue

                    # 检查是否已有 pending/running 任务（使用 robot_id 作为 target_id 区分不同机器人）
                    existing = rpa_task_service.get_pending_task_for_target(
                        db,
                        target_type=KEEP_LOGIN_TARGET_TYPE,
                        target_id=robot.id,
                        task_type=task_type_value,
                    )
                    if existing:
                        continue

                    # 读取凭据
                    creds = _load_creds_from_path(
                        business_config,
                        cfg["config_path"],
                        cfg.get("fallback_path"),
                    )
                    if not creds.get("system_account") or not creds.get("login_password"):
                        print(
                            f"[KeepLoginScheduler] 缺少凭据: robot={robot.name}, task_type={task_type_value}"
                        )
                        continue

                    # 获取该机器人对应的 job_uuid
                    robot_job = db.query(RobotJob).filter(
                        RobotJob.robot_id == robot.id,
                        RobotJob.task_name == task_type_value,
                    ).first()
                    job_uuid = robot_job.job_uuid if robot_job else None

                    # 创建任务，指定 robot_id 使其只被该机器人的 Worker 消费
                    rpa_task_service.create_task(
                        db=db,
                        task_type=task_type_value,
                        target_type=KEEP_LOGIN_TARGET_TYPE,
                        target_id=robot.id,
                        params=creds,
                        job_uuid=job_uuid,
                        priority=2,  # 保持登录任务优先级高于普通业务任务
                        created_by=None,
                        robot_id=robot.id,  # 指定消费机器人
                    )
                    print(
                        f"[KeepLoginScheduler] 已创建保持登录任务: robot={robot.name}, task_type={task_type_value}, job_uuid={job_uuid}"
                    )

        except Exception as e:
            print(
                f"[KeepLoginScheduler] 扫描入队失败: error={repr(e)}\n{traceback.format_exc()}"
            )
            db.rollback()
        finally:
            db.close()

    def stop(self) -> None:
        self._stop_event.set()
        print("[KeepLoginScheduler] 已停止保持登录调度器")


# 全局单例
rpa_keep_login_scheduler = KeepLoginScheduler()
