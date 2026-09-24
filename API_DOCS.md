# API 文档

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

深航和南航分别提供独立的环境变量开关，用于控制开单成功后的整条自动后处理链。为兼容既有部署环境，配置项继续沿用 `AUTO_PRINT` 名称，但控制范围已扩展为费用读取、结算单、运单同步、制单、文件生成及自动打印：

| 配置项 | 默认值 | 说明 |
| --- | --- | --- |
| `RPA_SHENZHEN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED` | `True` | 深航开单成功后是否执行结算、制单及打印等自动后处理 |
| `RPA_CHINA_SOUTHERN_AIR_AUTO_PRINT_AFTER_WAYBILL_ENABLED` | `True` | 南航开单成功后是否执行结算、制单及打印等自动后处理 |

- 配置为 `True`：保持原有行为。开单成功后继续读取费用队列、创建结算单，并按原链路同步运单、生成货站制单文件和创建自动打印任务。
- 配置为 `False`：开单或订舱本身仍正常完成并保留成功状态及已取得的运单号；跳过其后的费用读取、结算单创建、订舱开单后的运单记录同步、货站制单、文件生成和自动打印，相关执行状态保持未执行。用于获取核心结果的队列仍会正常清理。
- 单纯的南航订舱成功链路目前只保存订舱状态和运单号，本身没有结算、制单或打印后处理；后续从订舱发起开单时，上述南航开关会控制开单成功后的完整后处理链。
- 两个航司的开关相互独立，修改 `.env` 后需要重启应用服务生效。
- `POST /api/v1/waybills/{waybill_id}/print-document` 手动打印接口不受影响。

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
