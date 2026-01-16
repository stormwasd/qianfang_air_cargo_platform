"""
RPA任务队列服务
管理RPA任务的创建、查询、更新和删除
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.rpa_task import RPATask, RPATaskStatus, RPATaskType, RPATargetType
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
from app.config import settings


class RPATaskService:
    """RPA任务队列服务类"""
    
    def create_task(
        self,
        db: Session,
        task_type: str,
        target_type: str,
        target_id: int,
        params: Dict[str, Any],
        queue_params: Optional[Dict[str, Any]] = None,
        job_uuid: Optional[str] = None,
        priority: Optional[int] = None,
        created_by: Optional[int] = None
    ) -> RPATask:
        """
        创建RPA任务
        
        Args:
            db: 数据库会话
            task_type: 任务类型
            target_type: 目标类型（waybill/booking）
            target_id: 目标ID
            params: RPA调用参数
            queue_params: 队列参数（用于创建RPA数据队列）
            job_uuid: RPA的jobUuid
            priority: 优先级（不传则使用配置文件默认值）
            created_by: 创建用户ID
        
        Returns:
            创建的任务对象
        """
        # 使用配置文件中的默认优先级
        if priority is None:
            priority = settings.RPA_QUEUE_DEFAULT_PRIORITY
        
        task = RPATask(
            id=generate_id(),
            task_type=task_type,
            target_type=target_type,
            target_id=target_id,
            params=json.dumps(params, ensure_ascii=False),
            queue_params=json.dumps(queue_params, ensure_ascii=False) if queue_params else None,
            job_uuid=job_uuid,
            status=RPATaskStatus.PENDING.value,
            priority=priority,
            created_by=created_by
        )
        
        db.add(task)
        db.commit()
        db.refresh(task)
        
        return task
    
    def get_task_by_id(self, db: Session, task_id: int) -> Optional[RPATask]:
        """
        根据ID获取任务
        
        Args:
            db: 数据库会话
            task_id: 任务ID
        
        Returns:
            任务对象，不存在返回None
        """
        return db.query(RPATask).filter(RPATask.id == task_id).first()
    
    def get_pending_task(self, db: Session) -> Optional[RPATask]:
        """
        获取一个待执行的任务（按优先级降序、创建时间升序）
        使用数据库锁定防止多Worker竞争
        
        Args:
            db: 数据库会话
        
        Returns:
            待执行的任务对象，没有则返回None
        """
        # 查询待执行的任务，按优先级降序、创建时间升序
        task = db.query(RPATask).filter(
            RPATask.status == RPATaskStatus.PENDING.value
        ).order_by(
            RPATask.priority.desc(),
            RPATask.created_at.asc()
        ).with_for_update(skip_locked=True).first()  # 跳过已锁定的记录
        
        return task
    
    def lock_task(self, db: Session, task_id: int) -> bool:
        """
        锁定任务（将状态改为running）
        
        Args:
            db: 数据库会话
            task_id: 任务ID
        
        Returns:
            是否锁定成功
        """
        task = db.query(RPATask).filter(
            RPATask.id == task_id,
            RPATask.status == RPATaskStatus.PENDING.value
        ).first()
        
        if task:
            task.status = RPATaskStatus.RUNNING.value
            task.started_at = get_china_now()
            db.commit()
            return True
        
        return False
    
    def update_task_work_uuid(
        self,
        db: Session,
        task_id: int,
        work_uuid: str
    ) -> bool:
        """
        更新任务的workUuid
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            work_uuid: RPA返回的workUuid
        
        Returns:
            是否更新成功
        """
        task = db.query(RPATask).filter(RPATask.id == task_id).first()
        if task:
            task.work_uuid = work_uuid
            db.commit()
            return True
        return False
    
    def complete_task(
        self,
        db: Session,
        task_id: int,
        success: bool,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        完成任务（成功或失败）并删除
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            success: 是否成功
            result: 执行结果
            error_message: 错误信息
        
        Returns:
            是否更新成功
        """
        task = db.query(RPATask).filter(RPATask.id == task_id).first()
        if task:
            # 记录完成状态（用于日志）
            status = RPATaskStatus.SUCCESS.value if success else RPATaskStatus.FAILED.value
            print(f"任务 {task_id} 完成，状态: {status}, 错误: {error_message}")
            
            # 直接删除任务
            db.delete(task)
            db.commit()
            return True
        return False
    
    def timeout_task(
        self,
        db: Session,
        task_id: int,
        error_message: Optional[str] = None
    ) -> bool:
        """
        任务超时并删除
        
        Args:
            db: 数据库会话
            task_id: 任务ID
            error_message: 错误信息
        
        Returns:
            是否更新成功
        """
        task = db.query(RPATask).filter(RPATask.id == task_id).first()
        if task:
            # 记录超时状态（用于日志）
            print(f"任务 {task_id} 超时，错误: {error_message}")
            
            # 直接删除任务
            db.delete(task)
            db.commit()
            return True
        return False
    
    def delete_task(self, db: Session, task_id: int) -> bool:
        """
        删除任务
        
        Args:
            db: 数据库会话
            task_id: 任务ID
        
        Returns:
            是否删除成功
        """
        task = db.query(RPATask).filter(RPATask.id == task_id).first()
        if task:
            db.delete(task)
            db.commit()
            return True
        return False
    
    def get_tasks_by_target(
        self,
        db: Session,
        target_type: str,
        target_id: int,
        status: Optional[str] = None
    ) -> List[RPATask]:
        """
        根据目标获取任务列表
        
        Args:
            db: 数据库会话
            target_type: 目标类型
            target_id: 目标ID
            status: 任务状态（可选）
        
        Returns:
            任务列表
        """
        query = db.query(RPATask).filter(
            RPATask.target_type == target_type,
            RPATask.target_id == target_id
        )
        
        if status:
            query = query.filter(RPATask.status == status)
        
        return query.order_by(RPATask.created_at.desc()).all()
    
    def get_pending_task_for_target(
        self,
        db: Session,
        target_type: str,
        target_id: int,
        task_type: str
    ) -> Optional[RPATask]:
        """
        检查目标是否有待执行或执行中的同类型任务
        
        Args:
            db: 数据库会话
            target_type: 目标类型
            target_id: 目标ID
            task_type: 任务类型
        
        Returns:
            任务对象，不存在返回None
        """
        return db.query(RPATask).filter(
            RPATask.target_type == target_type,
            RPATask.target_id == target_id,
            RPATask.task_type == task_type,
            or_(
                RPATask.status == RPATaskStatus.PENDING.value,
                RPATask.status == RPATaskStatus.RUNNING.value
            )
        ).first()
    
    def get_tasks_list(
        self,
        db: Session,
        task_type: Optional[str] = None,
        target_type: Optional[str] = None,
        target_id: Optional[int] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        分页查询任务列表
        
        Args:
            db: 数据库会话
            task_type: 任务类型（可选）
            target_type: 目标类型（可选）
            target_id: 目标ID（可选）
            status: 任务状态（可选）
            page: 页码
            page_size: 每页数量
        
        Returns:
            包含列表和分页信息的字典
        """
        query = db.query(RPATask)
        
        if task_type:
            query = query.filter(RPATask.task_type == task_type)
        if target_type:
            query = query.filter(RPATask.target_type == target_type)
        if target_id:
            query = query.filter(RPATask.target_id == target_id)
        if status:
            query = query.filter(RPATask.status == status)
        
        # 获取总数
        total = query.count()
        
        # 分页查询
        tasks = query.order_by(
            RPATask.created_at.desc()
        ).offset((page - 1) * page_size).limit(page_size).all()
        
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": tasks
        }
    
    def get_queue_stats(self, db: Session) -> Dict[str, Any]:
        """
        获取队列统计信息
        
        Args:
            db: 数据库会话
        
        Returns:
            统计信息字典
        """
        pending_count = db.query(RPATask).filter(
            RPATask.status == RPATaskStatus.PENDING.value
        ).count()
        
        running_count = db.query(RPATask).filter(
            RPATask.status == RPATaskStatus.RUNNING.value
        ).count()
        
        return {
            "pending_count": pending_count,
            "running_count": running_count,
            "worker_count": settings.RPA_QUEUE_WORKER_COUNT,
            "queue_enabled": settings.RPA_QUEUE_ENABLED
        }
    
    def cleanup_stuck_tasks(self, db: Session, timeout_minutes: int = 30) -> int:
        """
        清理卡住的任务（长时间处于running状态的任务）
        
        Args:
            db: 数据库会话
            timeout_minutes: 超时时间（分钟）
        
        Returns:
            清理的任务数量
        """
        timeout_threshold = get_china_now() - timedelta(minutes=timeout_minutes)
        
        stuck_tasks = db.query(RPATask).filter(
            RPATask.status == RPATaskStatus.RUNNING.value,
            RPATask.started_at < timeout_threshold
        ).all()
        
        count = 0
        for task in stuck_tasks:
            print(f"清理卡住的任务: {task.id}")
            db.delete(task)
            count += 1
        
        if count > 0:
            db.commit()
        
        return count


# 全局单例
rpa_task_service = RPATaskService()

