"""
机器人任务同步与Job生成服务
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from app.models.robot import Robot, TaskProcess, RobotJob
from app.services.rpa_service import RPAService
from app.utils.robot_crypto import decrypt_robot_id
from app.utils.helpers import get_china_now

logger = logging.getLogger(__name__)
rpa_service = RPAService()

class RobotJobService:
    """机器人Job同步服务"""

    @staticmethod
    async def sync_robot_jobs(db: Session, robot: Robot):
        """
        根据机器人的任务权限同步生成 RPA Job
        """
        if not robot.task_permissions:
            return

        # 确保表中存在 bot_uuid 和 job_name 字段
        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE robot_jobs ADD COLUMN bot_uuid VARCHAR(100) NULL COMMENT '生成时使用的机器人UUID'"))
            db.commit()
        except Exception:
            db.rollback()

        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE robot_jobs ADD COLUMN job_name VARCHAR(200) NULL COMMENT '生成的RPA任务名称'"))
            db.commit()
        except Exception:
            db.rollback()

        try:
            permissions = json.loads(robot.task_permissions)
        except (json.JSONDecodeError, TypeError):
            logger.error(f"解析机器人权限失败: robot_id={robot.id}")
            return

        if not permissions:
            return

        # 解密机器人ID
        try:
            bot_uuid = decrypt_robot_id(robot.robot_id)
        except Exception as e:
            logger.error(f"解密机器人ID失败: robot_id={robot.id}, error={str(e)}")
            return

        # 获取所有流程配置
        processes = db.query(TaskProcess).filter(TaskProcess.task_name.in_(permissions)).all()
        process_map = {p.task_name: p for p in processes}

        # 获取已有的 Job 映射
        existing_jobs = db.query(RobotJob).filter(RobotJob.robot_id == robot.id).all()
        job_map = {j.task_name: j for j in existing_jobs}

        for task_name in permissions:
            process = process_map.get(task_name)
            if not process:
                logger.warning(f"未找到任务对应的流程配置: task_name={task_name}")
                continue

            existing_job = job_map.get(task_name)
            
            # 如果不存在，或者流程UUID已更新，或者绑定的物理机器人bot_uuid已发生变化，则重新生成
            if (not existing_job 
                or existing_job.process_detail_uuid != process.process_detail_uuid 
                or getattr(existing_job, "bot_uuid", None) != bot_uuid):
                await RobotJobService._create_or_update_job(db, robot, bot_uuid, process, existing_job)

    @staticmethod
    async def sync_all_robots_for_process(db: Session, task_name: str):
        """
        当某个流程详情更新时，同步所有拥有该权限的机器人
        """
        process = db.query(TaskProcess).filter(TaskProcess.task_name == task_name).first()
        if not process:
            return

        # 确保表中存在 bot_uuid 和 job_name 字段
        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE robot_jobs ADD COLUMN bot_uuid VARCHAR(100) NULL COMMENT '生成时使用的机器人UUID'"))
            db.commit()
        except Exception:
            db.rollback()

        try:
            from sqlalchemy import text
            db.execute(text("ALTER TABLE robot_jobs ADD COLUMN job_name VARCHAR(200) NULL COMMENT '生成的RPA任务名称'"))
            db.commit()
        except Exception:
            db.rollback()

        # 查找所有拥有此权限的机器人
        # 注意：task_permissions 存储为 JSON 字符串，使用 LIKE 匹配
        robots = db.query(Robot).filter(Robot.task_permissions.like(f'%"{task_name}"%')).all()
        
        for robot in robots:
            # 再次精确验证权限列表
            try:
                perms = json.loads(robot.task_permissions)
                if task_name not in perms:
                    continue
            except:
                continue

            # 解密机器人ID
            try:
                bot_uuid = decrypt_robot_id(robot.robot_id)
            except:
                continue

            existing_job = db.query(RobotJob).filter(
                RobotJob.robot_id == robot.id,
                RobotJob.task_name == task_name
            ).first()

            if (not existing_job 
                or existing_job.process_detail_uuid != process.process_detail_uuid 
                or getattr(existing_job, "bot_uuid", None) != bot_uuid):
                await RobotJobService._create_or_update_job(db, robot, bot_uuid, process, existing_job)

    @staticmethod
    async def _create_or_update_job(db: Session, robot: Robot, bot_uuid: str, process: TaskProcess, existing_job: Optional[RobotJob]):
        """内部方法：调用RPA接口并记录映射"""
        now_str = get_china_now().strftime("%Y_%m_%d_%H_%M_%S")
        name_prefix = process.chinese_name if process.chinese_name else process.task_name
        job_name = f"{name_prefix}_{bot_uuid}_{now_str}"
        
        input_param = {}
        if process.process_param:
            try:
                input_param = json.loads(process.process_param)
            except:
                pass

        try:
            result = await rpa_service.create_rpa_job(
                job_name=job_name,
                process_detail_uuid=process.process_detail_uuid,
                bot_uuid=bot_uuid,
                input_param=input_param
            )
            
            job_uuid = result.get("jobUUID")
            if not job_uuid:
                logger.error(f"RPA接口未返回jobUUID: task_name={process.task_name}")
                return

            if existing_job:
                existing_job.job_uuid = job_uuid
                existing_job.process_detail_uuid = process.process_detail_uuid
                existing_job.bot_uuid = bot_uuid
                existing_job.job_name = job_name
                existing_job.updated_at = get_china_now()
            else:
                new_job = RobotJob(
                    robot_id=robot.id,
                    task_name=process.task_name,
                    job_uuid=job_uuid,
                    process_detail_uuid=process.process_detail_uuid,
                    bot_uuid=bot_uuid,
                    job_name=job_name
                )
                db.add(new_job)
            
            db.commit()
            logger.info(f"生成/更新RobotJob成功: robot={robot.name}, task={process.task_name}, job_uuid={job_uuid}")
            
        except Exception as e:
            logger.error(f"生成RPA Job失败: robot={robot.name}, task={process.task_name}, error={str(e)}")

robot_job_service = RobotJobService()

