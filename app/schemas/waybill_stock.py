"""
单号库相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import date


class WaybillStockBatchCreate(BaseModel):
    """创建领单批次schema"""
    claim_date: date = Field(..., description="领单日期（格式：YYYY-MM-DD）")
    first_number: str = Field(..., description="首单号（数字后缀部分，如13349851）", min_length=1, max_length=50)
    last_number: str = Field(..., description="尾单号（数字后缀部分，如13353126）", min_length=1, max_length=50)
    claim_quantity: int = Field(..., description="领单数量", ge=1, le=10000)
    airline_name: str = Field(..., description="航司名称（如china_southern_air）", min_length=1, max_length=100)


class WaybillStockItemUpdate(BaseModel):
    """
    编辑单号详情schema（全量覆盖，所有字段均可修改）
    
    前端重新上传单号的完整信息，覆盖原有数据。
    """
    claim_date: Optional[date] = Field(None, description="领单日期（格式：YYYY-MM-DD）")
    number_prefix: Optional[str] = Field(None, description="单号前缀（如784-）", min_length=1, max_length=20)
    number_suffix: Optional[str] = Field(None, description="单号后缀（数字部分）", min_length=1, max_length=50)
    usage_status: Optional[str] = Field(None, description="使用状态（0=未使用，1=已使用，2=异常，3=失效）")

    @field_validator("usage_status")
    @classmethod
    def validate_usage_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("0", "1", "2", "3"):
            raise ValueError("使用状态值无效，有效值为：0=未使用，1=已使用，2=异常，3=失效")
        return v


class WaybillStockBatchQuery(BaseModel):
    """领单批次查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    airline_name: Optional[str] = Field(None, description="航司名称精确筛选（如china_southern_air）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")


class WaybillStockItemQuery(BaseModel):
    """单号详情查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    usage_status: Optional[str] = Field(None, description="使用状态筛选（0=未使用，1=已使用，2=异常，3=失效）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")
