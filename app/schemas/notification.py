"""
通知相关的Schema定义
"""
from typing import Optional, List
from pydantic import BaseModel


class TaskNotificationItem(BaseModel):
    """任务通知项"""
    id: str  
    task_type: str  
    source_table: str  
    airline: str  
    airline_name: Optional[str] = None  
    flight_number: Optional[str] = None  
    task_date: Optional[str] = None  
    customer_name: Optional[str] = None  
    quantity: Optional[str] = None  
    weight: Optional[str] = None  
    cargo_type: Optional[str] = None  
    exception_time: Optional[str] = None  


class PendingTasksResponse(BaseModel):
    """待执行任务响应"""
    total: int  
    items: List[TaskNotificationItem]  


class ExceptionTasksResponse(BaseModel):
    """异常任务响应"""
    total: int  
    items: List[TaskNotificationItem]  


class NotificationResponse(BaseModel):
    """通知接口响应"""
    pending_tasks: PendingTasksResponse  
    exception_tasks: ExceptionTasksResponse  

