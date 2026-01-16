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
from app.models.waybill import Waybill
from app.models.settlement import Settlement
from app.models.config import BusinessConfig
from app.schemas.waybill import (
    WaybillCreate, WaybillQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_today, get_china_now
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
        cargo_station_record_status="0",  # 数据字典值："0"=未执行
        document_print_status="0"  # 数据字典值："0"=未执行
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
        "waybill_void_status": new_waybill.waybill_void_status,
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
            "waybill_void_status": waybill.waybill_void_status,
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
        "waybill_void_status": waybill.waybill_void_status,
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at)
    }
    
    return success_response(data=waybill_data, msg="查询成功")


def poll_rpa_void_status(waybill_id: int, work_uuid: str, job_uuid: str):
    """
    轮询RPA作废状态的后台任务
    
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
                
                # 查询RPA作废状态（仅深航）
                try:
                    status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            # 更新运单作废状态
                            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
                            if waybill:
                                # 映射RPA状态到系统数据字典的值（作废状态）
                                # RPA status -> 数据字典值："1"（作废中）、"2"（作废失败）、"3"（作废成功）
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    waybill.waybill_void_status = dict_value
                                
                                # 如果作废成功(status=5)，记录日志（保留记录用于留痕，不删除）
                                if rpa_status == 5:
                                    print(f"运单作废成功: waybill_id={waybill_id}, waybill_number={waybill.waybill_number}, waybill_void_status={dict_value}")
                                
                                db_session.commit()
                            
                            # 如果状态是成功(5)或失败(3)，停止轮询
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    # 记录错误但继续轮询
                    print(f"轮询RPA作废状态失败: {str(e)}")
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
                                
                                # 如果状态是成功(5)，从4个队列获取数据（仅深航）
                                if rpa_status == 5 and is_shenzhen_air:
                                    try:
                                        # 解析队列信息
                                        queues_info = {}
                                        if waybill.rpa_queue_uuids:
                                            queues_info = json.loads(waybill.rpa_queue_uuids)
                                        
                                        if queues_info:
                                            # 从4个队列中获取数据
                                            waybill_number_data = None
                                            freight_rate_data = None
                                            freight_data = None
                                            delivery_fee_data = None
                                            
                                            # 获取运单号
                                            if "waybill_number" in queues_info:
                                                try:
                                                    waybill_number_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["waybill_number"]["queueUUID"]
                                                    )
                                                    if waybill_number_data:
                                                        # 格式化运单号（深航需要加上前缀 "479-"）
                                                        waybill_number = rpa_service.format_shenzhen_air_waybill_number(waybill_number_data)
                                                        waybill.waybill_number = waybill_number
                                                except Exception as e:
                                                    print(f"获取运单号失败: {str(e)}")
                                            
                                            # 获取费率
                                            if "freight_rate" in queues_info:
                                                try:
                                                    freight_rate_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["freight_rate"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取费率失败: {str(e)}")
                                            
                                            # 获取运费
                                            if "freight" in queues_info:
                                                try:
                                                    freight_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["freight"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取运费失败: {str(e)}")
                                            
                                            # 获取派送费
                                            if "delivery_fee" in queues_info:
                                                try:
                                                    delivery_fee_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["delivery_fee"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取派送费失败: {str(e)}")
                                            
                                            # 如果获取到了运单号，创建结算单
                                            if waybill_number_data:
                                                # 解析form_data获取RPA入参
                                                form_data_dict = json.loads(waybill.form_data)
                                                flight_info = form_data_dict.get("flight_info", {})
                                                shipper_consignee_info = form_data_dict.get("shipper_consignee_info", {})
                                                cargo_info = form_data_dict.get("cargo_info", {})
                                                
                                                # 获取RPA调用时间（精确到日）
                                                rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                                                
                                                # 构建结算单数据
                                                settlement_data = {
                                                    "airline_record_time": rpa_call_time,
                                                    "settlement_method": "1",
                                                    "settlement_status": "0",
                                                    "financial_review": "1",
                                                    "master_airwaybill_number": waybill.waybill_number or "",  # 已格式化，包含479-前缀
                                                    "transport_method": "0",
                                                    "airline": "1",  # 深航是1
                                                    "origin_station": flight_info.get("origin_station", ""),
                                                    "destination": flight_info.get("destination", ""),
                                                    "flight_number": flight_info.get("flight_number", ""),
                                                    "flight_date": flight_info.get("flight_date", ""),
                                                    "customer_name": shipper_consignee_info.get("shipper_info", ""),
                                                    "recipient_name": shipper_consignee_info.get("consignee_info", ""),
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
                                                    "master_rate": freight_rate_data.strip('"').strip("'") if freight_rate_data else "1",
                                                    "master_airline_fee": freight_data.strip('"').strip("'") if freight_data else "1",
                                                    "master_fuel_surcharge": "1",
                                                    "master_transit_weight": "1",
                                                    "master_transit_fee": "1",
                                                    "master_cca_cost": "1",
                                                    "master_packaging_fee": "1",
                                                    "master_telegraph_fee": "1",
                                                    "master_pickup_unit": "1",
                                                    "master_pickup_fee": "1",
                                                    "master_delivery_unit": "1",
                                                    "master_airport_pickup_fee": "1",
                                                    "master_delivery_fee": delivery_fee_data.strip('"').strip("'") if delivery_fee_data else "1",
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
                                                except Exception as e:
                                                    print(f"创建结算单失败: {str(e)}")
                                            
                                            # 删除所有队列
                                            for queue_key, queue_info in queues_info.items():
                                                if "queueID" in queue_info:
                                                    try:
                                                        await rpa_service.delete_queue(queue_info["queueID"])
                                                    except Exception as delete_error:
                                                        print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                            
                                            # 清空队列信息
                                            waybill.rpa_queue_uuids = None
                                    except Exception as e:
                                        # 记录错误但不影响状态更新
                                        print(f"从队列获取数据失败: {str(e)}")
                                        # 即使获取数据失败，也要尝试删除队列
                                        if waybill.rpa_queue_uuids:
                                            try:
                                                queues_info = json.loads(waybill.rpa_queue_uuids)
                                                for queue_key, queue_info in queues_info.items():
                                                    if "queueID" in queue_info:
                                                        try:
                                                            await rpa_service.delete_queue(queue_info["queueID"])
                                                        except Exception as delete_error:
                                                            print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                                waybill.rpa_queue_uuids = None
                                            except Exception as cleanup_error:
                                                print(f"清理队列失败: {str(cleanup_error)}")
                                
                                # 如果状态是失败(3)，也需要清理队列
                                elif rpa_status == 3:
                                    if waybill.rpa_queue_uuids:
                                        try:
                                            queues_info = json.loads(waybill.rpa_queue_uuids)
                                            for queue_key, queue_info in queues_info.items():
                                                if "queueID" in queue_info:
                                                    try:
                                                        await rpa_service.delete_queue(queue_info["queueID"])
                                                    except Exception as delete_error:
                                                        print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                            waybill.rpa_queue_uuids = None
                                        except Exception as delete_error:
                                            print(f"清理队列失败: {str(delete_error)}")
                                
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


def _extract_shenzhen_air_params(form_data: dict, business_config: dict) -> dict:
    """
    提取并映射深航开单RPA接口所需的参数
    
    参数优先级：
    1. 优先使用form_data中的值
    2. 如果form_data中没有，则从业务参数配置中的深航数据部分获取
    
    Args:
        form_data: 运单的form_data字典
        business_config: 业务参数配置字典
    
    Returns:
        映射后的RPA接口参数字典
    """
    # 从业务参数配置中获取深航相关配置
    shenzhen_air_config = business_config.get("shenzhen_air", {})
    booking_config = shenzhen_air_config.get("booking", {})
    shenzhen_air_login = booking_config.get("shenzhen_air_login", {})
    business_default = booking_config.get("business_default", {})
    
    # 从form_data中提取数据
    flight_info = form_data.get("flight_info", {})
    shipper_consignee_info = form_data.get("shipper_consignee_info", {})
    cargo_info = form_data.get("cargo_info", {})
    
    # 映射参数（优先使用form_data，如果没有则使用业务参数配置）
    params = {
        # 登录信息：从业务参数配置获取
        "system_url": shenzhen_air_login.get("system_url", ""),
        "system_account": shenzhen_air_login.get("system_account", ""),
        "login_password": shenzhen_air_login.get("login_password", ""),
        
        # 航班信息：优先使用form_data，如果没有则使用业务参数配置
        "origin_station": flight_info.get("origin_station") or business_default.get("origin_station", ""),
        "destination": flight_info.get("destination", ""),
        "flight_date": flight_info.get("flight_date", ""),
        "flight_number": flight_info.get("flight_number", ""),
        
        # 发货收货信息：优先使用form_data，如果没有则使用业务参数配置
        "shipper_info": shipper_consignee_info.get("shipper_info") or business_default.get("shipper_info", ""),
        "consignee_info": shipper_consignee_info.get("consignee_info", ""),
        
        # 货物信息：优先使用form_data，如果没有则使用业务参数配置
        "quantity": cargo_info.get("quantity", ""),
        "weight": cargo_info.get("weight", ""),
        "freight_code": cargo_info.get("freight_code") or business_default.get("freight_code", ""),
        "cargo_code": cargo_info.get("cargo_code") or business_default.get("cargo_code", ""),
        "cargo_name": cargo_info.get("cargo_name") or business_default.get("cargo_name", ""),
        "waybill_type": flight_info.get("waybill_type", ""),  # 运单类型，从form_data获取，可能为空
        "package": cargo_info.get("package") or business_default.get("package", "")
    }
    
    return params


@router.post("/{waybill_id}/execute", summary="确认并执行运单")
async def execute_waybill(
    waybill_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    确认并执行运单接口（队列模式）
    
    此接口会：
    1. 根据运单的airline判断是否为深航（airline="1"或"深圳航空"）
    2. 如果是深航，创建RPA任务并加入队列
    3. Worker会从队列中取出任务执行RPA调用
    4. 前端可以通过任务ID或运单状态轮询获取执行结果
    
    - **waybill_id**: 运单ID（字符串格式）
    
    返回：
    - task_id: RPA任务ID，可用于查询任务状态
    """
    from app.config import settings
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
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
    
    # 检查是否有正在执行的同类型任务
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value
    )
    if existing_task:
        raise BadRequestException(f"该运单已有待执行或执行中的开单任务，任务ID: {existing_task.id}")
    
    # 获取业务参数配置
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用深航开单接口")
    
    # 提取并映射参数（优先使用form_data，如果没有则使用业务参数配置）
    rpa_params = _extract_shenzhen_air_params(form_data_dict, business_config)
    
    # 验证必填参数
    required_params = [
        "system_url",
        "system_account",
        "login_password",
        "origin_station",
        "destination",
        "flight_date",
        "flight_number",
        "shipper_info",
        "consignee_info",
        "quantity",
        "weight",
        "freight_code",
        "cargo_code",
        "cargo_name",
        "package"
    ]
    
    missing_params = [key for key in required_params if not rpa_params.get(key)]
    if missing_params:
        raise BadRequestException(f"缺少必填参数: {', '.join(missing_params)}")
    
    # 构建队列参数
    queue_params = {
        "queue_configs": [
            {"name": settings.RPA_SHENZHEN_AIR_QUEUE_WAYBILL_NUMBER, "key": "waybill_number"},
            {"name": settings.RPA_SHENZHEN_AIR_QUEUE_FREIGHT_RATE, "key": "freight_rate"},
            {"name": settings.RPA_SHENZHEN_AIR_QUEUE_FREIGHT, "key": "freight"},
            {"name": settings.RPA_SHENZHEN_AIR_QUEUE_DELIVERY_FEE, "key": "delivery_fee"}
        ]
    }
    
    # 创建RPA任务
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        params=rpa_params,
        queue_params=queue_params,
        job_uuid=settings.RPA_SHENZHEN_AIR_JOB_UUID,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
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
        "waybill_void_status": waybill.waybill_void_status,
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "rpa_queue_uuids": waybill.rpa_queue_uuids,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
        "task_id": str(task.id)  # 返回任务ID
    }
    
    return success_response(data=waybill_data, msg="运单已加入执行队列，请等待处理")


@router.post("/{waybill_id}/void", summary="运单作废")
async def void_waybill(
    waybill_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    运单作废接口（队列模式）
    
    此接口会：
    1. 根据运单的airline判断是否为深航（airline="1"或"深圳航空"）
    2. 如果是深航，从waybill_number中提取运单号后八位（去除"479-"前缀）
    3. 创建RPA作废任务并加入队列
    4. Worker会从队列中取出任务执行RPA调用
    5. 当RPA作废成功时，更新运单作废状态为"3"（作废成功），保留记录用于留痕
    
    - **waybill_id**: 运单ID（字符串格式）
    
    返回：
    - task_id: RPA任务ID，可用于查询任务状态
    """
    from app.config import settings
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    # 查询运单
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    # 检查运单号是否存在
    if not waybill.waybill_number:
        raise BadRequestException("运单号不存在，无法作废")
    
    # 解析form_data
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    # 判断是否为深圳航空
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    if not is_shenzhen_air:
        raise BadRequestException("当前仅支持深圳航空的运单作废")
    
    # 检查是否有正在执行的同类型任务
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_VOID.value
    )
    if existing_task:
        raise BadRequestException(f"该运单已有待执行或执行中的作废任务，任务ID: {existing_task.id}")
    
    # 提取运单号后八位（去除深航前缀"479-"）
    waybill_number_8 = rpa_service.extract_waybill_suffix(waybill.waybill_number)
    
    # 验证运单号后八位
    if not waybill_number_8 or len(waybill_number_8) != 8:
        raise BadRequestException(f"运单号格式不正确，无法提取后八位: {waybill.waybill_number}")
    
    # 构建RPA参数
    rpa_params = {
        "waybill_number_8": waybill_number_8
    }
    
    # 创建RPA任务
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_VOID.value,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        params=rpa_params,
        job_uuid=settings.RPA_SHENZHEN_AIR_VOID_JOB_UUID,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
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
        "waybill_void_status": waybill.waybill_void_status,
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
        "task_id": str(task.id)  # 返回任务ID
    }
    
    return success_response(data=waybill_data, msg="运单作废已加入执行队列，请等待处理")

