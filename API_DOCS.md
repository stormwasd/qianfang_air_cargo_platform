# API 文档

## 2026-10-23 派送单位联系人及联系电话改为可选

派送单位管理统一前缀 `/api/v1/delivery-units`，继续要求 `Authorization: Bearer <access_token>`。本次放宽联系人与联系电话的输入校验，新增、编辑均可在未填写联系方式时保存。

| 接口 | 方法及路由 | 联系方式处理 |
| --- | --- | --- |
| 新增派送单位 | `POST /api/v1/delivery-units` | `contact_person`、`contact_phone` 均可省略、传null或空字符串，未填保存为 `""` |
| 编辑派送单位 | `PUT /api/v1/delivery-units/{unit_id}` | 省略某字段保留该字段原值；显式传null或 `""` 清空对应字段 |
| 派送单位详情 | `GET /api/v1/delivery-units/{unit_id}` | 两项继续返回string，未填返回 `""` |
| 派送单位列表 | `GET /api/v1/delivery-units` | `data.items` 中两项继续返回string，未填返回 `""`；筛选分页不变 |

新增时 `delivery_name`（1～200字符）及 `settlement_method`（整数）继续必填，`delivery_code` 可选，未填写沿用原自动编码逻辑。联系人最长50字符、联系电话最长20字符，填写时仍必须使用字符串；不新增手机号格式限制。两项相互独立，可只填其中一项。编辑只更新请求中明确提供的字段。

新增请求示例（也可显式传 `"contact_person":null,"contact_phone":""`）：

```json
{"delivery_name":"测试派送单位","settlement_method":1}
```

新增成功响应示例：

```json
{
  "code": 0,
  "data": {
    "id": "371229268321112064",
    "delivery_code": "PSS003",
    "delivery_name": "测试派送单位",
    "contact_person": "",
    "contact_phone": "",
    "settlement_method": 1,
    "creator_id": "265357797422665728",
    "creator_name": "系统管理员",
    "created_at": "2026-10-23T09:00:00+08:00",
    "updated_at": "2026-10-23T09:00:00+08:00"
  },
  "msg": "派送单位创建成功"
}
```

编辑示例：`PUT /api/v1/delivery-units/371229268321112064`，请求 `{"contact_phone":null}` 仅清空电话，联系人和其他未提供字段保留；请求 `{"contact_person":"","contact_phone":""}` 清空两项。成功响应结构同新增，消息为 `派送单位更新成功`；详情和列表消息为 `查询成功`，列表包装仍为 `{"code":0,"data":{"total":1,"items":[...]},"msg":"查询成功"}`。

缺失新增必填字段、名称为空、联系方式超长或非字符串类型继续返回422；无有效登录凭证返回401/403；编辑或查询不存在的单位继续返回404。此次使用空字符串兼容数据库现有NOT NULL列和既有string响应，不需要执行SQL迁移或修改配置；不修改提货单位、客户等其他模块的联系人规则。

## 2026-10-22 汽运代理对账联调修正

本次涉及以下四个接口，认证、查询入参、日期边界、分页及各自独立的结算状态不变：

| 模块 | 方法 | 路由 |
| --- | --- | --- |
| 应收汽运代理 | GET | `/api/v1/reconciliation/receivable/road-agent/road` |
| 应收汽运代理 | POST | `/api/v1/reconciliation/receivable/road-agent/road/export` |
| 应付汽运代理 | GET | `/api/v1/reconciliation/road-agent/road` |
| 应付汽运代理 | POST | `/api/v1/reconciliation/road-agent/road/export` |

### 新增计费重量

两个列表的每条 `data.items` 新增 `chargeable_weight`（`string/null`），直接读取费用登记台同源的 `consignment_notes.form_data.chargeable_weight`。数值转成字符串，保留零值；字符串原样保留小数位。未保存、null、布尔值、对象、数组或非有限数值返回null，不使用 `weight` 代替，不根据体积、费率或总运费反推。原有托运书新增/修改接口可通过动态 `form_data` 保存该键，无需新增业务表字段。两个Excel导出均新增“计费重量”列，位于“重量”之后、“体积”之前；缺失时单元格留空。

例如，已保存 `form_data.weight=81, form_data.chargeable_weight=100` 时，应收列表响应如下（其余字段仍按同源数据返回）：

```json
{
  "code": 0,
  "data": {
    "items": [{
      "settlement_status": 0,
      "settlement_auditor_name": null,
      "settlement_time": null,
      "transport_date": "2026-10-21",
      "customer_name": "Tester",
      "cargo_name": "五金件",
      "origin_city": "北京市-市辖区-西城区",
      "origin_address": null,
      "destination_city": "河北省-保定市-徐水区",
      "destination_address": null,
      "consignee_info": null,
      "contact_phone": null,
      "quantity": "2",
      "weight": "81",
      "chargeable_weight": "100",
      "volume": null,
      "vehicle_type": null,
      "rate": null,
      "total_freight": null,
      "other_fees": null,
      "total_amount": null,
      "source_id": "371229268321112064",
      "actual_customer_name": "Tester"
    }],
    "total": 1,
    "page": 1,
    "pageSize": 10
  },
  "msg": "success"
}
```

应付列表保留原有 `agent_settlement_status`、`agent_settlement_auditor_name`、`agent_settlement_time`，同样新增 `chargeable_weight`，不改名为应收结算字段。

### 修复 MySQL 排序规则冲突导致的500

`GET /api/v1/reconciliation/receivable/road-agent/road?date_start=2026-10-22&date_end=2026-10-22` 是合法请求。原共享查询通过 `CAST(customers.id AS CHAR) = consignment_notes.customer_name` 关联客户，连接默认排序规则 `utf8mb4_0900_ai_ci` 与托运书列的 `utf8mb4_unicode_ci` 不同，会在统计总数时触发MySQL 1267，空结果日期也可能500。

现改为将客户ID的十进制字符串和托运书客户原值作二进制精确比较，避免字符串排序规则冲突；不把客户名称转换为数字，避免 `7abc`、`007`、`7.0` 错误匹配客户ID `7`，也避免大整数ID的浮点精度问题。修复同时作用于两个模块的列表、筛选与导出。没有匹配客户时仍保留托运书并显示原始客户值；没有匹配单据时列表正常返回 `{"code":0,"data":{"items":[],"total":0,"page":1,"pageSize":10},"msg":"success"}`。前端无需修改上述请求。本次无需新增SQL迁移或 `config.py` 配置；原模块所需的已有迁移仍须完成。

## 应收对账：五个模块（25 个接口）

本节按产品更正后的口径，**全部读取费用登记台应收数据**。统一前缀 `/api/v1/reconciliation/receivable`，均需 `Authorization: Bearer <access_token>`，认证规则与现有对账接口相同。以下是独立新增接口；原 `/api/v1/reconciliation/airline`、`pickup`、`delivery`、`air-agent`、`road-agent` 应付接口及其结算状态继续使用。

### 数据流、模块范围及结算规则

空运数据流：深航/南航原始运单、同行空运托运书 → 业务单据审核 → 费用登记台应收投影（包含财务暂存/审核覆盖值、客户制单费和现有合计计算）→ 应收对账 → 独立标记结算。来源单据须通过业务审核（`audit_status=2`）；费用登记台直接新增的手工单据可查询。财务审核不是强制门槛，可用 `financial_audit_status` 筛选。手工单据的 `source_id` 使用财务记录ID，兼容历史数据库中 `source_id=0` 的记录。

四个空运模块均返回完整应收字段，另提供物流单位元数据；金额不使用应付成本替代。具体范围：

| 模块 | 路径段 | 范围与费用口径 |
| --- | --- | --- |
| 航司对账 | `airline` | 全部符合上述审核规则的空运数据；航司、金额均取最终应收值 |
| 提货单位对账 | `pickup` | 最终上门提货单位非空的空运数据；单位取费用登记台最终 `payable.door_pickup_company`，上门提货费取 `receivable.door_pickup_fee` |
| 派送单位对账 | `delivery` | 最终派送单位非空，或应收机场提货费/派送费有非零有效金额的空运数据；单位取最终 `payable.delivery_company`，金额取 `receivable.airport_pickup_fee`、`receivable.delivery_fee` |
| 空运代理对账 | `air-agent` | 全部符合上述审核规则的空运数据；与原空运代理对账读取同源应收值，结算状态独立 |
| 汽运代理对账 | `road-agent` | 汽运费用登记台同源托运书，见下文；不增加业务审核或财务审核门槛 |

提货/派送单位名称当前只存在于费用登记台应付区，因此仅将其作为归属元数据，不把应付费用当成应收。实走航班号优先使用深航/南航来源记录 `actual_flight`、同行托运书 `form_data.actual_flight`；深航回退至开单航班号，其余回退最终应收航班号。手工新增单据回退最终应收航班号。单位和实走航班号查询批量获取，避免逐单查询。

汽运数据流：`GET /api/v1/consignment-notes?transport_type=1&is_financial=true` 同源的托运书标准列与动态 `form_data` → 汽运应收对账。日期、目的城市和客户原值以托运书标准列为准；其他业务字段直接读取动态表单。当前没有独立汽运应收扩展表，不重算费率或应收总费用。**未保存 `rate`、`total_amount` 时返回 `null`，不自行按“总运费＋其他费用”推算。** 无审核扩展、未审、暂存、已审的汽运托运书均可查询和结算。

每个应收模块分别保存结算状态、操作人和北京时间，五个模块互不联动，也不覆盖原应付五模块状态。查询、导出不创建扩展记录；无扩展记录按未结算处理。确认结算按需创建扩展记录，不修改原始单据、应收/应付JSON、业务审核或财务审核状态，不触发收款/付款。重复确认保留首次操作人和时间；取消清空本模块的操作人和时间，再次取消仍成功，无扩展记录时不创建记录。结算后费用登记台修改数据，会展示最新值，结算状态保持，不保存金额快照。

### 部署：先升级现有表，再启动应用

已有库须在新版应用启动前执行一次 **`sql/migration_add_receivable_reconciliation_fields.sql`**，按文件顺序执行空运、汽运两条 `ALTER TABLE`，两条均成功后再启动。无需新建表、重建表或重跑历史迁移；`create_all` 不会给已有表补列。MySQL DDL 自动提交，若第二条失败，先核对已添加列再处理，不要直接重复执行整个文件。

| 现有表 | 新字段前缀 | 本次新增内容 |
| --- | --- | --- |
| `air_financial_audit_data` | `receivable_airline_settlement` | 航司应收结算 |
| `air_financial_audit_data` | `receivable_pickup_settlement` | 提货单位应收结算 |
| `air_financial_audit_data` | `receivable_delivery_settlement` | 派送单位应收结算 |
| `air_financial_audit_data` | `receivable_agent_settlement` | 空运代理应收结算 |
| `peer_road_departure_manual_data` | `receivable_agent_settlement` | 汽运代理应收结算 |

每组四列：`<前缀>_status` int 默认0，`<前缀>_auditor_id` bigint 可空，`<前缀>_auditor_name` varchar(255) 可空，`<前缀>_time` datetime 可空；每个状态字段带索引。历史应付结算值不迁移至应收，新增状态默认未结算。新建库建表脚本已同步本次字段；其余历史列仍按原初始化/迁移流程创建。本次不新增 `config.py` 配置。

### 全部接口路径

下表路径均相对于 `/api/v1/reconciliation/receivable`。

| 模块 | 方法 | 路径 | 功能 |
| --- | --- | --- | --- |
| 航司 | GET | `/airline/air` | 分页列表 |
| 航司 | POST | `/airline/air/{source_type}/{source_id}/settle` | 确认结算 |
| 航司 | POST | `/airline/air/{source_type}/{source_id}/cancel-settlement` | 取消结算 |
| 航司 | POST | `/airline/air/batch-settle` | 批量确认 |
| 航司 | POST | `/airline/air/export` | 选中/筛选导出 |
| 提货单位 | GET | `/pickup/air` | 分页列表 |
| 提货单位 | POST | `/pickup/air/{source_type}/{source_id}/settle` | 确认结算 |
| 提货单位 | POST | `/pickup/air/{source_type}/{source_id}/cancel-settlement` | 取消结算 |
| 提货单位 | POST | `/pickup/air/batch-settle` | 批量确认 |
| 提货单位 | POST | `/pickup/air/export` | 选中/筛选导出 |
| 派送单位 | GET | `/delivery/air` | 分页列表 |
| 派送单位 | POST | `/delivery/air/{source_type}/{source_id}/settle` | 确认结算 |
| 派送单位 | POST | `/delivery/air/{source_type}/{source_id}/cancel-settlement` | 取消结算 |
| 派送单位 | POST | `/delivery/air/batch-settle` | 批量确认 |
| 派送单位 | POST | `/delivery/air/export` | 选中/筛选导出 |
| 空运代理 | GET | `/air-agent/air` | 分页列表 |
| 空运代理 | POST | `/air-agent/air/{source_type}/{source_id}/settle` | 确认结算 |
| 空运代理 | POST | `/air-agent/air/{source_type}/{source_id}/cancel-settlement` | 取消结算 |
| 空运代理 | POST | `/air-agent/air/batch-settle` | 批量确认 |
| 空运代理 | POST | `/air-agent/air/export` | 选中/筛选导出 |
| 汽运代理 | GET | `/road-agent/road` | 分页列表 |
| 汽运代理 | POST | `/road-agent/road/{source_id}/settle` | 确认结算 |
| 汽运代理 | POST | `/road-agent/road/{source_id}/cancel-settlement` | 取消结算 |
| 汽运代理 | POST | `/road-agent/road/batch-settle` | 批量确认 |
| 汽运代理 | POST | `/road-agent/road/export` | 选中/筛选导出 |

### 空运四模块查询参数

沿用对应应付模块的搜索字段；新接口对日期、状态及分页参数显式校验，非法值返回422。运单号、航班日期、客户和航司筛选使用费用登记台**最终应收值**，应用全部筛选后再统计总数和分页，避免财务覆盖值与列表不一致。

| 参数 | 类型/默认 | 说明 |
| --- | --- | --- |
| `waybill_numbers` | string，可选 | 完整运单号精确匹配；多个用英文逗号隔开，忽略各项首尾空格和空项 |
| `flight_date_start` | date，可选 | 航班日期开始，`YYYY-MM-DD`，包含当天 |
| `flight_date_end` | date，可选 | 航班日期结束，包含当天；日期缺失不满足已传入的日期范围 |
| `financial_audit_status` | int，可选 | 0未审、1暂存、2已审；不传不限 |
| `customer_name` | string，可选 | 应收客户原值包含匹配，通常传客户ID；不是公司名称反查 |
| `settlement_status` | int，可选 | **当前应收模块**的0未结算、1已结算；不传不限 |
| `page` | int，1 | 页码，至少1 |
| `pageSize` | int，10 | 每页1～200条 |
| `airline` | string，可选 | 仅航司、空运代理：最终应收航司精确匹配；`全部`不限 |
| `actual_flight_number` | string，可选 | 仅提货、派送单位：实走航班号包含匹配 |
| `pickup_company` | string，可选 | 仅提货单位：最终上门提货单位包含匹配 |
| `delivery_company` | string，可选 | 仅派送单位：最终派送单位包含匹配 |

GET示例：`/api/v1/reconciliation/receivable/pickup/air?flight_date_start=2026-10-21&flight_date_end=2026-10-22&pickup_company=某提货单位&settlement_status=0&page=1&pageSize=20`。

返回统一包装 `{"code":0,"data":{"items":[...],"total":1,"page":1,"pageSize":20},"msg":"success"}`。空列表成功返回 `items:[]`、`total:0`。空运按最终航班日期、完整运单号、来源ID倒序。

### 空运列表字段（四个模块一致）

业务字段直接平铺，不额外嵌套 `receivable`；费用、件数、重量等采用费用登记台的 string/null，状态为整数，ID为字符串。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_type` | string | `shenzhen_air`、`china_southern_air`、`peer_air` |
| `source_id` | string | 来源主表ID；手工新增单据为财务记录ID，操作/导出原样传回 |
| `settlement_status` | int | 本应收模块0未结算、1已结算；不使用旧接口的 `*_settlement_status` 字段 |
| `settlement_auditor_name` | string/null | 本模块结算操作人 |
| `settlement_time` | string/null | 本模块结算时间，北京时间ISO 8601字符串，如`2026-10-21T17:32:35+08:00`，可能含微秒 |
| `financial_audit_status` | int | 财务审核状态0/1/2 |
| `financial_auditor_name` | string/null | 财务审核人 |
| `actual_customer_name` | string/null | 费用登记台客户公司名称投影 |
| `actual_flight_number` | string/null | 实走航班号，按上文来源规则获取 |
| `pickup_company` | string/null | 最终上门提货单位元数据 |
| `delivery_company` | string/null | 最终派送单位元数据 |
| `waybill_number` | string/null | 最终应收运单号；仅应收该值为null时回退费用登记台顶层运单号 |
| `flight_date` | string/null | 航班日期 |
| `customer_name` | string/null | 应收客户原值，通常为客户ID |
| `consignee_phone` | string/null | 收货电话 |
| `origin` / `destination` | string/null | 始发站/目的站 |
| `airline` / `flight_number` | string/null | 航空公司/应收航班号 |
| `cargo_name` | string/null | 货物名称 |
| `pieces` / `weight` | string/null | 件数/重量 |
| `chargeable_weight` / `freight_rate` | string/null | 计费重量/费率 |
| `freight` / `document_fee` | string/null | 运费/制单费 |
| `packaging_fee` | string/null | 包装费 |
| `telegram_fee` / `telegram_code` | string/null | 电报费/电报号 |
| `door_pickup_fee` | string/null | 应收上门提货费，不是应付提货成本 |
| `airport_pickup_fee` | string/null | 应收机场提货费，不是应付成本合计 |
| `delivery_fee` | string/null | 应收派送费，不是 `delivery_cost` |
| `carrier_deduction` | string/null | 承运扣款 |
| `cca` / `other_fees` | string/null | CCA/其他费用 |
| `other_fee_remark` | string/null | 其他费用说明 |
| `total_amount` | string/null | 费用登记台最终应收总金额，沿用其现有计算结果 |
| `payment_method` | string/null | 付款方式 |
| `consignee` / `pickup_method` | string/null | 收货单位/提货方式 |
| `collection_payment` / `remark` | string/null | 代收货款/备注 |
| `gross_profit` | string/null | 费用登记台毛利投影；仅此既有指标涉及成本计算 |

### 汽运查询参数与列表字段

| 参数 | 类型/默认 | 说明 |
| --- | --- | --- |
| `date_start` | date，北京时间当天减30天 | 托运日期开始，包含当天 |
| `date_end` | date，北京时间当天 | 托运日期结束，包含当天 |
| `customer_name` | string，可选 | 纯数字客户ID精确匹配；其他值同时包含匹配客户原值、公司名称 |
| `destination_city` | string，可选 | 目的城市包含匹配，`%`/`_`按普通字符匹配 |
| `settlement_status` | int，可选 | 本汽运应收模块0未结算、1已结算；不传不限 |
| `page` / `pageSize` | int，1/10 | page至少1；pageSize为1～200 |

汽运包装与空运一致，按托运日期、来源ID倒序。每条包括 `source_id`、`actual_customer_name`、`settlement_status`、`settlement_auditor_name`、`settlement_time`，以及以下 string/null 应收字段：

| 字段 | 说明 |
| --- | --- |
| `transport_date` / `customer_name` | 托运日期/客户原值（标准列） |
| `cargo_name` | 货物名称 |
| `origin_city` / `origin_address` | 始发城市/详细地址 |
| `destination_city` / `destination_address` | 目的城市（标准列）/详细地址 |
| `consignee_info` / `contact_phone` | 收货人/联系电话 |
| `quantity` / `weight` / `volume` | 件数/重量/体积 |
| `chargeable_weight` | 计费重量，取 `form_data.chargeable_weight`；缺失返回null，不以重量代替 |
| `vehicle_type` / `rate` | 车型/费率 |
| `total_freight` / `other_fees` | 总运费/其他费用 |
| `total_amount` | 已保存的应收总费用；没有该字段时null |

### 确认、取消及批量结算

单条确认和取消均为POST，无请求体。空运路径的 `source_type` 仅限上述三种，`source_id` 为1～9223372036854775807；汽运只传 `source_id`。空运单据必须存在且通过业务审核，或为费用登记台手工单据；汽运必须是 `transport_type=1` 的托运书。提货/派送确认结算还校验所属模块范围；取消允许清理已移除单位/费用的历史结算。

批量请求：空运四模块使用相同结构：

```json
{"items":[{"source_type":"shenzhen_air","source_id":"370976932327723008"}]}
```

汽运使用：

```json
{"items":[{"source_id":"371229268321112064"}]}
```

`items`必填，最多1000项；ID必须为正整数字符串且不超过bigint范围。重复项去重；空数组成功处理0条。所有单据先校验再写入，一个不合法则整体失败，不会部分结算。按来源和ID固定顺序锁定现有来源/扩展记录，首次创建扩展也遵循同一顺序。唯一冲突回滚并返回409，可刷新后重试。

确认成功：`{"code":0,"data":null,"msg":"确认结算成功"}`；取消成功消息为`取消结算成功`；批量成功消息如`成功结算2条单据`。

### Excel导出

POST `/export`请求体使用对应列表的筛选字段，另接受可选 `selected_items`（最多1000项），结构与对应批量 `items` 单项相同：

```json
{
  "flight_date_start":"2026-10-21",
  "flight_date_end":"2026-10-22",
  "settlement_status":0,
  "selected_items":[{"source_type":"shenzhen_air","source_id":"370976932327723008"}]
}
```

`selected_items`非空时导出“选中项与筛选结果的交集”；省略、null或空数组时导出所有筛选结果。接受page/pageSize但导出不受分页截断。空运所有列表筛选参数均可用，提货/派送分别使用各自单位参数。汽运默认日期与GET一致，若需不限制日期，在导出体中显式传`date_start:null,date_end:null`。

返回xlsx二进制，`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，`Content-Disposition`携带UTF-8文件名。表头含序号、来源ID（空运另含来源类型）、本模块结算状态和操作人/时间、客户及全部应收字段；空运另含财务状态、实走航班和物流单位。状态导出为未结算/已结算，电话号码保留前导0，用户文本强制Excel文本单元格，防止公式执行。金额按列表字符串导出，不再计算。无匹配数据返回400。

### 错误与验证边界

| 状态码 | 场景 |
| --- | --- |
| 401/403 | 无有效登录凭证或账号不可用，沿用现有认证逻辑 |
| 400 | 开始日期晚于结束日期、单据不属于待确认的物流应收模块、无匹配导出数据 |
| 404 | 来源不存在、空运来源未通过业务审核、来源类型与ID不对应、将空运托运书用于汽运结算 |
| 409 | 并发写入冲突，事务回滚，刷新后重试 |
| 422 | 日期格式、分页、状态、来源枚举、ID或批量数量不合法 |
| 500 | 汽运已保存动态表单不是合法JSON对象等数据异常；不把损坏数据静默当作零金额 |

本次本地回归使用真实SQLite查询和FastAPI HTTP调用，覆盖25个接口、费用登记台投影一致性、跨模块/应收应付状态隔离、全批回滚、来源审核门槛、手工单据ID、筛选分页、文本安全导出与登录校验。未在生产数据库执行迁移，也未执行真实收付款操作。

## 应付对账：汽运代理对账（5 个接口）

统一前缀 `/api/v1/reconciliation/road-agent`，均需登录并携带 `Authorization: Bearer <access_token>`，认证规则与现有对账接口一致。该模块读取费用登记台汽运的数据源，列表只读，操作区提供确认结算；另提供取消、批量结算、选中/批量导出。

### 数据流与部署

当前汽运费用登记台复用 `GET /api/v1/consignment-notes?transport_type=1&is_financial=true`，业务字段保存于 `consignment_notes` 的标准列和 `form_data`，审核状态位于 `peer_road_departure_manual_data`。本模块直接读取同一份保存数据，不复制账单，不使用空运 `AirFinancialAuditData`，不重算总运费、费率或应收总费用。未保存到后端的前端临时计算值不会自动出现在对账中。

汽运费用登记台当前没有强制“单据已审核”或“财务已审核”的条件，汽运代理对账也不增加该门槛：没有扩展记录、未审、暂存、已审的汽运托运书均可查询、结算；空运托运书不允许混入。此规则与空运代理对账不同。

结算状态、操作人及时间独立保存在现有汽运扩展表的 `agent_settlement_*` 列。读取、导出不创建扩展记录，无扩展记录时按未结算返回；首次确认结算时才按需创建扩展记录。操作不会修改原业务单据、动态表单、单据审核或财务审核状态，结算本身也不产生付款操作。结算后若费用登记台修改数据，对账展示最新保存值，结算状态保持不变，不保存费用快照。

**已有数据库须在新版应用启动前执行一次 `sql/migration_add_road_agent_settlement_fields.sql`**，新增四列及状态索引，不新建业务表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `agent_settlement_status` | int，默认0 | 0=未结算，1=已结算 |
| `agent_settlement_auditor_id` | bigint，可空 | 结算操作人ID |
| `agent_settlement_auditor_name` | varchar(255)，可空 | 结算操作人姓名 |
| `agent_settlement_time` | datetime，可空 | 结算时间，北京时间 |

新建库的汽运扩展表脚本已同步上述列；已有库不要重建表。历史财务审核字段仍使用原来的 `sql/migration_add_financial_audit_fields.sql` 管理。本次不新增 `config.py` 配置。应用 `create_all` 不会自动为已有表补列。

### 1. 列表查询

`GET /api/v1/reconciliation/road-agent/road`

| 参数 | 类型 | 默认/作用 |
| --- | --- | --- |
| `date_start` | date | 北京时间当天往前30天；托运日期起始，包含当天，格式 `YYYY-MM-DD` |
| `date_end` | date | 北京时间当天；托运日期结束，包含当天，格式 `YYYY-MM-DD` |
| `customer_name` | string | 可选；传纯数字客户ID时精确匹配；其他值同时模糊匹配托运书客户原值和客户公司名称 |
| `destination_city` | string | 可选；模糊匹配目的城市，沿用托运书标准列 `destination` |
| `page` | int | 默认1，必须≥1 |
| `pageSize` | int | 默认10，范围1～200 |

日期默认值在每次请求时按北京时间生成，不在服务启动时固定。客户及目的城市输入前后空格会去除，`%`、`_` 按普通字符搜索。所有筛选在数据库分页之前执行，排序为托运日期倒序、托运书ID倒序。客户下拉选择可复用现有客户查询接口，目的城市字典由前端沿用现有字典接口，不增加字典接口。

示例：`GET /api/v1/reconciliation/road-agent/road?date_start=2026-10-18&date_end=2026-10-25&customer_name=7&destination_city=SZX&page=1&pageSize=20`。

响应格式：`{"code":0,"data":{"items":[...],"total":3,"page":1,"pageSize":20},"msg":"success"}`。每个列表元素直接平铺以下字段；件数、重量、费率、费用可接受原始数值或字符串，返回时统一为 `string/null`，不丢失零值、手机号前导零和字符串小数位。动态表单中的布尔值、数组、对象不作为数值或文本列返回。

| 字段 | 展示/来源 |
| --- | --- |
| `source_id` | 汽运托运书ID，字符串；操作必须传此ID，不是扩展表ID |
| `agent_settlement_status` | 结算状态，整数：0=未结算，1=已结算 |
| `agent_settlement_auditor_name` | 结算操作人姓名，可空 |
| `agent_settlement_time` | 结算时间，北京时间，可空 |
| `transport_date` | 托运日期，取标准列 `consignment_date` |
| `customer_name` | 客户名称，托运书客户原值，可为客户ID |
| `actual_customer_name` | 若客户原值为客户ID则显示对应公司名称，否则显示原值 |
| `cargo_name` | 货物名称，取 `form_data.cargo_name` |
| `origin_city` | 始发城市，取 `form_data.origin_city` |
| `origin_address` | 始发详细地址，取 `form_data.origin_address` |
| `destination_city` | 目的城市，取标准列 `destination` |
| `destination_address` | 目的详细地址，取 `form_data.destination_address` |
| `consignee_info` | 收货人，取 `form_data.consignee_info` |
| `contact_phone` | 联系电话，取 `form_data.contact_phone` |
| `quantity` | 件数，取 `form_data.quantity` |
| `weight` | 重量，取 `form_data.weight` |
| `chargeable_weight` | 计费重量，取 `form_data.chargeable_weight`，返回string/null；保留零值，缺失不以重量代替 |
| `volume` | 体积，取 `form_data.volume` |
| `vehicle_type` | 车型，取 `form_data.vehicle_type` |
| `rate` | 费率，透传可选的同名已保存键 `form_data.rate`；缺失返回null，不用客户费率或总运费反推 |
| `total_freight` | 总运费，取 `form_data.total_freight` |
| `other_fees` | 其他费用，取 `form_data.other_fees` |
| `total_amount` | 应收总费用，读取 `form_data.total_amount` 原值；未保存则返回null，不在对账中重算 |

实际提供的费用登记台查询样例（`transport_type=1&is_financial=true`）只有 `total_freight`、`other_fees` 等原始业务值，没有 `chargeable_weight`、`rate` 或 `total_amount`。现有汽运 `/consignment-notes/audit`、`/consignment-notes/financial/audit` 暂存/审核仅更新审核状态，不会生成这三个字段。因此该样例在对账中这三列均返回null，导出留空；不能据此假设计费重量等于重量、应收总费用等于总运费加其他费用。若费用登记台前端另外计算显示这些列，须先核实其实际字段或计算规则，再补齐同源映射；本次不改变原有汽运保存、审核行为。

序号由前端按 `(page-1)*pageSize+行索引+1` 生成。标准列由原有托运书新增/修改接口随表单同步保存。原接口的动态 JSON 原样存储行为保持不变。

### 2. 确认结算

`POST /api/v1/reconciliation/road-agent/road/{source_id}/settle`

无需请求体。将该汽运托运书标记为已结算，保存当前操作人及北京时间；重复确认是幂等操作，不覆盖首次结算操作人和时间。成功：`{"code":0,"data":null,"msg":"确认结算成功"}`。

### 3. 取消结算

`POST /api/v1/reconciliation/road-agent/road/{source_id}/cancel-settlement`

无需请求体。恢复未结算并清空结算操作人及时间；重复取消成功，且不会为尚无扩展记录的单据新建空记录。成功：`{"code":0,"data":null,"msg":"取消结算成功"}`。

### 4. 批量确认结算

`POST /api/v1/reconciliation/road-agent/road/batch-settle`

```json
{"items":[{"source_id":"370976932327723008"},{"source_id":"370976932327723009"}]}
```

`items` 必填，最多1000项，ID为正整数的字符串，范围不超过有符号bigint。重复ID会去重，空数组返回成功且不更改数据。全部单据在同一事务内验证并执行；任一ID不存在或属于空运时整体失败，不部分结算。已结算项保留首次操作信息。成功示例：`{"code":0,"data":null,"msg":"成功批量结算 2 条单据"}`。

单条及批量操作先按ID顺序锁定汽运托运书，再锁定扩展记录，避免首次结算时并发创建重复扩展记录。

### 5. 选中/批量导出

`POST /api/v1/reconciliation/road-agent/road/export`

请求体支持与列表同名的全部筛选参数，并增加 `selected_items`（可选，最多1000项）：

```json
{
  "date_start":"2026-10-18",
  "date_end":"2026-10-25",
  "customer_name":"7",
  "destination_city":"SZX",
  "selected_items":[{"source_id":"370976932327723008"}]
}
```

未传 `selected_items` 或传空数组时，导出全部符合筛选条件的记录；非空时，导出筛选结果与选中ID的交集。忽略 `page/pageSize` 分页，不受200行限制。日期省略时与列表默认值一致；导出JSON可显式传 `"date_start":null` 或 `"date_end":null` 取消对应边界，例如 `{"date_start":null,"date_end":null}` 导出全部日期。

返回Excel文件，`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，UTF-8文件名 `汽运代理对账列表_时间戳.xlsx`。列顺序：序号、结算状态、托运日期、客户名称、货物名称、始发城市、始发详细地址、目的城市、目的详细地址、收货人、联系电话、件数、重量、计费重量、体积、车型、费率、总运费、其他费用、应收总费用。客户名称列使用解析后的公司名称，状态转成“已结算/未结算”；字符串明确写为文本单元格，避免Excel公式执行并保留手机号前导零。

### 错误响应

新接口使用HTTP错误状态（框架统一处理时错误正文可能被转换为项目格式）：日期开始晚于结束返回400；导出无匹配数据返回400；操作ID不存在/不是汽运返回404；ID、日期、分页或批量请求格式不合法返回422；并发写入唯一约束冲突回滚并返回409，可刷新后重试。未登录按现有认证规则返回401/403。损坏的动态表单JSON返回500并指出托运书ID，不静默伪造账单数据。

## 应付对账：空运代理对账（5 个接口）

接口前缀为 `/api/v1/reconciliation/air-agent`，均需登录，使用 `Authorization: Bearer <access_token>`，认证规则与航司对账一致。

### 数据来源与部署

列表复用 `GET /api/v1/financial-audit/air`（费用登记台空运）的应收数据构建逻辑，覆盖深航、南航、同行空运及费用登记台手工新增单据。来源单据沿用其他应付对账的准入条件：出港手工数据已通过业务审核（`audit_status=2`），同行托运书还要求 `transport_type="0"`；费用登记台手工新增单据不依赖出港业务审核。

数据流为来源业务数据 → 出港手工录入费用 → 财务应收 JSON 覆盖 → 客户制单费及付款方式 → 应收合计和毛利重算 → 代理对账。应收字段保留费用登记台的最终值；其中 `waybill_number` 未设置财务覆盖值时取来源运单号。列表筛选、导出均使用这份最终应收数据，修改后的航班日期、运单号等可直接用于筛选，不使用未覆盖的原始值。

空运代理结算使用独立的 `agent_settlement_*` 字段，确认/取消/批量结算不会修改航司、提货单位、派送单位结算状态，不会修改应收应付 JSON 或财务审核状态。读取列表和导出不创建财务扩展记录；尚无财务扩展记录的来源单据按未审、未结算处理。

现有数据库需在启动新版应用前执行一次 `sql/migration_add_agent_settlement_fields.sql`，在已有 `air_financial_audit_data` 表新增以下字段及状态索引，不新建业务表：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `agent_settlement_status` | int，默认 0 | 0=未结算，1=已结算 |
| `agent_settlement_auditor_id` | bigint，可空 | 结算操作人 ID |
| `agent_settlement_auditor_name` | varchar(255)，可空 | 结算操作人姓名 |
| `agent_settlement_time` | datetime，可空 | 结算时间，采用北京时间 |

已有数据库只执行新增字段脚本，不要重新执行建表脚本。新建库的 `sql/migration_create_air_financial_audit_data.sql` 已包含这些字段，应用启动的 `create_all` 不会为已有表自动补列。本次不新增 `config.py` 配置。

### 1. 查询列表

`GET /api/v1/reconciliation/air-agent/air`

搜索参数名称与航司对账一致，均为可选；分页在全部筛选完成后执行。

| 参数 | 类型 | 默认值及说明 |
| --- | --- | --- |
| `waybill_numbers` | string | 运单号，支持英文逗号分隔多个值，去除各值首尾空格后精确匹配 |
| `flight_date_start` | date | 航班日期开始，`YYYY-MM-DD`，包含当天 |
| `flight_date_end` | date | 航班日期结束，`YYYY-MM-DD`，包含当天；两个日期可单独传入 |
| `airline` | string | 航司精确匹配，如深航、南航；不传或为“全部”时不限 |
| `financial_audit_status` | int | 财务审核：0=未审，1=暂存，2=已审 |
| `customer_name` | string | 沿用航司对账按客户原始值包含匹配，通常传客户 ID；公司展示名使用响应 `actual_customer_name` |
| `settlement_status` | int | **空运代理**结算状态：0=未结算，1=已结算；不限制其他对账的结算状态 |
| `page` | int | 1，最小 1 |
| `pageSize` | int | 10，最小 1 |

示例：`GET /api/v1/reconciliation/air-agent/air?flight_date_start=2026-10-21&flight_date_end=2026-10-22&settlement_status=0&page=1&pageSize=20`

返回统一 JSON：`{"code":0,"data":{"items":[...],"total":5,"page":1,"pageSize":20},"msg":"success"}`。按航班日期、运单号、来源 ID 倒序排列。每个 `items` 元素直接平铺应收字段，不嵌套 `receivable`，金额、件数、重量沿用费用登记台的字符串类型（可空）。

| 身份及状态字段 | 类型 | 说明 |
| --- | --- | --- |
| `source_type` | string | `shenzhen_air` / `china_southern_air` / `peer_air` |
| `source_id` | string | 来源主表 ID；**费用登记台手工新增单据返回财务记录自身 ID**，历史 `source_id=0` 记录也返回自身 ID，不向结算接口传 0 |
| `agent_settlement_status` | int | 0=未结算，1=已结算，供列表“结算状态”列使用 |
| `agent_settlement_auditor_name` | string/null | 代理结算操作人 |
| `agent_settlement_time` | string/null | 代理结算时间，北京时间字符串 |
| `financial_audit_status` | int | 财务审核状态 |
| `financial_auditor_name` | string/null | 财务审核人 |
| `actual_customer_name` | string | 客户 ID 对应的公司名称，未匹配时为空字符串 |

应收区字段完整映射如下（所有字段类型均为 `string/null`）：

| 字段 | 说明 | 字段 | 说明 |
| --- | --- | --- | --- |
| `waybill_number` | 运单号 | `flight_date` | 航班日期 |
| `customer_name` | 客户原始值，通常是客户 ID | `consignee_phone` | 收货电话 |
| `origin` | 始发站 | `airline` | 航空公司 |
| `flight_number` | 航班号 | `cargo_name` | 货物名称 |
| `pieces` | 件数 | `chargeable_weight` | 计费重量 |
| `freight_rate` | 费率 | `document_fee` | 制单费 |
| `packaging_fee` | 包装费 | `telegram_fee` | 电报费 |
| `telegram_code` | 电报号 | `other_fee_remark` | 其他费用说明 |
| `door_pickup_fee` | 上门提货费 | `airport_pickup_fee` | 机场提货费 |
| `carrier_deduction` | 承运扣款 | `total_amount` | 应收总金额 |
| `payment_method` | 付款方式 | `consignee` | 收货单位 |
| `destination` | 目的站 | `pickup_method` | 提货方式 |
| `weight` | 重量 | `freight` | 运费 |
| `cca` | CCA | `other_fees` | 其他费用 |
| `delivery_fee` | 派送费 | `collection_payment` | 代收货款 |
| `remark` | 备注 | `gross_profit` | 毛利 |

合计和毛利继续使用费用登记台的既有计算口径。客户 ID 匹配成功时，制单费和付款方式取客户配置。

### 2. 确认结算

`POST /api/v1/reconciliation/air-agent/air/{source_type}/{source_id}/settle`

无请求体。路径参数使用列表返回的 `source_type`、`source_id`；ID 必须是 1 至 9223372036854775807 的整数。确认时写入代理结算状态、当前用户及北京时间。重复确认已结算记录直接成功，保留原代理结算人和时间。无财务扩展记录的合法来源单据会创建扩展记录。

返回：`{"code":0,"data":null,"msg":"确认结算成功"}`。

### 3. 取消结算

`POST /api/v1/reconciliation/air-agent/air/{source_type}/{source_id}/cancel-settlement`

无请求体，路径参数同上。仅清除代理结算状态、操作人和时间；合法单据本来就未结算（包括无财务扩展记录）时也成功，不创建新记录。

返回：`{"code":0,"data":null,"msg":"取消结算成功"}`。

### 4. 批量确认结算

`POST /api/v1/reconciliation/air-agent/air/batch-settle`

请求体：

```json
{
  "items": [
    {"source_type": "shenzhen_air", "source_id": "101"},
    {"source_type": "peer_air", "source_id": "301"}
  ]
}
```

`items` 必填，最多 1000 项，每项类型和 ID 范围同单条结算，JSON 中 `source_id` 传数字字符串。按来源类型和 ID 去重，整个批次先校验所有单据，全部成功后在一个事务中提交；任何一项无效则整个批次不结算。已结算记录不覆盖原操作人和时间。空数组成功处理 0 条。

返回：`{"code":0,"data":null,"msg":"成功批量结算 2 条单据"}`，数量按去重后的单据数计。

### 5. 导出列表（选中下载/批量下载）

`POST /api/v1/reconciliation/air-agent/air/export`

请求体可包含与列表同名的搜索条件，以及 `selected_items`，各筛选字段类型、含义同列表。

```json
{
  "flight_date_start": "2026-10-21",
  "flight_date_end": "2026-10-22",
  "settlement_status": 0,
  "selected_items": [
    {"source_type": "shenzhen_air", "source_id": "101"}
  ]
}
```

`selected_items` 不传、为 `null` 或空数组时导出全部筛选结果；非空时导出筛选结果与选中单据的交集，最多传 1000 项。忽略 `page`、`pageSize` 的分页作用，不截取当前页；两个字段若传入仍须为正整数。`{}` 可导出全部符合业务准入规则的记录。

成功响应为 Excel 二进制流，`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，`Content-Disposition` 提供 UTF-8 文件名 `空运代理对账列表_时间戳.xlsx`。导出列包含序号、结算状态（未结算/已结算）、客户公司名称及全部应收字段，顺序与上表对应的费用登记台应收模型一致。输入内容以文本写入，避免被当作 Excel 公式执行。

### 错误处理

沿用项目统一错误响应机制，前端按 HTTP 状态码及 `msg` 处理。五个接口均要求有效登录用户。

| HTTP 状态 | 场景 |
| --- | --- |
| 400 | 航班开始日期晚于结束日期；导出无符合条件数据 |
| 401/403 | 缺少/无效登录凭证、用户不可用等认证失败 |
| 404 | 结算/取消/批量中单据不存在、来源不匹配或尚未通过业务审核 |
| 409 | 结算保存发生唯一键等完整性冲突，刷新后重试 |
| 422 | 日期格式、来源枚举、ID、状态或分页参数不合法，或批量/选中项超过 1000 |

## 结算单列表查询

`GET /api/v1/settlements` 恢复按航司录单时间范围筛选，使用 `airline_record_time_start` 和 `airline_record_time_end`（`YYYY-MM-DD`）作为起止日期，筛选结算单 `form_data.airline_record_time`，包含边界日期。两个参数可单独传入，也可组合传入；未传入时不限制录单日期。`flight_date_start`、`flight_date_end` 不作为本接口的筛选参数。

请求示例：`GET /api/v1/settlements?airline_record_time_start=2026-10-21&airline_record_time_end=2026-10-21`。

其他筛选、分页、作废成功记录排除规则及响应结构保持不变。响应中的 `airline_record_time` 仍优先取关联运单的 `booking_date`，缺失时取 `form_data.airline_record_time`；日期筛选沿用原逻辑，仅使用后者。

## 深航 KingGo 航班表同步与时间来源

深航业务优先从 `shenzhen_air_flight_info` 查询计飞、实飞时间；南航继续使用原携程客户端。
无需创建 RPA 任务。新增表在应用现有 `Base.metadata.create_all` 启动过程中自动创建，
也可手动执行 `sql/migration_create_shenzhen_air_flight_info.sql`。

上游接口：`POST /flight_info/index/92?flag=true`。每页均重新从有效 HAR 提取 Cookie，
按当前 URL 及实际 POST 请求体生成 `oOr6SIhu`，不使用示例 Cookie 或固定签名。
请求体包含 `flightNoQ`、`carrierCodeQ`、`depCodeQ`、`destCodeQ`、`planeCodeQ`、`planeTypeQ`
（均为空）、`flightDateStart/flightDateEnd`（同一查询日期）、`flightStatusStrQ=1`、`areaTypeQ=D`，
并发送 `pageNum=1..N`、`numPerPage=200`。历史日期补充 `historyCheck=true`。
按返回的 `totalCount/numPerPage` 获取完整分页；登录页、列结构变化、HTTP失败、重复页、
日期不匹配或条数不完整都不提交本轮数据。完整抓取最多100页、总等待最多120秒。

主表保存日期、航班号、起降站、上游ID、区域、起飞/到达/实际起飞/实际到达时间、飞机号、
机型、宽窄、状态、总重量/体积、控制重量/体积、开放重量及货机标识。
唯一键为 `(flight_date, flight_number, origin, destination)`，防止同一航班号跨日期或航段串数据。
新增航段插入，已有航段逐字段比较，仅变化时 UPDATE 并修改 `updated_at`；不会全表删除重建。
空的实际起飞保留为缺失，不填造时间；本轮未返回的历史记录保留。

启动时先尝试同步北京时间当天的数据，随后启动消费者和独立后台同步，不受 `RPA_QUEUE_ENABLED` 限制。
启动同步失败不会阻止应用启动，后台按重试间隔重试；消费者查询明天或历史日期时也会按需同步该日。
同一进程跨线程共享同步互斥及日期级限频，避免每个运单重复下载全部航班；多进程通过数据库唯一键防重复。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SHENZHEN_AIR_FLIGHT_INFO_SYNC_ENABLED` | `True` | 启用KingGo同步及深航时间优先查询；关闭后仅按兜底开关调用携程 |
| `SHENZHEN_AIR_FLIGHT_INFO_SYNC_INTERVAL_SECONDS` | `1800` | 正常同步间隔，60—86400秒 |
| `SHENZHEN_AIR_FLIGHT_INFO_SYNC_RETRY_SECONDS` | `60` | 失败重试间隔，10—3600秒 |
| `SHENZHEN_AIR_CTRIP_FALLBACK_ENABLED` | `True` | 深航所需时间缺失时允许调用原携程；不改变南航，也不强制开启代理 |

内部时间约定：`planned_time` 为计飞/计划起飞，优先取 KingGo“起飞”；`actual_time` 为实飞，
优先取“实际起飞”；`ready_time` 为预飞/预计起飞，仅携程能补齐，KingGo不提供该字段。
查询按航班号、日期和起降站匹配，中文站名只能在匹配唯一航段时命中。
KingGo只有HHMM：按航班日期组合北京时间，实飞取距离计飞最近的一天；
实飞钟点比计飞早超过12小时按次日处理，晚超过12小时按前一日处理（兼容凌晨航班提前起飞）。
超过12小时的延误与跨日提前无法仅凭HHMM准确区分。无效时间留空。携程仅补缺失值，不覆盖已有KingGo时间；
携程兜底异常也保留已取得的KingGo时间。

深航计飞集装器的定时处理使用计飞时间减105分钟；出港/装机预警继续使用原提前量。
展示预飞时仅使用真实 `ready_time`，缺失展示 `/`；出港状态判断无预飞时可用计飞作为触发基准，
但不把该值写成预飞。实飞补偿继续保留原延迟、次数和重试策略。关闭携程兜底后，
依赖缺失时间的处理等待后续同步；已有正常数据照常使用。现有深航RPA和直连处理均走此来源规则。

## 深航订舱-过机-装机数据获取（KingGo直连下载）

定时管理器 TransitLoadingManager 默认通过 KingGo 接口 POST /awb/query/export/119
下载 AwbQueryExport.xlsx（按北京时间当天过滤操作日期与航班日期）到
RPA_GENERATED_FILES_DIR，文件名格式为 AwbQueryExport_YYYYMMDD_HHMMSS.xlsx。
后续文件扫描与解析入库逻辑不变。每次请求都会从 HAR 文件重新提取 Cookie 和
签名（oOr6SIhu 由签名生成），下载失败仅记录日志，本轮不再下发 RPA 任务。

切换回原 RPA 下载流程：

```env
SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE=rpa
```

该配置默认 direct；rpa 模式完整保留原有定时下发 RPA 下载任务的逻辑。

## 深航订舱-批复数据获取

配置 `SHENZHEN_AIR_APPROVAL_EXECUTION_MODE=direct` 时，调度器按北京时间分别下载今天和明天
的普通机型及宽体机批复文件到 `RPA_GENERATED_FILES_DIR`。普通机型请求 KingGo
`POST /agent_order_look/export/125`，宽体机请求 `POST /agent_order_look_wide/export/858`；
均固定发送 `depCode=SZX`、`agentCode=SZXFDH`、`ss=1`、`nn=0` 和对应的 `flightDate`，
普通机型额外发送 `orderType=1`（宽体接口参数不含此字段）。每次请求从 HAR 重新提取
Cookie 和 `oOr6SIhu` 签名。文件名分别以 `订舱查询导出`、`宽体机订舱查询与修改导出` 开头，
由现有批复 Excel 扫描器按原解析逻辑分别解析入库。

直连模式下普通机型和宽体机均不创建对应的 `rpa_tasks` 任务；网络、鉴权或文件格式失败时
不标记任何数据，下一轮定时调度自动重试。原 RPA 模式完整保留，切换为 `rpa` 后两种机型
均按原流程调度 `SHENZHEN_AIR_APPROVAL_DATA` 和 `SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY`。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SHENZHEN_AIR_APPROVAL_EXECUTION_MODE` | `direct` | 普通及宽体批复使用 KingGo 直连或原 RPA |
| `RPA_SHENZHEN_AIR_APPROVAL_INTERVAL_SECONDS` | `900` | 直连/RPA 调度间隔（秒） |
| `SHENZHEN_AIR_KINGGO_HAR_PATH` | `generated_files/www.kinggo.com.har` | HAR 签名与 Cookie 来源 |

下载文件写入既有 `RPA_GENERATED_FILES_DIR`，不新增业务表。

## 深航订舱-计飞时间-集装器数据获取

文件扫描器从 `AwbQueryExport*.xlsx` 读取单号、航程和航班日期后，优先以 KingGo 计飞
（缺失时按配置使用携程计飞，最后使用携程预飞）减105分钟调度处理。直连模式由定时管理器直接调用 KingGo GET
`/awb/query/getaway` 获取 HTML 表格，不创建 `rpa_tasks` 记录；RPA 执行器和队列消费
逻辑完整保留，可通过配置切换：

```env
SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE=direct
```

直连请求每次从 HAR 重新提取 Cookie 和签名，生成当前毫秒时间戳 `_` 及新的
`oOr6SIhu`，并发送 `awbPrefix=479`、Excel 单号、Excel 航程、Excel 航班日期、
`nti=119` 和 `historyCheck=false`。返回页面只解析 `#getWay` 下九列表格数据，
跳过表头和“合计”行，字段按原 RPA 映射写入
`shenzhen_air_billing_time_containers`，其中 `planned_time` 按上述来源规则补充计飞时间。空数据、登录页、
网络或上游错误不标记 Excel 明细完成，由下一次定时扫描重试；成功后标记 Excel 明细完成。
直连失败不会调用 RPA。设置为 `rpa` 后才创建
`SHENZHEN_AIR_BILLING_TIME_CONTAINER` 队列任务，并沿用原队列、机器人权限、轮询和消费逻辑。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE` | `direct` | `direct` 使用 KingGo GET 接口；`rpa` 使用原 RPA 流程 |
| `RPA_DEPARTURE_TASK_RETRY_INTERVAL_SECONDS` | 由现有配置决定 | 仅 RPA 模式的任务重试间隔；直连模式在下一次定时扫描重试 |
| `SHENZHEN_AIR_KINGGO_HAR_PATH` | `generated_files/www.kinggo.com.har` | 每次请求提取签名和 Cookie 的 HAR |
| `SHENZHEN_AIR_KINGGO_API_ORIGIN` | `https://www.kinggo.com` | KingGo 地址；本地模拟可覆盖 |
| `SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS` | `30` | 直连请求超时秒数 |

上游返回的九列依次映射为 `sequence`、`flight_number`、`flight_date`、
`billing_time`、`origin`、`destination`、`quantity`、`weight`、`container`。
直连模式不新增任务表，也不改变 Excel 解析入库流程；RPA 模式继续使用现有 `rpa_tasks`。
切换到直连后，管理器会清理遗留的待执行计飞集装器 RPA 任务；正在执行的旧任务会先完成，
避免与直连请求并发处理同一条 Excel 明细。
直连管理器不依赖 `RPA_QUEUE_ENABLED`，但 Excel 来源仍须配置为直连过机装机下载，或由其他流程提供文件。

## 单号库总览

`GET /api/v1/waybill-stocks/overview`

查询各航司单号库的领单及使用情况。调用方需要拥有 `bill` 权限。

查询参数：

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `airline_name` | string | 否 | 航司名称精确筛选；不传时返回全部单号库 |

成功响应中的 `data` 为数组，每个元素包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `stock_id` | string | 单号库 ID |
| `airline_name` | string | 航司名称 |
| `last_claim_date` | string \| null | 最后领单日期，格式为 `YYYY-MM-DD`；取该单号库全部领单批次中最大的业务领单日期 `claim_date`，无领单批次时为 `null` |
| `total_authorized_count` | integer \| null | 核定单号总数 |
| `claimed_count` | integer | 已领单数量 |
| `claimable_count` | integer | 按现有批次首尾单号容量计算的可领单数量 |
| `unused_count` | integer | 未使用单号数量 |
| `used_count` | integer | 已使用单号数量 |

`last_claim_date` 按业务日期判断，不按批次录入时间判断。补录历史批次不会覆盖一个更晚的领单日期。该字段仅新增返回信息，不改变已有统计字段的含义。

响应示例：

```json
{
  "code": 0,
  "data": [
    {
      "stock_id": "123456789012345678",
      "airline_name": "china_southern_air",
      "last_claim_date": "2026-09-20",
      "total_authorized_count": 1000,
      "claimed_count": 300,
      "claimable_count": 700,
      "unused_count": 180,
      "used_count": 120
    }
  ],
  "msg": "获取单号库总览成功"
}
```

## 开单成功后自动后处理配置

深航和南航分别提供自动制单、自动打单开关。两个阶段可以独立启停：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `RPA_SHENZHEN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED` | 未配置时沿用深航 `AUTO_PRINT` | 深航开单成功后是否自动生成货站制单文件 |
| `RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED` | `True` | 深航开单成功或制单成功后是否自动创建打印任务 |
| `RPA_CHINA_SOUTHERN_AIR_AUTO_DOCUMENT_AFTER_WAYBILL_ENABLED` | 未配置时沿用南航 `AUTO_PRINT` | 南航开单成功后是否自动生成货站制单文件 |
| `RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED` | `True` | 南航开单成功或制单成功后是否自动创建打印任务 |

- 制单开、打单关：正常读取费用、创建结算单并生成货站制单文件，不创建自动打印任务；制单状态正常更新，打印状态保持未执行。
- 制单关、打单开：正常读取费用并创建结算单，跳过货站制单文件生成，直接按打印机配置创建航司固定单据等可执行的打印任务；制单状态保持未执行。
- 两者均开：先制单，制单成功后创建打印任务，保持原有完整后处理行为。
- 两者均关：开单或订舱本身仍正常完成并保留成功状态及已取得的运单号；跳过费用读取、结算单创建、订舱开单后的运单记录同步、制单、文件生成和自动打印，相关执行状态保持未执行。用于获取核心结果的队列仍会正常清理。
- 为兼容旧部署，新增的 `AUTO_DOCUMENT` 未配置时沿用对应航司的 `AUTO_PRINT` 值；需要独立控制时必须显式配置两个值。
- 单纯的南航订舱成功链路目前只保存订舱状态和运单号，本身没有结算、制单或打印后处理；后续从订舱发起开单时，上述南航开关控制对应阶段。
- 深航、南航的制单及打单开关相互独立，修改 `.env` 后需要重启应用服务生效。
- `POST /api/v1/waybills/{waybill_id}/print-document` 手动打印接口不受影响。

## RPA 开单任务优先级

`rpa_tasks` 按 `priority` 降序、创建时间升序取待执行任务。为减少抓取类任务对用户点击开单的等待，以下任务类型使用专用优先级配置 `RPA_QUEUE_WAYBILL_PRIORITY`：

- `SHENZHEN_AIR_WAYBILL_EXECUTE`：深航开单
- `CHINA_SOUTHERN_AIR_WAYBILL_EXECUTE`：南航新增运单（兼容历史 RPA 开单链路）
- `CHINA_SOUTHERN_AIR_DIRECT_INVOICE`：南航直接开单
- `CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA`：南航修改数据后开单

配置项默认值为 `10`，高于普通任务默认优先级 `1`、保持登录任务优先级 `3` 和重启任务优先级 `4`。南航订舱、取消、出港跟踪、审批、抓取等其他任务优先级不受影响。优先级只影响尚未开始执行的任务，已经处于 `running` 的任务不会被中断；修改 `.env` 后需要重启服务生效。

## 深航获取 HAR 周期任务

新增 RPA 任务类型 `SHENZHEN_AIR_GET_HAR`（中文名称“深航获取har”），流程定义如下：

| 字段 | 值 |
| --- | --- |
| `process_detail_uuid` | `9d55ee2fbd0460f44c1dd1c47f5f7e32` |
| `version` | `0.0.2` |
| `process_param` | `{"system_url":"https://www.kinggo.com/main"}` |

部署时执行 `sql/migration_insert_shenzhen_air_get_har.sql` 写入或校准 `task_processes`；应用启动也会补齐缺失记录，但不会覆盖已有流程配置。之后需要通过机器人管理接口为目标机器人分配 `SHENZHEN_AIR_GET_HAR` 权限，保存配置时系统会自动创建该机器人的 RPA Job。`GET /api/v1/robots/task-types` 会返回这一新任务类型。

当 `RPA_QUEUE_ENABLED=True` 时，服务启动会立即为每台拥有该权限的启用机器人尝试创建一次任务，之后按以下配置循环调度：

| 配置项 | 默认值 | 范围 | 说明 |
| --- | --- | --- | --- |
| `RPA_SHENZHEN_AIR_GET_HAR_INTERVAL_SECONDS` | `1800` | `1-86400` 秒 | 同一机器人两轮调度的等待间隔；修改后需重启服务 |

调度器会跳过已经存在 pending/running 同类任务的机器人，避免任务堆积。该流程不使用 RPA 数据队列；RPA Job 成功结束后任务即完成，HAR 文件的实际保存位置由 RPA 流程自身配置决定。

## 深航 KingGo 直连接口开单

`POST /api/v1/waybills/{waybill_id}/execute` 默认通过 KingGo HTTP 接口创建深航运单；原有 RPA 开单实现和作废流程保留。设置 `SHENZHEN_AIR_WAYBILL_EXECUTION_MODE=rpa` 可切回原 RPA 开单任务队列。调用权限与既有运单操作权限一致。

直连模式校验运单表单、业务默认值、HAR路径和账号配置后创建独立任务表 `shenzhen_air_direct_waybill_tasks`，保存本次表单和解析后的参数快照，同时将运单状态置为 `1`。任务不进入 `rpa_tasks`，不会被 RPA Worker 领取。接口保持异步入队后立即返回，响应保留既有运单字段及 `task_id`，新增 `execution_mode=direct`、`direct_task_status`、`direct_task_error`。`GET /api/v1/rpa-tasks/{task_id}` 可查询任务状态，直连任务额外返回 `execution_mode=direct`、`stage`（`preparing/submitting/confirmed`）、`candidate_waybill_number`（提交前保存的完整候选单号，未提交时为 null）。状态为 `pending/running/success/failed/unknown`；列表和统计接口仍仅统计RPA任务。开单成功后更新运单号、航司状态和开单时间，并复用现有深航开单后处理开关创建结算单、制单和打印任务；两个自动化开关均关闭时不创建结算单或后续任务。

调用前必须在运行服务的文件系统配置有效 KingGo HAR，默认路径 `generated_files/www.kinggo.com.har`。Docker 部署中该目录挂载到 `/app/generated_files`。每一次 KingGo HTTP 请求都会重新读取 HAR、离线执行 `/main` 保护脚本提取配置和 Cookie，并针对当前实际请求 URL 重新生成 `oOr6SIhu`；不会缓存签名配置或 Cookie。`SHENZHEN_AIR_KINGGO_BROWSER` 控制提取浏览器；Linux/Docker 建议使用 `chromium`。HAR 不含可用 Cookie、HAR 无效或签名生成失败时，该次请求不会发给 KingGo。

接口依次为：`get_awb_no` 获取 `479` 前缀后的八位单号，按航线/日期/货运代码查询运单信息，查询航班并精确匹配航班号/航线/日期及起飞时间，查询费用，调用 `check_awb` 校验，最后调用 `submit_awb` 提交。字段从 `form_data.flight_info`、`shipper_consignee_info`、`cargo_info` 映射。代理身份、操作员、提货电话、收货地址代码和付款方式从环境变量读取，账号字段必须按真实账号填写。与提供的检查/提交表单一致，舱位默认为 `F/F舱`，`oldCabinType` 使用运单信息响应的 `cabinType`；固定舱位代码和名称必须同时设置；两者均置空时使用运单信息返回的舱位。

上游调用契约（路径相对于 `https://www.kinggo.com`，每次独立附加新签名和Cookie）：

| 顺序 | 方法及路径 | 输入与成功结果 |
| --- | --- | --- |
| 1 | `GET /awb/inland/get_awb_no` | 查询参数 `inlandAwbType=0`、`awbPrefix=479`、当前毫秒时间戳 `_`；要求 `retCode=100` 且 `result` 为8位数字 |
| 2 | `POST /awb/inland/get_bill_info_by_code` | 航线、日期、航班、表单货运代码、`awbType=0`、`awbPrefix=479`、空 `transCity`；读取 `retCode=100` 的 `result` 元数据 |
| 3 | `POST /awb/inland/get_flight_no` | `depCode/destCode/flightDate`；响应为数组，要求唯一匹配航班，读取 `takeoffTime/carrierCode` |
| 4 | `POST /awb/inland/computational_costs?nti=90` | 航线、日期、航班、计费重量，元数据 `awbType/billCode/feeModel`，配置 `agentType`，`insuranceValue=0`，空 `custNo/transCity`；响应为费用对象 |
| 5 | `POST /awb/inland/check_awb?nti=90` | 完整开单表单；仅 `retCode=100` 允许进入提交阶段 |
| 6 | `POST /awb/inland/submit_awb?nti=90` | 与检查相同的完整表单、独立生成的新签名；要求 `retCode=100`、`result.awbNo` 等于候选单号、`result.awbId` 非空 |

检查及提交的主要映射：

| KingGo字段 | 来源 |
| --- | --- |
| `awbPrefix/awbNo` | 固定 `479` / 第1步单号；本地保存为 `479-八位单号` |
| `depCode/destCode/flightDate/flightNo/transDate` | `flight_info.origin_station/destination/flight_date/flight_number/flight_date`；始发站为空时使用业务默认值 |
| `shpInfo/cneInfo` | `shipper_consignee_info.shipper_info/consignee_info`；发货人为空时使用业务默认值 |
| `pieces/weight/chargeWeight` | `cargo_info.quantity/weight/chargeable_weight`；必须为正数，件数必须为整数 |
| `aliasCode/goodsCode/goodsName/packName/transNote` | `cargo_info.freight_code/cargo_code/cargo_name/package/cargo_name`；允许沿用对应业务默认值 |
| `billCode/aug/ldcFlag/feeModel/fastFreightFlag/dealCode/oldCabinType` | 第2步元数据，`oldCabinType` 对应 `cabinType` |
| `takeOffTime/carrierCode` | 第3步匹配航班的 `takeoffTime/carrierCode` |
| `formerRate/aviationRate/formerFee/aviationFee` | 第4步 `aviationRate/aviationRate/aviationFee/aviationFee` |
| 保险、燃油、管理、派送、地面、延误、杂费的费率及金额、`otherTotalFee/depOtherFee` | 第4步同名字段，保留合法零值；缺少必要费用字段时中止 |
| `totalFee` | 使用十进制相加：`aviationFee + otherTotalFee` |
| `operDate` | 中国时区的实际操作日期 |
| 账号身份字段、舱位、付款方式 | 下表环境配置；其他空值、固定字段按提供的开单表单设置，`tlicellCellinfos=[]` |

直连入队响应新增字段示例（其余既有运单字段仍返回；此时尚未开单成功）：

```json
{"execution_mode":"direct","task_id":"369409067778707456","airline_record_status":"1","direct_task_status":"pending","direct_task_error":null}
```

任务详情的 `result` 成功时包含 `waybill_number`、`awb_id`、`aviation_rate`、`aviation_fee`、`delivery_fee`；费用值保留上游的数字或数字字符串类型。失败时读取 `error_message`；`unknown` 必须结合 `candidate_waybill_number` 人工核查。任务ID、运单ID均以字符串返回。

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SHENZHEN_AIR_WAYBILL_EXECUTION_MODE` | `direct` | `direct` 使用 KingGo 接口；`rpa` 使用原 RPA 流程 |
| `SHENZHEN_AIR_DIRECT_WAYBILL_QUEUE_ENABLED` | `True` | 是否启动独立持久化直连 Worker |
| `SHENZHEN_AIR_DIRECT_WAYBILL_WORKER_COUNT` | `1` | Worker 数量；共享账号由数据库互斥串行领取开单任务 |
| `SHENZHEN_AIR_DIRECT_WAYBILL_POLL_INTERVAL` | `2` | 空队列轮询秒数 |
| `SHENZHEN_AIR_KINGGO_HAR_PATH` | `generated_files/www.kinggo.com.har` | HAR 文件路径 |
| `SHENZHEN_AIR_KINGGO_API_ORIGIN` | `https://www.kinggo.com` | KingGo API 传输地址；仅本地模拟测试可覆盖 |
| `SHENZHEN_AIR_KINGGO_BROWSER` | `auto` | `auto`、`msedge` 或 `chromium` |
| `SHENZHEN_AIR_KINGGO_EXECUTABLE_PATH` | 空 | 可选浏览器可执行文件路径 |
| `SHENZHEN_AIR_DIRECT_WAYBILL_HTTP_TIMEOUT_SECONDS` | `30` | 每个上游请求超时秒数 |
| `SHENZHEN_AIR_KINGGO_AGENT_TYPE` | `1` | KingGo 代理类型 |
| `SHENZHEN_AIR_KINGGO_AGENT_NAME/ID/CODE` | 空 | 当前账号代理名称、ID 和编码 |
| `SHENZHEN_AIR_KINGGO_OPER_ID` | 空 | KingGo 操作员 ID |
| `SHENZHEN_AIR_KINGGO_PICK_TEL_NO` | 空 | 提货联系电话 |
| `SHENZHEN_AIR_KINGGO_CNE_ADDR` | 空 | KingGo 收货地址代码 |
| `SHENZHEN_AIR_KINGGO_CABIN_TYPE(_NAME)` | `F` / `F舱` | 固定舱位代码和名称；两者均置空时使用运单信息响应 |
| `SHENZHEN_AIR_KINGGO_PAY_TYPE` | `1` | 付款方式 |

每次提取时将实际方法、URL和完整编码表单交给HAR原脚本，随后将原脚本产生的 `requestDigest` 传入 `generate` 生成本次新签名，保证提取和实际发送使用同一份请求体。POST 使用 `application/x-www-form-urlencoded`。签名/Cookie提取失败不降级发送。HAR含有会话Cookie，不得提交代码仓库、写入日志或API响应。

## 深航运单作废

`POST /api/v1/waybills/{waybill_id}/void` 对深航默认使用 KingGo 直连接口；南航行为保持原有 RPA 队列不变。设置 `SHENZHEN_AIR_WAYBILL_VOID_EXECUTION_MODE=rpa` 可将深航切回原 RPA 作废流程。直连模式在本次请求内完成查询和删除，不创建新的任务表。

直连流程如下：

1. 从本地 `waybill_number` 校验并取得 `479-` 后的8位数字。
2. `POST /awb/query/index/119?flag=true`，以 `application/x-www-form-urlencoded` 发送查询表单（`awbPrefixQ=479`、`awbNoQ=8位单号`，其余筛选条件使用全量安全范围）。
3. 从返回 HTML 中仅匹配 `awbPrefix=479`、`awbNo=8位单号` 的唯一表格行，并校验该行的 `rel` 与 hidden `awbId` 一致，取得 KingGo 的真实 `awbId`；不会使用本地运单 ID。
4. 使用本次查询得到的 `awbId` 调用 `POST /awb/query/delete_awb_info/119?awbId=...`，请求体为空。
5. 只有 HTTP 2xx 且 JSON 返回 `statusCode="200"`、`message="成功删除"` 时才将本地运单和关联结算单置为作废成功（`waybill_void_status="3"`）。

查询和删除每次都从 HAR 离线提取 Cookie，并针对精确的方法、URL 和请求体重新生成 `oOr6SIhu`；不会复用旧签名或 Cookie。HAR、Cookie、签名和上游 HTML 不会写入日志或接口响应。查询不到、匹配不唯一或业务失败时标记作废失败（`"2"`）；删除请求已发出但结果不确定时保留作废中（`"1"`），阻止盲目重试，需人工核查 KingGo 后处理。成功响应在原有运单字段基础上增加：

| 字段 | 说明 |
| --- | --- |
| `execution_mode` | `direct` |
| `direct_void_status` | `success` |
| `kinggo_awb_id` | KingGo 查询到的上游运单 ID |
| `task_id` | 直连同步执行时为 `null`；RPA 模式仍返回原 RPA 任务 ID |

配置项：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `SHENZHEN_AIR_WAYBILL_VOID_EXECUTION_MODE` | `direct` | `direct` 使用 KingGo 查询/删除接口；`rpa` 使用原深航 RPA 作废流程 |

该配置仅影响深航作废，不影响深航开单配置 `SHENZHEN_AIR_WAYBILL_EXECUTION_MODE`，修改 `.env` 后需重启服务。

提交请求发出前失败会标记 `failed`，可重新执行。提交发出前先独立提交数据库事务，将 `stage=submitting` 和候选单号持久化；数据库写入失败则不发送提交请求。之后的网络异常、非2xx、业务拒绝、无效响应、返回单号不一致或本地结果落库异常均保守标记 `unknown`，禁止自动重试或自动降级RPA。切换到RPA模式也不能绕过 `pending/running/unknown` 直连任务。`PUT /api/v1/waybills/{id}` 修改运单时同样阻止这些任务关联的运单被修改。单任务上限20分钟，每分钟检查超过30分钟的遗留running任务；未跨过提交边界的任务置failed，已跨过的任务置unknown。人工必须先按候选单号核查KingGo并确认/修复本地运单、任务状态；未确认上游结果前不能将unknown直接改为failed重试。

确认成功时校验返回的八位运单号与候选号一致且包含 `awbId`，原子持久化运单号和任务成功状态。后续结算/制单/打印异常不会导致再次开单；后处理抛出异常时在任务 `result.post_processing_error` 中提示人工检查。直连模式不自动重发任何上游请求。

共享 KingGo 账号的领取过程通过 `shenzhen_air_direct_waybill_queue_lock` 单行锁协调：同一时刻只允许一个直连开单任务处于 running，多线程、多进程使用同一数据库时也遵循此限制，避免获取候选单号后尚未提交就被另一任务重复领取。互斥行仅在领取事务中加锁，HAR提取和HTTP请求期间不持有数据库连接。候选单号是否预占尚未得到上游契约确认，因此采用串行策略。

数据库部署：执行 `sql/migration_create_shenzhen_air_direct_waybill_tasks.sql`（幂等创建任务表、领取互斥表并初始化互斥行）；应用启动的模型建表逻辑也会创建这两张新表，首次领取时自动补齐互斥行。现有RPA表和流程不变。启动Worker的主机需安装项目依赖及Playwright Chromium（`python -m playwright install --with-deps chromium`）。本地验证使用提供的 `postman/simulations/shenzhen-waybill.sim.yaml`，依据本次提供的六个KingGo接口样例构造，不含真实Cookie或签名。

本地回归方式（PowerShell，模拟服务启动后另开终端执行测试）：

```powershell
postman simulation run postman/simulations/shenzhen-waybill.sim.yaml --port 4900 --output ndjson --no-history
$env:KINGGO_SIM_ORIGIN='http://127.0.0.1:4900/kinggo'
python -m unittest tests.test_shenzhen_air_direct_waybill -v
```

模拟测试使用虚拟签名替代HAR提取，其余业务映射、HTTP编码、上游错误处理均运行实际客户端。真实HAR离线提取验证与模拟HTTP验证分别进行，不能视为真实KingGo账号开单成功的证明。

## 空运财务审核

`GET /api/v1/financial-audit/air` 返回的列表项包含财务审核人字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `financial_auditor_name` | string | 财务审核人名称，来源为审核账号的用户姓名（`users.name`）；未审核或没有审核人时返回空字符串 |
| `agent_name` | string | 代理名称；仅来源为托运书的同行空运单据返回 `consignment_notes.company_name`，深航/南航 RPA 数据和手动新增财务单据返回空字符串 |

该字段对应费用登记台“空运单据审核”详情中的“审核人”，适用于深航、南航、同行空运和手动新增空运单据。

应付信息中的 `payable.agent_name` 遵循同一来源规则：仅关联托运书的同行空运单据返回代理公司名称，其他来源返回 `null`。深航/南航 RPA 页面中的“代理人”或“代理人编码”不属于本系统的业务代理名称，不会映射到该字段。`POST /api/v1/financial-audit/air/audit` 暂存或提交时，后端会按来源重新校准该字段，避免请求值或历史暂存值覆盖托运书代理公司；`POST /api/v1/financial-audit/air` 手动新增的财务单据不关联托运书，因此忽略传入的 `payable.agent_name` 并保存为 `null`。

`POST /api/v1/financial-audit/air/audit?action=save|submit` 的 `payable` 和 `receivable` 请求模型中，原本定义为字符串的件数、重量、费率和费用字段同时兼容 JSON number 与 string。后端接收 number 后会统一规范化为字符串再保存；`null` 和已有字符串保持不变，布尔值、数组和对象仍会触发参数校验错误。操作类型通过 query 参数 `action` 传递，请求体中的同名字段不会作为操作类型使用。请求字段应使用后端定义的名称（例如违规罚款使用 `penalty_fee`）；未声明字段不会进入保存数据。

## 托运书

`POST /api/v1/consignment-notes` 和 `PUT /api/v1/consignment-notes/{note_id}` 的 `form_data` 为动态 JSON。汽运（`transport_type="1"`）支持以下收件信息字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `form_data.consignee_info` | string | 收件人 |
| `form_data.contact_phone` | string | 联系电话 |

这两个字段随 `form_data` 原样保存，并在托运书列表和详情接口中原样返回；历史数据未填写时不补写。生成汽运托运书 PDF 时也会展示这两个字段。

## 南航货物类型数据字典自动同步

该功能为后台内部同步任务，不新增前端调用接口。

- 应用服务每次启动后立即调用南航货物类型接口；同步成功后默认每 `43200` 秒（12小时）再次执行。
- 查询参数固定为 `origin=SZX`、`dest=TAO`、`channel=B`、`directTransfer=D`、`customerno=SZXFED`。
- 请求头 `x-customs-user` 使用 `nanhang_token` 表中按 `updated_at`、`id` 倒序取得的最新非空 token；`x-customs-userid` 为 `SZXFED`。
- 南航成功响应中的全部 `result[].shipmentTypeName` 写入字典选项 `label`，`result[].shipmentType` 写入 `value`，覆盖的字典类型固定为 `nanfang_air_cargo_type`。不同名称允许使用相同的 `shipmentType`。
- 只有响应成功、列表非空且每一项名称和代码完整时才执行覆盖。覆盖过程在单个数据库事务内完成；token 缺失、网络/业务异常、空列表或异常数据均不会清空原字典，并默认在5分钟后重试。
- token 错误日志明确区分来源：本地没有可用记录或记录清洗后为空时提示`nanhang_token 中没有可用Token`；已发送 token 但南航返回“获取Token为空”时提示`南航接口拒绝Token：获取Token为空，可能已过期或失效`。
- 服务日志会明确输出调度器启动并立即执行、每次同步开始、同步成功及下次执行时间、同步失败及下次重试时间；这些 `INFO/WARNING` 日志使用 Uvicorn 日志器，可直接在后台控制台或容器日志中查看。
- 同步不依赖 `RPA_QUEUE_ENABLED`，关闭 RPA 队列时仍会运行。

环境变量配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_ENABLED` | `True` | 是否启用自动同步 |
| `CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_INTERVAL_SECONDS` | `43200` | 成功同步后的执行间隔（秒），允许 `60-604800` |
| `CHINA_SOUTHERN_AIR_CARGO_TYPE_SYNC_RETRY_SECONDS` | `300` | 同步失败后的重试间隔（秒），允许 `10-3600` |

## 南航最近导入批次单号可用性扫描

该功能是后台内部校准任务，不新增前端接口，默认关闭。开启后服务启动会立即扫描一次，后续按配置周期重复执行。

- 扫描范围固定为南航单号库最近导入的一个批次，不扫描全部历史单号。最近批次按 `claim_date`、`created_at`、批次 `id` 依次倒序确定；新增批次后，下一轮会自动切换到新批次。
- 每个单号使用 `waybill_stock_items.number_suffix` 作为南航 `getOrderList` 的 `awbNo`，并自动分页读取全部结果；请求头 `x-customs-user` 使用 `nanhang_token` 表中的最新非空 Token。
- 南航返回空列表，或全部列表项的 `statusCN` 都严格等于`已取消`时，单号校准为未使用；只要任一项不是`已取消`（包括状态缺失），就校准为已使用。
- 状态为未使用时写入 `usage_status="0"`、清空 `usage_date`；状态为已使用时写入 `usage_status="1"`，缺少 `usage_date` 时补当天日期。扫描也会解除系统因“南航提示运单号已被使用”或结果不确定而自动设置的隔离，但不会解除人工设置的失效原因或异常状态。
- 若单号正被本系统处于执行中的南航订舱/开单占用，或仍在最近预占保护期内，即使南航暂时返回空列表也不会回流，避免接口数据延迟造成重复分配。
- 单条网络、响应或业务异常只记录日志并保留该单号原状态，不中断本批次其余单号；Token 缺失等整轮前置错误按重试间隔再次尝试。
- 扫描采用单线程串行请求，不开启多进程或并发扫描；相邻请求之间强制等待配置的单号间隔，以降低南航风控风险。

环境变量配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_ENABLED` | `False` | 是否启用最近导入批次扫描 |
| `CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_ITEM_INTERVAL_SECONDS` | `30` | 相邻两个单号请求间隔（秒），允许 `1-3600` |
| `CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_CYCLE_INTERVAL_SECONDS` | `3600` | 一轮完成后的等待时间（秒），允许 `60-604800` |
| `CHINA_SOUTHERN_AIR_WAYBILL_STOCK_SCAN_RETRY_SECONDS` | `300` | 整轮前置失败后的重试时间（秒），允许 `10-3600` |
| `CHINA_SOUTHERN_AIR_WAYBILL_STOCK_RELEASE_GRACE_SECONDS` | `600` | 本地刚预占单号后的禁止回流保护期（秒），允许 `0-86400` |

## 南航订舱

### 南航订舱执行模式

通过 `CHINA_SOUTHERN_AIR_BOOKING_EXECUTION_MODE` 选择 `/api/v1/bookings/execute` 的执行方式：

| 配置值 | 行为 |
| --- | --- |
| `direct`（默认） | 写入南航专用直连任务表，由 `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_WORKER_COUNT` 个 Worker 并行消费；接口等待任务完成后返回南航实际成功/失败结果。 |
| `rpa` | 写入通用 `rpa_tasks`，由 RPA Worker 消费；接口返回成功仅表示成功入队。要求 `RPA_QUEUE_ENABLED=True`。 |

修改配置后需重启后端服务生效。

### 南航订舱接口直连执行

`POST /api/v1/bookings/execute` 在 `CHINA_SOUTHERN_AIR_BOOKING_EXECUTION_MODE=direct` 时为南航接口直连执行接口。请求会为每条订舱创建专用直连任务，由 `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_WORKER_COUNT` 个 Worker 并行消费；接口等待这些任务进入成功或失败终态后再返回，不把“写入任务队列”当作订舱成功。Worker 会依次调用南航航班、运价舱位（`queryB2eFlightPrice`）、费用、计费和 `createOrder` 接口。

请求体保持不变：

```json
{"booking_ids": ["订舱ID1", "订舱ID2"]}
```

成功响应中的 `data.items[].success` 表示对应直连任务已完成且南航订舱成功；`success_count` 和 `failed_count` 分别表示实际订舱成功数和失败数。`task_id`、`batch_id` 可用于定位本次直连任务和批次。

响应示例：

```json
{
  "code": 0,
  "data": {
    "items": [
      {"booking_id": "1001", "task_id": "任务ID", "success": true, "error_message": null}
    ],
    "total": 1,
    "success_count": 1,
    "failed_count": 0
  },
  "msg": "批量执行完成，成功: 1，失败: 0"
}
```

`success=true` 表示南航接口直连订舱已经成功；当 `queryB2eFlightPrice` 返回无效响应、`result.charge` 为空、费用/计费失败或 `createOrder` 失败时，Worker 会将任务标记为失败，接口等待到该终态后返回 `success=false`、`failed_count` 加一，并在 `error_message`/`error_details` 中返回原因。失败发生在单号预占前时不会消耗单号；下单结果不确定时会按单号保护逻辑处理。

当 `CHINA_SOUTHERN_AIR_BOOKING_EXECUTION_MODE=rpa` 时，同一个 `/api/v1/bookings/execute` 会创建通用 `rpa_tasks` 任务并立即返回；此时 `success=true`、`success_count` 仅表示成功入队，不代表南航订舱已经成功，最终结果通过 `/api/v1/rpa-tasks/{task_id}` 查询。直连订舱使用独立的 `china_southern_air_booking_tasks` 表和 Worker，不与通用 RPA 队列混用。

历史异步直连任务仍可通过以下接口查询，但这些接口不参与当前 `/bookings/execute` 的同步响应：

- `GET /api/v1/china-southern-air-booking-tasks/{task_id}`：查询单条历史任务。
- `GET /api/v1/china-southern-air-booking-tasks?batch_id={batch_id}`：按历史批次查询任务。

南航直连订舱 Worker 配置：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_QUEUE_ENABLED` | `True` | 是否启用南航直连订舱 Worker；关闭后 `direct` 模式不可执行。切换到 `rpa` 后仍会消费切换前遗留的直连任务 |
| `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_WORKER_COUNT` | `2` | 并行消费南航直连订舱任务的 Worker 数量 |
| `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_POLL_INTERVAL` | `2` | Worker 无任务时的轮询间隔（秒） |
| `CHINA_SOUTHERN_AIR_DIRECT_BOOKING_EXECUTE_TIMEOUT_SECONDS` | `1800` | 直连接口等待本批任务终态的最长时间（秒）；超时只结束 HTTP 等待，后台任务继续执行，需通过任务接口查询最终结果 |

已有部署需执行 `sql/migration_direct_booking_tasks.sql` 增加任务批次字段；新建数据库会随模型初始化自动创建。

### 下载批量订舱模板

`GET /api/v1/bookings/china-southern-air/template`

返回标准 `.xlsx` 文件。模板约定：

- 数据填写区统一使用文本格式并默认水平、垂直居中，避免航班号、货物代码等标识被 Excel 自动转换。
- 下载时动态读取启用的数据字典 `nanfang_air_cargo_type`，将全部有效 `label` 作为`货物类型`列的单选下拉选项；数据字典同步覆盖后，再次下载即可获得最新选项。选中该列单元格时不显示额外的输入提示浮窗；该动态处理不修改模板其他列、样式、默认值或既有下拉框。
- `特货码（多个用英文逗号隔开）`为可选列：用户只需填写默认码之外的附加特货码；多个使用英文逗号分隔，例如 `GEN,AKA`。执行订舱时后端会查询并自动合并南航默认特货码。
- `出港货邮处理费选项`为可选列，可留空；留空时执行订舱直接透传南航费用查询返回的完整费用列表。
- `超规货`、`无隐含危险品`、`出港货邮处理费选项`均为单选下拉框。

### 后台解析批量订舱 Excel

`POST /api/v1/bookings/china-southern-air/import-excel`

请求类型：`multipart/form-data`

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `file` | file | 是 | 通过模板下载接口获取并填写的标准 `.xlsx` 文件，最大 5 MB |

处理规则：

- 后端逐行解析 Excel，每个有效数据行创建一条未执行订舱记录。
- 全部行校验成功后才统一写库；任一行失败时不创建任何记录。
- 根据 Excel 的 `货物类型`，精确匹配启用的数据字典 `nanfang_air_cargo_type` 的 `label`，把对应 `value` 写入 `form_data.bookings[0].cargo_type_code`。
- `出港货邮处理费选项`写入 `form_data.outbound_cargo_and_mail_handling_fee_options`；该列允许留空。留空时执行订舱不会按名称定位或补勾，直接使用南航费用查询接口返回的完整费用列表。
- 本接口仅创建订舱记录，不直接调用南航；随后调用 `POST /api/v1/bookings/execute` 执行订舱。

成功响应中的每个 `items[].form_data.bookings[0]` 都包含后台补齐后的 `cargo_type_code`。

### 提交订舱信息

`POST /api/v1/bookings`

当 `form_data.airline` 为 `2` 或 `南方航空`，且某个 `form_data.bookings[n].cargo_type_code` 为空时，服务端会根据该项的 `cargo_type`，按启用的数据字典 `nanfang_air_cargo_type` 的 `label -> value` 自动补齐代码。

- 已传入非空 `cargo_type_code` 时保持原值，兼容现有调用方。
- 数据字典不存在、未启用、配置重复、存在空名称/空值，或找不到对应货物类型时，接口返回 `400`，不创建任何记录。
- 服务端补齐字段发生在收到请求之后，因此浏览器开发者工具的 Request Payload 不会出现该字段；应在接口响应或后续列表接口返回的 `form_data.bookings[0].cargo_type_code` 中查看。

### 修改订舱信息

`PUT /api/v1/bookings/{booking_id}`

南航数据的 `cargo_type_code` 缺失时，采用与新增接口一致的字典映射规则自动补齐；已传入非空值时保持原值。

### 批量执行订舱（接口直连）

`POST /api/v1/bookings/execute`

该接口在 `direct` 模式下将南航直连订舱任务提交到专用任务表，并等待多 Worker 完成实际南航调用后返回；在 `rpa` 模式下将任务提交到通用 `rpa_tasks` 后立即返回入队结果。南航返回无效运价响应（例如 `queryB2eFlightPrice` 的 `result.charge` 缺失或为空）时，`direct` 模式会在接口响应中返回失败；`rpa` 模式需待 RPA Worker 执行后查询最终状态。

`form_data.outbound_cargo_and_mail_handling_fee_options` 为可选字段。填写时仍按填写的费用名称定位“出港货邮处理费”明细并完成勾选；未填写、为 `null` 或空字符串时，执行阶段不再定位或修改任何费用组/明细，直接将 `queryServiceCharge` 返回的完整 `extServiceCharges` 列表原样传给后续 `calculateCharge` 和 `createOrder`。

`form_data.bookings[0].booking_volume` 为可选字段，页面提交和后台 Excel 解析均允许不填。已填写时直接作为南航请求的 `volume`；未传、为 `null` 或空字符串时，执行阶段先调用南航 `calculateCWeight`，固定传入 `dimensions=null`、`volume=""`、`channel="B2B"`，并将 `origin_station` 映射为 `depCityCode`、`weight` 映射为 `weight`。接口返回的 `result.volume` 会用于后续 `calculateCharge` 和 `createOrder`，但不回写原始 `form_data`。同一次批量执行中，相同始发站与重量会复用查询结果。查询失败时该条订舱失败，`error_details.stage` 为 `calculate_cweight`，诊断数据不包含 Token、Cookie 或请求头。

最终 `volume` 确定后、预占单号之前，后端调用南航 `queryB2eFlightPrice` 查询当前产品的运价舱位。请求映射为：`flightDep <- origin_station`、`flightDest <- destination`、`flightNo <- flight_number`、`flightDate <- flight_date`、`rateCode/shipmentType <- cargo_type_code`、`shipmentTypeName <- cargo_type`、`weight <- weight`、`volume <- 最终订舱体积`；其余固定为 `channel=B`、`customerCode=SZXFED`、`dimensions=null`、`rateType=SPY`。南航可能同时返回多个产品方案，后端按有效 `product_name`（为空时使用与 `parentProductionName` 相同的业务配置或默认“南航快运”）精确匹配 `result.charge[].parentProductionName`，将该项 `flightPriceCalculateResult.spaceClass` 同时写入 `bookGrade`、`spaceClass`，将 `subSpaceClass` 写入同名字段，并用于后续 `calculateCharge`、`createOrder`。匹配不到产品、舱位为空或南航查询失败时，该条订舱失败且不占用单号；`error_details.stage` 为 `query_b2e_flight_price`，并返回期望产品、可选产品及安全的上下游诊断信息。同一次批量执行中，全部查询维度一致时复用结果。

`form_data.bookings[0].special_cargo_code` 为可选字段，填写内容视为用户附加特货码。执行阶段在预占单号之前调用南航 `queryShipmentSubProductCode`：`dest <- destination`、`origin <- origin_station`、`shipmentType <- cargo_type`、`productName <- product_name`（为空时使用与 `parentProductionName` 一致的业务配置或默认“南航快运”），并固定传入 `channel=B`、`directTransfer=D`、`customerno=SZXFED`。返回的 `result.subCode` 作为默认码，按“默认码在前、用户码在后”进行大小写不敏感去重；例如默认 `XPS`、用户填写 `GEN`，持久化的 `form_data` 会回写为 `XPS,GEN`，发往南航 `orderInfo.orderShipment.spCode` 和 `productionCode` 的值均为 `XPS/GEN`。英文逗号、中文逗号及历史 `/` 分隔数据均兼容；同一次批量执行中，相同始发站、目的站、货物类型和产品名称复用查询结果。查询失败时该条订舱失败且不占用单号，`error_details.stage` 为 `query_shipment_sub_product_code`，诊断数据不包含 Token、Cookie 或请求头。

## 南航开单

### 查询南航出港货邮处理费选项

`POST /api/v1/waybills/china-southern-air/departure-cargo-mail-handling-charge-options`

请求体：

```json
{
  "origin_station": "SZX",
  "destination": "TAO",
  "flight_number": "CZ8735",
  "flight_date": "2026-08-20",
  "cargo_type_code": "3006",
  "cargo_name": "普货"
}
```

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `origin_station` | string | 是 | 始发站三字码，服务端自动去除首尾空格并转为大写 |
| `destination` | string | 是 | 目的站三字码，服务端自动去除首尾空格并转为大写 |
| `flight_number` | string | 是 | 航班号，服务端自动去除首尾空格并转为大写 |
| `flight_date` | string | 是 | 航班日期，格式为 `YYYY-MM-DD` |
| `cargo_type_code` | string | 是 | 货物类型代码，例如普货对应 `3006`；内部映射至南航请求的 `shipmentType` |
| `cargo_name` | string | 是 | 货物类型名称，例如 `普货`；内部映射至南航请求的 `shipmentTypeName` |

接口入参使用 `cargo_type_code`，不再使用容易与货物类型名称混淆的 `cargo_type`。

若南航查询成功但返回的 `extServiceCharges` 中没有名为“出港货邮处理费”的费用组，
接口返回 `502`，并在 `data.error_details` 中提供安全的排查信息：

```json
{
  "code": 502,
  "data": {
    "error_details": {
      "stage": "select_departure_cargo_mail_handling_charge",
      "request_data": {
        "resAllInfoList": [
          {
            "resDto": {
              "flightDep": "SZX",
              "flightDest": "TAO",
              "bookFlightno": "CZ8735",
              "bookFlightdate": "2026-08-31"
            }
          }
        ],
        "routing": "SZX/TAO",
        "shipmentType": "3006",
        "shipmentTypeName": "普货",
        "channel": "B2B"
      },
      "expected_service_main_name": "出港货邮处理费",
      "available_service_main_names": [],
      "upstream_response": {
        "extServiceCharges": []
      }
    }
  },
  "msg": "未查询到南航出港货邮处理费选项"
}
```

`upstream_response.extServiceCharges` 会保留南航实际返回的完整费用列表，便于判断是空列表、
费用组名称发生变化，还是请求业务参数不匹配。诊断数据不会包含南航 Token、Cookie 或请求头。

### 南航开单费用选项的可选规则

`form_data.outbound_cargo_and_mail_handling_fee_options` 为可选字段。填写时，执行阶段会按表单保存的费用组选项定位“出港货邮处理费”并完成对应明细的 `checked=Y` 勾选；未填写、为 `null` 或空字符串时，不再定位、替换或补勾任何费用组/明细，直接将本次 `queryServiceCharge` 返回的完整 `extServiceCharges` 列表传给 `calculateCharge` 和 `createOrder`，南航返回的原始 `checked` 状态保持不变。

### 新增南航运单

`POST /api/v1/waybills/{waybill_id}/execute-china-southern-air`

`form_data.cargo_info.special_cargo_code` 为可选的用户附加特货码。执行阶段在预占单号之前调用南航 `queryShipmentSubProductCode`，参数映射为 `dest <- flight_info.destination`、`origin <- flight_info.origin_station`、`shipmentType <- cargo_info.cargo_type`、`productName <- cargo_info.product_name`（为空时使用与 `parentProductionName` 一致的业务配置或默认“南航快运”），并固定传入 `channel=B`、`directTransfer=D`、`customerno=SZXFED`。返回的 `result.subCode` 与用户码按“默认码在前、用户码在后”进行大小写不敏感去重；例如默认 `XPS`、用户填写 `GEN`，持久化的 `form_data.cargo_info.special_cargo_code` 回写为 `XPS,GEN`，发往南航 `orderInfo.orderShipment.spCode` 和 `productionCode` 的值均为 `XPS/GEN`。英文逗号、中文逗号及历史 `/` 分隔数据均兼容。查询失败不会占用单号，并以 `502` 返回 `error_details.stage="query_shipment_sub_product_code"` 及安全的请求/响应诊断数据。

`form_data.cargo_info.booking_volume` 为可选字段。已填写时直接作为南航请求的 `volume`；未传、为 `null` 或空字符串时，在预占单号之前调用南航 `calculateCWeight`，将 `flight_info.origin_station` 作为 `depCityCode`、`cargo_info.weight` 作为 `weight`，其余请求字段固定为 `dimensions=null`、`volume=""`、`channel="B2B"`。返回的 `result.volume` 用于后续 `calculateCharge`、`createOrder`，但不回写原始 `form_data`；默认体积查询失败不会占用单号，并以 `502` 返回 `error_details.stage="calculate_cweight"` 及安全的请求/响应诊断数据。

`form_data.outbound_cargo_and_mail_handling_fee_options` 为可选字段。填写时，执行阶段使用表单保存的费用组选项定位“出港货邮处理费”并完成对应明细的 `checked=Y` 勾选；未填写、为 `null` 或空字符串时，不再定位、替换或补勾任何费用组/明细，直接将本次 `queryServiceCharge` 返回的完整 `extServiceCharges` 列表传给 `calculateCharge` 和 `createOrder`，南航返回的原始 `checked` 状态保持不变。

最终 `volume` 确定后、预占单号之前，后端调用南航 `queryB2eFlightPrice`。字段映射为：`flightDep <- flight_info.origin_station`、`flightDest <- flight_info.destination`、`flightNo <- flight_info.flight_number`、`flightDate <- flight_info.flight_date`、`rateCode/shipmentType <- cargo_info.cargo_type_code`、`shipmentTypeName <- cargo_info.cargo_type`、`weight <- cargo_info.weight`、`volume <- 最终订舱体积`；固定字段为 `channel=B`、`customerCode=SZXFED`、`dimensions=null`、`rateType=SPY`。后端按有效 `cargo_info.product_name` 精确匹配 `result.charge[].parentProductionName`，将对应 `flightPriceCalculateResult.spaceClass` 同时用于南航请求的 `orderInfo.orderShipment.bookGrade`、`spaceClass`，将 `subSpaceClass` 用于同名字段。查询失败、产品匹配不到或舱位字段为空时不开单、不占用单号，并以 `502` 返回 `error_details.stage="query_b2e_flight_price"` 及安全诊断信息。

南航 `createOrder` 成功后，服务端会在同一个数据库事务中将运单的 `airline_record_status` 更新为成功，并锁定本次实际使用的 `waybill_stock_items` 记录，再次确认 `usage_status="1"`、`usage_date=当天`。该确认是幂等操作，用于保证南航已成功开单时单号绝不会以未使用状态回流；后续结算、制单或打印异常不会改变该单号的已使用状态。南航直连订舱成功时采用相同的最终确认机制。
