# API 文档

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

## 南航订舱

### 下载批量订舱模板

`GET /api/v1/bookings/china-southern-air/template`

返回标准 `.xlsx` 文件。模板约定：

- 数据填写区统一使用文本格式并默认水平、垂直居中，避免航班号、货物代码等标识被 Excel 自动转换。
- `特货码（多个用英文逗号隔开）`：多个特货码使用英文逗号分隔，例如 `XPS,GEN`。
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
- `出港货邮处理费选项`写入 `form_data.outbound_cargo_and_mail_handling_fee_options`。
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

### 批量执行订舱

`POST /api/v1/bookings/execute`

执行南航订舱前会再次检查 `cargo_type_code`。对于本次修复上线前，由旧版前端 Excel 解析流程创建且缺少该字段的未执行或失败记录，后端会按 `cargo_type` 自动补齐并保存，再调用南航接口；无法完成字典映射时，该条执行失败并返回明确错误。

`form_data.bookings[0].special_cargo_code` 在平台内部保持英文逗号分隔，例如 `XPS,AKA`。调用南航 `createOrder` 时，服务端仅在请求构建阶段将英文逗号或中文逗号转换为 `/`，因此发往南航的 `orderInfo.orderShipment.spCode` 和 `productionCode` 均为 `XPS/AKA`；原始 `form_data` 不会被修改。历史上已经使用 `/` 分隔的数据仍兼容。

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

### 新增南航运单

`POST /api/v1/waybills/{waybill_id}/execute-china-southern-air`

`form_data.cargo_info.special_cargo_code` 在平台内部使用英文逗号分隔。调用南航 `createOrder` 时，服务端将英文逗号或中文逗号转换为 `/`，并同时写入 `orderInfo.orderShipment.spCode` 和 `productionCode`；原始 `form_data` 保持不变，已有 `/` 分隔数据继续兼容。
