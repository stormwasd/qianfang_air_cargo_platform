"""
天气预报相关的 Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import Optional


class WeatherQuery(BaseModel):
    """天气查询入参"""
    airport_code: str = Field(..., description="机场三字码，如 TAO", min_length=3, max_length=3)
    date: str = Field(..., description="目标日期，格式为 YYYY-MM-DD")


class WeatherResponse(BaseModel):
    """天气预报响应"""
    date: str = Field(..., description="日期")
    week: str = Field(..., description="星期几")
    dayweather: str = Field(..., description="白天天气")
    nightweather: str = Field(..., description="夜间天气")
    daytemp: str = Field(..., description="白天温度")
    nighttemp: str = Field(..., description="夜间温度")
    daywind: str = Field(..., description="白天风向")
    nightwind: str = Field(..., description="夜间风向")
    daypower: str = Field(..., description="白天风力")
    nightpower: str = Field(..., description="夜间风力")
    daytemp_float: str = Field(..., description="白天温度浮点数")
    nighttemp_float: str = Field(..., description="夜间温度浮点数")
