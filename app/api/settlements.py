"""
结算单管理接口
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, String
from sqlalchemy.dialects.mysql import JSON
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.settlement import Settlement
from app.models.waybill import Waybill
from app.schemas.settlement import (
    SettlementCreate, SettlementQuery, SettlementUpdate
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

router = APIRouter()


@router.post("", summary="新增结算单")
async def create_settlement(
    settlement: SettlementCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增结算单接口
    
    form_data包含三大块信息：基础信息、分单信息、主单信息（所有键名使用英文，遵循snake_case命名规范）
    
    **基础信息**：
    - transport_method: 运输方式
    - airline: 所属航司（必填）
    - origin_station: 始发站
    - destination: 目的站
    - flight_number: 航班号
    - flight_date: 航班日期
    - airline_record_time: 航司录单时间（格式：YYYY-MM-DD）
    - master_airwaybill_number: 主单号（建议包含，用于关联运单表查询航司录单时间）
    - customer_name: 客户名称
    - recipient_name: 收件人名称
    - cargo_name: 货物名称
    - quantity: 件数
    - weight: 重量
    - chargeable_weight: 计费重量
    
    **分单信息**：
    - sub_rate: 费率
    - sub_airline_fee: 航空费用
    - sub_document_fee: 制单费
    - sub_telegraph_fee: 电报费
    - sub_telegraph_number: 电报号
    - sub_cca_fee: CCA费用
    - sub_packaging_fee: 包装费
    - sub_pickup_fee: 上门提货费
    - sub_airport_pickup_fee: 机场提货费
    - sub_delivery_fee: 派送费
    - sub_carrier_deduction: 承运扣款
    - sub_other_fee: 其他费用
    - sub_other_fee_remark: 其他费用备注
    - sub_total_amount: 总金额
    - settlement_method: 结算方式
    - sub_remark: 备注
    - settlement_status: 结算状态（未结算/已结算）
    
    **主单信息**：
    - master_rate: 费率
    - master_airline_fee: 航空费用
    - master_fuel_surcharge: 航空燃油费
    - master_transit_weight: 过站重量
    - master_transit_fee: 过站费
    - master_cca_cost: CCA成本
    - master_packaging_fee: 包装费
    - master_telegraph_fee: 电报费
    - master_pickup_unit: 上门提货单位
    - master_pickup_fee: 上门提货费
    - master_delivery_unit: 派送单位
    - master_airport_pickup_fee: 机场提货费
    - master_delivery_fee: 派送费
    - master_other_fee: 其他费用
    - master_total_cost: 成本总金额
    - master_remark: 备注
    - financial_review: 财务审核（未审核/已审核）
    
    所有字段都是可选的，所有字段的值都是字符串类型
    """
    # 将form_data转换为JSON字符串
    form_data_json = json.dumps(settlement.form_data, ensure_ascii=False)
    
    new_settlement = Settlement(
        form_data=form_data_json
    )
    db.add(new_settlement)
    db.commit()
    db.refresh(new_settlement)
    
    # 解析form_data JSON
    form_data_dict = json.loads(new_settlement.form_data)
    
    settlement_data = {
        "id": str(new_settlement.id),
        "form_data": form_data_dict,
        "waybill_void_status": new_settlement.waybill_void_status,
        "created_at": format_datetime_china(new_settlement.created_at),
        "updated_at": format_datetime_china(new_settlement.updated_at)
    }
    
    return success_response(data=settlement_data, msg="结算单创建成功")


@router.get("", summary="结算单列表")
async def get_settlements(
    query: SettlementQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    结算单列表接口（支持多条件筛选）
    
    查询参数：
    - **airline**: 所属航司（模糊搜索，从form_data JSON中提取）
    - **destination**: 目的站（模糊搜索，从form_data JSON中提取）
    - **customer_name**: 客户名称/发货人名称（模糊搜索，从form_data JSON中提取）
    - **flight_number**: 航班号（模糊搜索，从form_data JSON中提取）
    - **master_airwaybill_number**: 主单号（模糊搜索，从form_data JSON中提取）
    - **settlement_status**: 结算状态（精确匹配，从form_data JSON中提取，可选值：未结算、已结算）
    - **financial_review**: 财务审核状态（精确匹配，从form_data JSON中提取，可选值：未审核、已审核）
    - **airline_record_time_start**: 航司录单时间开始（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选）
    - **airline_record_time_end**: 航司录单时间结束（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    
    支持多条件组合筛选，航司录单时间从form_data JSON中提取进行日期范围筛选。列表不包含 waybill_void_status='3'（作废成功）的结算单。
    """
    # 构建基础查询：outerjoin 运单表，列表返回与时间筛选都需用到（航司录单时间优先取运单 booking_date，无则取 form_data.airline_record_time）
    query_obj = db.query(Settlement).outerjoin(
        Waybill,
        func.cast(
            func.json_extract(
                func.cast(Settlement.form_data, JSON),
                "$.master_airwaybill_number"
            ),
            String(100)
        ) == Waybill.waybill_number
    )
    # 列表不展示运单已作废成功的结算单（waybill_void_status='3' 表示作废成功）
    query_obj = query_obj.filter(Settlement.waybill_void_status != "3")

    # 从form_data JSON中提取字段进行模糊搜索
    if query.airline:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.airline"
                ),
                func.CHAR
            ).like(f"%{query.airline}%")
        )
    
    if query.destination:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.destination"
                ),
                func.CHAR
            ).like(f"%{query.destination}%")
        )
    
    if query.customer_name:
        # 客户名称可能在form_data中的不同字段，尝试多个可能的字段名
        # 如：customer_name, shipper, consignor等
        customer_name_filter = or_(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.customer_name"
                ),
                func.CHAR
            ).like(f"%{query.customer_name}%"),
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.shipper"
                ),
                func.CHAR
            ).like(f"%{query.customer_name}%"),
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.consignor"
                ),
                func.CHAR
            ).like(f"%{query.customer_name}%")
        )
        query_obj = query_obj.filter(customer_name_filter)
    
    if query.flight_number:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.flight_number"
                ),
                func.CHAR
            ).like(f"%{query.flight_number}%")
        )
    
    if query.master_airwaybill_number:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.master_airwaybill_number"
                ),
                func.CHAR
            ).like(f"%{query.master_airwaybill_number}%")
        )
    
    # 结算状态筛选（精确匹配）
    if query.settlement_status:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.settlement_status"
                ),
                func.CHAR
            ) == query.settlement_status
        )
    
    # 财务审核状态筛选（精确匹配）
    if query.financial_review:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Settlement.form_data, JSON),
                    "$.financial_review"
                ),
                func.CHAR
            ) == query.financial_review
        )
    
    # 航司录单时间范围筛选：仅按 settlements 表 form_data 中的 airline_record_time（YYYY-MM-DD 字符串）筛选
    # MySQL JSON_EXTRACT 返回的值带双引号，需用 JSON_UNQUOTE 取出纯字符串后再做区间比较
    if query.airline_record_time_start or query.airline_record_time_end:
        airline_record_time_expr = func.json_unquote(
            func.json_extract(
                func.cast(Settlement.form_data, JSON),
                "$.airline_record_time"
            )
        )
        if query.airline_record_time_start:
            start_date_str = query.airline_record_time_start.isoformat()
            query_obj = query_obj.filter(airline_record_time_expr >= start_date_str)
        if query.airline_record_time_end:
            end_date_str = query.airline_record_time_end.isoformat()
            query_obj = query_obj.filter(airline_record_time_expr <= end_date_str)
    
    # 获取总数（需要去重，因为JOIN可能产生重复）
    total = query_obj.distinct().count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    settlements = query_obj.distinct().order_by(
        Settlement.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    # 批量查询关联的运单信息（优化性能，避免N+1查询）
    # 收集所有主单号
    master_airwaybill_numbers = []
    settlement_form_data_map = {}
    for settlement in settlements:
        form_data_dict = json.loads(settlement.form_data)
        settlement_form_data_map[settlement.id] = form_data_dict
        master_airwaybill_number = form_data_dict.get("master_airwaybill_number")
        if master_airwaybill_number:
            master_airwaybill_numbers.append(master_airwaybill_number)
    
    # 批量查询Waybill，建立主单号到booking_date的映射
    waybill_map = {}
    if master_airwaybill_numbers:
        waybills = db.query(Waybill).filter(
            Waybill.waybill_number.in_(master_airwaybill_numbers)
        ).all()
        waybill_map = {waybill.waybill_number: waybill for waybill in waybills}
    
    settlement_list = []
    for settlement in settlements:
        form_data_dict = settlement_form_data_map[settlement.id]
        master_airwaybill_number = form_data_dict.get("master_airwaybill_number")
        waybill = waybill_map.get(master_airwaybill_number) if master_airwaybill_number else None
        
        # 提取指定字段
        # 航司录单时间：优先使用通过主单号关联运单表获取的值，如果关联上了并且有值则用它，如果没有关联上或没有值则使用form_data中用户输入的airline_record_time
        airline_record_time = None
        if waybill and waybill.booking_date:
            # 如果通过主单号关联上了运单表并且有值，优先使用运单表的booking_date
            airline_record_time = waybill.booking_date.isoformat()
        else:
            # 如果没有关联上或没有值，使用form_data中用户输入的airline_record_time
            airline_record_time = form_data_dict.get("airline_record_time")
        
        settlement_item = {
            "id": str(settlement.id),
            "airline_record_time": airline_record_time,  # 航司录单时间
            "airline": form_data_dict.get("airline"),  # 所属航司
            "master_airwaybill_number": master_airwaybill_number,  # 主单号
            "flight_number": form_data_dict.get("flight_number"),  # 航班号
            "destination": form_data_dict.get("destination"),  # 目的站
            "flight_date": form_data_dict.get("flight_date"),  # 航班日期
            "shipper_unit": form_data_dict.get("customer_name"),  # 托运单位（就是客户名称）
            "quantity": form_data_dict.get("quantity"),  # 件数
            "weight": form_data_dict.get("weight"),  # 重量
            "chargeable_weight": form_data_dict.get("chargeable_weight"),  # 计费重量
            "transit_weight": form_data_dict.get("master_transit_weight"),  # 过站重量
            "cargo_name": form_data_dict.get("cargo_name"),  # 货物名称
            "customer_name": form_data_dict.get("customer_name"),  # 客户名称
            "airline_rate": form_data_dict.get("sub_rate"),  # 航空费率
            "airline_fee": form_data_dict.get("sub_airline_fee"),  # 航空运价
            "packaging_fee": form_data_dict.get("sub_packaging_fee"),  # 包装费
            "pickup_fee": form_data_dict.get("sub_pickup_fee"),  # 上门提货费
            "waybill_void_status": settlement.waybill_void_status,  # 运单作废状态
            "created_at": format_datetime_china(settlement.created_at),
            "updated_at": format_datetime_china(settlement.updated_at)
        }
        
        settlement_list.append(settlement_item)
    
    return success_response(
        data={"total": total, "items": settlement_list},
        msg="查询成功"
    )


@router.get("/{settlement_id}", summary="查看结算单详情")
async def get_settlement(
    settlement_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查看结算单详情接口
    
    - **settlement_id**: 结算单ID（字符串格式）
    """
    settlement = db.query(Settlement).filter(Settlement.id == int(settlement_id)).first()
    if not settlement:
        raise NotFoundException("结算单不存在")
    
    # 解析form_data JSON
    form_data_dict = json.loads(settlement.form_data)
    
    settlement_data = {
        "id": str(settlement.id),
        "form_data": form_data_dict,
        "waybill_void_status": settlement.waybill_void_status,
        "created_at": format_datetime_china(settlement.created_at),
        "updated_at": format_datetime_china(settlement.updated_at)
    }
    
    return success_response(data=settlement_data, msg="查询成功")


@router.put("/{settlement_id}", summary="修改结算单")
async def update_settlement(
    settlement_id: str,
    payload: SettlementUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    修改结算单接口

    - **settlement_id**: 结算单ID（字符串格式）
    - **form_data**: 与新增接口结构一致，传入完整的表单数据会整体替换原结算单的 form_data（基础信息、分单信息、主单信息）。不修改 waybill_void_status（由系统根据运单作废状态同步）。
    """
    settlement = db.query(Settlement).filter(Settlement.id == int(settlement_id)).first()
    if not settlement:
        raise NotFoundException("结算单不存在")

    form_data_json = json.dumps(payload.form_data, ensure_ascii=False)
    settlement.form_data = form_data_json
    db.commit()
    db.refresh(settlement)

    form_data_dict = json.loads(settlement.form_data)
    settlement_data = {
        "id": str(settlement.id),
        "form_data": form_data_dict,
        "waybill_void_status": settlement.waybill_void_status,
        "created_at": format_datetime_china(settlement.created_at),
        "updated_at": format_datetime_china(settlement.updated_at),
    }
    return success_response(data=settlement_data, msg="结算单修改成功")

