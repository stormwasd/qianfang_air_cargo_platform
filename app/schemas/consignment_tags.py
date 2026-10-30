"""两台页面勾选项的固定标识，独立于费用金额及计算逻辑。"""
from typing import Literal


CustomerTag = Literal["intl_air", "customs", "ground", "trucking", "dom_air"]
ExpenseTag = Literal[
    "intl_air", "customs", "ground", "trucking", "dom_air",
    "discount_info", "sales_commission",
]
