"""单据操作记录查询响应。"""
from typing import List, Literal

from pydantic import BaseModel, Field


class ConsignmentOperationLogItem(BaseModel):
    id: str = Field(..., description="操作记录ID")
    consignment_id: str = Field(..., description="两台共用单据ID")
    source: Literal["customer_service", "cost_service"] = Field(..., description="实际操作来源台")
    action: Literal["draft", "save", "void", "delete"] = Field(..., description="暂存、保存、作废、删除")
    operation_name: str = Field(..., description="操作名称")
    operator_id: str = Field(..., description="实际操作用户ID")
    operator_name: str = Field(..., description="操作时用户姓名")
    operated_at: str = Field(..., description="中国时间 ISO 8601，含 +08:00")


class ConsignmentOperationLogPage(BaseModel):
    consignment_id: str
    total: int
    items: List[ConsignmentOperationLogItem]
    page: int
    pageSize: int
