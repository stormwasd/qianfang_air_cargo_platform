"""
机器人任务同步与Job生成服务
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session
from app.models.robot import Robot, TaskProcess, RobotJob, RobotQueue
from app.services.rpa_service import RPAService
from app.services.rpa_task_service import TASK_QUEUE_CONFIGS
from app.utils.robot_crypto import decrypt_robot_id
from app.utils.helpers import get_china_now
from app.utils.snowflake import generate_id

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
        
        # 同步队列配置
        RobotJobService._sync_robot_queues(db, robot, permissions)

    @staticmethod
    def _sync_robot_queues(db: Session, robot: Robot, permissions: list):
        """
        根据机器人的任务权限，自动生成专属队列名称并存入 robot_queues 表。
        
        命名规则: {task_name_lower}_queue_{queue_key}_{robot_db_id}
        示例: shenzhen_air_waybill_execute_queue_waybill_number_310680091942326272
        """
        # 获取已有的队列配置
        existing_queues = db.query(RobotQueue).filter(RobotQueue.robot_id == robot.id).all()
        existing_map = {(q.task_name, q.queue_key): q for q in existing_queues}
        
        for task_name in permissions:
            queue_keys = TASK_QUEUE_CONFIGS.get(task_name)
            if not queue_keys:
                # 该任务类型不需要队列
                continue
            
            for queue_key in queue_keys:
                lookup = (task_name, queue_key)
                if lookup in existing_map:
                    # 已存在，跳过
                    continue
                
                # 生成全局唯一的队列名称
                queue_name = f"{task_name.lower()}_queue_{queue_key}_{robot.id}"
                
                new_queue = RobotQueue(
                    id=generate_id(),
                    robot_id=robot.id,
                    task_name=task_name,
                    queue_key=queue_key,
                    queue_name=queue_name
                )
                db.add(new_queue)
                logger.info(f"生成队列配置: robot={robot.name}, task={task_name}, key={queue_key}, name={queue_name}")
        
        db.commit()

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
        robots = db.query(Robot).filter(Robot.task_permissions.like(f'%"{task_name}"%')).all()
        
        for robot in robots:
            try:
                perms = json.loads(robot.task_permissions)
                if task_name not in perms:
                    continue
            except:
                continue

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
            
            # 同步队列配置
            RobotJobService._sync_robot_queues(db, robot, perms)

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

    @staticmethod
    async def cleanup_robot(db: Session, robot: Robot):
        """
        清理机器人关联的所有资源：
        1. 远程调用 RPA 接口逐个删除 robot_jobs 中的 Job
        2. 删除本地 robot_jobs 记录
        3. 删除本地 robot_queues 记录
        
        注意：此方法不删除 robots 表本身的记录，由调用方负责。
        """
        import asyncio
        
        # 1. 获取该机器人所有的 Job 映射
        jobs = db.query(RobotJob).filter(RobotJob.robot_id == robot.id).all()
        
        if jobs:
            # 并发调用 RPA 删除接口（加速删除）
            job_uuids = [j.job_uuid for j in jobs]
            results = await RobotJobService._delete_remote_jobs(job_uuids)
            
            success_count = sum(1 for r in results if r)
            logger.info(f"远程删除RPA Job: robot={robot.name}, 总数={len(job_uuids)}, 成功={success_count}")
            
            # 删除本地 robot_jobs 记录
            db.query(RobotJob).filter(RobotJob.robot_id == robot.id).delete(synchronize_session=False)
        
        # 2. 删除本地 robot_queues 记录
        db.query(RobotQueue).filter(RobotQueue.robot_id == robot.id).delete(synchronize_session=False)
        
        db.commit()
        logger.info(f"清理机器人关联资源完成: robot={robot.name}, id={robot.id}")
    
    @staticmethod
    async def _delete_remote_jobs(job_uuids: list) -> list:
        """
        并发删除多个远程 RPA Job（不因单个失败而中断）
        
        Args:
            job_uuids: 待删除的 job_uuid 列表
        
        Returns:
            每个删除操作的结果（True/False）
        """
        import asyncio
        
        async def _delete_one(job_uuid: str) -> bool:
            try:
                return await rpa_service.delete_rpa_job(job_uuid)
            except Exception as e:
                logger.error(f"远程删除RPA Job异常: job_uuid={job_uuid}, error={repr(e)}")
                return False
        
        # 并发执行所有删除请求
        tasks = [_delete_one(uuid) for uuid in job_uuids]
        return await asyncio.gather(*tasks)

robot_job_service = RobotJobService()
