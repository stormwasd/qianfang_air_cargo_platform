"""单号库状态一致性服务。"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.waybill_stock import WaybillStock, WaybillStockBatch, WaybillStockItem
from app.utils.helpers import get_china_now


class WaybillStockConsistencyError(Exception):
    """业务成功后无法确认对应单号库记录时抛出。"""


def reserve_available_stock_item(
    db: Session,
    airline_name: str,
) -> Optional[WaybillStockItem]:
    """预占一张可用单号，由调用方提交事务。

    航司和批次查询不加锁，最终仅锁定 ``waybill_stock_items`` 中被选中的
    单号行。多个 Worker 同时分配时使用 ``SKIP LOCKED`` 跳过正在被其他
    Worker 预占的明细，并继续领取下一张可用单号。

    按批次逐个查询还能避免联表 ``FOR UPDATE`` 锁住所有单号共享的航司或
    批次父记录，并延续优先使用最新批次、同批次按明细 ID 顺序分配的规则。
    """
    stock_id = (
        db.query(WaybillStock.id)
        .filter(WaybillStock.airline_name == airline_name)
        .scalar()
    )
    if stock_id is None:
        return None

    batch_ids = [
        batch_id
        for (batch_id,) in (
            db.query(WaybillStockBatch.id)
            .filter(WaybillStockBatch.stock_id == stock_id)
            .order_by(WaybillStockBatch.id.desc())
            .all()
        )
    ]
    for batch_id in batch_ids:
        stock_item = (
            db.query(WaybillStockItem)
            .filter(
                WaybillStockItem.batch_id == batch_id,
                WaybillStockItem.usage_status == "0",
                WaybillStockItem.is_abnormal == "1",
                WaybillStockItem.is_invalid == "0",
            )
            .order_by(WaybillStockItem.id.asc())
            .with_for_update(skip_locked=True)
            .first()
        )
        if stock_item is None:
            continue
        stock_item.usage_status = "1"
        stock_item.usage_date = get_china_now().date()
        return stock_item

    return None


def confirm_stock_item_used(
    db: Session,
    stock_item_id: int,
    *,
    expected_full_number: Optional[str] = None,
) -> WaybillStockItem:
    """锁定并确认单号为已使用，由调用方与业务成功状态一并提交事务。

    该操作是幂等的。即使单号在预占阶段已经写为已使用，成功收尾时仍会
    再次确认，避免开单/订舱成功状态与单号库状态分属不同事务而产生偏差。
    """
    stock_item = (
        db.query(WaybillStockItem)
        .filter(WaybillStockItem.id == stock_item_id)
        .with_for_update()
        .first()
    )
    if stock_item is None:
        raise WaybillStockConsistencyError(
            f"单号库记录不存在，stock_item_id={stock_item_id}"
        )

    expected_number = str(expected_full_number or "").strip()
    if expected_number and stock_item.full_number != expected_number:
        raise WaybillStockConsistencyError(
            "单号库记录与业务单号不一致："
            f"stock_item_id={stock_item_id}, expected={expected_number}, "
            f"actual={stock_item.full_number}"
        )

    stock_item.usage_status = "1"
    stock_item.usage_date = get_china_now().date()
    return stock_item
