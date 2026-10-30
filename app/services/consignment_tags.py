"""标签按字段存储，客服提交时复制到费用，费用可独立维护。"""

TAG_FIELDS = ("customer_tags", "expense_tags")


def apply_consignment_tags(target, source):
    """只复制已提供的非null数组；[]显式清空，使用新列表避免共享引用。"""
    for field in TAG_FIELDS:
        value = getattr(source, field, None)
        if value is not None:
            setattr(target, field, list(value))


def format_consignment_tags(record):
    return {field: list(getattr(record, field, None) or []) for field in TAG_FIELDS}
