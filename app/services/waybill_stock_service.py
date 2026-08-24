"""单号库状态一致性服务。"""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.waybill_stock import WaybillStockItem
from app.utils.helpers import get_china_now


class WaybillStockConsistencyError(Exception):
    """业务成功后无法确认对应单号库记录时抛出。"""


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
