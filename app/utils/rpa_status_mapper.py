"""
RPA状态映射工具
用于将RPA接口返回的状态码映射到系统数据字典的值
"""
from typing import Optional


RPA_STATUS_TO_DICT_VALUE = {
    1: "1",  
    3: "2",  
    5: "3",  
}


def map_rpa_status_to_dict_value(rpa_status: int) -> Optional[str]:
    """
    将RPA状态码映射到系统数据字典的值（用于airline_record_status字段）
    
    Args:
        rpa_status: RPA接口返回的状态码（整数）
    
    Returns:
        系统数据字典的值（字符串），如果状态码不在映射表中则返回None
        返回值："1"（开单中）、"2"（失败）、"3"（成功）
    """
    return RPA_STATUS_TO_DICT_VALUE.get(rpa_status)


def get_rpa_status_description(rpa_status: int) -> str:
    """
    获取RPA状态描述
    
    Args:
        rpa_status: RPA接口返回的状态码（整数）
    
    Returns:
        状态描述（字符串）
    """
    status_descriptions = {
        1: "开单中",
        3: "失败",
        5: "运行成功",
    }
    return status_descriptions.get(rpa_status, f"未知状态({rpa_status})")

