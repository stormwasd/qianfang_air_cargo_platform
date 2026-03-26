"""
RPA服务模块
统一管理外部RPA接口调用

注意：当前所有方法均为深圳航空（airline="1"或"深圳航空"）专用
后续如需支持其他航司（如南方航空），需要添加对应的接口方法
"""
import httpx
from typing import Dict, Any, Optional
from app.config import settings
from app.core.exceptions import BadRequestException
from app.utils.rpa_status_mapper import map_rpa_status_to_dict_value, get_rpa_status_description


class RPAService:
    """RPA服务类"""
    
    def __init__(self):
        self.base_url = settings.RPA_API_BASE_URL
        self.app_key = settings.RPA_API_APP_KEY
        self.app_secret = settings.RPA_API_APP_SECRET
        self.cookie = settings.RPA_API_COOKIE
    
    def _get_headers(self) -> Dict[str, str]:
        """获取请求头"""
        return {
            "appKey": self.app_key,
            "appSecret": self.app_secret,
            "Content-Type": "application/json",
            "Cookie": self.cookie
        }

    async def create_keep_login_job(
        self,
        job_uuid: str,
        system_account: str,
        login_password: str
    ) -> Dict[str, Any]:
        """
        调用“保持登录”RPA任务（仅使用 system_account/login_password）

        注意：该流程不涉及机器人端队列数据的创建/读取/删除。
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"

        payload_with_input_param = {
            "jobUuid": job_uuid,
            "operation": 1,
            "inputParam": {
                "system_account": system_account,
                "login_password": login_password
            }
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    url, headers=self._get_headers(), json=payload_with_input_param
                )
                response.raise_for_status()
                result = response.json()

                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA保持登录接口调用失败")
                    # 兼容：部分RPA jobUuid在RPA侧为“非引用类型”，
                    # 不允许通过API覆盖/修改任务入参。此时应重试一次：不传inputParam，
                    # 让job使用其预置的参数/默认配置。
                    if "非引用类型" in error_msg or "不允许修改任务入参" in error_msg:
                        payload_without_input_param = {
                            "jobUuid": job_uuid,
                            "operation": 1,
                        }
                        retry_response = await client.post(
                            url,
                            headers=self._get_headers(),
                            json=payload_without_input_param,
                        )
                        retry_response.raise_for_status()
                        retry_result = retry_response.json()
                        if retry_result.get("code") != 0:
                            retry_error_msg = retry_result.get("msg", "RPA保持登录接口重试失败")
                            raise BadRequestException(
                                f"RPA保持登录接口重试失败: {retry_error_msg}"
                            )
                        return retry_result.get("data", {})

                    raise BadRequestException(f"RPA保持登录接口调用失败: {error_msg}")

                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA保持登录接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA保持登录接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA保持登录接口调用异常: {repr(e)}")
    
    async def create_shenzhen_air_waybill(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        origin_station: str,
        destination: str,
        flight_date: str,
        flight_number: str,
        shipper_info: str,
        consignee_info: str,
        quantity: str,
        weight: str,
        freight_code: str,
        cargo_code: str,
        cargo_name: str,
        waybill_type: str,
        package: str
    ) -> Dict[str, Any]:
        """
        调用深航新增运单任务RPA接口（仅适用于深圳航空，airline="1"或"深圳航空"）
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            origin_station: 始发站（如：SZX）
            destination: 目的站（如：TAO）
            flight_date: 航班日期（格式：YYYY-MM-DD，如：2026-01-15）
            flight_number: 航班号（如：ZH9911）
            shipper_info: 发货人信息
            consignee_info: 收货人信息
            quantity: 件数
            weight: 重量
            freight_code: 运价代码（如：GEN）
            cargo_code: 货物代码（如：044）
            cargo_name: 货物名称（如：衣物）
            waybill_type: 运单类型（可选，可能为空）
            package: 包装（如：麻袋）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_SHENZHEN_AIR_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
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
                "waybill_type": waybill_type,
                "package": package
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA接口调用失败")
                    raise BadRequestException(f"RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA接口调用异常: {repr(e)}")
    
    async def query_shenzhen_air_waybill_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询深航新增运单任务状态接口（仅适用于深圳航空，airline="1"或"深圳航空"）
        
        Args:
            job_uuid: 任务jobUuid
            start_time: 开始时间（格式：YYYY-MM-DD HH:mm:ss，如：2021-02-20 22:00:06）
            end_time: 结束时间（格式：YYYY-MM-DD HH:mm:ss，如：2097-02-23 10:55:13）
            size: 查询数量（默认1000000）
        
        Returns:
            RPA接口返回的数据，包含任务执行状态等信息
        """
        url = f"{self.base_url}/openAPI/work-execute/list"
        
        # 如果没有提供时间，使用默认值
        if not start_time:
            start_time = "2021-02-20 22:00:06"
        if not end_time:
            end_time = "2097-02-23 10:55:13"
        
        payload = {
            "jobUuid": job_uuid,
            "startTime": start_time,
            "endTime": end_time,
            "size": size
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA状态查询失败")
                    raise BadRequestException(f"RPA状态查询失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA状态查询HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA状态查询请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA状态查询异常: {repr(e)}")
    
    def extract_work_uuid_from_create_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        从创建运单RPA接口的响应中提取workUuid
        
        Args:
            response_data: RPA接口返回的data部分
        
        Returns:
            workUuid（字符串），如果不存在则返回None
        """
        works = response_data.get("works", [])
        if works and len(works) > 0:
            return works[0].get("workUuid")
        return None
    
    def extract_status_from_query_response(
        self,
        response_data: Dict[str, Any],
        work_uuid: str
    ) -> Optional[Dict[str, Any]]:
        """
        从查询状态RPA接口的响应中提取指定workUuid的状态信息
        
        Args:
            response_data: RPA接口返回的data部分
            work_uuid: 要查询的workUuid
        
        Returns:
            包含status和statusDesc的字典，如果未找到则返回None
        """
        records = response_data.get("records", [])
        for record in records:
            if record.get("workUuid") == work_uuid:
                return {
                    "status": record.get("status"),
                    "statusDesc": record.get("statusDesc"),
                    "startTime": record.get("startTime"),
                    "endTime": record.get("endTime"),
                    "runTime": record.get("runTime")
                }
        return None
    
    async def get_shenzhen_air_waybill_number(self, queue_uuid: str) -> Optional[str]:
        """
        获取深航运单号接口（仅适用于深圳航空，airline="1"或"深圳航空"）
        
        Args:
            queue_uuid: 队列UUID
        
        Returns:
            运单号后八位（字符串），如果获取失败则返回None
        """
        url = f"{self.base_url}/openAPI/queue/consume/queue-UUID/{queue_uuid}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "获取运单号失败")
                    raise BadRequestException(f"获取运单号失败: {error_msg}")
                
                data = result.get("data", {})
                # data.data 是运单号后八位，可能是带引号的字符串，需要去除引号
                waybill_suffix = data.get("data", "")
                if waybill_suffix:
                    # 去除可能的引号
                    waybill_suffix = waybill_suffix.strip('"').strip("'")
                    return waybill_suffix
                return None
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"获取运单号HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"获取运单号请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"获取运单号异常: {repr(e)}")
    
    def format_shenzhen_air_waybill_number(self, waybill_suffix: str) -> str:
        """
        格式化深航运单号（加上前缀 "479-"）（仅适用于深圳航空）
        
        Args:
            waybill_suffix: 运单号后八位
        
        Returns:
            完整运单号（如：479-58841145）
        """
        return f"479-{waybill_suffix}"
    
    def extract_waybill_suffix(self, waybill_number: str) -> str:
        """
        提取运单号后八位（去除深航前缀 "479-"）
        
        Args:
            waybill_number: 完整运单号（如：479-58841145 或 58841145）
        
        Returns:
            运单号后八位（如：58841145）
        """
        if waybill_number.startswith("479-"):
            return waybill_number[4:]  # 去除 "479-" 前缀
        return waybill_number
    
    async def get_china_southern_air_waybill_number(self, queue_uuid: str) -> Optional[str]:
        """
        获取南航运单号接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            queue_uuid: 队列UUID
        
        Returns:
            运单号后八位（字符串），如果获取失败则返回None
        """
        url = f"{self.base_url}/openAPI/queue/consume/queue-UUID/{queue_uuid}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "获取运单号失败")
                    raise BadRequestException(f"获取运单号失败: {error_msg}")
                
                data = result.get("data", {})
                # data.data 是运单号后八位，可能是带引号的字符串，需要去除引号
                waybill_suffix = data.get("data", "")
                if waybill_suffix:
                    # 去除可能的引号
                    waybill_suffix = waybill_suffix.strip('"').strip("'")
                    return waybill_suffix
                return None
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"获取运单号HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"获取运单号请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"获取运单号异常: {repr(e)}")
    
    def format_china_southern_air_waybill_number(self, waybill_suffix: str) -> str:
        """
        格式化南航运单号（加上前缀 "784-"）（仅适用于南方航空）
        
        Args:
            waybill_suffix: 运单号后八位（如：47888190）
        
        Returns:
            完整运单号（如：784-47888190）
        """
        return f"784-{waybill_suffix}"
    
    async def cancel_shenzhen_air_waybill(self, waybill_number_8: str) -> Dict[str, Any]:
        """
        调用深航作废运单任务RPA接口（仅适用于深圳航空，airline="1"或"深圳航空"）
        
        Args:
            waybill_number_8: 运单号后八位（如：58841145）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_SHENZHEN_AIR_VOID_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "waybill_number_8": waybill_number_8
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA作废接口调用失败")
                    raise BadRequestException(f"RPA作废接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA作废接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA作废接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA作废接口调用异常: {repr(e)}")
    
    async def create_china_southern_air_booking(
        self,
        address_of_the_application_executable_file_tangyi: str,
        system_account: str,
        login_password: str,
        system_url: str,
        origin_station: str,
        destination: str,
        flight_date: str,
        cargo_type: str,
        cargo_code: str,
        flight_number: str,
        booking_remark: str,
        cargo_name: str,
        quantity: str,
        weight: str,
        special_cargo_code: str,
        region_province_shipper: str,
        region_city_shipper: str,
        region_city_district: str,
        address_detail: str,
        consignee_phone: str,
        settlement_file_number: str,
        order_contact_name: str,
        order_contact_phone: str,
        agent_checker_name: str,
        agent_consignor_name: str,
        oversized_cargo: str,
        no_dangerous_goods: str,
        shipper: str,
        shipper_phone: str,
        consignee: str
    ) -> Dict[str, Any]:
        """
        调用南航订舱任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            address_of_the_application_executable_file_tangyi: 唐易应用可执行文件地址
            system_account: 系统账号
            login_password: 登录密码
            system_url: 系统URL
            origin_station: 始发站
            destination: 目的站
            flight_date: 航班日期
            cargo_type: 货物类型
            cargo_code: 货物代码
            flight_number: 航班号
            booking_remark: 订舱备注
            cargo_name: 货物名称
            quantity: 件数
            weight: 重量
            special_cargo_code: 特货码
            region_province_shipper: 发货人省
            region_city_shipper: 发货人市
            region_city_district: 发货人区
            address_detail: 详细地址
            consignee_phone: 收货人电话
            settlement_file_number: 结算文件号
            order_contact_name: 订单联系人姓名
            order_contact_phone: 订单联系人电话
            agent_checker_name: 代理检查人姓名
            agent_consignor_name: 代理交运人姓名
            oversized_cargo: 超规货
            no_dangerous_goods: 无危险品
            shipper: 发货人
            shipper_phone: 发货人电话
            consignee: 收货人
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "address_of_the_application_executable_file_tangyi": address_of_the_application_executable_file_tangyi,
                "system_account": system_account,
                "login_password": login_password,
                "system_url": system_url,
                "origin_station": origin_station,
                "destination": destination,
                "flight_date": flight_date,
                "cargo_type": cargo_type,
                "cargo_code": cargo_code,
                "flight_number": flight_number,
                "booking_remark": booking_remark,
                "cargo_name": cargo_name,
                "quantity": quantity,
                "weight": weight,
                "special_cargo_code": special_cargo_code,
                "region_province_shipper": region_province_shipper,
                "region_city_shipper": region_city_shipper,
                "region_city_district": region_city_district,
                "address_detail": address_detail,
                "consignee_phone": consignee_phone,
                "settlement_file_number": settlement_file_number,
                "order_contact_name": order_contact_name,
                "order_contact_phone": order_contact_phone,
                "agent_checker_name": agent_checker_name,
                "agent_consignor_name": agent_consignor_name,
                "oversized_cargo": oversized_cargo,
                "no_dangerous_goods": no_dangerous_goods,
                "shipper": shipper,
                "shipper_phone": shipper_phone,
                "consignee": consignee
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA订舱接口调用失败")
                    raise BadRequestException(f"RPA订舱接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA订舱接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA订舱接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA订舱接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_booking_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询南航订舱任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            job_uuid: RPA jobUuid
            start_time: 开始时间（可选，默认：2021-02-20 22:00:06）
            end_time: 结束时间（可选，默认：2097-02-23 10:55:13）
            size: 查询数量（默认：1000000）
        
        Returns:
            RPA接口返回的数据，包含任务执行状态等信息
        """
        # 复用深航的状态查询接口，因为接口路径和参数格式相同
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    def extract_waybill_suffix_china_southern_air(self, waybill_number: str) -> str:
        """
        提取南航运单号后八位（去除前缀 "784-"）（仅适用于南方航空）
        
        Args:
            waybill_number: 完整运单号（如：784-47888190）
        
        Returns:
            运单号后八位（如：47888190），如果格式不正确则返回空字符串
        """
        if not waybill_number:
            return ""
        
        # 去除可能的空格
        waybill_number = waybill_number.strip()
        
        # 如果包含 "784-" 前缀，去除它
        if waybill_number.startswith("784-"):
            waybill_number = waybill_number[4:]
        
        # 返回后八位（如果长度超过8位，取最后8位）
        if len(waybill_number) >= 8:
            return waybill_number[-8:]
        
        return waybill_number
    
    async def cancel_china_southern_air_booking(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str
    ) -> Dict[str, Any]:
        """
        调用南航退舱任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            system_url: 系统URL
            system_account: 系统账号
            login_password: 登录密码
            waybill_number_8: 运单号后八位（如：47888190）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航退舱RPA接口调用失败")
                    raise BadRequestException(f"南航退舱RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航退舱RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航退舱RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航退舱RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_cancel_status(self, job_uuid: str, start_time: Optional[str] = None, end_time: Optional[str] = None, size: int = 1000000) -> Dict[str, Any]:
        """
        查询南航退舱任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        复用查询深航运单状态的接口，因为RPA状态查询接口是通用的
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def query_china_southern_air_direct_invoice_status(self, job_uuid: str, start_time: Optional[str] = None, end_time: Optional[str] = None, size: int = 1000000) -> Dict[str, Any]:
        """
        查询南航直接开单任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        复用查询深航运单状态的接口，因为RPA状态查询接口是通用的
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def create_china_southern_air_direct_invoice(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str
    ) -> Dict[str, Any]:
        """
        调用南航直接开单任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位（从booking.master_airwaybill_number提取，以"-"分割取最后一部分）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航直接开单RPA接口调用失败")
                    raise BadRequestException(f"南航直接开单RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航直接开单RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航直接开单RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航直接开单RPA接口调用异常: {repr(e)}")
    
    async def cancel_china_southern_air_waybill(self, waybill_number_8: str) -> Dict[str, Any]:
        """
        调用南航作废运单任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        Args:
            waybill_number_8: 运单号后八位（如：47888190）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_VOID_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "waybill_number_8": waybill_number_8
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "RPA作废接口调用失败")
                    raise BadRequestException(f"RPA作废接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"RPA作废接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"RPA作废接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA作废接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_waybill_void_status(self, job_uuid: str, start_time: Optional[str] = None, end_time: Optional[str] = None, size: int = 1000000) -> Dict[str, Any]:
        """
        查询南航作废运单任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        复用查询深航运单状态的接口，因为RPA状态查询接口是通用的
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def create_china_southern_air_waybill(
        self,
        address_of_the_application_executable_file_tangyi: str,
        system_account: str,
        login_password: str,
        system_url: str,
        origin_station: str,
        destination: str,
        flight_date: str,
        cargo_type: str,
        cargo_code: str,
        flight_number: str,
        booking_remark: str,
        cargo_name: str,
        quantity: str,
        weight: str,
        special_cargo_code: str,
        region_province_shipper: str,
        region_city_shipper: str,
        region_city_district: str,
        address_detail: str,
        consignee_phone: str,
        settlement_file_number: str,
        order_contact_name: str,
        order_contact_phone: str,
        agent_checker_name: str,
        agent_consignor_name: str,
        oversized_cargo: str,
        no_dangerous_goods: str,
        shipper: str,
        shipper_phone: str,
        consignee: str
    ) -> Dict[str, Any]:
        """
        调用南航新增运单任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        与南航订舱RPA接口入参一致，整合订舱+开单的流程
        
        Args:
            address_of_the_application_executable_file_tangyi: 唐易应用可执行文件地址
            system_account: 系统账号
            login_password: 登录密码
            system_url: 系统URL
            origin_station: 始发站
            destination: 目的站
            flight_date: 航班日期
            cargo_type: 货物类型
            cargo_code: 货物代码
            flight_number: 航班号
            booking_remark: 订舱备注
            cargo_name: 货物名称
            quantity: 件数
            weight: 重量
            special_cargo_code: 特货码
            region_province_shipper: 发货人省
            region_city_shipper: 发货人市
            region_city_district: 发货人区
            address_detail: 详细地址
            consignee_phone: 收货人电话
            settlement_file_number: 结算文件号
            order_contact_name: 订单联系人姓名
            order_contact_phone: 订单联系人电话
            agent_checker_name: 代理检查人姓名
            agent_consignor_name: 代理交运人姓名
            oversized_cargo: 超规货
            no_dangerous_goods: 无危险品
            shipper: 发货人
            shipper_phone: 发货人电话
            consignee: 收货人
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_WAYBILL_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "address_of_the_application_executable_file_tangyi": address_of_the_application_executable_file_tangyi,
                "system_account": system_account,
                "login_password": login_password,
                "system_url": system_url,
                "origin_station": origin_station,
                "destination": destination,
                "flight_date": flight_date,
                "cargo_type": cargo_type,
                "cargo_code": cargo_code,
                "flight_number": flight_number,
                "booking_remark": booking_remark,
                "cargo_name": cargo_name,
                "quantity": quantity,
                "weight": weight,
                "special_cargo_code": special_cargo_code,
                "region_province_shipper": region_province_shipper,
                "region_city_shipper": region_city_shipper,
                "region_city_district": region_city_district,
                "address_detail": address_detail,
                "consignee_phone": consignee_phone,
                "settlement_file_number": settlement_file_number,
                "order_contact_name": order_contact_name,
                "order_contact_phone": order_contact_phone,
                "agent_checker_name": agent_checker_name,
                "agent_consignor_name": agent_consignor_name,
                "oversized_cargo": oversized_cargo,
                "no_dangerous_goods": no_dangerous_goods,
                "shipper": shipper,
                "shipper_phone": shipper_phone,
                "consignee": consignee
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航新增运单RPA接口调用失败")
                    raise BadRequestException(f"南航新增运单RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航新增运单RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航新增运单RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航新增运单RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_waybill_status(self, job_uuid: str, start_time: Optional[str] = None, end_time: Optional[str] = None, size: int = 1000000) -> Dict[str, Any]:
        """
        查询南航新增运单任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        复用查询深航运单状态的接口，因为RPA状态查询接口是通用的
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def create_china_southern_air_invoice_with_data(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str,
        flight_number: str,
        flight_date: str,
        booking_remark: str,
        cargo_code: str,
        cargo_name: str,
        weight: str,
        quantity: str,
        volume: str,
        special_cargo_code: str,
        oversized_cargo: str,
        shipper: str,
        shipper_phone: str,
        address_detail: str,
        region_province_shipper: str,
        region_city_shipper: str,
        region_city_district: str,
        consignee: str,
        consignee_phone: str,
        order_contact_phone: str,
        order_contact_name: str,
        settlement_file_number: str
    ) -> Dict[str, Any]:
        """
        调用南航修改数据后开单任务RPA接口（仅适用于南方航空，airline="2"或"南方航空"）
        
        此接口用于：用户从订舱回显数据后修改再开单的场景
        与直接开单不同，此接口允许传入修改后的业务数据
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位（从booking.master_airwaybill_number提取）
            flight_number: 航班号
            flight_date: 航班日期
            booking_remark: 订舱备注
            cargo_code: 货物代码
            cargo_name: 货物名称
            weight: 重量
            quantity: 件数
            volume: 体积
            special_cargo_code: 特货码
            oversized_cargo: 超规货（0=否，1=是）
            shipper: 发货人
            shipper_phone: 发货人电话
            address_detail: 详细地址
            region_province_shipper: 发货人省
            region_city_shipper: 发货人市
            region_city_district: 发货人区
            consignee: 收货人
            consignee_phone: 收货人电话
            order_contact_phone: 订单联系人电话
            order_contact_name: 订单联系人姓名
            settlement_file_number: 结算文件号
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "flight_number": flight_number,
                "flight_date": flight_date,
                "booking_remark": booking_remark,
                "cargo_code": cargo_code,
                "cargo_name": cargo_name,
                "weight": weight,
                "quantity": quantity,
                "volume": volume,
                "special_cargo_code": special_cargo_code,
                "oversized_cargo": oversized_cargo,
                "shipper": shipper,
                "shipper_phone": shipper_phone,
                "address_detail": address_detail,
                "region_province_shipper": region_province_shipper,
                "region_city_shipper": region_city_shipper,
                "region_city_district": region_city_district,
                "consignee": consignee,
                "consignee_phone": consignee_phone,
                "order_contact_phone": order_contact_phone,
                "order_contact_name": order_contact_name,
                "settlement_file_number": settlement_file_number
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航修改数据后开单RPA接口调用失败")
                    raise BadRequestException(f"南航修改数据后开单RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航修改数据后开单RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航修改数据后开单RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航修改数据后开单RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_invoice_with_data_status(self, job_uuid: str, start_time: Optional[str] = None, end_time: Optional[str] = None, size: int = 1000000) -> Dict[str, Any]:
        """
        查询南航修改数据后开单任务状态接口（仅适用于南方航空，airline="2"或"南方航空"）
        复用查询深航运单状态的接口，因为RPA状态查询接口是通用的
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def create_queue(self, queue_name: str, max_queue_number: int = 999, is_expire: bool = False) -> Dict[str, Any]:
        """
        创建队列接口（通用，适用于所有航司）
        
        Args:
            queue_name: 队列名称（如：nanhang_air_queue_waybill_number）
            max_queue_number: 最大队列数量（默认999）
            is_expire: 是否过期（默认False）
        
        Returns:
            RPA接口返回的数据，包含queueID和queueUUID
        """
        url = f"{self.base_url}/openAPI/v1/queue/add"
        
        payload = {
            "queueName": queue_name,
            "maxQueueNumber": max_queue_number,
            "isExpire": is_expire
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "创建队列失败")
                    raise BadRequestException(f"创建队列失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"创建队列HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"创建队列请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"创建队列异常: {repr(e)}")
    
    async def delete_queue(self, queue_id: str) -> bool:
        """
        删除队列接口（通用，适用于所有航司）
        
        Args:
            queue_id: 队列ID（从创建队列接口返回的queueID）
        
        Returns:
            删除是否成功（True表示成功）
        """
        url = f"{self.base_url}/openAPI/v1/queue/delete"
        
        payload = {
            "id": int(queue_id) if queue_id.isdigit() else queue_id
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                # 检查RPA接口返回的code
                if result.get("code") != 0:
                    error_msg = result.get("msg", "删除队列失败")
                    raise BadRequestException(f"删除队列失败: {error_msg}")
                
                # 返回data字段的值（通常是True）
                return result.get("data", False)
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"删除队列HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"删除队列请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"删除队列异常: {repr(e)}")
    
    # ========== 打单RPA接口 ==========
    
    async def print_file(
        self,
        absolute_path_to_the_file: str,
        printer_name: str
    ) -> Dict[str, Any]:
        """
        调用文件打印RPA接口（深航和南航通用，用于打印制单后生成的文档文件）
        
        Args:
            absolute_path_to_the_file: 文件的绝对路径（如：D:\\generated_files_of_qianfang_air_cargo_platform\\280700936320585728\\交接单.pdf）
            printer_name: 打印机名称（从业务参数中的print_config获取）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_FILE_PRINT_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "absolute_path_to_the_file": absolute_path_to_the_file,
                "printer_name": printer_name
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") != 0:
                    error_msg = result.get("msg", "文件打印RPA接口调用失败")
                    raise BadRequestException(f"文件打印RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"文件打印RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"文件打印RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"文件打印RPA接口调用异常: {repr(e)}")
    
    async def query_file_print_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询文件打印RPA任务状态（复用通用状态查询接口）
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def print_shenzhen_air_main_waybill(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str,
        printer_name: str
    ) -> Dict[str, Any]:
        """
        调用深航货运主单打印RPA接口
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位
            printer_name: 打印机名称（从业务参数中的print_config获取"航司货运主单"对应的打印机）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_SHENZHEN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") != 0:
                    error_msg = result.get("msg", "深航货运主单打印RPA接口调用失败")
                    raise BadRequestException(f"深航货运主单打印RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"深航货运主单打印RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"深航货运主单打印RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"深航货运主单打印RPA接口调用异常: {repr(e)}")
    
    async def query_shenzhen_air_main_waybill_print_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询深航货运主单打印RPA任务状态（复用通用状态查询接口）
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def print_china_southern_air_main_waybill(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str,
        printer_name: str
    ) -> Dict[str, Any]:
        """
        调用南航货运主单打印RPA接口
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位
            printer_name: 打印机名称（从业务参数中的print_config获取"航司货运主单"对应的打印机）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航货运主单打印RPA接口调用失败")
                    raise BadRequestException(f"南航货运主单打印RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航货运主单打印RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航货运主单打印RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航货运主单打印RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_main_waybill_print_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询南航货运主单打印RPA任务状态（复用通用状态查询接口）
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def print_china_southern_air_security_declaration(
        self,
        system_url: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str,
        printer_name: str
    ) -> Dict[str, Any]:
        """
        调用南航货运安检申报单打印RPA接口
        
        Args:
            system_url: 系统URL（从业务参数配置获取）
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位
            printer_name: 打印机名称（从业务参数中的print_config获取"航空货物安检申报清单"对应的打印机）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_SECURITY_PRINT_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航货运安检申报单打印RPA接口调用失败")
                    raise BadRequestException(f"南航货运安检申报单打印RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航货运安检申报单打印RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航货运安检申报单打印RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航货运安检申报单打印RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_security_print_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询南航货运安检申报单打印RPA任务状态（复用通用状态查询接口）
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)
    
    async def print_china_southern_air_label(
        self,
        address_of_the_application_executable_file_tangyi: str,
        system_account: str,
        login_password: str,
        waybill_number_8: str,
        printer_name: str
    ) -> Dict[str, Any]:
        """
        调用南航标签单打印RPA接口
        
        Args:
            address_of_the_application_executable_file_tangyi: 唐易应用可执行文件地址
            system_account: 系统账号（从业务参数配置获取）
            login_password: 登录密码（从业务参数配置获取）
            waybill_number_8: 运单号后八位
            printer_name: 打印机名称（从业务参数中的print_config获取"标签单"对应的打印机）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_CHINA_SOUTHERN_AIR_LABEL_PRINT_JOB_UUID,
            "operation": 1,
            "inputParam": {
                "address_of_the_application_executable_file_tangyi": address_of_the_application_executable_file_tangyi,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": printer_name
            }
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(url, headers=self._get_headers(), json=payload)
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") != 0:
                    error_msg = result.get("msg", "南航标签单打印RPA接口调用失败")
                    raise BadRequestException(f"南航标签单打印RPA接口调用失败: {error_msg}")
                
                return result.get("data", {})
            except httpx.HTTPStatusError as e:
                raise BadRequestException(f"南航标签单打印RPA接口HTTP错误: {e.response.status_code}")
            except httpx.RequestError as e:
                raise BadRequestException(f"南航标签单打印RPA接口请求失败: {repr(e)}")
            except Exception as e:
                raise BadRequestException(f"南航标签单打印RPA接口调用异常: {repr(e)}")
    
    async def query_china_southern_air_label_print_status(
        self,
        job_uuid: str,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        size: int = 1000000
    ) -> Dict[str, Any]:
        """
        查询南航标签单打印RPA任务状态（复用通用状态查询接口）
        """
        return await self.query_shenzhen_air_waybill_status(job_uuid, start_time, end_time, size)


# 创建全局RPA服务实例
rpa_service = RPAService()

