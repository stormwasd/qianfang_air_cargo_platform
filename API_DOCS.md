# API 文档

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

## 深航订舱-计飞时间-集装器数据获取

文件扫描器从 `AwbQueryExport*.xlsx` 读取单号、航程和航班日期后，按既有携程
`ready_time - 105` 分钟调度处理。直连模式由定时管理器直接调用 KingGo GET
`/awb/query/getaway` 获取 HTML 表格，不创建 `rpa_tasks` 记录；RPA 执行器和队列消费
逻辑完整保留，可通过配置切换：

```env
SHENZHEN_AIR_BILLING_TIME_CONTAINER_EXECUTION_MODE=direct
```

直连请求每次从 HAR 重新提取 Cookie 和签名，生成当前毫秒时间戳 `_` 及新的
`oOr6SIhu`，并发送 `awbPrefix=479`、Excel 单号、Excel 航程、Excel 航班日期、
`nti=119` 和 `historyCheck=false`。返回页面只解析 `#getWay` 下九列表格数据，
跳过表头和“合计”行，字段按原 RPA 映射写入
`shenzhen_air_billing_time_containers`，并继续查询携程预飞时间。空数据、登录页、
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

调用前必须在运行服务的文件系统配置有效 KingGo HAR，默认路径 `generated_files/www.kinggo.com.har`。Docker 部署中该目录挂载到 `/app/generated_files`。每一次对六个 KingGo 接口的 HTTP 请求都会重新读取 HAR、离线执行 `/main` 保护脚本提取配置和 Cookie，并针对当前实际请求 URL 重新生成 `oOr6SIhu`；不会缓存签名配置或 Cookie。`SHENZHEN_AIR_KINGGO_BROWSER` 控制提取浏览器；Linux/Docker 建议使用 `chromium`。HAR 不含可用 Cookie、HAR 无效或签名生成失败时，该次请求不会发给 KingGo。

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
