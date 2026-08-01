"""
费用登记台数据库模型
"""
from sqlalchemy import Column, BigInteger, String, Integer, Numeric, Text, DateTime, Date
from app.database import Base
from app.utils.snowflake import generate_id
from app.utils.helpers import get_china_now


class CostRegistration(Base):
    """费用信息登记表（全局唯一记录）"""
    __tablename__ = "cost_registrations"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, comment="登记模版记录ID")
    
    # (1) 货主委托信息
    create_time = Column(DateTime(timezone=True), nullable=True, comment="制单时间")
    internal_doc_id = Column(String(100), nullable=True, comment="内部单据ID")
    warehouse_entry_date = Column(Date, nullable=True, comment="进仓日期")
    customer_name = Column(String(100), nullable=True, comment="客户名称")
    origin_destination = Column(String(100), nullable=True, comment="始发站-目的站")
    customs_declaration = Column(String(50), nullable=True, comment="报关")
    bill_of_lading = Column(String(100), nullable=True, comment="提单")
    flight_date = Column(Date, nullable=True, comment="航班日期")
    flight_no = Column(String(50), nullable=True, comment="航班号")
    flight_doc_no = Column(String(100), nullable=True, comment="航班单号")
    pieces = Column(Integer, nullable=True, comment="件数")
    actual_weight = Column(Numeric(10, 2), nullable=True, comment="实际重量")
    chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="计费重量")
    volume = Column(Numeric(10, 3), nullable=True, comment="体积")
    first_leg_weight = Column(Numeric(10, 2), nullable=True, comment="一程重量")
    agent = Column(String(100), nullable=True, comment="代理")
    remark = Column(Text, nullable=True, comment="备注")
    
    # (2) 应收款项
    unit_price = Column(Numeric(10, 2), nullable=True, comment="单价")
    receivable_freight = Column(Numeric(10, 2), nullable=True, comment="运费")
    receivable_lading_info_fee = Column(Numeric(10, 2), nullable=True, comment="提单费/信息录入费")
    receivable_split_offset_telex_fee = Column(Numeric(10, 2), nullable=True, comment="分单费/抵账费/电报费")
    receivable_customs_fee = Column(Numeric(10, 2), nullable=True, comment="报关费")
    receivable_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="续页费")
    receivable_customs_inspection_fee = Column(Numeric(10, 2), nullable=True, comment="海关查验费")
    receivable_magnetic_security_fee = Column(Numeric(10, 2), nullable=True, comment="磁检费/安检费")
    receivable_tc_express_fee = Column(Numeric(10, 2), nullable=True, comment="TC操作费/快件中心过站费")
    receivable_warehouse_ground_fee = Column(Numeric(10, 2), nullable=True, comment="前置仓/国际货站地面费")
    receivable_doc_make_fee = Column(Numeric(10, 2), nullable=True, comment="制单费")
    receivable_doc_split_fee = Column(Numeric(10, 2), nullable=True, comment="制单分单费")
    receivable_skid_fee = Column(Numeric(10, 2), nullable=True, comment="垫板费")
    receivable_pallet_packing_fee = Column(Numeric(10, 2), nullable=True, comment="打板/装箱费")
    receivable_probe_fee = Column(Numeric(10, 2), nullable=True, comment="探板费")
    receivable_consumables_fee = Column(Numeric(10, 2), nullable=True, comment="耗材费")
    receivable_first_leg_fee = Column(Numeric(10, 2), nullable=True, comment="一程费用")
    receivable_total = Column(Numeric(10, 2), nullable=True, comment="应收合计")
    receivable_agent = Column(String(100), nullable=True, comment="代理")
    
    # (3) 应付款项 - [1] 国际空运信息
    pay_intl_air_subtotal = Column(Numeric(10, 2), nullable=True, comment="国际空运-应付小计")
    pay_intl_air_date = Column(Date, nullable=True, comment="国际空运-托运日期")
    pay_intl_air_outsource_unit = Column(String(100), nullable=True, comment="国际空运-外发单位")
    pay_intl_air_origin = Column(String(50), nullable=True, comment="国际空运-始发站")
    pay_intl_air_destination = Column(String(50), nullable=True, comment="国际空运-到达站")
    pay_intl_air_airline = Column(String(100), nullable=True, comment="国际空运-航空公司")
    pay_intl_air_flight_doc_no = Column(String(100), nullable=True, comment="国际空运-航班单号/航空单号")
    pay_intl_air_flight_no = Column(String(50), nullable=True, comment="国际空运-航班号")
    pay_intl_air_flight_date = Column(Date, nullable=True, comment="国际空运-航班日期")
    pay_intl_air_pieces = Column(Integer, nullable=True, comment="国际空运-件数")
    pay_intl_air_weight = Column(Numeric(10, 2), nullable=True, comment="国际空运-重量")
    pay_intl_air_volume = Column(Numeric(10, 3), nullable=True, comment="国际空运-体积")
    pay_intl_air_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="国际空运-计费重量")
    pay_intl_air_rate = Column(Numeric(10, 2), nullable=True, comment="国际空运-费率")
    pay_intl_air_freight = Column(Numeric(10, 2), nullable=True, comment="国际空运-运费")
    pay_intl_air_lading_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-提单费")
    pay_intl_air_split_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-分单")
    pay_intl_air_borrow_magnetic_fuel_pickup_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-借单费/磁检费/燃油费/国内提货费")
    pay_intl_air_tc_network_disposal_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-TC费/入网费/国际处置费")
    pay_intl_air_customs_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-报关费")
    pay_intl_air_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-续页费")
    pay_intl_air_consumables_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-耗材费")
    pay_intl_air_front_warehouse = Column(Numeric(10, 2), nullable=True, comment="国际空运-前置仓")
    pay_intl_air_other_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-其他费用")
    pay_intl_air_remark = Column(Text, nullable=True, comment="国际空运-备注")
    
    # (3) 应付款项 - [2] 汽运信息
    pay_trucking_subtotal = Column(Numeric(10, 2), nullable=True, comment="汽运-应付小计")
    pay_trucking_date = Column(Date, nullable=True, comment="汽运-托运日期")
    pay_trucking_outsource_unit = Column(String(100), nullable=True, comment="汽运-外发单位")
    pay_trucking_pieces = Column(Integer, nullable=True, comment="汽运-件数")
    pay_trucking_weight = Column(Numeric(10, 2), nullable=True, comment="汽运-重量")
    pay_trucking_volume = Column(Numeric(10, 3), nullable=True, comment="汽运-体积")
    pay_trucking_unit_price = Column(Numeric(10, 2), nullable=True, comment="汽运-单价")
    pay_trucking_freight = Column(Numeric(10, 2), nullable=True, comment="汽运-运费")
    pay_trucking_doc_fee = Column(Numeric(10, 2), nullable=True, comment="汽运-制单费")
    pay_trucking_other_fee = Column(Numeric(10, 2), nullable=True, comment="汽运-其他费用")
    pay_trucking_remark = Column(Text, nullable=True, comment="汽运-备注")
    
    # (3) 应付款项 - [3] 国内空运信息
    pay_dom_air_subtotal = Column(Numeric(10, 2), nullable=True, comment="国内空运-应付小计")
    pay_dom_air_date = Column(Date, nullable=True, comment="国内空运-托运日期")
    pay_dom_air_outsource_unit = Column(String(100), nullable=True, comment="国内空运-外发单位")
    pay_dom_air_origin = Column(String(50), nullable=True, comment="国内空运-始发站")
    pay_dom_air_destination = Column(String(50), nullable=True, comment="国内空运-到达站")
    pay_dom_air_airline = Column(String(100), nullable=True, comment="国内空运-航空公司")
    pay_dom_air_airline_unit = Column(String(100), nullable=True, comment="国内空运-航空单位")
    pay_dom_air_flight_doc_no = Column(String(100), nullable=True, comment="国内空运-航空单号")
    pay_dom_air_flight_no = Column(String(50), nullable=True, comment="国内空运-航班号")
    pay_dom_air_flight_date = Column(Date, nullable=True, comment="国内空运-航班日期")
    pay_dom_air_pieces = Column(Integer, nullable=True, comment="国内空运-件数")
    pay_dom_air_weight = Column(Numeric(10, 2), nullable=True, comment="国内空运-重量")
    pay_dom_air_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="国内空运-计费重量")
    pay_dom_air_rate = Column(Numeric(10, 2), nullable=True, comment="国内空运-费率")
    pay_dom_air_freight = Column(Numeric(10, 2), nullable=True, comment="国内空运-运费")
    pay_dom_air_other_fee = Column(Numeric(10, 2), nullable=True, comment="国内空运-其他费用")
    pay_dom_air_remark = Column(Text, nullable=True, comment="国内空运-备注")
    
    # (3) 应付款项 - [4] 报关信息
    pay_customs_subtotal = Column(Numeric(10, 2), nullable=True, comment="报关-应付小计")
    pay_customs_date = Column(Date, nullable=True, comment="报关-报关日期")
    pay_customs_agent = Column(String(100), nullable=True, comment="报关-报关代理")
    pay_customs_fee = Column(Numeric(10, 2), nullable=True, comment="报关-报关费")
    pay_customs_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="报关-续页费")
    pay_customs_inspection_delete_fee = Column(Numeric(10, 2), nullable=True, comment="报关-查验费/删单费")
    pay_customs_rebate = Column(Numeric(10, 2), nullable=True, comment="报关-回扣栏")
    pay_customs_other_fee = Column(Numeric(10, 2), nullable=True, comment="报关-其他费用")
    pay_customs_remark = Column(Text, nullable=True, comment="报关-备注")
    
    # (3) 应付款项 - [5] 地面操作信息
    pay_ground_subtotal = Column(Numeric(10, 2), nullable=True, comment="地面操作-应付小计")
    pay_ground_date = Column(Date, nullable=True, comment="地面操作-托运日期")
    pay_ground_outsource_unit = Column(String(100), nullable=True, comment="地面操作-外发单位")
    pay_ground_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="地面操作-计费重量")
    pay_ground_rate = Column(Numeric(10, 2), nullable=True, comment="地面操作-费率")
    pay_ground_freight = Column(Numeric(10, 2), nullable=True, comment="地面操作-运费")
    pay_ground_lading_express_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-提单费/快件处置费")
    pay_ground_security_customs_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-安检费/报关费")
    pay_ground_pallet_exit_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-打板费/退场费")
    pay_ground_other_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-其他费用")
    pay_ground_remark = Column(Text, nullable=True, comment="地面操作-备注")
    
    # (3) 应付款项 - 合计
    pay_total = Column(Numeric(10, 2), nullable=True, comment="应付合计")
    
    # (4) 销售提成
    salesperson = Column(String(100), nullable=True, comment="业务员")
    commission_amount = Column(Numeric(10, 2), nullable=True, comment="提成金额")
    
    # (5) 经营信息
    profit = Column(Numeric(10, 2), nullable=True, comment="利润")
    profit_margin = Column(Numeric(10, 2), nullable=True, comment="利润率")
    
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")


class CostConsignment(Base):
    """费用单据明细表"""
    __tablename__ = "cost_consignments"
    
    id = Column(BigInteger, primary_key=True, default=generate_id, index=True, comment="费用单据明细ID")
    
    # (1) 货主委托信息
    create_time = Column(DateTime(timezone=True), nullable=True, comment="制单时间")
    internal_doc_id = Column(String(100), nullable=True, comment="内部单据ID")
    warehouse_entry_date = Column(Date, nullable=True, index=True, comment="进仓日期")
    customer_name = Column(String(100), nullable=True, index=True, comment="客户名称")
    origin_destination = Column(String(100), nullable=True, comment="始发站-目的站")
    customs_declaration = Column(String(50), nullable=True, comment="报关")
    bill_of_lading = Column(String(100), nullable=True, comment="提单")
    flight_date = Column(Date, nullable=True, comment="航班日期")
    flight_no = Column(String(50), nullable=True, index=True, comment="航班号")
    flight_doc_no = Column(String(100), nullable=True, index=True, comment="航班单号")
    pieces = Column(Integer, nullable=True, comment="件数")
    actual_weight = Column(Numeric(10, 2), nullable=True, comment="实际重量")
    chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="计费重量")
    volume = Column(Numeric(10, 3), nullable=True, comment="体积")
    first_leg_weight = Column(Numeric(10, 2), nullable=True, comment="一程重量")
    agent = Column(String(100), nullable=True, index=True, comment="代理")
    remark = Column(Text, nullable=True, comment="备注")
    
    # (2) 应收款项
    unit_price = Column(Numeric(10, 2), nullable=True, comment="单价")
    receivable_freight = Column(Numeric(10, 2), nullable=True, comment="运费")
    receivable_lading_info_fee = Column(Numeric(10, 2), nullable=True, comment="提单费/信息录入费")
    receivable_split_offset_telex_fee = Column(Numeric(10, 2), nullable=True, comment="分单费/抵账费/电报费")
    receivable_customs_fee = Column(Numeric(10, 2), nullable=True, comment="报关费")
    receivable_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="续页费")
    receivable_customs_inspection_fee = Column(Numeric(10, 2), nullable=True, comment="海关查验费")
    receivable_magnetic_security_fee = Column(Numeric(10, 2), nullable=True, comment="磁检费/安检费")
    receivable_tc_express_fee = Column(Numeric(10, 2), nullable=True, comment="TC操作费/快件中心过站费")
    receivable_warehouse_ground_fee = Column(Numeric(10, 2), nullable=True, comment="前置仓/国际货站地面费")
    receivable_doc_make_fee = Column(Numeric(10, 2), nullable=True, comment="制单费")
    receivable_doc_split_fee = Column(Numeric(10, 2), nullable=True, comment="制单分单费")
    receivable_skid_fee = Column(Numeric(10, 2), nullable=True, comment="垫板费")
    receivable_pallet_packing_fee = Column(Numeric(10, 2), nullable=True, comment="打板/装箱费")
    receivable_probe_fee = Column(Numeric(10, 2), nullable=True, comment="探板费")
    receivable_consumables_fee = Column(Numeric(10, 2), nullable=True, comment="耗材费")
    receivable_first_leg_fee = Column(Numeric(10, 2), nullable=True, comment="一程费用")
    receivable_total = Column(Numeric(10, 2), nullable=True, comment="应收合计")
    receivable_agent = Column(String(100), nullable=True, comment="代理")
    
    # (3) 应付款项 - [1] 国际空运信息
    pay_intl_air_subtotal = Column(Numeric(10, 2), nullable=True, comment="国际空运-应付小计")
    pay_intl_air_date = Column(Date, nullable=True, comment="国际空运-托运日期")
    pay_intl_air_outsource_unit = Column(String(100), nullable=True, comment="国际空运-外发单位")
    pay_intl_air_origin = Column(String(50), nullable=True, comment="国际空运-始发站")
    pay_intl_air_destination = Column(String(50), nullable=True, comment="国际空运-到达站")
    pay_intl_air_airline = Column(String(100), nullable=True, comment="国际空运-航空公司")
    pay_intl_air_flight_doc_no = Column(String(100), nullable=True, comment="国际空运-航班单号/航空单号")
    pay_intl_air_flight_no = Column(String(50), nullable=True, comment="国际空运-航班号")
    pay_intl_air_flight_date = Column(Date, nullable=True, comment="国际空运-航班日期")
    pay_intl_air_pieces = Column(Integer, nullable=True, comment="国际空运-件数")
    pay_intl_air_weight = Column(Numeric(10, 2), nullable=True, comment="国际空运-重量")
    pay_intl_air_volume = Column(Numeric(10, 3), nullable=True, comment="国际空运-体积")
    pay_intl_air_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="国际空运-计费重量")
    pay_intl_air_rate = Column(Numeric(10, 2), nullable=True, comment="国际空运-费率")
    pay_intl_air_freight = Column(Numeric(10, 2), nullable=True, comment="国际空运-运费")
    pay_intl_air_lading_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-提单费")
    pay_intl_air_split_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-分单")
    pay_intl_air_borrow_magnetic_fuel_pickup_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-借单费/磁检费/燃油费/国内提货费")
    pay_intl_air_tc_network_disposal_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-TC费/入网费/国际处置费")
    pay_intl_air_customs_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-报关费")
    pay_intl_air_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-续页费")
    pay_intl_air_consumables_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-耗材费")
    pay_intl_air_front_warehouse = Column(Numeric(10, 2), nullable=True, comment="国际空运-前置仓")
    pay_intl_air_other_fee = Column(Numeric(10, 2), nullable=True, comment="国际空运-其他费用")
    pay_intl_air_remark = Column(Text, nullable=True, comment="国际空运-备注")
    
    # (3) 应付款项 - [2] 汽运信息
    pay_trucking_subtotal = Column(Numeric(10, 2), nullable=True, comment="汽运-应付小计")
    pay_trucking_date = Column(Date, nullable=True, comment="汽运-托运日期")
    pay_trucking_outsource_unit = Column(String(100), nullable=True, comment="汽运-外发单位")
    pay_trucking_pieces = Column(Integer, nullable=True, comment="汽运-件数")
    pay_trucking_weight = Column(Numeric(10, 2), nullable=True, comment="汽运-重量")
    pay_trucking_volume = Column(Numeric(10, 3), nullable=True, comment="汽运-体积")
    pay_trucking_unit_price = Column(Numeric(10, 2), nullable=True, comment="汽运-单价")
    pay_trucking_freight = Column(Numeric(10, 2), nullable=True, comment="汽运-运费")
    pay_trucking_doc_fee = Column(Numeric(10, 2), nullable=True, comment="汽运-制单费")
    pay_trucking_other_fee = Column(Numeric(10, 2), nullable=True, comment="汽运-其他费用")
    pay_trucking_remark = Column(Text, nullable=True, comment="汽运-备注")
    
    # (3) 应付款项 - [3] 国内空运信息
    pay_dom_air_subtotal = Column(Numeric(10, 2), nullable=True, comment="国内空运-应付小计")
    pay_dom_air_date = Column(Date, nullable=True, comment="国内空运-托运日期")
    pay_dom_air_outsource_unit = Column(String(100), nullable=True, comment="国内空运-外发单位")
    pay_dom_air_origin = Column(String(50), nullable=True, comment="国内空运-始发站")
    pay_dom_air_destination = Column(String(50), nullable=True, comment="国内空运-到达站")
    pay_dom_air_airline = Column(String(100), nullable=True, comment="国内空运-航空公司")
    pay_dom_air_airline_unit = Column(String(100), nullable=True, comment="国内空运-航空单位")
    pay_dom_air_flight_doc_no = Column(String(100), nullable=True, comment="国内空运-航空单号")
    pay_dom_air_flight_no = Column(String(50), nullable=True, comment="国内空运-航班号")
    pay_dom_air_flight_date = Column(Date, nullable=True, comment="国内空运-航班日期")
    pay_dom_air_pieces = Column(Integer, nullable=True, comment="国内空运-件数")
    pay_dom_air_weight = Column(Numeric(10, 2), nullable=True, comment="国内空运-重量")
    pay_dom_air_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="国内空运-计费重量")
    pay_dom_air_rate = Column(Numeric(10, 2), nullable=True, comment="国内空运-费率")
    pay_dom_air_freight = Column(Numeric(10, 2), nullable=True, comment="国内空运-运费")
    pay_dom_air_other_fee = Column(Numeric(10, 2), nullable=True, comment="国内空运-其他费用")
    pay_dom_air_remark = Column(Text, nullable=True, comment="国内空运-备注")
    
    # (3) 应付款项 - [4] 报关信息
    pay_customs_subtotal = Column(Numeric(10, 2), nullable=True, comment="报关-应付小计")
    pay_customs_date = Column(Date, nullable=True, comment="报关-报关日期")
    pay_customs_agent = Column(String(100), nullable=True, comment="报关-报关代理")
    pay_customs_fee = Column(Numeric(10, 2), nullable=True, comment="报关-报关费")
    pay_customs_continuation_sheet_fee = Column(Numeric(10, 2), nullable=True, comment="报关-续页费")
    pay_customs_inspection_delete_fee = Column(Numeric(10, 2), nullable=True, comment="报关-查验费/删单费")
    pay_customs_rebate = Column(Numeric(10, 2), nullable=True, comment="报关-回扣栏")
    pay_customs_other_fee = Column(Numeric(10, 2), nullable=True, comment="报关-其他费用")
    pay_customs_remark = Column(Text, nullable=True, comment="报关-备注")
    
    # (3) 应付款项 - [5] 地面操作信息
    pay_ground_subtotal = Column(Numeric(10, 2), nullable=True, comment="地面操作-应付小计")
    pay_ground_date = Column(Date, nullable=True, comment="地面操作-托运日期")
    pay_ground_outsource_unit = Column(String(100), nullable=True, comment="地面操作-外发单位")
    pay_ground_chargeable_weight = Column(Numeric(10, 2), nullable=True, comment="地面操作-计费重量")
    pay_ground_rate = Column(Numeric(10, 2), nullable=True, comment="地面操作-费率")
    pay_ground_freight = Column(Numeric(10, 2), nullable=True, comment="地面操作-运费")
    pay_ground_lading_express_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-提单费/快件处置费")
    pay_ground_security_customs_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-安检费/报关费")
    pay_ground_pallet_exit_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-打板费/退场费")
    pay_ground_other_fee = Column(Numeric(10, 2), nullable=True, comment="地面操作-其他费用")
    pay_ground_remark = Column(Text, nullable=True, comment="地面操作-备注")
    
    # (3) 应付款项 - 合计
    pay_total = Column(Numeric(10, 2), nullable=True, comment="应付合计")
    
    # (4) 销售提成
    salesperson = Column(String(100), nullable=True, comment="业务员")
    commission_amount = Column(Numeric(10, 2), nullable=True, comment="提成金额")
    
    # (5) 经营信息
    profit = Column(Numeric(10, 2), nullable=True, comment="利润")
    profit_margin = Column(Numeric(10, 2), nullable=True, comment="利润率")
    
    creator_id = Column(BigInteger, nullable=True, comment="创建者ID")
    created_at = Column(DateTime(timezone=True), default=get_china_now, nullable=False, comment="创建时间")
    updated_at = Column(DateTime(timezone=True), default=get_china_now, onupdate=get_china_now, nullable=False, comment="更新时间")
