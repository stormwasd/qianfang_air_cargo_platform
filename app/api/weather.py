"""
天气服务接口
"""
from typing import Any
import httpx
import urllib.parse

from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException, BusinessException
from app.core.response import success_response, ResponseModel
from app.api.deps import get_current_active_user
from app.utils.airport_code_mapper import get_city_name_by_code
from app.schemas.weather import WeatherQuery, WeatherResponse

router = APIRouter()

AMAP_WEATHER_API = "https://restapi.amap.com/v3/weather/weatherInfo"
AMAP_KEY = "9fe669a436c5cab2488337aa471c77c8"

@router.get("", summary="获取机场指定日期天气", response_model=ResponseModel[Any])
async def get_weather(
    query: WeatherQuery = Depends(),
    current_user=Depends(get_current_active_user)
):
    """
    根据机场三字码和指定日期获取高德天气预报
    """
    # 1. 映射三字码到城市名称
    city_name = get_city_name_by_code(query.airport_code)
    if not city_name or city_name == query.airport_code:
        raise NotFoundException(f"未找到机场三字码 {query.airport_code} 对应的城市")
    
    # 2. 调用高德天气接口
    # 重点：直接使用中文城市名称请求高德接口
    url = f"{AMAP_WEATHER_API}?key={AMAP_KEY}&city={urllib.parse.quote(city_name)}&extensions=all"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise BusinessException(f"请求天气服务失败: {str(e)}")
        
    if data.get("status") != "1" or data.get("infocode") != "10000":
        raise BusinessException(f"高德天气服务异常: {data.get('info')}")
        
    # 3. 筛选指定日期
    forecasts = data.get("forecasts", [])
    if not forecasts:
        return success_response(msg="暂无天气预报")
        
    casts = forecasts[0].get("casts", [])
    for cast in casts:
        if cast.get("date") == query.date:
            return success_response(data=cast, msg="查询成功")
            
    # 如果遍历完毕也没找到目标日期的天气
    return success_response(msg="暂无天气预报")
