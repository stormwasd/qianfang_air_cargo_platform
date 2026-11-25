"""标签按字段存储，客服提交时复制到费用，费用可独立维护。"""

TAG_FIELDS = ("customer_tags", "expense_tags")
PAYABLE_TAGS = ("intl_air", "customs", "ground", "trucking", "dom_air")


def apply_consignment_tags(target, source):
    """只复制已提供的非null数组；[]显式清空，使用新列表避免共享引用。"""
    for field in TAG_FIELDS:
        value = getattr(source, field, None)
        if value is not None:
            setattr(target, field, list(value))


def format_consignment_tags(record):
    return {field: list(getattr(record, field, None) or []) for field in TAG_FIELDS}


def filter_consignment_modules(data, record, *, tag_field):
    """按本台标签裁剪新建的响应字典，不修改持久化数据或汇总金额。

    NULL表示历史未设置，保持旧返回格式；显式[]表示不选任何模块。
    两组标签各自独立，不从另一台或另一标签字段推导选择。
    """
    tags = getattr(record, tag_field, None)
    if tags is None:
        return data

    selected = set(tags)
    payables = data.get("payables")
    if isinstance(payables, dict):
        for group in PAYABLE_TAGS:
            if group not in selected:
                payables.pop(group, None)
    for group in ("discount_info", "sales_commission"):
        if group not in selected:
            data.pop(group, None)
    return data
