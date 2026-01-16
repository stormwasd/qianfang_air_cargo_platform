"""
RPA任务Schema
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime


class RPATaskCreate(BaseModel):
    """创建RPA任务的Schema"""
    task_type: str
    target_type: str
    target_id: str
    params: Dict[str, Any]
    queue_params: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 1


class RPATaskResponse(BaseModel):
    """RPA任务响应Schema"""
    id: str
    task_type: str
    target_type: str
    target_id: str
    status: str
    priority: int
    work_uuid: Optional[str]
    job_uuid: Optional[str]
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]


class RPATaskQuery(BaseModel):
    """查询RPA任务的Schema"""
    task_type: Optional[str] = None
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    status: Optional[str] = None
    page: int = 1
    page_size: int = 10

