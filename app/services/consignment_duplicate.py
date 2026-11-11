"""客服国际空运主单号近30天查重，与单据保存共享事务。"""
from datetime import timedelta
from hashlib import sha256
from string import ascii_lowercase, ascii_uppercase
from typing import Optional

from sqlalchemy import func
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictException
from app.models.consignment_number_guard import ConsignmentNumberGuard
from app.models.customer_service import ConsignmentInfo
from app.schemas.customer_service import ConsignmentBase
from app.utils.helpers import get_china_now


def submitted_intl_number(payload: ConsignmentBase) -> str:
    """只读取国际空运输入框；空值不触发查重，不回退委托主单号。"""
    intl_air = payload.payables.intl_air if payload.payables is not None else None
    if intl_air is None or intl_air.flight_doc_no is None:
        return ""
    return intl_air.flight_doc_no.strip(" ")


def ensure_customer_intl_number_available(
    db: Session, payload: ConsignmentBase, *, exclude_id: Optional[int] = None,
) -> None:
    """仅检查本次明确提交的非空国际空运主单号，不修改原始输入。

    加锁顺序为号码互斥键、待修改客服行、费用行。调用方须在业务写入/获取
    单据行锁前调用。先结束只读事务，再获取号码行锁，首次一致性读取发生在
    获锁之后，避免认证等先前查询的REPEATABLE READ快照漏掉刚提交的运单。
    """
    # 和数据库TRIM保持一致，仅忽略首尾半角空格；不删除中间字符或连字符。
    number = submitted_intl_number(payload)
    if not number:
        return

    # 此时只能有认证/单据状态预检查等只读查询；不允许丢弃任何待写入数据。
    if db.new or db.dirty or db.deleted:
        raise RuntimeError("主单号查重必须在业务写入前执行")
    db.rollback()
    guard = ConsignmentNumberGuard.__table__
    dialect = db.get_bind().dialect.name
    if dialect == "mysql":
        # 使用同一数据库UPPER规则生成互斥键和比较号码，避免Unicode大小写
        # 规则与Python不同导致相同输入漏检。输入仍为绑定参数。
        key = func.sha2(func.upper(number), 256)
        statement = mysql_insert(guard).values(number_hash=key)
        statement = statement.on_duplicate_key_update(number_hash=key)
    elif dialect == "sqlite":
        # SQLite原生UPPER仅转换ASCII字母，与测试库的比较规则保持一致。
        key = sha256(number.translate(str.maketrans(ascii_lowercase, ascii_uppercase)).encode("utf-8")).hexdigest()
        statement = sqlite_insert(guard).values(number_hash=key)
        statement = statement.on_conflict_do_update(
            index_elements=[guard.c.number_hash], set_={"number_hash": key},
        )
    else:
        raise RuntimeError("国际空运主单号查重仅支持MySQL和SQLite")
    # 同号请求在这条主键写入处等待，锁由同一事务的commit/rollback释放。
    db.execute(statement)

    now = get_china_now().replace(tzinfo=None)
    stored_number = ConsignmentInfo.financial_data["payables"]["intl_air"]["flight_doc_no"].as_string()
    normalized_number = func.upper(func.trim(stored_number))
    if dialect == "mysql":
        # JSON字符串使用二进制排序规则，避免默认不区分重音的比较和互斥键不一致。
        normalized_number = normalized_number.collate("utf8mb4_bin")
    query = db.query(ConsignmentInfo.id).filter(
        ConsignmentInfo.created_at >= now - timedelta(days=30),
        ConsignmentInfo.created_at <= now,
        normalized_number == func.upper(number),
    )
    if exclude_id is not None:
        query = query.filter(ConsignmentInfo.id != exclude_id)
    # 不锁历史运单或日期范围，避免不同号码的新增互相阻塞/产生范围锁死锁。
    # 同号请求由互斥键串行化，并与后续单据及日志写入保持同一事务。
    if query.first() is not None:
        raise ConflictException("该运单已存在")
