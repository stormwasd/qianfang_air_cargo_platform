"""
结算单管理接口
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.mysql import JSON
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.settlement import Settlement
from app.models.waybill import Waybill
from app.schemas.settlement import (
    SettlementCreate, SettlementQuery
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
    
    - **form_data**: 表单数据（JSON格式），前端可以传入任意字段
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
    - **booking_date_start**: 航司制单日期开始（格式：YYYY-MM-DD，通过主单号关联运单表获取开单日期）
    - **booking_date_end**: 航司制单日期结束（格式：YYYY-MM-DD，通过主单号关联运单表获取开单日期）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    
    支持多条件组合筛选，航司制单日期通过主单号关联运单表查询
    """
    # 构建基础查询，关联运单表
    # 通过结算单的form_data JSON中的主单号，关联运单表的waybill_number字段
    query_obj = db.query(Settlement).outerjoin(
        Waybill,
        func.cast(
            func.json_extract(
                func.cast(Settlement.form_data, JSON),
                "$.master_airwaybill_number"
            ),
            func.CHAR
        ) == Waybill.waybill_number
    )
    
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
    
    # 航司制单日期范围筛选（通过关联的运单表获取booking_date）
    if query.booking_date_start or query.booking_date_end:
        if query.booking_date_start:
            query_obj = query_obj.filter(
                Waybill.booking_date >= query.booking_date_start
            )
        if query.booking_date_end:
            query_obj = query_obj.filter(
                Waybill.booking_date <= query.booking_date_end
            )
    
    # 获取总数（需要去重，因为JOIN可能产生重复）
    total = query_obj.distinct().count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    settlements = query_obj.distinct().order_by(
        Settlement.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    settlement_list = []
    for settlement in settlements:
        # 解析form_data JSON
        form_data_dict = json.loads(settlement.form_data)
        
        settlement_list.append({
            "id": str(settlement.id),
            "form_data": form_data_dict,
            "created_at": format_datetime_china(settlement.created_at),
            "updated_at": format_datetime_china(settlement.updated_at)
        })
    
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
        "created_at": format_datetime_china(settlement.created_at),
        "updated_at": format_datetime_china(settlement.updated_at)
    }
    
    return success_response(data=settlement_data, msg="查询成功")

