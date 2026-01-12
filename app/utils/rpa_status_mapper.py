"""
RPA状态映射工具
用于将RPA接口返回的状态码映射到系统数据字典的值
"""
from typing import Optional


# RPA状态码到系统数据字典值的映射
# RPA status -> 系统数据字典 value (invoice_status)
RPA_STATUS_TO_DICT_VALUE = {
    1: "1",  # RPA status=1 (开单中) -> 系统字典 value="1" (开单中)
    3: "2",  # RPA status=3 (失败) -> 系统字典 value="2" (失败)
    5: "3",  # RPA status=5 (运行成功) -> 系统字典 value="3" (成功)
}

# RPA状态码到系统执行状态的映射
# RPA status -> 系统执行状态 (ExecutionStatus)
RPA_STATUS_TO_EXECUTION_STATUS = {
    1: "执行中",  # RPA status=1 -> 执行中
    3: "执行失败",  # RPA status=3 -> 执行失败
    5: "执行成功",  # RPA status=5 -> 执行成功
}


def map_rpa_status_to_dict_value(rpa_status: int) -> Optional[str]:
    """
    将RPA状态码映射到系统数据字典的值
    
    Args:
        rpa_status: RPA接口返回的状态码（整数）
    
    Returns:
        系统数据字典的值（字符串），如果状态码不在映射表中则返回None
    """
    return RPA_STATUS_TO_DICT_VALUE.get(rpa_status)


def map_rpa_status_to_execution_status(rpa_status: int) -> Optional[str]:
    """
    将RPA状态码映射到系统执行状态
    
    Args:
        rpa_status: RPA接口返回的状态码（整数）
    
    Returns:
        系统执行状态（字符串），如果状态码不在映射表中则返回None
    """
    return RPA_STATUS_TO_EXECUTION_STATUS.get(rpa_status)


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

