"""
订舱相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class BookingCreate(BaseModel):
    """
    创建订舱schema
    
    form_data 数据结构说明：
    form_data 是一个字典结构，包含航司和订舱信息数组（支持批量订舱）：
    
    - airline（必填）：航司名称，值为"南方航空"或其他航司（预留）
    - bookings（必填）：订舱信息数组，包含一条或多条订舱记录
    
    南方航空字段结构：
    {
      "airline": "南方航空",
      "bookings": [
        {
          "origin_station": "",  // 始发站（三字码）
          "destination": "",  // 到达站（三字码）
          "flight_date": "",  // 航班日期（格式：YYYY-MM-DD）
          "shipper_unit": "",  // 托运单位
          "flight_number": "",  // 航班号
          "booking_remark": "",  // 订舱备注
          "cargo_type": "",  // 货物类型
          "cargo_code": "",  // 货物代码
          "cargo_name": "",  // 货物名称
          "quantity": "",  // 件数
          "weight": "",  // 重量
          "product_name": "",  // 产品名称
          "oversized_cargo": "",  // 超规货
          "special_cargo_code": "",  // 特货码
          "no_dangerous_goods": "",  // 无危险品
          "consignee": "",  // 收货人
          "consignee_phone": ""  // 收货人手机号
        }
      ]
    }
    
    说明：
    - 所有字段的值都是字符串类型
    - bookings 是数组类型，支持批量提交多条订舱信息
    - 不同航司的字段结构可能不同，前端需要根据 airline 字段来展示对应的表单字段
    - 目前仅支持南方航空，其他航司字段结构待定义
    """
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），包含航司和订舱信息数组（支持批量订舱）")


class BookingUpdate(BaseModel):
    """
    修改订舱schema
    
    form_data 数据结构说明：
    form_data 是一个字典结构，包含航司和订舱信息数组：
    
    - airline（必填）：航司名称
    - bookings（必填）：订舱信息数组，通常只包含一条记录（长度为1）
    
    注意：修改时，bookings数组应该只包含一条记录，因为每条订舱记录对应数据库中的一条记录
    """
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），包含航司和订舱信息数组（通常只包含一条记录）")


class BookingQuery(BaseModel):
    """订舱查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    airline: Optional[str] = Field(None, description="航司（数据字典值精确匹配：1=深圳航空，2=南方航空）")
    booking_status: Optional[str] = Field(None, description="订舱状态筛选（数据字典值精确匹配：0=未执行，1=执行中，2=失败，3=成功）")
    invoice_status: Optional[str] = Field(None, description="开单状态筛选（数据字典值精确匹配：0=未开单，1=开单中，2=失败，3=成功）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, alias="pageSize", description="每页数量")


class BookingResponse(BaseModel):
    """订舱响应schema"""
    id: str  # ID以字符串形式返回
    form_data: Dict[str, Any]
    booking_status: str
    invoice_status: str
    booking_time: datetime
    master_airwaybill_number: Optional[str]
    rpa_work_uuid: Optional[str]
    rpa_queue_uuid: Optional[str]
    rpa_queue_id: Optional[str]
    booking_cancel_status: str
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    """订舱列表响应schema"""
    total: int
    items: List[BookingResponse]


class BookingExecuteRequest(BaseModel):
    """批量执行订舱请求schema"""
    booking_ids: List[str] = Field(..., min_items=1, description="订舱ID列表（至少包含一个ID）")


class BookingExecuteItem(BaseModel):
    """单个订舱执行结果schema"""
    booking_id: str
    task_id: Optional[str] = None
    success: bool
    error_message: Optional[str] = None


class BookingExecuteResponse(BaseModel):
    """批量执行订舱响应schema"""
    items: List[BookingExecuteItem]
    total: int
    success_count: int
    failed_count: int

