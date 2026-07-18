"""
天气服务接口
"""
from typing import Any
import httpx
import urllib.parse

from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.response import success_response, ResponseModel
from app.api.deps import get_current_active_user
from app.utils.airport_code_mapper import get_city_name_by_code
from app.schemas.weather import WeatherQuery, WeatherResponse

router = APIRouter()

AMAP_WEATHER_API = "https://restapi.amap.com/v3/weather/weatherInfo"
AMAP_KEY = "9fe669a436c5cab2488337aa471c77c8"

AMAP_WEATHER_CITY_MAPPING = {
    "北京首都": "北京",
    "北京大兴": "北京",
    "上海虹桥": "上海",
    "上海浦东": "上海",
    "成都双流": "成都",
    "成都天府": "成都",
    "锦州湾": "锦州",
    "西双版纳": "西双版纳傣族自治州",
    "宁蒗": "宁蒗彝族自治县",
    "怒江": "怒江傈僳族自治州",
    "迪庆": "迪庆藏族自治州",
    "文山": "文山壮族苗族自治州",
    "长白山": "抚松县",  
    "横店": "东阳市",    
    "那拉提": "新源县",  
    "花土沟": "茫崖市",  
    "果洛": "果洛藏族自治州",
    "建三江": "佳木斯",  
}

@router.get("", summary="获取机场指定日期天气", response_model=ResponseModel[Any])
async def get_weather(
    query: WeatherQuery = Depends(),
    current_user=Depends(get_current_active_user)
):
    """
    根据机场三字码和指定日期获取高德天气预报
    """
    raw_city = get_city_name_by_code(query.airport_code)
    city_name = AMAP_WEATHER_CITY_MAPPING.get(raw_city.strip() if raw_city else "", raw_city)
    
    url = f"{AMAP_WEATHER_API}?key={AMAP_KEY}&city={urllib.parse.quote(city_name)}&extensions=all"
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
    except Exception as e:
        raise BadRequestException(f"请求天气服务失败: {str(e)}")
        
    if data.get("status") != "1" or data.get("infocode") != "10000":
        raise BadRequestException(f"高德天气服务异常: {data.get('info')}")
        
    forecasts = data.get("forecasts", [])
    if not forecasts:
        return success_response(msg="暂无天气预报")
        
    casts = forecasts[0].get("casts", [])
    for cast in casts:
        if cast.get("date") == query.date:
            return success_response(data=cast, msg="查询成功")
            
    return success_response(msg="暂无天气预报")
