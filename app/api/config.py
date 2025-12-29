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
    DictOptionCreate, DictOptionUpdate, DictOptionUpdateByIdentifier, DictOptionQuery, DictOptionResponse
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
    - 全局唯一配置，如果尚未配置，则创建新配置
    - 如果已有配置，则更新现有配置
    - 这是一个 upsert 操作（update or insert）
    - 只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询是否已存在配置（全局唯一）
    existing_config = db.query(BusinessConfig).first()
    
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
        "config_data": response_data,
        "created_at": format_datetime_china(config.created_at),
        "updated_at": format_datetime_china(config.updated_at)
    }
    return success_response(data=result_data, msg=msg)


@router.get("", summary="获取业务参数配置")
async def get_current_config(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取业务参数配置（全局唯一配置）
    
    如果尚未配置，返回404错误
    只有管理员可以操作此接口（通过菜单权限控制）
    """
    config = db.query(BusinessConfig).first()
    
    if not config:
        raise NotFoundException("未找到配置信息，请先保存配置")
    
    response_data = json.loads(config.config_data)
    config_data = {
        "id": str(config.id),
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
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 检查type是否已存在（全局唯一）
    existing_type = db.query(DictType).filter(DictType.type == dict_type.type).first()
    if existing_type:
        raise BadRequestException(f"类型标识 '{dict_type.type}' 已存在")
    
    # 创建新类型
    new_dict_type = DictType(
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
    
    - **type**: 类型标识筛选（可选，唯一标识，如：freight_code）
    - **status**: 状态筛选（可选）
    - **page**: 页码（默认1）
    - **page_size**: 每页数量（默认10，最大100）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 构建查询（全局共享）
    query_obj = db.query(DictType)
    
    # 类型标识筛选
    if query.type:
        query_obj = query_obj.filter(DictType.type == query.type)
    
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


@router.put("/dict-types/{type_id}", summary="更新字典类型（通过ID）")
async def update_dict_type_by_id(
    type_id: str,
    dict_type_update: DictTypeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典类型接口（通过ID）
    
    - **type_id**: 字典类型ID（字符串格式）
    - 所有字段都是可选的，只更新传入的字段
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典类型
    dict_type = db.query(DictType).filter(DictType.id == int(type_id)).first()
    if not dict_type:
        raise NotFoundException("字典类型不存在")
    
    return await _update_dict_type_internal(dict_type, dict_type_update, db)


@router.put("/dict-types/by-type/{type}", summary="更新字典类型（通过type唯一标识）")
async def update_dict_type_by_type(
    type: str,
    dict_type_update: DictTypeUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典类型接口（通过type唯一标识）
    
    - **type**: 字典类型的唯一标识（如：freight_code）
    - 所有字段都是可选的，只更新传入的字段
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典类型
    dict_type = db.query(DictType).filter(DictType.type == type).first()
    if not dict_type:
        raise NotFoundException(f"字典类型 '{type}' 不存在")
    
    return await _update_dict_type_internal(dict_type, dict_type_update, db)


async def _update_dict_type_internal(
    dict_type: DictType,
    dict_type_update: DictTypeUpdate,
    db: Session
):
    """内部更新字典类型的通用逻辑"""
    
    # 如果更新type字段，检查是否与其他类型冲突（全局唯一）
    if dict_type_update.type and dict_type_update.type != dict_type.type:
        existing_type = db.query(DictType).filter(
            and_(
                DictType.type == dict_type_update.type,
                DictType.id != dict_type.id
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
    创建字典选项接口（支持批量创建）
    
    - **dict_type**: 父级type（字典类型的唯一标识，如：freight_code）
    - **label**: 显示字段
    - **value**: 存储的值列表（每个值会创建一个选项）
    - **status**: 状态（True=开启，False=禁用）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典类型（全局共享）
    dict_type = db.query(DictType).filter(DictType.type == dict_option.dict_type).first()
    if not dict_type:
        raise NotFoundException(f"字典类型 '{dict_option.dict_type}' 不存在")
    
    # 检查是否有重复的value（去重）
    unique_values = list(dict.fromkeys(dict_option.value))  # 保持顺序并去重
    
    # 检查同一类型下是否已存在相同的value
    existing_values = db.query(DictOption.value).filter(
        and_(
            DictOption.dict_type_id == dict_type.id,
            DictOption.value.in_(unique_values)
        )
    ).all()
    existing_value_set = {v[0] for v in existing_values}
    
    # 找出已存在的value
    duplicate_values = [v for v in unique_values if v in existing_value_set]
    if duplicate_values:
        raise BadRequestException(f"该类型下已存在以下值：{', '.join(duplicate_values)}")
    
    # 批量创建选项
    new_options = []
    for value in unique_values:
        new_option = DictOption(
            dict_type_id=dict_type.id,
            label=dict_option.label,
            value=value,
            status=dict_option.status
        )
        new_options.append(new_option)
        db.add(new_option)
    
    db.commit()
    
    # 刷新所有新创建的选项
    for option in new_options:
        db.refresh(option)
    
    # 返回创建的选项列表
    result_list = []
    for option in new_options:
        result_list.append({
            "id": str(option.id),
            "dict_type_id": str(option.dict_type_id),
            "dict_type": dict_type.type,
            "label": option.label,
            "value": option.value,
            "status": option.status,
            "created_at": format_datetime_china(option.created_at),
            "updated_at": format_datetime_china(option.updated_at)
        })
    
    return success_response(data={"items": result_list, "count": len(result_list)}, msg=f"成功创建 {len(result_list)} 个字典选项")


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
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 构建查询（全局共享）
    query_obj = db.query(DictOption).join(
        DictType, 
        DictOption.dict_type_id == DictType.id
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


@router.put("/dict-options/{option_id}", summary="更新字典选项（通过ID）")
async def update_dict_option_by_id(
    option_id: str,
    dict_option_update: DictOptionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典选项接口（通过ID）
    
    - **option_id**: 字典选项ID（字符串格式）
    - 所有字段都是可选的，只更新传入的字段
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典选项（全局共享）
    dict_option = db.query(DictOption).filter(DictOption.id == int(option_id)).first()
    if not dict_option:
        raise NotFoundException("字典选项不存在")
    
    return await _update_dict_option_internal(dict_option, dict_option_update, db)


@router.put("/dict-options/by-type-value", summary="更新字典选项（通过dictType和value）")
async def update_dict_option_by_type_value(
    dict_option_update: DictOptionUpdateByIdentifier,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典选项接口（通过dictType和value唯一标识）
    
    - **dict_type**: 父级type（字典类型的唯一标识，如：freight_code）
    - **value**: 存储的值（用于定位要更新的选项，同一类型下value唯一）
    - **label**: 显示字段（可选）
    - **status**: 状态（可选）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典类型
    dict_type = db.query(DictType).filter(DictType.type == dict_option_update.dict_type).first()
    if not dict_type:
        raise NotFoundException(f"字典类型 '{dict_option_update.dict_type}' 不存在")
    
    # 查询字典选项（通过dict_type_id和value）
    dict_option = db.query(DictOption).filter(
        and_(
            DictOption.dict_type_id == dict_type.id,
            DictOption.value == dict_option_update.value
        )
    ).first()
    if not dict_option:
        raise NotFoundException(f"字典选项不存在（dict_type: {dict_option_update.dict_type}, value: {dict_option_update.value}）")
    
    # 转换为DictOptionUpdate格式
    # 注意：value不能更新，因为它是定位标识，所以不传递value字段
    update_data = DictOptionUpdate(
        dict_type=None,  # 不更新dict_type，因为它是定位标识的一部分
        label=dict_option_update.label,
        value=None,  # value不能更新，因为它是定位标识
        status=dict_option_update.status
    )
    
    return await _update_dict_option_internal(dict_option, update_data, db)


async def _update_dict_option_internal(
    dict_option: DictOption,
    dict_option_update: DictOptionUpdate,
    db: Session
):
    """内部更新字典选项的通用逻辑"""
    
    # 如果更新dict_type，需要验证新的类型是否存在（全局共享）
    new_dict_type_id = dict_option.dict_type_id
    if dict_option_update.dict_type:
        new_dict_type = db.query(DictType).filter(DictType.type == dict_option_update.dict_type).first()
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
                DictOption.id != dict_option.id
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

