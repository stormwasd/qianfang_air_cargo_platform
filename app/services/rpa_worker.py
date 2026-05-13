"""
RPA Worker模块
从任务队列中获取任务并执行RPA操作
"""
import json
import asyncio
import threading
import traceback
from typing import Optional, Dict, Any
from datetime import datetime

from app.database import SessionLocal
from app.config import settings
from app.models.rpa_task import RPATask, RPATaskType, RPATaskStatus, RPATargetType
from app.models.robot import Robot, RobotJob
from app.models.waybill import Waybill
from app.models.booking import Booking
from app.models.settlement import Settlement
from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.services.rpa_service import rpa_service
from app.services.rpa_task_service import rpa_task_service, PRINT_TASK_TYPES, PRINT_TYPE_REVERSE_MAPPING, PRINT_TYPE_MAPPING
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value
from app.utils.helpers import get_china_now


def _get_error_detail(e: Exception) -> str:
    """从异常中提取完整的错误描述信息。
    
    兼容 FastAPI/Starlette HTTPException 子类（如 BadRequestException），
    其错误信息存储在 .detail 属性而非 str() 中。
    当 str(e) 为空时回退到 repr(e) 确保始终有可读信息。
    """
    detail = getattr(e, "detail", None)
    if detail is not None:
        return str(detail)
    msg = str(e)
    return msg if msg else repr(e)


class RPAWorker:
    """RPA Worker类 - 每个Worker绑定到一台物理机器人"""
    
    def __init__(self, robot_db_id: int, robot_name: str = "未知机器人"):
        self.robot_db_id = robot_db_id
        self.robot_name = robot_name
        self.running = False
        self._thread: Optional[threading.Thread] = None
    
    @property
    def _log_prefix(self) -> str:
        return f"[Worker-{self.robot_name}]"
    
    def start(self):
        """启动Worker"""
        if self.running:
            print(f"{self._log_prefix} 已经在运行")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"{self._log_prefix} 已启动")
    
    def stop(self):
        """停止Worker"""
        self.running = False
        print(f"{self._log_prefix} 已停止")
    
    def _run_loop(self):
        """Worker主循环"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.running:
                try:
                    loop.run_until_complete(self._process_one_task())
                except Exception as e:
                    print(f"{self._log_prefix} 处理任务异常: {_get_error_detail(e)}\n{traceback.format_exc()}")
                
                # 等待一段时间再查询下一个任务
                loop.run_until_complete(asyncio.sleep(settings.RPA_QUEUE_POLL_INTERVAL))
        finally:
            loop.close()
    
    def _resolve_job_uuid(self, db, task_type: str) -> Optional[str]:
        """从 robot_jobs 表解析该机器人对应任务类型的 job_uuid"""
        robot_job = db.query(RobotJob).filter(
            RobotJob.robot_id == self.robot_db_id,
            RobotJob.task_name == task_type
        ).first()
        return robot_job.job_uuid if robot_job else None
    
    def _apply_extra_config_overrides(self, db, task: RPATask, robot: Robot):
        """
        应用机器人 extra_config 中的参数覆盖
        
        覆盖规则：
        1. shenzhen_air_account: account+password 均非空 → 替换 system_account, login_password
        2. printer_service: 三种打印机均非空 → 将 printer_name（打印机类型）映射为真实打印机名称
        3. tangyi_program: executable_path 非空 → 替换 address_of_the_application_executable_file_tangyi
        
        只有当机器人的 location 与任务的 location 匹配时才进行覆盖。
        """
        if not robot.extra_config:
            return
        
        try:
            extra_config = json.loads(robot.extra_config) if isinstance(robot.extra_config, str) else robot.extra_config
        except (json.JSONDecodeError, TypeError):
            return
        
        if not extra_config or not isinstance(extra_config, dict):
            return
        
        # 解析当前任务参数
        try:
            params = json.loads(task.params) if isinstance(task.params, str) else task.params
        except (json.JSONDecodeError, TypeError):
            return
        
        if not isinstance(params, dict):
            return
        
        modified = False
        
        # 1. shenzhen_air_account 覆盖 system_account + login_password
        # 仅针对深航任务进行账号覆盖
        if task.location == "shenzhen_air":
            sz_account = extra_config.get("shenzhen_air_account")
            if isinstance(sz_account, dict):
                account = sz_account.get("account", "")
                password = sz_account.get("password", "")
                if account and password:
                    if "system_account" in params:
                        params["system_account"] = account
                        params["login_password"] = password
                        modified = True
                        print(f"{self._log_prefix} [extra_config] 覆盖 system_account/login_password (来自 shenzhen_air_account)")
        
        # 2. printer_service 覆盖 printer_name
        #    printer_name 字段存储的是打印机类型（如 normal_a4_printer / dot_matrix_printer / label_printer），
        #    通过机器人 printer_service 映射为真实打印机名称。
        printer_svc = extra_config.get("printer_service")
        if isinstance(printer_svc, dict):
            normal = printer_svc.get("normal_a4_printer", "")
            dot_matrix = printer_svc.get("dot_matrix_printer", "")
            label = printer_svc.get("label_printer", "")
            if normal and dot_matrix and label:
                # 直接覆盖顶层 printer_name（打印机类型 → 真实名称）
                if "printer_name" in params:
                    resolved = printer_svc.get(params["printer_name"])
                    if resolved:
                        print(f"{self._log_prefix} [extra_config] 覆盖 printer_name: {params['printer_name']} → {resolved}")
                        params["printer_name"] = resolved
                        modified = True
                    else:
                        print(f"{self._log_prefix} [extra_config] printer_name '{params['printer_name']}' 不是已知的打印机类型，保持原值")
                # 对于打印子任务（tasks 数组内的 params），也进行类型→名称转换
                if "tasks" in params and isinstance(params["tasks"], list):
                    for sub_task in params["tasks"]:
                        sub_params = sub_task.get("params", {})
                        if isinstance(sub_params, dict) and "printer_name" in sub_params:
                            resolved = printer_svc.get(sub_params["printer_name"])
                            if resolved:
                                sub_params["printer_name"] = resolved
                                modified = True
        
        # 3. tangyi_program 覆盖 address_of_the_application_executable_file_tangyi
        # 仅针对南航任务进行唐翼程序覆盖
        if task.location == "china_southern_air":
            tangyi = extra_config.get("tangyi_program")
            if isinstance(tangyi, dict):
                exe_path = tangyi.get("executable_path", "")
                if exe_path:
                    if "address_of_the_application_executable_file_tangyi" in params:
                        params["address_of_the_application_executable_file_tangyi"] = exe_path
                        modified = True
                        print(f"{self._log_prefix} [extra_config] 覆盖 tangyi executable_path → {exe_path}")
                    # 对于打印子任务（tasks 数组内的 params），也进行覆盖
                    if "tasks" in params and isinstance(params["tasks"], list):
                        for sub_task in params["tasks"]:
                            sub_params = sub_task.get("params", {})
                            if isinstance(sub_params, dict) and "address_of_the_application_executable_file_tangyi" in sub_params:
                                sub_params["address_of_the_application_executable_file_tangyi"] = exe_path
                                modified = True
        
        # 写回 task.params
        if modified:
            task.params = json.dumps(params, ensure_ascii=False)
    
    def _resolve_queue_names(self, db, task: RPATask):
        """
        从 robot_queues 表读取该机器人专属的队列名称，动态覆盖 task.queue_params。
        
        覆盖逻辑：
        1. 根据 task.robot_id + task.task_type 查询 robot_queues 表
        2. 如果找到队列配置，重新构造 queue_params（统一为 queue_configs 格式）
        3. 将新的 queue_params 写回 task.queue_params
        """
        from app.models.robot import RobotQueue
        from app.services.rpa_task_service import TASK_QUEUE_CONFIGS
        
        # 只有需要队列的任务类型才处理
        if task.task_type not in TASK_QUEUE_CONFIGS:
            return
        
        robot_id = task.robot_id
        if not robot_id:
            return
        
        # 查询该机器人该任务类型的所有队列配置
        queues = db.query(RobotQueue).filter(
            RobotQueue.robot_id == robot_id,
            RobotQueue.task_name == task.task_type
        ).all()
        
        if not queues:
            print(f"{self._log_prefix} [队列] 未找到机器人 {robot_id} 的队列配置（task_type={task.task_type}），保留原始 queue_params")
            return
        
        # 构造统一格式的 queue_configs
        queue_configs = []
        for q in queues:
            queue_configs.append({
                "name": q.queue_name,
                "key": q.queue_key
            })
        
        new_queue_params = {"queue_configs": queue_configs}
        task.queue_params = json.dumps(new_queue_params, ensure_ascii=False)
        print(f"{self._log_prefix} [队列] 已替换为机器人专属队列: {[c['key'] + '=' + c['name'] for c in queue_configs]}")
    
    @staticmethod
    def _build_queue_names_for_flow(queues_info: dict) -> dict:
        """
        从 queues_info 中提取队列名称，构建 RPA 流程 inputParam 所需的 queue_names 字典。
        
        转换规则：queue_key → queue_{queue_key} = queue_name
        例如：{"waybill_number": {"queueName": "xxx"}} → {"queue_waybill_number": "xxx"}
        """
        if not queues_info:
            return {}
        queue_names = {}
        for key, info in queues_info.items():
            queue_names[f"queue_{key}"] = info.get("queueName", "")
        return queue_names
    
    @staticmethod
    def _allocate_waybill_number_from_stock(db, airline_name: str) -> WaybillStockItem:
        """
        从单号库中分配一个可用的运单号。
        
        查询条件：usage_status="0"(未使用) AND is_abnormal="1"(正常) AND is_invalid="0"(未失效)
        分配后将 usage_status 改为 "1"(已使用)，usage_date 设为当天。
        
        Args:
            db: 数据库会话
            airline_name: 航司名称（如 shenzhen_air、china_southern_air）
        
        Returns:
            WaybillStockItem 对象
        
        Raises:
            Exception: 没有可用单号时抛出异常
        """
        stock_item = (
            db.query(WaybillStockItem)
            .join(WaybillStockBatch, WaybillStockItem.batch_id == WaybillStockBatch.id)
            .join(WaybillStock, WaybillStockBatch.stock_id == WaybillStock.id)
            .filter(
                WaybillStock.airline_name == airline_name,
                WaybillStockItem.usage_status == "0",
                WaybillStockItem.is_abnormal == "1",
                WaybillStockItem.is_invalid == "0"
            )
            .order_by(WaybillStockItem.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        
        if not stock_item:
            raise Exception(f"航司 {airline_name} 的单号库中没有可用单号，请及时补充单号库")
        
        stock_item.usage_status = "1"
        stock_item.usage_date = get_china_now().date()
        db.commit()
        db.refresh(stock_item)
        print(f"[单号库] 已分配单号 {stock_item.full_number}, usage_status={stock_item.usage_status}, usage_date={stock_item.usage_date}")
        
        return stock_item
    

    
    async def _process_one_task(self):
        """处理一个任务"""
        import json as _json
        db = SessionLocal()
        try:
            # 1. 重新查询机器人最新状态（支持运行时热变更）
            robot = db.query(Robot).filter(Robot.id == self.robot_db_id).first()
            if not robot:
                return
            
            # 机器人已禁用，跳过本轮
            if robot.status != 1:
                return
            
            # 解析最新权限列表
            try:
                permissions = _json.loads(robot.task_permissions) if robot.task_permissions else []
            except (_json.JSONDecodeError, TypeError):
                permissions = []
            
            if not permissions:
                return
            
            # 更新机器人名称（可能被修改）
            self.robot_name = robot.name
            
            # 2. 获取该机器人可消费的一个待执行任务（按权限+location匹配）
            task = rpa_task_service.get_pending_task_for_robot(
                db, self.robot_db_id, permissions,
                robot_location=robot.location if robot.location_required == 1 else None
            )
            if not task:
                return
            
            # 3. 锁定任务
            if not rpa_task_service.lock_task(db, task.id):
                print(f"{self._log_prefix} 任务 {task.id} 锁定失败，可能已被其他Worker处理")
                return
            
            # 4. 从 robot_jobs 表解析该机器人对应的 job_uuid，并记录消费机器人
            if task.robot_id is None:
                task.robot_id = self.robot_db_id
            resolved_job_uuid = self._resolve_job_uuid(db, task.task_type)
            if resolved_job_uuid:
                task.job_uuid = resolved_job_uuid
            
            # 5. 应用机器人 extra_config 参数覆盖（替换 system_account/login_password/printer_name 等）
            self._apply_extra_config_overrides(db, task, robot)
            
            # 6. 动态替换队列名称（从 robot_queues 表获取该机器人专属的队列名称）
            self._resolve_queue_names(db, task)
            
            db.commit()
            
            print(f"{self._log_prefix} 开始处理任务 {task.id}, 类型: {task.task_type}, location: {task.location}, job_uuid: {task.job_uuid}")
            
            # 5. 根据任务类型执行不同的处理逻辑
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
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_VOID.value:
                    await self._execute_china_southern_air_waybill_void(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE.value:
                    await self._execute_china_southern_air_waybill(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value:
                    await self._execute_china_southern_air_invoice_with_data(db, task)
                elif task.task_type == RPATaskType.FILE_PRINT.value:
                    await self._execute_individual_print(db, task)
                elif task.task_type == RPATaskType.SHENZHEN_AIR_MAIN_WAYBILL_PRINT.value:
                    await self._execute_individual_print(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT.value:
                    await self._execute_individual_print(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_SECURITY_PRINT.value:
                    await self._execute_individual_print(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_LABEL_PRINT.value:
                    await self._execute_individual_print(db, task)
                elif task.task_type == RPATaskType.SHENZHEN_AIR_KEEP_LOGIN.value:
                    await self._execute_shenzhen_air_keep_login(db, task)
                elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_KEEP_LOGIN.value:
                    await self._execute_china_southern_air_keep_login(db, task)
                elif task.task_type == RPATaskType.TANGYI_KEEP_LOGIN.value:
                    await self._execute_tangyi_keep_login(db, task)
                else:
                    print(f"{self._log_prefix} 未知的任务类型: {task.task_type}")
                    rpa_task_service.complete_task(db, task.id, False, error_message=f"未知的任务类型: {task.task_type}")
            except asyncio.TimeoutError:
                print(f"{self._log_prefix} 任务 {task.id} 执行超时")
                # 更新目标状态为失败
                await self._update_target_status_failed(db, task, "RPA接口调用超时")
                rpa_task_service.timeout_task(db, task.id, "RPA接口调用超时")
            except Exception as e:
                error_msg = _get_error_detail(e)
                print(f"{self._log_prefix} 任务 {task.id} 执行失败: {error_msg}\n{traceback.format_exc()}")
                # 更新目标状态为失败
                await self._update_target_status_failed(db, task, error_msg)
                rpa_task_service.complete_task(db, task.id, False, error_message=error_msg)
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
                    elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_VOID.value:
                        waybill.waybill_void_status = "2"  # 作废失败
                    elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE.value:
                        waybill.airline_record_status = "2"  # 开单失败
                    elif task.task_type in PRINT_TASK_TYPES:
                        waybill.document_print_status = "2"  # 打单失败
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
                    elif task.task_type == RPATaskType.CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA.value:
                        booking.invoice_status = "2"  # 开单失败
                    db.commit()
        except Exception as e:
            print(f"{self._log_prefix} 更新目标状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")

    async def _execute_keep_login_job(self, db, task: RPATask, job_uuid: str):
        """
        执行“保持登录”任务（仅传入 system_account/login_password）

        该任务不涉及机器人端队列数据的创建/读取/删除。
        """
        params = json.loads(task.params) if task.params else {}

        system_account = params.get("system_account", "")
        login_password = params.get("login_password", "")

        if not system_account or not login_password:
            raise Exception("保持登录任务参数缺失：system_account/login_password")

        # 调用RPA保持登录接口并获取workUuid
        rpa_response = await asyncio.wait_for(
            rpa_service.create_keep_login_job(
                job_uuid=job_uuid,
                system_account=system_account,
                login_password=login_password
            ),
            timeout=settings.RPA_QUEUE_TASK_TIMEOUT
        )

        work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
        if not work_uuid:
            raise Exception("RPA保持登录接口未返回workUuid")

        success, poll_error_detail = await self._poll_keep_login_job_status(
            job_uuid=job_uuid, work_uuid=work_uuid
        )
        if success:
            rpa_task_service.complete_task(db, task.id, True)
        else:
            rpa_task_service.complete_task(
                db,
                task.id,
                False,
                error_message=poll_error_detail or "RPA保持登录执行失败"
            )

    async def _poll_keep_login_job_status(self, job_uuid: str, work_uuid: str) -> tuple[bool, str]:
        """轮询保持登录RPA任务状态（status=5成功，status=3失败）"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL

        last_status = None
        last_status_desc = None
        for _ in range(max_polls):
            await asyncio.sleep(poll_interval)

            try:
                status_data = await rpa_service.query_shenzhen_air_waybill_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)

                if status_info:
                    rpa_status = status_info.get("status")
                    last_status = rpa_status
                    last_status_desc = status_info.get("statusDesc")
                    if rpa_status == 5:
                        return True, "保持登录成功"
                    if rpa_status == 3:
                        return False, f"保持登录失败: status=3 statusDesc={last_status_desc}"
            except Exception as e:
                print(
                    f"{self._log_prefix} 轮询保持登录状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}"
                )
                continue

        if last_status is not None:
            return False, f"保持登录超时: 最后状态 status={last_status} statusDesc={last_status_desc}"
        return False, "保持登录超时: 未获取到对应workUuid的状态记录"

    async def _execute_shenzhen_air_keep_login(self, db, task: RPATask):
        job_uuid = task.job_uuid or settings.RPA_SHENZHEN_AIR_KEEP_LOGIN_JOB_UUID
        await self._execute_keep_login_job(db, task, job_uuid=job_uuid)

    async def _execute_china_southern_air_keep_login(self, db, task: RPATask):
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_JOB_UUID
        await self._execute_keep_login_job(db, task, job_uuid=job_uuid)

    async def _execute_tangyi_keep_login(self, db, task: RPATask):
        job_uuid = task.job_uuid or settings.RPA_TANGYI_KEEP_LOGIN_JOB_UUID
        await self._execute_keep_login_job(db, task, job_uuid=job_uuid)
    
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
                    print(f"{self._log_prefix} 创建队列失败: {queue_config['name']}, 错误: {_get_error_detail(e)}\n{traceback.format_exc()}")
        
        # 保存队列信息到运单
        if queues_info:
            waybill.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 调用RPA接口
        queue_names = self._build_queue_names_for_flow(queues_info)
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
                    storage_and_transportation_precautions=params.get("storage_and_transportation_precautions", ""),
                    chargeable_weight=params.get("chargeable_weight", ""),
                    job_uuid=task.job_uuid,
                    queue_names=queue_names
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
        job_uuid = task.job_uuid or settings.RPA_SHENZHEN_AIR_JOB_UUID
        
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
                print(f"{self._log_prefix} 轮询状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
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
        
        # 队列数据获取重试配置（RPA状态变为成功后，数据写入队列可能有延迟）
        max_queue_retries = 5  # 最大重试次数
        queue_retry_interval = 2  # 每次重试间隔（秒）
        
        try:
            # 获取运单号（带重试机制，因为RPA写入队列可能有延迟）
            waybill_number_retrieved = False
            if "waybill_number" in queues_info:
                for retry in range(max_queue_retries):
                    try:
                        waybill_number_data = await rpa_service.get_shenzhen_air_waybill_number(
                            queues_info["waybill_number"]["queueUUID"]
                        )
                        if waybill_number_data:
                            waybill_number = rpa_service.format_shenzhen_air_waybill_number(waybill_number_data)
                            waybill.waybill_number = waybill_number
                            waybill_number_retrieved = True
                            print(f"{self._log_prefix} 获取运单号成功: {waybill_number}，重试次数: {retry}")
                            break
                        else:
                            # 返回为空，等待后重试
                            if retry < max_queue_retries - 1:
                                print(f"{self._log_prefix} 队列数据为空，等待 {queue_retry_interval} 秒后重试（{retry + 1}/{max_queue_retries}）")
                                await asyncio.sleep(queue_retry_interval)
                    except Exception as e:
                        # 发生异常，等待后重试
                        if retry < max_queue_retries - 1:
                            print(f"{self._log_prefix} 获取运单号失败: {_get_error_detail(e)}，等待 {queue_retry_interval} 秒后重试（{retry + 1}/{max_queue_retries}）\n{traceback.format_exc()}")
                            await asyncio.sleep(queue_retry_interval)
                        else:
                            print(f"{self._log_prefix} 获取运单号最终失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 如果获取运单号失败，将状态设置为失败
            if not waybill_number_retrieved:
                waybill.airline_record_status = "2"  # 失败
                print(f"{self._log_prefix} RPA返回成功但获取运单号失败（已重试{max_queue_retries}次），将状态设置为失败")
                db.commit()
                return
            
            # 获取费率
            if "freight_rate" in queues_info:
                try:
                    freight_rate_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["freight_rate"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取费率失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取运费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取派送费
            if "delivery_fee" in queues_info:
                try:
                    delivery_fee_data = await rpa_service.get_shenzhen_air_waybill_number(
                        queues_info["delivery_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取派送费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 创建结算单
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
                        waybill_void_status=waybill.waybill_void_status or "0"  # 同步运单作废状态到结算单数据库字段
                    )
                    db.add(settlement)
                except Exception as e:
                    print(f"{self._log_prefix} 创建结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                
                # 自动触发货站录单（深航开单成功后自动执行）
                try:
                    await self._auto_generate_cargo_station_documents(db, waybill, form_data_dict)
                except Exception as e:
                    print(f"{self._log_prefix} 自动生成货站录单文档失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            waybill.rpa_queue_uuids = None
            db.commit()
    
    async def _auto_generate_cargo_station_documents(self, db, waybill: Waybill, form_data_dict: dict):
        """
        自动生成货站录单文档
        
        在深航开单成功后自动触发，根据条件生成交接单、航空货物明细表、货物收运检查清单、标签单等
        
        Args:
            db: 数据库会话
            waybill: 运单对象
            form_data_dict: 运单表单数据字典
        """
        from app.services.cargo_station_record_service import generate_all_documents
        from app.models.config import BusinessConfig
        
        print(f"{self._log_prefix} 开始自动生成货站录单文档，运单ID: {waybill.id}")
        
        # 更新货站录单状态为执行中
        waybill.cargo_station_record_status = "1"
        db.commit()
        
        try:
            # 获取业务参数配置
            config = db.query(BusinessConfig).first()
            business_config = json.loads(config.config_data) if config else {}
            
            # 生成所有文档
            documents_result = generate_all_documents(
                waybill_id=waybill.id,
                waybill_number=waybill.waybill_number,
                form_data=form_data_dict,
                business_config=business_config
            )
            
            # 检查是否所有文档都生成成功
            all_success = True
            for doc_type, doc_info in documents_result.items():
                if doc_info.get("error") or not doc_info.get("excel"):
                    all_success = False
                    print(f"{self._log_prefix} 文档生成失败: {doc_type}, 错误: {doc_info.get('error')}")
                    break
            
            # 更新状态
            if all_success:
                waybill.cargo_station_record_status = "3"  # 已录单
                print(f"{self._log_prefix} 货站录单文档生成成功，运单ID: {waybill.id}")
                db.commit()
                
                # 货站录单成功后自动触发打单（延迟等待文件传输）
                await self._auto_trigger_document_print(db, waybill, form_data_dict, delay_for_file_transfer=True)
            else:
                waybill.cargo_station_record_status = "2"  # 失败
                print(f"{self._log_prefix} 货站录单文档生成失败，运单ID: {waybill.id}")
                db.commit()
            
        except Exception as e:
            waybill.cargo_station_record_status = "2"  # 失败
            db.commit()
            raise e
    
    async def _auto_generate_csa_cargo_station_documents(self, db, waybill: Waybill, form_data_dict: dict):
        """
        自动生成南航货站录单文档并在完成后自动触发打单
        
        在南航开单成功后自动触发：
        - 当 oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时：
          先生成文档，再触发打单（包含制单文档打印 + 固定打印流程）
        - 当开关不为 "0" 时：
          跳过文档生成，直接触发打单（仅固定打印流程：货运主单、安检申报单、标签单）
        
        Args:
            db: 数据库会话
            waybill: 运单对象
            form_data_dict: 运单表单数据字典
        """
        from app.services.cargo_station_record_service import (
            generate_csa_all_documents, 
            is_csa_cargo_station_record_required
        )
        from app.models.config import BusinessConfig
        
        # 检查是否需要进行货站录单
        if not is_csa_cargo_station_record_required(form_data_dict):
            print(f"{self._log_prefix} 南航运单ID: {waybill.id} 不需要货站录单（开关不为0），直接触发固定打单流程")
            # 不需要制单，但固定打单流程（货运主单、安检申报单、标签单）仍需执行
            await self._auto_trigger_document_print(db, waybill, form_data_dict)
            return
        
        print(f"{self._log_prefix} 开始南航自动生成货站录单文档，运单ID: {waybill.id}")
        
        # 更新货站录单状态为执行中
        waybill.cargo_station_record_status = "1"
        db.commit()
        
        try:
            # 获取业务参数配置
            config = db.query(BusinessConfig).first()
            business_config = json.loads(config.config_data) if config else {}
            
            # 生成所有文档（南航充氧类水生动物货物收运检查单，xlsx格式）
            documents_result = generate_csa_all_documents(
                waybill_id=waybill.id,
                waybill_number=waybill.waybill_number,
                form_data=form_data_dict,
                business_config=business_config
            )
            
            # 检查是否所有文档都生成成功
            all_success = True
            for doc_type, doc_info in documents_result.items():
                if doc_info.get("error") or not doc_info.get("excel"):
                    all_success = False
                    print(f"{self._log_prefix} 南航文档生成失败: {doc_type}, 错误: {doc_info.get('error')}")
                    break
            
            # 更新状态
            if all_success and documents_result:
                waybill.cargo_station_record_status = "3"  # 已录单
                print(f"{self._log_prefix} 南航货站录单文档生成成功，运单ID: {waybill.id}")
                db.commit()
                
                # 货站录单成功后自动触发打单（延迟等待文件传输）
                await self._auto_trigger_document_print(db, waybill, form_data_dict, delay_for_file_transfer=True)
            elif not documents_result:
                # 没有文档需要生成（理论上不会走到这里，因为前面已经检查过了）
                print(f"{self._log_prefix} 南航无文档需要生成，运单ID: {waybill.id}")
                db.commit()
            else:
                waybill.cargo_station_record_status = "2"  # 失败
                print(f"{self._log_prefix} 南航货站录单文档生成失败，运单ID: {waybill.id}")
                db.commit()
            
        except Exception as e:
            waybill.cargo_station_record_status = "2"  # 失败
            db.commit()
            raise e
    
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
            rpa_service.cancel_shenzhen_air_waybill(params.get("waybill_number_8", ""), job_uuid=task.job_uuid),
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
        job_uuid = task.job_uuid or settings.RPA_SHENZHEN_AIR_VOID_JOB_UUID
        
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
                                        print(f"{self._log_prefix} 方法1未找到结算单，使用方法2查找: waybill_number={waybill.waybill_number}")
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
                                            print(f"{self._log_prefix} 已同步运单作废状态到结算单: settlement_id={settlement.id}, waybill_number={waybill.waybill_number}, waybill_void_status=3")
                                    else:
                                        print(f"{self._log_prefix} 警告：未找到对应的结算单，waybill_number={waybill.waybill_number}")
                                except Exception as e:
                                    print(f"{self._log_prefix} 同步运单作废状态到结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                            
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"{self._log_prefix} 轮询作废状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
        waybill.waybill_void_status = "2"  # 作废失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA作废状态轮询超时")
    
    async def _execute_china_southern_air_waybill_void(self, db, task: RPATask):
        """执行南航作废任务"""
        params = json.loads(task.params)
        
        # 更新运单状态为作废中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        waybill.waybill_void_status = "1"  # 作废中
        db.commit()
        
        # 调用RPA接口
        rpa_response = await asyncio.wait_for(
            rpa_service.cancel_china_southern_air_waybill(params.get("waybill_number_8", ""), job_uuid=task.job_uuid),
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
        await self._poll_china_southern_air_void_status(db, task, waybill, work_uuid)
    
    async def _poll_china_southern_air_void_status(self, db, task: RPATask, waybill: Waybill, work_uuid: str):
        """轮询南航作废RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_VOID_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_china_southern_air_waybill_void_status(job_uuid)
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
                                        print(f"{self._log_prefix} 方法1未找到结算单，使用方法2查找: waybill_number={waybill.waybill_number}")
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
                                            print(f"{self._log_prefix} 已同步运单作废状态到结算单: settlement_id={settlement.id}, waybill_number={waybill.waybill_number}, waybill_void_status=3")
                                    else:
                                        print(f"{self._log_prefix} 警告：未找到对应的结算单，waybill_number={waybill.waybill_number}")
                                except Exception as e:
                                    print(f"{self._log_prefix} 同步运单作废状态到结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                            
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"{self._log_prefix} 轮询作废状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
        waybill.waybill_void_status = "2"  # 作废失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA作废状态轮询超时")
    
    async def _execute_china_southern_air_booking(self, db, task: RPATask):
        """执行南航订舱任务"""
        params = json.loads(task.params)
        
        # 更新订舱状态为执行中
        booking = db.query(Booking).filter(Booking.id == task.target_id).first()
        if not booking:
            raise Exception("订舱不存在")
        
        booking.booking_status = "1"  # 执行中
        db.commit()
        
        # 从单号库预分配运单号
        allocated_stock_item = None
        try:
            allocated_stock_item = self._allocate_waybill_number_from_stock(db, "china_southern_air")
            booking.master_airwaybill_number = allocated_stock_item.full_number
            db.commit()
            print(f"{self._log_prefix} 已从单号库分配南航运单号: {allocated_stock_item.number_suffix} (full: {allocated_stock_item.full_number})")
        except Exception as e:
            booking.booking_status = "2"  # 失败
            db.commit()
            raise Exception(f"单号库分配失败: {_get_error_detail(e)}")
        
        # 调用RPA接口（南航订舱不再使用队列，仅传入预分配的运单号）
        booking_queue_names = {"allocated_waybill_number": allocated_stock_item.number_suffix}
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_booking(**params, job_uuid=task.job_uuid, queue_names=booking_queue_names),
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
            await self._poll_china_southern_air_booking_status(db, task, booking, work_uuid, allocated_stock_item.id)
            
        except Exception as e:
            raise e
    
    async def _poll_china_southern_air_booking_status(self, db, task: RPATask, booking: Booking, work_uuid: str, stock_item_id: int = None):
        """轮询南航订舱RPA状态（运单号已从单号库预分配，不再从队列获取）"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID
        
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
                        
                        # 如果成功（运单号已预分配，直接标记成功）
                        if rpa_status == 5:
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        # 如果失败
                        elif rpa_status == 3:
                            # 识别具体的异常信息（如：机型识别失败）
                            await self._check_csa_booking_feedback(db, booking, work_uuid)
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA订舱执行失败")
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"{self._log_prefix} 轮询订舱状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
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
                waybill_number_8=params.get("waybill_number_8", ""),
                job_uuid=task.job_uuid
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
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID
        
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
                print(f"{self._log_prefix} 轮询退舱状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
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
                    print(f"{self._log_prefix} 创建队列失败: {queue_config['name']}, 错误: {_get_error_detail(e)}\n{traceback.format_exc()}")
        
        # 保存队列信息到订舱
        if queues_info:
            booking.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 调用RPA接口
        queue_names = self._build_queue_names_for_flow(queues_info)
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_direct_invoice(
                    system_url=params.get("system_url", ""),
                    system_account=params.get("system_account", ""),
                    login_password=params.get("login_password", ""),
                    waybill_number_8=params.get("waybill_number_8", ""),
                    job_uuid=task.job_uuid,
                    queue_names=queue_names
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
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID
        
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
                print(f"{self._log_prefix} 轮询直接开单状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
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
                    print(f"{self._log_prefix} 获取费率失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取运费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取燃油费
            if "fuel_costs" in queues_info:
                try:
                    fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["fuel_costs"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取燃油费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取延伸服务费
            if "extended_service_fee" in queues_info:
                try:
                    extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["extended_service_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取延伸服务费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 创建结算单
            # 注意：订舱的form_data结构是扁平的 {"airline": "2", "bookings": [...]}
            # 需要从 bookings[0] 中直接提取数据
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
                "airline": "2",  # 南航
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
                db.add(settlement)
            except Exception as e:
                print(f"{self._log_prefix} 创建结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 同步创建waybills记录（将bookings的form_data结构转换为waybills的form_data结构）
            new_waybill = None
            try:
                waybill_form_data = self._convert_booking_to_waybill_form_data(form_data_dict, booking_item, params)
                new_waybill = Waybill(
                    waybill_number=booking.master_airwaybill_number,
                    form_data=json.dumps(waybill_form_data, ensure_ascii=False),
                    airline_record_status="3",  # 成功（因为直接开单已成功）
                    cargo_station_record_status="0",  # 未执行
                    document_print_status="0",  # 未执行
                    waybill_void_status="0",  # 未作废
                    booking_date=get_china_now().date(),
                    rpa_work_uuid=booking.rpa_work_uuid  # 同步RPA workUuid
                )
                db.add(new_waybill)
                db.flush()  # 刷新以获取waybill的id
                print(f"{self._log_prefix} 同步创建waybill记录成功，订舱ID: {booking.id}, 运单号: {booking.master_airwaybill_number}")
                
                # 自动触发南航货站录单（仅当开关为"0"时）
                # 注意：直接开单的form_data中可能不包含oxygenated_aquatic_animal_goods_receipt_inspection_form_switch字段
                # 该字段主要在"修改数据后开单"时由用户传入
                try:
                    await self._auto_generate_csa_cargo_station_documents(db, new_waybill, waybill_form_data)
                except Exception as e:
                    print(f"{self._log_prefix} 南航直接开单自动生成货站录单文档失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            except Exception as e:
                print(f"{self._log_prefix} 同步创建waybill记录失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            booking.rpa_queue_uuids = None
            db.commit()
    
    def _convert_booking_to_waybill_form_data(self, form_data_dict: dict, booking_item: dict, params: dict) -> dict:
        """
        将bookings表的form_data结构转换为waybills表的form_data结构
        
        bookings结构：扁平结构，数据在bookings[0]中
        waybills结构：嵌套结构，按flight_info、cargo_info、contact_info等分组
        
        Args:
            form_data_dict: bookings表的form_data
            booking_item: bookings数组中的第一条记录
            params: RPA参数（包含shipper等信息）
        
        Returns:
            转换后的waybills form_data结构
        """
        # 获取业务参数中的shipper信息
        shipper = params.get("shipper", "")
        
        waybill_form_data = {
            "airline": form_data_dict.get("airline", "2"),
            "flight_info": {
                "origin_station": booking_item.get("origin_station", ""),
                "destination": booking_item.get("destination", ""),
                "flight_date": booking_item.get("flight_date", ""),
                "flight_number": booking_item.get("flight_number", ""),
                "booking_remark": booking_item.get("booking_remark", "")
            },
            "cargo_info": {
                "cargo_type": booking_item.get("cargo_type", ""),
                "cargo_code": booking_item.get("cargo_code", ""),
                "cargo_name": booking_item.get("cargo_name", ""),
                "quantity": str(booking_item.get("quantity", "")),
                "weight": str(booking_item.get("weight", "")),
                "product_name": booking_item.get("product_name", ""),
                "oversized_cargo": str(booking_item.get("oversized_cargo", "0")),
                "special_cargo_code": booking_item.get("special_cargo_code", "")
            },
            "contact_info": {
                "consignee": booking_item.get("consignee", ""),
                "consignee_phone": booking_item.get("consignee_phone", ""),
                "shipper_unit": booking_item.get("shipper_unit", ""),
                "shipper": shipper,
                "shipper_phone": ""
            },
            "dangerous_goods_declaration": {
                "no_hidden_dangerous_goods": str(booking_item.get("no_dangerous_goods", "0"))
            }
        }
        
        return waybill_form_data
    
    async def _execute_china_southern_air_waybill(self, db, task: RPATask):
        """执行南航新增运单任务"""
        params = json.loads(task.params)
        queue_params = json.loads(task.queue_params) if task.queue_params else None
        
        # 更新运单状态为执行中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        waybill.airline_record_status = "1"  # 开单中
        db.commit()
        
        # 创建队列（4个队列：运单号、费率、运费、派送费）
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
                    print(f"{self._log_prefix} 创建队列失败: {queue_config['name']}, 错误: {_get_error_detail(e)}\n{traceback.format_exc()}")
        
        # 保存队列信息到运单
        if queues_info:
            waybill.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 从单号库预分配运单号
        allocated_stock_item = None
        try:
            allocated_stock_item = self._allocate_waybill_number_from_stock(db, "china_southern_air")
            waybill.waybill_number = allocated_stock_item.full_number
            db.commit()
            print(f"{self._log_prefix} 已从单号库分配南航运单号: {allocated_stock_item.number_suffix} (full: {allocated_stock_item.full_number})")
        except Exception as e:
            waybill.airline_record_status = "2"  # 失败
            db.commit()
            raise Exception(f"单号库分配失败: {_get_error_detail(e)}")
        
        # 调用RPA接口
        queue_names = self._build_queue_names_for_flow(queues_info)
        queue_names["allocated_waybill_number"] = allocated_stock_item.number_suffix
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_waybill(
                    address_of_the_application_executable_file_tangyi=params.get("address_of_the_application_executable_file_tangyi", ""),
                    system_account=params.get("system_account", ""),
                    login_password=params.get("login_password", ""),
                    system_url=params.get("system_url", ""),
                    origin_station=params.get("origin_station", ""),
                    destination=params.get("destination", ""),
                    flight_date=params.get("flight_date", ""),
                    cargo_type=params.get("cargo_type", ""),
                    cargo_code=params.get("cargo_code", ""),
                    flight_number=params.get("flight_number", ""),
                    booking_remark=params.get("booking_remark", ""),
                    cargo_name=params.get("cargo_name", ""),
                    quantity=params.get("quantity", ""),
                    weight=params.get("weight", ""),
                    special_cargo_code=params.get("special_cargo_code", ""),
                    region_province_shipper=params.get("region_province_shipper", ""),
                    region_city_shipper=params.get("region_city_shipper", ""),
                    region_city_district=params.get("region_city_district", ""),
                    address_detail=params.get("address_detail", ""),
                    consignee_phone=params.get("consignee_phone", ""),
                    settlement_file_number=params.get("settlement_file_number", ""),
                    order_contact_name=params.get("order_contact_name", ""),
                    order_contact_phone=params.get("order_contact_phone", ""),
                    agent_checker_name=params.get("agent_checker_name", ""),
                    agent_consignor_name=params.get("agent_consignor_name", ""),
                    oversized_cargo=params.get("oversized_cargo", "0"),
                    no_dangerous_goods=params.get("no_dangerous_goods", "0"),
                    shipper=params.get("shipper", ""),
                    shipper_phone=params.get("shipper_phone", ""),
                    consignee=params.get("consignee", ""),
                    storage_and_transportation_precautions=params.get("storage_and_transportation_precautions", ""),
                    product_name=params.get("product_name", ""),
                    booking_volume=params.get("booking_volume", ""),
                    job_uuid=task.job_uuid,
                    queue_names=queue_names
                ),
                timeout=settings.RPA_QUEUE_TASK_TIMEOUT
            )
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise Exception("RPA南航新增运单接口未返回workUuid")
            
            # 保存workUuid
            waybill.rpa_work_uuid = work_uuid
            db.commit()
            
            # 更新任务的workUuid
            rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
            
            # 轮询RPA状态
            await self._poll_china_southern_air_waybill_status(db, task, waybill, work_uuid, queues_info, params, allocated_stock_item.id)
            
        except Exception as e:
            # 清理队列
            await self._cleanup_queues(queues_info)
            waybill.rpa_queue_uuids = None
            db.commit()
            raise e
    
    async def _poll_china_southern_air_waybill_status(self, db, task: RPATask, waybill: Waybill, work_uuid: str, queues_info: dict, params: dict, stock_item_id: int = None):
        """轮询南航新增运单RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_WAYBILL_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                # 查询南航新增运单任务状态
                status_data = await rpa_service.query_china_southern_air_waybill_status(job_uuid)
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
                        
                        # 如果成功，获取队列数据（运单号已预分配，只需获取费率等）
                        if rpa_status == 5:
                            await self._process_china_southern_air_waybill_success(db, waybill, queues_info, params)
                            db.refresh(waybill)
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        # 如果失败，清理队列
                        elif rpa_status == 3:
                            await self._cleanup_queues(queues_info)
                            waybill.rpa_queue_uuids = None
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA南航新增运单执行失败")
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"{self._log_prefix} 轮询南航新增运单状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
        await self._cleanup_queues(queues_info)
        waybill.rpa_queue_uuids = None
        waybill.airline_record_status = "2"  # 失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA南航新增运单状态轮询超时")
    
    async def _process_china_southern_air_waybill_success(self, db, waybill: Waybill, queues_info: dict, params: dict):
        """处理南航新增运单成功后的数据获取和结算单创建（运单号已从单号库预分配）"""
        freight_rate_data = None
        freight_data = None
        fuel_costs_data = None
        extended_service_fee_data = None
        
        try:
            # 运单号已在调用RPA前从单号库预分配，无需从队列获取
            
            # 获取费率
            if "freight_rate" in queues_info:
                try:
                    freight_rate_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["freight_rate"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取费率失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取运费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取燃油费
            if "fuel_costs" in queues_info:
                try:
                    fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["fuel_costs"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取燃油费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取延伸服务费
            if "extended_service_fee" in queues_info:
                try:
                    extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["extended_service_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取延伸服务费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 创建结算单（运单号已从单号库预分配）
            if waybill.waybill_number:
                form_data_dict = json.loads(waybill.form_data)
                flight_info = form_data_dict.get("flight_info", {})
                cargo_info = form_data_dict.get("cargo_info", {})
                contact_info = form_data_dict.get("contact_info", {})
                other_fees = form_data_dict.get("other_fees", {})
                
                rpa_call_time = get_china_now().strftime("%Y-%m-%d")
                
                settlement_data = {
                    "airline_record_time": rpa_call_time,
                    "settlement_method": "1",
                    "settlement_status": "0",
                    "financial_review": "0",
                    "master_airwaybill_number": waybill.waybill_number or "",
                    "transport_method": "2",
                    "airline": "2",  # 南航
                    "origin_station": flight_info.get("origin_station", ""),
                    "destination": flight_info.get("destination", ""),
                    "flight_number": flight_info.get("flight_number", ""),
                    "flight_date": flight_info.get("flight_date", ""),
                    "customer_name": contact_info.get("shipper_unit", ""),
                    "recipient_name": contact_info.get("consignee", ""),
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
                        form_data=json.dumps(settlement_data, ensure_ascii=False),
                        waybill_void_status=waybill.waybill_void_status or "0"  # 同步运单作废状态到结算单数据库字段
                    )
                    db.add(settlement)
                except Exception as e:
                    print(f"{self._log_prefix} 创建结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                
                # 自动触发货站录单（南航开单成功后自动执行，仅当开关为"0"时）
                try:
                    await self._auto_generate_csa_cargo_station_documents(db, waybill, form_data_dict)
                except Exception as e:
                    print(f"{self._log_prefix} 南航自动生成货站录单文档失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            waybill.rpa_queue_uuids = None
            db.commit()
    
    async def _execute_china_southern_air_invoice_with_data(self, db, task: RPATask):
        """执行南航修改数据后开单任务"""
        params = json.loads(task.params)
        queue_params = json.loads(task.queue_params) if task.queue_params else None
        
        # 更新订舱开单状态为开单中
        booking = db.query(Booking).filter(Booking.id == task.target_id).first()
        if not booking:
            raise Exception("订舱不存在")
        
        booking.invoice_status = "1"  # 开单中
        db.commit()
        
        # 创建队列（4个费用队列）
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
                    print(f"{self._log_prefix} 创建队列失败: {queue_config['name']}, 错误: {_get_error_detail(e)}\n{traceback.format_exc()}")
        
        # 保存队列信息到订舱
        if queues_info:
            booking.rpa_queue_uuids = json.dumps(queues_info, ensure_ascii=False)
            db.commit()
        
        # 调用RPA接口
        queue_names = self._build_queue_names_for_flow(queues_info)
        try:
            rpa_response = await asyncio.wait_for(
                rpa_service.create_china_southern_air_invoice_with_data(
                    system_url=params.get("system_url", ""),
                    system_account=params.get("system_account", ""),
                    login_password=params.get("login_password", ""),
                    waybill_number_8=params.get("waybill_number_8", ""),
                    flight_number=params.get("flight_number", ""),
                    flight_date=params.get("flight_date", ""),
                    booking_remark=params.get("booking_remark", ""),
                    cargo_code=params.get("cargo_code", ""),
                    cargo_name=params.get("cargo_name", ""),
                    weight=params.get("weight", ""),
                    quantity=params.get("quantity", ""),
                    volume=params.get("volume", ""),
                    special_cargo_code=params.get("special_cargo_code", ""),
                    oversized_cargo=params.get("oversized_cargo", "0"),
                    shipper=params.get("shipper", ""),
                    shipper_phone=params.get("shipper_phone", ""),
                    address_detail=params.get("address_detail", ""),
                    region_province_shipper=params.get("region_province_shipper", ""),
                    region_city_shipper=params.get("region_city_shipper", ""),
                    region_city_district=params.get("region_city_district", ""),
                    consignee=params.get("consignee", ""),
                    consignee_phone=params.get("consignee_phone", ""),
                    order_contact_phone=params.get("order_contact_phone", ""),
                    order_contact_name=params.get("order_contact_name", ""),
                    settlement_file_number=params.get("settlement_file_number", ""),
                    job_uuid=task.job_uuid,
                    queue_names=queue_names
                ),
                timeout=settings.RPA_QUEUE_TASK_TIMEOUT
            )
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                raise Exception("RPA修改数据后开单接口未返回workUuid")
            
            # 保存workUuid
            booking.rpa_work_uuid = work_uuid
            db.commit()
            
            # 更新任务的workUuid
            rpa_task_service.update_task_work_uuid(db, task.id, work_uuid)
            
            # 轮询RPA状态
            await self._poll_china_southern_air_invoice_with_data_status(db, task, booking, work_uuid, queues_info, params)
            
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            booking.rpa_queue_uuids = None
            db.commit()
    
    async def _poll_china_southern_air_invoice_with_data_status(self, db, task: RPATask, booking: Booking, work_uuid: str, queues_info: dict, params: dict):
        """轮询南航修改数据后开单RPA状态"""
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        job_uuid = task.job_uuid or settings.RPA_CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_JOB_UUID
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                status_data = await rpa_service.query_china_southern_air_invoice_with_data_status(job_uuid)
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
                            db.commit()
                            rpa_task_service.complete_task(db, task.id, False, error_message="RPA修改数据后开单执行失败")
                            return
                        elif rpa_status == 5:
                            booking.invoice_status = "3"  # 开单成功
                            # 获取队列数据并创建结算单和运单记录
                            await self._process_china_southern_air_invoice_with_data_success(db, booking, queues_info, params)
                            rpa_task_service.complete_task(db, task.id, True)
                            return
                        
                        db.commit()
            except Exception as e:
                print(f"{self._log_prefix} 轮询修改数据后开单状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
        booking.invoice_status = "2"  # 开单失败
        db.commit()
        rpa_task_service.complete_task(db, task.id, False, error_message="RPA修改数据后开单状态轮询超时")
    
    async def _process_china_southern_air_invoice_with_data_success(self, db, booking: Booking, queues_info: dict, params: dict):
        """处理南航修改数据后开单成功后的数据获取、结算单创建和运单记录同步"""
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
                    print(f"{self._log_prefix} 获取费率失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取运费
            if "freight" in queues_info:
                try:
                    freight_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["freight"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取运费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取燃油费
            if "fuel_costs" in queues_info:
                try:
                    fuel_costs_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["fuel_costs"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取燃油费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取延伸服务费
            if "extended_service_fee" in queues_info:
                try:
                    extended_service_fee_data = await rpa_service.get_china_southern_air_waybill_number(
                        queues_info["extended_service_fee"]["queueUUID"]
                    )
                except Exception as e:
                    print(f"{self._log_prefix} 获取延伸服务费失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 获取原始form_data（用户提交的修改后的数据）
            original_form_data = params.get("_original_form_data", {})
            flight_info = original_form_data.get("flight_info", {})
            cargo_info = original_form_data.get("cargo_info", {})
            contact_info = original_form_data.get("contact_info", {})
            other_fees = original_form_data.get("other_fees", {})
            
            rpa_call_time = get_china_now().strftime("%Y-%m-%d")
            
            # 创建结算单
            settlement_data = {
                "airline_record_time": rpa_call_time,
                "settlement_method": "1",
                "settlement_status": "0",
                "financial_review": "0",
                "master_airwaybill_number": booking.master_airwaybill_number or "",
                "transport_method": "2",
                "airline": "2",  # 南航
                "origin_station": flight_info.get("origin_station", ""),
                "destination": flight_info.get("destination", ""),
                "flight_number": params.get("flight_number", ""),
                "flight_date": params.get("flight_date", ""),
                "customer_name": contact_info.get("shipper_unit", ""),
                "recipient_name": params.get("consignee", ""),
                "cargo_name": params.get("cargo_name", ""),
                "quantity": params.get("quantity", ""),
                "weight": params.get("weight", ""),
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
                db.add(settlement)
                print(f"{self._log_prefix} 创建结算单成功，订舱ID: {booking.id}")
            except Exception as e:
                print(f"{self._log_prefix} 创建结算单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            
            # 同步创建waybills记录（使用用户提交的修改后的form_data）
            new_waybill = None
            try:
                # 直接使用用户提交的form_data作为运单的form_data（已经是嵌套结构）
                waybill_form_data = original_form_data.copy()
                waybill_form_data["airline"] = "2"  # 确保airline是南航
                
                new_waybill = Waybill(
                    waybill_number=booking.master_airwaybill_number,
                    form_data=json.dumps(waybill_form_data, ensure_ascii=False),
                    airline_record_status="3",  # 成功（因为开单已成功）
                    cargo_station_record_status="0",  # 未执行
                    document_print_status="0",  # 未执行
                    waybill_void_status="0",  # 未作废
                    booking_date=get_china_now().date(),
                    rpa_work_uuid=booking.rpa_work_uuid  # 同步RPA workUuid
                )
                db.add(new_waybill)
                db.flush()  # 刷新以获取waybill的id
                print(f"{self._log_prefix} 同步创建waybill记录成功，订舱ID: {booking.id}, 运单号: {booking.master_airwaybill_number}")
                
                # 自动触发南航货站录单（仅当开关为"0"时）
                try:
                    await self._auto_generate_csa_cargo_station_documents(db, new_waybill, waybill_form_data)
                except Exception as e:
                    print(f"{self._log_prefix} 南航修改数据后开单自动生成货站录单文档失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            except Exception as e:
                print(f"{self._log_prefix} 同步创建waybill记录失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
        finally:
            # 清理队列
            await self._cleanup_queues(queues_info)
            booking.rpa_queue_uuids = None
            db.commit()
    
    async def _cleanup_queues(self, queues_info: dict):
        """清理队列"""
        for queue_key, queue_info in queues_info.items():
            if "queueID" in queue_info:
                queue_id = queue_info["queueID"]
                for retry in range(3):
                    try:
                        await rpa_service.delete_queue(queue_id)
                        break
                    except Exception as e:
                        if retry == 2:
                            print(f"[Worker] 最终删除队列失败 ({queue_key}, ID: {queue_id}): {_get_error_detail(e)}\n{traceback.format_exc()}")
                        else:
                            await asyncio.sleep(1)
    
    # ========== 打单任务相关方法 ==========
    
    async def _auto_trigger_document_print(self, db, waybill: Waybill, form_data_dict: dict, delay_for_file_transfer: bool = False):
        """
        自动触发打单
        
        在以下场景调用：
        1. 货站录单成功后（cargo_station_record_status = "3"），触发完整打单流程（制单文档打印 + 固定打印流程）
        2. 南航不需要制单时（开关不为"0"），直接触发固定打印流程（货运主单、安检申报单、标签单）
        
        创建打单RPA任务到队列中，由Worker异步执行
        
        Args:
            db: 数据库会话
            waybill: 运单对象
            form_data_dict: 运单表单数据字典
            delay_for_file_transfer: 是否需要等待文件传输完成后再执行打单（货站录单生成文件后需要等待）
        """
        from app.services.document_print_service import prepare_print_tasks, get_print_task_count
        from app.models.config import BusinessConfig
        
        # 货站录单生成的文件需要传输到打印机所在的机器，等待一段时间再执行打单
        if delay_for_file_transfer:
            # 从业务参数配置中获取延迟时间（config_data.{航司}.document.print_delay_after_cargo_station_record）
            config = db.query(BusinessConfig).first()
            business_config = json.loads(config.config_data) if config else {}
            airline = form_data_dict.get("airline", "")
            airline_code = "shenzhen_air" if airline in ["1", "深圳航空", "shenzhen_air"] else ("china_southern_air" if airline in ["2", "南方航空", "china_southern_air"] else "")
            doc_config = business_config.get(airline_code, {}).get("document", {}) if airline_code else {}
            delay_val = doc_config.get("print_delay_after_cargo_station_record")
            try:
                delay_seconds = int(delay_val) if isinstance(delay_val, (int, float)) else int(str(delay_val)) if delay_val is not None else 30
            except (ValueError, TypeError):
                delay_seconds = 30
            delay_seconds = max(0, min(600, delay_seconds))  # 限制在 0-600 秒
            if delay_seconds > 0:
                print(f"{self._log_prefix} [自动打单] 等待文件传输完成，延迟 {delay_seconds} 秒后执行打单...")
                await asyncio.sleep(delay_seconds)
                print(f"{self._log_prefix} [自动打单] 延迟等待结束，开始执行打单")
        
        # 检查运单号是否存在
        if not waybill.waybill_number:
            print(f"{self._log_prefix} [自动打单] 运单号不存在，跳过自动打单，运单ID: {waybill.id}")
            return
        
        airline = form_data_dict.get("airline", "")
        print(f"{self._log_prefix} [自动打单] 开始自动触发打单，运单ID: {waybill.id}, 运单号: {waybill.waybill_number}, 航司: {airline}")
        
        try:
            # 获取业务参数配置
            config = db.query(BusinessConfig).first()
            if not config:
                print(f"{self._log_prefix} [自动打单] 业务参数未配置，跳过自动打单")
                return
            business_config = json.loads(config.config_data)
            
            # 检查打印机配置是否存在
            airline_code = ""
            if airline in ["1", "深圳航空", "shenzhen_air"]:
                airline_code = "shenzhen_air"
            elif airline in ["2", "南方航空", "china_southern_air"]:
                airline_code = "china_southern_air"
            airline_print_config = business_config.get(airline_code, {}).get("print", {}).get("printer_config", [])
            print(f"{self._log_prefix} [自动打单] 航司: {airline_code}, 打印机配置数量: {len(airline_print_config)}, 配置内容: {airline_print_config}")
            
            # 准备打印任务
            print_tasks = prepare_print_tasks(
                waybill_id=waybill.id,
                waybill_number=waybill.waybill_number,
                airline=airline,
                business_config=business_config
            )
            
            # 检查是否有打印任务
            task_count = get_print_task_count(print_tasks)
            if task_count == 0:
                print(f"{self._log_prefix} [自动打单] 没有可执行的打印任务（task_count=0），跳过自动打单。请检查业务参数中 {airline_code}.print.printer_config 是否已配置打印机")
                return
            
            # 打印任务详情
            sub_tasks = print_tasks.get("tasks", [])
            for i, t in enumerate(sub_tasks):
                print(f"{self._log_prefix} [自动打单] 打印子任务 {i+1}/{task_count}: {t.get('description')}, 类型: {t.get('type')}")
            
            # 为每个打印子任务创建独立的 rpa_tasks 记录
            created_count = 0
            for sub_task in sub_tasks:
                sub_type = sub_task.get("type", "")
                rpa_task_type = PRINT_TYPE_MAPPING.get(sub_type)
                if not rpa_task_type:
                    print(f"{self._log_prefix} [自动打单] 未知的打印子任务类型: {sub_type}，跳过")
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
            
            print(f"{self._log_prefix} [自动打单] 打单任务已成功创建！共创建 {created_count} 个独立打印任务，运单ID: {waybill.id}")
            
        except Exception as e:
            print(f"{self._log_prefix} [自动打单] 自动触发打单失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
            # 自动打单失败不影响货站录单的成功状态
    
    async def _execute_individual_print(self, db, task: RPATask):
        """
        执行独立打印任务（拆分后的单个打印任务）
        
        每个打印任务对应一条独立的 rpa_tasks 记录，params 是扁平结构：
        - FILE_PRINT: {"absolute_path_to_the_file": "...", "printer_name": "..."}
        - SHENZHEN_AIR_MAIN_WAYBILL_PRINT: {"system_url": "...", "system_account": "...", ...}
        - 其他打印类型类似
        """
        params = json.loads(task.params) if isinstance(task.params, str) else task.params
        
        # 更新运单打单状态为执行中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        if waybill.document_print_status != "1":
            waybill.document_print_status = "1"  # 打单中
            db.commit()
        
        # 将 RPATaskType 枚举值映射为 _execute_single_print_task 所需的小写类型字符串
        print_sub_type = PRINT_TYPE_REVERSE_MAPPING.get(task.task_type)
        if not print_sub_type:
            raise Exception(f"无法识别的打印任务类型: {task.task_type}")
        
        print(f"{self._log_prefix} 执行独立打印任务: {task.task_type} → {print_sub_type}")
        
        try:
            success = await self._execute_single_print_task(
                print_sub_type, task.job_uuid, params
            )
            
            if success:
                print(f"{self._log_prefix} 打印任务执行成功: {task.task_type}")
                # 检查该运单是否还有其他未完成的打印任务
                self._update_waybill_print_status(db, waybill, task)
                rpa_task_service.complete_task(db, task.id, True)
            else:
                print(f"{self._log_prefix} 打印任务执行失败: {task.task_type}")
                db.refresh(waybill)
                waybill.document_print_status = "2"  # 失败
                db.commit()
                rpa_task_service.complete_task(db, task.id, False, error_message="RPA执行失败")
        except Exception as e:
            db.refresh(waybill)
            waybill.document_print_status = "2"  # 失败
            db.commit()
            raise e
    
    def _update_waybill_print_status(self, db, waybill, current_task: RPATask):
        """
        当一个打印任务成功完成后，检查该运单是否还有其他未完成的打印任务。
        如果所有打印任务都已完成且成功，则将 document_print_status 设为 "3"（成功）。
        """
        # 查询该运单下所有打印类型的任务（排除当前任务）
        other_print_tasks = db.query(RPATask).filter(
            RPATask.target_type == RPATargetType.WAYBILL.value,
            RPATask.target_id == waybill.id,
            RPATask.task_type.in_(list(PRINT_TASK_TYPES)),
            RPATask.id != current_task.id
        ).all()
        
        # 检查是否有未完成的打印任务
        has_pending = any(
            t.status in (RPATaskStatus.PENDING.value, RPATaskStatus.RUNNING.value)
            for t in other_print_tasks
        )
        
        # 检查是否有失败的打印任务
        has_failed = any(
            t.status == RPATaskStatus.FAILED.value
            for t in other_print_tasks
        )
        
        db.refresh(waybill)
        if has_pending:
            # 还有未完成的任务，保持"打单中"
            waybill.document_print_status = "1"
        elif has_failed:
            # 有失败的任务
            waybill.document_print_status = "2"
        else:
            # 所有打印任务都已成功完成
            waybill.document_print_status = "3"
        db.commit()
    
    async def _execute_document_print(self, db, task: RPATask):
        """
        执行单据打印任务
        
        打单任务包含多个子任务，按顺序执行：
        - 制单后打印流程（遍历文件夹下的所有文件）
        - 固定打印流程（如货运主单、安检申报单、标签单等）
        
        重要：所有子任务都会被执行，不会因为某个子任务失败而中断后续任务。
        全部执行完成后，只要有一个子任务失败，整体打单状态即为失败。
        """
        params = json.loads(task.params)
        
        # 更新运单打单状态为执行中
        waybill = db.query(Waybill).filter(Waybill.id == task.target_id).first()
        if not waybill:
            raise Exception("运单不存在")
        
        waybill.document_print_status = "1"  # 打单中
        db.commit()
        
        # 获取所有打印子任务
        sub_tasks = params.get("tasks", [])
        if not sub_tasks:
            raise Exception("没有打印任务")
        
        airline = params.get("airline", "")
        waybill_id = params.get("waybill_id")
        
        total_count = len(sub_tasks)
        print(f"{self._log_prefix} 开始执行打单任务，运单ID: {waybill_id}, 航司: {airline}, 共 {total_count} 个子任务")
        
        # 用于记录每个子任务的执行结果
        task_results = []
        
        try:
            # 按顺序执行每个打印子任务（不因某个失败而中断）
            for i, print_task in enumerate(sub_tasks):
                task_type = print_task.get("type")
                task_desc = print_task.get("description", f"打印任务{i+1}")
                job_uuid = print_task.get("job_uuid")
                task_params = print_task.get("params", {})
                
                print(f"{self._log_prefix} 执行打印子任务 ({i+1}/{total_count}): {task_desc}")
                
                try:
                    # 根据任务类型调用对应的RPA接口
                    success = await self._execute_single_print_task(
                        task_type, job_uuid, task_params
                    )
                    
                    if success:
                        task_results.append({
                            "index": i + 1,
                            "description": task_desc,
                            "status": "success"
                        })
                        print(f"{self._log_prefix} 打印子任务成功 ({i+1}/{total_count}): {task_desc}")
                    else:
                        task_results.append({
                            "index": i + 1,
                            "description": task_desc,
                            "status": "failed",
                            "error": "RPA执行失败"
                        })
                        print(f"{self._log_prefix} 打印子任务失败 ({i+1}/{total_count}): {task_desc}，继续执行后续任务...")
                        
                except Exception as e:
                    task_results.append({
                        "index": i + 1,
                        "description": task_desc,
                        "status": "failed",
                        "error": _get_error_detail(e)
                    })
                    print(f"{self._log_prefix} 打印子任务异常 ({i+1}/{total_count}): {task_desc}, 错误: {_get_error_detail(e)}，继续执行后续任务...\n{traceback.format_exc()}")
            
            # 所有子任务执行完毕，统计结果
            success_count = sum(1 for r in task_results if r["status"] == "success")
            failed_count = sum(1 for r in task_results if r["status"] == "failed")
            failed_tasks = [r for r in task_results if r["status"] == "failed"]
            
            print(f"{self._log_prefix} 打单执行完毕，运单ID: {waybill_id}, 总计: {total_count}, 成功: {success_count}, 失败: {failed_count}")
            
            # 更新状态
            db.refresh(waybill)
            
            if failed_count > 0:
                # 只要有一个子任务失败，整体打单状态即为失败
                failed_descriptions = "; ".join(
                    f"{r['description']}({r.get('error', '未知错误')})" for r in failed_tasks
                )
                waybill.document_print_status = "2"  # 失败
                db.commit()
                error_msg = f"打单部分失败（{failed_count}/{total_count}）: {failed_descriptions}"
                print(f"{self._log_prefix} {error_msg}")
                rpa_task_service.complete_task(db, task.id, False, error_message=error_msg)
            else:
                waybill.document_print_status = "3"  # 成功
                db.commit()
                print(f"{self._log_prefix} 所有打印任务全部成功，运单ID: {waybill_id}")
                rpa_task_service.complete_task(db, task.id, True)
                
        except Exception as e:
            db.refresh(waybill)
            waybill.document_print_status = "2"  # 失败
            db.commit()
            raise e
    
    async def _execute_single_print_task(
        self,
        task_type: str,
        job_uuid: str,
        params: dict
    ) -> bool:
        """
        执行单个打印子任务
        
        Args:
            task_type: 任务类型（file_print, shenzhen_air_main_waybill_print, china_southern_air_main_waybill_print, 等）
            job_uuid: RPA jobUuid
            params: 任务参数
        
        Returns:
            是否执行成功
        """
        work_uuid = None
        
        try:
            # 根据任务类型调用对应的RPA接口
            if task_type == "file_print":
                # 文件打印（深航和南航通用）
                rpa_response = await asyncio.wait_for(
                    rpa_service.print_file(
                        absolute_path_to_the_file=params.get("absolute_path_to_the_file", ""),
                        printer_name=params.get("printer_name", ""),
                        job_uuid=job_uuid
                    ),
                    timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                )
            elif task_type == "shenzhen_air_main_waybill_print":
                # 深航货运主单打印
                rpa_response = await asyncio.wait_for(
                    rpa_service.print_shenzhen_air_main_waybill(
                        system_url=params.get("system_url", ""),
                        system_account=params.get("system_account", ""),
                        login_password=params.get("login_password", ""),
                        waybill_number_8=params.get("waybill_number_8", ""),
                        printer_name=params.get("printer_name", ""),
                        job_uuid=job_uuid
                    ),
                    timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                )
            elif task_type == "china_southern_air_main_waybill_print":
                # 南航货运主单打印
                rpa_response = await asyncio.wait_for(
                    rpa_service.print_china_southern_air_main_waybill(
                        system_url=params.get("system_url", ""),
                        system_account=params.get("system_account", ""),
                        login_password=params.get("login_password", ""),
                        waybill_number_8=params.get("waybill_number_8", ""),
                        printer_name=params.get("printer_name", ""),
                        job_uuid=job_uuid
                    ),
                    timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                )
            elif task_type == "china_southern_air_security_print":
                # 南航货运安检申报单打印
                rpa_response = await asyncio.wait_for(
                    rpa_service.print_china_southern_air_security_declaration(
                        system_url=params.get("system_url", ""),
                        system_account=params.get("system_account", ""),
                        login_password=params.get("login_password", ""),
                        waybill_number_8=params.get("waybill_number_8", ""),
                        printer_name=params.get("printer_name", ""),
                        job_uuid=job_uuid
                    ),
                    timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                )
            elif task_type == "china_southern_air_label_print":
                # 南航标签打印
                rpa_response = await asyncio.wait_for(
                    rpa_service.print_china_southern_air_label(
                        address_of_the_application_executable_file_tangyi=params.get("address_of_the_application_executable_file_tangyi", ""),
                        system_account=params.get("system_account", ""),
                        login_password=params.get("login_password", ""),
                        waybill_number_8=params.get("waybill_number_8", ""),
                        printer_name=params.get("printer_name", ""),
                        job_uuid=job_uuid
                    ),
                    timeout=settings.RPA_QUEUE_TASK_TIMEOUT
                )
            else:
                print(f"{self._log_prefix} 未知的打印任务类型: {task_type}")
                return False
            
            # 提取workUuid
            work_uuid = rpa_service.extract_work_uuid_from_create_response(rpa_response)
            if not work_uuid:
                print(f"{self._log_prefix} RPA打印接口未返回workUuid")
                return False
            
            # 轮询RPA状态
            return await self._poll_print_task_status(job_uuid, work_uuid)
            
        except asyncio.TimeoutError:
            print(f"{self._log_prefix} 打印RPA接口调用超时")
            return False
        except Exception as e:
            print(f"{self._log_prefix} 打印任务执行异常: {_get_error_detail(e)}\n{traceback.format_exc()}")
            return False
    
    async def _poll_print_task_status(self, job_uuid: str, work_uuid: str) -> bool:
        """
        轮询打印任务RPA状态
        
        Args:
            job_uuid: RPA jobUuid
            work_uuid: RPA workUuid
        
        Returns:
            是否执行成功
        """
        max_polls = settings.RPA_POLL_MAX_COUNT
        poll_interval = settings.RPA_POLL_INTERVAL
        
        for i in range(max_polls):
            await asyncio.sleep(poll_interval)
            
            try:
                # 复用文件打印状态查询接口
                status_data = await rpa_service.query_file_print_status(job_uuid)
                status_info = rpa_service.extract_status_from_query_response(status_data, work_uuid)
                
                if status_info:
                    rpa_status = status_info.get("status")
                    if rpa_status is not None:
                        # RPA状态: 1=执行中, 3=失败, 5=成功
                        if rpa_status == 5:
                            return True
                        elif rpa_status == 3:
                            print(f"{self._log_prefix} 打印RPA执行失败")
                            return False
                        # 状态为1时继续轮询
            except Exception as e:
                print(f"{self._log_prefix} 轮询打印状态失败: {_get_error_detail(e)}\n{traceback.format_exc()}")
                continue
        
        # 轮询超时
        print(f"{self._log_prefix} 打印RPA状态轮询超时")
        return False

    async def _check_csa_booking_feedback(self, db, booking: Booking, work_uuid: str):
        """
        检查南航订舱反馈信息（在任务失败时调用）
        """
        try:
            # 获取RPA工作详情
            details = await rpa_service.get_rpa_work_details([work_uuid])
            if details.get("code") == 0 and details.get("data"):
                # 获取第一条记录的失败描述
                work_item = details["data"][0]
                fail_desc = work_item.get("failDescription", "")
                
                # 匹配特定的错误模式
                if "异常信息为：【1】" in fail_desc:
                    booking.booking_feedback = "机型识别失败"
                    db.commit()
                    print(f"{self._log_prefix} 识别到南航异常: 机型识别失败 (workUuid: {work_uuid})")
        except Exception as e:
            print(f"{self._log_prefix} 检查南航反馈详情失败: {str(e)}")


# 全局Worker管理器
class RPAWorkerManager:
    """RPA Worker管理器 - 为每台启用的机器人创建独立的Worker"""
    
    def __init__(self):
        self.workers: list[RPAWorker] = []
    
    def start_workers(self):
        """启动所有Worker（为每台启用的机器人创建一个）"""
        if not settings.RPA_QUEUE_ENABLED:
            print("​RPA任务队列已禁用，不启动Worker")
            return
        
        db = SessionLocal()
        try:
            robots = db.query(Robot).filter(Robot.status == 1).all()
            if not robots:
                print("没有启用的机器人，不启动Worker")
                return
            
            print(f"启动 {len(robots)} 个RPA Worker（每台机器人一个）")
            
            for robot in robots:
                worker = RPAWorker(robot_db_id=robot.id, robot_name=robot.name)
                worker.start()
                self.workers.append(worker)
        finally:
            db.close()
    
    def sync_workers(self):
        """
        热同步Worker线程与数据库中的机器人（无需重启服务）
        
        - 新增了启用的机器人 → 自动启动对应Worker
        - 机器人被禁用或删除 → 自动停止对应Worker
        - 机器人状态未变 → 不做任何操作
        """
        if not settings.RPA_QUEUE_ENABLED:
            return
        
        db = SessionLocal()
        try:
            # 查询所有启用的机器人
            enabled_robots = db.query(Robot).filter(Robot.status == 1).all()
            enabled_map = {r.id: r for r in enabled_robots}
            
            # 当前正在运行的 Worker 对应的机器人 ID
            running_ids = {w.robot_db_id for w in self.workers}
            
            # 1. 启动新增机器人的 Worker
            for robot in enabled_robots:
                if robot.id not in running_ids:
                    worker = RPAWorker(robot_db_id=robot.id, robot_name=robot.name)
                    worker.start()
                    self.workers.append(worker)
                    print(f"[WorkerManager] 热启动新Worker: {robot.name} (ID: {robot.id})")
            
            # 2. 停止已禁用/删除的机器人的 Worker
            workers_to_remove = []
            for worker in self.workers:
                if worker.robot_db_id not in enabled_map:
                    worker.stop()
                    workers_to_remove.append(worker)
                    print(f"[WorkerManager] 停止Worker: {worker.robot_name} (ID: {worker.robot_db_id})")
            
            for w in workers_to_remove:
                self.workers.remove(w)
            
            print(f"[WorkerManager] 同步完成，当前活跃Worker数: {len(self.workers)}")
        finally:
            db.close()
    
    def stop_workers(self):
        """停止所有Worker"""
        for worker in self.workers:
            worker.stop()
        self.workers.clear()


# 全局单例
rpa_worker_manager = RPAWorkerManager()

