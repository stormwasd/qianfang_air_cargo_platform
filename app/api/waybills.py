"""
运单管理接口
"""
import json
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.mysql import JSON
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.response import success_response
from app.database import get_db
from app.models.waybill import Waybill, ExecutionStatus
from app.schemas.waybill import (
    WaybillCreate, WaybillQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_today
from app.services.rpa_service import rpa_service
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value

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
        airline_record_status="0",  # 数据字典值："0"=未开单
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
        "rpa_work_uuid": new_waybill.rpa_work_uuid,
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
    - **airline**: 航司（模糊搜索，从form_data.airline中提取）
    - **destination**: 目的站（模糊搜索，从form_data.flight_info.destination中提取）
    - **flight_number**: 航班号（模糊搜索，从form_data.flight_info.flight_number中提取）
    - **waybill_type**: 运单类型（模糊搜索，从form_data.flight_info.waybill_type中提取，仅深圳航空）
    - **shipper**: 托运单位（模糊搜索，从form_data中提取，支持深圳航空的shipper_consignee_info.shipper_unit和南方航空的contact_info.shipper_unit）
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
        # 新结构：destination在flight_info.destination中
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.flight_info.destination"
                ),
                func.CHAR
            ).like(f"%{query.destination}%")
        )
    
    if query.flight_number:
        # 新结构：flight_number在flight_info.flight_number中
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.flight_info.flight_number"
                ),
                func.CHAR
            ).like(f"%{query.flight_number}%")
        )
    
    if query.waybill_type:
        # 运单类型在flight_info.waybill_type中（仅深圳航空）
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.flight_info.waybill_type"
                ),
                func.CHAR
            ).like(f"%{query.waybill_type}%")
        )
    
    if query.shipper:
        # 新结构：shipper_unit在不同位置
        # 深圳航空：shipper_consignee_info.shipper_unit
        # 南方航空：contact_info.shipper_unit
        shipper_filter = or_(
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.shipper_consignee_info.shipper_unit"
                ),
                func.CHAR
            ).like(f"%{query.shipper}%"),
            func.cast(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.contact_info.shipper_unit"
                ),
                func.CHAR
            ).like(f"%{query.shipper}%")
        )
        query_obj = query_obj.filter(shipper_filter)
    
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
            "rpa_work_uuid": waybill.rpa_work_uuid,
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
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at)
    }
    
    return success_response(data=waybill_data, msg="查询成功")


def poll_rpa_status(waybill_id: int, work_uuid: str, job_uuid: str):
    """
    轮询RPA状态的后台任务
    
    Args:
        waybill_id: 运单ID
        work_uuid: RPA workUuid
        job_uuid: RPA jobUuid
    """
    import asyncio
    from app.database import SessionLocal
    
    async def _poll():
        # 创建新的数据库会话（因为后台任务在独立线程中运行）
        db_session = SessionLocal()
        try:
            # 首先检查运单是否存在，并判断是否为深航
            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
            if not waybill:
                print(f"运单不存在，停止轮询: {waybill_id}")
                return
            
            # 判断是否为深航（只有深航才需要轮询RPA状态）
            form_data_dict = json.loads(waybill.form_data)
            airline = form_data_dict.get("airline", "")
            is_shenzhen_air = airline == "1" or airline == "深圳航空"
            if not is_shenzhen_air:
                print(f"运单不是深航，停止轮询: {waybill_id}, airline={airline}")
                return
            
            # 从配置文件读取轮询参数
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                # 等待一段时间后查询
                await asyncio.sleep(poll_interval)
                
                # 查询RPA状态（仅深航）
                try:
                    status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            # 更新运单状态
                            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
                            if waybill:
                                # 映射RPA状态到系统数据字典的值
                                # RPA status -> 数据字典值："1"（开单中）、"2"（失败）、"3"（成功）
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    waybill.airline_record_status = dict_value
                                    
                                    # 如果状态是成功(5)，获取运单号（仅深航）
                                    if rpa_status == 5 and not waybill.waybill_number and is_shenzhen_air:
                                        try:
                                            # 调用获取运单号接口（深航专用）
                                            waybill_suffix = await rpa_service.get_shenzhen_air_waybill_number(
                                                settings.RPA_SHENZHEN_AIR_QUEUE_UUID
                                            )
                                            
                                            if waybill_suffix:
                                                # 格式化运单号（深航需要加上前缀 "479-"）
                                                waybill_number = rpa_service.format_shenzhen_air_waybill_number(waybill_suffix)
                                                waybill.waybill_number = waybill_number
                                        except Exception as e:
                                            # 记录错误但不影响状态更新
                                            print(f"获取运单号失败: {str(e)}")
                                    
                                    db_session.commit()
                                
                                # 如果状态是成功(5)或失败(3)，停止轮询
                                if rpa_status in [3, 5]:
                                    break
                except Exception as e:
                    # 记录错误但继续轮询
                    print(f"轮询RPA状态失败: {str(e)}")
                    continue
        finally:
            db_session.close()
    
    # 在新的事件循环中运行异步函数
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_poll())
    finally:
        loop.close()


@router.post("/{waybill_id}/execute", summary="确认并执行运单")
async def execute_waybill(
    waybill_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认并执行运单接口
    
    此接口会：
    1. 根据运单的airline判断是否为深航（airline="1"或"深圳航空"）
    2. 如果是深航，调用深航新增运单任务RPA接口
    3. 从RPA响应中提取workUuid并保存到数据库
    4. 启动后台任务轮询RPA执行状态
    
    - **waybill_id**: 运单ID（字符串格式）
    """
    # 查询运单
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    # 解析form_data
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    # 判断是否为深圳航空
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    if not is_shenzhen_air:
        raise BadRequestException("当前仅支持深圳航空的运单执行")
    
    # 允许重复执行，会覆盖之前的rpa_work_uuid
    
    # 从form_data中提取RPA接口所需的参数
    flight_info = form_data_dict.get("flight_info", {})
    shipper_consignee_info = form_data_dict.get("shipper_consignee_info", {})
    cargo_info = form_data_dict.get("cargo_info", {})
    
    # 提取参数（确保所有参数都有值）
    origin_station = flight_info.get("origin_station", "")
    destination = flight_info.get("destination", "")
    flight_date = flight_info.get("flight_date", "")
    flight_number = flight_info.get("flight_number", "")
    shipper_info = shipper_consignee_info.get("shipper_info", "")
    consignee_info = shipper_consignee_info.get("consignee_info", "")
    quantity = cargo_info.get("quantity", "")
    weight = cargo_info.get("weight", "")
    freight_code = cargo_info.get("freight_code", "")
    cargo_code = cargo_info.get("cargo_code", "")
    cargo_name = cargo_info.get("cargo_name", "")
    package = cargo_info.get("package", "")
    
    # 验证必填参数
    required_params = {
        "origin_station": origin_station,
        "destination": destination,
        "flight_date": flight_date,
        "flight_number": flight_number,
        "shipper_info": shipper_info,
        "consignee_info": consignee_info,
        "quantity": quantity,
        "weight": weight,
        "freight_code": freight_code,
        "cargo_code": cargo_code,
        "cargo_name": cargo_name,
        "package": package
    }
    
    missing_params = [key for key, value in required_params.items() if not value]
    if missing_params:
        raise BadRequestException(f"缺少必填参数: {', '.join(missing_params)}")
    
    # 调用RPA接口
    try:
        rpa_response = await rpa_service.create_shenzhen_air_waybill(
            origin_station=origin_station,
            destination=destination,
            flight_date=flight_date,
            flight_number=flight_number,
            shipper_info=shipper_info,
            consignee_info=consignee_info,
            quantity=quantity,
            weight=weight,
            freight_code=freight_code,
            cargo_code=cargo_code,
            cargo_name=cargo_name,
            package=package
        )
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise BadRequestException("RPA接口未返回workUuid")
        
        # 保存workUuid到数据库
        # 状态设置为"1"（开单中），对应数据字典invoice_status的value="1"
        waybill.rpa_work_uuid = work_uuid
        waybill.airline_record_status = "1"  # 数据字典值："1"=开单中
        db.commit()
        db.refresh(waybill)
        
        # 启动后台任务轮询RPA状态
        from app.config import settings
        background_tasks.add_task(
            poll_rpa_status,
            waybill_id=int(waybill_id),
            work_uuid=work_uuid,
            job_uuid=settings.RPA_SHENZHEN_AIR_JOB_UUID
        )
        
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
            "rpa_work_uuid": waybill.rpa_work_uuid,
            "created_at": format_datetime_china(waybill.created_at),
            "updated_at": format_datetime_china(waybill.updated_at)
        }
        
        return success_response(data=waybill_data, msg="运单执行成功，正在处理中")
        
    except BadRequestException:
        raise
    except Exception as e:
        raise BadRequestException(f"调用RPA接口失败: {str(e)}")

