"""
RPA Worker模块
从任务队列中获取任务并执行RPA操作
"""
import json
import asyncio
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATask, RPATaskType, RPATaskStatus, RPATargetType
from app.models.waybill import Waybill
from app.models.booking import Booking
from app.models.settlement import Settlement
from app.services.rpa_service import rpa_service
from app.services.rpa_task_service import rpa_task_service
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value
from app.utils.helpers import get_china_now


class RPAWorker:
    """RPA Worker类"""
    
    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id
        self.running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动Worker"""
        if self.running:
            print(f"[Worker-{self.worker_id}] 已经在运行")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[Worker-{self.worker_id}] 已启动")
    
    def stop(self):
        """停止Worker"""
        self.running = False
        print(f"[Worker-{self.worker_id}] 已停止")
    
    def _run_loop(self):
        """Worker主循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.running:
                try:
                    loop.run_until_complete(self._process_one_task())
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 处理任务异常: {str(e)}")
                
                # 等待一段时间再查询下一个任务
                loop.run_until_complete(asyncio.sleep(settings.RPA_QUEUE_POLL_INTERVAL))
        finally:
            loop.close()
    
    async def _process_one_task(self):
        """处理一个任务"""
        db = SessionLocal()
        try:
            # 获取一个待执行的任务
            task = rpa_task_service.get_pending_task(db)
            if not task:
                return
            
            # 锁定任务
            if not rpa_task_service.lock_task(db, task.id):
                print(f"[Worker-{self.worker_id}] 任务 {task.id} 锁定失败，可能已被其他Worker处理")
                return
            
            print(f"[Worker-{self.worker_id}] 开始处理任务 {task.id}, 类型: {task.task_type}")
            
            # 根据任务类型执行不同的处理逻辑
            try:
                if task.task_type == RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value:
                    await self._execute_shenzhen_air_waybill(db, task)
                elif task.task_type == RPATaskType.SHENZHEN_AIR_WAYBILL_VOID.value:
                    await self._execute_shenzhen_air_waybill_void(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_EXECUTE.value:
                    await self._execute_china_southern_air_booking(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value:
                    await self._execute_china_southern_air_booking_cancel(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value:
                    await self._execute_china_southern_air_direct_invoice(db, task)
                else:
                    print(f"[Worker-{self.worker_id}] 未知的任务类型: {task.task_type}")
                    rpa_task_service.complete_task(db, task.id, False, error_message=f"未知的任务类型: {task.task_type}")
            except asyncio.TimeoutError:
                print(f"[Worker-{self.worker_id}] 任务 {task.id} 执行超时")
                # 更新目标状态为失败
                await self._update_target_status_failed(db, task, "RPA接口调用超时")
                rpa_task_service.timeout_task(db, task.id, "RPA接口调用超时")
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 任务 {task.id} 执行失败: {str(e)}")
                # 更新目标状态为失败
                await self._update_target_status_failed(db, task, str(e))
                rpa_task_service.complete_task(db, task.id, False, error_message=str(e))
        finally:
            db.close()
    
    async def _update_target_status_failed(self, db, task: RPATask, error_message: str):
        """更新目标状态为失败"""
        try:
            if task.target_type == RPATargetType.WAYBILL.value:
                waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
                if waybill:
                    if task.task_type == RPATaskType.SHENZHEN_AIR_WAYBILL_EXECUTE.value:
                        waybill.airline_record_status = "2"  # 失败
                    elif task.task_type == RPATaskType.SHENZHEN_AIR_WAYBILL_VOID.value:
                        waybill.waybill_void_status = "2"  # 作废失败
                    db.commit()
            elif task.target_type == RPATargetType.BOOKING.value:
                booking = db.query(Booking).filter(Booking.id == task.target_id).first()
                if booking:
                    if task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_EXECUTE.value:
                        booking.booking_status = "2"  # 失败
                    elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_BOOKING_CANCEL.value:
                        booking.booking_cancel_status = "2"  # 退舱失败
                    elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_DIRECT_INVOICE.value:
                        booking.invoice_status = "2"  # 开单失败
                    db.commit()
        except Exception as e:
            print(f"[Worker-{self.worker_id}] 更新目标状态失败: {str(e)}")
    
    async def _execute_shenzhen_air_waybill(self, db, task: RPATask):
        """执行深航开单任务"""
        params = json.loads(task.params)
        queue_params = json.loads(task.queue_params) if task.queue_params else None
        
        # 更新运单状态为执行中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        waybill.airline_record_status = "1"  # 开单中
        db.commit()
        
        # 创建队列
        queues_info = {}
        if queue_params:
            queue_configs = queue_params.get("queue_configs", [])
            for queue_config in queue_configs:
                try:
                    queue_data = await asyncio.wait_for(
                        rpa_service.create_queue(
                            queue_name=queue_config["name"],
                            max_queue_number=999,
                            is_expire=False
                        ),
                        timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                    )
                    queue_uuid = queue_data.get("queueUUID", "")
                    queue_id = str(queue_data.get("queueID", ""))
                    
                    if queue_uuid:
                        queues_info[queue_config["key"]] = {
                            "queueUUID": queue_uuid,
                            "queueID": queue_id,
                            "queueName": queue_config["name"]
                        }
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 创建队列失败: {queue_config['name']}, 错误: {str(e)}")
        
        # 保存队列信息到运单
        if queues_info:
            waybill.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 调用RPA接口（传递队列UUID，让RPA知道把数据写入哪些队列）
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_shenzhen_air_waybill(
                    system_url=params.get("system_url", ""),
                    system_account=params.get("system_account", ""),
                    login_password=params.get("login_password", ""),
                    origin_station=params.get("origin_station", ""),
                    destination=params.get("destination", ""),
                    flight_date=params.get("flight_date", ""),
                    flight_number=params.get("flight_number", ""),
                    shipper_info=params.get("shipper_info", ""),
                    consignee_info=params.get("consignee_info", ""),
                    quantity=params.get("quantity", ""),
                    weight=params.get("weight", ""),
                    freight_code=params.get("freight_code", ""),
                    cargo_code=params.get("cargo_code", ""),
                    cargo_name=params.get("cargo_name", ""),
                    waybill_type=params.get("waybill_type", ""),
                    package=params.get("package", ""),
                    queue_uuid_waybill_number=queues_info.get("waybill_number", {}).get("queueUUID", ""),
                    queue_uuid_freight_rate=queues_info.get("freight_rate", {}).get("queueUUID", ""),
                    queue_uuid_freight=queues_info.get("freight", {}).get("queueUUID", ""),
                    queue_uuid_delivery_fee=queues_info.get("delivery_fee", {}).get("queueUUID", "")
                ),
                timeout=settings.RPA_QUEUE_TASK_TIMEOUT
            )
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise Exception("RPA接口未返回workUuid")
            
            # 保存workUuid
            waybill.rpa_work_uuid = work_uuid
            db.commit()
            
            # 更新任务的workUuid
            rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
            
            # 轮询RPA状态
            await self._poll_shenzhen_air_waybill_status(db, task, waybill, work_uuid, queues_info, params)
            
        except Exception as e:
            # 清理队列
            await self._cleanup_queues(queues_info)
            waybill.rpa_queue_uuids = None
            db.commit()
            raise e
    
    async def _poll_shenzhen_air_waybill_status(self, db, task: RPATask, waybill: Waybill, work_uuid: str, queues_info: dict, params: dict):
        """轮询深航开单RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = settings.RPA_SHENZHEN_AIR_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        # 刷新运单对象
                        db.refresh(waybill)
                        
                        # 更新运单状态
                        dict_value = map_rpa_status_to_dict_value(rpa_status)
                        if dict_value:
                            waybill.airline_record_status = dict_value
                        
                        # 如果成功，获取队列数据
                        if rpa_status == 5:
                            # 处理成功后的数据获取，如果获取运单号失败，方法内部会将状态设置为失败并返回
                            await self._process_shenzhen_air_waybill_success(db, waybill, queues_info, params)
                            # 检查最终状态，如果运单号获取失败，状态会被设置为失败
                            db.refresh(waybill)
                            is_success = waybill.airline_record_status == "3" and waybill.waybill_number is not None
                            rpa_task_service.complete_task(db, task.id, is_success)
                            return
                        
                        # 如果失败，清理队列
                        elif rpa_status == 3:
                            await self._cleanup_queues(queues_info)
                            waybill.rpa_queue_uuids = None
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA执行失败")
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 轮询状态失败: {str(e)}")
                continue
        
        # 轮询超时
        await self._cleanup_queues(queues_info)
        waybill.rpa_queue_uuids = None
        waybill.airline_record_status = "2"  # 失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA状态轮询超时")
    
    async def _process_shenzhen_air_waybill_success(self, db, waybill: Waybill, queues_info: dict, params: dict):
        """处理深航开单成功后的数据获取和结算单创建"""
        waybill_number_data = None
        freight_rate_data = None
        freight_data = None
        delivery_fee_data = None
        
        try:
            # 获取运单号
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
                    print(f"[Worker-{self.worker_id}] 获取运单号失败: {str(e)}")
            
            # 如果获取运单号失败，将状态设置为失败
            if not waybill_number_retrieved:
                waybill.airline_record_status = "2"  # 失败
                print(f"[Worker-{self.worker_id}] RPA返回成功但获取运单号失败，将状态设置为失败")
                db.commit()
                return
            
            # 获取费率
            if "freight_rate" in queues_info:
                try:
                    freight_rate_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["freight_rate"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取费率失败: {str(e)}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取运费失败: {str(e)}")
            
            # 获取派送费
            if "delivery_fee" in queues_info:
                try:
                    delivery_fee_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["delivery_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取派送费失败: {str(e)}")
            
            # 创建结算单
            if waybill_number_data:
                form_data_dict = json.loads(waybill.form_data)
                flight_info = form_data_dict.get("flight_info", {})
                shipper_consignee_info = form_data_dict.get("shipper_consignee_info", {})
                cargo_info = form_data_dict.get("cargo_info", {})
                
                rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                
                settlement_data = {
                    "airline_record_time": rpa_call_time,
                    "settlement_method": "1",
                    "settlement_status": "0",
                    "financial_review": "1",
                    "master_airwaybill_number": waybill.waybill_number or "",
                    "transport_method": "0",
                    "airline": "1",
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
                
                try:
                    settlement = Settlement(
                        form_data=json.dumps(settlement_data, ensure_ascii=False),
                        waybill_void_status=waybill.waybill_void_status or "0"  # 同步运单作废状态到结算单数据库字段
                    )
                    db.add(settlement)
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 创建结算单失败: {str(e)}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            waybill.rpa_queue_uuids = None
            db.commit()
    
    async def _execute_shenzhen_air_waybill_void(self, db, task: RPATask):
        """执行深航作废任务"""
        params = json.loads(task.params)
        
        # 更新运单状态为作废中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        waybill.waybill_void_status = "1"  # 作废中
        db.commit()
        
        # 调用RPA接口
        rpa_response = await asyncio.wait_for(
            rpa_service.cancel_shenzhen_air_waybill(params.get("waybill_number_8", "")),
            timeout=settings.RPA_QUEUE_TASK_TIMEOUT
        )
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise Exception("RPA作废接口未返回workUuid")
        
        # 保存workUuid
        waybill.rpa_work_uuid = work_uuid
        db.commit()
        
        # 更新任务的workUuid
        rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
        
        # 轮询RPA状态
        await self._poll_shenzhen_air_void_status(db, task, waybill, work_uuid)
    
    async def _poll_shenzhen_air_void_status(self, db, task: RPATask, waybill: Waybill, work_uuid: str):
        """轮询深航作废RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = settings.RPA_SHENZHEN_AIR_VOID_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        db.refresh(waybill)
                        
                        # 映射作废状态
                        if rpa_status == 1:
                            waybill.waybill_void_status = "1"  # 作废中
                        elif rpa_status == 3:
                            waybill.waybill_void_status = "2"  # 作废失败
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA作废执行失败")
                            return
                        elif rpa_status == 5:
                            waybill.waybill_void_status = "3"  # 作废成功
                            
                            # 同步运单作废状态到结算单
                            if waybill.waybill_number:
                                try:
                                    from sqlalchemy import func, cast, String
                                    from sqlalchemy.dialects.mysql import JSON
                                    import json as json_lib
                                    
                                    # 方法1：使用JSON提取（更精确）
                                    settlements = db.query(Settlement).filter(
                                        func.cast(
                                            func.json_extract(
                                                cast(Settlement.form_data, JSON),
                                                "$.master_airwaybill_number"
                                            ),
                                            String(100)
                                        ) == waybill.waybill_number
                                    ).all()
                                    
                                    # 如果方法1没找到，使用方法2：遍历所有settlement（备用方案）
                                    if not settlements:
                                        print(f"[Worker-{self.worker_id}] 方法1未找到结算单，使用方法2查找: waybill_number={waybill.waybill_number}")
                                        all_settlements = db.query(Settlement).all()
                                        for settlement in all_settlements:
                                            try:
                                                form_data_dict = json_lib.loads(settlement.form_data)
                                                master_airwaybill_number = form_data_dict.get("master_airwaybill_number", "")
                                                if master_airwaybill_number == waybill.waybill_number:
                                                    settlements.append(settlement)
                                            except Exception as e:
                                                continue
                                    
                                    # 更新所有匹配的结算单的waybill_void_status数据库字段
                                    if settlements:
                                        for settlement in settlements:
                                            settlement.waybill_void_status = "3"  # 作废成功
                                            print(f"[Worker-{self.worker_id}] 已同步运单作废状态到结算单: settlement_id={settlement.id}, waybill_number={waybill.waybill_number}, waybill_void_status=3")
                                    else:
                                        print(f"[Worker-{self.worker_id}] 警告：未找到对应的结算单，waybill_number={waybill.waybill_number}")
                                except Exception as e:
                                    import traceback
                                    print(f"[Worker-{self.worker_id}] 同步运单作废状态到结算单失败: {str(e)}")
                                    print(f"[Worker-{self.worker_id}] 错误详情: {traceback.format_exc()}")
                            
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 轮询作废状态失败: {str(e)}")
                continue
        
        # 轮询超时
        waybill.waybill_void_status = "2"  # 作废失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA作废状态轮询超时")
    
    async def _execute_china_southern_air_booking(self, db, task: RPATask):
        """执行南航订舱任务"""
        params = json.loads(task.params)
        queue_params = json.loads(task.queue_params) if task.queue_params else None
        
        # 更新订舱状态为执行中
        booking = db.query(Booking).filter(Booking.id == task.target_id).first()
        if not booking:
            raise Exception("订舱不存在")
        
        booking.booking_status = "1"  # 执行中
        db.commit()
        
        # 创建队列
        queue_uuid = None
        queue_id = None
        if queue_params:
            queue_name = queue_params.get("queue_name", "")
            if queue_name:
                try:
                    queue_data = await asyncio.wait_for(
                        rpa_service.create_queue(queue_name=queue_name, max_queue_number=999, is_expire=False),
                        timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                    )
                    queue_uuid = queue_data.get("queueUUID", "")
                    queue_id = str(queue_data.get("queueID", ""))
                    
                    # 保存队列信息到订舱
                    booking.rpa_queue_uuid = queue_uuid
                    booking.rpa_queue_id = queue_id
                    db.commit()
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 创建队列失败: {str(e)}")
        
        # 调用RPA接口（传递queue_uuid，让RPA知道把运单号写入哪个队列）
        try:
            # 将queue_uuid添加到params中
            params_with_queue = params.copy()
            params_with_queue["queue_uuid"] = queue_uuid or ""
            
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_booking(**params_with_queue),
                timeout=settings.RPA_QUEUE_TASK_TIMEOUT
            )
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise Exception("RPA订舱接口未返回workUuid")
            
            # 保存workUuid
            booking.rpa_work_uuid = work_uuid
            db.commit()
            
            # 更新任务的workUuid
            rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
            
            # 轮询RPA状态
            await self._poll_china_southern_air_booking_status(db, task, booking, work_uuid, queue_uuid, queue_id)
            
        except Exception as e:
            # 清理队列
            if queue_id:
                try:
                    await rpa_service.delete_queue(queue_id)
                except:
                    pass
                booking.rpa_queue_uuid = None
                booking.rpa_queue_id = None
                db.commit()
            raise e
    
    async def _poll_china_southern_air_booking_status(self, db, task: RPATask, booking: Booking, work_uuid: str, queue_uuid: str, queue_id: str):
        """轮询南航订舱RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = settings.RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_china_southern_air_booking_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        db.refresh(booking)
                        
                        dict_value = map_rpa_status_to_dict_value(rpa_status)
                        if dict_value:
                            booking.booking_status = dict_value
                        
                        # 如果成功，获取运单号
                        if rpa_status == 5:
                            waybill_number_retrieved = False
                            # 优先使用传入的queue_uuid，如果为空则从数据库读取
                            actual_queue_uuid = queue_uuid or booking.rpa_queue_uuid
                            actual_queue_id = queue_id or booking.rpa_queue_id
                            
                            if actual_queue_uuid:
                                try:
                                    waybill_suffix = await rpa_service.get_china_southern_air_waybill_number(actual_queue_uuid)
                                    if waybill_suffix:
                                        booking.master_airwaybill_number = rpa_service.format_china_southern_air_waybill_number(waybill_suffix)
                                        waybill_number_retrieved = True
                                except Exception as e:
                                    print(f"[Worker-{self.worker_id}] 获取南航运单号失败: {str(e)}")
                            else:
                                print(f"[Worker-{self.worker_id}] 订舱 {booking.id} 没有queue_uuid，无法获取运单号")
                            
                            # 如果获取运单号失败，将状态设置为失败
                            if not waybill_number_retrieved:
                                booking.booking_status = "2"  # 失败
                                print(f"[Worker-{self.worker_id}] RPA返回成功但获取主单号失败，将状态设置为失败")
                            
                            # 清理队列
                            if actual_queue_id:
                                try:
                                    await rpa_service.delete_queue(actual_queue_id)
                                except:
                                    pass
                                booking.rpa_queue_uuid = None
                                booking.rpa_queue_id = None
                            
                            db.commit()
                            # 只有成功获取运单号时才标记任务为成功
                            rpa_task_service.complete_task(db, task.id, waybill_number_retrieved)
                            return
                        
                        # 如果失败，清理队列
                        elif rpa_status == 3:
                            if queue_id:
                                try:
                                    await rpa_service.delete_queue(queue_id)
                                except:
                                    pass
                                booking.rpa_queue_uuid = None
                                booking.rpa_queue_id = None
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA订舱执行失败")
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 轮询订舱状态失败: {str(e)}")
                continue
        
        # 轮询超时
        if queue_id:
            try:
                await rpa_service.delete_queue(queue_id)
            except:
                pass
            booking.rpa_queue_uuid = None
            booking.rpa_queue_id = None
        booking.booking_status = "2"  # 失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA订舱状态轮询超时")
    
    async def _execute_china_southern_air_booking_cancel(self, db, task: RPATask):
        """执行南航退舱任务"""
        params = json.loads(task.params)
        
        # 更新订舱状态为退舱中
        booking = db.query(Booking).filter(Booking.id == task.target_id).first()
        if not booking:
            raise Exception("订舱不存在")
        
        booking.booking_cancel_status = "1"  # 退舱中
        db.commit()
        
        # 调用RPA接口
        rpa_response = await asyncio.wait_for(
            rpa_service.cancel_china_southern_air_booking(
                system_url=params.get("system_url", ""),
                system_account=params.get("system_account", ""),
                login_password=params.get("login_password", ""),
                waybill_number_8=params.get("waybill_number_8", "")
            ),
            timeout=settings.RPA_QUEUE_TASK_TIMEOUT
        )
        
        # 提取workUuid
        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise Exception("RPA退舱接口未返回workUuid")
        
        # 保存workUuid
        booking.rpa_work_uuid = work_uuid
        db.commit()
        
        # 更新任务的workUuid
        rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
        
        # 轮询RPA状态
        await self._poll_china_southern_air_cancel_status(db, task, booking, work_uuid)
    
    async def _poll_china_southern_air_cancel_status(self, db, task: RPATask, booking: Booking, work_uuid: str):
        """轮询南航退舱RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = settings.RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_china_southern_air_cancel_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        db.refresh(booking)
                        
                        if rpa_status == 1:
                            booking.booking_cancel_status = "1"  # 退舱中
                        elif rpa_status == 3:
                            booking.booking_cancel_status = "2"  # 退舱失败
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA退舱执行失败")
                            return
                        elif rpa_status == 5:
                            booking.booking_cancel_status = "3"  # 退舱成功
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 轮询退舱状态失败: {str(e)}")
                continue
        
        # 轮询超时
        booking.booking_cancel_status = "2"  # 退舱失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA退舱状态轮询超时")
    
    async def _execute_china_southern_air_direct_invoice(self, db, task: RPATask):
        """执行南航直接开单任务"""
        params = json.loads(task.params)
        queue_params = json.loads(task.queue_params) if task.queue_params else None
        
        # 更新订舱开单状态为开单中
        booking = db.query(Booking).filter(Booking.id == task.target_id).first()
        if not booking:
            raise Exception("订舱不存在")
        
        booking.invoice_status = "1"  # 开单中
        db.commit()
        
        # 创建队列
        queues_info = {}
        if queue_params:
            queue_configs = queue_params.get("queue_configs", [])
            for queue_config in queue_configs:
                try:
                    queue_data = await asyncio.wait_for(
                        rpa_service.create_queue(
                            queue_name=queue_config["name"],
                            max_queue_number=999,
                            is_expire=False
                        ),
                        timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                    )
                    queue_uuid = queue_data.get("queueUUID", "")
                    queue_id = str(queue_data.get("queueID", ""))
                    
                    if queue_uuid:
                        queues_info[queue_config["key"]] = {
                            "queueUUID": queue_uuid,
                            "queueID": queue_id,
                            "queueName": queue_config["name"]
                        }
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 创建队列失败: {queue_config['name']}, 错误: {str(e)}")
        
        # 保存队列信息到订舱
        if queues_info:
            booking.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 调用RPA接口（传递队列UUID，让RPA知道把数据写入哪些队列）
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_direct_invoice(
                    system_url=params.get("system_url", ""),
                    system_account=params.get("system_account", ""),
                    login_password=params.get("login_password", ""),
                    waybill_number_8=params.get("waybill_number_8", ""),
                    queue_uuid_rate=queues_info.get("rate", {}).get("queueUUID", ""),
                    queue_uuid_freight=queues_info.get("freight", {}).get("queueUUID", ""),
                    queue_uuid_fuel_costs=queues_info.get("fuel_costs", {}).get("queueUUID", ""),
                    queue_uuid_extended_service_fee=queues_info.get("extended_service_fee", {}).get("queueUUID", "")
                ),
                timeout=settings.RPA_QUEUE_TASK_TIMEOUT
            )
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise Exception("RPA直接开单接口未返回workUuid")
            
            # 保存workUuid
            booking.rpa_work_uuid = work_uuid
            db.commit()
            
            # 更新任务的workUuid
            rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
            
            # 轮询RPA状态
            await self._poll_china_southern_air_direct_invoice_status(db, task, booking, work_uuid, queues_info, params)
            
        except Exception as e:
            # 清理队列
            await self._cleanup_queues(queues_info)
            booking.rpa_queue_uuids = None
            db.commit()
            raise e
    
    async def _poll_china_southern_air_direct_invoice_status(self, db, task: RPATask, booking: Booking, work_uuid: str, queues_info: dict, params: dict):
        """轮询南航直接开单RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_china_southern_air_direct_invoice_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        db.refresh(booking)
                        
                        # 更新开单状态
                        if rpa_status == 1:
                            booking.invoice_status = "1"  # 开单中
                        elif rpa_status == 3:
                            booking.invoice_status = "2"  # 开单失败
                            await self._cleanup_queues(queues_info)
                            booking.rpa_queue_uuids = None
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA直接开单执行失败")
                            return
                        elif rpa_status == 5:
                            booking.invoice_status = "3"  # 开单成功
                            # 获取队列数据并创建结算单
                            await self._process_china_southern_air_direct_invoice_success(db, booking, queues_info, params)
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 轮询直接开单状态失败: {str(e)}")
                continue
        
        # 轮询超时
        await self._cleanup_queues(queues_info)
        booking.rpa_queue_uuids = None
        booking.invoice_status = "2"  # 开单失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA直接开单状态轮询超时")
    
    async def _process_china_southern_air_direct_invoice_success(self, db, booking: Booking, queues_info: dict, params: dict):
        """处理南航直接开单成功后的数据获取和结算单创建"""
        rate_data = None
        freight_data = None
        fuel_costs_data = None
        extended_service_fee_data = None
        
        try:
            # 获取费率
            if "rate" in queues_info:
                try:
                    rate_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["rate"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取费率失败: {str(e)}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取运费失败: {str(e)}")
            
            # 获取燃油费
            if "fuel_costs" in queues_info:
                try:
                    fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["fuel_costs"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取燃油费失败: {str(e)}")
            
            # 获取延伸服务费
            if "extended_service_fee" in queues_info:
                try:
                    extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["extended_service_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"[Worker-{self.worker_id}] 获取延伸服务费失败: {str(e)}")
            
            # 创建结算单
            form_data_dict = json.loads(booking.form_data)
            bookings = form_data_dict.get("bookings", [{}])
            booking_item = bookings[0] if bookings else {}
            flight_info = booking_item.get("flight_info", {}) or {}
            cargo_info = booking_item.get("cargo_info", {}) or {}
            contact_info = booking_item.get("contact_info", {}) or {}
            
            rpa_call_time = get_china_now().strftime("%Y-%m-%d")
            
            settlement_data = {
                "airline_record_time": rpa_call_time,
                "settlement_method": "1",
                "settlement_status": "0",
                "financial_review": "1",
                "master_airwaybill_number": booking.master_airwaybill_number or "",
                "transport_method": "0",
                "airline": "2",  # 南航
                "origin_station": flight_info.get("origin_station", "") or booking_item.get("origin_station", ""),
                "destination": flight_info.get("destination", "") or booking_item.get("destination", ""),
                "flight_number": flight_info.get("flight_number", "") or booking_item.get("flight_number", ""),
                "flight_date": flight_info.get("flight_date", "") or booking_item.get("flight_date", ""),
                "customer_name": params.get("shipper", ""),
                "recipient_name": contact_info.get("consignee", "") or booking_item.get("consignee", ""),
                "cargo_name": cargo_info.get("cargo_name", "") or booking_item.get("cargo_name", ""),
                "quantity": cargo_info.get("quantity", "") or booking_item.get("quantity", ""),
                "weight": cargo_info.get("weight", "") or booking_item.get("weight", ""),
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
            
            try:
                settlement = Settlement(
                    form_data=json.dumps(settlement_data, ensure_ascii=False)
                )
                db.add(settlement)
            except Exception as e:
                print(f"[Worker-{self.worker_id}] 创建结算单失败: {str(e)}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            booking.rpa_queue_uuids = None
            db.commit()
    
    async def _cleanup_queues(self, queues_info: dict):
        """清理队列"""
        for queue_key, queue_info in queues_info.items():
            if "queueID" in queue_info:
                try:
                    await rpa_service.delete_queue(queue_info["queueID"])
                except Exception as e:
                    print(f"[Worker] 删除队列失败 ({queue_key}): {str(e)}")


# 全局Worker管理器
class RPAWorkerManager:
    """RPA Worker管理器"""
    
    def __init__(self):
        self.workers: list[RPAWorker] = []
    
    def start_workers(self):
        """启动所有Worker"""
        if not settings.RPA_QUEUE_ENABLED:
            print("RPA任务队列已禁用，不启动Worker")
            return
        
        worker_count = settings.RPA_QUEUE_WORKER_COUNT
        print(f"启动 {worker_count} 个RPA Worker")
        
        for i in range(worker_count):
            worker = RPAWorker(worker_id=i + 1)
            worker.start()
            self.workers.append(worker)
    
    def stop_workers(self):
        """停止所有Worker"""
        for worker in self.workers:
            worker.stop()
        self.workers.clear()


# 全局单例
rpa_worker_manager = RPAWorkerManager()

