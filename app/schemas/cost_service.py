"""
费用登记台 Pydantic Schemas（层级化/结构化设计，方便前端分类渲染与提交）
"""
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# 1. 业务层级子模型定义
# ============================================================================

class ConsignorInfo(BaseModel):
    """(1) 货主委托信息"""
    create_time: Optional[str] = Field(None, description="制单时间 (YYYY-MM-DD HH:MM:SS)")
    internal_doc_id: Optional[str] = Field(None, description="内部单据ID")
    warehouse_entry_date: Optional[str] = Field(None, description="进仓日期 (YYYY-MM-DD)")
    customer_name: Optional[str] = Field(None, description="客户名称")
    origin_destination: Optional[str] = Field(None, description="始发站-目的站")
    customs_declaration: Optional[str] = Field(None, description="报关")
    bill_of_lading: Optional[str] = Field(None, description="提单")
    flight_date: Optional[str] = Field(None, description="航班日期 (YYYY-MM-DD)")
    flight_no: Optional[str] = Field(None, description="航班号")
    flight_doc_no: Optional[str] = Field(None, description="航班单号")
    pieces: Optional[int] = Field(None, description="件数")
    actual_weight: Optional[float] = Field(None, description="实际重量")
    chargeable_weight: Optional[float] = Field(None, description="计费重量")
    volume: Optional[float] = Field(None, description="体积")
    first_leg_weight: Optional[float] = Field(None, description="一程重量")
    agent: Optional[str] = Field(None, description="代理")
    remark: Optional[str] = Field(None, description="备注")


class ReceivablesInfo(BaseModel):
    """(2) 应收款项"""
    unit_price: Optional[float] = Field(None, description="单价")
    freight_method: Optional[str] = Field(None, description="运费计算方式")
    freight: Optional[float] = Field(None, description="运费")
    lading_info_fee: Optional[float] = Field(None, description="提单费/信息录入费")
    split_offset_telex_fee: Optional[float] = Field(None, description="分单费/抵账费/电报费")
    customs_fee: Optional[float] = Field(None, description="报关费")
    continuation_sheet_fee: Optional[float] = Field(None, description="续页费")
    customs_inspection_fee: Optional[float] = Field(None, description="海关查验费")
    magnetic_security_fee: Optional[float] = Field(None, description="磁检费/安检费")
    tc_express_fee: Optional[float] = Field(None, description="TC操作费/快件中心过站费")
    warehouse_ground_fee: Optional[float] = Field(None, description="前置仓/国际货站地面费")
    doc_make_fee: Optional[float] = Field(None, description="制单费")
    doc_split_fee: Optional[float] = Field(None, description="制单分单费")
    skid_fee: Optional[float] = Field(None, description="垫板费")
    pallet_packing_fee: Optional[float] = Field(None, description="打板/装箱费")
    probe_fee: Optional[float] = Field(None, description="探板费")
    consumables_fee: Optional[float] = Field(None, description="耗材费")
    first_leg_fee: Optional[float] = Field(None, description="一程费用")
    total: Optional[float] = Field(None, description="应收合计")


class PayableIntlAir(BaseModel):
    """(3) 应付款项 - [1] 国际空运信息"""
    subtotal: Optional[float] = Field(None, description="应付小计")
    outsource_unit: Optional[str] = Field(None, description="外发单位")
    origin: Optional[str] = Field(None, description="始发站")
    destination: Optional[str] = Field(None, description="到达站")
    flight_doc_no: Optional[str] = Field(None, description="航班单号/航空单号")
    flight_no: Optional[str] = Field(None, description="航班号")
    flight_date: Optional[str] = Field(None, description="航班日期 (YYYY-MM-DD)")
    pieces: Optional[int] = Field(None, description="件数")
    weight: Optional[float] = Field(None, description="重量")
    volume: Optional[float] = Field(None, description="体积")
    chargeable_weight: Optional[float] = Field(None, description="计费重量")
    rate: Optional[float] = Field(None, description="费率")
    freight: Optional[float] = Field(None, description="运费")
    lading_fee: Optional[float] = Field(None, description="提单费")
    split_fee: Optional[float] = Field(None, description="分单")
    borrow_magnetic_fuel_pickup_fee: Optional[float] = Field(None, description="借单费/磁检费/燃油费/国内提货费")
    tc_network_disposal_fee: Optional[float] = Field(None, description="TC费/入网费/国际处置费")
    customs_fee: Optional[float] = Field(None, description="报关费")
    continuation_sheet_fee: Optional[float] = Field(None, description="续页费")
    consumables_fee: Optional[float] = Field(None, description="耗材费")
    front_warehouse: Optional[float] = Field(None, description="前置仓")
    other_fee: Optional[float] = Field(None, description="其他费用")
    remark: Optional[str] = Field(None, description="备注")


class PayableTrucking(BaseModel):
    """(3) 应付款项 - [2] 汽运信息"""
    subtotal: Optional[float] = Field(None, description="应付小计")
    date: Optional[str] = Field(None, description="托运日期 (YYYY-MM-DD)")
    outsource_unit: Optional[str] = Field(None, description="外发单位")
    pieces: Optional[int] = Field(None, description="件数")
    weight: Optional[float] = Field(None, description="重量")
    volume: Optional[float] = Field(None, description="体积")
    unit_price: Optional[float] = Field(None, description="单价")
    freight: Optional[float] = Field(None, description="运费")
    doc_fee: Optional[float] = Field(None, description="制单费")
    other_fee: Optional[float] = Field(None, description="其他费用")
    remark: Optional[str] = Field(None, description="备注")


class PayableDomAir(BaseModel):
    """(3) 应付款项 - [3] 国内空运信息"""
    subtotal: Optional[float] = Field(None, description="应付小计")
    date: Optional[str] = Field(None, description="托运日期 (YYYY-MM-DD)")
    outsource_unit: Optional[str] = Field(None, description="外发单位")
    origin: Optional[str] = Field(None, description="始发站")
    destination: Optional[str] = Field(None, description="到达站")
    airline: Optional[str] = Field(None, description="航空公司")
    airline_unit: Optional[str] = Field(None, description="航空单位")
    flight_doc_no: Optional[str] = Field(None, description="航空单号")
    flight_no: Optional[str] = Field(None, description="航班号")
    flight_date: Optional[str] = Field(None, description="航班日期 (YYYY-MM-DD)")
    pieces: Optional[int] = Field(None, description="件数")
    weight: Optional[float] = Field(None, description="重量")
    chargeable_weight: Optional[float] = Field(None, description="计费重量")
    rate: Optional[float] = Field(None, description="费率")
    freight: Optional[float] = Field(None, description="运费")
    other_fee: Optional[float] = Field(None, description="其他费用")
    remark: Optional[str] = Field(None, description="备注")


class PayableCustoms(BaseModel):
    """(3) 应付款项 - [4] 报关信息"""
    subtotal: Optional[float] = Field(None, description="应付小计")
    date: Optional[str] = Field(None, description="报关日期 (YYYY-MM-DD)")
    agent: Optional[str] = Field(None, description="报关代理")
    customs_fee: Optional[float] = Field(None, description="报关费")
    continuation_sheet_fee: Optional[float] = Field(None, description="续页费")
    inspection_delete_fee: Optional[float] = Field(None, description="查验费/删单费")
    other_fee: Optional[float] = Field(None, description="其他费用")
    remark: Optional[str] = Field(None, description="备注")


class PayableGround(BaseModel):
    """(3) 应付款项 - [5] 地面操作信息"""
    subtotal: Optional[float] = Field(None, description="应付小计")
    date: Optional[str] = Field(None, description="托运日期 (YYYY-MM-DD)")
    outsource_unit: Optional[str] = Field(None, description="外发单位")
    chargeable_weight: Optional[float] = Field(None, description="计费重量")
    rate: Optional[float] = Field(None, description="费率")
    freight: Optional[float] = Field(None, description="运费")
    lading_express_fee: Optional[float] = Field(None, description="提单费/快件处置费")
    security_customs_fee: Optional[float] = Field(None, description="安检费/报关费")
    pallet_exit_fee: Optional[float] = Field(None, description="打板费/退场费")
    other_fee: Optional[float] = Field(None, description="其他费用")
    remark: Optional[str] = Field(None, description="备注")


class PayablesInfo(BaseModel):
    """(3) 应付款项整体结构"""
    intl_air: Optional[PayableIntlAir] = Field(default_factory=PayableIntlAir, description="国际空运信息")
    trucking: Optional[PayableTrucking] = Field(default_factory=PayableTrucking, description="汽运信息")
    dom_air: Optional[PayableDomAir] = Field(default_factory=PayableDomAir, description="国内空运信息")
    customs: Optional[PayableCustoms] = Field(default_factory=PayableCustoms, description="报关信息")
    ground: Optional[PayableGround] = Field(default_factory=PayableGround, description="地面操作信息")
    pay_total: Optional[float] = Field(None, description="应付合计")


class DiscountInfo(BaseModel):
    """(4) 折让信息"""
    discount_person: Optional[str] = Field(None, description="折让人员")
    discount_fee: Optional[float] = Field(None, description="折让费")


class SalesCommission(BaseModel):
    """(5) 销售提成"""
    salesperson: Optional[str] = Field(None, description="业务员")
    commission_amount: Optional[float] = Field(None, description="提成金额")


class OperatingInfo(BaseModel):
    """(6) 经营信息"""
    profit: Optional[float] = Field(None, description="利润")
    profit_margin: Optional[float] = Field(None, description="利润率")


# ============================================================================
# 2. 顶级请求与查询 Schema 定义
# ============================================================================

class CostRegistrationSave(BaseModel):
    """费用信息登记 保存/修改 层级结构"""
    consignor_info: Optional[ConsignorInfo] = Field(default_factory=ConsignorInfo, description="货主委托信息")
    receivables: Optional[ReceivablesInfo] = Field(default_factory=ReceivablesInfo, description="应收款项")
    payables: Optional[PayablesInfo] = Field(default_factory=PayablesInfo, description="应付款项")
    discount_info: Optional[DiscountInfo] = Field(default_factory=DiscountInfo, description="折让信息")
    sales_commission: Optional[SalesCommission] = Field(default_factory=SalesCommission, description="销售提成")
    operating_info: Optional[OperatingInfo] = Field(default_factory=OperatingInfo, description="经营信息")


class CostConsignmentCreate(CostRegistrationSave):
    """新增 单据费用明细 请求结构"""
    pass


class CostConsignmentUpdate(CostRegistrationSave):
    """修改 单据费用明细 请求结构"""
    pass


class CostConsignmentSortField(str, Enum):
    """费用单据列表支持的排序字段。"""
    CREATE_TIME = "create_time"
    WAREHOUSE_ENTRY_DATE = "warehouse_entry_date"


class CostConsignmentSortOrder(str, Enum):
    """费用单据列表支持的排序方向。"""
    ASC = "asc"
    DESC = "desc"


class CostConsignmentQuery(BaseModel):
    """单据信息-列表 查询参数"""
    start_warehouse_date: Optional[str] = Field(None, description="进仓开始日期 (YYYY-MM-DD)")
    end_warehouse_date: Optional[str] = Field(None, description="进仓结束日期 (YYYY-MM-DD)")
    customer_name: Optional[str] = Field(None, description="客户名称 (模糊匹配)")
    agent: Optional[str] = Field(None, description="代理单位 (模糊匹配)")
    flight_doc_no: Optional[str] = Field(
        None,
        description=(
            "航司单号/航班单号 (模糊匹配，同时匹配货主托运、国际空运应付、"
            "国内空运应付中的航司单号，并兼容匹配提单)"
        ),
    )
    flight_no: Optional[str] = Field(
        None,
        description=(
            "航班号 (模糊匹配，同时匹配货主托运、国际空运应付、国内空运应付中的航班号)"
        ),
    )
    sort_by: CostConsignmentSortField = Field(
        CostConsignmentSortField.WAREHOUSE_ENTRY_DATE,
        description="排序字段：create_time（制单时间）或 warehouse_entry_date（进仓日期）",
    )
    sort_order: CostConsignmentSortOrder = Field(
        CostConsignmentSortOrder.DESC,
        description="排序方向：asc（正序）或 desc（倒序）",
    )
    page: Optional[int] = Field(1, ge=1, description="页码")
    pageSize: Optional[int] = Field(10, ge=1, description="每页数量")


class CostBatchDeleteRequest(BaseModel):
    """批量删除请求体"""
    ids: List[str] = Field(..., description="要删除的单据ID列表")


class CostExportExcelRequest(BaseModel):
    """导出 Excel 请求体"""
    ids: List[str] = Field(..., description="要导出的单据ID列表")
