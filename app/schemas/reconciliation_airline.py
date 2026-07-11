from pydantic import BaseModel, Field
from typing import Optional, List

class AirlineReconciliationQuery(BaseModel):
    waybill_numbers: Optional[str] = Field(None, description="运单号，可输入多个单号，单号之间用英文逗号隔开")
    flight_date_start: Optional[str] = Field(None, description="航班日期起始 (YYYY-MM-DD)")
    flight_date_end: Optional[str] = Field(None, description="航班日期结束 (YYYY-MM-DD)")
    airline: Optional[str] = Field(None, description="航司 (如：深航, 南航 等)")
    financial_audit_status: Optional[int] = Field(None, description="财务审核：0=未审, 1=暂存, 2=已审")
    customer_name: Optional[str] = Field(None, description="客户名称（通常为前端传入的客户ID）")
    settlement_status: Optional[int] = Field(None, description="结算状态：0=未结算, 1=已结算")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")

class AirlineReconciliationItemResponse(BaseModel):
    source_type: str = Field(..., description="来源类型: shenzhen_air / china_southern_air / peer_air")
    source_id: str = Field(..., description="来源主表ID")
    waybill_number: Optional[str] = Field(None, description="1. 运单号")
    financial_audit_status: int = Field(0, description="2. 财务审核状态: 0=未审, 1=暂存, 2=已审")
    financial_auditor_name: Optional[str] = Field(None, description="3. 财务审核人")
    airline_settlement_status: int = Field(0, description="4. 结算状态: 0=未结算, 1=已结算")
    origin: Optional[str] = Field(None, description="5. 始发站")
    destination: Optional[str] = Field(None, description="6. 目的站")
    flight_date: Optional[str] = Field(None, description="7. 航班日期")
    airline: Optional[str] = Field(None, description="8. 航空公司")
    actual_customer_name: Optional[str] = Field(None, description="9. 客户名称")
    flight_number: Optional[str] = Field(None, description="10. 开单航班号")
    actual_flight_number: Optional[str] = Field(None, description="11. 实走航班号")
    cargo_name: Optional[str] = Field(None, description="12. 货物名称")
    billing_quantity: Optional[str] = Field(None, description="13. 开单件数")
    billing_weight: Optional[str] = Field(None, description="14. 开单重量")
    actual_pieces: Optional[str] = Field(None, description="15. 实走件数 (payable.gate_pieces)")
    actual_weight: Optional[str] = Field(None, description="16. 实走重量 (payable.transit_weight)")
    chargeable_weight: Optional[str] = Field(None, description="17. 计费重量 (payable.chargeable_weight)")
    freight_rate: Optional[str] = Field(None, description="18. 费率 (payable.freight_rate)")
    air_freight: Optional[str] = Field(None, description="19. 运费 (payable.air_freight)")
    fuel_surcharge: Optional[str] = Field(None, description="20. 燃油费 (payable.fuel_surcharge)")
    transit_fee: Optional[str] = Field(None, description="21. 过站费 (payable.transit_fee)")
    telegraph_cost: Optional[str] = Field(None, description="22. 电报费 (payable.telegraph_cost)")
    cca_cost: Optional[str] = Field(None, description="23. CCA费用 (payable.cca_cost)")
    penalty_fee: Optional[str] = Field(None, description="24. 违规罚款 (payable.penalty_fee)")
    total_cost: Optional[str] = Field(None, description="25. 应付合计 (payable.total_cost)")
    airline_settlement_auditor_name: Optional[str] = Field(None, description="26. 结算审核人")

class AirlineReconciliationListResponse(BaseModel):
    items: List[AirlineReconciliationItemResponse]
    total: int
    page: int
    pageSize: int
