"""
业务参数配置接口
"""
import json
from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException, BadRequestException
from app.core.response import success_response
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import get_db
from app.models.config import BusinessConfig
from app.models.business_option import BusinessOption
from app.schemas.config import BusinessConfigCreate
from app.schemas.business_option import (
    OptionDictSave, OptionDictQuery, OptionDictResponse
)
from app.api.deps import get_current_active_user
from app.models.user import User
from app.utils.helpers import format_datetime_china

router = APIRouter()


@router.put("", summary="保存业务参数配置")
async def save_config(
    config_data: BusinessConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    保存业务参数配置接口（创建或更新）
    
    - **config_data**: 配置数据（JSON格式）
    
    说明：
    - 如果用户尚未配置，则创建新配置
    - 如果用户已有配置，则更新现有配置
    - 这是一个 upsert 操作（update or insert）
    """
    # 查询是否已存在配置
    existing_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    config_json = json.dumps(config_data.config_data, ensure_ascii=False)
    
    if existing_config:
        # 更新现有配置
        existing_config.config_data = config_json
        db.commit()
        db.refresh(existing_config)
        config = existing_config
        msg = "配置更新成功"
    else:
        # 创建新配置
        new_config = BusinessConfig(
            user_id=current_user.id,
            config_data=config_json
        )
        db.add(new_config)
        db.commit()
        db.refresh(new_config)
        config = new_config
        msg = "配置创建成功"
    
    # 返回响应（ID转换为字符串）
    response_data = json.loads(config.config_data)
    result_data = {
        "id": str(config.id),
        "user_id": str(config.user_id),
        "config_data": response_data,
        "created_at": format_datetime_china(config.created_at),
        "updated_at": format_datetime_china(config.updated_at)
    }
    return success_response(data=result_data, msg=msg)


@router.get("", summary="获取当前用户配置")
async def get_current_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取当前用户的业务参数配置
    
    如果用户尚未配置，返回404错误
    """
    config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise NotFoundException("未找到配置信息，请先保存配置")
    
    response_data = json.loads(config.config_data)
    config_data = {
        "id": str(config.id),
        "user_id": str(config.user_id),
        "config_data": response_data,
        "created_at": format_datetime_china(config.created_at),
        "updated_at": format_datetime_china(config.updated_at)
    }
    return success_response(data=config_data, msg="查询成功")


@router.put("/options", summary="保存选项字典")
async def save_options(
    options: OptionDictSave,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    保存选项字典接口（创建或更新）
    
    - **options_data**: 选项字典数据，如：{"freight_code": ["M", "N"], "goods_code": ["A", "B"]}
    
    说明：
    - 如果用户尚未有选项数据，则创建新记录
    - 如果用户已有选项数据，则合并新数据到现有数据（相同key会覆盖，不同key会保留）
    - 自动去重：每个key对应的数组会自动去重
    - 支持部分保存：可以只传递部分key，其他key会保留
    """
    # 验证key的有效性（可选，如果需要限制key的话）
    valid_keys = ["freight_code", "goods_code", "package", "goods_name"]
    for key in options.options_data.keys():
        if key not in valid_keys:
            raise BadRequestException(f"无效的key: {key}，有效key为：{', '.join(valid_keys)}")
    
    # 验证value必须是字符串数组
    for key, value in options.options_data.items():
        if not isinstance(value, list):
            raise BadRequestException(f"key '{key}' 的值必须是数组类型")
        if not all(isinstance(item, str) for item in value):
            raise BadRequestException(f"key '{key}' 的数组元素必须是字符串类型")
    
    # 查询是否已存在选项数据
    existing_option = db.query(BusinessOption).filter(
        BusinessOption.user_id == current_user.id
    ).first()
    
    if existing_option:
        # 合并新数据到现有数据
        existing_data = json.loads(existing_option.options_data)
        # 更新现有数据（相同key覆盖，不同key保留）
        for key, value in options.options_data.items():
            # 去重并保持顺序
            existing_data[key] = list(dict.fromkeys(value))
        merged_data = existing_data
        msg = "选项更新成功"
    else:
        # 创建新数据，自动去重
        merged_data = {}
        for key, value in options.options_data.items():
            merged_data[key] = list(dict.fromkeys(value))
        msg = "选项创建成功"
    
    # 保存到数据库
    options_json = json.dumps(merged_data, ensure_ascii=False)
    
    if existing_option:
        existing_option.options_data = options_json
        db.commit()
        db.refresh(existing_option)
        option = existing_option
    else:
        new_option = BusinessOption(
            user_id=current_user.id,
            options_data=options_json
        )
        db.add(new_option)
        db.commit()
        db.refresh(new_option)
        option = new_option
    
    # 返回响应
    response_data = json.loads(option.options_data)
    result_data = {
        "id": str(option.id),
        "user_id": str(option.user_id),
        "options_data": response_data,
        "created_at": format_datetime_china(option.created_at),
        "updated_at": format_datetime_china(option.updated_at)
    }
    
    return success_response(data=result_data, msg=msg)


@router.get("/options", summary="获取选项字典")
async def get_options(
    query: OptionDictQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取选项字典接口
    
    - **keys**: 要获取的key列表，如：["freight_code", "goods_code"]，不传则返回所有
    
    说明：
    - 如果传递keys参数，只返回指定的key对应的数据
    - 如果不传递keys参数，返回所有key的数据
    - 如果用户尚未有选项数据，返回空字典 {}
    """
    # 查询选项数据
    option = db.query(BusinessOption).filter(
        BusinessOption.user_id == current_user.id
    ).first()
    
    if not option:
        # 如果用户尚未有选项数据，返回空字典
        result_data = {
            "id": None,
            "user_id": str(current_user.id),
            "options_data": {},
            "created_at": None,
            "updated_at": None
        }
        return success_response(data=result_data, msg="查询成功（暂无数据）")
    
    # 解析JSON数据
    all_data = json.loads(option.options_data)
    
    # 如果指定了keys，只返回指定的key
    if query.keys:
        # 验证keys的有效性
        valid_keys = ["freight_code", "goods_code", "package", "goods_name"]
        for key in query.keys:
            if key not in valid_keys:
                raise BadRequestException(f"无效的key: {key}，有效key为：{', '.join(valid_keys)}")
        
        # 只返回指定的key
        filtered_data = {key: all_data.get(key, []) for key in query.keys}
    else:
        # 返回所有数据
        filtered_data = all_data
    
    result_data = {
        "id": str(option.id),
        "user_id": str(option.user_id),
        "options_data": filtered_data,
        "created_at": format_datetime_china(option.created_at),
        "updated_at": format_datetime_china(option.updated_at)
    }
    
    return success_response(data=result_data, msg="查询成功")

