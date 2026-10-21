"""汽运代理对账接口约定。"""
from datetime import date, timedelta
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.financial_audit import FinancialAuditRequestModel
from app.utils.helpers import get_china_now

MAX_SOURCE_ID = 2**63 - 1


class RoadAgentReconciliationQuery(BaseModel):
    date_start: Optional[date] = Field(default_factory=lambda: get_china_now().date() - timedelta(days=30), description="托运日期开始，默认北京时间当天往前30天；null不限")
    date_end: Optional[date] = Field(default_factory=lambda: get_china_now().date(), description="托运日期结束，默认北京时间当天；null不限")
    customer_name: Optional[str] = Field(None, description="客户ID精确匹配，或客户名称模糊搜索")
    destination_city: Optional[str] = Field(None, description="目的城市模糊搜索")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")


class RoadAgentReceivableResponse(FinancialAuditRequestModel):
    transport_date: Optional[str] = Field(None, description="托运日期")
    customer_name: Optional[str] = Field(None, description="客户名称（托运书原始值，可为客户ID）")
    cargo_name: Optional[str] = Field(None, description="货物名称")
    origin_city: Optional[str] = Field(None, description="始发城市")
    origin_address: Optional[str] = Field(None, description="始发城市详细地址")
    destination_city: Optional[str] = Field(None, description="目的城市")
    destination_address: Optional[str] = Field(None, description="目的城市详细地址")
    consignee_info: Optional[str] = Field(None, description="收货人")
    contact_phone: Optional[str] = Field(None, description="联系电话")
    quantity: Optional[str] = Field(None, description="件数")
    weight: Optional[str] = Field(None, description="重量")
    volume: Optional[str] = Field(None, description="体积")
    vehicle_type: Optional[str] = Field(None, description="车型")
    rate: Optional[str] = Field(None, description="费率")
    total_freight: Optional[str] = Field(None, description="总运费")
    other_fees: Optional[str] = Field(None, description="其他费用")
    total_amount: Optional[str] = Field(None, description="应收总费用")


class RoadAgentReconciliationItemResponse(RoadAgentReceivableResponse):
    source_id: str = Field(..., description="汽运托运书ID，结算/取消/选中导出均使用此ID")
    actual_customer_name: str = Field("", description="客户ID对应的公司名称；非ID时保留客户原值")
    agent_settlement_status: int = Field(0, description="0=未结算，1=已结算")
    agent_settlement_auditor_name: Optional[str] = None
    agent_settlement_time: Optional[str] = None


class RoadAgentReconciliationListResponse(BaseModel):
    items: List[RoadAgentReconciliationItemResponse]
    total: int
    page: int
    pageSize: int


class RoadAgentSelection(BaseModel):
    source_id: str = Field(..., pattern=r"^[1-9][0-9]*$", max_length=19)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value):
        if int(value) > MAX_SOURCE_ID:
            raise ValueError("来源ID超出范围")
        return value


class RoadAgentBatchSettleRequest(BaseModel):
    items: List[RoadAgentSelection] = Field(..., max_length=1000)


class RoadAgentReconciliationExportRequest(RoadAgentReconciliationQuery):
    selected_items: Optional[List[RoadAgentSelection]] = Field(None, max_length=1000, description="非空时导出筛选结果中的选中单据，否则导出全部筛选结果")
