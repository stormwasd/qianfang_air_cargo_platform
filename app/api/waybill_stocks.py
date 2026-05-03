"""
单号库管理接口
包含：新增单号（领单）、单号详情列表、单号编辑、领单统计
"""
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.config import settings
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.waybill_stock import WaybillStockBatch, WaybillStockItem
from app.schemas.waybill_stock import (
    WaybillStockBatchCreate,
    WaybillStockItemUpdate,
    WaybillStockItemBatchDelete,
    WaybillStockBatchQuery,
    WaybillStockItemQuery,
)
from app.api.deps import require_permission
from app.utils.helpers import format_datetime_china

logger = logging.getLogger(__name__)

router = APIRouter()


# ======================== 单号生成核心算法 ========================

def generate_next_number(current: int) -> int:
    """
    根据特殊规则生成下一个单号。
    
    规则：
    - 个位数从0-6循环（共7个有效值）
    - 个位数每变一次，十位数递增1
    - 百位及以上正常十进制递进
    
    实现逻辑：
    - 当前个位为6时，下一个号 = 当前号 + 4（个位 6→0 回绕 -6，十位 +1 即 +10，净增 +4）
    - 其他情况，下一个号 = 当前号 + 11（个位 +1，十位 +1）
    """
    units = current % 10
    if units == 6:
        return current + 4
    else:
        return current + 11


def validate_number_units_digit(number: int) -> bool:
    """验证单号个位数是否在有效范围 [0-6] 内"""
    return (number % 10) <= 6


def generate_waybill_numbers(first_number: str, last_number: str, quantity: int) -> List[str]:
    """
    根据首单号、尾单号和数量生成单号列表。
    
    Args:
        first_number: 首单号（数字字符串）
        last_number: 尾单号（数字字符串）
        quantity: 需要生成的单号数量
    
    Returns:
        生成的单号字符串列表
    
    Raises:
        BadRequestException: 参数校验失败时抛出
    """
    try:
        first = int(first_number)
        last = int(last_number)
    except ValueError:
        raise BadRequestException("首单号和尾单号必须是纯数字")
    
    if first > last:
        raise BadRequestException("首单号不能大于尾单号")
    
    if not validate_number_units_digit(first):
        raise BadRequestException(f"首单号个位数必须在0-6之间，当前值为{first % 10}")
    
    if quantity < 1:
        raise BadRequestException("领单数量必须大于0")
    
    # 生成单号序列
    numbers = [str(first)]
    current = first
    
    for _ in range(quantity - 1):
        current = generate_next_number(current)
        if current > last:
            raise BadRequestException(
                f"按照单号生成规则，从{first_number}开始生成{quantity}个单号时，"
                f"第{len(numbers) + 1}个单号{current}已超过尾单号{last_number}，请检查领单数量或尾单号"
            )
        numbers.append(str(current))
    
    return numbers


def calculate_max_capacity(first_number: str, last_number: str) -> int:
    """
    计算两个单号之间按规则（个位数0-6循环，变一次十位递增1）能包含的最大单号数。
    
    Args:
        first_number: 首单号（数字字符串）
        last_number: 尾单号（数字字符串）
        
    Returns:
        最大单号数量
    """
    try:
        first = int(first_number)
        last = int(last_number)
    except ValueError:
        return 0
        
    if first > last:
        return 0
        
    # 计算两个单号之间的有效数字个数
    # 由于只有个位为0-6的数字是有效的，相当于7进制。
    # 我们把每个有效数字映射到一个从0开始连续的整数上：
    # index(num) = (num // 10) * 7 + (num % 10)
    
    def get_index(num):
        return (num // 10) * 7 + (num % 10)
        
    return get_index(last) - get_index(first) + 1


# ======================== 接口实现 ========================

@router.post("", summary="新增单号（领单）")
async def create_waybill_stock_batch(
    payload: WaybillStockBatchCreate,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    新增单号（领单）接口

    根据入参的首单号、尾单号和领单数量，按照特殊编码规则生成单号并批量存储。
    
    单号生成规则：
    - 个位数从0-6循环
    - 个位数每变一次，十位数递增1
    - 百位及以上正常十进制递进
    
    参数说明：
    - **claim_date**: 领单日期（格式：YYYY-MM-DD）
    - **first_number**: 首单号（数字后缀部分）
    - **last_number**: 尾单号（数字后缀部分）
    - **claim_quantity**: 领单数量
    - **airline_name**: 航司名称（如 china_southern_air）
    """
    # 1. 根据航司名称获取单号前缀
    number_prefix = settings.AIRLINE_NUMBER_PREFIX.get(payload.airline_name)
    if not number_prefix:
        raise BadRequestException(
            f"未找到航司'{payload.airline_name}'对应的单号前缀，"
            f"当前支持的航司：{', '.join(settings.AIRLINE_NUMBER_PREFIX.keys())}"
        )
    
    # 2. 生成单号序列
    number_suffixes = generate_waybill_numbers(
        payload.first_number,
        payload.last_number,
        payload.claim_quantity,
    )
    
    # 3. 创建领单批次记录
    batch = WaybillStockBatch(
        claim_date=payload.claim_date,
        first_number=payload.first_number,
        last_number=payload.last_number,
        claim_quantity=payload.claim_quantity,
        airline_name=payload.airline_name,
        number_prefix=number_prefix,
        total_authorized_count=payload.total_authorized_count,
    )
    db.add(batch)
    db.flush()  # 获取 batch.id
    
    # 4. 批量创建单号详情记录
    items = []
    for suffix in number_suffixes:
        item = WaybillStockItem(
            batch_id=batch.id,
            claim_date=payload.claim_date,
            number_prefix=number_prefix,
            number_suffix=suffix,
            full_number=f"{number_prefix}{suffix}",
            usage_status="0",
            is_abnormal="1",
            is_invalid="0",
        )
        items.append(item)
    db.add_all(items)
    
    db.commit()
    db.refresh(batch)
    
    logger.info(
        "新增领单批次成功: batch_id=%s, airline=%s, quantity=%d",
        batch.id, payload.airline_name, payload.claim_quantity,
    )
    
    batch_data = _format_batch_response(batch)
    return success_response(data=batch_data, msg="新增单号成功")


@router.get("/{batch_id}/items", summary="单号详情列表")
async def get_waybill_stock_items(
    batch_id: str,
    query: WaybillStockItemQuery = Depends(),
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    根据领单批次ID查询单号详情列表

    参数说明：
    - **batch_id**: 领单批次ID（字符串格式）
    - **usage_status**: 使用状态筛选（可选，0=未使用，1=已使用，2=异常，3=失效）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大100）
    """
    # 验证批次是否存在
    batch = db.query(WaybillStockBatch).filter(
        WaybillStockBatch.id == int(batch_id)
    ).first()
    if not batch:
        raise NotFoundException("领单批次不存在")
    
    # 构建查询
    query_obj = db.query(WaybillStockItem).filter(
        WaybillStockItem.batch_id == int(batch_id)
    )
    
    if query.claim_date_range:
        dates = [d.strip() for d in query.claim_date_range.split(',') if d.strip()]
        if len(dates) == 2:
            query_obj = query_obj.filter(WaybillStockItem.claim_date >= dates[0], WaybillStockItem.claim_date <= dates[1])
        elif len(dates) == 1:
            query_obj = query_obj.filter(WaybillStockItem.claim_date == dates[0])
            
    if query.usage_date_range:
        dates = [d.strip() for d in query.usage_date_range.split(',') if d.strip()]
        if len(dates) == 2:
            query_obj = query_obj.filter(WaybillStockItem.usage_date >= dates[0], WaybillStockItem.usage_date <= dates[1])
        elif len(dates) == 1:
            query_obj = query_obj.filter(WaybillStockItem.usage_date == dates[0])
    
    # 使用状态筛选
    if query.usage_status is not None:
        if query.usage_status not in ("0", "1"):
            raise BadRequestException("使用状态值无效，有效值为：0=未使用，1=已使用")
        query_obj = query_obj.filter(WaybillStockItem.usage_status == query.usage_status)

    if query.is_abnormal is not None:
        if query.is_abnormal not in ("0", "1"):
            raise BadRequestException("异常状态值无效，有效值为：0=异常，1=正常")
        query_obj = query_obj.filter(WaybillStockItem.is_abnormal == query.is_abnormal)
        
    if query.is_invalid is not None:
        if query.is_invalid not in ("0", "1"):
            raise BadRequestException("失效状态值无效，有效值为：0=未失效，1=已失效")
        query_obj = query_obj.filter(WaybillStockItem.is_invalid == query.is_invalid)
    
    # 总数
    total = query_obj.count()
    
    # 分页（按单号后缀升序排列）
    offset = (query.page - 1) * query.page_size
    items = query_obj.order_by(
        WaybillStockItem.number_suffix.asc()
    ).offset(offset).limit(query.page_size).all()
    
    item_list = [_format_item_response(item) for item in items]
    
    return success_response(
        data={"total": total, "items": item_list},
        msg="查询成功",
    )


@router.get("/items/{item_id}", summary="单号详情")
async def get_waybill_stock_item(
    item_id: str,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    根据ID获取单个单号详情
    """
    try:
        item_id_int = int(item_id)
    except ValueError:
        raise BadRequestException("单号详情ID无效")

    item = db.query(WaybillStockItem).filter(WaybillStockItem.id == item_id_int).first()
    if not item:
        raise NotFoundException("单号详情不存在")

    return success_response(data=_format_item_response(item), msg="查询单号详情成功")


@router.put("/items/{item_id}", summary="单号编辑")
async def update_waybill_stock_item(
    item_id: str,
    payload: WaybillStockItemUpdate,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    编辑单号详情（所有字段均可修改）

    前端重新上传单号的完整信息，覆盖原有数据。传入的字段会更新，未传入的字段保持原值。

    参数说明：
    - **item_id**: 单号详情ID（字符串格式）
    - **claim_date**: 领单日期（可选）
    - **number_prefix**: 单号前缀（可选，如 784-）
    - **number_suffix**: 单号后缀（可选，数字部分）
    - **usage_status**: 使用状态（可选，0=未使用，1=已使用）
    - **is_abnormal**: 异常状态（可选，0=异常，1=正常）
    - **is_invalid**: 失效状态（可选，0=未失效，1=已失效）
    - **invalid_reason**: 失效原因登记（可选）
    - **usage_date**: 用单日期（可选）
    """
    # 查找单号详情
    item = db.query(WaybillStockItem).filter(
        WaybillStockItem.id == int(item_id)
    ).first()
    if not item:
        raise NotFoundException("单号详情不存在")
    
    # 部分更新：仅更新传入的字段
    update_data = payload.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(item, key, value)
    
    # 如果前缀或后缀被修改，自动重新计算完整单号
    if "number_prefix" in update_data or "number_suffix" in update_data:
        item.full_number = f"{item.number_prefix}{item.number_suffix}"
    
    db.commit()
    db.refresh(item)
    
    logger.info(
        "编辑单号详情成功: item_id=%s, full_number=%s",
        item.id, item.full_number,
    )
    
    item_data = _format_item_response(item)
    return success_response(data=item_data, msg="单号编辑成功")


@router.delete("/items", summary="批量删除单号")
async def delete_waybill_stock_items(
    payload: WaybillStockItemBatchDelete,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    批量删除单号详情

    注意：
    - 只能删除未使用、异常或失效的单号。
    - 包含任何已使用的单号都不允许删除。
    - 删除单号后，所属领单批次的领单数量将自动减去删除的数量。
    
    参数说明：
    - **item_ids**: 要删除的单号详情ID列表
    """
    if not payload.item_ids:
        raise BadRequestException("未选择要删除的单号")
        
    try:
        item_ids = [int(i) for i in payload.item_ids]
    except ValueError:
        raise BadRequestException("单号ID必须为有效的数字字符串")

    # 1. 查找所有单号详情
    items = db.query(WaybillStockItem).filter(
        WaybillStockItem.id.in_(item_ids)
    ).all()
    
    if not items:
        return success_response(data=None, msg="无匹配的单号被删除")
    
    # 2. 校验状态：已使用的单号不允许删除
    for item in items:
        if item.usage_status == "1":
            raise BadRequestException(f"单号 {item.full_number} 已使用，不允许删除")
    
    # 记录每个批次需要扣减的数量
    batch_deducts = {}
    deleted_ids = []
    
    # 3. 统计并删除记录
    for item in items:
        batch_id = item.batch_id
        if batch_id not in batch_deducts:
            batch_deducts[batch_id] = 0
        batch_deducts[batch_id] += 1
        deleted_ids.append(item.id)
        
        db.delete(item)
    
    # 4. 同步更新相关领单批次的领单数量
    batches = db.query(WaybillStockBatch).filter(
        WaybillStockBatch.id.in_(list(batch_deducts.keys()))
    ).all()
    
    for batch in batches:
        deduct_amount = batch_deducts.get(batch.id, 0)
        if batch.claim_quantity >= deduct_amount:
            batch.claim_quantity -= deduct_amount
        else:
            batch.claim_quantity = 0
            
    db.commit()
    
    logger.info(
        "批量删除单号详情成功: count=%d, item_ids=%s",
        len(deleted_ids), deleted_ids,
    )
    
    return success_response(data=None, msg=f"成功删除 {len(deleted_ids)} 个单号")


@router.get("", summary="领单统计（领单列表）")
async def get_waybill_stock_batches(
    query: WaybillStockBatchQuery = Depends(),
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    领单统计接口：查询领单批次列表

    参数说明：
    - **airline_name**: 航司名称精确筛选（可选，如 china_southern_air）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大100）
    """
    # 构建查询
    query_obj = db.query(WaybillStockBatch)
    
    # 航司名称筛选
    if query.airline_name:
        query_obj = query_obj.filter(WaybillStockBatch.airline_name == query.airline_name)
    
    # 总数
    total = query_obj.count()
    
    # 分页（按创建时间倒序）
    offset = (query.page - 1) * query.page_size
    batches = query_obj.order_by(
        WaybillStockBatch.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    # 统计单号使用情况
    batch_ids = [b.id for b in batches]
    stats_dict = {}
    if batch_ids:
        stats_query = db.query(
            WaybillStockItem.batch_id,
            func.sum(case((WaybillStockItem.usage_status == '0', 1), else_=0)).label('unused_count'),
            func.sum(case((WaybillStockItem.usage_status == '1', 1), else_=0)).label('used_count'),
            func.sum(case((WaybillStockItem.is_abnormal == '0', 1), else_=0)).label('abnormal_count'),
            func.sum(case((WaybillStockItem.is_invalid == '1', 1), else_=0)).label('invalid_count')
        ).filter(
            WaybillStockItem.batch_id.in_(batch_ids)
        ).group_by(
            WaybillStockItem.batch_id
        ).all()
        
        for stat in stats_query:
            stats_dict[stat.batch_id] = {
                "unused_count": int(stat.unused_count or 0),
                "used_count": int(stat.used_count or 0),
                "abnormal_count": int(stat.abnormal_count or 0),
                "invalid_count": int(stat.invalid_count or 0),
            }
    
    batch_list = []
    for b in batches:
        b_stats = stats_dict.get(b.id, {
            "unused_count": 0, "used_count": 0, "abnormal_count": 0, "invalid_count": 0
        })
        batch_list.append(_format_batch_response(b, b_stats))
    
    return success_response(
        data={"total": total, "items": batch_list},
        msg="查询成功",
    )


# ======================== 响应格式化工具 ========================

def _format_batch_response(batch: WaybillStockBatch, stats: dict = None) -> dict:
    """格式化领单批次响应数据"""
    result = {
        "id": str(batch.id),
        "batch_id": str(batch.id),
        "claim_date": batch.claim_date.isoformat() if batch.claim_date else None,
        "first_number": batch.first_number,
        "last_number": batch.last_number,
        "claim_quantity": batch.claim_quantity,
        "airline_name": batch.airline_name,
        "number_prefix": batch.number_prefix,
        "total_authorized_count": batch.total_authorized_count,
        "created_at": format_datetime_china(batch.created_at),
        "updated_at": format_datetime_china(batch.updated_at),
    }
    if stats:
        result.update(stats)
    else:
        result.update({
            "unused_count": 0,
            "used_count": 0,
            "abnormal_count": 0,
            "invalid_count": 0,
        })
    return result


def _format_item_response(item: WaybillStockItem) -> dict:
    """格式化单号详情响应数据"""
    return {
        "id": str(item.id),
        "batch_id": str(item.batch_id),
        "claim_date": item.claim_date.isoformat() if item.claim_date else None,
        "number_prefix": item.number_prefix,
        "number_suffix": item.number_suffix,
        "full_number": item.full_number,
        "usage_status": item.usage_status,
        "is_abnormal": item.is_abnormal,
        "is_invalid": item.is_invalid,
        "invalid_reason": item.invalid_reason,
        "usage_date": item.usage_date.isoformat() if item.usage_date else None,
        "created_at": format_datetime_china(item.created_at),
        "updated_at": format_datetime_china(item.updated_at),
    }

@router.get("/overview", summary="单号库总览")
async def get_waybill_stock_overview(
    airline_name: Optional[str] = None,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    单号库总览接口
    
    返回包括航司名称、核定单号总数、已领用单号数、可领用单号数、未使用单号数、已使用单号数。
    返回结构为一个数组，支持查询所有航司（如果不传airline_name）或特定航司。
    """
    if airline_name:
        airlines = [airline_name]
    else:
        airlines_res = db.query(WaybillStockBatch.airline_name).distinct().all()
        airlines = [a[0] for a in airlines_res]

    results = []
    for al_name in airlines:
        batches = db.query(WaybillStockBatch).filter(WaybillStockBatch.airline_name == al_name).all()
        
        claimed_count = 0
        total_capacity = 0
        
        # 查找最新的核定单号总数
        latest_authorized_count = None
        latest_batch = db.query(WaybillStockBatch).filter(
            WaybillStockBatch.airline_name == al_name,
            WaybillStockBatch.total_authorized_count.isnot(None)
        ).order_by(WaybillStockBatch.created_at.desc()).first()
        
        if latest_batch:
            latest_authorized_count = latest_batch.total_authorized_count
            
        batch_ids = []
        for b in batches:
            claimed_count += b.claim_quantity
            total_capacity += calculate_max_capacity(b.first_number, b.last_number)
            batch_ids.append(b.id)
            
        claimable_count = total_capacity - claimed_count if total_capacity > claimed_count else 0
        
        unused_count = 0
        used_count = 0
        
        if batch_ids:
            # 统计单号使用情况
            stats = db.query(
                func.sum(case((WaybillStockItem.usage_status == '0', 1), else_=0)).label('unused_count'),
                func.sum(case((WaybillStockItem.usage_status == '1', 1), else_=0)).label('used_count')
            ).filter(
                WaybillStockItem.batch_id.in_(batch_ids)
            ).first()
            
            if stats:
                unused_count = int(stats.unused_count or 0)
                used_count = int(stats.used_count or 0)
                
        results.append({
            "airline_name": al_name,
            "total_authorized_count": latest_authorized_count,
            "claimed_count": claimed_count,
            "claimable_count": claimable_count,
            "unused_count": unused_count,
            "used_count": used_count,
        })
            
    return success_response(data=results, msg="获取单号库总览成功")


@router.get("/airlines/{airline_name}/authorized-count", summary="获取航司核定单号总数")
async def get_airline_authorized_count(
    airline_name: str,
    current_user=Depends(require_permission("bill")),
    db: Session = Depends(get_db),
):
    """
    获取指定航司的最新核定单号总数
    用于在新增单号页面自动带入之前输入的数值。
    """
    latest_batch = db.query(WaybillStockBatch).filter(
        WaybillStockBatch.airline_name == airline_name,
        WaybillStockBatch.total_authorized_count.isnot(None)
    ).order_by(WaybillStockBatch.created_at.desc()).first()
    
    authorized_count = latest_batch.total_authorized_count if latest_batch else None
    
    return success_response(data={"total_authorized_count": authorized_count}, msg="获取成功")
