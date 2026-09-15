"""记录真实用户操作；同步写入不另记为一次用户操作。"""
from sqlalchemy.orm import Session

from app.core.exceptions import BadRequestException, NotFoundException
from app.models.consignment_operation_log import ConsignmentOperationLog
from app.models.cost_service import CostConsignment
from app.models.customer_service import ConsignmentInfo
from app.models.user import User
from app.schemas.consignment_operation_log import ConsignmentOperationLogItem, ConsignmentOperationLogPage
from app.utils.helpers import format_datetime_china, get_china_now


OPERATION_NAMES = {
    ("customer_service", "draft"): "货主委托信息暂存",
    ("customer_service", "save"): "货主委托信息保存",
    ("customer_service", "void"): "货主委托信息作废",
    ("customer_service", "delete"): "货主委托信息删除",
    ("cost_service", "draft"): "费用信息暂存",
    ("cost_service", "save"): "费用信息保存",
    ("cost_service", "void"): "费用信息作废",
    ("cost_service", "delete"): "费用信息删除",
}


def append_consignment_operation(
    db: Session, consignment_id: int, operator: User, *, source: str, action: str,
) -> None:
    """仅加入当前事务；由调用方与单据及同步数据一起提交。"""
    db.add(ConsignmentOperationLog(
        consignment_id=consignment_id,
        source=source,
        action=action,
        operation_name=OPERATION_NAMES[(source, action)],
        operator_id=operator.id,
        operator_name=operator.name,
        operated_at=get_china_now(),
    ))


def get_consignment_operations(
    db: Session, consignment_id: str, *, page: int, page_size: int,
) -> ConsignmentOperationLogPage:
    try:
        record_id = int(consignment_id)
    except ValueError:
        raise BadRequestException("consignment_id 必须为合法数字格式")
    if not 0 < record_id < 2 ** 63:
        raise BadRequestException("consignment_id 必须为有效的正整数ID")

    query = db.query(ConsignmentOperationLog).filter(
        ConsignmentOperationLog.consignment_id == record_id,
    )
    total = query.count()
    # 有历史记录的已删除单据仍可追溯；从未存在的 ID 不伪装为空历史。
    if total == 0:
        customer_exists = db.query(ConsignmentInfo.id).filter(ConsignmentInfo.id == record_id).first()
        cost_exists = db.query(CostConsignment.id).filter(CostConsignment.id == record_id).first()
        if not customer_exists and not cost_exists:
            raise NotFoundException(f"单据及操作记录不存在 (ID: {consignment_id})")

    records = query.order_by(
        ConsignmentOperationLog.operated_at.desc(), ConsignmentOperationLog.id.desc(),
    ).offset((page - 1) * page_size).limit(page_size).all()
    return ConsignmentOperationLogPage(
        consignment_id=str(record_id), total=total, page=page, pageSize=page_size,
        items=[ConsignmentOperationLogItem(
            id=str(record.id), consignment_id=str(record.consignment_id),
            source=record.source, action=record.action, operation_name=record.operation_name,
            operator_id=str(record.operator_id), operator_name=record.operator_name,
            operated_at=format_datetime_china(record.operated_at),
        ) for record in records],
    )
