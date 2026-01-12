"""
运单相关的Pydantic schemas
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


class WaybillCreate(BaseModel):
    """
    创建运单schema
    
    form_data 数据结构说明：
    form_data 是一个字典结构，根据选择的航司（airline字段）包含不同的字段：
    
    - airline（必填）：航司标识，可以是字典值（"1"=深圳航空，"2"=南方航空）或字符串（"深圳航空"、"南方航空"）
    
    深圳航空字段结构（airline 可以是 "1" 或 "深圳航空"）：
    {
      "airline": "1",  // 或 "深圳航空"
      "flight_info": {
        "destination": "",  // 到达站
        "flight_date": "",  // 航班日期
        "flight_number": "",  // 航班号
        "origin_station": "",  // 始发站
        "waybill_type": ""  // 运单类型（可选，仅深圳航空，如：普通运单、加急运单等）
      },
      "shipper_consignee_info": {
        "consignee_info": "",  // 收货人信息
        "shipper_info": "",  // 发货人信息
        "shipper_unit": ""  // 托运单位
      },
      "cargo_info": {
        "quantity": "",  // 件数
        "weight": "",  // 重量
        "chargeable_weight": "",  // 计费重量
        "freight_code": "",  // 运价代码
        "cargo_code": "",  // 货物代码
        "cargo_name": "",  // 货物名称
        "package": ""  // 包装
      },
      "other_fees": {
        "packaging_fee": "",  // 包装费
        "pickup_fee": "",  // 上门提货费
        "delivery_fee": ""  // 派送费
      }
    }
    
    南方航空字段结构（airline 可以是 "2" 或 "南方航空"）：
    {
      "airline": "2",  // 或 "南方航空"
      "flight_info": {
        "destination": "",  // 到达站
        "flight_date": "",  // 航班日期
        "flight_number": "",  // 航班号
        "booking_remark": "",  // 订舱备注
        "origin_station": ""  // 始发站
      },
      "cargo_info": {
        "cargo_type": "",  // 货物类型
        "cargo_code": "",  // 货物代码
        "cargo_name": "",  // 货物名称
        "quantity": "",  // 件数
        "weight": "",  // 重量
        "booking_volume": "",  // 订舱体积
        "product_name": "",  // 产品名称
        "oversized_cargo": "",  // 超规货
        "special_cargo_code": ""  // 特货码
      },
      "contact_info": {
        "consignee": "",  // 收货人
        "consignee_phone": "",  // 手机号（收货人）
        "shipper_unit": "",  // 托运单位
        "shipper": "",  // 托运人
        "shipper_phone": "",  // 手机号（托运人）
        "address": {  // 地址（对象类型）
          "region": "",  // 省/市/区
          "detail": ""  // 详细地址
        }
      },
      "dangerous_goods_declaration": {
        "no_hidden_dangerous_goods": "",  // 该票货物无隐含危险品
        "agent_checker_signature": "",  // 代理公司检查人签字
        "agent_consignor_signature": ""  // 代理公司交运人签字
      },
      "other_info": {
        "order_contact": "",  // 订单联系人
        "contact_phone": "",  // 联系人电话
        "settlement_file_number": ""  // 结算文件号
      },
      "other_fees": {
        "packaging_fee": "",  // 包装费
        "pickup_fee": "",  // 上门提货费
        "delivery_fee": ""  // 派送费
      }
    }
    
    说明：
    - 所有字段的值都是字符串类型
    - address 是对象类型，包含 region（省/市/区）和 detail（详细地址）两个字段
    - 不同航司的字段结构不同，前端需要根据 airline 字段来展示对应的表单字段
    - 深圳航空的运单可以选择性提供 flight_info.waybill_type 字段（运单类型），南方航空不需要此字段
    """
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），根据航司类型包含不同的字段结构")


class WaybillQuery(BaseModel):
    """运单查询schema"""
    airline_record_status: Optional[str] = Field(None, description="航司录单执行状态筛选（未执行、执行中、执行失败）")
    cargo_station_record_status: Optional[str] = Field(None, description="货站录单执行状态筛选（未执行、执行中、执行失败）")
    document_print_status: Optional[str] = Field(None, description="单据打印执行状态筛选（未执行、执行中、执行失败）")
    booking_date_start: Optional[date] = Field(None, description="开单日期开始（格式：YYYY-MM-DD）")
    booking_date_end: Optional[date] = Field(None, description="开单日期结束（格式：YYYY-MM-DD）")
    airline: Optional[str] = Field(None, description="航司（模糊搜索）")
    destination: Optional[str] = Field(None, description="目的站（模糊搜索）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索）")
    waybill_type: Optional[str] = Field(None, description="运单类型（模糊搜索，从form_data.flight_info.waybill_type中提取，仅深圳航空）")
    shipper: Optional[str] = Field(None, description="托运单位（模糊搜索）")
    waybill_number: Optional[str] = Field(None, description="运单号（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    page_size: int = Field(10, ge=1, le=100, description="每页数量")


class WaybillResponse(BaseModel):
    """运单响应schema"""
    id: str  # ID以字符串形式返回
    waybill_number: Optional[str]
    form_data: Dict[str, Any]
    airline_record_status: str
    cargo_station_record_status: str
    document_print_status: str
    departure_time: Optional[datetime]
    booking_date: date
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class WaybillListResponse(BaseModel):
    """运单列表响应schema"""
    total: int
    items: List[WaybillResponse]

