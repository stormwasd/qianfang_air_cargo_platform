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
from app.models.dict_type import DictType
from app.models.dict_option import DictOption
from app.schemas.config import BusinessConfigCreate
from app.schemas.dict_type import (
    DictTypeCreate, DictTypeUpdate, DictTypeQuery, DictTypeResponse
)
from app.schemas.dict_option import (
    DictOptionCreate, DictOptionUpdate, DictOptionQuery, DictOptionResponse
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


# ==================== 字典类型管理接口 ====================

@router.post("/dict-types", summary="创建字典类型")
async def create_dict_type(
    dict_type: DictTypeCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    创建字典类型接口
    
    - **name**: 名称
    - **type**: 唯一类型标识（如：freight_code, goods_code）
    - **status**: 状态（True=开启，False=禁用）
    """
    # 检查该用户下type是否已存在
    existing_type = db.query(DictType).filter(
        and_(
            DictType.user_id == current_user.id,
            DictType.type == dict_type.type
        )
    ).first()
    if existing_type:
        raise BadRequestException(f"类型标识 '{dict_type.type}' 已存在")
    
    # 创建新类型
    new_dict_type = DictType(
        user_id=current_user.id,
        name=dict_type.name,
        type=dict_type.type,
        status=dict_type.status
    )
    db.add(new_dict_type)
    db.commit()
    db.refresh(new_dict_type)
    
    result_data = {
        "id": str(new_dict_type.id),
        "name": new_dict_type.name,
        "type": new_dict_type.type,
        "status": new_dict_type.status,
        "created_at": format_datetime_china(new_dict_type.created_at),
        "updated_at": format_datetime_china(new_dict_type.updated_at)
    }
    
    return success_response(data=result_data, msg="字典类型创建成功")


@router.get("/dict-types", summary="获取字典类型列表")
async def get_dict_types(
    query: DictTypeQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取字典类型列表接口
    
    - **status**: 状态筛选（可选）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    """
    # 构建查询（只查询当前用户的字典类型）
    query_obj = db.query(DictType).filter(DictType.user_id == current_user.id)
    
    # 状态筛选
    if query.status is not None:
        query_obj = query_obj.filter(DictType.status == query.status)
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    dict_types = query_obj.order_by(DictType.created_at.desc()).offset(offset).limit(query.page_size).all()
    
    type_list = []
    for dt in dict_types:
        type_list.append({
            "id": str(dt.id),
            "user_id": str(dt.user_id),
            "name": dt.name,
            "type": dt.type,
            "status": dt.status,
            "created_at": format_datetime_china(dt.created_at),
            "updated_at": format_datetime_china(dt.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": type_list},
        msg="查询成功"
    )


@router.put("/dict-types/{type_id}", summary="更新字典类型")
async def update_dict_type(
    type_id: str,
    dict_type_update: DictTypeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典类型接口
    
    - **type_id**: 字典类型ID（字符串格式）
    - 所有字段都是可选的，只更新传入的字段
    """
    # 查询字典类型（只能更新当前用户的）
    dict_type = db.query(DictType).filter(
        and_(
            DictType.id == int(type_id),
            DictType.user_id == current_user.id
        )
    ).first()
    if not dict_type:
        raise NotFoundException("字典类型不存在或无权限访问")
    
    # 如果更新type字段，检查是否与该用户下的其他类型冲突
    if dict_type_update.type and dict_type_update.type != dict_type.type:
        existing_type = db.query(DictType).filter(
            and_(
                DictType.user_id == current_user.id,
                DictType.type == dict_type_update.type,
                DictType.id != int(type_id)
            )
        ).first()
        if existing_type:
            raise BadRequestException(f"类型标识 '{dict_type_update.type}' 已存在")
    
    # 更新字段
    if dict_type_update.name is not None:
        dict_type.name = dict_type_update.name
    if dict_type_update.type is not None:
        dict_type.type = dict_type_update.type
    if dict_type_update.status is not None:
        dict_type.status = dict_type_update.status
    
    db.commit()
    db.refresh(dict_type)
    
    result_data = {
        "id": str(dict_type.id),
        "user_id": str(dict_type.user_id),
        "name": dict_type.name,
        "type": dict_type.type,
        "status": dict_type.status,
        "created_at": format_datetime_china(dict_type.created_at),
        "updated_at": format_datetime_china(dict_type.updated_at)
    }
    
    return success_response(data=result_data, msg="字典类型更新成功")


# ==================== 字典选项管理接口 ====================

@router.post("/dict-options", summary="创建字典选项")
async def create_dict_option(
    dict_option: DictOptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    创建字典选项接口
    
    - **dict_type**: 父级type（字典类型的唯一标识，如：freight_code）
    - **label**: 显示字段
    - **value**: 存储的值
    - **status**: 状态（True=开启，False=禁用）
    """
    # 查询字典类型（只能使用当前用户的字典类型）
    dict_type = db.query(DictType).filter(
        and_(
            DictType.user_id == current_user.id,
            DictType.type == dict_option.dict_type
        )
    ).first()
    if not dict_type:
        raise NotFoundException(f"字典类型 '{dict_option.dict_type}' 不存在")
    
    # 检查同一类型下是否已存在相同的value
    existing_option = db.query(DictOption).filter(
        and_(
            DictOption.dict_type_id == dict_type.id,
            DictOption.value == dict_option.value
        )
    ).first()
    if existing_option:
        raise BadRequestException(f"该类型下已存在值为 '{dict_option.value}' 的选项")
    
    # 创建新选项
    new_dict_option = DictOption(
        dict_type_id=dict_type.id,
        label=dict_option.label,
        value=dict_option.value,
        status=dict_option.status
    )
    db.add(new_dict_option)
    db.commit()
    db.refresh(new_dict_option)
    
    result_data = {
        "id": str(new_dict_option.id),
        "dict_type_id": str(new_dict_option.dict_type_id),
        "dict_type": dict_type.type,
        "label": new_dict_option.label,
        "value": new_dict_option.value,
        "status": new_dict_option.status,
        "created_at": format_datetime_china(new_dict_option.created_at),
        "updated_at": format_datetime_china(new_dict_option.updated_at)
    }
    
    return success_response(data=result_data, msg="字典选项创建成功")


@router.get("/dict-options", summary="获取字典选项列表")
async def get_dict_options(
    query: DictOptionQuery = Depends(),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取字典选项列表接口
    
    - **dict_type**: 字典类型（唯一标识，如：freight_code）（可选）
    - **status**: 状态筛选（可选）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    """
    # 构建查询（只查询当前用户的字典选项）
    query_obj = db.query(DictOption).join(
        DictType, 
        and_(
            DictOption.dict_type_id == DictType.id,
            DictType.user_id == current_user.id
        )
    )
    
    # 字典类型筛选
    if query.dict_type:
        query_obj = query_obj.filter(DictType.type == query.dict_type)
    
    # 状态筛选
    if query.status is not None:
        query_obj = query_obj.filter(DictOption.status == query.status)
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    dict_options = query_obj.order_by(DictOption.created_at.desc()).offset(offset).limit(query.page_size).all()
    
    option_list = []
    for do in dict_options:
        option_list.append({
            "id": str(do.id),
            "dict_type_id": str(do.dict_type_id),
            "dict_type": do.dict_type.type,
            "label": do.label,
            "value": do.value,
            "status": do.status,
            "created_at": format_datetime_china(do.created_at),
            "updated_at": format_datetime_china(do.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": option_list},
        msg="查询成功"
    )


@router.put("/dict-options/{option_id}", summary="更新字典选项")
async def update_dict_option(
    option_id: str,
    dict_option_update: DictOptionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典选项接口
    
    - **option_id**: 字典选项ID（字符串格式）
    - 所有字段都是可选的，只更新传入的字段
    """
    # 查询字典选项（只能更新当前用户的）
    dict_option = db.query(DictOption).join(
        DictType,
        DictOption.dict_type_id == DictType.id
    ).filter(
        and_(
            DictType.user_id == current_user.id,
            DictOption.id == int(option_id)
        )
    ).first()
    if not dict_option:
        raise NotFoundException("字典选项不存在或无权限访问")
    
    # 如果更新dict_type，需要验证新的类型是否存在（必须是当前用户的）
    new_dict_type_id = dict_option.dict_type_id
    if dict_option_update.dict_type:
        new_dict_type = db.query(DictType).filter(
            and_(
                DictType.user_id == current_user.id,
                DictType.type == dict_option_update.dict_type
            )
        ).first()
        if not new_dict_type:
            raise NotFoundException(f"字典类型 '{dict_option_update.dict_type}' 不存在")
        new_dict_type_id = new_dict_type.id
    
    # 如果更新value或dict_type，检查是否与其他选项冲突
    if dict_option_update.value or dict_option_update.dict_type:
        check_value = dict_option_update.value if dict_option_update.value else dict_option.value
        check_type_id = new_dict_type_id
        
        existing_option = db.query(DictOption).filter(
            and_(
                DictOption.dict_type_id == check_type_id,
                DictOption.value == check_value,
                DictOption.id != int(option_id)
            )
        ).first()
        if existing_option:
            raise BadRequestException(f"该类型下已存在值为 '{check_value}' 的选项")
    
    # 更新字段
    if dict_option_update.dict_type:
        dict_option.dict_type_id = new_dict_type_id
    if dict_option_update.label is not None:
        dict_option.label = dict_option_update.label
    if dict_option_update.value is not None:
        dict_option.value = dict_option_update.value
    if dict_option_update.status is not None:
        dict_option.status = dict_option_update.status
    
    db.commit()
    db.refresh(dict_option)
    
    # 重新加载关联的dict_type
    db.refresh(dict_option.dict_type)
    
    result_data = {
        "id": str(dict_option.id),
        "dict_type_id": str(dict_option.dict_type_id),
        "dict_type": dict_option.dict_type.type,
        "label": dict_option.label,
        "value": dict_option.value,
        "status": dict_option.status,
        "created_at": format_datetime_china(dict_option.created_at),
        "updated_at": format_datetime_china(dict_option.updated_at)
    }
    
    return success_response(data=result_data, msg="字典选项更新成功")

