"""
运单相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
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
        "package": "",  // 包装
        "storage_and_transportation_precautions": ""  // 储运注意事项（可选）
      },
      "other_fees": {
        "packaging_fee": "",  // 包装费
        "pickup_fee": "",  // 上门提货费
        "delivery_fee": ""  // 派送费
      },
      "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "",  // 充氧类水生动物货物收运检查单开关
      "pickup_method": ""  // 提货方式（独立字段，不参与RPA开单）
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
        "booking_volume": "",  // 订舱体积（可选）
        "product_name": "",  // 产品名称
        "oversized_cargo": "",  // 超规货
        "special_cargo_code": "",  // 特货码
        "storage_and_transportation_precautions": ""  // 储运注意事项（可选）
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
      },
      "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "",  // 充氧类水生动物货物收运检查单开关
      "pickup_method": ""  // 提货方式（独立字段，不参与RPA开单）
    }
    
    说明：
    - 所有字段的值都是字符串类型
    - address 是对象类型，包含 region（省/市/区）和 detail（详细地址）两个字段
    - 不同航司的字段结构不同，前端需要根据 airline 字段来展示对应的表单字段
    - 深圳航空的运单可以选择性提供 flight_info.waybill_type 字段（运单类型），南方航空不需要此字段
    """
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），根据航司类型包含不同的字段结构")


class WaybillUpdate(BaseModel):
    """
    修改运单 schema

    仅当运单处于「未开单」（airline_record_status="0"）或「开单失败」（airline_record_status="2"）时可修改，修改后可重新开单。
    form_data 结构与 WaybillCreate 一致；booking_date 可选，不传则保持原值。
    """
    form_data: Dict[str, Any] = Field(..., description="表单数据（JSON格式），与新增运单结构一致，整体替换")
    booking_date: Optional[date] = Field(None, description="开单日期（格式：YYYY-MM-DD），可选，不传则不修改")


class WaybillQuery(BaseModel):
    """运单查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    airline_record_status: Optional[str] = Field(None, description="航司录单执行状态筛选（数据字典值精确匹配：0=未开单，1=开单中，2=失败，3=成功）")
    cargo_station_record_status: Optional[str] = Field(None, description="货站录单执行状态筛选（数据字典值精确匹配：0=未执行，1=执行中，2=失败，3=已录单）")
    document_print_status: Optional[str] = Field(None, description="单据打印执行状态筛选（数据字典值精确匹配：0=未执行，1=执行中，2=失败）")
    booking_date_start: Optional[date] = Field(None, description="开单日期开始（格式：YYYY-MM-DD）")
    booking_date_end: Optional[date] = Field(None, description="开单日期结束（格式：YYYY-MM-DD）")
    airline: Optional[str] = Field(None, description="航司（数据字典值精确匹配：1=深圳航空，2=南方航空）")
    destination: Optional[str] = Field(None, description="目的站（城市名称模糊搜索，如输入'西宁'会匹配到'西宁曹家堡机场'对应的三字码XNN；也可直接输入三字码如'PEK'）")
    flight_number: Optional[str] = Field(None, description="航班号（模糊搜索）")
    waybill_type: Optional[str] = Field(None, description="运单类型（数据字典值精确匹配，仅深圳航空，如：0=普通运单，1=急件运单，2=鲜活运单等）")
    shipper: Optional[str] = Field(None, description="托运单位（模糊搜索）")
    waybill_number: Optional[str] = Field(None, description="运单号（模糊搜索）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")


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

