from pydantic import BaseModel, Field
from typing import Optional, List

class PickupReconciliationQuery(BaseModel):
    waybill_numbers: Optional[str] = Field(None, description="运单号，可输入多个单号，单号之间用英文逗号隔开")
    flight_date_start: Optional[str] = Field(None, description="航班日期起始 (YYYY-MM-DD)")
    flight_date_end: Optional[str] = Field(None, description="航班日期结束 (YYYY-MM-DD)")
    actual_flight_number: Optional[str] = Field(None, description="实走航班号")
    financial_audit_status: Optional[int] = Field(None, description="财务审核：0=未审, 1=暂存, 2=已审")
    customer_name: Optional[str] = Field(None, description="客户名称")
    settlement_status: Optional[int] = Field(None, description="结算状态：0=未结算, 1=已结算")
    pickup_company: Optional[str] = Field(None, description="上门提货单位")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, description="每页数量")

class PickupReconciliationItemResponse(BaseModel):
    source_type: str = Field(..., description="来源类型: shenzhen_air / china_southern_air / peer_air")
    source_id: str = Field(..., description="来源主表ID")
    waybill_number: Optional[str] = Field(None, description="2. 运单号")
    financial_audit_status: int = Field(0, description="3. 财务审核状态: 0=未审, 1=暂存, 2=已审")
    pickup_settlement_status: int = Field(0, description="4. 结算状态: 0=未结算, 1=已结算")
    pickup_company: Optional[str] = Field(None, description="5. 上门提货单位")
    flight_date: Optional[str] = Field(None, description="6. 航班日期")
    actual_flight_number: Optional[str] = Field(None, description="7. 实走航班号")
    destination: Optional[str] = Field(None, description="8. 目的站")
    actual_pieces: Optional[str] = Field(None, description="9. 实走件数")
    actual_weight: Optional[str] = Field(None, description="10. 实走重量")
    pickup_fee: Optional[str] = Field(None, description="11. 上门提货费")

class PickupReconciliationListResponse(BaseModel):
    items: List[PickupReconciliationItemResponse]
    total: int
    page: int
    pageSize: int

class PickupBatchSettleItem(BaseModel):
    source_type: str = Field(..., description="来源类型")
    source_id: str = Field(..., description="来源主表ID")

class PickupBatchSettleRequest(BaseModel):
    items: List[PickupBatchSettleItem] = Field(..., description="待结算的单据列表")

class PickupReconciliationExportRequest(BaseModel):
    waybill_numbers: Optional[str] = None
    flight_date_start: Optional[str] = None
    flight_date_end: Optional[str] = None
    actual_flight_number: Optional[str] = None
    financial_audit_status: Optional[int] = None
    customer_name: Optional[str] = None
    settlement_status: Optional[int] = None
    pickup_company: Optional[str] = None
    selected_items: Optional[List[PickupBatchSettleItem]] = Field(None, description="如果传了，就只导出这些选中的；如果为空，则根据查询条件批量导出")
