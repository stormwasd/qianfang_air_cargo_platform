import httpx
from datetime import datetime
from typing import Optional, Dict

class CtripClient:
    """携程航班接口客户端"""

    @staticmethod
    async def get_flight_times(flight_no: str, flight_date: str, routing: str) -> Optional[Dict[str, str]]:
        """
        获取航班的各维度的起飞时间
        :param flight_no: 航班号 (例如: ZH9947)
        :param flight_date: 航班日期 (例如: 2026-06-12)
        :param routing: 航程 (例如: SZX-HFE)
        :return: 包含 planned_time(预飞时间) 和 ready_time(计飞时间) 的字典, 获取失败返回 None
        """
        if not flight_no or not routing:
            return None
        
        try:
            # 解析 routing 获取起降点
            ports = routing.split("-") if routing else []
            if len(ports) != 2:
                return None
            d_port, a_port = ports[0], ports[1]

            url = "https://m.ctrip.com/restapi/soa2/14566/FlightVarDetailSearchV2"
            
            params = {
                "_fxpcqlniredt": "09031145217077804929",
                "x-traceID": "09031145217077804929-1782312914489-8957979"
            }
            
            headers = {
                "accept": "*/*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json",
                "cookieorigin": "https://flights.ctrip.com",
                "locale": "zh-CN",
                "origin": "https://flights.ctrip.com",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://flights.ctrip.com/",
                "sec-ch-ua": '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
                "x-ctx-locale": "zh-CN",
                "x-ctx-wclient-req": "cb71d51832f5a4da4db52b280a323a8d",
                "Cookie": "GUID=09031145217077804929;DUID=u=D725C5916DD1E07C5BF791B5774572C6&v=0;"
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
                    "ctok": "",
                    "cver": "1.0",
                    "lang": "01",
                    "sid": "8888",
                    "syscode": "09",
                    "auth": "",
                    "xsid": "",
                    "extension": [{"name": "i18n.locale", "value": "zh_CN"}, {"name": "source", "value": "online"}],
                    "Locale": "zh-CN",
                    "Language": "",
                    "Currency": "",
                    "ClientID": "09031145217077804929"
                }
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, params=params, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                
                if not data:
                    return None
                
                # detailItem -> basicItemInfo -> dItemInfo -> dateTimeForRecord -> plannedDateTime / ReadyDateTime / actualDateTime
                detail_item = data.get("detailItem") or {}
                basic_item_info = detail_item.get("basicItemInfo") or {}
                d_item_info = basic_item_info.get("dItemInfo") or {}
                date_time_record = d_item_info.get("dateTimeForRecord") or {}
                
                planned_time = date_time_record.get("plannedDateTime")
                ready_time = date_time_record.get("ReadyDateTime")
                actual_time = date_time_record.get("actualDateTime")
                
                return {"planned_time": planned_time, "ready_time": ready_time, "actual_time": actual_time}
        except Exception as e:
            print(f"Error fetching Ctrip flight time for {flight_no} {flight_date}: {e}")
            return None

ctrip_client = CtripClient()
