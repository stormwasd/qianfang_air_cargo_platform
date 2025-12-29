"""
业务参数配置接口
"""
import json
from typing import List
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
    
    # 生成option_group_id（用于标识这个option）
    option_group_id = generate_id()
    
    # 批量创建选项（同一个option的所有value记录共享option_group_id）
    # 注意：由于是新创建的option，option_group_id是新的，所以不需要检查重复
    new_options = []
    for value in unique_values:
        new_option = DictOption(
            option_group_id=option_group_id,
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
    
    # 返回格式：一个option是一个整体，包含option_id、label、value（列表）、status
    value_list = [option.value for option in new_options]
    
    result_data = {
        "dict_type": dict_type.type,
        "label": dict_option.label,
        "value": value_list,
        "option_id": str(option_group_id),
        "status": dict_option.status
    }
    
    return success_response(data=result_data, msg=f"成功创建 1 个字典选项（包含 {len(value_list)} 个值）")


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
    
    # 获取所有符合条件的选项（不分页，因为需要分组）
    dict_options = query_obj.order_by(DictOption.created_at.desc()).all()
    
    # 按option_group_id分组，每个分组是一个option
    grouped_options = {}
    for do in dict_options:
        # 使用option_group_id作为分组key
        if do.option_group_id not in grouped_options:
            grouped_options[do.option_group_id] = {
                "dict_type": do.dict_type.type,
                "label": do.label,
                "value": [],
                "option_id": str(do.option_group_id),
                "status": do.status
            }
        # 收集value列表（字符串数组）
        grouped_options[do.option_group_id]["value"].append(do.value)
    
    # 转换为列表
    option_list = list(grouped_options.values())
    
    # 获取分组后的总数
    total = len(option_list)
    
    # 分页处理（对分组后的结果进行分页）
    offset = (query.page - 1) * query.page_size
    paginated_items = option_list[offset:offset + query.page_size]
    
    return success_response(
        data={"total": total, "items": paginated_items},
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
    # option_id就是option_group_id，找到该option的所有记录
    option_records = db.query(DictOption).filter(DictOption.option_group_id == int(option_id)).all()
    if not option_records:
        raise NotFoundException("字典选项不存在")
    
    return await _update_dict_option_internal(option_records, dict_option_update, db)


@router.put("/dict-options/by-type-value", summary="更新字典选项（通过dictType和value）")
async def update_dict_option_by_type_value(
    dict_option_update: DictOptionUpdateByIdentifier,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典选项接口（通过dictType和value唯一标识）
    
    - **dict_type**: 父级type（字典类型的唯一标识，如：freight_code）
    - **value**: 存储的值（用于定位要更新的选项，同一类型和label组合下value唯一）
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
    
    # 找到该option的所有记录（通过option_group_id）
    option_records = db.query(DictOption).filter(
        DictOption.option_group_id == dict_option.option_group_id
    ).all()
    
    return await _update_dict_option_internal(option_records, update_data, db)


async def _update_dict_option_internal(
    option_records: List[DictOption],
    dict_option_update: DictOptionUpdate,
    db: Session
):
    """内部更新字典选项的通用逻辑（option是一个整体，通过option_group_id标识）"""
    
    if not option_records:
        raise NotFoundException("字典选项不存在")
    
    # 使用第一个记录作为参考
    first_record = option_records[0]
    option_group_id = first_record.option_group_id
    
    # 如果更新dict_type，需要验证新的类型是否存在（全局共享）
    new_dict_type_id = first_record.dict_type_id
    if dict_option_update.dict_type:
        new_dict_type = db.query(DictType).filter(DictType.type == dict_option_update.dict_type).first()
        if not new_dict_type:
            raise NotFoundException(f"字典类型 '{dict_option_update.dict_type}' 不存在")
        new_dict_type_id = new_dict_type.id
    
    # 需要确定更新后使用的label（如果更新了label，使用新的label；否则使用当前的label）
    new_label = dict_option_update.label if dict_option_update.label is not None else first_record.label
    
    # 如果更新value列表（批量更新）
    if dict_option_update.value is not None:
        # 去重
        unique_values = list(dict.fromkeys(dict_option_update.value))
        
        # 查询该option_group_id下的所有现有记录
        existing_options = db.query(DictOption).filter(
            DictOption.option_group_id == option_group_id
        ).all()
        
        existing_value_set = {opt.value for opt in existing_options}
        new_value_set = set(unique_values)
        
        # 需要删除的记录（在数据库中但不在新列表中）
        to_delete = [opt for opt in existing_options if opt.value not in new_value_set]
        for opt in to_delete:
            db.delete(opt)
        
        # 需要创建的记录（在新列表中但不在数据库中）
        to_create = [v for v in unique_values if v not in existing_value_set]
        for value in to_create:
            new_option = DictOption(
                option_group_id=option_group_id,
                dict_type_id=new_dict_type_id,
                label=new_label,
                value=value,
                status=dict_option_update.status if dict_option_update.status is not None else first_record.status
            )
            db.add(new_option)
        
        # 更新现有记录的状态和dict_type_id、label（如果status有更新）
        if dict_option_update.status is not None or dict_option_update.dict_type or dict_option_update.label:
            for opt in existing_options:
                if opt.value in new_value_set:
                    if dict_option_update.status is not None:
                        opt.status = dict_option_update.status
                    if dict_option_update.dict_type:
                        opt.dict_type_id = new_dict_type_id
                    if dict_option_update.label is not None:
                        opt.label = new_label
    
    # 如果只更新其他字段（不更新value）
    else:
        if dict_option_update.dict_type or dict_option_update.label or dict_option_update.status is not None:
            for opt in option_records:
                if dict_option_update.dict_type:
                    opt.dict_type_id = new_dict_type_id
                if dict_option_update.label is not None:
                    opt.label = new_label
                if dict_option_update.status is not None:
                    opt.status = dict_option_update.status
    
    db.commit()
    
    # 重新加载关联的dict_type
    if dict_option_update.dict_type:
        dict_type = db.query(DictType).filter(DictType.id == new_dict_type_id).first()
    else:
        dict_type = first_record.dict_type
    
    # 返回格式：一个option是一个整体，包含option_id、label、value（列表）、status
    # 查询该option_group_id下的所有记录
    all_options = db.query(DictOption).filter(
        DictOption.option_group_id == option_group_id
    ).order_by(DictOption.id).all()
    
    value_list = [opt.value for opt in all_options]
    
    result_data = {
        "dict_type": dict_type.type,
        "label": new_label,
        "value": value_list,
        "option_id": str(option_group_id),
        "status": all_options[0].status if all_options else (dict_option_update.status if dict_option_update.status is not None else first_record.status)
    }
    
    return success_response(data=result_data, msg="字典选项更新成功")

