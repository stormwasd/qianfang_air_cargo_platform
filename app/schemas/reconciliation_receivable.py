"""应收对账五个模块的独立接口契约。"""
from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field

from app.schemas.financial_audit import ReceivableResponse
from app.schemas.reconciliation_agent import AgentBatchSettleItem, AirSourceType
from app.schemas.reconciliation_road_agent import (
    RoadAgentReceivableResponse, RoadAgentReconciliationQuery, RoadAgentSelection,
)


class AirReceivableQuery(BaseModel):
    waybill_numbers: Optional[str] = Field(None, description="完整运单号，多个用英文逗号分隔")
    flight_date_start: Optional[date] = Field(None, description="航班日期开始，包含当天")
    flight_date_end: Optional[date] = Field(None, description="航班日期结束，包含当天")
    financial_audit_status: Optional[int] = Field(None, ge=0, le=2)
    customer_name: Optional[str] = Field(None, description="应收客户原值包含匹配，通常传客户ID")
    settlement_status: Optional[int] = Field(None, ge=0, le=1, description="本模块应收结算状态")
    page: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=200)


class AirlineReceivableQuery(AirReceivableQuery):
    airline: Optional[str] = Field(None, description="航司精确匹配；全部表示不限")


class PickupReceivableQuery(AirReceivableQuery):
    actual_flight_number: Optional[str] = Field(None, description="实走航班号包含匹配")
    pickup_company: Optional[str] = Field(None, description="上门提货单位包含匹配")


class DeliveryReceivableQuery(AirReceivableQuery):
    actual_flight_number: Optional[str] = Field(None, description="实走航班号包含匹配")
    delivery_company: Optional[str] = Field(None, description="派送单位包含匹配")


class AirlineReceivableExport(AirlineReceivableQuery):
    selected_items: Optional[List[AgentBatchSettleItem]] = Field(None, max_length=1000)


class PickupReceivableExport(PickupReceivableQuery):
    selected_items: Optional[List[AgentBatchSettleItem]] = Field(None, max_length=1000)


class DeliveryReceivableExport(DeliveryReceivableQuery):
    selected_items: Optional[List[AgentBatchSettleItem]] = Field(None, max_length=1000)


class SettlementResponse(BaseModel):
    settlement_status: int = Field(0, description="仅当前应收模块：0未结算，1已结算")
    settlement_auditor_name: Optional[str] = None
    settlement_time: Optional[str] = None


class AirReceivableItem(ReceivableResponse, SettlementResponse):
    source_type: AirSourceType
    source_id: str
    financial_audit_status: int = 0
    financial_auditor_name: Optional[str] = None
    actual_customer_name: Optional[str] = None
    actual_flight_number: Optional[str] = None
    pickup_company: Optional[str] = None
    delivery_company: Optional[str] = None


class AirReceivableList(BaseModel):
    items: List[AirReceivableItem]
    total: int
    page: int
    pageSize: int


class RoadReceivableQuery(RoadAgentReconciliationQuery):
    settlement_status: Optional[int] = Field(None, ge=0, le=1, description="应收汽运代理结算状态")


class RoadReceivableItem(RoadAgentReceivableResponse, SettlementResponse):
    source_id: str
    actual_customer_name: str = ""


class RoadReceivableList(BaseModel):
    items: List[RoadReceivableItem]
    total: int
    page: int
    pageSize: int


class RoadReceivableExport(RoadReceivableQuery):
    selected_items: Optional[List[RoadAgentSelection]] = Field(None, max_length=1000)
