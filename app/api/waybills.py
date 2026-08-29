"""
运单管理接口
"""
import asyncio
import json
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.mysql import JSON
from app.core.exceptions import BaseAPIException, NotFoundException, BadRequestException
from app.core.response import success_response
from app.database import get_db
from app.models.waybill import Waybill
from app.models.nanhang_token import NanHangToken
from app.models.settlement import Settlement
from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.models.config import BusinessConfig
from app.schemas.waybill import (
    ChinaSouthernAirServiceChargeOptionsQuery, WaybillCreate, WaybillUpdate, WaybillQuery
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_today, get_china_now
from app.services.rpa_service import rpa_service
from app.services.china_southern_air_service_client import (
    ChinaSouthernAirServiceError,
    china_southern_air_service,
)
from app.services.china_southern_air_direct_order import (
    ChinaSouthernAirDirectOrderError,
    china_southern_air_direct_order_service,
)
from app.services.document_print_service import is_post_waybill_automation_enabled
from app.services.waybill_stock_service import confirm_stock_item_used
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value
from app.utils.airport_code_mapper import search_airport_codes_by_keyword

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
    
    form_data_json = json.dumps(waybill.form_data, ensure_ascii=False)
    
    booking_date = get_china_today()
    
    new_waybill = Waybill(
        form_data=form_data_json,
        booking_date=booking_date,
        airline_record_status="0",  
        cargo_station_record_status="0",  
        document_print_status="0"  
    )
    db.add(new_waybill)
    db.commit()
    db.refresh(new_waybill)
    
    form_data_dict = json.loads(new_waybill.form_data)
    
    waybill_data = {
        "id": str(new_waybill.id),
        "waybill_number": new_waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": new_waybill.airline_record_status,
        "cargo_station_record_status": new_waybill.cargo_station_record_status,
        "document_print_status": new_waybill.document_print_status,
        "waybill_void_status": new_waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(new_waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(new_waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(new_waybill.document_print_time),
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
    - **airline_record_status**: 航司录单执行状态筛选（数据字典值：0=未开单，1=开单中，2=失败，3=成功）
    - **cargo_station_record_status**: 货站录单执行状态筛选（数据字典值：0=未执行，1=执行中，2=失败，3=已录单）
    - **document_print_status**: 单据打印执行状态筛选（数据字典值：0=未执行，1=执行中，2=失败）
    - **booking_date_start**: 开单日期开始（格式：YYYY-MM-DD）
    - **booking_date_end**: 开单日期结束（格式：YYYY-MM-DD）
    - **airline**: 航司（数据字典值精确匹配：1=深圳航空，2=南方航空）
    - **destination**: 目的站（城市名称模糊搜索，如"西宁"会转换为三字码"XNN"后精确匹配）
    - **flight_number**: 航班号（模糊搜索，从form_data.flight_info.flight_number中提取）
    - **waybill_type**: 运单类型（数据字典值精确匹配，从form_data.flight_info.waybill_type中提取，仅深圳航空）
    - **shipper**: 托运单位（模糊搜索，从form_data中提取，支持深圳航空的shipper_consignee_info.shipper_unit和南方航空的contact_info.shipper_unit）
    - **waybill_number**: 运单号（模糊搜索）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    
    支持多条件组合筛选
    """
    query_obj = db.query(Waybill)
    
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
    
    if query.booking_date_start:
        query_obj = query_obj.filter(
            Waybill.booking_date >= query.booking_date_start
        )
    
    if query.booking_date_end:
        query_obj = query_obj.filter(
            Waybill.booking_date <= query.booking_date_end
        )
    
    if query.waybill_number:
        query_obj = query_obj.filter(
            Waybill.waybill_number.like(f"%{query.waybill_number}%")
        )
    
    
    if query.airline:
        query_obj = query_obj.filter(
            func.json_unquote(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.airline"
                )
            ) == query.airline
        )
    
    if query.destination:
        matched_codes = search_airport_codes_by_keyword(query.destination)
        
        if matched_codes:
            if len(matched_codes) == 1:
                query_obj = query_obj.filter(
                    func.json_unquote(
                        func.json_extract(
                            func.cast(Waybill.form_data, JSON), 
                            "$.flight_info.destination"
                        )
                    ) == matched_codes[0]
                )
            else:
                query_obj = query_obj.filter(
                    func.json_unquote(
                        func.json_extract(
                            func.cast(Waybill.form_data, JSON), 
                            "$.flight_info.destination"
                        )
                    ).in_(matched_codes)
                )
        else:
            query_obj = query_obj.filter(
                func.json_unquote(
                    func.json_extract(
                        func.cast(Waybill.form_data, JSON), 
                        "$.flight_info.destination"
                    )
                ) == query.destination.upper()
            )
    
    if query.flight_number:
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
        query_obj = query_obj.filter(
            func.json_unquote(
                func.json_extract(
                    func.cast(Waybill.form_data, JSON), 
                    "$.flight_info.waybill_type"
                )
            ) == query.waybill_type
        )
    
    if query.shipper:
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
    
    total = query_obj.count()
    
    offset = (query.page - 1) * query.pageSize
    waybills = query_obj.order_by(
        Waybill.created_at.desc(), Waybill.id.desc()
    ).offset(offset).limit(query.pageSize).all()
    
    waybill_list = []
    for waybill in waybills:
        form_data_dict = json.loads(waybill.form_data)
        
        waybill_list.append({
            "id": str(waybill.id),
            "waybill_number": waybill.waybill_number,
            "form_data": form_data_dict,
            "airline_record_status": waybill.airline_record_status,
            "cargo_station_record_status": waybill.cargo_station_record_status,
            "document_print_status": waybill.document_print_status,
            "waybill_void_status": waybill.waybill_void_status,
            "airline_record_time": format_datetime_china(waybill.airline_record_time),
            "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
            "document_print_time": format_datetime_china(waybill.document_print_time),
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


@router.post(
    "/china-southern-air/departure-cargo-mail-handling-charge-options",
    summary="查询南航出港货邮处理费选项",
)
async def get_china_southern_air_departure_cargo_mail_handling_charge_options(
    query: ChinaSouthernAirServiceChargeOptionsQuery,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """按航班和货物类型查询南航的出港货邮处理费选项。"""
    service_charge_query_data = {
        "resAllInfoList": [{"resDto": {
            "flightDep": query.origin_station,
            "flightDest": query.destination,
            "bookFlightno": query.flight_number,
            "bookFlightdate": query.flight_date.isoformat(),
        }}],
        "routing": f"{query.origin_station}/{query.destination}",
        "shipmentType": query.cargo_type_code,
        "shipmentTypeName": query.cargo_name,
        "channel": "B2B",
    }
    token_record = (
        db.query(NanHangToken)
        .filter(NanHangToken.token.isnot(None), NanHangToken.token != "")
        .order_by(NanHangToken.updated_at.desc(), NanHangToken.id.desc())
        .first()
    )
    if token_record is None:
        raise BaseAPIException(503, "暂无可用的南航 Token，请先完成南航 Token 获取任务")

    try:
        charge_options = await china_southern_air_service.query_departure_cargo_mail_handling_charge(
            token=token_record.token,
            origin_station=query.origin_station,
            destination=query.destination,
            flight_number=query.flight_number,
            flight_date=query.flight_date.isoformat(),
            cargo_type=query.cargo_type_code,
            cargo_name=query.cargo_name,
        )
    except ChinaSouthernAirServiceError as exc:
        error_details = {
            "stage": "query_service_charges",
            "request_data": service_charge_query_data,
        }
        if exc.details:
            error_details.update(exc.details)
        raise BaseAPIException(
            502,
            str(exc),
            data={"error_details": error_details},
        ) from exc

    return success_response(data=charge_options, msg="查询成功")

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
    
    form_data_dict = json.loads(waybill.form_data)
    
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at)
    }
    
    return success_response(data=waybill_data, msg="查询成功")


@router.put("/{waybill_id}", summary="修改运单信息")
async def update_waybill(
    waybill_id: str,
    payload: WaybillUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    修改运单信息接口

    - 仅当运单处于「未开单」（airline_record_status="0"）或「开单失败」（airline_record_status="2"）时允许修改，修改后可重新开单
    - 可更新 form_data（整体替换）与可选的 booking_date
    - waybill_number、departure_time、各执行状态等由系统/RPA 维护，不可通过本接口修改
    """
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")

    if waybill.airline_record_status not in ("0", "2"):
        raise BadRequestException(
            "仅未开单或开单失败状态的运单可修改；当前运单正在开单中或已开单成功，无法修改"
        )

    form_data_json = json.dumps(payload.form_data, ensure_ascii=False)
    waybill.form_data = form_data_json
    if payload.booking_date is not None:
        waybill.booking_date = payload.booking_date

    db.commit()
    db.refresh(waybill)

    form_data_dict = json.loads(waybill.form_data)
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at)
    }
    return success_response(data=waybill_data, msg="运单修改成功")


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
        db_session = SessionLocal()
        try:
            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
            if not waybill:
                print(f"运单不存在，停止轮询: {waybill_id}")
                return
            
            form_data_dict = json.loads(waybill.form_data)
            airline = form_data_dict.get("airline", "")
            is_shenzhen_air = airline == "1" or airline == "深圳航空"
            if not is_shenzhen_air:
                print(f"运单不是深航，停止轮询: {waybill_id}, airline={airline}")
                return
            
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                await asyncio.sleep(poll_interval)
                
                try:
                    status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
                            if waybill:
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    waybill.waybill_void_status = dict_value
                                
                                if rpa_status == 5:
                                    print(f"运单作废成功: waybill_id={waybill_id}, waybill_number={waybill.waybill_number}, waybill_void_status={dict_value}")
                                    
                                    if waybill.waybill_number:
                                        try:
                                            from sqlalchemy import func, cast, String
                                            from sqlalchemy.dialects.mysql import JSON
                                            import json as json_lib
                                            
                                            settlements = db_session.query(Settlement).filter(
                                                func.cast(
                                                    func.json_extract(
                                                        cast(Settlement.form_data, JSON),
                                                        "$.master_airwaybill_number"
                                                    ),
                                                    String(100)
                                                ) == waybill.waybill_number
                                            ).all()
                                            
                                            if not settlements:
                                                print(f"方法1未找到结算单，使用方法2查找: waybill_number={waybill.waybill_number}")
                                                all_settlements = db_session.query(Settlement).all()
                                                for settlement in all_settlements:
                                                    try:
                                                        form_data_dict = json_lib.loads(settlement.form_data)
                                                        master_airwaybill_number = form_data_dict.get("master_airwaybill_number", "")
                                                        if master_airwaybill_number == waybill.waybill_number:
                                                            settlements.append(settlement)
                                                    except Exception as e:
                                                        continue
                                            
                                            if settlements:
                                                for settlement in settlements:
                                                    settlement.waybill_void_status = "3"  
                                                    print(f"已同步运单作废状态到结算单: settlement_id={settlement.id}, waybill_number={waybill.waybill_number}, waybill_void_status=3")
                                            else:
                                                print(f"警告：未找到对应的结算单，waybill_number={waybill.waybill_number}")
                                        except Exception as e:
                                            import traceback
                                            print(f"同步运单作废状态到结算单失败: {str(e)}")
                                            print(f"错误详情: {traceback.format_exc()}")
                                
                                db_session.commit()
                            
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    print(f"轮询RPA作废状态失败: {str(e)}")
                    continue
        finally:
            db_session.close()
    
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
        db_session = SessionLocal()
        try:
            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
            if not waybill:
                print(f"运单不存在，停止轮询: {waybill_id}")
                return
            
            form_data_dict = json.loads(waybill.form_data)
            airline = form_data_dict.get("airline", "")
            is_shenzhen_air = airline == "1" or airline == "深圳航空"
            if not is_shenzhen_air:
                print(f"运单不是深航，停止轮询: {waybill_id}, airline={airline}")
                return
            
            from app.config import settings
            max_polls = settings.RPA_POLL_MAX_COUNT
            poll_interval = settings.RPA_POLL_INTERVAL
            
            for i in range(max_polls):
                await asyncio.sleep(poll_interval)
                
                try:
                    status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                    status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                    
                    if status_info:
                        rpa_status = status_info.get("status")
                        if rpa_status is not None:
                            waybill = db_session.query(Waybill).filter(Waybill.id == waybill_id).first()
                            if waybill:
                                dict_value = map_rpa_status_to_dict_value(rpa_status)
                                if dict_value:
                                    waybill.airline_record_status = dict_value
                                
                                if rpa_status == 5 and is_shenzhen_air:
                                    try:
                                        queues_info = {}
                                        if waybill.rpa_queue_uuids:
                                            queues_info = json.loads(waybill.rpa_queue_uuids)
                                        
                                        if queues_info:
                                            waybill_number_data = None
                                            freight_rate_data = None
                                            freight_data = None
                                            delivery_fee_data = None
                                            
                                            waybill_number_retrieved = False
                                            if "waybill_number" in queues_info:
                                                try:
                                                    waybill_number_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["waybill_number"]["queueUUID"]
                                                    )
                                                    if waybill_number_data:
                                                        waybill_number = rpa_service.format_shenzhen_air_waybill_number(waybill_number_data)
                                                        waybill.waybill_number = waybill_number
                                                        waybill_number_retrieved = True
                                                except Exception as e:
                                                    print(f"获取运单号失败: {str(e)}")
                                            
                                            if not waybill_number_retrieved:
                                                waybill.airline_record_status = "2"  
                                                print(f"运单 {waybill_id} RPA返回成功但获取运单号失败，将状态设置为失败")
                                            
                                            if "freight_rate" in queues_info:
                                                try:
                                                    freight_rate_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["freight_rate"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取费率失败: {str(e)}")
                                            
                                            if "freight" in queues_info:
                                                try:
                                                    freight_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["freight"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取运费失败: {str(e)}")
                                            
                                            if "delivery_fee" in queues_info:
                                                try:
                                                    delivery_fee_data = await rpa_service.get_shenzhen_air_waybill_number(
                                                        queues_info["delivery_fee"]["queueUUID"]
                                                    )
                                                except Exception as e:
                                                    print(f"获取派送费失败: {str(e)}")
                                            
                                            if waybill_number_data:
                                                form_data_dict = json.loads(waybill.form_data)
                                                flight_info = form_data_dict.get("flight_info", {})
                                                shipper_consignee_info = form_data_dict.get("shipper_consignee_info", {})
                                                cargo_info = form_data_dict.get("cargo_info", {})
                                                other_fees = form_data_dict.get("other_fees", {})
                                                
                                                rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                                                
                                                settlement_data = {
                                                    "airline_record_time": rpa_call_time,
                                                    "settlement_method": "1",
                                                    "settlement_status": "0",
                                                    "financial_review": "0",
                                                    "master_airwaybill_number": waybill.waybill_number or "",  
                                                    "transport_method": "2",
                                                    "airline": "1",  
                                                    "origin_station": flight_info.get("origin_station", ""),
                                                    "destination": flight_info.get("destination", ""),
                                                    "flight_number": flight_info.get("flight_number", ""),
                                                    "flight_date": flight_info.get("flight_date", ""),
                                                    "customer_name": shipper_consignee_info.get("shipper_unit", ""),
                                                    "recipient_name": shipper_consignee_info.get("consignee_info", ""),
                                                    "cargo_name": cargo_info.get("cargo_name", ""),
                                                    "quantity": cargo_info.get("quantity", ""),
                                                    "weight": cargo_info.get("weight", ""),
                                                    "chargeable_weight": "",
                                                    "sub_rate": "",
                                                    "sub_airline_fee": "",
                                                    "sub_document_fee": "",
                                                    "sub_telegraph_fee": "",
                                                    "sub_telegraph_number": "",
                                                    "sub_cca_fee": "",
                                                    "sub_packaging_fee": other_fees.get("packaging_fee", ""),
                                                    "sub_pickup_fee": other_fees.get("pickup_fee", ""),
                                                    "sub_airport_pickup_fee": "",
                                                    "sub_delivery_fee": other_fees.get("delivery_fee", ""),
                                                    "sub_carrier_deduction": "",
                                                    "sub_other_fee": "",
                                                    "sub_other_fee_remark": "",
                                                    "sub_total_amount": "",
                                                    "sub_remark": "",
                                                    "master_rate": freight_rate_data.strip('"').strip("'") if freight_rate_data else "",
                                                    "master_airline_fee": freight_data.strip('"').strip("'") if freight_data else "",
                                                    "master_fuel_surcharge": "",
                                                    "master_transit_weight": "",
                                                    "master_transit_fee": "",
                                                    "master_cca_cost": "",
                                                    "master_packaging_fee": "",
                                                    "master_telegraph_fee": "",
                                                    "master_pickup_unit": "",
                                                    "master_pickup_fee": "",
                                                    "master_delivery_unit": "",
                                                    "master_airport_pickup_fee": "",
                                                    "master_delivery_fee": delivery_fee_data.strip('"').strip("'") if delivery_fee_data else "",
                                                    "master_other_fee": "",
                                                    "master_total_cost": "",
                                                    "master_remark": ""
                                                }
                                                
                                                try:
                                                    settlement = Settlement(
                                                        form_data=json.dumps(settlement_data, ensure_ascii=False),
                                                        waybill_void_status=waybill.waybill_void_status or "0"  
                                                    )
                                                    db_session.add(settlement)
                                                    db_session.commit()
                                                except Exception as e:
                                                    print(f"创建结算单失败: {str(e)}")
                                            
                                            for queue_key, queue_info in queues_info.items():
                                                if "queueID" in queue_info:
                                                    try:
                                                        await rpa_service.delete_queue(queue_info["queueID"])
                                                    except Exception as delete_error:
                                                        print(f"删除队列失败 ({queue_key}): {str(delete_error)}")
                                            
                                            waybill.rpa_queue_uuids = None
                                    except Exception as e:
                                        print(f"从队列获取数据失败: {str(e)}")
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
                            
                            if rpa_status in [3, 5]:
                                break
                except Exception as e:
                    print(f"轮询RPA状态失败: {str(e)}")
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


def _reserve_china_southern_air_stock_item(db: Session) -> WaybillStockItem:
    """以行锁预占一个南航可用单号，避免并发开单重复分配。"""
    stock_item = (
        db.query(WaybillStockItem)
        .join(WaybillStockBatch, WaybillStockItem.batch_id == WaybillStockBatch.id)
        .join(WaybillStock, WaybillStockBatch.stock_id == WaybillStock.id)
        .filter(
            WaybillStock.airline_name == "china_southern_air",
            WaybillStockItem.usage_status == "0",
            WaybillStockItem.is_abnormal == "1",
            WaybillStockItem.is_invalid == "0",
        )
        .order_by(WaybillStockBatch.id.desc(), WaybillStockItem.id.asc())
        .with_for_update(skip_locked=True)
        .first()
    )
    if stock_item is None:
        raise BadRequestException("南航单号库中没有可用单号，请先补充单号库")

    stock_item.usage_status = "1"
    stock_item.usage_date = get_china_now().date()
    return stock_item


def _release_stock_item(db: Session, stock_item_id: int) -> None:
    """归还尚未提交到南航的单号。"""
    stock_item = (
        db.query(WaybillStockItem)
        .filter(WaybillStockItem.id == stock_item_id)
        .with_for_update()
        .first()
    )
    if stock_item is not None:
        stock_item.usage_status = "0"
        stock_item.usage_date = None


def _mark_stock_item_unavailable(db: Session, stock_item_id: int, reason: str) -> None:
    """隔离已被南航使用或结果不确定的单号，避免再次抢占。"""
    stock_item = (
        db.query(WaybillStockItem)
        .filter(WaybillStockItem.id == stock_item_id)
        .with_for_update()
        .first()
    )
    if stock_item is not None:
        stock_item.usage_status = "1"
        stock_item.usage_date = get_china_now().date()
        stock_item.is_invalid = "1"
        stock_item.invalid_reason = (reason or "南航开单结果不确定")[:255]


def _create_china_southern_air_settlement(
    db: Session,
    waybill: Waybill,
    form_data: dict,
    calculation_result: dict,
) -> None:
    """沿用南航 RPA 开单成功后的结算单落库语义。"""
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    contact_info = form_data.get("contact_info", {})
    other_fees = form_data.get("other_fees", {})
    flight_price = calculation_result.get("flightPriceCalculateResult") or {}

    settlement_data = {
        "airline_record_time": get_china_now().strftime("%Y-%m-%d"),
        "settlement_method": "1",
        "settlement_status": "0",
        "financial_review": "0",
        "master_airwaybill_number": waybill.waybill_number or "",
        "transport_method": "2",
        "airline": "2",
        "origin_station": flight_info.get("origin_station", ""),
        "destination": flight_info.get("destination", ""),
        "flight_number": flight_info.get("flight_number", ""),
        "flight_date": flight_info.get("flight_date", ""),
        "customer_name": contact_info.get("shipper_unit", ""),
        "recipient_name": contact_info.get("consignee", ""),
        "cargo_name": cargo_info.get("cargo_name", ""),
        "quantity": cargo_info.get("quantity", ""),
        "weight": cargo_info.get("weight", ""),
        "chargeable_weight": calculation_result.get("cweight", ""),
        "sub_rate": "",
        "sub_airline_fee": "",
        "sub_document_fee": "",
        "sub_telegraph_fee": "",
        "sub_telegraph_number": "",
        "sub_cca_fee": "",
        "sub_packaging_fee": other_fees.get("packaging_fee", ""),
        "sub_pickup_fee": other_fees.get("pickup_fee", ""),
        "sub_airport_pickup_fee": "",
        "sub_delivery_fee": other_fees.get("delivery_fee", ""),
        "sub_carrier_deduction": "",
        "sub_other_fee": "",
        "sub_other_fee_remark": "",
        "sub_total_amount": "",
        "sub_remark": "",
        "master_rate": flight_price.get("norRate", ""),
        "master_airline_fee": calculation_result.get("weightCharge", ""),
        "master_fuel_surcharge": calculation_result.get("oilFee", ""),
        "master_transit_weight": "",
        "master_transit_fee": calculation_result.get("totalExtensionCharge", ""),
        "master_cca_cost": "",
        "master_packaging_fee": "",
        "master_telegraph_fee": "",
        "master_pickup_unit": "",
        "master_pickup_fee": "",
        "master_delivery_unit": "",
        "master_airport_pickup_fee": "",
        "master_delivery_fee": "",
        "master_other_fee": "",
        "master_total_cost": calculation_result.get("totalCharge", ""),
        "master_remark": "",
    }
    db.add(Settlement(
        form_data=json.dumps(settlement_data, ensure_ascii=False),
        waybill_void_status=waybill.waybill_void_status or "0",
    ))


async def _post_process_china_southern_air_waybill(
    waybill_id: int,
    form_data: dict,
    business_config: dict,
) -> None:
    """开单成功后异步生成南航货站文件并创建打印任务。"""
    if not is_post_waybill_automation_enabled("2"):
        print(
            "[南航直连开单] 开单后自动处理已关闭，"
            f"取消异步制单及打印，运单ID: {waybill_id}"
        )
        return

    from app.database import SessionLocal
    from app.services.cargo_station_record_service import generate_csa_all_documents

    db = SessionLocal()
    try:
        waybill = db.query(Waybill).filter(Waybill.id == waybill_id).first()
        if waybill is None or waybill.airline_record_status != "3":
            return

        waybill.cargo_station_record_status = "1"
        db.commit()
        documents_result = await asyncio.to_thread(
            generate_csa_all_documents,
            waybill_id=waybill.id,
            waybill_number=waybill.waybill_number,
            form_data=form_data,
            business_config=business_config,
        )
        all_success = all(
            not document.get("error") and document.get("excel")
            for document in documents_result.values()
        )
        waybill.cargo_station_record_status = "3" if all_success else "2"
        db.commit()
        if all_success:
            _auto_trigger_document_print(db, waybill, form_data, business_config)
    except Exception:
        db.rollback()
        waybill = db.query(Waybill).filter(Waybill.id == waybill_id).first()
        if waybill is not None:
            waybill.cargo_station_record_status = "2"
            db.commit()
    finally:
        db.close()


def _auto_trigger_document_print(db: Session, waybill, form_data_dict: dict, business_config: dict):
    """
    货站录单成功后自动触发打单
    
    创建打单RPA任务到队列中，由Worker异步执行
    
    Args:
        db: 数据库会话
        waybill: 运单对象
        form_data_dict: 运单表单数据字典
        business_config: 业务参数配置
    """
    import traceback
    from app.services.document_print_service import (
        get_print_task_count,
        prepare_print_tasks,
    )
    from app.services.rpa_task_service import rpa_task_service
    from app.models.rpa_task import RPATaskType, RPATargetType
    
    airline = form_data_dict.get("airline", "")
    if not is_post_waybill_automation_enabled(airline):
        print(
            f"[自动打单] 航司开单后自动处理已关闭，跳过自动打单，"
            f"运单ID: {waybill.id}, 航司: {airline}"
        )
        return

    print(f"[自动打单] 开始自动触发打单，运单ID: {waybill.id}, 运单号: {waybill.waybill_number}, 航司: {airline}")
    
    try:
        airline_code = ""
        if airline in ["1", "深圳航空", "shenzhen_air"]:
            airline_code = "shenzhen_air"
        elif airline in ["2", "南方航空", "china_southern_air"]:
            airline_code = "china_southern_air"
        airline_print_config = business_config.get(airline_code, {}).get("print", {}).get("printer_config", [])
        print(f"[自动打单] 航司: {airline_code}, 打印机配置数量: {len(airline_print_config)}, 配置内容: {airline_print_config}")
        
        print_tasks = prepare_print_tasks(
            waybill_id=waybill.id,
            waybill_number=waybill.waybill_number,
            airline=airline,
            business_config=business_config
        )
        
        task_count = get_print_task_count(print_tasks)
        if task_count == 0:
            print(f"[自动打单] 没有可执行的打印任务（task_count=0），跳过自动打单，运单ID: {waybill.id}。请检查业务参数中 {airline_code}.print.printer_config 是否已配置打印机")
            return
        
        sub_tasks = print_tasks.get("tasks", [])
        for i, t in enumerate(sub_tasks):
            print(f"[自动打单] 打印子任务 {i+1}/{task_count}: {t.get('description')}, 类型: {t.get('type')}")
        
        from app.services.rpa_task_service import PRINT_TYPE_MAPPING
        created_count = 0
        for sub_task in sub_tasks:
            sub_type = sub_task.get("type", "")
            rpa_task_type = PRINT_TYPE_MAPPING.get(sub_type)
            if not rpa_task_type:
                print(f"[自动打单] 未知的打印子任务类型: {sub_type}，跳过")
                continue
            
            rpa_task_service.create_task(
                db=db,
                task_type=rpa_task_type,
                target_type=RPATargetType.WAYBILL.value,
                target_id=waybill.id,
                params=sub_task.get("params", {}),
                created_by=None,
                location=airline_code
            )
            created_count += 1
        
        print(f"[自动打单] 打单任务已成功创建！共创建 {created_count} 个独立打印任务，运单ID: {waybill.id}")
        
    except Exception as e:
        print(f"[自动打单] 自动触发打单失败，运单ID: {waybill.id}, 错误: {str(e)}")
        print(f"[自动打单] 错误详情: {traceback.format_exc()}")


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
    shenzhen_air_config = business_config.get("shenzhen_air", {})
    booking_config = shenzhen_air_config.get("booking", {})
    shenzhen_air_login = booking_config.get("shenzhen_air_login", {})
    business_default = booking_config.get("business_default", {})
    
    flight_info = form_data.get("flight_info", {})
    shipper_consignee_info = form_data.get("shipper_consignee_info", {})
    cargo_info = form_data.get("cargo_info", {})
    
    params = {
        "system_url": shenzhen_air_login.get("system_url", ""),
        "system_account": shenzhen_air_login.get("system_account", ""),
        "login_password": shenzhen_air_login.get("login_password", ""),
        
        "origin_station": flight_info.get("origin_station") or business_default.get("origin_station", ""),
        "destination": flight_info.get("destination", ""),
        "flight_date": flight_info.get("flight_date", ""),
        "flight_number": flight_info.get("flight_number", ""),
        
        "shipper_info": shipper_consignee_info.get("shipper_info") or business_default.get("shipper_info", ""),
        "consignee_info": shipper_consignee_info.get("consignee_info", ""),
        
        "quantity": str(cargo_info.get("quantity", "")),
        "weight": str(cargo_info.get("weight", "")),
        "chargeable_weight": str(cargo_info.get("chargeable_weight", "")),
        "freight_code": cargo_info.get("freight_code") or business_default.get("freight_code", ""),
        "cargo_code": cargo_info.get("cargo_code") or business_default.get("cargo_code", ""),
        "cargo_name": cargo_info.get("cargo_name") or business_default.get("cargo_name", ""),
        "waybill_type": flight_info.get("waybill_type") or business_default.get("waybill_type", ""),
        "package": cargo_info.get("package") or business_default.get("package", ""),
        "storage_and_transportation_precautions": cargo_info.get("storage_and_transportation_precautions", "")
    }
    
    return params


def _extract_china_southern_air_waybill_params(form_data: dict, business_config: dict) -> dict:
    """
    提取并映射南航新增运单RPA接口所需的参数
    
    参数优先级：
    1. 优先使用form_data中的值
    2. 如果form_data中没有，则从业务参数配置中的南航数据部分获取
    
    注意：form_data结构为运单的南航结构：
    {
      "airline": "2",
      "flight_info": {
        "destination": "北京",
        "flight_date": "2025-01-15",
        "flight_number": "CZ5678",
        "booking_remark": "备注信息",
        "origin_station": "CAN"
      },
      "cargo_info": {
        "cargo_type": "普通货物",
        "cargo_code": "0001",
        "cargo_name": "货物名称",
        "quantity": "10",
        "weight": "100.5",
        "oversized_cargo": "否",
        "special_cargo_code": ""
      },
      "contact_info": {
        "consignee": "收货人",
        "consignee_phone": "13800138000",
        "shipper_unit": "XX物流公司",
        "shipper": "托运人",
        "shipper_phone": "13900139000",
        "address": {
          "region": "广东省/深圳市/南山区",
          "detail": "科技园南区"
        }
      },
      "dangerous_goods_declaration": {
        "no_hidden_dangerous_goods": "是",
        "agent_checker_signature": "检查人签字",
        "agent_consignor_signature": "交运人签字"
      },
      "other_info": {
        "order_contact": "订单联系人",
        "contact_phone": "13700137000",
        "settlement_file_number": "SF001"
      }
    }
    
    Args:
        form_data: 运单的form_data字典
        business_config: 业务参数配置字典
    
    Returns:
        映射后的RPA接口参数字典
    """
    china_southern_air_config = business_config.get("china_southern_air", {})
    booking_and_create_config = china_southern_air_config.get("booking_and_create", {})
    
    tangi_login = booking_and_create_config.get("tangi_login", {})
    china_southern_air_login = booking_and_create_config.get("china_southern_air_login", {})
    business_default = booking_and_create_config.get("business_default", {})
    default_address = business_default.get("address", {})
    
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    contact_info = form_data.get("contact_info", {})
    dangerous_goods_declaration = form_data.get("dangerous_goods_declaration", {})
    other_info = form_data.get("other_info", {})
    
    form_address = contact_info.get("address", {})
    form_region = form_address.get("region", "")
    
    if not form_region:
        form_region = default_address.get("region", "")
    
    if isinstance(form_region, list):
        region_province = form_region[0] if len(form_region) > 0 else ""
        region_city = form_region[1] if len(form_region) > 1 else ""
        region_district = form_region[2] if len(form_region) > 2 else ""
    elif isinstance(form_region, str):
        region_parts = form_region.split("/") if form_region else []
        region_province = region_parts[0] if len(region_parts) > 0 else ""
        region_city = region_parts[1] if len(region_parts) > 1 else ""
        region_district = region_parts[2] if len(region_parts) > 2 else ""
    else:
        region_province = ""
        region_city = ""
        region_district = ""
    
    address_detail = form_address.get("detail", "") or default_address.get("detail", "")
    
    address_of_app = tangi_login.get("address_of_the_application_executable_file_tangyi", "")
    if not address_of_app:
        address_of_app = tangi_login.get("app_name", "")
    
    order_contact_name_raw = other_info.get("order_contact", "") or business_default.get("order_contact_name", "")
    order_contact_phone_raw = other_info.get("contact_phone", "") or business_default.get("order_contact_phone", "")
    
    if not order_contact_phone_raw and order_contact_name_raw and "/" in order_contact_name_raw:
        parts = order_contact_name_raw.split("/", 1)
        order_contact_name_raw = parts[0] if len(parts) > 0 else order_contact_name_raw
        order_contact_phone_raw = parts[1] if len(parts) > 1 else ""
    
    params = {
        "address_of_the_application_executable_file_tangyi": address_of_app,
        "system_account": china_southern_air_login.get("system_account", ""),
        "login_password": china_southern_air_login.get("login_password", ""),
        "system_url": china_southern_air_login.get("system_url", ""),
        
        "region_province_shipper": region_province,
        "region_city_shipper": region_city,
        "region_city_district": region_district,
        "address_detail": address_detail,
        
        "order_contact_name": order_contact_name_raw,
        "order_contact_phone": order_contact_phone_raw,
        
        "agent_checker_name": dangerous_goods_declaration.get("agent_checker_signature", "") or business_default.get("agent_checker_name", ""),
        "agent_consignor_name": dangerous_goods_declaration.get("agent_consignor_signature", "") or business_default.get("agent_consignor_name", ""),
        
        "shipper": contact_info.get("shipper", "") or contact_info.get("shipper_unit", "") or business_default.get("shipper", ""),
        "shipper_phone": contact_info.get("shipper_phone", "") or business_default.get("phone", ""),
        
        "booking_remark": flight_info.get("booking_remark", "") or business_default.get("booking_remark", ""),
        "settlement_file_number": other_info.get("settlement_file_number", "") or business_default.get("settlement_file_number", ""),
        
        "origin_station": flight_info.get("origin_station", "") or business_default.get("origin_station", ""),
        "destination": flight_info.get("destination", ""),
        "flight_date": flight_info.get("flight_date", ""),
        "flight_number": flight_info.get("flight_number", ""),
        
        "cargo_type": cargo_info.get("cargo_type", "") or business_default.get("cargo_type", ""),
        "cargo_code": cargo_info.get("cargo_code", "") or business_default.get("cargo_code", ""),
        "cargo_name": cargo_info.get("cargo_name", ""),
        "quantity": cargo_info.get("quantity", ""),
        "weight": cargo_info.get("weight", ""),
        "special_cargo_code": cargo_info.get("special_cargo_code", "") or business_default.get("special_cargo_code", ""),
        
        "consignee_phone": contact_info.get("consignee_phone", ""),
        "consignee": contact_info.get("consignee", ""),
        
        "oversized_cargo": cargo_info.get("oversized_cargo", "0"),
        "no_dangerous_goods": dangerous_goods_declaration.get("no_hidden_dangerous_goods", "0"),
        
        "storage_and_transportation_precautions": cargo_info.get("storage_and_transportation_precautions", ""),
        "product_name": cargo_info.get("product_name", "")[0] if isinstance(cargo_info.get("product_name", ""), list) and len(cargo_info.get("product_name", "")) > 0 else (cargo_info.get("product_name", "") if not isinstance(cargo_info.get("product_name", ""), list) else ""),
        "booking_volume": cargo_info.get("booking_volume", "")
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
    
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    if not is_shenzhen_air:
        raise BadRequestException("当前仅支持深圳航空的运单执行")
    
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value
    )
    if existing_task:
        raise BadRequestException(f"该运单已有待执行或执行中的开单任务，任务ID: {existing_task.id}")
    
    business_config = _get_business_config(db)
    if not business_config:
        raise BadRequestException("业务参数配置不存在，无法调用深航开单接口")
    
    rpa_params = _extract_shenzhen_air_params(form_data_dict, business_config)
    
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
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        params=rpa_params,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
    )
    
    form_data_dict = json.loads(waybill.form_data)
    
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "rpa_queue_uuids": waybill.rpa_queue_uuids,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
        "task_id": str(task.id)  
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
    1. 根据运单的airline判断航空公司（深航：airline="1"或"深圳航空"，南航：airline="2"或"南方航空"）
    2. 从waybill_number中提取运单号后八位（深航去除"479-"前缀，南航去除"784-"前缀）
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
    
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    if not waybill.waybill_number:
        raise BadRequestException("运单号不存在，无法作废")
    
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    is_china_southern_air = airline == "2" or airline == "南方航空"
    
    if not is_shenzhen_air and not is_china_southern_air:
        raise BadRequestException("当前仅支持深圳航空和南方航空的运单作废")
    
    if is_shenzhen_air:
        task_type = RPATaskType.SHENZHEN_AIR_WAYBILL_VOID.value
        job_uuid = settings.RPA_SHENZHEN_AIR_VOID_JOB_UUID
        waybill_number_8 = rpa_service.extract_waybill_suffix(waybill.waybill_number)
    else:  
        task_type = RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_VOID.value
        job_uuid = settings.RPA_CHINA_SOUTHERN_AIR_VOID_JOB_UUID
        waybill_number_8 = rpa_service.extract_waybill_suffix_china_southern_air(waybill.waybill_number)
    
    existing_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        task_type=task_type
    )
    if existing_task:
        raise BadRequestException(f"该运单已有待执行或执行中的作废任务，任务ID: {existing_task.id}")
    
    if not waybill_number_8 or len(waybill_number_8) != 8:
        raise BadRequestException(f"运单号格式不正确，无法提取后八位: {waybill.waybill_number}")
    
    rpa_params = {
        "waybill_number_8": waybill_number_8
    }
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=task_type,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        params=rpa_params,
        job_uuid=job_uuid,
        priority=settings.RPA_QUEUE_DEFAULT_PRIORITY,
        created_by=current_user.id if current_user else None
    )
    
    form_data_dict = json.loads(waybill.form_data)
    
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
        "task_id": str(task.id)  
    }
    
    return success_response(data=waybill_data, msg="运单作废已加入执行队列，请等待处理")


@router.post("/{waybill_id}/execute-china-southern-air", summary="南航新增运单")
async def execute_china_southern_air_waybill(
    waybill_id: str,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    通过南航 B2E 接口同步计算费用并开单。

    本接口不创建南航开单 RPA 任务，也不依赖机器人；开单成功后会异步沿用
    既有的货站文件生成和打印任务流程。

    南航上游调用失败时，响应 `data.error_details` 会返回调用阶段、HTTP 状态、
    完整上游响应体以及发往 calculateCharge/createOrder 的完整 JSON 请求体。
    不会返回南航 Token、Cookie 或请求头。

    费用计算前会实时查询南航完整扩展服务费列表，并合并表单选择；发送给
    calculateCharge 的请求采用南航要求的最小字段结构，不复用 createOrder 请求体。
    form_data中的cargo_info.special_cargo_code保持英文逗号分隔；发往南航的
    spCode和productionCode会在请求构建阶段转换为斜杠分隔。
    """
    try:
        waybill_id_int = int(waybill_id)
    except (TypeError, ValueError) as exc:
        raise BadRequestException("运单ID格式不正确") from exc

    waybill = db.query(Waybill).filter(Waybill.id == waybill_id_int).first()
    if not waybill:
        raise NotFoundException("运单不存在")

    try:
        form_data_dict = json.loads(waybill.form_data)
    except (TypeError, json.JSONDecodeError) as exc:
        raise BadRequestException("运单表单数据格式不正确") from exc
    airline = form_data_dict.get("airline", "")

    is_china_southern_air = airline in {"2", "南方航空", "china_southern_air"}
    if not is_china_southern_air:
        raise BadRequestException("此接口仅支持南方航空的运单执行，深圳航空请使用 /execute 接口")

    # 历史上已创建、但尚未结束的 RPA 开单任务不能与直连开单并发执行。
    # 该检查仅用于兼容旧任务，直连流程本身不会创建任何 RPA 开单任务。
    from app.models.rpa_task import RPATaskType, RPATargetType
    from app.services.rpa_task_service import rpa_task_service
    legacy_task = rpa_task_service.get_pending_task_for_target(
        db,
        target_type=RPATargetType.WAYBILL.value,
        target_id=waybill_id_int,
        task_type=RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE.value,
    )
    if legacy_task is not None:
        raise BadRequestException(
            f"该运单存在历史南航开单 RPA 任务（ID: {legacy_task.id}），请待其结束后再使用直连接口"
        )

    business_config = _get_business_config(db)

    try:
        direct_order_values = china_southern_air_direct_order_service.get_form_values(
            form_data_dict, business_config
        )
    except ChinaSouthernAirDirectOrderError as exc:
        raise BadRequestException(str(exc)) from exc

    token_record = (
        db.query(NanHangToken)
        .filter(NanHangToken.token.isnot(None), NanHangToken.token != "")
        .order_by(NanHangToken.updated_at.desc(), NanHangToken.id.desc())
        .first()
    )
    if token_record is None:
        raise BaseAPIException(503, "暂无可用的南航 Token，请先完成南航 Token 获取任务")

    # booking_volume 是平台可选字段，但南航 calculateCharge/createOrder 的
    # volume 必须有值。未填写时先用始发站、重量调用 calculateCWeight 补齐；
    # 此过程发生在预占单号之前，查询失败不会消耗单号库存。
    try:
        direct_order_values["volume"] = (
            await china_southern_air_direct_order_service.resolve_volume(
                token=token_record.token,
                values=direct_order_values,
                business_config=business_config,
            )
        )
    except ChinaSouthernAirServiceError as exc:
        raise BaseAPIException(
            502,
            str(exc),
            data={"error_details": exc.details},
        ) from exc

    # 最终 volume 确定后，按当前航班、货物和产品查询南航运价舱位。
    # 查询发生在预占单号之前，失败不会消耗单号库存。
    try:
        await china_southern_air_direct_order_service.resolve_cabin_class(
            token=token_record.token,
            values=direct_order_values,
            business_config=business_config,
        )
    except ChinaSouthernAirServiceError as exc:
        raise BaseAPIException(
            502,
            str(exc),
            data={"error_details": exc.details},
        ) from exc

    # 南航会按航线、货物类型和产品返回默认特货码。默认码在前、用户码在后
    # 去重合并；平台 form_data 保持逗号格式，发往南航的值保持斜杠格式。
    try:
        special_cargo_code = (
            await china_southern_air_direct_order_service.resolve_special_cargo_code(
                token=token_record.token,
                values=direct_order_values,
                business_config=business_config,
            )
        )
    except ChinaSouthernAirServiceError as exc:
        raise BaseAPIException(
            502,
            str(exc),
            data={"error_details": exc.details},
        ) from exc

    platform_special_cargo_code = special_cargo_code["platform_code"]
    if (
        form_data_dict["cargo_info"].get("special_cargo_code")
        != platform_special_cargo_code
    ):
        try:
            locked_waybill = (
                db.query(Waybill)
                .filter(Waybill.id == waybill_id_int)
                .with_for_update()
                .first()
            )
            if locked_waybill is None:
                raise NotFoundException("运单不存在")
            if locked_waybill.airline_record_status not in {"0", "2"}:
                raise BadRequestException("该运单正在开单或已开单成功，不能更新特货码")
            try:
                latest_form_data = json.loads(locked_waybill.form_data)
            except (TypeError, json.JSONDecodeError) as exc:
                raise BadRequestException("运单表单数据格式错误") from exc
            if latest_form_data != form_data_dict:
                raise BadRequestException("运单信息已被修改，请重新执行南航开单")
            latest_form_data["cargo_info"]["special_cargo_code"] = (
                platform_special_cargo_code
            )
            locked_waybill.form_data = json.dumps(latest_form_data, ensure_ascii=False)
            db.commit()
            form_data_dict = latest_form_data
        except Exception:
            db.rollback()
            raise

    # calculateCharge 使用 queryServiceCharge 返回的完整费用列表；当表单
    # 未填写费用选项时，保持南航返回的所有费用组及 checked 状态原样透传。
    service_charge_query_data = {
        "resAllInfoList": [{"resDto": {
            "flightDep": direct_order_values["origin_station"],
            "flightDest": direct_order_values["destination"],
            "bookFlightno": direct_order_values["flight_number"],
            "bookFlightdate": direct_order_values["flight_date"],
        }}],
        "routing": (
            f"{direct_order_values['origin_station']}/"
            f"{direct_order_values['destination']}"
        ),
        "shipmentType": direct_order_values["rate_code"],
        "shipmentTypeName": direct_order_values["shipment_type_name"],
        "channel": "B2B",
    }
    try:
        service_charges = await china_southern_air_service.query_service_charges(
            token=token_record.token,
            origin_station=direct_order_values["origin_station"],
            destination=direct_order_values["destination"],
            flight_number=direct_order_values["flight_number"],
            flight_date=direct_order_values["flight_date"],
            cargo_type=direct_order_values["rate_code"],
            cargo_name=direct_order_values["shipment_type_name"],
        )
        calculate_payload = china_southern_air_direct_order_service.build_calculate_payload(
            form_data_dict,
            business_config,
            service_charges=service_charges,
            form_values=direct_order_values,
        )
    except ChinaSouthernAirServiceError as exc:
        raise BaseAPIException(
            502,
            str(exc),
            data={
                "error_details": {
                    "stage": "query_service_charges",
                    "request_data": service_charge_query_data,
                }
            },
        ) from exc
    except ChinaSouthernAirDirectOrderError as exc:
        raise BadRequestException(str(exc)) from exc

    # 短事务内锁定运单并预占单号；外部网络调用期间不持有数据库锁。
    try:
        locked_waybill = (
            db.query(Waybill)
            .filter(Waybill.id == waybill_id_int)
            .with_for_update()
            .first()
        )
        if locked_waybill is None:
            raise NotFoundException("运单不存在")
        if locked_waybill.airline_record_status not in {"0", "2"}:
            raise BadRequestException("该运单正在开单或已开单成功，不能重复提交")

        stock_item = _reserve_china_southern_air_stock_item(db)
        locked_waybill.waybill_number = stock_item.full_number
        locked_waybill.airline_record_status = "1"
        db.commit()
    except Exception:
        db.rollback()
        raise

    # 费用计算不包含运单号；同一份成功的计算结果可用于后续单号重试。
    try:
        calculation_result = await china_southern_air_direct_order_service.calculate_charge(
            token=token_record.token,
            payload=calculate_payload,
            business_config=business_config,
        )
    except ChinaSouthernAirDirectOrderError as exc:
        db.rollback()
        locked_waybill = (
            db.query(Waybill).filter(Waybill.id == waybill_id_int).with_for_update().first()
        )
        if locked_waybill is not None:
            _release_stock_item(db, stock_item.id)
            locked_waybill.waybill_number = None
            locked_waybill.airline_record_status = "2"
            db.commit()
        raise BaseAPIException(
            502,
            str(exc),
            data={"error_details": exc.details},
        ) from exc
    except Exception:
        db.rollback()
        locked_waybill = (
            db.query(Waybill).filter(Waybill.id == waybill_id_int).with_for_update().first()
        )
        if locked_waybill is not None:
            _release_stock_item(db, stock_item.id)
            locked_waybill.waybill_number = None
            locked_waybill.airline_record_status = "2"
            db.commit()
        raise

    while True:
        create_started = False
        try:
            create_payload = china_southern_air_direct_order_service.build_create_payload(
                form_data_dict,
                business_config,
                number_prefix=stock_item.number_prefix,
                number_suffix=stock_item.number_suffix,
                calculation_result=calculation_result,
                form_values=direct_order_values,
            )
            create_started = True
            await china_southern_air_direct_order_service.create_order(
                token=token_record.token,
                payload=create_payload,
                business_config=business_config,
            )
            break
        except ChinaSouthernAirDirectOrderError as exc:
            db.rollback()
            locked_waybill = (
                db.query(Waybill).filter(Waybill.id == waybill_id_int).with_for_update().first()
            )
            if locked_waybill is None:
                raise NotFoundException("运单不存在") from exc

            if exc.number_is_used:
                # 南航确认该号已被占用：本地也标记为已使用/失效，随后继续尝试下一张可用单号。
                _mark_stock_item_unavailable(db, stock_item.id, "南航提示运单号已被使用")
                locked_waybill.waybill_number = None
                locked_waybill.airline_record_status = "1"
                db.commit()

                try:
                    locked_waybill = (
                        db.query(Waybill)
                        .filter(Waybill.id == waybill_id_int)
                        .with_for_update()
                        .first()
                    )
                    if locked_waybill is None:
                        raise NotFoundException("运单不存在")
                    stock_item = _reserve_china_southern_air_stock_item(db)
                    locked_waybill.waybill_number = stock_item.full_number
                    locked_waybill.airline_record_status = "1"
                    db.commit()
                except BadRequestException as stock_exc:
                    db.rollback()
                    locked_waybill = (
                        db.query(Waybill)
                        .filter(Waybill.id == waybill_id_int)
                        .with_for_update()
                        .first()
                    )
                    if locked_waybill is not None:
                        locked_waybill.waybill_number = None
                        locked_waybill.airline_record_status = "2"
                        db.commit()
                    raise BaseAPIException(
                        409,
                        "南航提示可用单号均已被使用，未能完成开单，请补充单号库后重试",
                        data={"error_details": exc.details},
                    ) from stock_exc
                except Exception:
                    db.rollback()
                    raise
                continue

            if exc.outcome_unknown:
                # 请求可能已经被南航接收，不能把该号重新投入池中。
                _mark_stock_item_unavailable(db, stock_item.id, "南航开单完成状态不确定")
                locked_waybill.waybill_number = None
                locked_waybill.airline_record_status = "2"
                db.commit()
                raise BaseAPIException(
                    502,
                    str(exc),
                    data={"error_details": exc.details},
                ) from exc

            # 对于南航已经明确返回的业务/参数错误，可确认未开单，单号回流。
            _release_stock_item(db, stock_item.id)
            locked_waybill.waybill_number = None
            locked_waybill.airline_record_status = "2"
            db.commit()
            raise BaseAPIException(
                502,
                str(exc),
                data={"error_details": exc.details},
            ) from exc
        except Exception:
            db.rollback()
            locked_waybill = (
                db.query(Waybill).filter(Waybill.id == waybill_id_int).with_for_update().first()
            )
            if locked_waybill is not None:
                if create_started:
                    _mark_stock_item_unavailable(db, stock_item.id, "南航开单完成状态不确定")
                else:
                    _release_stock_item(db, stock_item.id)
                locked_waybill.waybill_number = None
                locked_waybill.airline_record_status = "2"
                db.commit()
            raise

    # 开单成功状态与单号库“已使用”必须在同一事务最终确认；结算落库异常
    # 不得导致远端已开单的单号被重新使用。
    try:
        waybill = db.query(Waybill).filter(Waybill.id == waybill_id_int).with_for_update().first()
        if waybill is None:
            raise NotFoundException("运单不存在")
        confirmed_stock_item = confirm_stock_item_used(
            db,
            stock_item.id,
            expected_full_number=waybill.waybill_number,
        )
        waybill.airline_record_status = "3"
        db.commit()
        print(
            "[南航直连开单] 开单成功状态与单号库状态已同步提交，"
            f"运单ID: {waybill.id}, 单号: {confirmed_stock_item.full_number}, "
            f"usage_status: {confirmed_stock_item.usage_status}, "
            f"usage_date: {confirmed_stock_item.usage_date}"
        )
    except Exception:
        db.rollback()
        raise

    if is_post_waybill_automation_enabled("2"):
        try:
            _create_china_southern_air_settlement(db, waybill, form_data_dict, calculation_result)
            db.commit()
        except Exception:
            # 远端已成功开单，保留已使用单号和成功状态，避免因本地结算异常诱发重复开单。
            db.rollback()

        db.refresh(waybill)
        background_tasks.add_task(
            _post_process_china_southern_air_waybill,
            waybill.id,
            form_data_dict,
            business_config,
        )
    else:
        print(
            "[南航直连开单] 开单后自动处理已关闭，"
            f"跳过结算单、制单、文件生成及打印，运单ID: {waybill.id}"
        )
        db.refresh(waybill)
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "departure_time": format_datetime_china(waybill.departure_time),
        "booking_date": waybill.booking_date.isoformat(),
        "rpa_work_uuid": waybill.rpa_work_uuid,
        "rpa_queue_uuids": waybill.rpa_queue_uuids,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
    }

    return success_response(data=waybill_data, msg="南航开单成功")


@router.post("/{waybill_id}/cargo-station-record", summary="深航货站录单重新执行")
async def execute_cargo_station_record(
    waybill_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    深航货站录单重新执行接口
    
    **说明**：
    - 正常情况下，货站录单会在航司录单成功后自动执行，无需手动调用此接口
    - 此接口用于以下场景：
      1. 货站录单自动执行失败后的重新执行
      2. 需要重新生成文档的情况（会覆盖之前生成的文档）
    
    此接口仅针对深圳航空，用于生成货站录单所需的文档：
    1. 交接单（仅当 cargo_info.cargo_code == "044" 时生成）
    2. 航空货物明细表（仅当 form_data.declaration_list == "0" 时生成）
    3. 货物收运检查清单（仅当 cargo_info.cargo_code == "044" 时生成）
    4. 标签单（必生成）
    5. 充氧类水生动物货物收运检查单（仅当 oxygenated_aquatic_animal_goods_receipt_inspection_form_switch == "0" 时生成）
    
    执行流程：
    1. 验证运单是否为深圳航空且航司录单状态为成功
    2. 将货站录单状态更新为"执行中"(1)
    3. 读取运单数据和业务参数配置
    4. 根据配置生成相应的Excel文档并填充数据
    5. 将Excel转换为PDF（使用纯Python实现，无需安装Microsoft Excel）
    6. 保存文件到指定目录
    7. 更新货站录单状态为"已录单"(3)或"失败"(2)
    
    状态说明：
    - 0: 未执行
    - 1: 执行中
    - 2: 执行失败
    - 3: 已录单
    
    - **waybill_id**: 运单ID（字符串格式）
    
    返回：
    - 运单信息及生成的文档路径
    """
    from app.services.cargo_station_record_service import generate_all_documents
    
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    if not waybill.waybill_number:
        raise BadRequestException("运单号不存在，需要先执行航司录单成功后才能进行货站录单")
    
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    if not is_shenzhen_air:
        raise BadRequestException("货站录单功能仅支持深圳航空")
    
    if waybill.airline_record_status != "3":
        raise BadRequestException(f"航司录单状态必须为成功才能进行货站录单，当前状态: {waybill.airline_record_status}")
    
    if waybill.cargo_station_record_status == "1":
        raise BadRequestException("货站录单正在执行中，请勿重复提交")
    
    waybill.cargo_station_record_status = "1"
    db.commit()
    
    try:
        business_config = _get_business_config(db)
        
        documents_result = generate_all_documents(
            waybill_id=int(waybill_id),
            waybill_number=waybill.waybill_number,
            form_data=form_data_dict,
            business_config=business_config
        )
        
        all_success = True
        for doc_type, doc_info in documents_result.items():
            if doc_info.get("error") or not doc_info.get("excel"):
                all_success = False
                break
        
        if all_success:
            waybill.cargo_station_record_status = "3"  
        else:
            waybill.cargo_station_record_status = "2"  
        
        db.commit()
        db.refresh(waybill)
        
        if all_success and waybill.waybill_number:
            _auto_trigger_document_print(db, waybill, form_data_dict, business_config)
        
        form_data_dict = json.loads(waybill.form_data)
        
        waybill_data = {
            "id": str(waybill.id),
            "waybill_number": waybill.waybill_number,
            "form_data": form_data_dict,
            "airline_record_status": waybill.airline_record_status,
            "cargo_station_record_status": waybill.cargo_station_record_status,
            "document_print_status": waybill.document_print_status,
            "waybill_void_status": waybill.waybill_void_status,
            "airline_record_time": format_datetime_china(waybill.airline_record_time),
            "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
            "document_print_time": format_datetime_china(waybill.document_print_time),
            "departure_time": format_datetime_china(waybill.departure_time),
            "booking_date": waybill.booking_date.isoformat(),
            "rpa_work_uuid": waybill.rpa_work_uuid,
            "created_at": format_datetime_china(waybill.created_at),
            "updated_at": format_datetime_china(waybill.updated_at),
            "documents": documents_result  
        }
        
        msg = "货站录单执行成功" if all_success else "货站录单执行失败，部分文档生成失败"
        return success_response(data=waybill_data, msg=msg)
        
    except Exception as e:
        waybill.cargo_station_record_status = "2"
        db.commit()
        import traceback
        print(f"货站录单执行失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        raise BadRequestException(f"货站录单执行失败: {str(e)}")


@router.get("/{waybill_id}/documents", summary="获取运单相关文档")
async def get_waybill_documents(
    waybill_id: str,
    doc_type: str = None,
    file_format: str = "pdf",
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取运单相关文档接口
    
    此接口用于获取运单关联的货站录单文档信息或下载文档
    支持深圳航空和南方航空的货站录单文档
    
    参数说明：
    - **waybill_id**: 运单ID（字符串格式）
    - **doc_type**: 文档类型（可选）
      - 深航文档类型：
        - handover: 交接单（仅当 cargo_code == "044" 时生成）
        - cargo_detail: 航空货物明细表（仅当 declaration_list == "0" 时生成）
        - cargo_checklist: 货物收运检查清单（仅当 cargo_code == "044" 时生成）
        - label: 标签单（必生成）
        - aquatic_animal_checklist: 充氧类水生动物货物收运检查单（仅当开关为"0"时生成）
      - 南航文档类型：
        - csa_aquatic_animal_checklist: 充氧类水生动物货物收运检查单（xlsx，仅当开关为"0"时生成）
      - 不传：返回所有文档的列表信息
    - **file_format**: 文件格式（可选，默认pdf）
      - pdf: PDF格式
      - excel: Excel格式
    
    返回：
    - 如果不传doc_type：返回所有文档的路径信息（根据航司类型返回对应文档）
    - 如果传doc_type：返回指定文档的文件内容（用于下载）
    """
    from fastapi.responses import FileResponse
    from app.services.cargo_station_record_service import (
        list_documents, get_document_path, DOC_TYPE_TO_FILENAME,
        list_csa_documents, get_csa_document_path, CSA_DOC_TYPE_TO_FILENAME
    )
    
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    is_shenzhen_air = airline == "1" or airline == "深圳航空"
    is_china_southern_air = airline == "2" or airline == "南方航空"
    
    if not doc_type:
        documents = {}
        if is_shenzhen_air:
            documents = list_documents(int(waybill_id))
        elif is_china_southern_air:
            documents = list_csa_documents(int(waybill_id))
        
        return success_response(
            data={
                "waybill_id": waybill_id,
                "waybill_number": waybill.waybill_number,
                "airline": airline,
                "documents": documents
            },
            msg="查询成功"
        )
    
    shenzhen_air_doc_types = ["handover", "cargo_detail", "cargo_checklist", "label", "aquatic_animal_checklist"]
    china_southern_air_doc_types = ["csa_aquatic_animal_checklist"]
    
    if doc_type in shenzhen_air_doc_types:
        valid_formats = ["pdf", "excel"]
        if file_format not in valid_formats:
            raise BadRequestException(f"深航文档无效的文件格式: {file_format}，支持的格式: {', '.join(valid_formats)}")
        
        doc_path = get_document_path(int(waybill_id), doc_type, file_format)
        if not doc_path or not doc_path.exists():
            raise NotFoundException(f"文档不存在: {DOC_TYPE_TO_FILENAME.get(doc_type, doc_type)}")
        
        doc_name = DOC_TYPE_TO_FILENAME.get(doc_type, doc_type)
        if file_format == "pdf":
            media_type = "application/pdf"
            filename = f"{doc_name}_{waybill.waybill_number}.pdf"
        else:
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{doc_name}_{waybill.waybill_number}.xlsx"
        
    elif doc_type in china_southern_air_doc_types:
        valid_formats = ["pdf", "excel"]
        if file_format not in valid_formats:
            file_format = "pdf"
        
        doc_path = get_csa_document_path(int(waybill_id), doc_type, file_format)
        if not doc_path or not doc_path.exists():
            raise NotFoundException(f"文档不存在: {CSA_DOC_TYPE_TO_FILENAME.get(doc_type, doc_type)}")
        
        doc_name = CSA_DOC_TYPE_TO_FILENAME.get(doc_type, doc_type)
        if file_format == "pdf":
            media_type = "application/pdf"
            filename = f"{doc_name}_{waybill.waybill_number}.pdf"
        else:
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = f"{doc_name}_{waybill.waybill_number}.xlsx"
        
    else:
        all_valid_types = shenzhen_air_doc_types + china_southern_air_doc_types
        raise BadRequestException(f"无效的文档类型: {doc_type}，支持的类型: {', '.join(all_valid_types)}")
    
    return FileResponse(
        path=str(doc_path),
        media_type=media_type,
        filename=filename
    )


@router.post("/{waybill_id}/print-document", summary="单个文档打印")
async def print_single_document(
    waybill_id: str,
    print_type: str,
    doc_type: str = None,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    单个文档打印接口
    
    此接口用于打印单个文档，支持以下打印类型：
    
    **文件打印 (print_type="file")**
    - 打印 generated_files/{waybill_id}/ 目录下的指定文档
    - 需要指定 doc_type 参数，如 "交接单"、"航空货物明细表" 等
    - 系统会自动查找对应的文件（支持 .xlsx 格式，跳过 .pdf 文件）
    
    **航司货运主单打印 (print_type="main_waybill")**
    - 调用航司货运主单打印RPA流程
    - 深航和南航均支持
    
    **南航安检申报单打印 (print_type="security_declaration")**
    - 调用南航货运安检申报单打印RPA流程
    - 仅南航支持
    
    **南航标签打印 (print_type="label")**
    - 调用南航标签打印RPA流程
    - 仅南航支持
    
    前置条件：
    - 运单必须已成功开单（airline_record_status = "3"）
    - 运单号必须存在（waybill_number 不为空）
    
    参数说明：
    - **waybill_id**: 运单ID（字符串格式）
    - **print_type**: 打印类型
      - "file": 文件打印
      - "main_waybill": 航司货运主单打印
      - "security_declaration": 安检申报单打印（南航专用）
      - "label": 标签打印（南航专用）
    - **doc_type**: 文档类型（当 print_type 为 "file" 时必填）
      - 深航文档类型：交接单、航空货物明细表、货物收运检查清单、标签单、充氧类水生动物货物收运检查单
      - 南航文档类型：充氧类水生动物货物收运检查单
    
    返回：
    - 成功：返回运单信息和打印任务信息
    - 失败：返回错误信息
    """
    from app.services.document_print_service import (
        get_printer_name_from_config,
        build_rpa_file_path,
        list_waybill_files
    )
    from app.models.rpa_task import RPATaskType, RPATargetType
    from app.services.rpa_task_service import rpa_task_service
    from app.config import settings
    
    valid_print_types = ["file", "main_waybill", "security_declaration", "label"]
    if print_type not in valid_print_types:
        raise BadRequestException(f"无效的打印类型，有效值：{', '.join(valid_print_types)}")
    
    if print_type == "file" and not doc_type:
        raise BadRequestException("文件打印类型必须指定 doc_type 参数")
    
    waybill = db.query(Waybill).filter(Waybill.id == int(waybill_id)).first()
    if not waybill:
        raise NotFoundException("运单不存在")
    
    if waybill.airline_record_status != "3":
        raise BadRequestException("运单尚未完成航司录单，无法执行打印")
    
    if not waybill.waybill_number:
        raise BadRequestException("运单号不存在，无法执行打印")
    
    form_data_dict = json.loads(waybill.form_data)
    airline = form_data_dict.get("airline", "")
    
    airline_code = ""
    if airline in ["1", "深圳航空", "shenzhen_air"]:
        airline_code = "shenzhen_air"
    elif airline in ["2", "南方航空", "china_southern_air"]:
        airline_code = "china_southern_air"
    else:
        raise BadRequestException(f"不支持的航司类型: {airline}")
    
    if print_type == "security_declaration" and airline_code != "china_southern_air":
        raise BadRequestException("安检申报单打印仅支持南航")
    if print_type == "label" and airline_code != "china_southern_air":
        raise BadRequestException("标签打印仅支持南航")
    
    config = db.query(BusinessConfig).first()
    if not config:
        raise BadRequestException("业务参数未配置，请先配置业务参数")
    business_config = json.loads(config.config_data)
    
    waybill_number_8 = waybill.waybill_number.split("-")[-1] if "-" in waybill.waybill_number else waybill.waybill_number
    
    print_task = None
    
    if print_type == "file":
        files = list_waybill_files(int(waybill_id))
        target_file = None
        for f in files:
            if f["doc_type"] == doc_type:
                target_file = f
                break
        
        if not target_file:
            raise BadRequestException(f"未找到文档：{doc_type}，请确认货站录单已完成")
        
        printer_name = get_printer_name_from_config(business_config, airline_code, doc_type)
        if not printer_name:
            raise BadRequestException(f"未配置文档 {doc_type} 的打印机，请检查业务参数中的打印机配置")
        
        rpa_file_path = build_rpa_file_path(int(waybill_id), target_file["filename"])
        
        print_task = {
            "type": "file_print",
            "job_uuid": settings.RPA_FILE_PRINT_JOB_UUID,
            "description": f"文档打印-{doc_type}",
            "params": {
                "absolute_path_to_the_file": rpa_file_path,
                "printer_name": printer_name
            }
        }
    
    elif print_type == "main_waybill":
        printer_name = get_printer_name_from_config(business_config, airline_code, "航司货运主单")
        if not printer_name:
            raise BadRequestException("未配置航司货运主单的打印机，请检查业务参数中的打印机配置")
        
        if airline_code == "shenzhen_air":
            shenzhen_air_config = business_config.get("shenzhen_air", {})
            booking_config = shenzhen_air_config.get("booking", {})
            login_config = booking_config.get("shenzhen_air_login", {})
            
            print_task = {
                "type": "shenzhen_air_main_waybill_print",
                "job_uuid": settings.RPA_SHENZHEN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
                "description": "深航-货运主单打印",
                "params": {
                    "system_url": login_config.get("system_url", ""),
                    "system_account": login_config.get("system_account", ""),
                    "login_password": login_config.get("login_password", ""),
                    "waybill_number_8": waybill_number_8,
                    "printer_name": printer_name
                }
            }
        else:
            csa_config = business_config.get("china_southern_air", {})
            booking_and_create_config = csa_config.get("booking_and_create", {})
            csa_login_config = booking_and_create_config.get("china_southern_air_login", {})
            
            print_task = {
                "type": "china_southern_air_main_waybill_print",
                "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
                "description": "南航-货运主单打印",
                "params": {
                    "system_url": csa_login_config.get("system_url", ""),
                    "system_account": csa_login_config.get("system_account", ""),
                    "login_password": csa_login_config.get("login_password", ""),
                    "waybill_number_8": waybill_number_8,
                    "printer_name": printer_name
                }
            }
    
    elif print_type == "security_declaration":
        printer_name = get_printer_name_from_config(business_config, "china_southern_air", "航空货物安检申报清单")
        if not printer_name:
            raise BadRequestException("未配置安检申报单的打印机，请检查业务参数中的打印机配置")
        
        csa_config = business_config.get("china_southern_air", {})
        booking_and_create_config = csa_config.get("booking_and_create", {})
        csa_login_config = booking_and_create_config.get("china_southern_air_login", {})
        
        print_task = {
            "type": "china_southern_air_security_print",
            "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_SECURITY_PRINT_JOB_UUID,
            "description": "南航-货运安检申报单打印",
            "params": {
                "system_url": csa_login_config.get("system_url", ""),
                "system_account": csa_login_config.get("system_account", ""),
                "login_password": csa_login_config.get("login_password", ""),
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
    
    elif print_type == "label":
        printer_name = get_printer_name_from_config(business_config, "china_southern_air", "标签单")
        if not printer_name:
            raise BadRequestException("未配置标签单的打印机，请检查业务参数中的打印机配置")
        
        csa_config = business_config.get("china_southern_air", {})
        booking_and_create_config = csa_config.get("booking_and_create", {})
        csa_login_config = booking_and_create_config.get("china_southern_air_login", {})
        tangyi_login_config = booking_and_create_config.get("tangi_login", {})
        
        print_task = {
            "type": "china_southern_air_label_print",
            "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_LABEL_PRINT_JOB_UUID,
            "description": "南航-标签打印",
            "params": {
                "address_of_the_application_executable_file_tangyi": tangyi_login_config.get("address_of_the_application_executable_file_tangyi", ""),
                "system_account": csa_login_config.get("system_account", ""),
                "login_password": csa_login_config.get("login_password", ""),
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
    
    from app.services.rpa_task_service import PRINT_TYPE_MAPPING
    sub_type = print_task.get("type", "")
    rpa_task_type = PRINT_TYPE_MAPPING.get(sub_type, RPATaskType.FILE_PRINT.value)
    
    task = rpa_task_service.create_task(
        db=db,
        task_type=rpa_task_type,
        target_type=RPATargetType.WAYBILL.value,
        target_id=int(waybill_id),
        params=print_task.get("params", {}),
        created_by=current_user.id if hasattr(current_user, 'id') else None,
        location=airline_code
    )
    
    waybill.document_print_status = "1"
    db.commit()
    
    db.refresh(waybill)
    
    waybill_data = {
        "id": str(waybill.id),
        "waybill_number": waybill.waybill_number,
        "form_data": form_data_dict,
        "airline_record_status": waybill.airline_record_status,
        "cargo_station_record_status": waybill.cargo_station_record_status,
        "document_print_status": waybill.document_print_status,
        "waybill_void_status": waybill.waybill_void_status,
        "airline_record_time": format_datetime_china(waybill.airline_record_time),
        "cargo_station_record_time": format_datetime_china(waybill.cargo_station_record_time),
        "document_print_time": format_datetime_china(waybill.document_print_time),
        "booking_date": waybill.booking_date.isoformat() if waybill.booking_date else None,
        "created_at": format_datetime_china(waybill.created_at),
        "updated_at": format_datetime_china(waybill.updated_at),
        "print_task": {
            "task_id": str(task.id),
            "print_type": print_type,
            "doc_type": doc_type,
            "description": print_task.get("description"),
            "airline": airline_code
        }
    }
    
    return success_response(
        data=waybill_data,
        msg=f"打印任务已提交：{print_task.get('description')}"
    )
