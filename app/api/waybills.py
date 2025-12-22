"""
运单管理接口
"""
import json
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.waybill import Waybill, ExecutionStatus
from app.schemas.waybill import (
    WaybillCreate, WaybillQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_today

router = APIRouter()


@router.post("", summary="新增运单")
async def create_waybill(
    waybill: WaybillCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增运单接口
    
    - **form_data**: 表单数据（JSON格式），前端可以传入任意字段
    - 自动设置booking_date为当前日期（中国时间）
    - 所有执行状态默认为"未执行"
    - waybill_number和departure_time初始为null，由RPA后续写入
    """
    # 将form_data转换为JSON字符串
    form_data_json = json.dumps(waybill.form_data, ensure_ascii=False)
    
    # 获取当前日期（中国时间）
    booking_date = get_china_today()
    
    new_waybill = Waybill(
        form_data=form_data_json,
        booking_date=booking_date,
        airline_record_status=ExecutionStatus.NOT_EXECUTED.value,
        cargo_station_record_status=ExecutionStatus.NOT_EXECUTED.value,
        document_print_status=ExecutionStatus.NOT_EXECUTED.value
    )
    db.add(new_waybill)
    db.commit()
    db.refresh(new_waybill)
    
    # 解析form_data JSON
    form_data_dict = json.loads(new_waybill.form_data)
    
    waybill_data = {
        "id": str(new_waybill.id),
        "waybill_number": new_waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": new_waybill.airline_record_status,
        "cargo_station_record_status": new_waybill.cargo_station_record_status,
        "document_print_status": new_waybill.document_print_status,
        "departure_time": format_datetime_china(new_waybill.departure_time),
        "booking_date": new_waybill.booking_date.isoformat(),
        "created_at": format_datetime_china(new_waybill.created_at),
        "updated_at": format_datetime_china(new_waybill.updated_at)
    }
    
    return success_response(data=waybill_data, msg="运单创建成功")


@router.get("", summary="查询运单列表")
async def get_waybills(
    query: WaybillQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询运单列表接口（支持多条件筛选）
    
    查询参数：
    - **airline_record_status**: 航司录单执行状态筛选（未执行、执行中、执行失败）
    - **cargo_station_record_status**: 货站录单执行状态筛选（未执行、执行中、执行失败）
    - **document_print_status**: 单据打印执行状态筛选（未执行、执行中、执行失败）
    - **booking_date_start**: 开单日期开始（格式：YYYY-MM-DD）
    - **booking_date_end**: 开单日期结束（格式：YYYY-MM-DD）
    - **airline**: 航司（模糊搜索，从form_data中提取）
    - **destination**: 目的站（模糊搜索，从form_data中提取）
    - **flight_number**: 航班号（模糊搜索，从form_data中提取）
    - **shipper**: 托运单位（模糊搜索，从form_data中提取）
    - **waybill_number**: 运单号（模糊搜索）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    
    支持多条件组合筛选，航司、目的站、航班号、托运单位从form_data JSON中提取进行模糊搜索
    """
    # 构建查询
    query_obj = db.query(Waybill)
    
    # 执行状态筛选
    if query.airline_record_status:
        query_obj = query_obj.filter(
            Waybill.airline_record_status == query.airline_record_status
        )
    
    if query.cargo_station_record_status:
        query_obj = query_obj.filter(
            Waybill.cargo_station_record_status == query.cargo_station_record_status
        )
    
    if query.document_print_status:
        query_obj = query_obj.filter(
            Waybill.document_print_status == query.document_print_status
        )
    
    # 开单日期范围筛选
    if query.booking_date_start:
        query_obj = query_obj.filter(
            Waybill.booking_date >= query.booking_date_start
        )
    
    if query.booking_date_end:
        query_obj = query_obj.filter(
            Waybill.booking_date <= query.booking_date_end
        )
    
    # 运单号模糊搜索
    if query.waybill_number:
        query_obj = query_obj.filter(
            Waybill.waybill_number.like(f"%{query.waybill_number}%")
        )
    
    # 从form_data JSON中提取字段进行模糊搜索
    # 使用MySQL的JSON函数进行搜索（MySQL 5.7+支持）
    # 对于Text类型存储的JSON，先转换为JSON类型，然后使用JSON_EXTRACT提取字段值
    if query.airline:
        # 使用JSON_EXTRACT提取字段值，然后进行LIKE搜索
        # 如果字段不存在或值为null，JSON_EXTRACT返回null，LIKE不会匹配
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.airline"
                ),
                func.CHAR
            ).like(f"%{query.airline}%")
        )
    
    if query.destination:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.destination"
                ),
                func.CHAR
            ).like(f"%{query.destination}%")
        )
    
    if query.flight_number:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.flight_number"
                ),
                func.CHAR
            ).like(f"%{query.flight_number}%")
        )
    
    if query.shipper:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.shipper"
                ),
                func.CHAR
            ).like(f"%{query.shipper}%")
        )
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    waybills = query_obj.order_by(
        Waybill.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    waybill_list = []
    for waybill in waybills:
        # 解析form_data JSON
        form_data_dict = json.loads(waybill.form_data)
        
        waybill_list.append({
            "id": str(waybill.id),
            "waybill_number": waybill.waybill_number,
            "form_data": form_data_dict,
            "airline_record_status": waybill.airline_record_status,
            "cargo_station_record_status": waybill.cargo_station_record_status,
            "document_print_status": waybill.document_print_status,
            "departure_time": format_datetime_china(waybill.departure_time),
            "booking_date": waybill.booking_date.isoformat(),
            "created_at": format_datetime_china(waybill.created_at),
            "updated_at": format_datetime_china(waybill.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": waybill_list},
        msg="查询成功"
    )


@router.get("/{waybill_id}", summary="查询运单详情")
async def get_waybill(
    waybill_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询运单详情接口
    
    - **waybill_id**: 运单ID（字符串格式）
    """
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    # 解析form_data JSON
    form_data_dict = json.loads(waybill.form_data)
    
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at)
    }
    
    return success_response(data=waybill_data, msg="查询成功")

