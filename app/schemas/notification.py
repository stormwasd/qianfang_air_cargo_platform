"""
通知相关的Schema定义
"""
from typing import Optional, List
from pydantic import BaseModel


class TaskNotificationItem(BaseModel):
    """任务通知项"""
    id: str  # 任务ID (waybill_id 或 booking_id)
    task_type: str  # 任务类型："开单" 或 "订舱"
    source_table: str  # 来源表："waybills" 或 "bookings"
    airline: str  # 航空公司（数据字典值：1=深圳航空，2=南方航空）
    airline_name: Optional[str] = None  # 航空公司名称
    flight_number: Optional[str] = None  # 航班号
    task_date: Optional[str] = None  # 任务日期（开单日期或订舱时间）
    customer_name: Optional[str] = None  # 客户名称（仅开单有，订舱为空）
    quantity: Optional[str] = None  # 数量
    weight: Optional[str] = None  # 重量
    cargo_type: Optional[str] = None  # 货物类型/名称
    exception_time: Optional[str] = None  # 异常时间（仅异常任务有）


class PendingTasksResponse(BaseModel):
    """待执行任务响应"""
    total: int  # 总数
    items: List[TaskNotificationItem]  # 任务列表


class ExceptionTasksResponse(BaseModel):
    """异常任务响应"""
    total: int  # 总数
    items: List[TaskNotificationItem]  # 任务列表


class NotificationResponse(BaseModel):
    """通知接口响应"""
    pending_tasks: PendingTasksResponse  # 待执行任务
    exception_tasks: ExceptionTasksResponse  # 异常任务

