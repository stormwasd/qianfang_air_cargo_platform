import httpx
from datetime import datetime
from typing import Optional, Dict

class CtripClient:
    """携程航班接口客户端"""

    @staticmethod
    async def get_planned_departure_time(flight_no: str, flight_date: str, routing: str) -> Optional[str]:
        """
        获取计飞时间
        :param flight_no: 航班号 (例如: ZH9947)
        :param flight_date: 航班日期 (例如: 2026-06-12)
        :param routing: 航程 (例如: SZX-HFE)
        :return: 计飞时间字符串 (例如: 2026-06-12 17:05), 获取失败返回 None
        """
        try:
            # 解析 routing 获取起降点
            ports = routing.split("-") if routing else []
            if len(ports) != 2:
                return None
            d_port, a_port = ports[0], ports[1]

            url = "https://m.ctrip.com/restapi/soa2/14566/FlightVarDetailSearchV2"
            
            headers = {
                "accept": "*/*",
                "content-type": "application/json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
            }
            
            payload = {
                "fltItem": {
                    "aPort": a_port,
                    "dPort": d_port,
                    "fltno": flight_no,
                    "queryDate": flight_date
                },
                "head": {
                    "cid": "09031145217077804929",
                    "cver": "1.0",
                    "syscode": "09"
                }
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                # 尝试解析计飞时间
                # detailItem -> basicItemInfo -> dItemInfo -> dateTimeForRecord -> ReadyDateTime
                detail_item = data.get("detailItem", {})
                basic_item_info = detail_item.get("basicItemInfo", {})
                d_item_info = basic_item_info.get("dItemInfo", {})
                date_time_record = d_item_info.get("dateTimeForRecord", {})
                planned_time = date_time_record.get("ReadyDateTime")
                
                return planned_time
        except Exception as e:
            print(f"Error fetching Ctrip flight time for {flight_no} {flight_date}: {e}")
            return None

ctrip_client = CtripClient()
