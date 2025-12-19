"""
业务参数配置接口
"""
import json
from fastapi import APIRouter, Depends
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.response import success_response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.config import BusinessConfig
from app.schemas.config import BusinessConfigCreate
from app.api.deps import get_current_active_user
from app.models.user import User

router = APIRouter()


@router.post("/initialize", summary="初始化配置")
async def initialize_config(
    config_data: BusinessConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    初始化业务参数配置接口
    
    - **config_data**: 配置数据（JSON格式）
    
    注意：每个用户只能初始化一次配置
    """
    # 检查是否已经初始化
    existing_config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if existing_config:
        raise BadRequestException("该用户已经初始化过配置，如需修改请使用更新接口")
    
    # 创建配置
    config_json = json.dumps(config_data.config_data, ensure_ascii=False)
    business_config = BusinessConfig(
        user_id=current_user.id,
        config_data=config_json
    )
    db.add(business_config)
    db.commit()
    db.refresh(business_config)
    
    # 返回响应
    response_data = json.loads(business_config.config_data)
    config_data = {
        "id": business_config.id,
        "user_id": business_config.user_id,
        "config_data": response_data,
        "created_at": business_config.created_at.isoformat(),
        "updated_at": business_config.updated_at.isoformat()
    }
    return success_response(data=config_data, msg="配置初始化成功")


@router.get("/current", summary="获取当前用户配置")
async def get_current_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取当前用户的业务参数配置"""
    config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise NotFoundException("未找到配置信息，请先初始化配置")
    
    response_data = json.loads(config.config_data)
    config_data = {
        "id": config.id,
        "user_id": config.user_id,
        "config_data": response_data,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat()
    }
    return success_response(data=config_data, msg="查询成功")


@router.put("/current", summary="更新当前用户配置")
async def update_current_config(
    config_data: BusinessConfigCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新当前用户的业务参数配置"""
    config = db.query(BusinessConfig).filter(
        BusinessConfig.user_id == current_user.id
    ).first()
    
    if not config:
        raise NotFoundException("未找到配置信息，请先初始化配置")
    
    # 更新配置
    config.config_data = json.dumps(config_data.config_data, ensure_ascii=False)
    db.commit()
    db.refresh(config)
    
    response_data = json.loads(config.config_data)
    config_data = {
        "id": config.id,
        "user_id": config.user_id,
        "config_data": response_data,
        "created_at": config.created_at.isoformat(),
        "updated_at": config.updated_at.isoformat()
    }
    return success_response(data=config_data, msg="查询成功")

