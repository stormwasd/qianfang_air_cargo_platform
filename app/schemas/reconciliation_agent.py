from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas.financial_audit import ReceivableResponse
from app.schemas.reconciliation_airline import AirlineReconciliationQuery

AirSourceType = Literal["shenzhen_air", "china_southern_air", "peer_air"]
MAX_SOURCE_ID = 2**63 - 1


class AgentReconciliationQuery(AirlineReconciliationQuery):
    flight_date_start: Optional[date] = Field(None, description="航班日期起始（YYYY-MM-DD，包含当天）")
    flight_date_end: Optional[date] = Field(None, description="航班日期结束（YYYY-MM-DD，包含当天）")
    financial_audit_status: Optional[int] = Field(None, ge=0, le=2, description="仅查询财务已审2；不传或传2返回已审，传0/1返回空列表")
    settlement_status: Optional[int] = Field(None, ge=0, le=1, description="空运代理结算：0=未结算, 1=已结算")


class AgentReconciliationItemResponse(ReceivableResponse):
    source_type: AirSourceType
    source_id: str = Field(..., description="来源主表ID；费用登记台手工新增单据为财务记录ID")
    agent_settlement_status: int = Field(0, description="空运代理结算：0=未结算, 1=已结算")
    agent_settlement_auditor_name: Optional[str] = None
    agent_settlement_time: Optional[str] = None
    financial_audit_status: int = 0
    financial_auditor_name: Optional[str] = None
    actual_customer_name: str = Field("", description="客户ID对应的公司名称，原客户值保留在customer_name")
    actual_flight_number: str = Field("", description="实走航班号；来源走货航班优先，缺失时回退开单航班")
    actual_pieces: str = Field("", description="实走件数，取费用登记台最终payable.gate_pieces，不以开单件数替代")
    actual_weight: str = Field("", description="实走重量，取费用登记台最终payable.transit_weight，不以计费重量替代")


class AgentReconciliationListResponse(BaseModel):
    items: List[AgentReconciliationItemResponse]
    total: int
    page: int
    pageSize: int


class AgentBatchSettleItem(BaseModel):
    source_type: AirSourceType
    source_id: str = Field(..., pattern=r"^[1-9][0-9]*$", max_length=19)

    @field_validator("source_id")
    @classmethod
    def validate_source_id(cls, value):
        if int(value) > MAX_SOURCE_ID:
            raise ValueError("来源ID超出范围")
        return value


class AgentBatchSettleRequest(BaseModel):
    items: List[AgentBatchSettleItem] = Field(..., max_length=1000)


class AgentReconciliationExportRequest(AgentReconciliationQuery):
    selected_items: Optional[List[AgentBatchSettleItem]] = Field(
        None, max_length=1000, description="非空时导出筛选结果中的选中单据，否则导出全部筛选结果"
    )
