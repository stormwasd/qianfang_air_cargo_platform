"""
业务参数配置接口
"""
import json
from fastapi import APIRouter, Depends, Path
from app.core.exceptions import NotFoundException, BadRequestException, ConflictException
from app.core.response import success_response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.config import BusinessConfig
from app.models.dict_type import DictType
from app.models.dict_option import DictOption
from app.schemas.config import BusinessConfigCreate
from app.schemas.dict_type import DictTypeCreate, DictTypeUpdate, DictTypeQuery
from app.schemas.dict_option import DictOptionCreate, DictOptionUpdate, DictOptionQuery
from app.api.deps import get_current_active_user
from app.models.user import User
from app.utils.helpers import format_datetime_china

router = APIRouter()


# ==================== 业务参数配置接口 ====================

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
    
    如果尚未配置，返回 code=0，data=null（这是正常情况，不是错误）
    只有管理员可以操作此接口（通过菜单权限控制）
    """
    config = db.query(BusinessConfig).first()
    
    if not config:
        # 没有配置是正常情况，返回 code=0，data=null
        return success_response(data=None, msg="暂无配置信息")
    
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
    dict_type_data: DictTypeCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    创建字典类型接口
    
    - **name**: 名称
    - **type**: 唯一类型标识（如：freight_code, goods_code）
    - **status**: 状态（0=禁用，1=开启）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 检查type是否已存在
    existing_type = db.query(DictType).filter(DictType.type == dict_type_data.type).first()
    if existing_type:
        raise ConflictException(f"类型标识 '{dict_type_data.type}' 已存在")
    
    # 创建新字典类型
    new_dict_type = DictType(
        name=dict_type_data.name,
        type=dict_type_data.type,
        status=dict_type_data.status
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
    - **status**: 状态筛选（可选，0=禁用，1=开启）
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
    
    # 构建响应
    items = []
    for dt in dict_types:
        items.append({
            "id": str(dt.id),
            "name": dt.name,
            "type": dt.type,
            "status": dt.status,
            "created_at": format_datetime_china(dt.created_at),
            "updated_at": format_datetime_china(dt.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": items},
        msg="查询成功"
    )


@router.get("/dict-types/{dict_type_id}", summary="获取字典类型详情")
async def get_dict_type_detail(
    dict_type_id: str = Path(..., description="字典类型ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取字典类型详情接口
    
    - **dict_type_id**: 字典类型ID（字符串格式）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        type_id = int(dict_type_id)
    except ValueError:
        raise BadRequestException(f"dict_type_id 必须是数字格式（当前值: {dict_type_id}）")
    
    dict_type = db.query(DictType).filter(DictType.id == type_id).first()
    if not dict_type:
        raise NotFoundException(f"字典类型不存在（id: {dict_type_id}）")
    
    result_data = {
        "id": str(dict_type.id),
        "name": dict_type.name,
        "type": dict_type.type,
        "status": dict_type.status,
        "created_at": format_datetime_china(dict_type.created_at),
        "updated_at": format_datetime_china(dict_type.updated_at)
    }
    
    return success_response(data=result_data, msg="查询成功")


@router.put("/dict-types/{dict_type_id}", summary="更新字典类型")
async def update_dict_type(
    dict_type_data: DictTypeUpdate,
    dict_type_id: str = Path(..., description="字典类型ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典类型接口
    
    - **dict_type_id**: 字典类型ID（字符串格式）
    - **name**: 名称（可选）
    - **type**: 唯一类型标识（可选）
    - **status**: 状态（可选，0=禁用，1=开启）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        type_id = int(dict_type_id)
    except ValueError:
        raise BadRequestException(f"dict_type_id 必须是数字格式（当前值: {dict_type_id}）")
    
    dict_type = db.query(DictType).filter(DictType.id == type_id).first()
    if not dict_type:
        raise NotFoundException(f"字典类型不存在（id: {dict_type_id}）")
    
    # 如果更新type，检查是否与其他类型冲突
    if dict_type_data.type is not None and dict_type_data.type != dict_type.type:
        existing_type = db.query(DictType).filter(
            DictType.type == dict_type_data.type,
            DictType.id != type_id
        ).first()
        if existing_type:
            raise ConflictException(f"类型标识 '{dict_type_data.type}' 已被其他字典类型使用")
        dict_type.type = dict_type_data.type
    
    # 更新其他字段
    if dict_type_data.name is not None:
        dict_type.name = dict_type_data.name
    if dict_type_data.status is not None:
        dict_type.status = dict_type_data.status
    
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


@router.delete("/dict-types/{dict_type_id}", summary="删除字典类型")
async def delete_dict_type(
    dict_type_id: str = Path(..., description="字典类型ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除字典类型接口
    
    - **dict_type_id**: 字典类型ID（字符串格式）
    
    说明：
    - 删除字典类型会自动删除关联的所有字典选项（CASCADE级联删除）
    - 只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        type_id = int(dict_type_id)
    except ValueError:
        raise BadRequestException(f"dict_type_id 必须是数字格式（当前值: {dict_type_id}）")
    
    dict_type = db.query(DictType).filter(DictType.id == type_id).first()
    if not dict_type:
        raise NotFoundException(f"字典类型不存在（id: {dict_type_id}）")
    
    # 统计关联的选项数量
    options_count = db.query(DictOption).filter(DictOption.dict_type_id == type_id).count()
    
    # 删除字典类型（关联的选项会自动级联删除）
    dict_type_type = dict_type.type
    dict_type_name = dict_type.name
    db.delete(dict_type)
    db.commit()
    
    return success_response(
        data={
            "id": dict_type_id,
            "type": dict_type_type,
            "name": dict_type_name,
            "deleted_options_count": options_count
        },
        msg=f"字典类型删除成功，已删除 {options_count} 个关联的字典选项"
    )


# ==================== 字典选项管理接口 ====================

def _parse_value_json(value_str: str) -> list:
    """解析value字段的JSON字符串为列表"""
    try:
        value_list = json.loads(value_str)
        if isinstance(value_list, list):
            return value_list
        return [value_str]
    except json.JSONDecodeError:
        return [value_str]


@router.post("/dict-options", summary="创建字典选项")
async def create_dict_option(
    dict_option_data: DictOptionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    创建字典选项接口
    
    - **dict_type**: 父级type（字典类型的唯一标识，如：freight_code）
    - **label**: 显示字段
    - **value**: 存储的值（数组格式，如：["L", "M", "X"]）
    - **status**: 状态（0=禁用，1=开启）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    # 查询字典类型
    dict_type = db.query(DictType).filter(DictType.type == dict_option_data.dict_type).first()
    if not dict_type:
        raise NotFoundException(f"字典类型 '{dict_option_data.dict_type}' 不存在")
    
    # 将value列表转为JSON字符串存储
    value_json = json.dumps(dict_option_data.value, ensure_ascii=False)
    
    # 创建新字典选项
    new_option = DictOption(
        dict_type_id=dict_type.id,
        label=dict_option_data.label,
        value=value_json,
        status=dict_option_data.status
    )
    db.add(new_option)
    db.commit()
    db.refresh(new_option)
    
    result_data = {
        "id": str(new_option.id),
        "dict_type_id": str(new_option.dict_type_id),
        "dict_type": dict_type.type,
        "label": new_option.label,
        "value": dict_option_data.value,  # 返回数组格式
        "status": new_option.status,
        "created_at": format_datetime_china(new_option.created_at),
        "updated_at": format_datetime_china(new_option.updated_at)
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
    - **status**: 状态筛选（可选，0=禁用，1=开启）
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
    
    # 构建响应
    items = []
    for do in dict_options:
        # 解析value JSON字符串为列表
        value_list = _parse_value_json(do.value)
        
        items.append({
            "id": str(do.id),
            "dict_type_id": str(do.dict_type_id),
            "dict_type": do.dict_type.type,
            "label": do.label,
            "value": value_list,  # 返回数组格式
            "status": do.status,
            "created_at": format_datetime_china(do.created_at),
            "updated_at": format_datetime_china(do.updated_at)
        })
    
    return success_response(
        data={"total": total, "items": items},
        msg="查询成功"
    )


@router.get("/dict-options/{option_id}", summary="获取字典选项详情")
async def get_dict_option_detail(
    option_id: str = Path(..., description="字典选项ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取字典选项详情接口
    
    - **option_id**: 字典选项ID（字符串格式）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        opt_id = int(option_id)
    except ValueError:
        raise BadRequestException(f"option_id 必须是数字格式（当前值: {option_id}）")
    
    dict_option = db.query(DictOption).filter(DictOption.id == opt_id).first()
    if not dict_option:
        raise NotFoundException(f"字典选项不存在（id: {option_id}）")
    
    # 解析value JSON字符串为列表
    value_list = _parse_value_json(dict_option.value)
    
    result_data = {
        "id": str(dict_option.id),
        "dict_type_id": str(dict_option.dict_type_id),
        "dict_type": dict_option.dict_type.type,
        "label": dict_option.label,
        "value": value_list,  # 返回数组格式
        "status": dict_option.status,
        "created_at": format_datetime_china(dict_option.created_at),
        "updated_at": format_datetime_china(dict_option.updated_at)
    }
    
    return success_response(data=result_data, msg="查询成功")


@router.put("/dict-options/{option_id}", summary="更新字典选项")
async def update_dict_option(
    dict_option_data: DictOptionUpdate,
    option_id: str = Path(..., description="字典选项ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新字典选项接口（整体替换）
    
    - **option_id**: 字典选项ID（字符串格式）
    - **dict_type**: 父级type（可选，字典类型的唯一标识）
    - **label**: 显示字段（可选）
    - **value**: 存储的值（可选，数组格式，整体替换）
    - **status**: 状态（可选，0=禁用，1=开启）
    
    说明：
    - 更新时，传入的字段会整体替换原有值
    - value数组会整体替换，不是追加
    - 只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        opt_id = int(option_id)
    except ValueError:
        raise BadRequestException(f"option_id 必须是数字格式（当前值: {option_id}）")
    
    dict_option = db.query(DictOption).filter(DictOption.id == opt_id).first()
    if not dict_option:
        raise NotFoundException(f"字典选项不存在（id: {option_id}）")
    
    # 如果更新dict_type，检查新的类型是否存在
    if dict_option_data.dict_type is not None:
        new_dict_type = db.query(DictType).filter(DictType.type == dict_option_data.dict_type).first()
        if not new_dict_type:
            raise NotFoundException(f"字典类型 '{dict_option_data.dict_type}' 不存在")
        dict_option.dict_type_id = new_dict_type.id
    
    # 更新其他字段
    if dict_option_data.label is not None:
        dict_option.label = dict_option_data.label
    if dict_option_data.value is not None:
        # 将value列表转为JSON字符串存储（整体替换）
        dict_option.value = json.dumps(dict_option_data.value, ensure_ascii=False)
    if dict_option_data.status is not None:
        dict_option.status = dict_option_data.status
    
    db.commit()
    db.refresh(dict_option)
    
    # 解析value JSON字符串为列表
    value_list = _parse_value_json(dict_option.value)
    
    result_data = {
        "id": str(dict_option.id),
        "dict_type_id": str(dict_option.dict_type_id),
        "dict_type": dict_option.dict_type.type,
        "label": dict_option.label,
        "value": value_list,  # 返回数组格式
        "status": dict_option.status,
        "created_at": format_datetime_china(dict_option.created_at),
        "updated_at": format_datetime_china(dict_option.updated_at)
    }
    
    return success_response(data=result_data, msg="字典选项更新成功")


@router.delete("/dict-options/{option_id}", summary="删除字典选项")
async def delete_dict_option(
    option_id: str = Path(..., description="字典选项ID"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除字典选项接口
    
    - **option_id**: 字典选项ID（字符串格式）
    
    说明：只有管理员可以操作此接口（通过菜单权限控制）
    """
    try:
        opt_id = int(option_id)
    except ValueError:
        raise BadRequestException(f"option_id 必须是数字格式（当前值: {option_id}）")
    
    dict_option = db.query(DictOption).filter(DictOption.id == opt_id).first()
    if not dict_option:
        raise NotFoundException(f"字典选项不存在（id: {option_id}）")
    
    # 保存信息用于返回
    option_label = dict_option.label
    option_dict_type = dict_option.dict_type.type
    
    db.delete(dict_option)
    db.commit()
    
    return success_response(
        data={
            "id": option_id,
            "dict_type": option_dict_type,
            "label": option_label
        },
        msg="字典选项删除成功"
    )
