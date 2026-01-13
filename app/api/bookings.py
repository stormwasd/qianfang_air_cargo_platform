"""
订舱管理接口
"""
import json
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from app.core.response import success_response
from app.core.exceptions import BadRequestException
from app.database import get_db, SessionLocal
from app.models.booking import Booking, BookingStatus, InvoiceStatus
from app.models.config import BusinessConfig
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
                                # 映射RPA状态到系统状态
                                # RPA status -> 系统状态："1"（执行中）、"2"（执行失败）、"3"（执行成功）
                                # 使用数据字典值存储，与运单保持一致
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    # 将数据字典值转换为BookingStatus枚举值
                                    if dict_value == "1":
                                        booking.booking_status = BookingStatus.EXECUTING.value  # "执行中"
                                    elif dict_value == "2":
                                        booking.booking_status = BookingStatus.FAILED.value  # "执行失败"
                                    elif dict_value == "3":
                                        booking.booking_status = BookingStatus.SUCCESS.value  # "执行成功"
                                    
                                    # 如果状态是成功(5)，获取运单号（仅南航）
                                    if rpa_status == 5 and not booking.master_airwaybill_number and is_china_southern_air:
                                        try:
                                            # 调用获取运单号接口（南航专用）
                                            waybill_suffix = await rpa_service.get_china_southern_air_waybill_number(
                                                settings.RPA_CHINA_SOUTHERN_AIR_QUEUE_UUID
                                            )
                                            
                                            if waybill_suffix:
                                                # 格式化运单号（南航需要加上前缀 "784-"）
                                                waybill_number = rpa_service.format_china_southern_air_waybill_number(waybill_suffix)
                                                booking.master_airwaybill_number = waybill_number
                                        except Exception as e:
                                            # 记录错误但不影响状态更新
                                            print(f"获取运单号失败: {str(e)}")
                                
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
    
    Args:
        form_data: 用户提交的表单数据
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
    
    # 处理region（省/市/区）
    # region可能是数组格式：["44", "4403", "440306"]，也可能是字符串格式："44/4403/440306"
    region = address.get("region", "")
    if isinstance(region, list):
        # 数组格式，直接取三个元素
        region_province = region[0] if len(region) > 0 else ""
        region_city = region[1] if len(region) > 1 else ""
        region_district = region[2] if len(region) > 2 else ""
    elif isinstance(region, str):
        # 字符串格式，按"/"分割
        region_parts = region.split("/") if region else []
        region_province = region_parts[0] if len(region_parts) > 0 else ""
        region_city = region_parts[1] if len(region_parts) > 1 else ""
        region_district = region_parts[2] if len(region_parts) > 2 else ""
    else:
        region_province = ""
        region_city = ""
        region_district = ""
    
    # 从form_data中提取数据（支持从contact_info中提取）
    contact_info = form_data.get("contact_info", {})
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    dangerous_goods_declaration = form_data.get("dangerous_goods_declaration", {})
    
    # address_of_the_application_executable_file_tangyi 对应 config_data.china_southern_air.booking_and_create.tangi_login.address_of_the_application_executable_file_tangyi
    # 如果不存在，则使用tangi_login.app_name作为备选
    address_of_app = tangi_login.get("address_of_the_application_executable_file_tangyi", "")
    if not address_of_app:
        address_of_app = tangi_login.get("app_name", "")
    
    # order_contact_name可能包含姓名和电话，格式如："唐文旭/13823668395"
    # 如果order_contact_phone不存在，尝试从order_contact_name中提取（按"/"分割，取第二部分）
    order_contact_name_raw = business_default.get("order_contact_name", "")
    order_contact_phone_raw = business_default.get("order_contact_phone", "")
    if not order_contact_phone_raw and order_contact_name_raw and "/" in order_contact_name_raw:
        # 从order_contact_name中提取电话（格式：姓名/电话）
        parts = order_contact_name_raw.split("/", 1)
        order_contact_name_raw = parts[0] if len(parts) > 0 else order_contact_name_raw
        order_contact_phone_raw = parts[1] if len(parts) > 1 else ""
    
    # origin_station、cargo_type、cargo_code优先从业务参数获取，如果form_data中有则覆盖
    origin_station = flight_info.get("origin_station", "") or business_default.get("origin_station", "")
    cargo_type = cargo_info.get("cargo_type", "") or business_default.get("cargo_type", "")
    cargo_code = cargo_info.get("cargo_code", "") or business_default.get("cargo_code", "")
    
    # 映射参数
    params = {
        # 从业务参数获取
        "address_of_the_application_executable_file_tangyi": address_of_app,
        "system_account": china_southern_air_login.get("system_account", ""),
        "login_password": china_southern_air_login.get("login_password", ""),
        "system_url": china_southern_air_login.get("system_url", ""),
        "region_province_shipper": region_province,
        "region_city_shipper": region_city,
        "region_city_district": region_district,
        "address_detail": address.get("detail", ""),
        "order_contact_name": order_contact_name_raw,
        "order_contact_phone": order_contact_phone_raw,
        "agent_checker_name": business_default.get("agent_checker_name", ""),
        "agent_consignor_name": business_default.get("agent_consignor_name", ""),
        "shipper": business_default.get("shipper", ""),
        "shipper_phone": business_default.get("phone", ""),
        
        # origin_station优先从业务参数获取，如果form_data中有则覆盖
        "origin_station": origin_station,
        "destination": flight_info.get("destination", ""),
        "flight_date": flight_info.get("flight_date", ""),
        "flight_number": flight_info.get("flight_number", ""),
        # cargo_type和cargo_code优先从业务参数获取，如果form_data中有则覆盖
        "cargo_type": cargo_type,
        "cargo_code": cargo_code,
        "cargo_name": cargo_info.get("cargo_name", ""),
        "quantity": cargo_info.get("quantity", ""),
        "weight": cargo_info.get("weight", ""),
        "special_cargo_code": cargo_info.get("special_cargo_code", ""),
        "consignee_phone": contact_info.get("consignee_phone", ""),
        "consignee": contact_info.get("consignee", ""),
        "oversized_cargo": cargo_info.get("oversized_cargo", "0"),
        "no_dangerous_goods": dangerous_goods_declaration.get("no_hidden_dangerous_goods", "0"),
    }
    
    return params


@router.post("", summary="确认订舱信息并提交")
async def create_booking(
    booking: BookingCreate,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认订舱信息并提交接口
    
    - **form_data**: 表单数据（JSON格式），前端可以传入任意字段
    - 自动设置booking_time为当前时间（中国时间）
    - 订舱状态默认为"未执行"
    - 开单状态默认为"未开单"
    - master_airwaybill_number初始为null，由RPA后续写入
    - 如果airline="2"（南方航空），会自动调用南航订舱RPA接口
    """
    # 将form_data转换为JSON字符串
    form_data_json = json.dumps(booking.form_data, ensure_ascii=False)
    
    # 获取当前时间（中国时间）作为订舱时间
    booking_time = get_china_now()
    
    # 解析form_data判断是否为南航
    form_data_dict = booking.form_data
    airline = form_data_dict.get("airline", "")
    is_china_southern_air = airline == "2" or airline == "南方航空"
    
    # 创建订舱记录
    new_booking = Booking(
        form_data=form_data_json,
        booking_time=booking_time,
        booking_status=BookingStatus.NOT_EXECUTED.value,
        invoice_status=InvoiceStatus.NOT_INVOICED.value
    )
    db.add(new_booking)
    db.commit()
    db.refresh(new_booking)
    
    # 如果是南航，调用RPA订舱接口
    if is_china_southern_air:
        try:
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
            
            # 调用RPA订舱接口
            rpa_response = await rpa_service.create_china_southern_air_booking(**rpa_params)
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise BadRequestException("RPA订舱接口未返回workUuid")
            
            # 保存workUuid到数据库
            # 状态设置为"执行中"
            new_booking.rpa_work_uuid = work_uuid
            new_booking.booking_status = BookingStatus.EXECUTING.value
            db.commit()
            db.refresh(new_booking)
            
            # 启动后台任务轮询RPA状态
            background_tasks.add_task(
                poll_china_southern_air_booking_status,
                booking_id=int(new_booking.id),
                work_uuid=work_uuid,
                job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID
            )
        except BadRequestException:
            raise
        except Exception as e:
            # RPA调用失败不影响订舱记录创建，但记录错误
            print(f"调用南航订舱RPA接口失败: {str(e)}")
            # 可以选择抛出异常或继续执行
            # raise BadRequestException(f"调用南航订舱RPA接口失败: {str(e)}")
    
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
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": booking_list},
        msg="查询成功"
    )

