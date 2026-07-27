"""
RPA任务队列服务
管理RPA任务的创建、查询、更新和删除
"""
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.rpa_task import RPATask, RPATaskStatus, RPATaskType, RPATargetType, RPATaskLastSuccess
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now
from app.config import settings

PRINT_TYPE_MAPPING = {
    "file_print": RPATaskType.FILE_PRINT.value,
    "shenzhen_air_main_waybill_print": RPATaskType.SHENZHEN_AIR_MAIN_WAYBILL_PRINT.value,
    "china_southern_air_main_waybill_print": RPATaskType.CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT.value,
    "china_southern_air_security_print": RPATaskType.CHINA_SOUTHERN_AIR_SECURITY_PRINT.value,
    "china_southern_air_label_print": RPATaskType.CHINA_SOUTHERN_AIR_LABEL_PRINT.value,
}

PRINT_TYPE_REVERSE_MAPPING = {v: k for k, v in PRINT_TYPE_MAPPING.items()}

PRINT_TASK_TYPES = set(PRINT_TYPE_MAPPING.values())

TASK_QUEUE_CONFIGS = {
    "SHENZHEN_AIR_WAYBILL_EXECUTE": ["waybill_number", "freight_rate", "freight", "delivery_fee"],
    "SHENZHEN_AIR_BILLING_TIME_CONTAINER": ["billing_time_container", "change_order_information"],
    "CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE": ["freight_rate", "freight", "fuel_costs", "extended_service_fee"],
    "CHINA_SOUTHERN_AIR_DIRECT_INVOICE": ["rate", "freight", "fuel_costs", "extended_service_fee"],
    "CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA": ["rate", "freight", "fuel_costs", "extended_service_fee"],
    "CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING": ["product_information_on_this_site", "lalamove_information"],
}

SINGLETON_TASK_TYPES: set = {
    RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value,
}

TASK_PRIORITY_MAP = {
    RPATaskType.SHENZHEN_AIR_KEEP_LOGIN.value: 3,
    RPATaskType.CHINA_SOUTHERN_AIR_KEEP_LOGIN.value: 3,
    RPATaskType.TANGYI_KEEP_LOGIN.value: 3,
    RPATaskType.TANGYI_RESTART.value: 4,
    RPATaskType.SHENZHEN_AIR_MAIN_WAYBILL_PRINT.value: 2,
    RPATaskType.CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT.value: 2,
    RPATaskType.CHINA_SOUTHERN_AIR_SECURITY_PRINT.value: 2,
    RPATaskType.CHINA_SOUTHERN_AIR_LABEL_PRINT.value: 2,
}

class RPATaskService:
    """RPA任务队列服务类"""
    
    @staticmethod
    def resolve_task_location(task_type: str) -> Optional[str]:
        """
        根据任务类型自动推断所属区域
        
        Returns:
            "shenzhen_air" / "china_southern_air" / None（无法推断，需显式传入）
        """
        if task_type.startswith("SHENZHEN_AIR_"):
            return "shenzhen_air"
        elif task_type.startswith("CHINA_SOUTHERN_AIR_") or task_type.startswith("TANGYI_"):
            return "china_southern_air"
        return None
    
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
        created_by: Optional[int] = None,
        robot_id: Optional[int] = None,
        location: Optional[str] = None
    ) -> RPATask:
        """
        创建RPA任务
        
        注意：任务创建时 robot_id 默认为 NULL，由 Worker 消费时通过 location + 权限竞争分配。
        仅在需要指定特定机器人消费时才传入 robot_id。
        
        Args:
            db: 数据库会话
            task_type: 任务类型
            target_type: 目标类型（waybill/booking）
            target_id: 目标ID
            params: RPA调用参数
            queue_params: 队列参数（已废弃，Worker 消费时从 robot_queues 动态构建）
            job_uuid: RPA的jobUuid（已废弃，Worker 消费时从 robot_jobs 动态解析）
            priority: 优先级（不传则使用配置文件默认值）
            created_by: 创建用户ID
            robot_id: 指定消费的机器人ID（通常为 NULL，由 Worker 竞争消费）
            location: 任务所属区域（shenzhen_air/china_southern_air），不传则从 task_type 自动推断
        
        Returns:
            创建的任务对象
        """
        if priority is None:
            priority = TASK_PRIORITY_MAP.get(task_type, settings.RPA_QUEUE_DEFAULT_PRIORITY)
        
        if location is None:
            location = self.resolve_task_location(task_type)
        
        task = RPATask(
            id=generate_id(),
            task_type=task_type,
            target_type=target_type,
            target_id=target_id,
            params=json.dumps(params, ensure_ascii=False),
            queue_params=None,  
            job_uuid=None,  
            robot_id=robot_id,  
            location=location,
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
        task = db.query(RPATask).filter(
            RPATask.status == RPATaskStatus.PENDING.value
        ).order_by(
            RPATask.priority.desc(),
            RPATask.created_at.asc()
        ).with_for_update(skip_locked=True).first()  
        
        return task
    
    def get_pending_task_for_robot(
        self,
        db: Session,
        robot_db_id: int,
        allowed_task_types: list,
        robot_location: Optional[str] = None
    ) -> Optional[RPATask]:
        """
        获取该机器人可消费的一个待执行任务
        
        匹配规则：
        1. 任务类型必须在机器人的权限列表中
        2. 任务的 location 必须与机器人的 location 一致
        3. 任务的 robot_id 为 NULL（任意机器人可消费）或等于当前机器人ID（指定消费）
        4. 使用行级锁 skip_locked 防止多 Worker 竞争
        5. SINGLETON_TASK_TYPES 中的任务类型：如果全局已有同类任务 RUNNING，则本次不消费该类型
        
        Args:
            db: 数据库会话
            robot_db_id: 机器人记录数据库主键ID
            allowed_task_types: 该机器人可执行的任务类型列表
            robot_location: 机器人所属区域（shenzhen_air/china_southern_air）
        
        Returns:
            待执行的任务对象，没有则返回None
        """
        if not allowed_task_types:
            return None
        
        effective_types = list(allowed_task_types)
        singleton_types_in_allowed = [t for t in effective_types if t in SINGLETON_TASK_TYPES]
        if singleton_types_in_allowed:
            already_running = db.query(RPATask.task_type).filter(
                RPATask.task_type.in_(singleton_types_in_allowed),
                RPATask.status == RPATaskStatus.RUNNING.value
            ).first()
            if already_running:
                running_type = already_running[0]
                effective_types = [t for t in effective_types if t != running_type]
                if not effective_types:
                    return None
        
        filters = [
            RPATask.status == RPATaskStatus.PENDING.value,
            RPATask.task_type.in_(effective_types),
            or_(
                RPATask.robot_id == None,
                RPATask.robot_id == robot_db_id
            )
        ]
        
        if robot_location:
            filters.append(RPATask.location == robot_location)
        
        task = db.query(RPATask).filter(
            *filters
        ).order_by(
            RPATask.priority.desc(),
            RPATask.created_at.asc()
        ).with_for_update(skip_locked=True).first()
        
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
            status = RPATaskStatus.SUCCESS.value if success else RPATaskStatus.FAILED.value
            print(f"任务 {task_id} 完成，状态: {status}, 错误: {error_message}")
            
            if success and task.task_type:
                self.record_task_success(db, task.task_type)

            db.delete(task)
            db.commit()
            return True
        return False

    def record_task_success(self, db: Session, task_type: str) -> bool:
        """
        记录/刷新指定任务类型的最后一次成功执行时间（UTC+8）
        """
        if not task_type:
            return False
        try:
            now = get_china_now()
            record = db.query(RPATaskLastSuccess).filter(RPATaskLastSuccess.task_type == task_type).first()
            if record:
                record.last_success_at = now
                record.updated_at = now
            else:
                record = RPATaskLastSuccess(
                    task_type=task_type,
                    last_success_at=now,
                    updated_at=now
                )
                db.add(record)
            db.commit()
            return True
        except Exception as e:
            print(f"记录 RPA 任务({task_type})成功时间打卡失败: {e}")
            db.rollback()
            return False

    def get_last_success_time(self, db: Session, task_type: str) -> Optional[datetime]:
        """
        获取指定任务类型的最后一次成功执行时间
        """
        if not task_type:
            return None
        record = db.query(RPATaskLastSuccess).filter(RPATaskLastSuccess.task_type == task_type).first()
        return record.last_success_at if record else None
    
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
            print(f"任务 {task_id} 超时，错误: {error_message}")
            
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
        pageSize: int = 10
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
            pageSize: 每页数量
        
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
        
        total = query.count()
        
        tasks = query.order_by(
            RPATask.created_at.desc()
        ).offset((page - 1) * pageSize).limit(pageSize).all()
        
        return {
            "total": total,
            "page": page,
            "pageSize": pageSize,
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
        
        from app.models.robot import Robot
        worker_count = db.query(Robot).filter(Robot.status == 1).count()
        
        return {
            "pending_count": pending_count,
            "running_count": running_count,
            "worker_count": worker_count,
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


rpa_task_service = RPATaskService()

