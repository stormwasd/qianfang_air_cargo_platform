"""
业务参数配置接口
"""
import json
from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.config import BusinessConfig
from app.schemas.config import BusinessConfigCreate
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

