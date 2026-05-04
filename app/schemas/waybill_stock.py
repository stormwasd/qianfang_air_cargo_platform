"""
单号库相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import date


class WaybillStockCreate(BaseModel):
    """创建单号库schema"""
    airline_name: str = Field(..., description="航司名称（如china_southern_air）", min_length=1, max_length=100)
    total_authorized_count: Optional[int] = Field(None, description="核定单号总数", ge=0)


class WaybillStockBatchCreate(BaseModel):
    """创建领单批次schema"""
    claim_date: date = Field(..., description="领单日期（格式：YYYY-MM-DD）")
    first_number: str = Field(..., description="首单号（数字后缀部分，如13349851）", min_length=1, max_length=50)
    last_number: str = Field(..., description="尾单号（数字后缀部分，如13353126）", min_length=1, max_length=50)
    claim_quantity: int = Field(..., description="领单数量", ge=1, le=10000)
    stock_id: str = Field(..., description="关联单号库ID（字符串格式）")


class WaybillStockPreview(BaseModel):
    """单号预览请求schema"""
    first_number: str = Field(..., description="首单号（数字后缀部分）", min_length=1, max_length=50)
    last_number: str = Field(..., description="尾单号（数字后缀部分）", min_length=1, max_length=50)
    stock_id: str = Field(..., description="关联单号库ID")


class WaybillStockItemUpdate(BaseModel):
    """
    编辑单号详情schema（全量覆盖，所有字段均可修改）
    
    前端重新上传单号的完整信息，覆盖原有数据。
    """
    claim_date: Optional[date] = Field(None, description="领单日期（格式：YYYY-MM-DD）")
    number_prefix: Optional[str] = Field(None, description="单号前缀（如784-）", min_length=1, max_length=20)
    number_suffix: Optional[str] = Field(None, description="单号后缀（数字部分）", min_length=1, max_length=50)
    usage_status: Optional[str] = Field(None, description="使用状态（0=未使用，1=已使用）")
    is_abnormal: Optional[str] = Field(None, description="异常状态（0=异常，1=正常）")
    is_invalid: Optional[str] = Field(None, description="失效状态（0=未失效，1=已失效）")
    invalid_reason: Optional[str] = Field(None, description="失效原因登记", max_length=255)
    usage_date: Optional[date] = Field(None, description="用单日期")

    @field_validator("usage_status")
    @classmethod
    def validate_usage_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("0", "1"):
            raise ValueError("使用状态值无效，有效值为：0=未使用，1=已使用")
        return v

    @field_validator("is_abnormal")
    @classmethod
    def validate_is_abnormal(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("0", "1"):
            raise ValueError("异常状态值无效，有效值为：0=异常，1=正常")
        return v

    @field_validator("is_invalid")
    @classmethod
    def validate_is_invalid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("0", "1"):
            raise ValueError("失效状态值无效，有效值为：0=未失效，1=已失效")
        return v


class WaybillStockItemBatchDelete(BaseModel):
    """批量删除单号详情schema"""
    item_ids: list[str] = Field(default_factory=list, description="要删除的单号详情ID列表")


class WaybillStockBatchQuery(BaseModel):
    """领单批次查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    stock_id: Optional[str] = Field(None, description="单号库ID精确筛选")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")


class WaybillStockItemQuery(BaseModel):
    """单号详情查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    batch_id: Optional[str] = Field(None, description="领单批次ID精确筛选")
    claim_date_range: Optional[str] = Field(None, description="领单日期范围，格式：YYYY-MM-DD,YYYY-MM-DD")
    usage_status: Optional[str] = Field(None, description="使用状态筛选（0=未使用，1=已使用）")
    is_abnormal: Optional[str] = Field(None, description="异常状态筛选（0=异常，1=正常）")
    is_invalid: Optional[str] = Field(None, description="失效状态筛选（0=未失效，1=已失效）")
    usage_date_range: Optional[str] = Field(None, description="用单日期范围，格式：YYYY-MM-DD,YYYY-MM-DD")
    is_all: Optional[bool] = Field(False, description="是否获取全部数据，传 true 时忽略分页参数")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")
