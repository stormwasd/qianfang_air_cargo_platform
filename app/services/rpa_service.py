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
    
    async def create_shenzhen_air_waybill(
        self,
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
        package: str
    ) -> Dict[str, Any]:
        """
        调用深航新增运单任务RPA接口（仅适用于深圳航空，airline="1"或"深圳航空"）
        
        Args:
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
            package: 包装（如：麻袋）
        
        Returns:
            RPA接口返回的数据，包含workUuid等信息
        """
        url = f"{self.base_url}/openAPI/v2/job/operation"
        
        payload = {
            "jobUuid": settings.RPA_SHENZHEN_AIR_JOB_UUID,
            "operation": 1,
            "inputParam": {
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
                raise BadRequestException(f"RPA接口请求失败: {str(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA接口调用异常: {str(e)}")
    
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
                raise BadRequestException(f"RPA状态查询请求失败: {str(e)}")
            except Exception as e:
                raise BadRequestException(f"RPA状态查询异常: {str(e)}")
    
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
                raise BadRequestException(f"获取运单号请求失败: {str(e)}")
            except Exception as e:
                raise BadRequestException(f"获取运单号异常: {str(e)}")
    
    def format_shenzhen_air_waybill_number(self, waybill_suffix: str) -> str:
        """
        格式化深航运单号（加上前缀 "479-"）（仅适用于深圳航空）
        
        Args:
            waybill_suffix: 运单号后八位
        
        Returns:
            完整运单号（如：479-58841145）
        """
        return f"479-{waybill_suffix}"


# 创建全局RPA服务实例
rpa_service = RPAService()

