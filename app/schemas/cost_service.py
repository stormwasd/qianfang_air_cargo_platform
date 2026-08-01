"""
费用登记台 Pydantic Schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class CostRegistrationSave(BaseModel):
    """保存/编辑 费用信息登记 数据结构"""
    # (1) 货主委托信息
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
    
    # (2) 应收款项
    unit_price: Optional[float] = Field(None, description="单价")
    receivable_freight: Optional[float] = Field(None, description="运费")
    receivable_lading_info_fee: Optional[float] = Field(None, description="提单费/信息录入费")
    receivable_split_offset_telex_fee: Optional[float] = Field(None, description="分单费/抵账费/电报费")
    receivable_customs_fee: Optional[float] = Field(None, description="报关费")
    receivable_continuation_sheet_fee: Optional[float] = Field(None, description="续页费")
    receivable_customs_inspection_fee: Optional[float] = Field(None, description="海关查验费")
    receivable_magnetic_security_fee: Optional[float] = Field(None, description="磁检费/安检费")
    receivable_tc_express_fee: Optional[float] = Field(None, description="TC操作费/快件中心过站费")
    receivable_warehouse_ground_fee: Optional[float] = Field(None, description="前置仓/国际货站地面费")
    receivable_doc_make_fee: Optional[float] = Field(None, description="制单费")
    receivable_doc_split_fee: Optional[float] = Field(None, description="制单分单费")
    receivable_skid_fee: Optional[float] = Field(None, description="垫板费")
    receivable_pallet_packing_fee: Optional[float] = Field(None, description="打板/装箱费")
    receivable_probe_fee: Optional[float] = Field(None, description="探板费")
    receivable_consumables_fee: Optional[float] = Field(None, description="耗材费")
    receivable_first_leg_fee: Optional[float] = Field(None, description="一程费用")
    receivable_total: Optional[float] = Field(None, description="应收合计")
    receivable_agent: Optional[str] = Field(None, description="代理")
    
    # (3) 应付款项 - [1] 国际空运信息
    pay_intl_air_subtotal: Optional[float] = Field(None, description="国际空运-应付小计")
    pay_intl_air_date: Optional[str] = Field(None, description="国际空运-托运日期 (YYYY-MM-DD)")
    pay_intl_air_outsource_unit: Optional[str] = Field(None, description="国际空运-外发单位")
    pay_intl_air_origin: Optional[str] = Field(None, description="国际空运-始发站")
    pay_intl_air_destination: Optional[str] = Field(None, description="国际空运-到达站")
    pay_intl_air_airline: Optional[str] = Field(None, description="国际空运-航空公司")
    pay_intl_air_flight_doc_no: Optional[str] = Field(None, description="国际空运-航班单号/航空单号")
    pay_intl_air_flight_no: Optional[str] = Field(None, description="国际空运-航班号")
    pay_intl_air_flight_date: Optional[str] = Field(None, description="国际空运-航班日期 (YYYY-MM-DD)")
    pay_intl_air_pieces: Optional[int] = Field(None, description="国际空运-件数")
    pay_intl_air_weight: Optional[float] = Field(None, description="国际空运-重量")
    pay_intl_air_volume: Optional[float] = Field(None, description="国际空运-体积")
    pay_intl_air_chargeable_weight: Optional[float] = Field(None, description="国际空运-计费重量")
    pay_intl_air_rate: Optional[float] = Field(None, description="国际空运-费率")
    pay_intl_air_freight: Optional[float] = Field(None, description="国际空运-运费")
    pay_intl_air_lading_fee: Optional[float] = Field(None, description="国际空运-提单费")
    pay_intl_air_split_fee: Optional[float] = Field(None, description="国际空运-分单")
    pay_intl_air_borrow_magnetic_fuel_pickup_fee: Optional[float] = Field(None, description="国际空运-借单费/磁检费/燃油费/国内提货费")
    pay_intl_air_tc_network_disposal_fee: Optional[float] = Field(None, description="国际空运-TC费/入网费/国际处置费")
    pay_intl_air_customs_fee: Optional[float] = Field(None, description="国际空运-报关费")
    pay_intl_air_continuation_sheet_fee: Optional[float] = Field(None, description="国际空运-续页费")
    pay_intl_air_consumables_fee: Optional[float] = Field(None, description="国际空运-耗材费")
    pay_intl_air_front_warehouse: Optional[float] = Field(None, description="国际空运-前置仓")
    pay_intl_air_other_fee: Optional[float] = Field(None, description="国际空运-其他费用")
    pay_intl_air_remark: Optional[str] = Field(None, description="国际空运-备注")
    
    # (3) 应付款项 - [2] 汽运信息
    pay_trucking_subtotal: Optional[float] = Field(None, description="汽运-应付小计")
    pay_trucking_date: Optional[str] = Field(None, description="汽运-托运日期 (YYYY-MM-DD)")
    pay_trucking_outsource_unit: Optional[str] = Field(None, description="汽运-外发单位")
    pay_trucking_pieces: Optional[int] = Field(None, description="汽运-件数")
    pay_trucking_weight: Optional[float] = Field(None, description="汽运-重量")
    pay_trucking_volume: Optional[float] = Field(None, description="汽运-体积")
    pay_trucking_unit_price: Optional[float] = Field(None, description="汽运-单价")
    pay_trucking_freight: Optional[float] = Field(None, description="汽运-运费")
    pay_trucking_doc_fee: Optional[float] = Field(None, description="汽运-制单费")
    pay_trucking_other_fee: Optional[float] = Field(None, description="汽运-其他费用")
    pay_trucking_remark: Optional[str] = Field(None, description="汽运-备注")
    
    # (3) 应付款项 - [3] 国内空运信息
    pay_dom_air_subtotal: Optional[float] = Field(None, description="国内空运-应付小计")
    pay_dom_air_date: Optional[str] = Field(None, description="国内空运-托运日期 (YYYY-MM-DD)")
    pay_dom_air_outsource_unit: Optional[str] = Field(None, description="国内空运-外发单位")
    pay_dom_air_origin: Optional[str] = Field(None, description="国内空运-始发站")
    pay_dom_air_destination: Optional[str] = Field(None, description="国内空运-到达站")
    pay_dom_air_airline: Optional[str] = Field(None, description="国内空运-航空公司")
    pay_dom_air_airline_unit: Optional[str] = Field(None, description="国内空运-航空单位")
    pay_dom_air_flight_doc_no: Optional[str] = Field(None, description="国内空运-航空单号")
    pay_dom_air_flight_no: Optional[str] = Field(None, description="国内空运-航班号")
    pay_dom_air_flight_date: Optional[str] = Field(None, description="国内空运-航班日期 (YYYY-MM-DD)")
    pay_dom_air_pieces: Optional[int] = Field(None, description="国内空运-件数")
    pay_dom_air_weight: Optional[float] = Field(None, description="国内空运-重量")
    pay_dom_air_chargeable_weight: Optional[float] = Field(None, description="国内空运-计费重量")
    pay_dom_air_rate: Optional[float] = Field(None, description="国内空运-费率")
    pay_dom_air_freight: Optional[float] = Field(None, description="国内空运-运费")
    pay_dom_air_other_fee: Optional[float] = Field(None, description="国内空运-其他费用")
    pay_dom_air_remark: Optional[str] = Field(None, description="国内空运-备注")
    
    # (3) 应付款项 - [4] 报关信息
    pay_customs_subtotal: Optional[float] = Field(None, description="报关-应付小计")
    pay_customs_date: Optional[str] = Field(None, description="报关-报关日期 (YYYY-MM-DD)")
    pay_customs_agent: Optional[str] = Field(None, description="报关-报关代理")
    pay_customs_fee: Optional[float] = Field(None, description="报关-报关费")
    pay_customs_continuation_sheet_fee: Optional[float] = Field(None, description="报关-续页费")
    pay_customs_inspection_delete_fee: Optional[float] = Field(None, description="报关-查验费/删单费")
    pay_customs_rebate: Optional[float] = Field(None, description="报关-回扣栏")
    pay_customs_other_fee: Optional[float] = Field(None, description="报关-其他费用")
    pay_customs_remark: Optional[str] = Field(None, description="报关-备注")
    
    # (3) 应付款项 - [5] 地面操作信息
    pay_ground_subtotal: Optional[float] = Field(None, description="地面操作-应付小计")
    pay_ground_date: Optional[str] = Field(None, description="地面操作-托运日期 (YYYY-MM-DD)")
    pay_ground_outsource_unit: Optional[str] = Field(None, description="地面操作-外发单位")
    pay_ground_chargeable_weight: Optional[float] = Field(None, description="地面操作-计费重量")
    pay_ground_rate: Optional[float] = Field(None, description="地面操作-费率")
    pay_ground_freight: Optional[float] = Field(None, description="地面操作-运费")
    pay_ground_lading_express_fee: Optional[float] = Field(None, description="地面操作-提单费/快件处置费")
    pay_ground_security_customs_fee: Optional[float] = Field(None, description="地面操作-安检费/报关费")
    pay_ground_pallet_exit_fee: Optional[float] = Field(None, description="地面操作-打板费/退场费")
    pay_ground_other_fee: Optional[float] = Field(None, description="地面操作-其他费用")
    pay_ground_remark: Optional[str] = Field(None, description="地面操作-备注")
    
    # (3) 应付款项 - 合计
    pay_total: Optional[float] = Field(None, description="应付合计")
    
    # (4) 销售提成
    salesperson: Optional[str] = Field(None, description="业务员")
    commission_amount: Optional[float] = Field(None, description="提成金额")
    
    # (5) 经营信息
    profit: Optional[float] = Field(None, description="利润")
    profit_margin: Optional[float] = Field(None, description="利润率")


class CostConsignmentCreate(CostRegistrationSave):
    """新增 单据费用明细 请求结构"""
    pass


class CostConsignmentUpdate(CostRegistrationSave):
    """修改 单据费用明细 请求结构"""
    pass


class CostConsignmentQuery(BaseModel):
    """单据信息-列表 查询参数"""
    start_warehouse_date: Optional[str] = Field(None, description="进仓开始日期 (YYYY-MM-DD)")
    end_warehouse_date: Optional[str] = Field(None, description="进仓结束日期 (YYYY-MM-DD)")
    customer_name: Optional[str] = Field(None, description="客户名称 (模糊匹配)")
    agent: Optional[str] = Field(None, description="代理单位 (模糊匹配)")
    flight_doc_no: Optional[str] = Field(None, description="航司单号/航班单号 (模糊匹配)")
    flight_no: Optional[str] = Field(None, description="航班号 (模糊匹配)")
    page: Optional[int] = Field(1, ge=1, description="页码")
    pageSize: Optional[int] = Field(10, ge=1, description="每页数量")


class CostBatchDeleteRequest(BaseModel):
    """批量删除请求体"""
    ids: List[str] = Field(..., description="要删除的单据ID列表")


class CostExportExcelRequest(BaseModel):
    """导出 Excel 请求体"""
    ids: List[str] = Field(..., description="要导出的单据ID列表")
