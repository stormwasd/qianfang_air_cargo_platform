"""
单据打印服务

用于处理深圳航空和南方航空的单据打印功能：

深圳航空打单流程：
1. 制单后打印流程：遍历 generated_files/{waybill_id}/ 目录下的所有文件，
   对每个文件调用文件打印RPA接口
2. 货运主单打印流程（固定）：调用深航货运主单打印RPA接口

南方航空打单流程：
1. 制单后打印流程（可选）：如果 generated_files/{waybill_id}/ 目录存在，
   遍历目录下的所有文件，对每个文件调用文件打印RPA接口
2. 货运主单打印流程（固定）：调用南航货运主单打印RPA接口
3. 货运安检申报单打印流程（固定）：调用南航货运安检申报单打印RPA接口
4. 标签打印流程（固定）：调用南航标签打印RPA接口
"""
import os
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from app.config import settings


GENERATED_FILES_DIR = "generated_files"


def _get_project_root() -> Path:
    """获取项目根目录"""
    return Path(__file__).parent.parent.parent


def get_waybill_files_dir(waybill_id: int) -> Optional[Path]:
    """
    获取运单的文件存储目录
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        文件存储目录路径，如果目录不存在则返回None
    """
    project_root = _get_project_root()
    waybill_dir = project_root / GENERATED_FILES_DIR / str(waybill_id)
    
    if waybill_dir.exists() and waybill_dir.is_dir():
        return waybill_dir
    return None


def list_waybill_files(waybill_id: int) -> List[Dict[str, str]]:
    """
    列出运单目录下的所有可打印文件（仅 xlsx 和 docx，跳过 pdf）
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        文件信息列表，每个元素包含：
        - filename: 文件名（如：交接单.xlsx）
        - filepath: 文件完整路径
        - doc_type: 文档类型（从文件名中提取，去除扩展名）
    """
    waybill_dir = get_waybill_files_dir(waybill_id)
    if not waybill_dir:
        return []
    
    files = []
    supported_extensions = ['.xlsx', '.docx']
    
    for file_path in waybill_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            filename = file_path.name
            doc_type = file_path.stem
            files.append({
                "filename": filename,
                "filepath": str(file_path),
                "doc_type": doc_type
            })
    
    return files


def get_printer_name_from_config(
    business_config: dict,
    airline: str,
    document_type: str
) -> Optional[str]:
    """
    从业务参数配置中获取指定文档类型对应的打印机类型
    
    注意：printer_config 中的 printer_name 存储的是打印机类型（如 normal_a4_printer / dot_matrix_printer / label_printer），
    而非真实的打印机名称。真实打印机名称在 Worker 消费时通过机器人 extra_config.printer_service 映射。
    
    Args:
        business_config: 业务参数配置
        airline: 航司代码 ("shenzhen_air" 或 "china_southern_air")
        document_type: 文档类型（如：交接单、航司货运主单、航空货物安检申报清单、标签单）
    
    Returns:
        打印机类型（如 normal_a4_printer），如果未找到则返回None
    """
    airline_config = business_config.get(airline, {})
    print_config = airline_config.get("print", {})
    printer_configs = print_config.get("printer_config", [])
    
    for config in printer_configs:
        if config.get("document_type") == document_type:
            return config.get("printer_name")
    
    return None


def build_rpa_file_path(waybill_id: int, filename: str) -> str:
    """
    构建RPA机器人上的文件绝对路径
    
    使用固定的RPA文件根目录 + waybill_id + 文件名
    
    Args:
        waybill_id: 运单ID
        filename: 文件名
    
    Returns:
        RPA机器人上的文件绝对路径
    """
    root_path = settings.RPA_PRINT_FILE_ROOT_PATH
    return f"{root_path}\\{waybill_id}\\{filename}"


def prepare_shenzhen_air_print_tasks(
    waybill_id: int,
    waybill_number: str,
    business_config: dict
) -> Dict[str, Any]:
    """
    准备深航打单任务参数
    
    深航打单包含：
    1. 制单后打印流程：遍历所有生成的文件
    2. 货运主单打印流程（固定）
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        business_config: 业务参数配置
    
    Returns:
        打单任务参数，包含所有需要打印的任务列表
    """
    tasks = []
    
    waybill_number_8 = waybill_number.split("-")[-1] if "-" in waybill_number else waybill_number
    
    files = list_waybill_files(waybill_id)
    for file_info in files:
        filename = file_info["filename"]
        doc_type = file_info["doc_type"]
        
        printer_name = get_printer_name_from_config(
            business_config, "shenzhen_air", doc_type
        )
        
        if printer_name:
            rpa_file_path = build_rpa_file_path(waybill_id, filename)
            
            tasks.append({
                "type": "file_print",
                "job_uuid": settings.RPA_FILE_PRINT_JOB_UUID,
                "description": f"深航-制单文档打印-{doc_type}",
                "params": {
                    "absolute_path_to_the_file": rpa_file_path,
                    "printer_name": printer_name
                }
            })
    
    shenzhen_air_config = business_config.get("shenzhen_air", {})
    booking_config = shenzhen_air_config.get("booking", {})
    login_config = booking_config.get("shenzhen_air_login", {})
    
    system_url = login_config.get("system_url", "")
    system_account = login_config.get("system_account", "")
    login_password = login_config.get("login_password", "")
    
    main_waybill_printer = get_printer_name_from_config(
        business_config, "shenzhen_air", "航司货运主单"
    )
    
    if main_waybill_printer:
        tasks.append({
            "type": "shenzhen_air_main_waybill_print",
            "job_uuid": settings.RPA_SHENZHEN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
            "description": "深航-货运主单打印",
            "params": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": main_waybill_printer
            }
        })
    
    return {
        "airline": "shenzhen_air",
        "waybill_id": waybill_id,
        "waybill_number": waybill_number,
        "tasks": tasks
    }


def prepare_china_southern_air_print_tasks(
    waybill_id: int,
    waybill_number: str,
    business_config: dict
) -> Dict[str, Any]:
    """
    准备南航打单任务参数
    
    南航打单包含：
    1. 制单后打印流程（可选）：如果文件目录存在，遍历所有生成的文件
    2. 货运主单打印流程（固定）
    3. 货运安检申报单打印流程（固定）
    4. 标签打印流程（固定）
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        business_config: 业务参数配置
    
    Returns:
        打单任务参数，包含所有需要打印的任务列表
    """
    tasks = []
    
    waybill_number_8 = waybill_number.split("-")[-1] if "-" in waybill_number else waybill_number
    
    csa_config = business_config.get("china_southern_air", {})
    booking_and_create_config = csa_config.get("booking_and_create", {})
    
    csa_login_config = booking_and_create_config.get("china_southern_air_login", {})
    system_url = csa_login_config.get("system_url", "")
    system_account = csa_login_config.get("system_account", "")
    login_password = csa_login_config.get("login_password", "")
    
    tangyi_login_config = booking_and_create_config.get("tangi_login", {})
    tangyi_app_path = tangyi_login_config.get("address_of_the_application_executable_file_tangyi", "")
    
    waybill_dir = get_waybill_files_dir(waybill_id)
    if waybill_dir:
        files = list_waybill_files(waybill_id)
        for file_info in files:
            filename = file_info["filename"]
            doc_type = file_info["doc_type"]
            
            printer_name = get_printer_name_from_config(
                business_config, "china_southern_air", doc_type
            )
            
            if printer_name:
                rpa_file_path = build_rpa_file_path(waybill_id, filename)
                
                tasks.append({
                    "type": "file_print",
                    "job_uuid": settings.RPA_FILE_PRINT_JOB_UUID,
                    "description": f"南航-制单文档打印-{doc_type}",
                    "params": {
                        "absolute_path_to_the_file": rpa_file_path,
                        "printer_name": printer_name
                    }
                })
    
    main_waybill_printer = get_printer_name_from_config(
        business_config, "china_southern_air", "航司货运主单"
    )
    
    if main_waybill_printer:
        tasks.append({
            "type": "china_southern_air_main_waybill_print",
            "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID,
            "description": "南航-货运主单打印",
            "params": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": main_waybill_printer
            }
        })
    
    security_printer = get_printer_name_from_config(
        business_config, "china_southern_air", "航空货物安检申报清单"
    )
    
    if security_printer:
        tasks.append({
            "type": "china_southern_air_security_print",
            "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_SECURITY_PRINT_JOB_UUID,
            "description": "南航-货运安检申报单打印",
            "params": {
                "system_url": system_url,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": security_printer
            }
        })
    
    label_printer = get_printer_name_from_config(
        business_config, "china_southern_air", "标签单"
    )
    
    if label_printer:
        tasks.append({
            "type": "china_southern_air_label_print",
            "job_uuid": settings.RPA_CHINA_SOUTHERN_AIR_LABEL_PRINT_JOB_UUID,
            "description": "南航-标签打印",
            "params": {
                "address_of_the_application_executable_file_tangyi": tangyi_app_path,
                "system_account": system_account,
                "login_password": login_password,
                "waybill_number_8": waybill_number_8,
                "printer_name": label_printer
            }
        })
    
    return {
        "airline": "china_southern_air",
        "waybill_id": waybill_id,
        "waybill_number": waybill_number,
        "tasks": tasks
    }


def prepare_print_tasks(
    waybill_id: int,
    waybill_number: str,
    airline: str,
    business_config: dict
) -> Dict[str, Any]:
    """
    根据航司类型准备打单任务参数
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        airline: 航司代码 ("1" 或 "shenzhen_air" 为深航, "2" 或 "china_southern_air" 为南航)
        business_config: 业务参数配置
    
    Returns:
        打单任务参数
    """
    if airline in ["1", "深圳航空", "shenzhen_air"]:
        return prepare_shenzhen_air_print_tasks(waybill_id, waybill_number, business_config)
    elif airline in ["2", "南方航空", "china_southern_air"]:
        return prepare_china_southern_air_print_tasks(waybill_id, waybill_number, business_config)
    else:
        raise ValueError(f"不支持的航司类型: {airline}")


def get_print_task_count(print_tasks: Dict[str, Any]) -> int:
    """
    获取打印任务数量
    
    Args:
        print_tasks: 打印任务参数
    
    Returns:
        任务数量
    """
    return len(print_tasks.get("tasks", []))


def has_file_print_tasks(waybill_id: int) -> bool:
    """
    检查是否有制单后的文件需要打印
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        是否有文件需要打印
    """
    files = list_waybill_files(waybill_id)
    return len(files) > 0
