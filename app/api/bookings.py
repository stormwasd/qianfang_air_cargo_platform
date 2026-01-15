"""
订舱管理接口
"""
import json
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from app.core.response import success_response
from app.core.exceptions import BadRequestException, NotFoundException
from app.database import get_db, SessionLocal
from app.models.booking import Booking, BookingStatus, InvoiceStatus
from app.models.config import BusinessConfig
from app.models.settlement import Settlement
from app.schemas.booking import (
    BookingCreate, BookingQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_now
from app.services.rpa_service import rpa_service
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value
from app.config import settings

router = APIRouter()


def poll_china_southern_air_booking_status(booking_id: int, work_uuid: str, job_uuid: str):
    """
    轮询南航订舱RPA状态的后台任务
    
    Args:
        booking_id: 订舱ID
        work_uuid: RPA workUuid
        job_uuid: RPA jobUuid
    """
    import asyncio
    from app.database import SessionLocal
    
    async def _poll():
        # 创建新的数据库会话（因为后台任务在独立线程中运行）
        db_session = SessionLocal()
        try:
            # 首先检查订舱是否存在，并判断是否为南航
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            # 判断是否为南航（只有南航才需要轮询RPA状态）
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            if not is_china_southern_air:
                print(f"订舱不是南航，停止轮询: {booking_id}, airline={airline}")
                return
            
            # 从配置文件读取轮询参数
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                # 等待一段时间后查询
                await asyncio.sleep(poll_interval)
                
                # 查询RPA订舱状态（仅南航）
                try:
                    status_data = await rpa_service.query_china_southern_air_booking_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            # 更新订舱状态
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                # 映射RPA状态到系统数据字典的值
                                # RPA status -> 数据字典值："1"（执行中）、"2"（执行失败）、"3"（执行成功）
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    booking.booking_status = dict_value
                                
                                # 如果状态是成功(5)，获取运单号（仅南航）
                                if rpa_status == 5 and is_china_southern_air:
                                    try:
                                        # 使用本次创建的queue_uuid获取运单号
                                        if booking.rpa_queue_uuid:
                                            waybill_suffix = await rpa_service.get_china_southern_air_waybill_number(
                                                booking.rpa_queue_uuid
                                            )
                                            
                                            if waybill_suffix:
                                                # 格式化运单号（南航需要加上前缀 "784-"）
                                                waybill_number = rpa_service.format_china_southern_air_waybill_number(waybill_suffix)
                                                booking.master_airwaybill_number = waybill_number
                                            
                                            # 无论是否成功获取运单号，都要删除队列
                                            if booking.rpa_queue_id:
                                                try:
                                                    await rpa_service.delete_queue(booking.rpa_queue_id)
                                                    # 清空队列信息
                                                    booking.rpa_queue_uuid = None
                                                    booking.rpa_queue_id = None
                                                except Exception as delete_error:
                                                    # 删除队列失败不影响主流程，只记录错误
                                                    print(f"删除队列失败: {str(delete_error)}")
                                        else:
                                            print(f"订舱 {booking_id} 没有queue_uuid，无法获取运单号")
                                    except Exception as e:
                                        # 记录错误但不影响状态更新
                                        print(f"获取运单号失败: {str(e)}")
                                        # 即使获取运单号失败，也要尝试删除队列
                                        booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                                        if booking and booking.rpa_queue_id:
                                            try:
                                                await rpa_service.delete_queue(booking.rpa_queue_id)
                                                booking.rpa_queue_uuid = None
                                                booking.rpa_queue_id = None
                                            except Exception as delete_error:
                                                print(f"删除队列失败: {str(delete_error)}")
                                
                                # 如果状态是失败(3)，也需要清理队列
                                elif rpa_status == 3:
                                    if booking.rpa_queue_id:
                                        try:
                                            await rpa_service.delete_queue(booking.rpa_queue_id)
                                            booking.rpa_queue_uuid = None
                                            booking.rpa_queue_id = None
                                        except Exception as delete_error:
                                            print(f"删除队列失败: {str(delete_error)}")
                                
                                db_session.commit()
                            
                            # 如果状态是成功(5)或失败(3)，停止轮询
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    # 记录错误但继续轮询
                    print(f"轮询南航订舱RPA状态失败: {str(e)}")
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


def _get_business_config(db: Session) -> dict:
    """
    获取业务参数配置
    
    Returns:
        业务参数配置字典，如果不存在则返回空字典
    """
    config = db.query(BusinessConfig).first()
    if not config:
        return {}
    return json.loads(config.config_data)


def _extract_china_southern_air_params(form_data: dict, business_config: dict) -> dict:
    """
    提取并映射南航订舱RPA接口所需的参数
    
    参数优先级：
    1. 优先使用form_data中的值
    2. 如果form_data中没有，则从业务参数配置中的南航数据部分获取
    
    Args:
        form_data: 用户提交的表单数据（从booking表的form_data字段获取）
        business_config: 业务参数配置
    
    Returns:
        映射后的参数字典
    """
    # 从业务参数中获取南航配置
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    
    # 获取各个配置组
    tangi_login = booking_and_create_config.get("tangi_login", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    business_default = booking_and_create_config.get("business_default", {})
    address = business_default.get("address", {})
    
    # 从form_data中提取数据
    contact_info = form_data.get("contact_info", {})
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    dangerous_goods_declaration = form_data.get("dangerous_goods_declaration", {})
    
    # 处理region（省/市/区）- 优先从form_data获取，如果没有则从业务参数配置获取
    # 先尝试从form_data中获取address信息
    form_address = form_data.get("address", {})
    form_region = form_address.get("region", "")
    
    # 如果form_data中没有region，则从业务参数配置获取
    if not form_region:
        form_region = address.get("region", "")
    
    # 处理region格式（可能是数组或字符串）
    if isinstance(form_region, list):
        # 数组格式，直接取三个元素
        region_province = form_region[0] if len(form_region) > 0 else ""
        region_city = form_region[1] if len(form_region) > 1 else ""
        region_district = form_region[2] if len(form_region) > 2 else ""
    elif isinstance(form_region, str):
        # 字符串格式，按"/"分割
        region_parts = form_region.split("/") if form_region else []
        region_province = region_parts[0] if len(region_parts) > 0 else ""
        region_city = region_parts[1] if len(region_parts) > 1 else ""
        region_district = region_parts[2] if len(region_parts) > 2 else ""
    else:
        region_province = ""
        region_city = ""
        region_district = ""
    
    # address_detail：优先从form_data获取，如果没有则从业务参数配置获取
    address_detail = form_address.get("detail", "") or address.get("detail", "")
    
    # address_of_the_application_executable_file_tangyi：从业务参数配置获取（这个参数通常不在form_data中）
    address_of_app = tangi_login.get("address_of_the_application_executable_file_tangyi", "")
    if not address_of_app:
        address_of_app = tangi_login.get("app_name", "")
    
    # order_contact_name和order_contact_phone：优先从form_data获取，如果没有则从业务参数配置获取
    order_contact_name_raw = form_data.get("order_contact_name", "") or business_default.get("order_contact_name", "")
    order_contact_phone_raw = form_data.get("order_contact_phone", "") or business_default.get("order_contact_phone", "")
    
    # 如果order_contact_phone不存在，尝试从order_contact_name中提取（按"/"分割，取第二部分）
    if not order_contact_phone_raw and order_contact_name_raw and "/" in order_contact_name_raw:
        # 从order_contact_name中提取电话（格式：姓名/电话）
        parts = order_contact_name_raw.split("/", 1)
        order_contact_name_raw = parts[0] if len(parts) > 0 else order_contact_name_raw
        order_contact_phone_raw = parts[1] if len(parts) > 1 else ""
    
    # 映射参数（优先使用form_data，如果没有则使用业务参数配置）
    params = {
        # 登录信息：从业务参数配置获取（这些通常不在form_data中）
        "address_of_the_application_executable_file_tangyi": address_of_app,
        "system_account": china_southern_air_login.get("system_account", ""),
        "login_password": china_southern_air_login.get("login_password", ""),
        "system_url": china_southern_air_login.get("system_url", ""),
        
        # 地址信息：优先使用form_data，如果没有则使用业务参数配置
        "region_province_shipper": region_province,
        "region_city_shipper": region_city,
        "region_city_district": region_district,
        "address_detail": address_detail,
        
        # 联系人信息：优先使用form_data，如果没有则使用业务参数配置
        "order_contact_name": order_contact_name_raw,
        "order_contact_phone": order_contact_phone_raw,
        
        # 代理信息：优先使用form_data，如果没有则使用业务参数配置
        "agent_checker_name": form_data.get("agent_checker_name", "") or business_default.get("agent_checker_name", ""),
        "agent_consignor_name": form_data.get("agent_consignor_name", "") or business_default.get("agent_consignor_name", ""),
        
        # 发货人信息：优先使用form_data，如果没有则使用业务参数配置
        "shipper": form_data.get("shipper", "") or contact_info.get("shipper", "") or business_default.get("shipper", ""),
        "shipper_phone": form_data.get("shipper_phone", "") or contact_info.get("shipper_phone", "") or business_default.get("phone", ""),
        
        # 备注和结算文件号：优先使用form_data，如果没有则使用业务参数配置
        "booking_remark": form_data.get("booking_remark", "") or business_default.get("booking_remark", ""),
        "settlement_file_number": form_data.get("settlement_file_number", "") or business_default.get("settlement_file_number", ""),
        
        # 航班信息：优先使用form_data，如果没有则使用业务参数配置
        "origin_station": flight_info.get("origin_station", "") or form_data.get("origin_station", "") or business_default.get("origin_station", ""),
        "destination": flight_info.get("destination", "") or form_data.get("destination", ""),
        "flight_date": flight_info.get("flight_date", "") or form_data.get("flight_date", ""),
        "flight_number": flight_info.get("flight_number", "") or form_data.get("flight_number", ""),
        
        # 货物信息：优先使用form_data，如果没有则使用业务参数配置
        "cargo_type": cargo_info.get("cargo_type", "") or form_data.get("cargo_type", "") or business_default.get("cargo_type", ""),
        "cargo_code": cargo_info.get("cargo_code", "") or form_data.get("cargo_code", "") or business_default.get("cargo_code", ""),
        "cargo_name": cargo_info.get("cargo_name", "") or form_data.get("cargo_name", ""),
        "quantity": cargo_info.get("quantity", "") or form_data.get("quantity", ""),
        "weight": cargo_info.get("weight", "") or form_data.get("weight", ""),
        "special_cargo_code": cargo_info.get("special_cargo_code", "") or form_data.get("special_cargo_code", "") or business_default.get("special_cargo_code", ""),
        
        # 收货人信息：优先使用form_data，如果没有则使用业务参数配置
        "consignee_phone": contact_info.get("consignee_phone", "") or form_data.get("consignee_phone", ""),
        "consignee": contact_info.get("consignee", "") or form_data.get("consignee", ""),
        
        # 其他信息：优先使用form_data，如果没有则使用默认值
        "oversized_cargo": cargo_info.get("oversized_cargo", "") or form_data.get("oversized_cargo", "0"),
        "no_dangerous_goods": dangerous_goods_declaration.get("no_hidden_dangerous_goods", "") or form_data.get("no_dangerous_goods", "0"),
    }
    
    return params


@router.post("", summary="提交订舱信息")
async def create_booking(
    booking: BookingCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    提交订舱信息接口
    
    - **form_data**: 表单数据（JSON格式），前端可以传入任意字段
    - 自动设置booking_time为当前时间（中国时间）
    - 订舱状态默认为"0"（未执行，数据字典值）
    - 开单状态默认为"未开单"
    - master_airwaybill_number初始为null，由RPA后续写入
    - 此接口仅保存订舱信息，不调用RPA接口
    """
    # 将form_data转换为JSON字符串
    form_data_json = json.dumps(booking.form_data, ensure_ascii=False)
    
    # 获取当前时间（中国时间）作为订舱时间
    booking_time = get_china_now()
    
    # 创建订舱记录
    new_booking = Booking(
        form_data=form_data_json,
        booking_time=booking_time,
        booking_status="0",  # 数据字典值："0"=未执行
        invoice_status=InvoiceStatus.NOT_INVOICED.value
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    # 解析form_data JSON
    form_data_dict = json.loads(new_booking.form_data)
    
    booking_data = {
        "id": str(new_booking.id),
        "form_data": form_data_dict,
        "booking_status": new_booking.booking_status,
        "invoice_status": new_booking.invoice_status,
        "booking_time": format_datetime_china(new_booking.booking_time),
        "master_airwaybill_number": new_booking.master_airwaybill_number,
        "rpa_work_uuid": new_booking.rpa_work_uuid,
        "created_at": format_datetime_china(new_booking.created_at),
        "updated_at": format_datetime_china(new_booking.updated_at)
    }
    
    return success_response(data=booking_data, msg="订舱信息提交成功")


@router.post("/{booking_id}/execute", summary="确认并执行订舱")
async def execute_booking(
    booking_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认并执行订舱接口
    
    此接口会：
    1. 根据订舱的airline判断是否为南航（airline="2"或"南方航空"）
    2. 如果是南航，调用南航订舱任务RPA接口
    3. 从RPA响应中提取workUuid并保存到数据库
    4. 启动后台任务轮询RPA执行状态
    
    - **booking_id**: 订舱ID（字符串格式）
    """
    # 查询订舱
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    # 解析form_data
    form_data_dict = json.loads(booking.form_data)
    airline = form_data_dict.get("airline", "")
    
    # 判断是否为南方航空
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的订舱执行")
    
    # 允许重复执行，会覆盖之前的rpa_work_uuid
    
    # 获取业务参数配置
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航订舱接口")
    
    # 提取并映射参数
    rpa_params = _extract_china_southern_air_params(form_data_dict, business_config)
    
    # 验证必填参数
    required_params = [
        "address_of_the_application_executable_file_tangyi",
        "system_account",
        "login_password",
        "system_url",
        "origin_station",
        "destination",
        "flight_date",
        "flight_number",
        "cargo_type",
        "cargo_code",
        "cargo_name",
        "quantity",
        "weight",
        "special_cargo_code",
        "shipper",
        "shipper_phone",
        "consignee",
        "consignee_phone"
    ]
    
    missing_params = [key for key in required_params if not rpa_params.get(key)]
    if missing_params:
        raise BadRequestException(f"缺少必填参数: {', '.join(missing_params)}")
    
    # 在调用RPA接口之前，先创建队列（使用固定的队列名称）
    queue_uuid = None
    queue_id = None
    try:
        # 使用固定的队列名称（从配置文件读取）
        queue_name = settings.RPA_CHINA_SOUTHERN_AIR_QUEUE_NAME
        queue_data = await rpa_service.create_queue(
            queue_name=queue_name,
            max_queue_number=999,
            is_expire=False
        )
        queue_uuid = queue_data.get("queueUUID", "")
        queue_id = str(queue_data.get("queueID", ""))
        
        if not queue_uuid:
            raise BadRequestException("创建队列失败，未返回queueUUID")
    except BadRequestException:
        raise
    except Exception as e:
        raise BadRequestException(f"创建队列失败: {str(e)}")
    
    # 调用RPA接口
    try:
        rpa_response = await rpa_service.create_china_southern_air_booking(**rpa_params)
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise BadRequestException("RPA订舱接口未返回workUuid")
        
        # 保存workUuid和队列信息到数据库
        # 状态设置为"1"（执行中），对应数据字典值="1"
        booking.rpa_work_uuid = work_uuid
        booking.rpa_queue_uuid = queue_uuid
        booking.rpa_queue_id = queue_id
        booking.booking_status = "1"  # 数据字典值："1"=执行中
        db.commit()
        db.refresh(booking)
        
        # 启动后台任务轮询RPA状态
        background_tasks.add_task(
            poll_china_southern_air_booking_status,
            booking_id=int(booking_id),
            work_uuid=work_uuid,
            job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID
        )
        
        # 解析form_data JSON
        form_data_dict = json.loads(booking.form_data)
        
        booking_data = {
            "id": str(booking.id),
            "form_data": form_data_dict,
            "booking_status": booking.booking_status,
            "invoice_status": booking.invoice_status,
            "booking_time": format_datetime_china(booking.booking_time),
            "master_airwaybill_number": booking.master_airwaybill_number,
            "rpa_work_uuid": booking.rpa_work_uuid,
            "rpa_queue_uuid": booking.rpa_queue_uuid,
            "rpa_queue_id": booking.rpa_queue_id,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        }
        
        return success_response(data=booking_data, msg="订舱执行成功，正在处理中")
        
    except BadRequestException:
        raise
    except Exception as e:
        raise BadRequestException(f"调用RPA接口失败: {str(e)}")


@router.get("", summary="订舱列表")
async def get_bookings(
    query: BookingQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    订舱列表接口（支持筛选）
    
    查询参数：
    - **airline**: 航司（模糊搜索，从form_data JSON中提取，如：南方航空、深圳航空）
    - **booking_status**: 订舱状态筛选（未执行、执行中、执行失败）
    - **invoice_status**: 开单状态筛选（未开单、成功）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    
    支持多条件组合筛选，航司从form_data JSON中提取进行模糊搜索
    """
    # 构建查询
    query_obj = db.query(Booking)
    
    # 订舱状态筛选
    if query.booking_status:
        query_obj = query_obj.filter(
            Booking.booking_status == query.booking_status
        )
    
    # 开单状态筛选
    if query.invoice_status:
        query_obj = query_obj.filter(
            Booking.invoice_status == query.invoice_status
        )
    
    # 从form_data JSON中提取航司字段进行模糊搜索
    # 使用MySQL的JSON函数进行搜索（MySQL 5.7+支持）
    if query.airline:
        query_obj = query_obj.filter(
            func.cast(
                func.json_extract(
                    func.cast(Booking.form_data, JSON), 
                    "$.airline"
                ),
                func.CHAR
            ).like(f"%{query.airline}%")
        )
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    bookings = query_obj.order_by(
        Booking.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    booking_list = []
    for booking in bookings:
        # 解析form_data JSON
        form_data_dict = json.loads(booking.form_data)
        
        # 处理bookings字段：将bookings中的数据展开到form_data中
        # 支持两种情况：
        # 1. bookings是数组：取第一个元素（通常只有一个元素）
        # 2. bookings是对象：提取fullData、visibleData或tableData的第一个元素
        processed_form_data = form_data_dict.copy()
        
        if "bookings" in processed_form_data:
            bookings_data = processed_form_data.pop("bookings")
            
            # 情况1：bookings是数组
            if isinstance(bookings_data, list) and len(bookings_data) > 0:
                # 取第一个元素，将其字段合并到form_data中
                first_booking = bookings_data[0]
                if isinstance(first_booking, dict):
                    processed_form_data.update(first_booking)
            
            # 情况2：bookings是对象（包含fullData、visibleData、tableData等）
            elif isinstance(bookings_data, dict):
                # 优先使用fullData，如果没有则使用visibleData，再没有则使用tableData
                booking_items = None
                if "fullData" in bookings_data and isinstance(bookings_data["fullData"], list) and len(bookings_data["fullData"]) > 0:
                    booking_items = bookings_data["fullData"]
                elif "visibleData" in bookings_data and isinstance(bookings_data["visibleData"], list) and len(bookings_data["visibleData"]) > 0:
                    booking_items = bookings_data["visibleData"]
                elif "tableData" in bookings_data and isinstance(bookings_data["tableData"], list) and len(bookings_data["tableData"]) > 0:
                    booking_items = bookings_data["tableData"]
                
                # 如果找到了数据数组，取第一个元素合并到form_data中
                if booking_items and len(booking_items) > 0:
                    first_booking = booking_items[0]
                    if isinstance(first_booking, dict):
                        processed_form_data.update(first_booking)
        
        booking_list.append({
            "id": str(booking.id),
            "form_data": processed_form_data,
            "booking_status": booking.booking_status,
            "invoice_status": booking.invoice_status,
            "booking_time": format_datetime_china(booking.booking_time),
            "master_airwaybill_number": booking.master_airwaybill_number,
            "rpa_work_uuid": booking.rpa_work_uuid,
            "rpa_queue_uuid": booking.rpa_queue_uuid,
            "rpa_queue_id": booking.rpa_queue_id,
            "booking_cancel_status": booking.booking_cancel_status,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": booking_list},
        msg="查询成功"
    )


def poll_china_southern_air_cancel_status(booking_id: int, work_uuid: str, job_uuid: str):
    """
    轮询南航退舱RPA状态的后台任务
    
    Args:
        booking_id: 订舱ID
        work_uuid: RPA workUuid
        job_uuid: RPA jobUuid
    """
    import asyncio
    from app.database import SessionLocal
    
    async def _poll():
        # 创建新的数据库会话（因为后台任务在独立线程中运行）
        db_session = SessionLocal()
        try:
            # 首先检查订舱是否存在，并判断是否为南航
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            # 判断是否为南航（只有南航才需要轮询RPA状态）
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            if not is_china_southern_air:
                print(f"订舱不是南航，停止轮询: {booking_id}, airline={airline}")
                return
            
            # 从配置文件读取轮询参数
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                # 等待一段时间后查询
                await asyncio.sleep(poll_interval)
                
                # 查询RPA退舱状态（仅南航）
                try:
                    status_data = await rpa_service.query_china_southern_air_cancel_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            # 更新退舱状态
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                # 映射RPA状态到系统数据字典的值
                                # RPA status -> 数据字典值："1"（退舱中）、"2"（退舱失败）、"3"（退舱成功）
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    booking.booking_cancel_status = dict_value
                                
                                db_session.commit()
                            
                            # 如果状态是成功(5)或失败(3)，停止轮询
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    # 记录错误但继续轮询
                    print(f"轮询南航退舱RPA状态失败: {str(e)}")
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


@router.post("/{booking_id}/cancel", summary="退舱")
async def cancel_booking(
    booking_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    退舱接口
    
    此接口会：
    1. 根据订舱的airline判断是否为南航（airline="2"或"南方航空"）
    2. 如果是南航，从master_airwaybill_number中提取运单号后八位（去除"784-"前缀）
    3. 从业务参数配置中获取system_url、system_account、login_password
    4. 调用南航退舱任务RPA接口
    5. 从RPA响应中提取workUuid并保存到数据库（覆盖之前的rpa_work_uuid）
    6. 启动后台任务轮询RPA退舱执行状态
    7. 当RPA退舱成功时，更新退舱状态为"3"（退舱成功），保留记录用于留痕
    
    - **booking_id**: 订舱ID（字符串格式）
    """
    # 查询订舱
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    # 检查主单号是否存在
    if not booking.master_airwaybill_number:
        raise BadRequestException("主单号不存在，无法退舱")
    
    # 解析form_data
    form_data_dict = json.loads(booking.form_data)
    airline = form_data_dict.get("airline", "")
    
    # 判断是否为南方航空
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的退舱")
    
    # 提取运单号后八位（去除南航前缀"784-"）
    waybill_number_8 = rpa_service.extract_waybill_suffix_china_southern_air(booking.master_airwaybill_number)
    
    # 验证运单号后八位
    if not waybill_number_8 or len(waybill_number_8) != 8:
        raise BadRequestException(f"主单号格式不正确，无法提取后八位: {booking.master_airwaybill_number}")
    
    # 获取业务参数配置
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航退舱接口")
    
    # 从业务参数中获取南航登录配置
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    
    system_url = china_southern_air_login.get("system_url", "")
    system_account = china_southern_air_login.get("system_account", "")
    login_password = china_southern_air_login.get("login_password", "")
    
    # 验证必填参数
    if not system_url or not system_account or not login_password:
        raise BadRequestException("业务参数配置中缺少南航登录信息（system_url、system_account、login_password）")
    
    # 调用RPA退舱接口
    try:
        rpa_response = await rpa_service.cancel_china_southern_air_booking(
            system_url=system_url,
            system_account=system_account,
            login_password=login_password,
            waybill_number_8=waybill_number_8
        )
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise BadRequestException("RPA退舱接口未返回workUuid")
        
        # 保存workUuid到数据库（覆盖之前的rpa_work_uuid）
        # 状态设置为"1"（退舱中），对应数据字典值="1"
        booking.rpa_work_uuid = work_uuid
        booking.booking_cancel_status = "1"  # 数据字典值："1"=退舱中
        db.commit()
        db.refresh(booking)
        
        # 启动后台任务轮询RPA退舱状态
        background_tasks.add_task(
            poll_china_southern_air_cancel_status,
            booking_id=int(booking_id),
            work_uuid=work_uuid,
            job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID
        )
        
        # 解析form_data JSON
        form_data_dict = json.loads(booking.form_data)
        
        booking_data = {
            "id": str(booking.id),
            "form_data": form_data_dict,
            "booking_status": booking.booking_status,
            "invoice_status": booking.invoice_status,
            "booking_time": format_datetime_china(booking.booking_time),
            "master_airwaybill_number": booking.master_airwaybill_number,
            "rpa_work_uuid": booking.rpa_work_uuid,
            "rpa_queue_uuid": booking.rpa_queue_uuid,
            "rpa_queue_id": booking.rpa_queue_id,
            "booking_cancel_status": booking.booking_cancel_status,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        }
        
        return success_response(data=booking_data, msg="退舱成功，正在处理中")
        
    except BadRequestException:
        raise
    except Exception as e:
        raise BadRequestException(f"调用RPA退舱接口失败: {str(e)}")


def poll_china_southern_air_direct_invoice_status(booking_id: int, work_uuid: str, job_uuid: str):
    """
    轮询南航直接开单RPA状态的后台任务
    
    Args:
        booking_id: 订舱ID
        work_uuid: RPA workUuid
        job_uuid: RPA jobUuid
    """
    import asyncio
    
    async def _poll():
        # 创建新的数据库会话（因为后台任务在独立线程中运行）
        db_session = SessionLocal()
        try:
            # 首先检查订舱是否存在，并判断是否为南航
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            # 判断是否为南航（只有南航才需要轮询RPA状态）
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            
            if not is_china_southern_air:
                print(f"订舱 {booking_id} 不是南航，停止轮询")
                return
            
            # 获取队列信息（从rpa_queue_uuids字段获取）
            queues_info = {}
            if booking.rpa_queue_uuids:
                queues_info = json.loads(booking.rpa_queue_uuids)
            
            # 轮询RPA状态
            poll_count = 0
            max_poll_count = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            while poll_count < max_poll_count:
                await asyncio.sleep(poll_interval)
                poll_count += 1
                
                try:
                    # 查询RPA状态
                    status_response = await rpa_service.query_china_southern_air_booking_status(
                        job_uuid=job_uuid
                    )
                    
                    # 从响应中提取状态信息
                    status_info = rpa_service.extract_status_from_response(status_response, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            # 更新开单状态
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                # 如果状态是成功(5)，获取队列数据并创建结算单
                                if rpa_status == 5:
                                    try:
                                        # 从四个队列中获取数据
                                        rate_data = None
                                        freight_data = None
                                        fuel_costs_data = None
                                        extended_service_fee_data = None
                                        
                                        # 获取费率
                                        if "rate" in queues_info and queues_info["rate"].get("queueUUID"):
                                            try:
                                                rate_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["rate"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取费率失败: {str(e)}")
                                        
                                        # 获取运费
                                        if "freight" in queues_info and queues_info["freight"].get("queueUUID"):
                                            try:
                                                freight_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["freight"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取运费失败: {str(e)}")
                                        
                                        # 获取燃油费
                                        if "fuel_costs" in queues_info and queues_info["fuel_costs"].get("queueUUID"):
                                            try:
                                                fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["fuel_costs"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取燃油费失败: {str(e)}")
                                        
                                        # 获取延伸服务费
                                        if "extended_service_fee" in queues_info and queues_info["extended_service_fee"].get("queueUUID"):
                                            try:
                                                extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["extended_service_fee"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取延伸服务费失败: {str(e)}")
                                        
                                        # 构建结算单数据
                                        form_data_dict = json.loads(booking.form_data)
                                        flight_info = form_data_dict.get("flight_info", {})
                                        contact_info = form_data_dict.get("contact_info", {})
                                        cargo_info = form_data_dict.get("cargo_info", {})
                                        
                                        # 获取业务参数配置中的shipper
                                        business_config = _get_business_config(db_session)
                                        customer_name = ""
                                        if business_config:
                                            china_southern_air_config = business_config.get("china_southern_air", {})
                                            booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
                                            business_default = booking_and_create_config.get("business_default", {})
                                            customer_name = business_default.get("shipper", "")
                                        
                                        # 获取RPA调用时间（精确到日）
                                        rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                                        
                                        # 构建结算单数据
                                        settlement_data = {
                                            "airline_record_time": rpa_call_time,
                                            "settlement_method": "1",
                                            "settlement_status": "0",
                                            "financial_review": "1",
                                            "master_airwaybill_number": booking.master_airwaybill_number or "",
                                            "transport_method": "0",
                                            "airline": "2",  # 南航是2
                                            "origin_station": flight_info.get("origin_station", ""),
                                            "destination": flight_info.get("destination", ""),
                                            "flight_number": flight_info.get("flight_number", ""),
                                            "flight_date": flight_info.get("flight_date", ""),
                                            "customer_name": customer_name,
                                            "recipient_name": contact_info.get("consignee", ""),
                                            "cargo_name": cargo_info.get("cargo_name", ""),
                                            "quantity": cargo_info.get("quantity", ""),
                                            "weight": cargo_info.get("weight", ""),
                                            "chargeable_weight": "1",
                                            "sub_rate": "1",
                                            "sub_airline_fee": "1",
                                            "sub_document_fee": "1",
                                            "sub_telegraph_fee": "1",
                                            "sub_telegraph_number": "1",
                                            "sub_cca_fee": "1",
                                            "sub_packaging_fee": "1",
                                            "sub_pickup_fee": "1",
                                            "sub_airport_pickup_fee": "1",
                                            "sub_delivery_fee": "1",
                                            "sub_carrier_deduction": "1",
                                            "sub_other_fee": "1",
                                            "sub_other_fee_remark": "1",
                                            "sub_total_amount": "1",
                                            "sub_remark": "1",
                                            "master_rate": rate_data.strip('"').strip("'") if rate_data else "1",
                                            "master_airline_fee": freight_data.strip('"').strip("'") if freight_data else "1",
                                            "master_fuel_surcharge": fuel_costs_data.strip('"').strip("'") if fuel_costs_data else "1",
                                            "master_transit_weight": "1",
                                            "master_transit_fee": extended_service_fee_data.strip('"').strip("'") if extended_service_fee_data else "1",
                                            "master_cca_cost": "1",
                                            "master_packaging_fee": "1",
                                            "master_telegraph_fee": "1",
                                            "master_pickup_unit": "1",
                                            "master_pickup_fee": "1",
                                            "master_delivery_unit": "1",
                                            "master_airport_pickup_fee": "1",
                                            "master_delivery_fee": "1",
                                            "master_other_fee": "1",
                                            "master_total_cost": "1",
                                            "master_remark": "1"
                                        }
                                        
                                        # 创建结算单
                                        try:
                                            settlement = Settlement(
                                                form_data=json.dumps(settlement_data, ensure_ascii=False)
                                            )
                                            db_session.add(settlement)
                                            db_session.commit()
                                            
                                            # 更新订舱的开单状态为成功
                                            booking.invoice_status = "成功"
                                        except Exception as e:
                                            print(f"创建结算单失败: {str(e)}")
                                    finally:
                                        # 无论是否成功获取数据和创建结算单，都删除所有队列
                                        for queue_key, queue_data in queues_info.items():
                                            if queue_data.get("queueID"):
                                                try:
                                                    await rpa_service.delete_queue(queue_data["queueID"])
                                                except Exception as delete_error:
                                                    print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                        # 清空队列信息
                                        booking.rpa_queue_uuids = None
                                        db_session.commit()
                                
                                # 如果状态是失败(3)，也需要清理队列
                                elif rpa_status == 3:
                                    if queues_info:
                                        for queue_key, queue_data in queues_info.items():
                                            if queue_data.get("queueID"):
                                                try:
                                                    await rpa_service.delete_queue(queue_data["queueID"])
                                                except Exception as delete_error:
                                                    print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                        # 清空队列信息
                                        booking.rpa_queue_uuids = None
                                        db_session.commit()
                            
                            # 如果状态是成功(5)或失败(3)，停止轮询
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    # 记录错误但继续轮询
                    print(f"轮询南航直接开单RPA状态失败: {str(e)}")
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


@router.post("/{booking_id}/direct-invoice", summary="南航直接开单")
async def direct_invoice(
    booking_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    南航直接开单接口
    
    此接口会：
    1. 根据订舱的airline判断是否为南航（airline="2"或"南方航空"）
    2. 检查订舱是否有master_airwaybill_number
    3. 如果是南航，创建4个队列，调用南航直接开单任务RPA接口
    4. 从RPA响应中提取workUuid并保存到数据库
    5. 启动后台任务轮询RPA执行状态
    6. 当RPA执行成功后，从4个队列中获取数据，创建结算单，然后删除队列
    
    - **booking_id**: 订舱ID（字符串格式）
    """
    # 查询订舱
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    # 解析form_data
    form_data_dict = json.loads(booking.form_data)
    airline = form_data_dict.get("airline", "")
    
    # 判断是否为南方航空
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的直接开单")
    
    # 检查是否有主单号
    if not booking.master_airwaybill_number:
        raise BadRequestException("订舱尚未完成，无法进行开单操作")
    
    # 获取业务参数配置
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航直接开单接口")
    
    # 从业务参数配置中获取南航登录信息
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    
    system_url = china_southern_air_login.get("system_url", "")
    system_account = china_southern_air_login.get("system_account", "")
    login_password = china_southern_air_login.get("login_password", "")
    
    if not system_url or not system_account or not login_password:
        raise BadRequestException("业务参数配置中缺少南航登录信息")
    
    # 从master_airwaybill_number中提取waybill_number_8（以"-"分割，取最后一部分）
    waybill_number_8 = booking.master_airwaybill_number.split("-")[-1] if "-" in booking.master_airwaybill_number else booking.master_airwaybill_number
    
    # 在调用RPA接口之前，先循环创建4个队列（使用固定的队列名称）
    queue_configs = [
        {"name": settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_QUEUE_RATE, "key": "rate"},
        {"name": settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_QUEUE_FREIGHT, "key": "freight"},
        {"name": settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_QUEUE_FUEL_COSTS, "key": "fuel_costs"},
        {"name": settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_QUEUE_EXTENDED_SERVICE_FEE, "key": "extended_service_fee"}
    ]
    queues_info = {}
    try:
        for queue_config in queue_configs:
            queue_data = await rpa_service.create_queue(
                queue_name=queue_config["name"],
                max_queue_number=999,
                is_expire=False
            )
            queue_uuid = queue_data.get("queueUUID", "")
            queue_id = str(queue_data.get("queueID", ""))
            
            if not queue_uuid:
                raise BadRequestException(f"创建队列失败，未返回queueUUID: {queue_config['name']}")
            
            queues_info[queue_config["key"]] = {
                "queueUUID": queue_uuid,
                "queueID": queue_id,
                "queueName": queue_config["name"]
            }
    except BadRequestException:
        raise
    except Exception as e:
        raise BadRequestException(f"创建队列失败: {str(e)}")
    
    # 调用RPA接口
    try:
        rpa_response = await rpa_service.create_china_southern_air_direct_invoice(
            system_url=system_url,
            system_account=system_account,
            login_password=login_password,
            waybill_number_8=waybill_number_8
        )
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise BadRequestException("RPA直接开单接口未返回workUuid")
        
        # 保存workUuid和队列信息到数据库
        booking.rpa_work_uuid = work_uuid
        booking.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
        db.commit()
        db.refresh(booking)
        
        # 启动后台任务轮询RPA状态
        background_tasks.add_task(
            poll_china_southern_air_direct_invoice_status,
            booking_id=int(booking_id),
            work_uuid=work_uuid,
            job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID
        )
        
        # 解析form_data JSON
        form_data_dict = json.loads(booking.form_data)
        
        booking_data = {
            "id": str(booking.id),
            "form_data": form_data_dict,
            "booking_status": booking.booking_status,
            "invoice_status": booking.invoice_status,
            "booking_time": format_datetime_china(booking.booking_time),
            "master_airwaybill_number": booking.master_airwaybill_number,
            "rpa_work_uuid": booking.rpa_work_uuid,
            "rpa_queue_uuid": booking.rpa_queue_uuid,
            "rpa_queue_id": booking.rpa_queue_id,
            "booking_cancel_status": booking.booking_cancel_status,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        }
        
        return success_response(data=booking_data, msg="直接开单成功，正在处理中")
        
    except BadRequestException:
        # 如果RPA调用失败，也尝试删除已创建的队列
        if queues_info:
            for queue_key, queue_data in queues_info.items():
                if queue_data.get("queueID"):
                    try:
                        await rpa_service.delete_queue(queue_data["queueID"])
                    except Exception as delete_error:
                        print(f"RPA调用失败后删除队列 {queue_data['queueName']} 失败: {str(delete_error)}")
        raise
    except Exception as e:
        # 如果RPA调用失败，也尝试删除已创建的队列
        if queues_info:
            for queue_key, queue_data in queues_info.items():
                if queue_data.get("queueID"):
                    try:
                        await rpa_service.delete_queue(queue_data["queueID"])
                    except Exception as delete_error:
                        print(f"RPA调用失败后删除队列 {queue_data['queueName']} 失败: {str(delete_error)}")
        raise BadRequestException(f"调用RPA直接开单接口失败: {str(e)}")

