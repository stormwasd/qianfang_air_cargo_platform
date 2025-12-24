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
from app.models.business_option import BusinessOption, OptionType
from app.schemas.config import BusinessConfigCreate
from app.schemas.business_option import (
    OptionCreate, OptionResponse
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


@router.post("/options", summary="添加选项")
async def add_option(
    option: OptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    添加选项接口
    
    - **option_type**: 选项类型（运价代码、货物代码、包装、货物名称）
    - **option_value**: 选项值
    
    说明：
    - 如果该用户该类型下已存在相同的选项值，则返回已存在的选项（不重复创建）
    - 每个用户的选项是独立的
    """
    # 验证选项类型
    valid_types = [opt.value for opt in OptionType]
    if option.option_type not in valid_types:
        raise BadRequestException(f"选项类型无效，有效类型为：{', '.join(valid_types)}")
    
    # 检查是否已存在相同的选项（同一用户、同一类型、同一值）
    existing_option = db.query(BusinessOption).filter(
        and_(
            BusinessOption.user_id == current_user.id,
            BusinessOption.option_type == option.option_type,
            BusinessOption.option_value == option.option_value
        )
    ).first()
    
    if existing_option:
        # 如果已存在，直接返回
        option_data = {
            "id": str(existing_option.id),
            "user_id": str(existing_option.user_id),
            "option_type": existing_option.option_type,
            "option_value": existing_option.option_value,
            "is_favorite": existing_option.is_favorite,
            "created_at": format_datetime_china(existing_option.created_at),
            "updated_at": format_datetime_china(existing_option.updated_at)
        }
        return success_response(data=option_data, msg="选项已存在")
    
    # 创建新选项
    new_option = BusinessOption(
        user_id=current_user.id,
        option_type=option.option_type,
        option_value=option.option_value,
        is_favorite=False  # 默认不是常用选项
    )
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    
    option_data = {
        "id": str(new_option.id),
        "user_id": str(new_option.user_id),
        "option_type": new_option.option_type,
        "option_value": new_option.option_value,
        "is_favorite": new_option.is_favorite,
        "created_at": format_datetime_china(new_option.created_at),
        "updated_at": format_datetime_china(new_option.updated_at)
    }
    
    return success_response(data=option_data, msg="选项添加成功")


@router.put("/options/{option_id}/favorite", summary="设置常用选项")
async def set_favorite_option(
    option_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    设置常用选项接口
    
    - **option_id**: 选项ID（字符串格式）
    
    说明：
    - 将指定选项设置为常用选项（is_favorite = True）
    - 设置后返回该选项类型的所有常用选项列表
    """
    # 查询选项
    option = db.query(BusinessOption).filter(
        and_(
            BusinessOption.id == int(option_id),
            BusinessOption.user_id == current_user.id
        )
    ).first()
    
    if not option:
        raise NotFoundException("选项不存在或无权限访问")
    
    # 设置为常用选项
    option.is_favorite = True
    db.commit()
    db.refresh(option)
    
    # 获取该选项类型的所有常用选项
    favorite_options = db.query(BusinessOption).filter(
        and_(
            BusinessOption.user_id == current_user.id,
            BusinessOption.option_type == option.option_type,
            BusinessOption.is_favorite == True
        )
    ).order_by(BusinessOption.updated_at.desc()).all()
    
    # 构建响应数据
    favorite_values = [opt.option_value for opt in favorite_options]
    
    response_data = {
        "option_type": option.option_type,
        "items": favorite_values
    }
    
    return success_response(data=response_data, msg="常用选项设置成功")

