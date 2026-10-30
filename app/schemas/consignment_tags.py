"""两台页面勾选项的固定标识，独立于费用金额及计算逻辑。"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator


CustomerTag = Literal["intl_air", "customs", "ground", "trucking", "dom_air"]
ExpenseTag = Literal[
    "intl_air", "customs", "ground", "trucking", "dom_air",
    "discount_info", "sales_commission",
]


class ConsignmentTags(BaseModel):
    """两台共用标签契约，字段按名称区分选项范围而非限制使用页面。"""
    customer_tags: Optional[List[CustomerTag]] = Field(
        None, max_length=5, description="客服勾选项；两台均支持，省略或null保持原值，[]清空，最多5项",
    )
    expense_tags: Optional[List[ExpenseTag]] = Field(
        None, max_length=7, description="费用勾选项；两台均支持，省略或null保持原值，[]清空，最多7项",
    )

    @field_validator("customer_tags", "expense_tags")
    @classmethod
    def deduplicate_tags(cls, value):
        return list(dict.fromkeys(value)) if value is not None else None
