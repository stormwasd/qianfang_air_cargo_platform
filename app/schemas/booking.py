"""
订舱相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, date


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
      "order_contact_name": "张三",  // 订单联系人姓名（可选，未传时读取业务参数默认值）
      "order_contact_phone": "13800138000",  // 订单联系人电话（可选，未传时读取业务参数默认值）
      "bookings": [
        {
          "origin_station": "",  // 始发站（三字码）
          "destination": "",  // 到达站（三字码）
          "flight_date": "",  // 航班日期（格式：YYYY-MM-DD）
          "shipper_unit": "",  // 托运单位（平台业务数据，不映射到南航 createOrder 请求）
          "flight_number": "",  // 航班号
          "booking_remark_wide": "",  // 宽体机订舱备注
          "booking_remark_narrow": "",  // 窄体机订舱备注
          "cargo_type": "",  // 货物类型
          "cargo_type_code": "",  // 货物类型费率代码
          "cargo_code": "",  // 货物代码
          "cargo_name": "",  // 货物名称
          "quantity": "",  // 件数
          "weight": "",  // 重量
          "product_name": "",  // 产品名称
          "booking_volume": "",  // 订舱体积（可选；未填时执行阶段由南航接口计算默认值）
          "oversized_cargo": "",  // 超规货
          "special_cargo_code": "",  // 用户附加特货码（可选）；多个使用英文逗号分隔，例如 GEN,AKA
          "no_dangerous_goods": "",  // 无危险品
          "consignee": "",  // 收货人
          "consignee_phone": "",  // 收货人手机号
          "storage_and_transportation_precautions": ""  // 储运注意事项（可选）
        }
      ],
      "outbound_cargo_and_mail_handling_fee_options": "普货"
    }
    
    说明：
    - `order_contact_name` 和 `order_contact_phone` 位于 form_data 顶层，不在 bookings 数组元素中
    - 执行南航订舱时，`contactName`、`contactPhone` 优先使用上述 form_data 字段；未传时分别读取业务参数配置中的 `business_default.order_contact_name`、`business_default.order_contact_phone`
    - `shipper_unit` 仅作为平台业务数据保存，不替换南航 createOrder 中的任何字段；`orderShipmentContact` 按南航请求结构传 null
    - `special_cargo_code` 可不填；执行时按始发站、目的站、货物类型和有效产品名称查询南航默认特货码，再与用户码去重合并。平台 `form_data` 回写为英文逗号格式，发往南航的 `spCode`、`productionCode` 使用 `/` 格式
    - 南航接口订舱时，`bookings[0].product_name` 有值则同时映射到 createOrder 的 `parentProductionName`、`parentProductionNameCn`；未填时沿用 `direct_order.parent_production_name`、`direct_order.parent_production_name_cn`，配置未提供时默认 `南航快运`
    - `bookings[0].booking_volume` 可不填；未填、为 `null` 或空字符串时，执行阶段使用 `origin_station` 和 `weight` 调用南航 `calculateCWeight`，并将返回的 `volume` 用于后续 `calculateCharge`、`createOrder`；已填写时原值优先
    - 最终体积确定后，执行阶段按航班、货物类型、重量、体积及有效产品名称查询南航运价舱位；返回的 `spaceClass` 用于 `bookGrade`、`spaceClass`，`subSpaceClass` 用于同名字段
    - `outbound_cargo_and_mail_handling_fee_options` 只能填写一个费用名称：贵重物品、活体动物、危险品、鲜活易腐、鲜活容腐、普货、急件快件
    - 批量Excel使用 `POST /api/v1/bookings/china-southern-air/import-excel` 上传；后端按 `nanfang_air_cargo_type` 数据字典的 `label` 匹配货物类型，并把对应 `value` 写入 `cargo_type_code`
    - 为兼容仍由前端解析Excel后调用 `POST /api/v1/bookings` 的流程，南航新增/修改接口也会在 `cargo_type_code` 缺失时按同一数据字典自动补齐；已传入非空值时保持原值
    - 执行订舱时由服务端查询航班机型，按系统参数中的宽窄体规则选择对应备注
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
    booking_date_start: Optional[date] = Field(None, description="订舱日期开始（格式：YYYY-MM-DD，作用于booking_time）")
    booking_date_end: Optional[date] = Field(None, description="订舱日期结束（格式：YYYY-MM-DD，作用于booking_time）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")


class BookingResponse(BaseModel):
    """订舱响应schema"""
    id: str  
    form_data: Dict[str, Any]
    booking_status: str
    invoice_status: str
    booking_time: datetime
    master_airwaybill_number: Optional[str]
    rpa_work_uuid: Optional[str]
    rpa_queue_uuid: Optional[str]
    rpa_queue_id: Optional[str]
    booking_cancel_status: str
    booking_feedback: Optional[str] = None
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
    task_id: Optional[str] = Field(
        None, description="历史队列任务ID；南航直连订舱固定为null"
    )
    success: bool
    error_message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "结构化失败详情；南航上游调用失败时包含 stage、http_status 和完整的 "
            "upstream_response；最终订舱失败时 request_context 包含实际提交的 "
            "contactName、contactPhone，request_data 包含发往 createOrder 的完整 JSON "
            "请求体；费用选项不匹配时还包含 selected_option、normalized_selected_option、"
            "available_options。不会包含 Token、Cookie 或请求头"
        ),
    )


class BookingExecuteResponse(BaseModel):
    """批量执行订舱响应schema"""
    items: List[BookingExecuteItem]
    total: int
    success_count: int
    failed_count: int

