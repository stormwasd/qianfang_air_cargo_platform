"""
客服接单台 Pydantic Schemas
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Union
from datetime import datetime, date


class ConsignmentBase(BaseModel):
    """委托信息基础 Schema"""
    create_time: Optional[Union[datetime, str]] = Field(None, description="制单时间，例如 '2026-07-25 14:30:00' 或 ISO 格式")
    internal_doc_id: Optional[str] = Field(None, description="内部单据ID")
    warehouse_entry_date: Optional[Union[date, str]] = Field(None, description="进仓日期，例如 '2026-07-25'")
    customer_name: Optional[str] = Field(None, description="客户名称")
    origin_destination: Optional[str] = Field(None, description="始发站-目的站，例如 'CAN-PVG'")
    customs_declaration: Optional[str] = Field(None, description="报关")
    bill_of_lading: Optional[str] = Field(None, description="提单")
    flight_date: Optional[Union[date, str]] = Field(None, description="航班日期，例如 '2026-07-26'")
    flight_no: Optional[str] = Field(None, description="航班号")
    flight_doc_no: Optional[str] = Field(None, description="航班单号")
    pieces: Optional[int] = Field(None, description="件数")
    actual_weight: Optional[float] = Field(None, description="实际重量")
    chargeable_weight: Optional[float] = Field(None, description="计费重量")
    volume: Optional[float] = Field(None, description="体积")
    first_leg_weight: Optional[float] = Field(None, description="一程重量")
    agent: Optional[str] = Field(None, description="代理")
    remark: Optional[str] = Field(None, description="备注")


class ConsignmentRegistrationSave(ConsignmentBase):
    """委托信息登记-保存 Schema"""
    pass


class ConsignmentRegistrationResponse(ConsignmentBase):
    """委托信息登记-响应 Schema"""
    id: str = Field(..., description="主键ID")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")


class ConsignmentInfoCreate(ConsignmentBase):
    """委托信息-新增 Schema"""
    pass


class ConsignmentInfoUpdate(ConsignmentBase):
    """委托信息-修改 Schema。

    数值字段未传时保持原值；显式传 ``null`` 时清空对应数值。
    """
    pass


class ConsignmentInfoSortField(str, Enum):
    """委托信息列表支持的排序字段。"""
    CREATE_TIME = "create_time"
    WAREHOUSE_ENTRY_DATE = "warehouse_entry_date"


class ConsignmentInfoSortOrder(str, Enum):
    """委托信息列表支持的排序方向。"""
    ASC = "asc"
    DESC = "desc"


class ConsignmentInfoQuery(BaseModel):
    """委托信息-列表查询 Schema"""
    start_date: Optional[str] = Field(None, description="制单日期区间-开始日期 (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="制单日期区间-结束日期 (YYYY-MM-DD)")
    customer_name: Optional[str] = Field(None, description="客户名称 (模糊查询)")
    sort_by: ConsignmentInfoSortField = Field(
        ConsignmentInfoSortField.CREATE_TIME,
        description="排序字段：create_time（制单时间）或 warehouse_entry_date（进仓日期）",
    )
    sort_order: ConsignmentInfoSortOrder = Field(
        ConsignmentInfoSortOrder.DESC,
        description="排序方向：asc（正序）或 desc（倒序）",
    )
    page: Optional[int] = Field(1, ge=1, description="页码，默认1")
    pageSize: Optional[int] = Field(10, ge=1, description="每页数量，默认10")


class BatchDeleteRequest(BaseModel):
    """批量删除请求 Schema"""
    ids: List[str] = Field(..., description="待删除的委托信息ID数组", min_items=1)


class ExportExcelRequest(BaseModel):
    """选中导出 Excel 请求 Schema"""
    ids: List[str] = Field(..., description="选中待导出的委托信息ID数组", min_items=1)


class ConsignmentInfoResponse(ConsignmentBase):
    """委托信息-明细响应 Schema"""
    id: str = Field(..., description="委托信息ID")
    creator_id: Optional[str] = Field(None, description="创建人ID")
    created_at: Optional[str] = Field(None, description="创建时间")
    updated_at: Optional[str] = Field(None, description="更新时间")
