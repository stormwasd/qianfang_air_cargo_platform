"""
订舱管理接口
"""
import json
from pathlib import Path
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.mysql import JSON
from app.core.response import success_response
from app.core.exceptions import BadRequestException, NotFoundException
from app.database import get_db, SessionLocal
from app.models.booking import Booking
from app.models.config import BusinessConfig
from app.models.settlement import Settlement
from app.schemas.booking import (
    BookingCreate, BookingQuery, BookingUpdate, BookingExecuteRequest, BookingExecuteItem, BookingExecuteResponse
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_now
from app.services.rpa_service import rpa_service
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value
from app.config import settings

router = APIRouter()
CHINA_SOUTHERN_AIR_TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2] / "documents" / "china_southern_air"
)


def _get_china_southern_air_template_path() -> Path:
    """
    获取南航订舱模板路径（兼容历史文件名）

    兼容原因：历史上模板文件名可能使用“模板/模版”两种写法。
    """
    candidates = [
        CHINA_SOUTHERN_AIR_TEMPLATE_DIR / "南航订舱模板.xlsx",
        CHINA_SOUTHERN_AIR_TEMPLATE_DIR / "南航订舱模版.xlsx",
    ]
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


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
        db_session = SessionLocal()
        try:
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            if not is_china_southern_air:
                print(f"订舱不是南航，停止轮询: {booking_id}, airline={airline}")
                return
            
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                await asyncio.sleep(poll_interval)
                
                try:
                    status_data = await rpa_service.query_china_southern_air_booking_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    booking.booking_status = dict_value
                                
                                if rpa_status == 5 and is_china_southern_air:
                                    waybill_number_retrieved = False
                                    try:
                                        if booking.rpa_queue_uuid:
                                            waybill_suffix = await rpa_service.get_china_southern_air_waybill_number(
                                                booking.rpa_queue_uuid
                                            )
                                            
                                            if waybill_suffix:
                                                waybill_number = rpa_service.format_china_southern_air_waybill_number(waybill_suffix)
                                                booking.master_airwaybill_number = waybill_number
                                                waybill_number_retrieved = True
                                            
                                            if booking.rpa_queue_id:
                                                try:
                                                    await rpa_service.delete_queue(booking.rpa_queue_id)
                                                    booking.rpa_queue_uuid = None
                                                    booking.rpa_queue_id = None
                                                except Exception as delete_error:
                                                    print(f"删除队列失败: {str(delete_error)}")
                                        else:
                                            print(f"订舱 {booking_id} 没有queue_uuid，无法获取运单号")
                                    except Exception as e:
                                        print(f"获取运单号失败: {str(e)}")
                                        booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                                        if booking and booking.rpa_queue_id:
                                            try:
                                                await rpa_service.delete_queue(booking.rpa_queue_id)
                                                booking.rpa_queue_uuid = None
                                                booking.rpa_queue_id = None
                                            except Exception as delete_error:
                                                print(f"删除队列失败: {str(delete_error)}")
                                    
                                    if not waybill_number_retrieved:
                                        booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                                        if booking:
                                            booking.booking_status = "2"  
                                            print(f"订舱 {booking_id} RPA返回成功但获取主单号失败，将状态设置为失败")
                                
                                elif rpa_status == 3:
                                    if booking.rpa_queue_id:
                                        try:
                                            await rpa_service.delete_queue(booking.rpa_queue_id)
                                            booking.rpa_queue_uuid = None
                                            booking.rpa_queue_id = None
                                        except Exception as delete_error:
                                            print(f"删除队列失败: {str(delete_error)}")
                                
                                db_session.commit()
                            
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    print(f"轮询南航订舱RPA状态失败: {str(e)}")
                    continue
        finally:
            db_session.close()
    
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
    1. 优先使用form_data.bookings[0]中的值（新的数据结构）
    2. 如果form_data.bookings[0]中没有，则从业务参数配置中的南航数据部分获取
    
    注意：form_data结构为：
    {
      "airline": "南方航空",
      "bookings": [
        {
          "origin_station": "SZX",
          "destination": "TAO",
          "flight_date": "2026-04-25",
          "flight_number": "CZ8735",
          "booking_remark_wide": "宽体备注（非必填）",
          "booking_remark_narrow": "窄体备注（非必填）",
          "cargo_type": "普货",
          "cargo_code": "9000",
          "cargo_name": "衣物",
          "quantity": "1",
          "weight": "5",
          "oversized_cargo": "0",
          "special_cargo_code": "ACO",
          "no_dangerous_goods": "0"
        }
      ]
    }
    
    Args:
        form_data: 用户提交的表单数据（从booking表的form_data字段获取）
        business_config: 业务参数配置
    
    Returns:
        映射后的参数字典
    """
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    
    tangi_login = booking_and_create_config.get("tangi_login", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    business_default = booking_and_create_config.get("business_default", {})
    
    booking_config_raw = china_southern_air_config.get("booking", {})
    booking_config = booking_config_raw.get("booking_config", {})
    
    bookings = form_data.get("bookings", [])
    booking_item = bookings[0] if bookings and len(bookings) > 0 else {}
    
    address_of_app = tangi_login.get("address_of_the_application_executable_file_tangyi", "")
    if not address_of_app:
        address_of_app = tangi_login.get("app_name", "")
    
    order_contact_name_raw = form_data.get("order_contact_name", "") or business_default.get("order_contact_name", "")
    order_contact_phone_raw = form_data.get("order_contact_phone", "") or business_default.get("order_contact_phone", "")
    
    if not order_contact_phone_raw and order_contact_name_raw and "/" in order_contact_name_raw:
        parts = order_contact_name_raw.split("/", 1)
        order_contact_name_raw = parts[0] if len(parts) > 0 else order_contact_name_raw
        order_contact_phone_raw = parts[1] if len(parts) > 1 else ""
    
    params = {
        "address_of_the_application_executable_file_tangyi": address_of_app,
        "system_account": china_southern_air_login.get("system_account", ""),
        "login_password": china_southern_air_login.get("login_password", ""),
        "system_url": china_southern_air_login.get("system_url", ""),
        
        "order_contact_name": order_contact_name_raw,
        "order_contact_phone": order_contact_phone_raw,
        
        "agent_checker_name": form_data.get("agent_checker_name", "") or business_default.get("agent_checker_name", ""),
        "agent_consignor_name": form_data.get("agent_consignor_name", "") or business_default.get("agent_consignor_name", ""),
        
        "settlement_file_number": form_data.get("settlement_file_number", "") or business_default.get("settlement_file_number", ""),
        
        "origin_station": booking_item.get("origin_station", "") or business_default.get("origin_station", ""),
        "destination": booking_item.get("destination", ""),
        "flight_date": booking_item.get("flight_date", ""),
        "flight_number": booking_item.get("flight_number", ""),
        
        "booking_remark_wide": booking_item.get("booking_remark_wide", "") or business_default.get("booking_remark_wide", ""),
        "booking_remark_narrow": booking_item.get("booking_remark_narrow", "") or business_default.get("booking_remark_narrow", ""),
        
        "cargo_type": booking_item.get("cargo_type", "") or business_default.get("cargo_type", ""),
        "cargo_code": booking_item.get("cargo_code", "") or business_default.get("cargo_code", ""),
        "cargo_name": booking_item.get("cargo_name", ""),
        "quantity": booking_item.get("quantity", ""),
        "weight": booking_item.get("weight", ""),
        "special_cargo_code": booking_item.get("special_cargo_code", "") or business_default.get("special_cargo_code", ""),
        
        "oversized_cargo": booking_item.get("oversized_cargo", "0"),
        "no_dangerous_goods": booking_item.get("no_dangerous_goods", "0"),
        
        "storage_and_transportation_precautions": booking_item.get("storage_and_transportation_precautions", ""),
        "product_name": booking_item.get("product_name", "")[0] if isinstance(booking_item.get("product_name", ""), list) and len(booking_item.get("product_name", "")) > 0 else (booking_item.get("product_name", "") if not isinstance(booking_item.get("product_name", ""), list) else ""),
        "booking_volume": booking_item.get("booking_volume", ""),
        
        "wide_body_aircraft_rules": booking_config.get("wide", "[\"35\",\"33\",\"74\",\"77\",\"78\"]"),
        "narrow_body_aircraft_rules": booking_config.get("narrow", "[\"31\",\"32\",\"73\",\"38\",\"21\"]"),
    }
    
    return params


@router.post("", summary="提交订舱信息")
async def create_booking(
    booking: BookingCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    提交订舱信息接口（支持批量提交）
    
    - **form_data**: 表单数据（JSON格式），包含航司和订舱信息数组
    - 如果`form_data.bookings`是数组且包含多个元素，会拆分为多条记录存储
    - 每条记录的`form_data.bookings`仍然是一个数组，但只包含一个元素（长度为1）
    - 自动设置booking_time为当前时间（中国时间）
    - 订舱状态默认为"0"（未执行，数据字典值）
    - 开单状态默认为"0"（未开单，数据字典值）
    - master_airwaybill_number初始为null，由RPA后续写入
    - 此接口仅保存订舱信息，不调用RPA接口
    
    示例：
    输入：
    {
      "form_data": {
        "airline": "2",
        "bookings": [
          {"origin_station": "SZX", "destination": "PEK", ...},
          {"origin_station": "CAN", "destination": "TAO", ...}
        ]
      }
    }
    
    输出：返回两条记录，每条记录的form_data.bookings只包含一个元素
    """
    import copy
    form_data_dict = copy.deepcopy(booking.form_data)
    
    bookings_list = form_data_dict.get("bookings", [])
    
    if not isinstance(bookings_list, list):
        raise BadRequestException("form_data.bookings必须是数组类型")
    
    if len(bookings_list) == 0:
        raise BadRequestException("form_data.bookings不能为空数组")
    
    booking_time = get_china_now()
    
    created_bookings = []
    try:
        for booking_item in bookings_list:
            single_form_data = copy.deepcopy(form_data_dict)
            single_form_data["bookings"] = [copy.deepcopy(booking_item)]  
            
            form_data_json = json.dumps(single_form_data, ensure_ascii=False)
            
            new_booking = Booking(
                form_data=form_data_json,
                booking_time=booking_time,
                booking_status="0",  
                invoice_status="0"  
            )
            db.add(new_booking)
            created_bookings.append(new_booking)
        
        db.commit()
        
        for new_booking in created_bookings:
            db.refresh(new_booking)
        
        booking_list = []
        for new_booking in created_bookings:
            form_data_dict_parsed = json.loads(new_booking.form_data)
            
            booking_list.append({
                "id": str(new_booking.id),
                "form_data": form_data_dict_parsed,
                "booking_status": new_booking.booking_status,
                "invoice_status": new_booking.invoice_status,
                "booking_time": format_datetime_china(new_booking.booking_time),
                "master_airwaybill_number": new_booking.master_airwaybill_number,
                "rpa_work_uuid": new_booking.rpa_work_uuid,
                "rpa_queue_uuid": new_booking.rpa_queue_uuid,
                "rpa_queue_id": new_booking.rpa_queue_id,
                "rpa_queue_uuids": new_booking.rpa_queue_uuids,
                "booking_cancel_status": new_booking.booking_cancel_status,
                "created_at": format_datetime_china(new_booking.created_at),
                "updated_at": format_datetime_china(new_booking.updated_at)
            })
        
        return success_response(
            data={"items": booking_list, "count": len(booking_list)},
            msg=f"订舱信息提交成功，共创建{len(booking_list)}条记录"
        )
    except Exception as e:
        db.rollback()
        import traceback
        print(f"创建订舱记录失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        raise BadRequestException(f"创建订舱记录失败: {str(e)}")


@router.post("/execute", summary="确认并执行订舱（批量）")
async def execute_booking(
    request: BookingExecuteRequest,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认并执行订舱接口（队列模式，支持批量）
    
    此接口会：
    1. 接收一个或多个订舱ID列表
    2. 对每个订舱ID，根据其airline判断是否为南航（airline="2"或"南方航空"）
    3. 如果是南航，创建RPA订舱任务并加入队列
    4. Worker会从队列中取出任务执行RPA调用
    5. 前端可以通过任务ID或订舱状态轮询获取执行结果
    
    - **booking_ids**: 订舱ID列表（字符串格式，至少包含一个ID）
    
    返回：
    - items: 每个订舱的执行结果列表，包含booking_id、task_id、success、error_message
    - total: 总数量
    - success_count: 成功数量
    - failed_count: 失败数量
    """
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    if not request.booking_ids or len(request.booking_ids) < 1:
        raise BadRequestException("booking_ids列表不能为空，至少需要包含一个订舱ID")
    
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航订舱接口")
    

    
    execute_results = []
    success_count = 0
    failed_count = 0
    
    for booking_id_str in request.booking_ids:
        try:
            booking_id = int(booking_id_str)
            
            booking = db.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                execute_results.append(BookingExecuteItem(
                    booking_id=booking_id_str,
                    success=False,
                    error_message="订舱不存在"
                ))
                failed_count += 1
                continue
            
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            
            is_china_southern_air = airline == "2" or airline == "南方航空"
            if not is_china_southern_air:
                execute_results.append(BookingExecuteItem(
                    booking_id=booking_id_str,
                    success=False,
                    error_message="当前仅支持南方航空的订舱执行"
                ))
                failed_count += 1
                continue
            
            existing_task = rpa_task_service.get_pending_task_for_target(
                db,
                target_type=RPATargetType.BOOKING.value,
                target_id=booking_id,
                task_type=RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_EXECUTE.value
            )
            if existing_task:
                execute_results.append(BookingExecuteItem(
                    booking_id=booking_id_str,
                    success=False,
                    error_message=f"该订舱已有待执行或执行中的订舱任务，任务ID: {existing_task.id}"
                ))
                failed_count += 1
                continue
            
            rpa_params = _extract_china_southern_air_params(form_data_dict, business_config)
            
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
                "special_cargo_code"
            ]
            
            missing_params = [key for key in required_params if not rpa_params.get(key)]
            if missing_params:
                execute_results.append(BookingExecuteItem(
                    booking_id=booking_id_str,
                    success=False,
                    error_message=f"缺少必填参数: {', '.join(missing_params)}"
                ))
                failed_count += 1
                continue
            
            task = rpa_task_service.create_task(
                db=db,
                task_type=RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_EXECUTE.value,
                target_type=RPATargetType.BOOKING.value,
                target_id=booking_id,
                params=rpa_params,
                priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
                created_by=current_user.id if current_user else None
            )
            
            execute_results.append(BookingExecuteItem(
                booking_id=booking_id_str,
                task_id=str(task.id),
                success=True,
                error_message=None
            ))
            success_count += 1
            
        except ValueError:
            execute_results.append(BookingExecuteItem(
                booking_id=booking_id_str,
                success=False,
                error_message="订舱ID格式错误，必须是数字"
            ))
            failed_count += 1
        except Exception as e:
            execute_results.append(BookingExecuteItem(
                booking_id=booking_id_str,
                success=False,
                error_message=f"处理订舱时发生错误: {str(e)}"
            ))
            failed_count += 1
    
    response_data = BookingExecuteResponse(
        items=execute_results,
        total=len(execute_results),
        success_count=success_count,
        failed_count=failed_count
    )
    
    return success_response(
        data=response_data.dict(),
        msg=f"批量执行完成，成功: {success_count}，失败: {failed_count}"
    )


@router.get("", summary="订舱列表")
async def get_bookings(
    query: BookingQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    订舱列表接口（支持筛选）
    
    查询参数：
    - **airline**: 航司（数据字典值精确匹配：1=深圳航空，2=南方航空）
    - **booking_status**: 订舱状态筛选（数据字典值：0=未执行，1=执行中，2=失败，3=成功）
    - **invoice_status**: 开单状态筛选（数据字典值：0=未开单，1=开单中，2=失败，3=成功）
    - **booking_date_start**: 订舱日期开始（格式：YYYY-MM-DD，作用于booking_time）
    - **booking_date_end**: 订舱日期结束（格式：YYYY-MM-DD，作用于booking_time）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    
    支持多条件组合筛选
    """
    query_obj = db.query(Booking)
    
    if query.booking_status:
        query_obj = query_obj.filter(
            Booking.booking_status == query.booking_status
        )
    
    if query.invoice_status:
        query_obj = query_obj.filter(
            Booking.invoice_status == query.invoice_status
        )

    if query.booking_date_start:
        start_datetime = datetime.combine(query.booking_date_start, datetime.min.time())
        query_obj = query_obj.filter(
            Booking.booking_time >= start_datetime
        )

    if query.booking_date_end:
        end_exclusive_datetime = datetime.combine(
            query.booking_date_end + timedelta(days=1),
            datetime.min.time()
        )
        query_obj = query_obj.filter(
            Booking.booking_time < end_exclusive_datetime
        )
    
    if query.airline:
        query_obj = query_obj.filter(
            func.json_unquote(
                func.json_extract(
                    func.cast(Booking.form_data, JSON), 
                    "$.airline"
                )
            ) == query.airline
        )
    
    total = query_obj.count()
    
    offset = (query.page - 1) * query.pageSize
    bookings = query_obj.order_by(
        Booking.created_at.desc(), Booking.id.desc()
    ).offset(offset).limit(query.pageSize).all()
    
    booking_list = []
    for booking in bookings:
        form_data_dict = json.loads(booking.form_data)
        
        processed_form_data = form_data_dict.copy()
        
        if "bookings" in processed_form_data:
            bookings_data = processed_form_data.pop("bookings")
            
            if isinstance(bookings_data, list) and len(bookings_data) > 0:
                first_booking = bookings_data[0]
                if isinstance(first_booking, dict):
                    processed_form_data.update(first_booking)
            
            elif isinstance(bookings_data, dict):
                booking_items = None
                if "fullData" in bookings_data and isinstance(bookings_data["fullData"], list) and len(bookings_data["fullData"]) > 0:
                    booking_items = bookings_data["fullData"]
                elif "visibleData" in bookings_data and isinstance(bookings_data["visibleData"], list) and len(bookings_data["visibleData"]) > 0:
                    booking_items = bookings_data["visibleData"]
                elif "tableData" in bookings_data and isinstance(bookings_data["tableData"], list) and len(bookings_data["tableData"]) > 0:
                    booking_items = bookings_data["tableData"]
                
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
            "booking_feedback": booking.booking_feedback,
            "created_at": format_datetime_china(booking.created_at),
            "updated_at": format_datetime_china(booking.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": booking_list},
        msg="查询成功"
    )


@router.get("/china-southern-air/template", summary="下载南航订舱模板")
async def download_china_southern_air_template(
    current_user = Depends(get_current_active_user),
):
    """
    下载南航订舱Excel模板文件

    返回：
    - xlsx文件流（attachment）
    """
    template_path = _get_china_southern_air_template_path()
    if not template_path.exists():
        raise NotFoundException("南航订舱模板不存在，请联系管理员上传模板文件")

    return FileResponse(
        path=str(template_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="南航订舱模板.xlsx",
    )


@router.get("/{booking_id}", summary="获取订舱信息")
async def get_booking(
    booking_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取订舱信息接口（用于回显）
    
    - **booking_id**: 订舱ID（字符串格式）
    
    返回完整的订舱信息，包括form_data中的所有字段，用于前端表单回显
    """
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
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
        "rpa_queue_uuids": booking.rpa_queue_uuids,
        "booking_cancel_status": booking.booking_cancel_status,
        "created_at": format_datetime_china(booking.created_at),
        "updated_at": format_datetime_china(booking.updated_at)
    }
    
    return success_response(data=booking_data, msg="查询成功")


def _convert_booking_to_waybill_form_data(booking_form_data: dict, business_config: dict) -> dict:
    """
    将订舱数据转换为运单form_data结构
    
    订舱数据结构（扁平结构）：
    {
      "airline": "2",
      "bookings": [
        {
          "origin_station": "CAN",
          "destination": "PEK",
          "flight_date": "2025-01-15",
          "shipper_unit": "XX物流公司",
          "flight_number": "CZ1234",
          "booking_remark_wide": "宽体备注（非必填）",
          "booking_remark_narrow": "窄体备注（非必填）",
          "cargo_type": "普通货物",
          "cargo_code": "0001",
          "cargo_name": "货物名称",
          "quantity": "10",
          "weight": "100.5",
          "product_name": "产品名称",
          "oversized_cargo": "否",
          "special_cargo_code": "",
          "no_dangerous_goods": "是",
          "consignee": "收货人",
          "consignee_phone": "13800138000"
        }
      ]
    }
    
    转换为运单form_data结构（嵌套结构）：
    {
      "airline": "2",
      "flight_info": { ... },
      "cargo_info": { ... },
      "contact_info": { ... },
      "dangerous_goods_declaration": { ... },
      "other_info": { ... },
      "other_fees": { ... }
    }
    
    Args:
        booking_form_data: 订舱的form_data字典
        business_config: 业务参数配置字典
    
    Returns:
        转换后的运单form_data字典
    """
    airline = booking_form_data.get("airline", "")
    
    bookings = booking_form_data.get("bookings", [])
    booking_item = bookings[0] if bookings and len(bookings) > 0 else {}
    
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    business_default = booking_and_create_config.get("business_default", {})
    default_address = business_default.get("address", {})
    
    config_region = default_address.get("region", "")
    config_detail = default_address.get("detail", "")
    
    if isinstance(config_region, list):
        region_str = "/".join(config_region) if config_region else ""
    else:
        region_str = config_region or ""
    
    waybill_form_data = {
        "airline": airline,
        
        "flight_info": {
            "origin_station": booking_item.get("origin_station", "") or business_default.get("origin_station", ""),
            "destination": booking_item.get("destination", ""),
            "flight_date": booking_item.get("flight_date", ""),
            "flight_number": booking_item.get("flight_number", ""),
            "booking_remark": booking_item.get("booking_remark", "") or booking_item.get("booking_remark_wide", "") or business_default.get("booking_remark", ""),
            "booking_remark_wide": booking_item.get("booking_remark_wide", "") or business_default.get("booking_remark_wide", ""),
            "booking_remark_narrow": booking_item.get("booking_remark_narrow", "") or business_default.get("booking_remark_narrow", "")
        },
        
        "cargo_info": {
            "cargo_type": booking_item.get("cargo_type", "") or business_default.get("cargo_type", ""),
            "cargo_code": booking_item.get("cargo_code", "") or business_default.get("cargo_code", ""),
            "cargo_name": booking_item.get("cargo_name", ""),
            "quantity": booking_item.get("quantity", ""),
            "weight": booking_item.get("weight", ""),
            "booking_volume": booking_item.get("booking_volume", ""),
            "product_name": booking_item.get("product_name", ""),
            "oversized_cargo": booking_item.get("oversized_cargo", ""),
            "special_cargo_code": booking_item.get("special_cargo_code", "") or business_default.get("special_cargo_code", "")
        },
        
        "contact_info": {
            "consignee": booking_item.get("consignee", ""),
            "consignee_phone": booking_item.get("consignee_phone", ""),
            "shipper_unit": booking_item.get("shipper_unit", ""),
            "shipper": business_default.get("shipper", ""),
            "shipper_phone": business_default.get("phone", ""),
            "address": {
                "region": region_str,
                "detail": config_detail
            }
        },
        
        "dangerous_goods_declaration": {
            "no_hidden_dangerous_goods": booking_item.get("no_dangerous_goods", ""),
            "agent_checker_signature": business_default.get("agent_checker_name", ""),
            "agent_consignor_signature": business_default.get("agent_consignor_name", "")
        },
        
        "other_info": {
            "order_contact": business_default.get("order_contact_name", ""),
            "contact_phone": business_default.get("order_contact_phone", ""),
            "settlement_file_number": business_default.get("settlement_file_number", "")
        },
        
        "other_fees": {
            "packaging_fee": "",
            "pickup_fee": "",
            "delivery_fee": ""
        }
    }
    
    return waybill_form_data


@router.get("/{booking_id}/waybill-form", summary="获取订舱数据转运单form_data（回显接口）")
async def get_booking_waybill_form(
    booking_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取订舱数据转运单form_data接口（用于运单管理界面回显）
    
    此接口用于：
    1. 用户在订舱执行后，选择来到运单管理界面进行开单
    2. 系统将订舱数据（扁平结构）转换为运单form_data结构（嵌套结构）
    3. 结合业务参数配置补充必要的字段（如shipper、shipper_phone、address等）
    4. 返回符合运单新增接口所需的form_data数据结构
    
    **参数优先级**：
    - 优先使用订舱时用户填写的数据
    - 如果订舱数据中没有，则从业务参数配置的南航部分获取
    
    **使用场景**：
    - 用户订舱执行成功后，可以选择"直接开单"或"来到运单管理界面开单"
    - 如果选择后者，前端调用此接口获取回显数据，用户可以修改后再调用新增运单接口提交
    
    - **booking_id**: 订舱ID（字符串格式）
    
    返回：
    - form_data: 符合运单新增接口所需的form_data数据结构
    - booking_id: 订舱ID
    - master_airwaybill_number: 主单号（如果已有）
    """
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    booking_form_data = json.loads(booking.form_data)
    airline = booking_form_data.get("airline", "")
    
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的订舱数据转换")
    
    business_config = _get_business_config(db)
    
    waybill_form_data = _convert_booking_to_waybill_form_data(booking_form_data, business_config)
    
    response_data = {
        "booking_id": str(booking.id),
        "form_data": waybill_form_data,
        "master_airwaybill_number": booking.master_airwaybill_number,
        "booking_status": booking.booking_status,
        "invoice_status": booking.invoice_status
    }
    
    return success_response(data=response_data, msg="查询成功")


@router.put("/{booking_id}", summary="修改订舱信息")
async def update_booking(
    booking_id: str,
    booking: BookingUpdate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    修改订舱信息接口
    
    - **booking_id**: 订舱ID（字符串格式）
    - **form_data**: 表单数据（JSON格式），包含航司和订舱信息数组
    
    说明：
    - 只能修改未执行（booking_status="0"）的订舱记录
    - 如果订舱已经执行或正在执行，不允许修改
    - form_data.bookings数组通常只包含一条记录（长度为1）
    - 修改后，booking_time保持不变，updated_at会自动更新
    """
    existing_booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not existing_booking:
        raise NotFoundException("订舱不存在")
    
    
    form_data_dict = booking.form_data.copy()
    bookings_list = form_data_dict.get("bookings", [])
    
    if not isinstance(bookings_list, list):
        raise BadRequestException("form_data.bookings必须是数组类型")
    
    if len(bookings_list) == 0:
        raise BadRequestException("form_data.bookings不能为空数组")
    
    if len(bookings_list) > 1:
        raise BadRequestException("修改订舱时，form_data.bookings只能包含一条记录")
    
    single_form_data = form_data_dict.copy()
    single_form_data["bookings"] = [bookings_list[0]]  
    
    form_data_json = json.dumps(single_form_data, ensure_ascii=False)
    
    existing_booking.form_data = form_data_json
    
    db.commit()
    db.refresh(existing_booking)
    
    form_data_dict = json.loads(existing_booking.form_data)
    
    booking_data = {
        "id": str(existing_booking.id),
        "form_data": form_data_dict,
        "booking_status": existing_booking.booking_status,
        "invoice_status": existing_booking.invoice_status,
        "booking_time": format_datetime_china(existing_booking.booking_time),
        "master_airwaybill_number": existing_booking.master_airwaybill_number,
        "rpa_work_uuid": existing_booking.rpa_work_uuid,
        "rpa_queue_uuid": existing_booking.rpa_queue_uuid,
        "rpa_queue_id": existing_booking.rpa_queue_id,
        "rpa_queue_uuids": existing_booking.rpa_queue_uuids,
        "booking_cancel_status": existing_booking.booking_cancel_status,
        "created_at": format_datetime_china(existing_booking.created_at),
        "updated_at": format_datetime_china(existing_booking.updated_at)
    }
    
    return success_response(data=booking_data, msg="订舱信息修改成功")


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
        db_session = SessionLocal()
        try:
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            if not is_china_southern_air:
                print(f"订舱不是南航，停止轮询: {booking_id}, airline={airline}")
                return
            
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                await asyncio.sleep(poll_interval)
                
                try:
                    status_data = await rpa_service.query_china_southern_air_cancel_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    booking.booking_cancel_status = dict_value
                                
                                db_session.commit()
                            
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    print(f"轮询南航退舱RPA状态失败: {str(e)}")
                    continue
        finally:
            db_session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_poll())
    finally:
        loop.close()


@router.post("/{booking_id}/cancel", summary="退舱")
async def cancel_booking(
    booking_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    退舱接口（队列模式）
    
    此接口会：
    1. 根据订舱的airline判断是否为南航（airline="2"或"南方航空"）
    2. 如果是南航，从master_airwaybill_number中提取运单号后八位（去除"784-"前缀）
    3. 从业务参数配置中获取system_url、system_account、login_password
    4. 创建RPA退舱任务并加入队列
    5. Worker会从队列中取出任务执行RPA调用
    6. 当RPA退舱成功时，更新退舱状态为"3"（退舱成功），保留记录用于留痕
    
    - **booking_id**: 订舱ID（字符串格式）
    
    返回：
    - task_id: RPA任务ID，可用于查询任务状态
    """
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    if not booking.master_airwaybill_number:
        raise BadRequestException("主单号不存在，无法退舱")
    
    form_data_dict = json.loads(booking.form_data)
    airline = form_data_dict.get("airline", "")
    
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的退舱")
    
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value
    )
    if existing_task:
        raise BadRequestException(f"该订舱已有待执行或执行中的退舱任务，任务ID: {existing_task.id}")
    
    waybill_number_8 = rpa_service.extract_waybill_suffix_china_southern_air(booking.master_airwaybill_number)
    
    if not waybill_number_8 or len(waybill_number_8) != 8:
        raise BadRequestException(f"主单号格式不正确，无法提取后八位: {booking.master_airwaybill_number}")
    
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航退舱接口")
    
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    
    system_url = china_southern_air_login.get("system_url", "")
    system_account = china_southern_air_login.get("system_account", "")
    login_password = china_southern_air_login.get("login_password", "")
    
    if not system_url or not system_account or not login_password:
        raise BadRequestException("业务参数配置中缺少南航登录信息（system_url、system_account、login_password）")
    
    rpa_params = {
        "system_url": system_url,
        "system_account": system_account,
        "login_password": login_password,
        "waybill_number_8": waybill_number_8
    }
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        params=rpa_params,
        job_uuid=settings.RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
    )
    
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
        "updated_at": format_datetime_china(booking.updated_at),
        "task_id": str(task.id)  
    }
    
    return success_response(data=booking_data, msg="退舱已加入执行队列，请等待处理")


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
        db_session = SessionLocal()
        try:
            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
            if not booking:
                print(f"订舱不存在，停止轮询: {booking_id}")
                return
            
            form_data_dict = json.loads(booking.form_data)
            airline = form_data_dict.get("airline", "")
            is_china_southern_air = airline == "2" or airline == "南方航空"
            
            if not is_china_southern_air:
                print(f"订舱 {booking_id} 不是南航，停止轮询")
                return
            
            queues_info = {}
            if booking.rpa_queue_uuids:
                queues_info = json.loads(booking.rpa_queue_uuids)
            
            poll_count = 0
            max_poll_count = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            while poll_count < max_poll_count:
                await asyncio.sleep(poll_interval)
                poll_count += 1
                
                try:
                    status_response = await rpa_service.query_china_southern_air_direct_invoice_status(
                        job_uuid=job_uuid
                    )
                    
                    status_info = rpa_service.extract_status_from_query_response(status_response, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            booking = db_session.query(Booking).filter(Booking.id == booking_id).first()
                            if booking:
                                if rpa_status == 1:
                                    booking.invoice_status = "1"
                                    db_session.commit()
                                elif rpa_status == 3:
                                    booking.invoice_status = "2"
                                    db_session.commit()
                                elif rpa_status == 5:
                                    booking.invoice_status = "3"
                                    db_session.commit()
                                
                                if rpa_status == 5:
                                    try:
                                        rate_data = None
                                        freight_data = None
                                        fuel_costs_data = None
                                        extended_service_fee_data = None
                                        
                                        if "rate" in queues_info and queues_info["rate"].get("queueUUID"):
                                            try:
                                                rate_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["rate"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取费率失败: {str(e)}")
                                        
                                        if "freight" in queues_info and queues_info["freight"].get("queueUUID"):
                                            try:
                                                freight_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["freight"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取运费失败: {str(e)}")
                                        
                                        if "fuel_costs" in queues_info and queues_info["fuel_costs"].get("queueUUID"):
                                            try:
                                                fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["fuel_costs"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取燃油费失败: {str(e)}")
                                        
                                        if "extended_service_fee" in queues_info and queues_info["extended_service_fee"].get("queueUUID"):
                                            try:
                                                extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                                                    queues_info["extended_service_fee"]["queueUUID"]
                                                )
                                            except Exception as e:
                                                print(f"获取延伸服务费失败: {str(e)}")
                                        
                                        form_data_dict = json.loads(booking.form_data)
                                        bookings = form_data_dict.get("bookings", [])
                                        booking_item = bookings[0] if bookings and len(bookings) > 0 else {}
                                        
                                        rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                                        
                                        settlement_data = {
                                            "airline_record_time": rpa_call_time,
                                            "settlement_method": "1",
                                            "settlement_status": "0",
                                            "financial_review": "0",
                                            "master_airwaybill_number": booking.master_airwaybill_number or "",
                                            "transport_method": "2",
                                            "airline": "2",  
                                            "origin_station": booking_item.get("origin_station", ""),
                                            "destination": booking_item.get("destination", ""),
                                            "flight_number": booking_item.get("flight_number", ""),
                                            "flight_date": booking_item.get("flight_date", ""),
                                            "customer_name": booking_item.get("shipper_unit", ""),
                                            "recipient_name": booking_item.get("consignee", ""),
                                            "cargo_name": booking_item.get("cargo_name", ""),
                                            "quantity": str(booking_item.get("quantity", "")),
                                            "weight": str(booking_item.get("weight", "")),
                                            "chargeable_weight": "",
                                            "sub_rate": "",
                                            "sub_airline_fee": "",
                                            "sub_document_fee": "",
                                            "sub_telegraph_fee": "",
                                            "sub_telegraph_number": "",
                                            "sub_cca_fee": "",
                                            "sub_packaging_fee": "",
                                            "sub_pickup_fee": "",
                                            "sub_airport_pickup_fee": "",
                                            "sub_delivery_fee": "",
                                            "sub_carrier_deduction": "",
                                            "sub_other_fee": "",
                                            "sub_other_fee_remark": "",
                                            "sub_total_amount": "",
                                            "sub_remark": "",
                                            "master_rate": rate_data.strip('"').strip("'") if rate_data else "",
                                            "master_airline_fee": freight_data.strip('"').strip("'") if freight_data else "",
                                            "master_fuel_surcharge": fuel_costs_data.strip('"').strip("'") if fuel_costs_data else "",
                                            "master_transit_weight": "",
                                            "master_transit_fee": extended_service_fee_data.strip('"').strip("'") if extended_service_fee_data else "",
                                            "master_cca_cost": "",
                                            "master_packaging_fee": "",
                                            "master_telegraph_fee": "",
                                            "master_pickup_unit": "",
                                            "master_pickup_fee": "",
                                            "master_delivery_unit": "",
                                            "master_airport_pickup_fee": "",
                                            "master_delivery_fee": "",
                                            "master_other_fee": "",
                                            "master_total_cost": "",
                                            "master_remark": ""
                                        }
                                        
                                        try:
                                            settlement = Settlement(
                                                form_data=json.dumps(settlement_data, ensure_ascii=False)
                                            )
                                            db_session.add(settlement)
                                            db_session.commit()
                                            
                                        except Exception as e:
                                            print(f"创建结算单失败: {str(e)}")
                                    finally:
                                        for queue_key, queue_data in queues_info.items():
                                            if queue_data.get("queueID"):
                                                try:
                                                    await rpa_service.delete_queue(queue_data["queueID"])
                                                except Exception as delete_error:
                                                    print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                        booking.rpa_queue_uuids = None
                                        db_session.commit()
                                
                                elif rpa_status == 3:
                                    if queues_info:
                                        for queue_key, queue_data in queues_info.items():
                                            if queue_data.get("queueID"):
                                                try:
                                                    await rpa_service.delete_queue(queue_data["queueID"])
                                                except Exception as delete_error:
                                                    print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                        booking.rpa_queue_uuids = None
                                        db_session.commit()
                            
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    print(f"轮询南航直接开单RPA状态失败: {str(e)}")
                    continue
        finally:
            db_session.close()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_poll())
    finally:
        loop.close()


@router.post("/{booking_id}/direct-invoice", summary="南航直接开单")
async def direct_invoice(
    booking_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    南航直接开单接口（队列模式）
    
    此接口会：
    1. 根据订舱的airline判断是否为南航（airline="2"或"南方航空"）
    2. 检查订舱是否有master_airwaybill_number
    3. 如果是南航，创建RPA直接开单任务并加入队列
    4. Worker会从队列中取出任务执行RPA调用
    5. 当RPA执行成功后，从4个队列中获取数据，创建结算单，然后删除队列
    
    - **booking_id**: 订舱ID（字符串格式）
    
    返回：
    - task_id: RPA任务ID，可用于查询任务状态
    """
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    form_data_dict = json.loads(booking.form_data)
    airline = form_data_dict.get("airline", "")
    
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的直接开单")
    
    if not booking.master_airwaybill_number:
        raise BadRequestException("订舱尚未完成，无法进行开单操作")
    
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value
    )
    if existing_task:
        raise BadRequestException(f"该订舱已有待执行或执行中的开单任务，任务ID: {existing_task.id}")
    
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航直接开单接口")
    
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    business_default = booking_and_create_config.get("business_default", {})
    
    system_url = china_southern_air_login.get("system_url", "")
    system_account = china_southern_air_login.get("system_account", "")
    login_password = china_southern_air_login.get("login_password", "")
    shipper = business_default.get("shipper", "")
    
    if not system_url or not system_account or not login_password:
        raise BadRequestException("业务参数配置中缺少南航登录信息")
    
    waybill_number_8 = booking.master_airwaybill_number.split("-")[-1] if "-" in booking.master_airwaybill_number else booking.master_airwaybill_number
    
    rpa_params = {
        "system_url": system_url,
        "system_account": system_account,
        "login_password": login_password,
        "waybill_number_8": waybill_number_8,
        "shipper": shipper  
    }
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        params=rpa_params,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
    )
    
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
        "updated_at": format_datetime_china(booking.updated_at),
        "task_id": str(task.id)  
    }
    
    return success_response(data=booking_data, msg="直接开单已加入执行队列，请等待处理")


@router.post("/{booking_id}/invoice-with-data", summary="南航修改数据后开单")
async def invoice_with_data(
    booking_id: str,
    form_data: dict,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    南航修改数据后开单接口（队列模式）
    
    此接口用于：用户从订舱回显数据后修改再开单的场景
    与直接开单接口不同，此接口允许用户传入修改后的业务数据
    
    使用场景：
    1. 用户订舱执行成功后，调用回显接口获取数据
    2. 用户在前端修改数据
    3. 调用此接口传入修改后的form_data进行开单
    4. 开单成功后，系统会自动同步创建运单记录到waybills表
    
    - **booking_id**: 订舱ID（字符串格式）
    - **form_data**: 修改后的表单数据（结构与回显接口返回的form_data相同）
    
    返回：
    - task_id: RPA任务ID，可用于查询任务状态
    """
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    booking = db.query(Booking).filter(Booking.id == int(booking_id)).first()
    if not booking:
        raise NotFoundException("订舱不存在")
    
    booking_form_data = json.loads(booking.form_data)
    airline = booking_form_data.get("airline", "")
    
    is_china_southern_air = airline == "2" or airline == "南方航空"
    if not is_china_southern_air:
        raise BadRequestException("当前仅支持南方航空的修改数据后开单")
    
    if not booking.master_airwaybill_number:
        raise BadRequestException("订舱尚未完成，无法进行开单操作")
    
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value
    )
    if existing_task:
        raise BadRequestException(f"该订舱已有待执行或执行中的开单任务，任务ID: {existing_task.id}")
    
    existing_direct_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value
    )
    if existing_direct_task:
        raise BadRequestException(f"该订舱已有待执行或执行中的直接开单任务，任务ID: {existing_direct_task.id}")
    
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用南航修改数据后开单接口")
    
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    business_default = booking_and_create_config.get("business_default", {})
    
    system_url = china_southern_air_login.get("system_url", "")
    system_account = china_southern_air_login.get("system_account", "")
    login_password = china_southern_air_login.get("login_password", "")
    
    if not system_url or not system_account or not login_password:
        raise BadRequestException("业务参数配置中缺少南航登录信息")
    
    waybill_number_8 = booking.master_airwaybill_number.split("-")[-1] if "-" in booking.master_airwaybill_number else booking.master_airwaybill_number
    
    if "form_data" in form_data and isinstance(form_data.get("form_data"), dict):
        form_data = form_data.get("form_data")
    
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    contact_info = form_data.get("contact_info", {})
    other_info = form_data.get("other_info", {})
    address = contact_info.get("address", {})
    
    region = address.get("region", "")
    if isinstance(region, str) and "/" in region:
        region_parts = region.split("/")
        region_province = region_parts[0] if len(region_parts) > 0 else ""
        region_city = region_parts[1] if len(region_parts) > 1 else ""
        region_district = region_parts[2] if len(region_parts) > 2 else ""
    elif isinstance(region, list):
        region_province = region[0] if len(region) > 0 else ""
        region_city = region[1] if len(region) > 1 else ""
        region_district = region[2] if len(region) > 2 else ""
    else:
        region_province = ""
        region_city = ""
        region_district = ""
    
    rpa_params = {
        "system_url": system_url,
        "system_account": system_account,
        "login_password": login_password,
        "waybill_number_8": waybill_number_8,
        "flight_number": flight_info.get("flight_number", "") or business_default.get("flight_number", ""),
        "flight_date": flight_info.get("flight_date", "") or business_default.get("flight_date", ""),
        "booking_remark": flight_info.get("booking_remark", "") or business_default.get("booking_remark", ""),
        "cargo_code": cargo_info.get("cargo_code", "") or business_default.get("cargo_code", ""),
        "cargo_name": cargo_info.get("cargo_name", "") or business_default.get("cargo_name", ""),
        "weight": str(cargo_info.get("weight", "")) or business_default.get("weight", ""),
        "quantity": str(cargo_info.get("quantity", "")) or business_default.get("quantity", ""),
        "volume": str(cargo_info.get("booking_volume", "")) or business_default.get("volume", ""),
        "special_cargo_code": cargo_info.get("special_cargo_code", "") or business_default.get("special_cargo_code", ""),
        "oversized_cargo": str(cargo_info.get("oversized_cargo", "0")) or "0",
        "shipper": contact_info.get("shipper", "") or business_default.get("shipper", ""),
        "shipper_phone": contact_info.get("shipper_phone", "") or business_default.get("phone", ""),
        "address_detail": address.get("detail", "") or business_default.get("address_detail", ""),
        "region_province_shipper": region_province or business_default.get("region_province_shipper", ""),
        "region_city_shipper": region_city or business_default.get("region_city_shipper", ""),
        "region_city_district": region_district or business_default.get("region_city_district", ""),
        "consignee": contact_info.get("consignee", "") or business_default.get("consignee", ""),
        "consignee_phone": contact_info.get("consignee_phone", "") or business_default.get("consignee_phone", ""),
        "order_contact_phone": other_info.get("contact_phone", "") or business_default.get("order_contact_phone", ""),
        "order_contact_name": other_info.get("order_contact", "") or business_default.get("order_contact_name", ""),
        "settlement_file_number": other_info.get("settlement_file_number", "") or business_default.get("settlement_file_number", ""),
        "_original_form_data": form_data
    }
    
    required_params = [
        "waybill_number_8",
        "flight_number",
        "flight_date",
        "cargo_name",
        "weight",
        "quantity",
        "shipper",
        "shipper_phone",
        "consignee"
    ]
    
    missing_params = [key for key in required_params if not rpa_params.get(key)]
    if missing_params:
        raise BadRequestException(f"缺少必填参数: {', '.join(missing_params)}")
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value,
        target_type=RPATargetType.BOOKING.value,
        target_id=int(booking_id),
        params=rpa_params,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
    )
    
    booking_form_data_response = json.loads(booking.form_data)
    
    booking_data = {
        "id": str(booking.id),
        "form_data": booking_form_data_response,
        "submitted_form_data": form_data,  
        "booking_status": booking.booking_status,
        "invoice_status": booking.invoice_status,
        "booking_time": format_datetime_china(booking.booking_time),
        "master_airwaybill_number": booking.master_airwaybill_number,
        "rpa_work_uuid": booking.rpa_work_uuid,
        "rpa_queue_uuid": booking.rpa_queue_uuid,
        "rpa_queue_id": booking.rpa_queue_id,
        "booking_cancel_status": booking.booking_cancel_status,
        "created_at": format_datetime_china(booking.created_at),
        "updated_at": format_datetime_china(booking.updated_at),
        "task_id": str(task.id)  
    }
    
    return success_response(data=booking_data, msg="修改数据后开单已加入执行队列，请等待处理")

