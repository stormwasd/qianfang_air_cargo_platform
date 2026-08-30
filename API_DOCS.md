# 千方航空物流平台 API 接口文档

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证方式**: Bearer Token (JWT)
- **Content-Type**: `application/json`

## 统一响应格式

所有接口返回统一的JSON格式：

```json
{
  "code": 0,
  "data": {},
  "msg": "success"
}
```

**说明**：

- `code`: 状态码，`0` 表示成功，其他情况使用HTTP状态码（如 400、401、403、404、500等）
- `data`: 返回的数据，成功时包含具体数据，失败时为 `null`
- `msg`: 消息描述，成功或错误信息

## 认证说明

除了登录接口和刷新token接口外，其他接口都需要在请求头中携带 token：

```
Authorization: Bearer <access_token>
```

## 权限代码说明

所有权限相关的输入输出都使用权限代码，而不是中文名称：

| 权限代码 | 对应一级菜单 |
|---------|---------|
| `organizational_management` | 组织管理（账号管理、部门管理） |
| `system` | 系统管理 |
| `customer_service` | 客服接单台 |
| `expense_registration` | 费用登记台 |
| `admin` | 管理员（返回全部菜单） |

前端新增、修改账号时应提交上表中的固定权限代码。后端仍兼容历史权限代码
`waybill`、`booking`、`settlement`、`customer`、`bill`、`robot` 和 `cost_service`；
其中历史代码 `cost_service` 在读取和接口返回时会规范化为 `expense_registration`，二者均生成
“费用登记台”菜单；数据库旧数据无需迁移，新数据统一使用 `expense_registration`。

登录接口会根据账号保存的权限代码生成 `menus`：

- `organizational_management`：返回“组织管理”，子菜单为“账号管理”和“部门管理”；
- `system`：返回“系统管理”，子菜单为“业务参数管理”；
- `customer_service`：返回“客服接单台”；
- `expense_registration`：返回“费用登记台”；
- 除 `admin` 外，上述权限生成的菜单均包含“用户中心”；多个权限的菜单会合并、去重，并将“用户中心”固定在末尾；
- `admin`：直接返回系统全部菜单。

## 时间格式说明

所有时间字段统一使用中国时间（UTC+8），格式为 ISO 8601 标准格式，例如：`2025-01-01T12:00:00+08:00`

## ID 格式说明

所有 ID 字段（用户ID、部门ID、客户ID等）都是 `BigInteger` 类型，在 API 响应中统一转换为字符串格式返回。

## 接口列表

### 1. 认证相关

#### 1.1 用户登录

**接口地址**: `POST /api/v1/auth/login`

**请求参数**:

```json
{
  "phone": "13800138000",
  "password": "password123"
}
```

**响应示例**（管理员用户）:

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "has_initialized": false,
    "permissions": ["admin"],
    "menus": [
      {
        "name": "主单管理",
        "children": [
          {"name": "运单管理"},
          {"name": "订舱管理"}
        ]
      },
      {
        "name": "结算单管理",
        "children": [
          {"name": "结算单管理"}
        ]
      },
      {
        "name": "客户管理",
        "children": [
          {"name": "客户管理"}
        ]
      },
      {
        "name": "单号管理",
        "children": [
          {"name": "单号管理"}
        ]
      },
      {
        "name": "机器人管理",
        "children": [
          {"name": "机器人管理"}
        ]
      },
      {
        "name": "系统管理",
        "children": [
          {"name": "业务参数管理"}
        ]
      },
      {
        "name": "组织管理",
        "children": [
          {"name": "账号管理"},
          {"name": "部门管理"}
        ]
      },
      {
        "name": "客服接单台",
        "children": [
          {"name": "客服接单台"}
        ]
      },
      {
        "name": "费用登记台",
        "children": [
          {"name": "费用登记台"}
        ]
      },
      {
        "name": "用户中心",
        "children": [
          {"name": "用户中心"}
        ]
      }
    ],
    "user": {
      "id": "260819415803760640",
      "phone": "13800138000",
      "name": "张三",
      "department_ids": ["260819415803760641", "260819415803760642"],
      "departments": [
        {"id": "260819415803760641", "name": "技术部"},
        {"id": "260819415803760642", "name": "运营部"}
      ],
      "permissions": ["admin"],
      "is_active": true,
      "created_at": "2025-01-01T12:00:00+08:00",
      "updated_at": "2025-01-01T12:00:00+08:00"
    }
  },
  "msg": "登录成功"
}
```

**响应示例**（非管理员用户）:

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "permissions": ["customer_service", "expense_registration"],
    "menus": [
      {
        "name": "客服接单台",
        "children": [
          {"name": "客服接单台"}
        ]
      },
      {
        "name": "费用登记台",
        "children": [
          {"name": "费用登记台"}
        ]
      },
      {
        "name": "用户中心",
        "children": [
          {"name": "用户中心"}
        ]
      }
    ],
    "user": {
      "id": "260819415803760641",
      "phone": "13900139000",
      "name": "李四",
      "department_ids": ["260819415803760641"],
      "departments": [
        {"id": "260819415803760641", "name": "技术部"}
      ],
      "permissions": ["customer_service", "expense_registration"],
      "is_active": true,
      "created_at": "2025-01-01T12:00:00+08:00",
      "updated_at": "2025-01-01T12:00:00+08:00"
    }
  },
  "msg": "登录成功"
}
```

**响应字段详细说明**:

| 字段名 | 类型 | 是否必返 | 说明 |
|--------|------|---------|------|
| `access_token` | string | 是 | 访问令牌，用于后续接口认证，格式：`Bearer <access_token>` |
| `refresh_token` | string | 是 | 刷新令牌，用于刷新access_token，有效期90天 |
| `has_initialized` | boolean | 否 | **仅管理员权限用户返回此字段**。表示业务参数配置是否已初始化，`true`表示已初始化，`false`表示未初始化。前端根据此字段决定是否显示业务参数初始化配置页面。非管理员用户不返回此字段，因为业务参数管理只有管理员权限才能看到 |
| `permissions` | array[string] | 是 | 用户权限列表（权限代码），用于生成可见菜单。前端使用：`organizational_management`（组织管理）、`system`（系统管理）、`customer_service`（客服接单台）、`expense_registration`（费用登记台）、`admin`（管理员） |
| `menus` | array[object] | 是 | 用户菜单列表，根据用户权限动态生成。每个菜单项包含：<br>- `name`（string）：菜单名称<br>- `children`（array[object]）：子菜单列表，每个子菜单包含 `name` 字段 |
| `user` | object | 是 | 用户完整信息对象，包含以下字段：<br>- `id`（string）：用户ID（BigInteger转字符串）<br>- `phone`（string）：手机号（11位）<br>- `name`（string）：用户姓名<br>- `department_ids`（array[string]）：所属部门ID列表（BigInteger转字符串）<br>- `departments`（array[object]）：所属部门详细信息列表，每个部门包含：<br>  - `id`（string）：部门ID<br>  - `name`（string）：部门名称<br>- `permissions`（array[string]）：用户权限列表（权限代码）<br>- `is_active`（boolean）：是否启用<br>- `created_at`（string）：创建时间（中国时间，UTC+8，ISO 8601格式）<br>- `updated_at`（string）：更新时间（中国时间，UTC+8，ISO 8601格式） |

**说明**:

- **权限控制**：`has_initialized` 字段仅对管理员权限（`admin`）用户返回，因为业务参数管理功能只有管理员权限才能访问。非管理员用户登录时不会返回此字段
- **菜单生成**：`menus` 字段根据用户权限动态生成；拥有 `system` 权限的非管理员用户也会看到“系统管理”菜单，管理员用户返回全部菜单
- **时间格式**：所有时间字段使用中国时间（UTC+8），格式为 ISO 8601 标准格式，例如：`2025-01-01T12:00:00+08:00`
- **ID格式**：所有ID字段（用户ID、部门ID等）都是 `BigInteger` 类型，在API响应中统一转换为字符串格式返回

#### 1.2 退出登录

**接口地址**: `POST /api/v1/auth/logout`

**请求头**: `Authorization: Bearer <token>`

**说明**:

- 需要认证，需要在请求头中携带有效的access_token
- 退出登录后，通过递增用户的token_version使所有现有的access_token和refresh_token失效
- 用户需要重新登录才能获取新的token
- 即使token尚未过期，也会因为token_version不匹配而无法使用

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "退出登录成功"
}
```

**说明**:

- 退出登录后，所有现有的access_token和refresh_token都会失效
- 用户需要重新登录才能获取新的token
- 即使token尚未过期，也会因为token_version不匹配而无法使用

---

#### 1.3 刷新token

**接口地址**: `POST /api/v1/auth/refresh`

**请求参数**:

```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  },
  "msg": "token刷新成功"
}
```

**说明**: 使用refresh_token获取新的access_token和refresh_token

---

### 2. 业务参数管理

#### 2.1 保存业务参数配置（创建或更新）

**接口地址**: `PUT /api/v1/config`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

`config_data` 是一个四层嵌套的字典结构（所有键名使用英文，遵循snake_case命名规范）：

- **第一层**：航司代码（如："shenzhen_air"、"china_southern_air"）
- **第二层**：业务类型（如："booking"、"document"、"print"、"booking_and_create"）
- **第三层**：参数组代码（如："shenzhen_air_login"、"business_default"等）
- **第四层**：参数项（键值对，值为字符串）

**完整数据结构示例**:

```json
{
  "config_data": {
    "shenzhen_air": {
      "booking": {
        "shenzhen_air_login": {
          "system_url": "https://example.com",
          "system_account": "username",
          "login_password": "password"
        },
        "business_default": {
          "origin_station": "SZX",
          "shipper_info": "默认发货人",
          "freight_code": "L",
          "cargo_code": "0001",
          "package": "纸箱",
          "cargo_name": "普通货物"
        }
      },
      "document": {
        "print_delay_after_cargo_station_record": 30,
        "domestic_cargo_checklist": {
          "shipper_or_agent": "XX公司",
          "shipper_or_agent_seal": "XX公司签章",
          "shipper_or_inspector": "检查人姓名"
        },
        "inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo": {
          "shipper_or_agent": "XX公司"
        },
        "shenzhen_airport_air_cargo_security_inspection_declaration_list": {
          "delivery_person": "交运人姓名"
        },
        "domestic_cargo_detail": {},
        "emergency_lithium_battery": {
          "emergency_contact": "张三",
          "emergency_phone_24h": "13800138000"
        },
        "shenzhen_airport_security_declaration": {
          "shipper_seal": "托运人签章"
        },
        "packaging_spec_part2_battery_checklist": {
          "consignor_agent": "XX公司",
          "consignor_agent_checker_signature": "李四"
        }
      },
      "print": {
        "printer_config": [
          {
            "document_type": "交接单",
            "printer_name": "HP LaserJet"
          },
          {
            "document_type": "航空货物明细表",
            "printer_name": "HP LaserJet"
          },
          {
            "document_type": "货物收运检查清单",
            "printer_name": "Canon Printer"
          },
          {
            "document_type": "标签单",
            "printer_name": "Canon Printer"
          },
          {
            "document_type": "充氧类水生动物货物收运检查单",
            "printer_name": "Canon Printer"
          },
          {
            "document_type": "航司货运主单",
            "printer_name": "Canon Printer"
          }
        ]
      }
    },
    "china_southern_air": {
      "booking_and_create": {
        "china_southern_air_login": {
          "system_url": "https://csair.example.com",
          "system_account": "username",
          "login_password": "password"
        },
        "tangi_login": {
          "address_of_the_application_executable_file_tangyi": "C:\\path\\to\\Tang.Face.Main.exe",
          "system_account": "username",
          "login_password": "password"
        },
        "business_default": {
          "origin_station": "CAN",
          "booking_remark": "备注信息",
          "cargo_code": "0001",
          "cargo_type": "普通货物",
          "package": "纸箱",
          "special_cargo_code": "",
          "agent_checker_name": "王五",
          "agent_consignor_name": "赵六",
          "order_contact_name": "联系人",
          "order_contact_phone": "13800138000",
          "settlement_file_number": "SF001",
          "shipper": "托运人",
          "phone": "13900139000",
          "address": {
            "region": "广东省/深圳市/南山区",
            "detail": "科技园南区"
          }
        }
      },
      "document": {
        "print_delay_after_cargo_station_record": 30,
        "inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo": {
          "shipper_or_agent": "XX公司"
        }
      },
      "print": {
        "printer_config": [
          {
            "document_type": "充氧类水生动物货物收运检查单",
            "printer_name": "Canon Printer"
          },
          {
            "document_type": "航司货运主单",
            "printer_name": "Canon Printer"
          },
          {
            "document_type": "航空货物安检申报清单",
            "printer_name": "HP LaserJet"
          },
          {
            "document_type": "标签单",
            "printer_name": "HP LaserJet"
          }
        ]
      }
    }
  }
}
```

**数据结构详细说明**:

这是一个完整的配置示例，包含了所有航司、所有业务类型和所有参数组：

- **第一层（航司代码）**：
  - `shenzhen_air`: 深圳航空
  - `china_southern_air`: 南方航空

- **第二层（业务类型）**：
  - 深圳航空：`booking`（开单）、`document`（制单）、`print`（打单）
  - 南方航空：`booking_and_create`（订舱与开单）、`document`（制单）、`print`（打单）

- **第三层（参数组代码）**：
  - **深圳航空-开单**：
    - `shenzhen_air_login`（深航系统登录参数）：包含系统网址、系统账号、登录密码
    - `business_default`（业务默认参数）：包含始发站、发货人信息、运价代码、货物代码、包装、货物名称
  - **深圳航空-制单**：
    - `print_delay_after_cargo_station_record`（货站录单成功后延迟打单时间，秒）：0-600，默认30，0表示不延迟
    - `domestic_cargo_checklist`（国内货站货物收运检查清单）：包含托运人或代理人（shipper_or_agent）、签章（shipper_or_agent_seal）、检查人（shipper_or_inspector）
    - `inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo`（充氧类水生动物货物收运检查单）：包含托运人或代理人（shipper_or_agent）
    - `shenzhen_airport_air_cargo_security_inspection_declaration_list`（深圳机场航空货物安检申报清单-交接单）：包含交运人（delivery_person）
    - `domestic_cargo_detail`（国内始发航空货物明细表）：目前为空字典，无参数项
    - `emergency_lithium_battery`（应急措施（锂电池））：包含紧急联系人、24小时联系电话
    - `shenzhen_airport_security_declaration`（深圳机场航空货物安检申报清单）：包含托运人签章
    - `packaging_spec_part2_battery_checklist`（符合包装说明第II部分锂电池/钠离子电池货物收运检查单）：包含托运人/托运人代理人、检查人签字
  - **深圳航空-打单**：
    - `printer_config`（打印机配置）：数组类型，支持配置多个打印机。document_type 可选值：交接单、航空货物明细表、货物收运检查清单、标签单、充氧类水生动物货物收运检查单、航司货运主单
  - **南方航空-订舱与开单**：
    - `china_southern_air_login`（南航系统登录参数）：包含系统网址、系统账号、登录密码
    - `tangi_login`（唐翼系统登录参数）：包含唐翼应用可执行文件地址（address_of_the_application_executable_file_tangyi）、系统账号、登录密码
    - `business_default`（业务默认参数）：包含始发站、订舱备注、货物代码、货物类型、包装、特货码、代理公司检查人名称、代理公司交运人名称、订单联系人名称、订单联系人电话、结算文件号、托运人、手机号、地址（address对象，包含region省/市/区和detail详细地址）
  - **南方航空-制单**：
    - `print_delay_after_cargo_station_record`（货站录单成功后延迟打单时间，秒）：0-600，默认30，0表示不延迟
    - `inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo`（充氧类水生动物货物收运检查单）：包含托运人或代理人（shipper_or_agent）
  - **南方航空-打单**：
    - `printer_config`（打印机配置）：数组类型，支持配置多个打印机。document_type 可选值：充氧类水生动物货物收运检查单、航司货运主单、航空货物安检申报清单、标签单

- **第四层（参数项）**：
  - 大部分参数项的值都是字符串类型；`print_delay_after_cargo_station_record` 为数字类型（整数，秒）
  - `printer_config` 数组中的每个元素包含：
    - `document_type`（单据类型）：如"运单"、"订舱单"等
    - `printer_name`（打印机名称）：打印机设备名称
  - 示例中每个航司都配置了2个打印机，实际使用时可以根据需要配置任意数量的打印机

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760643",
    "config_data": {
      "shenzhen_air": {
        "booking": { "..." : "..." },
        "document": { "..." : "..." },
        "print": { "..." : "..." }
      },
      "china_southern_air": {
        "booking_and_create": { "..." : "..." },
        "document": { "..." : "..." },
        "print": { "..." : "..." }
      }
    },
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "配置创建成功"
}
```

**说明**:

- 这是一个 upsert 操作（update or insert）
- 全局唯一配置，如果尚未配置，则创建新配置，返回 "配置创建成功"
- 如果已有配置，则更新现有配置，返回 "配置更新成功"
- `config_data` 采用四层嵌套字典结构：航司代码 -> 业务类型 -> 参数组代码 -> 参数项
- 所有键名使用英文，遵循snake_case命名规范
- 所有参数项的值都是字符串类型（`printer_config` 中的值除外，其为数组）
- 参数组可以为空字典（如："domestic_cargo_detail"）
- `printer_config` 是一个数组，支持配置多个打印机（每个元素包含 `document_type` 和 `printer_name`）
- 响应体中的 `config_data` 结构与请求体一致，完整数据结构请参考上方"完整数据结构示例"
- 只有管理员可以操作此接口（通过菜单权限控制）

#### 2.2 获取业务参数配置

**接口地址**: `GET /api/v1/config`

**请求头**: `Authorization: Bearer <token>`

**响应示例**（有配置）:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760643",
    "config_data": {
      "shenzhen_air": {
        "booking": {
          "shenzhen_air_login": {
            "system_url": "https://example.com",
            "system_account": "username",
            "login_password": "password"
          },
          "business_default": {
            "origin_station": "SZX",
            "shipper_info": "默认发货人",
            "freight_code": "L",
            "cargo_code": "0001",
            "package": "纸箱",
            "cargo_name": "普通货物"
          }
        },
        "document": {
          "print_delay_after_cargo_station_record": 30,
          "domestic_cargo_checklist": {
            "shipper_or_agent": "XX公司",
            "shipper_or_agent_seal": "XX公司签章",
            "shipper_or_inspector": "检查人姓名"
          },
          "inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo": {
            "shipper_or_agent": "XX公司"
          },
          "shenzhen_airport_air_cargo_security_inspection_declaration_list": {
            "delivery_person": "交运人姓名"
          }
        },
        "print": {
          "printer_config": [
            {
              "document_type": "交接单",
              "printer_name": "HP LaserJet"
            },
            {
              "document_type": "航空货物明细表",
              "printer_name": "HP LaserJet"
            },
            {
              "document_type": "货物收运检查清单",
              "printer_name": "Canon Printer"
            },
            {
              "document_type": "标签单",
              "printer_name": "Canon Printer"
            },
            {
              "document_type": "充氧类水生动物货物收运检查单",
              "printer_name": "Canon Printer"
            },
            {
              "document_type": "航司货运主单",
              "printer_name": "Canon Printer"
            }
          ]
        }
      },
      "china_southern_air": {
        "booking": {
          "booking_config": {
            "wide": ["4", "5", "6"],
            "narrow": ["1", "2", "3"]
          }
        },
        "booking_and_create": {
          "china_southern_air_login": {
            "system_url": "https://csair.example.com",
            "system_account": "username",
            "login_password": "password"
          },
          "tangi_login": {
            "address_of_the_application_executable_file_tangyi": "C:\\path\\to\\Tang.Face.Main.exe",
            "system_account": "username",
            "login_password": "password"
          },
          "business_default": {
            "origin_station": "CAN",
            "booking_remark": "开单默认备注信息",
            "booking_remark_wide": "订舱默认宽体备注",
            "booking_remark_narrow": "订舱默认窄体备注",
            "cargo_code": "0001",
            "cargo_type": "普通货物",
            "package": "纸箱",
            "special_cargo_code": "",
            "agent_checker_name": "王五",
            "agent_consignor_name": "赵六",
            "order_contact_name": "联系人",
            "order_contact_phone": "13800138000",
            "settlement_file_number": "SF001",
            "shipper": "托运人",
            "phone": "13900139000",
            "address": {
              "region": "广东省/深圳市/南山区",
              "detail": "科技园南区"
            }
          }
        },
        "document": {
          "print_delay_after_cargo_station_record": 30,
          "inspection_form_for_the_receipt_and_transport_of_oxygenated_aquatic_animal_cargo": {
            "shipper_or_agent": "XX公司"
          }
        },
        "print": {
          "printer_config": [
            {
              "document_type": "充氧类水生动物货物收运检查单",
              "printer_name": "Canon Printer"
            },
            {
              "document_type": "航司货运主单",
              "printer_name": "Canon Printer"
            },
            {
              "document_type": "航空货物安检申报清单",
              "printer_name": "HP LaserJet"
            },
            {
              "document_type": "标签单",
              "printer_name": "HP LaserJet"
            }
          ]
        }
      }
    },
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**响应示例**（无配置）:

```json
{
  "code": 0,
  "data": null,
  "msg": "暂无配置信息"
}
```

**说明**:

- 获取全局唯一配置
- `config_data` 返回四层嵌套字典结构：航司代码 -> 业务类型 -> 参数组代码 -> 参数项
- 所有键名使用英文，遵循snake_case命名规范
- 如果尚未配置，返回 `code=0`，`data=null`（这是正常情况，不是错误）
- 前端可以根据 `data` 是否为 `null` 来判断是否有配置
- 只有管理员可以操作此接口（通过菜单权限控制）

#### 2.3 字典类型管理

##### 2.3.1 创建字典类型

**接口地址**: `POST /api/v1/config/dict-types`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "name": "运价代码",
  "type": "freight_code",
  "status": 1
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "name": "运价代码",
    "type": "freight_code",
    "status": 1,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "字典类型创建成功"
}
```

**说明**:

- `name`: 名称（1-100个字符）
- `type`: 唯一类型标识（1-50个字符），如：`freight_code`、`goods_code`
- `status`: 状态（0=禁用，1=开启），默认为1
- 如果`type`已存在，返回409错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.3.2 获取字典类型列表

**接口地址**: `GET /api/v1/config/dict-types`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `type`: 类型标识筛选（可选，唯一标识，如：`freight_code`）
- `status`: 状态筛选（可选，0=禁用，1=开启）
- `page`: 页码（可选，不传则不分页，返回全部）
- `pageSize`: 每页数量（可选，不传则不分页，返回全部，最大200）

**请求示例**:

- 分页查询：`GET /api/v1/config/dict-types?type=freight_code&status=1&page=1&pageSize=10`
- 不分页（返回全部）：`GET /api/v1/config/dict-types?status=1`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 4,
    "items": [
      {
        "id": "260819415803760650",
        "name": "运价代码",
        "type": "freight_code",
        "status": 1,
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**说明**:

- 返回全局共享的字典类型
- 支持按type精确筛选
- 支持按状态筛选
- 支持分页
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.3.3 获取字典类型详情

**接口地址**: `GET /api/v1/config/dict-types/{dict_type_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `dict_type_id`: 字典类型ID（字符串格式）

**请求示例**: `GET /api/v1/config/dict-types/260819415803760650`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "name": "运价代码",
    "type": "freight_code",
    "status": 1,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**:

- 通过`id`获取字典类型详情
- 如果字典类型不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.3.4 更新字典类型

**接口地址**: `PUT /api/v1/config/dict-types/{dict_type_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `dict_type_id`: 字典类型ID（字符串格式）

**请求参数**（所有字段可选）:

```json
{
  "name": "运价代码（更新）",
  "type": "freight_code_new",
  "status": 0
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "name": "运价代码（更新）",
    "type": "freight_code_new",
    "status": 0,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:30:00+08:00"
  },
  "msg": "字典类型更新成功"
}
```

**说明**:

- 传入的字段会更新，未传入的字段保持原值
- 如果更新`type`，会检查是否与其他类型冲突
- 如果字典类型不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.3.5 删除字典类型

**接口地址**: `DELETE /api/v1/config/dict-types/{dict_type_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `dict_type_id`: 字典类型ID（字符串格式）

**请求示例**: `DELETE /api/v1/config/dict-types/260819415803760650`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "type": "freight_code",
    "name": "运价代码",
    "deleted_options_count": 5
  },
  "msg": "字典类型删除成功，已删除 5 个关联的字典选项"
}
```

**说明**:

- 删除字典类型会自动删除关联的所有字典选项（CASCADE级联删除）
- 返回信息中包含删除的关联选项数量
- 如果字典类型不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

#### 2.4 字典选项管理

##### 2.4.1 创建字典选项

**接口地址**: `POST /api/v1/config/dict-options`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "dict_type": "freight_code",
  "label": "运价代码",
  "value": "L",
  "status": 1,
  "color_type": "success"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760651",
    "dict_type_id": "260819415803760650",
    "dict_type": "freight_code",
    "label": "运价代码",
    "value": "L",
    "status": 1,
    "color_type": "success",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "字典选项创建成功"
}
```

**说明**:

- `dict_type`: 父级type（字典类型的唯一标识，如：`freight_code`）
- `label`: 显示字段（1-100个字符）
- `value`: 存储的值（单个字符串，如：`"L"`）
- `status`: 状态（0=禁用，1=开启），默认为1
- `color_type`: 颜色类型（用于前端区分状态颜色，非必填，最大50个字符）
- 一个字典类型下可以有多个字典选项，每个选项有独立的id
- 如果字典类型不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.4.2 获取字典选项列表

**接口地址**: `GET /api/v1/config/dict-options`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `dict_type`: 字典类型（唯一标识，如：`freight_code`）（可选）
- `status`: 状态筛选（可选，0=禁用，1=开启）
- `page`: 页码（可选，不传则不分页，返回全部）
- `pageSize`: 每页数量（可选，不传则不分页，返回全部，最大200）
- `order`: 排序方式（可选，`asc`=从小到大，`desc`=从大到小），**仅当所有选项的value全为数字时生效**，不传则默认从小到大排序。如果选项不全为数字，则不受此参数影响，保持按创建时间倒序排序

**请求示例**:

- 分页查询：`GET /api/v1/config/dict-options?dict_type=freight_code&status=1&page=1&pageSize=10`
- 不分页（返回全部）：`GET /api/v1/config/dict-options?dict_type=freight_code&status=1`
- 数字排序（从小到大）：`GET /api/v1/config/dict-options?dict_type=freight_code&order=asc`
- 数字排序（从大到小）：`GET /api/v1/config/dict-options?dict_type=freight_code&order=desc`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 3,
    "items": [
      {
        "id": "260819415803760651",
        "dict_type_id": "260819415803760650",
        "dict_type": "freight_code",
        "label": "最低运价",
        "value": "M",
        "status": 1,
        "color_type": "success",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      },
      {
        "id": "260819415803760652",
        "dict_type_id": "260819415803760650",
        "dict_type": "freight_code",
        "label": "最低运价",
        "value": "N",
        "status": 1,
        "color_type": null,
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      },
      {
        "id": "260819415803760653",
        "dict_type_id": "260819415803760650",
        "dict_type": "freight_code",
        "label": "普通运价",
        "value": "Q",
        "status": 1,
        "color_type": "warning",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**说明**:

- 返回全局共享的字典选项
- 每个选项包含：`id`、`dict_type_id`、`dict_type`、`label`、`value`（字符串）、`status`、`color_type`（颜色类型，非必填，可能为null）等
- 一个字典类型下可以有多个选项，每个选项有独立的id和value
- 支持按字典类型筛选
- 支持按状态筛选
- 支持分页
- **排序规则**：
  - `order` 参数仅当所有选项的 `value` 全为数字时生效（包括整数和小数，如："1"、"2.5"、"10"等）
  - 如果所有选项的 `value` 全为数字：
    - 不传 `order` 参数时，默认按 `value` 从小到大排序（`asc`）
    - 传 `order=asc` 时，按 `value` 从小到大排序
    - 传 `order=desc` 时，按 `value` 从大到小排序
  - 如果选项不全为数字（包含非数字的 `value`），则不受 `order` 参数影响，保持按创建时间倒序排序（`created_at.desc()`）
- 只有管理员可以操作此接口（通过菜单权限控制）

**排序示例**:

- 假设字典选项的 `value` 为：["10", "2", "5", "1"]（全为数字）
  - 不传 `order` 或传 `order=asc`：排序结果为 ["1", "2", "5", "10"]
  - 传 `order=desc`：排序结果为 ["10", "5", "2", "1"]
- 假设字典选项的 `value` 为：["A", "B", "C"]（不全为数字）
  - 无论是否传 `order` 参数，都按创建时间倒序排序，不受 `order` 参数影响

##### 2.4.3 获取字典选项详情

**接口地址**: `GET /api/v1/config/dict-options/{option_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `option_id`: 字典选项ID（字符串格式）

**请求示例**: `GET /api/v1/config/dict-options/260819415803760651`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760651",
    "dict_type_id": "260819415803760650",
    "dict_type": "freight_code",
    "label": "运价代码",
    "value": "L",
    "status": 1,
    "color_type": "success",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**:

- 通过`id`获取字典选项详情
- `value` 返回单个字符串，与创建时传入的格式一致
- `color_type` 返回颜色类型（用于前端区分状态颜色），可能为 `null`（如果创建时未提供）
- 如果字典选项不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.4.4 更新字典选项

**接口地址**: `PUT /api/v1/config/dict-options/{option_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `option_id`: 字典选项ID（字符串格式）

**请求参数**（所有字段可选，传入的字段会更新）:

```json
{
  "dict_type": "freight_code_new",
  "label": "运价代码（更新）",
  "value": "X",
  "status": 0,
  "color_type": "error"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760651",
    "dict_type_id": "260819415803760652",
    "dict_type": "freight_code_new",
    "label": "运价代码（更新）",
    "value": "X",
    "status": 0,
    "color_type": "error",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:30:00+08:00"
  },
  "msg": "字典选项更新成功"
}
```

**说明**:

- 传入的字段会更新，未传入的保持原值
- 可以更新 `dict_type`、`label`、`value`、`status`、`color_type` 等所有字段
- `color_type` 字段可选，如果传入 `null` 或空字符串，会清空该字段
- 如果更新`dict_type`，会检查新的类型是否存在
- 如果字典选项不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

##### 2.4.5 删除字典选项

**接口地址**: `DELETE /api/v1/config/dict-options/{option_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `option_id`: 字典选项ID（字符串格式）

**请求示例**: `DELETE /api/v1/config/dict-options/260819415803760651`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760651",
    "dict_type": "freight_code",
    "label": "运价代码"
  },
  "msg": "字典选项删除成功"
}
```

**说明**:

- 通过`id`删除字典选项
- 如果字典选项不存在，返回404错误
- 只有管理员可以操作此接口（通过菜单权限控制）

---

### 3. 部门管理

> **说明**：此模块的查询接口（GET）面向所有活跃用户开放，新建、修改和删除操作仍需要管理员（admin）权限。

#### 3.1 新建部门（需要管理员权限）

**接口地址**: `POST /api/v1/departments`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "name": "技术部"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760641",
    "name": "技术部",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "部门创建成功"
}
```

#### 3.2 查看已创建部门

**接口地址**: `GET /api/v1/departments`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 2,
    "items": [
      {
        "id": "260819415803760641",
        "name": "技术部",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      },
      {
        "id": "260819415803760642",
        "name": "运营部",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 3.3 获取部门详情

**接口地址**: `GET /api/v1/departments/{department_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `department_id`: 部门ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760641",
    "name": "技术部",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**: 返回指定部门的详细信息

#### 3.4 修改部门（需要管理员权限）

**接口地址**: `PUT /api/v1/departments/{department_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `department_id`: 部门ID（字符串格式）

**请求参数**:

```json
{
  "name": "新技术部"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760641",
    "name": "新技术部",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:30:00+08:00"
  },
  "msg": "部门修改成功"
}
```

**说明**:

- 只能修改部门名称
- 新名称不能与其他部门重复

#### 3.5 删除部门（需要管理员权限）

**接口地址**: `DELETE /api/v1/departments/{department_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `department_id`: 部门ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "department_id": "260819415803760641",
    "department_name": "技术部",
    "affected_users_count": 5
  },
  "msg": "部门删除成功，已解除 5 个用户的关联关系"
}
```

**说明**:

- 删除部门会自动解除该部门与所有用户的关联关系（由数据库CASCADE处理）
- 删除后，原本只属于该部门的用户将没有部门归属
- 响应中包含受影响的用户数量

---

### 4. 账号管理（需要管理员权限）

#### 4.1 新增账号

**接口地址**: `POST /api/v1/users`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "phone": "13800138001",
  "password": "password123",
  "name": "张三",
  "department_ids": ["260819415803760641", "260819415803760642"],
  "permissions": ["organizational_management", "expense_registration"]
}
```

**前端权限代码选项**：`organizational_management`（组织管理）、`system`（系统管理）、`customer_service`（客服接单台）、`expense_registration`（费用登记台）、`admin`（管理员）。历史代码继续兼容，但新数据应使用这五个代码。

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760644",
    "phone": "13800138001",
    "name": "张三",
    "department_ids": ["260819415803760641", "260819415803760642"],
    "departments": [
      {"id": "260819415803760641", "name": "技术部"},
      {"id": "260819415803760642", "name": "运营部"}
    ],
    "permissions": ["organizational_management", "expense_registration"],
    "is_active": true,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "账号创建成功"
}
```

**说明**:

- 新增账号默认启用
- 手机号必须为11位数字且以1开头
- 密码长度6-50位
- 支持多个部门（`department_ids` 为数组）
- 权限使用固定权限代码（如 `organizational_management`, `expense_registration`）
- 权限列表中任意一项不在后端权限白名单时，接口返回 `400` 和“权限列表包含无效的权限”，账号不会创建

#### 4.2 查看已创建账号

**接口地址**: `GET /api/v1/users`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 2,
    "items": [
      {
        "id": "260819415803760640",
        "phone": "13800138000",
        "name": "管理员",
        "department_ids": ["260819415803760641"],
        "departments": [
          {"id": "260819415803760641", "name": "技术部"}
        ],
        "permissions": ["admin"],
        "is_active": true,
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      },
      {
        "id": "260819415803760644",
        "phone": "13800138001",
        "name": "张三",
        "department_ids": ["260819415803760641", "260819415803760642"],
        "departments": [
          {"id": "260819415803760641", "name": "技术部"},
          {"id": "260819415803760642", "name": "运营部"}
        ],
        "permissions": ["waybill", "booking"],
        "is_active": true,
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 4.3 获取账号详情

**接口地址**: `GET /api/v1/users/{user_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `user_id`: 用户ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760644",
    "phone": "13800138001",
    "name": "张三",
    "department_ids": ["260819415803760641", "260819415803760642"],
    "departments": [
      {"id": "260819415803760641", "name": "技术部"},
      {"id": "260819415803760642", "name": "运营部"}
    ],
    "permissions": ["waybill", "booking"],
    "is_active": true,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**: 返回指定账号的详细信息，包括所属部门和权限信息

#### 4.4 启用或停用账号（单个）

**接口地址**: `PUT /api/v1/users/{user_id}/status?is_active=true`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `user_id`: 用户ID（字符串格式）

**查询参数**:

- `is_active`: `true` 启用，`false` 停用

**响应示例**（停用）:

```json
{
  "code": 0,
  "data": {
    "user_id": "260819415803760644",
    "is_active": false
  },
  "msg": "账号已停用，该用户的所有登录凭证已失效"
}
```

**响应示例**（启用）:

```json
{
  "code": 0,
  "data": {
    "user_id": "260819415803760644",
    "is_active": true
  },
  "msg": "账号已启用"
}
```

**说明**:

- 停用账号时会递增该用户的 `token_version`，使其所有已有的 JWT（access_token 和 refresh_token）立即失效
- 被停用的用户使用缓存的 token 访问 API 时，会返回 401 错误（token已失效），前端应跳转到登录页面
- 被停用的用户尝试重新登录时，会被 `is_active` 检查拦截，返回 403 错误（"用户已被禁用"）
- 启用账号时不会影响 `token_version`，用户需要重新登录获取新的 token

#### 4.5 批量启用或停用账号

**接口地址**: `PUT /api/v1/users/batch-status`

**请求头**: `Authorization: Bearer <token>`

**请求体**:

```json
{
  "user_ids": ["260819415803760644", "260819415803760645", "260819415803760646"],
  "is_active": false
}
```

**响应示例**（批量停用）:

```json
{
  "code": 0,
  "data": {
    "count": 3,
    "is_active": false
  },
  "msg": "批量停用成功，共停用3个账号，所有登录凭证已失效"
}
```

**响应示例**（批量启用）:

```json
{
  "code": 0,
  "data": {
    "count": 3,
    "is_active": true
  },
  "msg": "批量启用成功，共启用3个账号"
}
```

**说明**:

- 批量停用账号时会递增每个用户的 `token_version`，使其所有已有的 JWT（access_token 和 refresh_token）立即失效
- 被停用的用户使用缓存的 token 访问 API 时，会返回 401 错误（token已失效），前端应跳转到登录页面
- 被停用的用户尝试重新登录时，会被 `is_active` 检查拦截，返回 403 错误（"用户已被禁用"）
- 启用账号时不会影响 `token_version`，用户需要重新登录获取新的 token

#### 4.6 修改用户信息

**接口地址**: `PUT /api/v1/users/{user_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `user_id`: 用户ID（字符串格式）

**请求参数**（所有字段都是可选的，传入值的就修改，没传值的就保留）:

```json
{
  "phone": "13800138001",
  "password": "newpassword123",
  "name": "张三",
  "department_ids": ["260819415803760641", "260819415803760642"],
  "permissions": ["waybill", "booking"]
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760644",
    "phone": "13800138001",
    "name": "张三",
    "department_ids": ["260819415803760641", "260819415803760642"],
    "departments": [
      {"id": "260819415803760641", "name": "技术部"},
      {"id": "260819415803760642", "name": "运营部"}
    ],
    "permissions": ["waybill", "booking"],
    "is_active": true,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:30:00+08:00"
  },
  "msg": "用户信息修改成功"
}
```

**说明**:

- 需要管理员权限
- 所有字段都是可选的，传入值的就修改该用户属性，没传值的就保留原值
- 如果修改了权限，该用户的JWT将失效，需要重新登录（返回消息中会提示）
- 手机号不能与其他用户重复
- 权限使用权限代码（如 `waybill`, `booking`）

#### 4.7 删除账号（单个）

**接口地址**: `DELETE /api/v1/users/{user_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `user_id`: 用户ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "user_id": "260819415803760644"
  },
  "msg": "账号删除成功"
}
```

**说明**: 不能删除自己的账号

#### 4.8 批量删除账号

**接口地址**: `DELETE /api/v1/users`

**请求头**: `Authorization: Bearer <token>`

**请求体**:

```json
{
  "user_ids": ["260819415803760644", "260819415803760645", "260819415803760646"]
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "count": 3
  },
  "msg": "批量删除成功"
}
```

---

### 5. 用户中心

#### 5.1 查看当前用户信息

**接口地址**: `GET /api/v1/user-center/info`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760640",
    "phone": "13800138000",
    "name": "管理员",
    "department_ids": ["260819415803760641", "260819415803760642"],
    "departments": [
      {"id": "260819415803760641", "name": "技术部"},
      {"id": "260819415803760642", "name": "运营部"}
    ],
    "permissions": ["admin"],
    "is_active": true,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**:

- 返回当前登录用户的完整信息
- 支持多个部门
- 权限返回权限代码

#### 5.2 重置当前用户登录密码

**接口地址**: `PUT /api/v1/user-center/password`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "old_password": "oldpassword123",
  "new_password": "newpassword123"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "密码重置成功"
}
```

**说明**:

- 此接口只能重置当前登录用户自己的密码
- 需要提供旧密码和新密码（两个都是必填项）
- 旧密码验证失败会返回错误

#### 5.3 获取当前登录用户姓名

**接口地址**: `GET /api/v1/user-center/username`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "username": "张三",
    "name": "张三",
    "phone": "13800000000"
  },
  "msg": "success"
}
```

**说明**:

- 返回当前登录用户的真实姓名和登录手机号
- 方便前端直接在各个模块预填或渲染操作人姓名

---

### 6. 客户管理

#### 6.1 新增客户信息

**接口地址**: `POST /api/v1/customers`

**请求头**: `Authorization: Bearer <token>`

**请求参数**（仅 `company_name` 必填，其余均为可选）:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_name | string | 是 | 承运单位/公司名称 |
| settlement_method | string | 否 | 结算方式 |
| rate | number | 否 | 费率(元/公斤)，未传默认 0 |
| contact_person | string | 否 | 联系人 |
| contact_phone | string | 否 | 联系电话 |

**最小请求示例**（仅必填）:

```json
{
  "company_name": "XX物流公司"
}
```

**完整请求示例**（含可选字段）:

```json
{
  "company_name": "XX物流公司",
  "settlement_method": "月结",
  "rate": 10.50,
  "contact_person": "李四",
  "contact_phone": "13800138002"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760647",
    "company_name": "XX物流公司",
    "settlement_method": "月结",
    "rate": 10.50,
    "contact_person": "李四",
    "contact_phone": "13800138002",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "客户创建成功"
}
```

**说明**:

- 仅 `company_name` 为必填；`settlement_method`、`rate`、`contact_person`、`contact_phone` 均为可选
- 未传的可选字段：字符串类默认存空字符串，`rate` 默认 0

#### 6.2 客户信息查询

**接口地址**: `GET /api/v1/customers`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `company_name`: 公司名称（模糊搜索，可选）
- `contact_person`: 联系人（模糊搜索，可选）
- `page`: 页码（默认1）
- `pageSize`: 每页数量（默认10，最大200）

**请求示例**: `GET /api/v1/customers?company_name=物流&contact_person=李&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 10,
    "items": [
      {
        "id": "260819415803760647",
        "company_name": "XX物流公司",
        "settlement_method": "月结",
        "rate": 10.50,
        "contact_person": "李四",
        "contact_phone": "13800138002",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 6.3 编辑客户信息

**接口地址**: `PUT /api/v1/customers/{customer_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `customer_id`: 客户ID（字符串格式）

**请求参数**（均为可选，仅更新传入的字段，未传字段保持原值）:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| company_name | string | 否 | 承运单位/公司名称 |
| settlement_method | string | 否 | 结算方式 |
| rate | number | 否 | 费率(元/公斤) |
| contact_person | string | 否 | 联系人 |
| contact_phone | string | 否 | 联系电话 |

**请求示例**（只更新联系人和电话）:

```json
{
  "contact_person": "王五",
  "contact_phone": "13900139000"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760647",
    "company_name": "XX物流公司",
    "settlement_method": "月结",
    "rate": 10.50,
    "contact_person": "王五",
    "contact_phone": "13900139000",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T14:30:00+08:00"
  },
  "msg": "客户信息更新成功"
}
```

**说明**:

- 部分更新：仅更新请求体中传入的字段，未传字段保持原值
- 若某字段传 `null`，该字段会被置为空字符串（字符串类）或 0（rate）

#### 6.4 获取客户详情

**接口地址**: `GET /api/v1/customers/{customer_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `customer_id`: 客户ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760647",
    "company_name": "XX物流公司",
    "settlement_method": "月结",
    "rate": 10.50,
    "contact_person": "李四",
    "contact_phone": "13800138002",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

---

### 7. 运单管理

#### 7.1 新增运单

**接口地址**: `POST /api/v1/waybills`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

- **form_data**（必填）：表单数据（JSON格式），根据航司类型包含不同的字段结构

`form_data` 是一个字典结构，根据选择的航司（airline字段）包含不同的字段结构（所有键名使用英文，遵循snake_case命名规范）：

**深圳航空完整数据结构示例**（airline 可以是 "1" 或 "深圳航空"）:

```json
{
  "form_data": {
    "airline": "1",  // 或 "深圳航空"
    "flight_info": {
      "destination": "北京",
      "flight_date": "2025-01-15",
      "flight_number": "ZH1234",
      "origin_station": "SZX",
      "waybill_type": "普通运单"  // 可选，运单类型
    },
    "shipper_consignee_info": {
      "consignee_info": "收货人信息",
      "shipper_info": "发货人信息",
      "shipper_unit": "XX物流公司"
    },
    "cargo_info": {
      "quantity": "10",
      "weight": "100.5",
      "chargeable_weight": "105.0",
      "freight_code": "L",
      "cargo_code": "0001",
      "cargo_name": "普通货物",
      "package": "纸箱",
      "storage_and_transportation_precautions": "",
    },
    "other_fees": {
      "packaging_fee": "50.00",
      "pickup_fee": "100.00",
      "delivery_fee": "150.00"
    },
    "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "1",  // 充氧类水生动物货物收运检查单开关，"0"=需要生成，"1"或不传=不需要生成
      "pickup_method": "1"
    "declaration_list": "0",  // 航空货物明细表开关，"0"=需要生成航空货物明细表，其他值或不传=不需要生成
    "airline_consent_certificate": "",  // 航空公司同意运输证明编号，非空时替换交接单中的"深航安检编号：74"
    "oxygen_supply_test_results": ""  // 充氧类检查结果（蔬菜品名等），用于充氧类水生动物货物收运检查单中的检查结果替换
  }
}
```

**南方航空完整数据结构示例**（airline 可以是 "2" 或 "南方航空"）:

```json
{
  "form_data": {
    "airline": "2",  // 或 "南方航空"
    "flight_info": {
      "destination": "北京",
      "flight_date": "2025-01-15",
      "flight_number": "CZ5678",
      "booking_remark": "备注信息",
      "origin_station": "CAN"
    },
    "cargo_info": {
      "cargo_type": "普通货物",
      "cargo_code": "0001",
      "cargo_name": "货物名称",
      "quantity": "10",
      "weight": "100.5",
      "product_name": "产品名称",
          "booking_volume": "2.5",
      "oversized_cargo": "否",
      "booking_volume": "2.5",
      "product_name": "产品名称",
      "oversized_cargo": "否",
      "special_cargo_code": "",
      "storage_and_transportation_precautions": "",
    },
    "contact_info": {
      "consignee": "收货人",
      "consignee_phone": "13800138000",
      "shipper_unit": "XX物流公司",
      "shipper": "托运人",
      "shipper_phone": "13900139000",
      "address": {
        "region": "广东省/深圳市/南山区",
        "detail": "科技园南区"
      }
    },
    "dangerous_goods_declaration": {
      "no_hidden_dangerous_goods": "是",
      "agent_checker_signature": "检查人签字",
      "agent_consignor_signature": "交运人签字"
    },
    "other_info": {
      "order_contact": "订单联系人",
      "contact_phone": "13700137000",
      "settlement_file_number": "SF001"
    },
    "other_fees": {
      "packaging_fee": "50.00",
      "pickup_fee": "100.00",
      "delivery_fee": "150.00"
    },
    "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "1",  // 充氧类水生动物货物收运检查单开关，"0"=需要生成，"1"或不传=不需要生成
      "pickup_method": "1"
    "oxygen_supply_test_results": ""  // 充氧类检查结果（蔬菜品名等），用于充氧类水生动物货物收运检查单中的检查结果替换
  }
}
```

**响应示例**（深圳航空）:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": null,
    "form_data": {
      "airline": "深圳航空",
      "flight_info": {
        "destination": "北京",
        "flight_date": "2025-01-15",
        "flight_number": "ZH1234",
        "origin_station": "SZX"
      },
      "shipper_consignee_info": {
        "consignee_info": "收货人信息",
        "shipper_info": "发货人信息",
        "shipper_unit": "XX物流公司"
      },
      "cargo_info": {
        "quantity": "10",
        "weight": "100.5",
        "chargeable_weight": "105.0",
        "freight_code": "L",
        "cargo_code": "0001",
        "cargo_name": "普通货物",
        "package": "纸箱",
      "storage_and_transportation_precautions": "",
      },
      "other_fees": {
        "packaging_fee": "50.00",
        "pickup_fee": "100.00",
        "delivery_fee": "150.00"
      }
    },
    "airline_record_status": "0",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-01T12:00:00+08:00",
    "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
    "document_print_time": "2025-01-01T12:00:00+08:00",
    "departure_time": null,
    "booking_date": "2025-01-01",
    "rpa_work_uuid": null,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "运单创建成功"
}
```

**form_data字段结构详细说明**:

- **airline**（必填）：航司标识，可以是字典值（`"1"`=深圳航空，`"2"`=南方航空）或字符串（`"深圳航空"`、`"南方航空"`）。前端通过数据字典选择航司时，通常传入字典值（"1"或"2"）

**深圳航空字段结构**：

- **flight_info**（航班信息）：
  - `destination`：到达站
  - `flight_date`：航班日期
  - `flight_number`：航班号
  - `origin_station`：始发站
  - `waybill_type`：运单类型（可选，仅深圳航空，如：普通运单、加急运单等）
- **shipper_consignee_info**（收发货人信息）：
  - `consignee_info`：收货人信息
  - `shipper_info`：发货人信息
  - `shipper_unit`：托运单位
- **cargo_info**（货物信息）：
  - `quantity`：件数
  - `weight`：重量
  - `chargeable_weight`：计费重量
  - `freight_code`：运价代码
  - `cargo_code`：货物代码
  - `cargo_name`：货物名称
  - `package`：包装
  - `storage_and_transportation_precautions`：储运注意事项（可选）
- **other_fees**（其他费用信息）：
  - `packaging_fee`：包装费
  - `pickup_fee`：上门提货费
  - `delivery_fee`：派送费
- **oxygenated_aquatic_animal_goods_receipt_inspection_form_switch**（可选）：充氧类水生动物货物收运检查单开关，`"0"`表示需要生成该文档，`"1"`或不传表示不需要生成
  - **pickup_method**：可选。提货方式（独立字段，不参与RPA开单）
- **declaration_list**（可选）：航空货物明细表开关，`"0"`表示需要生成航空货物明细表，其他值或不传表示不需要生成
- **airline_consent_certificate**（可选）：航空公司同意运输证明编号，非空时替换交接单中的"深航安检编号：74"
- **oxygen_supply_test_results**（可选）：充氧类检查结果（蔬菜品名等），用于充氧类水生动物货物收运检查单中的检查结果替换

**南方航空字段结构**：

- **flight_info**（航班信息）：
  - `destination`：到达站
  - `flight_date`：航班日期
  - `flight_number`：航班号
  - `booking_remark`：订舱备注
  - `origin_station`：始发站
- **cargo_info**（货物信息）：
  - `cargo_type`：货物类型
  - `cargo_code`：货物代码
  - `cargo_name`：货物名称
  - `quantity`：件数
  - `weight`：重量
  - `booking_volume`：订舱体积
  - `product_name`：产品名称（如果是非空列表自动提取第一项）
- `booking_volume`：订舱体积
  - `oversized_cargo`：超规货
  - `booking_volume`：订舱体积（可选）
  - `product_name`：产品名称（如果是非空列表自动提取第一项）
  - `oversized_cargo`：超规货
  - `special_cargo_code`：特货码
  - `storage_and_transportation_precautions`：储运注意事项（可选）
- **contact_info**（联系人信息）：
  - `consignee`：收货人
  - `consignee_phone`：手机号（收货人）
  - `shipper_unit`：托运单位
  - `shipper`：托运人
  - `shipper_phone`：手机号（托运人）
  - `address`：地址（对象类型，包含 `region` 省/市/区和 `detail` 详细地址）
- **dangerous_goods_declaration**（防止隐含危险品货物运输声明）：
  - `no_hidden_dangerous_goods`：该票货物无隐含危险品
  - `agent_checker_signature`：代理公司检查人签字
  - `agent_consignor_signature`：代理公司交运人签字
- **other_info**（其他信息）：
  - `order_contact`：订单联系人
  - `contact_phone`：联系人电话
  - `settlement_file_number`：结算文件号
- **other_fees**（其他费用信息）：
  - `packaging_fee`：包装费
  - `pickup_fee`：上门提货费
  - `delivery_fee`：派送费
- **oxygenated_aquatic_animal_goods_receipt_inspection_form_switch**（可选）：充氧类水生动物货物收运检查单开关，`"0"`表示需要生成该文档，`"1"`或不传表示不需要生成
  - **pickup_method**：可选。提货方式（独立字段，不参与RPA开单）
- **oxygen_supply_test_results**（可选）：充氧类检查结果（蔬菜品名等），用于充氧类水生动物货物收运检查单中的检查结果替换

**说明**:

- `form_data` 根据航司类型包含不同的字段结构，前端需要根据 `airline` 字段来展示对应的表单字段
- **airline 字段说明**：可以是字典值（"1"=深圳航空，"2"=南方航空）或字符串（"深圳航空"、"南方航空"）。前端通过数据字典选择航司时，通常传入字典值
- **深圳航空说明**：深圳航空的运单可以选择性提供 `flight_info.waybill_type` 字段（运单类型），南方航空不需要此字段
- 所有字段的值都是字符串类型
- `address` 是对象类型，包含 `region`（省/市/区）和 `detail`（详细地址）两个字段
- `booking_date`：自动设置为当前日期（中国时间）
- 所有执行状态默认为数据字典值"0"（未执行）
- `waybill_number` 和 `departure_time` 由RPA后续写入，初始为 `null`
- 执行状态使用数据字典值：`"0"`（未执行）、`"1"`（执行中）、`"2"`（失败）

#### 7.2 查询运单列表

**接口地址**: `GET /api/v1/waybills`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `airline_record_status`: 航司录单执行状态筛选（数据字典值精确匹配，可选：`"0"`=未开单，`"1"`=开单中，`"2"`=失败，`"3"`=成功）
- `cargo_station_record_status`: 货站录单执行状态筛选（数据字典值精确匹配，可选：`"0"`=未执行，`"1"`=执行中，`"2"`=失败，`"3"`=已录单）
- `document_print_status`: 单据打印执行状态筛选（数据字典值精确匹配，可选：`"0"`=未执行，`"1"`=执行中，`"2"`=失败，`"3"`=成功）
- `booking_date_start`: 开单日期开始（格式：YYYY-MM-DD，可选）
- `booking_date_end`: 开单日期结束（格式：YYYY-MM-DD，可选）
- `airline`: 航司（数据字典值精确匹配，可选：`"1"`=深圳航空，`"2"`=南方航空）
- `destination`: 目的站（城市名称模糊搜索，如输入"西宁"会转换为三字码"XNN"后匹配；也可直接输入三字码如"PEK"，可选）
- `flight_number`: 航班号（模糊搜索，从form_data.flight_info.flight_number中提取，可选）
- `waybill_type`: 运单类型（数据字典值精确匹配，仅深圳航空，可选：`"0"`=普通运单，`"1"`=急件运单，`"2"`=鲜活运单等）
- `shipper`: 托运单位（模糊搜索，从form_data中提取，支持深圳航空的shipper_consignee_info.shipper_unit和南方航空的contact_info.shipper_unit，可选）
- `waybill_number`: 运单号（模糊搜索，可选）
- `page`: 页码（默认1）
- `pageSize`: 每页数量（默认10，最大200）

**请求示例**: `GET /api/v1/waybills?airline_record_status=0&booking_date_start=2025-01-01&booking_date_end=2025-01-31&airline=1&destination=西宁&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 10,
    "items": [
      {
        "id": "260819415803760648",
        "waybill_number": "WB123456789",
        "form_data": {
          "airline": "1",
          "flight_info": {
            "destination": "XNN",
            "flight_date": "2025-01-15",
            "flight_number": "ZH1234",
            "origin_station": "SZX",
            "waybill_type": "0"
          },
          "shipper_consignee_info": {
            "consignee_info": "收货人信息",
            "shipper_info": "发货人信息",
            "shipper_unit": "XX物流公司"
          },
          "cargo_info": {
            "quantity": "10",
            "weight": "100.5",
            "chargeable_weight": "105.0",
            "freight_code": "L",
            "cargo_code": "0001",
            "cargo_name": "普通货物",
            "package": "纸箱",
      "storage_and_transportation_precautions": "",
          },
          "other_fees": {
            "packaging_fee": "50.00",
            "pickup_fee": "100.00",
            "delivery_fee": "150.00"
          }
        },
        "airline_record_status": "0",
        "cargo_station_record_status": "0",
        "document_print_status": "0",
        "waybill_void_status": "0",
        "airline_record_time": "2025-01-01T12:00:00+08:00",
        "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
        "document_print_time": "2025-01-01T12:00:00+08:00",
        "departure_time": "2025-01-01T14:00:00+08:00",
        "booking_date": "2025-01-01",
        "rpa_work_uuid": "360ccb96184964381549f7f366979bcb",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**说明**:

- 支持多条件组合筛选
- 执行状态筛选（`airline_record_status`、`cargo_station_record_status`、`document_print_status`）使用数据字典值精确匹配（如`"0"`、`"1"`、`"2"`、`"3"`）
- `airline`（航司）使用数据字典值精确匹配（`"1"`=深圳航空，`"2"`=南方航空）
- `waybill_type`（运单类型）使用数据字典值精确匹配（仅深圳航空）
- `destination`（目的站）支持城市名称模糊搜索（如输入"西宁"会匹配到"西宁曹家堡机场"对应的三字码"XNN"），也可直接输入三字码（如"PEK"）
- `flight_number`（航班号）、`shipper`（托运单位）、`waybill_number`（运单号）使用模糊搜索
- 日期范围筛选支持 YYYY-MM-DD 格式

#### 7.3 查询运单详情

**接口地址**: `GET /api/v1/waybills/{waybill_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `waybill_id`: 运单ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": "WB123456789",
    "form_data": {
      "airline": "深圳航空",
      "flight_info": {
        "destination": "北京",
        "flight_date": "2025-01-15",
        "flight_number": "ZH1234",
        "origin_station": "SZX"
      },
      "shipper_consignee_info": {
        "consignee_info": "收货人信息",
        "shipper_info": "发货人信息",
        "shipper_unit": "XX物流公司"
      },
      "cargo_info": {
        "quantity": "10",
        "weight": "100.5",
        "chargeable_weight": "105.0",
        "freight_code": "L",
        "cargo_code": "0001",
        "cargo_name": "普通货物",
        "package": "纸箱",
      "storage_and_transportation_precautions": "",
      },
      "other_fees": {
        "packaging_fee": "50.00",
        "pickup_fee": "100.00",
        "delivery_fee": "150.00"
      }
    },
    "airline_record_status": "0",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-01T12:00:00+08:00",
    "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
    "document_print_time": "2025-01-01T12:00:00+08:00",
    "departure_time": "2025-01-01T14:00:00+08:00",
    "booking_date": "2025-01-01",
    "rpa_work_uuid": "360ccb96184964381549f7f366979bcb",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**: 返回运单的完整信息，包括所有表单数据和执行状态。`rpa_work_uuid`字段在运单执行后会有值，用于查询RPA执行状态。

**状态变更时间字段说明**:

- `airline_record_time`: 航司录单状态最近一次变更的时间（当 `airline_record_status` 变为 `"0"`/`"1"`/`"2"`/`"3"` 时自动记录）
- `cargo_station_record_time`: 货站录单状态最近一次变更的时间（当 `cargo_station_record_status` 变为 `"0"`/`"1"`/`"2"`/`"3"` 时自动记录）
- `document_print_time`: 单据打印状态最近一次变更的时间（当 `document_print_status` 变为 `"0"`/`"1"`/`"2"`/`"3"` 时自动记录）

#### 7.4 修改运单信息

**接口地址**: `PUT /api/v1/waybills/{waybill_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `waybill_id`: 运单ID（字符串格式）

**请求参数**:

- **form_data**（必填）：表单数据（JSON格式），与新增运单结构一致，整体替换原 form_data
- **booking_date**（可选）：开单日期（格式：YYYY-MM-DD），不传则不修改原值

**请求示例**:

```json
{
  "form_data": {
    "airline": "1",
    "flight_info": {
      "destination": "XNN",
      "flight_date": "2025-01-16",
      "flight_number": "ZH1234",
      "origin_station": "SZX",
      "waybill_type": "0"
    },
    "shipper_consignee_info": {
      "consignee_info": "收货人信息",
      "shipper_info": "发货人信息",
      "shipper_unit": "XX物流公司"
    },
    "cargo_info": {
      "quantity": "10",
      "weight": "100.5",
      "chargeable_weight": "105.0",
      "freight_code": "L",
      "cargo_code": "0001",
      "cargo_name": "普通货物",
      "package": "纸箱",
      "storage_and_transportation_precautions": "",
    },
    "other_fees": {
      "packaging_fee": "50.00",
      "pickup_fee": "100.00",
      "delivery_fee": "150.00"
    }
  },
  "booking_date": "2025-01-02"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": null,
    "form_data": { ... },
    "airline_record_status": "0",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-01T12:00:00+08:00",
    "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
    "document_print_time": "2025-01-01T12:00:00+08:00",
    "departure_time": null,
    "booking_date": "2025-01-02",
    "rpa_work_uuid": null,
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-02T10:00:00+08:00"
  },
  "msg": "运单修改成功"
}
```

**说明**:

- **可修改条件**：仅当运单处于「未开单」（`airline_record_status="0"`）或「开单失败」（`airline_record_status="2"`）时允许修改；开单中（`"1"`）或已成功（`"3"`）的运单不可修改。修改后可通过执行接口重新开单
- **可修改字段**：`form_data`（必传，整体替换）、`booking_date`（可选）
- **不可通过本接口修改的字段**：`waybill_number`、`departure_time`、各执行状态等由系统或 RPA 维护
- `form_data` 结构与新增运单接口一致，详见 7.1 新增运单

#### 7.5 确认并执行运单

**接口地址**: `POST /api/v1/waybills/{waybill_id}/execute`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `waybill_id`: 运单ID（字符串格式）

**功能说明**:

- 此接口用于确认并执行运单，会调用RPA接口进行自动化处理
- 当前仅支持深圳航空的运单（airline="1"或"深圳航空"）
- **队列管理流程**：
  1. **流程运行开始-新增队列**：在调用RPA接口之前，系统会循环创建4个队列，队列名称分别为：
     - `shenzhen_air_kaidan_queue_waybill_number`（运单号队列）
     - `shenzhen_air_kaidan_queue_freight_rate`（费率队列）
     - `shenzhen_air_kaidan_queue_freight`（运费队列）
     - `shenzhen_air_kaidan_queue_delivery_fee`（派送费队列）
     每个开单都会创建独立的队列实例
  2. **流程运行过程中-数据存入队列**：RPA执行过程中会将数据存入对应的队列
  3. **流程运行结束-用本次新增的队列id查询队列数据**：当RPA执行状态变为"执行成功"（status=5，系统状态为"3"）时，系统会循环从4个队列中获取数据：
     - 从运单号队列获取数据，格式化后（加"479-"前缀）保存到`waybill_number`字段
     - 从费率队列获取数据，用于构建结算单的`master_rate`字段
     - 从运费队列获取数据，用于构建结算单的`master_airline_fee`字段
     - 从派送费队列获取数据，用于构建结算单的`master_delivery_fee`字段
     - 获取数据后，会创建结算单记录，将处理后的数据保存到`settlements`表的`form_data`字段
  4. **流程运行结束-队列删除**：
     - **成功时**：获取所有队列数据并创建结算单后，系统会自动删除所有4个队列
     - **失败时**：如果RPA执行失败（status=3，系统状态为"2"），系统也会自动清理所有队列
     - **无论成功还是失败，只要流程结束，都会删除所有队列**
- 接口会从运单的form_data中提取参数并调用深航新增运单任务RPA接口
- 调用成功后，会保存RPA返回的workUuid和队列信息到数据库
- 同时启动后台任务自动轮询RPA执行状态，并更新运单的airline_record_status字段

**请求参数说明**:

- 接口不需要请求体，所有参数从运单的form_data和业务参数配置中提取
- **参数优先级**：优先使用form_data中的值，如果form_data中没有，则从业务参数配置中的深航数据部分获取
- 对于深圳航空，RPA接口需要的参数包括：
  - **从业务参数配置获取**（config_data.shenzhen_air.booking.shenzhen_air_login）：
    - `system_url`: 系统URL
    - `system_account`: 系统账号
    - `login_password`: 登录密码
  - **优先使用form_data，如果没有则使用业务参数配置**（config_data.shenzhen_air.booking.business_default）：
    - `flight_info.origin_station`: 始发站（如：SZX）
    - `flight_info.destination`: 目的站（如：TAO）
    - `flight_info.flight_date`: 航班日期（格式：YYYY-MM-DD，如：2026-01-15）
    - `flight_info.flight_number`: 航班号（如：ZH9911）
    - `flight_info.waybill_type`: 运单类型（可选，可能为空）
    - `shipper_consignee_info.shipper_info`: 发货人信息
    - `shipper_consignee_info.consignee_info`: 收货人信息
    - `cargo_info.quantity`: 件数
    - `cargo_info.weight`: 重量
    - `cargo_info.chargeable_weight`: 计费重量
    - `cargo_info.freight_code`: 运价代码（如：GEN）
    - `cargo_info.cargo_code`: 货物代码（如：044）
    - `cargo_info.cargo_name`: 货物名称（如：衣物）
    - `cargo_info.package`: 包装（如：麻袋）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": null,
    "form_data": {
      "airline": "1",
      "flight_info": {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-01-15",
        "flight_number": "ZH9911",
        "waybill_type": "普通运单"
      },
      "shipper_consignee_info": {
        "shipper_info": "张三",
        "consignee_info": "李四",
        "shipper_unit": "XX物流公司"
      },
      "cargo_info": {
        "quantity": "1",
        "weight": "5",
        "freight_code": "GEN",
        "cargo_code": "044",
        "cargo_name": "衣物",
        "package": "麻袋"
      }
    },
    "airline_record_status": "1",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-01T12:00:00+08:00",
    "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
    "document_print_time": "2025-01-01T12:00:00+08:00",
    "departure_time": null,
    "booking_date": "2025-01-01",
    "rpa_work_uuid": "360ccb96184964381549f7f366979bcb",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "运单执行成功，正在处理中"
}
```

**说明**:

- 接口调用成功后，`airline_record_status`会更新为"1"（开单中，对应数据字典invoice_status的value="1"）
- `rpa_work_uuid`字段会保存RPA返回的workUuid，用于后续查询RPA执行状态
- 后台任务会自动轮询RPA状态，当状态变为成功(5)或失败(3)时，会更新`airline_record_status`为对应的数据字典值
- **运单号自动获取**：当RPA执行状态变为"执行成功"（status=5，系统状态为"3"）时，系统会从运单号队列获取数据，格式化后（加"479-"前缀）保存到`waybill_number`字段
- **结算单自动创建**：当RPA执行状态变为"执行成功"（status=5）时，系统会从4个队列中获取数据，处理后创建结算单记录，保存到`settlements`表。结算单默认值：
  - `settlement_status`: "0"（未结算）
  - `financial_review`: "0"（未审核）
  - 运单`form_data.other_fees`中的费用会自动同步到结算单：
    - `other_fees.packaging_fee` → `settlement.form_data.sub_packaging_fee`（包装费）
    - `other_fees.pickup_fee` → `settlement.form_data.sub_pickup_fee`（上门提货费）
    - `other_fees.delivery_fee` → `settlement.form_data.sub_delivery_fee`（派送费）
- **队列自动清理**：获取所有队列数据并创建结算单后，系统会自动删除所有4个队列。如果RPA执行失败（status=3），系统也会自动清理所有队列
- **允许重复执行**：如果运单已经执行过（已有rpa_work_uuid），可以重复执行，会覆盖之前的rpa_work_uuid和队列信息
- 如果业务参数配置不存在，会返回错误
- 如果创建队列失败，会返回错误，不会继续调用RPA接口
- 如果运单的airline不是深圳航空，会返回错误
- 如果缺少必填参数（包括业务参数配置中的登录信息），会返回错误

**RPA状态映射说明**:

- `airline_record_status`字段存储的是数据字典的值，不是中文描述。前端通过数据字典（dict_type="invoice_status"）将值转换为对应的中文显示
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (开单中) -> airline_record_status="1"（对应数据字典：value="1", label="开单中"）
  - status=3 (失败) -> airline_record_status="2"（对应数据字典：value="2", label="失败"）
  - status=5 (运行成功) -> airline_record_status="3"（对应数据字典：value="3", label="成功"），同时自动获取运单号并保存到`waybill_number`字段
- **重要**：即使RPA返回成功（status=5），如果获取运单号失败（`waybill_number`为空），系统会将`airline_record_status`设置为"2"（失败），因为运单号是开单成功的必要条件

**轮询配置说明**:

- 轮询间隔和最大轮询次数可在配置文件中配置（`RPA_POLL_INTERVAL`和`RPA_POLL_MAX_COUNT`）
- 默认配置：每5秒轮询一次，最多轮询60次（即最多轮询5分钟）
- 当RPA状态变为成功(5)或失败(3)时，停止轮询

#### 7.6 运单作废

**接口地址**: `POST /api/v1/waybills/{waybill_id}/void`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `waybill_id`: 运单ID（字符串格式）

**功能说明**:

- 此接口用于作废运单，会调用RPA接口进行自动化处理
- 支持深圳航空和南方航空的运单作废：
  - 深圳航空：airline="1"或"深圳航空"
  - 南方航空：airline="2"或"南方航空"
- 接口会从运单的waybill_number中提取运单号后八位：
  - 深航：去除"479-"前缀（如：479-58841145 -> 58841145）
  - 南航：去除"784-"前缀（如：784-47888190 -> 47888190）
- 调用成功后，会保存RPA返回的workUuid到数据库（覆盖之前的rpa_work_uuid）
- 同时启动后台任务自动轮询RPA作废执行状态，并更新运单的waybill_void_status字段
- **重要**：当RPA作废成功时，系统会更新运单作废状态为"3"（作废成功），但会保留记录用于留痕，不会删除运单记录
- 当RPA作废成功时，系统会自动同步运单作废状态到对应的结算单（通过master_airwaybill_number匹配）

**请求参数说明**:

- 接口不需要请求体，所有参数从运单数据中提取
- 运单必须已有waybill_number（运单号），否则无法作废
- 运单号格式要求：
  - 深航：格式为"479-XXXXXXXX"（如：479-58841145），系统会自动提取后八位"58841145"
  - 南航：格式为"784-XXXXXXXX"（如：784-47888190），系统会自动提取后八位"47888190"

**响应示例**（深航）:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": "479-58841145",
    "form_data": {
      "airline": "1",
      "flight_info": {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-01-15",
        "flight_number": "ZH9911"
      }
    },
    "airline_record_status": "3",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "1",
    "departure_time": null,
    "booking_date": "2025-01-01",
    "rpa_work_uuid": "360ccb96184964381549f7f366979bcb",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00",
    "task_id": "260819415803760650"
  },
  "msg": "运单作废已加入执行队列，请等待处理"
}
```

**响应示例**（南航）:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760649",
    "waybill_number": "784-47888190",
    "form_data": {
      "airline": "2",
      "flight_info": {
        "origin_station": "CAN",
        "destination": "PEK",
        "flight_date": "2026-01-15",
        "flight_number": "CZ1234"
      }
    },
    "airline_record_status": "3",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "1",
    "departure_time": null,
    "booking_date": "2025-01-01",
    "rpa_work_uuid": "360ccb96184964381549f7f366979bcb",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00",
    "task_id": "260819415803760651"
  },
  "msg": "运单作废已加入执行队列，请等待处理"
}
```

**说明**:

- 接口调用成功后，`waybill_void_status`会更新为"1"（作废中，对应数据字典invoice_status的value="1"）
- `rpa_work_uuid`字段会保存RPA返回的workUuid（覆盖之前的workUuid），用于后续查询RPA执行状态
- `task_id`字段返回RPA任务ID，可用于查询任务执行状态
- 后台任务会自动轮询RPA作废状态，当状态变为成功(5)或失败(3)时，会更新`waybill_void_status`为对应的数据字典值
- **重要**：当RPA作废状态变为成功(5)时，系统会更新运单作废状态为"3"（作废成功），但会保留记录用于留痕，不会删除运单记录
- **结算单同步**：当RPA作废成功时，系统会自动查找并更新对应的结算单（通过master_airwaybill_number匹配），将结算单的waybill_void_status字段更新为"3"（作废成功）
- 如果运单号不存在，会返回错误
- 如果运单的airline不是深圳航空或南方航空，会返回错误
- 如果运单号格式不正确（无法提取后八位），会返回错误
- 如果该运单已有待执行或执行中的作废任务，会返回错误

**RPA作废状态映射说明**:

- `waybill_void_status`字段存储的是数据字典的值，不是中文描述。前端通过数据字典（dict_type="invoice_status"）将值转换为对应的中文显示
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (作废中) -> waybill_void_status="1"（对应数据字典：value="1", label="开单中"）
  - status=3 (失败) -> waybill_void_status="2"（对应数据字典：value="2", label="失败"）
  - status=5 (运行成功) -> waybill_void_status="3"（对应数据字典：value="3", label="成功"），**保留记录用于留痕，不删除**

**轮询配置说明**:

- 轮询间隔和最大轮询次数可在配置文件中配置（`RPA_POLL_INTERVAL`和`RPA_POLL_MAX_COUNT`）
- 默认配置：每5秒轮询一次，最多轮询60次（即最多轮询5分钟）
- 当RPA状态变为成功(5)或失败(3)时，停止轮询

#### 7.7 南航新增运单

**接口地址**: `POST /api/v1/waybills/{waybill_id}/execute-china-southern-air`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `waybill_id`: 运单ID（字符串格式）

**功能说明**:

- 此接口专门用于南方航空（airline="2"或"南方航空"）的运单执行/开单
- 功能与南航订舱执行+直接开单的整合效果类似，但此接口是针对运单管理模块
- 接口会从运单的form_data中提取RPA所需的参数，优先使用form_data中的值，如果没有则从业务参数配置的南航部分获取
- 调用时会创建5个队列用于获取RPA返回的数据：运单号(waybill_number)、费率(freight_rate)、运费(freight)、燃油费(fuel_costs)、延伸服务费(extended_service_fee)
- RPA任务完成后（无论成功或失败），都会销毁这5个队列
- 成功时会从队列中获取数据后再销毁，并自动创建结算单
- 调用成功后，会保存RPA返回的workUuid到数据库
- 同时启动后台任务自动轮询RPA执行状态，并更新运单的airline_record_status字段

**请求参数说明**:

- 接口不需要请求体，所有参数从运单的form_data中提取
- 运单的airline字段必须是"2"或"南方航空"，否则会返回错误
- 如果运单缺少必填参数，会返回错误并提示缺少哪些参数

**form_data参数提取说明**（参数优先级：form_data > 业务参数配置）:

| 参数名 | 来源路径 | 说明 |
|-------|---------|------|
| system_url | 业务参数配置 | 南航系统URL |
| system_account | 业务参数配置 | 南航系统账号 |
| login_password | 业务参数配置 | 南航系统密码 |
| address_of_the_application_executable_file_tangyi | 业务参数配置 | 唐易应用可执行文件地址 |
| origin_station | form_data.flight_info.origin_station | 始发站 |
| destination | form_data.flight_info.destination | 目的站 |
| flight_date | form_data.flight_info.flight_date | 航班日期 |
| flight_number | form_data.flight_info.flight_number | 航班号 |
| booking_remark | form_data.flight_info.booking_remark | 订舱备注 |
| cargo_type | form_data.cargo_info.cargo_type | 货物类型 |
| cargo_code | form_data.cargo_info.cargo_code | 货物代码 |
| cargo_name | form_data.cargo_info.cargo_name | 货物名称 |
| quantity | form_data.cargo_info.quantity | 件数 |
| weight | form_data.cargo_info.weight | 重量 |
| special_cargo_code | form_data.cargo_info.special_cargo_code | 特货码 |
| oversized_cargo | form_data.cargo_info.oversized_cargo | 超规货 |
| consignee | form_data.contact_info.consignee | 收货人 |
| consignee_phone | form_data.contact_info.consignee_phone | 收货人电话 |
| shipper | form_data.contact_info.shipper | 发货人 |
| shipper_phone | form_data.contact_info.shipper_phone | 发货人电话 |
| region_province_shipper | form_data.contact_info.address.region[0] | 发货人省 |
| region_city_shipper | form_data.contact_info.address.region[1] | 发货人市 |
| region_city_district | form_data.contact_info.address.region[2] | 发货人区 |
| address_detail | form_data.contact_info.address.detail | 详细地址 |
| order_contact_name | form_data.other_info.order_contact | 订单联系人姓名 |
| order_contact_phone | form_data.other_info.contact_phone | 订单联系人电话 |
| settlement_file_number | form_data.other_info.settlement_file_number | 结算文件号 |
| agent_checker_name | form_data.dangerous_goods_declaration.agent_checker_signature | 代理检查人签字 |
| agent_consignor_name | form_data.dangerous_goods_declaration.agent_consignor_signature | 代理交运人签字 |
| no_dangerous_goods | form_data.dangerous_goods_declaration.no_hidden_dangerous_goods | 无隐含危险品声明 |

**必填参数**:

- address_of_the_application_executable_file_tangyi
- system_account
- login_password
- system_url
- origin_station
- destination
- flight_date
- flight_number
- cargo_name
- quantity
- weight
- consignee
- consignee_phone
- shipper
- shipper_phone

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760648",
    "waybill_number": null,
    "form_data": {
      "airline": "2",
      "flight_info": {
        "origin_station": "CAN",
        "destination": "PEK",
        "flight_date": "2026-01-15",
        "flight_number": "CZ1234",
        "booking_remark": "测试备注"
      },
      "cargo_info": {
        "cargo_type": "普通货物",
        "cargo_code": "0001",
        "cargo_name": "测试货物",
        "quantity": "10",
        "weight": "100.5",
        "oversized_cargo": "否",
        "special_cargo_code": "",
      "storage_and_transportation_precautions": "",
      },
      "contact_info": {
        "consignee": "测试收货人",
        "consignee_phone": "13800138000",
        "shipper": "测试发货人",
        "shipper_phone": "13900139000",
        "shipper_unit": "XX物流公司",
        "address": {
          "region": "广东省/深圳市/南山区",
          "detail": "科技园南区"
        }
      },
      "dangerous_goods_declaration": {
        "no_hidden_dangerous_goods": "是",
        "agent_checker_signature": "检查人",
        "agent_consignor_signature": "交运人"
      },
      "other_info": {
        "order_contact": "订单联系人",
        "contact_phone": "13700137000",
        "settlement_file_number": "SF001"
      }
    },
    "airline_record_status": "1",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-01T12:00:00+08:00",
    "cargo_station_record_time": "2025-01-01T12:00:00+08:00",
    "document_print_time": "2025-01-01T12:00:00+08:00",
    "departure_time": null,
    "booking_date": "2025-01-01",
    "rpa_work_uuid": null,
    "rpa_queue_uuids": "{\"waybill_number\":{\"queueUUID\":\"xxx\",\"queueID\":\"123\"},\"freight_rate\":{\"queueUUID\":\"xxx\",\"queueID\":\"124\"},\"freight\":{\"queueUUID\":\"xxx\",\"queueID\":\"125\"},\"fuel_costs\":{\"queueUUID\":\"xxx\",\"queueID\":\"126\"},\"extended_service_fee\":{\"queueUUID\":\"xxx\",\"queueID\":\"127\"}}",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00",
    "task_id": "260819415803760650"
  },
  "msg": "南航新增运单已加入执行队列，请等待处理"
}
```

**说明**:

- 接口调用成功后，`airline_record_status`会更新为"1"（开单中，对应数据字典invoice_status的value="1"）
- `task_id`字段返回RPA任务ID，可用于查询任务执行状态
- `rpa_queue_uuids`字段保存了创建的4个队列的信息（JSON格式），用于后续从队列中获取数据
- 后台任务会自动轮询RPA状态，当状态变为成功(5)或失败(3)时，会更新`airline_record_status`为对应的数据字典值
- 当RPA执行成功时：
  - 系统会从队列中获取运单号并更新`waybill_number`字段
  - 系统会从队列中获取费率(freight_rate)、运费(freight)、燃油费(fuel_costs)、延伸服务费(extended_service_fee)数据
  - 系统会自动创建结算单，包含上述费用信息，结算单默认值：
    - `settlement_status`: "0"（未结算）
    - `financial_review`: "0"（未审核）
  - 运单`form_data.other_fees`中的费用会自动同步到结算单：
    - `other_fees.packaging_fee` → `settlement.form_data.sub_packaging_fee`（包装费）
    - `other_fees.pickup_fee` → `settlement.form_data.sub_pickup_fee`（上门提货费）
    - `other_fees.delivery_fee` → `settlement.form_data.sub_delivery_fee`（派送费）
  - 如果获取运单号失败，状态会被设置为失败("2")
  - 最后销毁所有队列，清空`rpa_queue_uuids`字段
- 当RPA执行失败或超时时：
  - 直接销毁所有队列，清空`rpa_queue_uuids`字段
  - 更新`airline_record_status`为"2"（失败）
- 如果运单的airline不是南方航空，会返回错误提示使用 /execute 接口（深航专用）
- 如果该运单已有待执行或执行中的南航新增运单任务，会返回错误

**RPA状态映射说明**:

- `airline_record_status`字段存储的是数据字典的值，不是中文描述
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (执行中) -> airline_record_status="1"（对应数据字典：value="1", label="开单中"）
  - status=3 (失败) -> airline_record_status="2"（对应数据字典：value="2", label="失败"）
  - status=5 (运行成功) -> airline_record_status="3"（对应数据字典：value="3", label="成功"）

**轮询配置说明**:

- 轮询间隔和最大轮询次数可在配置文件中配置（`RPA_POLL_INTERVAL`和`RPA_POLL_MAX_COUNT`）
- 默认配置：每5秒轮询一次，最多轮询60次（即最多轮询5分钟）
- 当RPA状态变为成功(5)或失败(3)时，停止轮询

**与现有接口的对比**:

| 接口 | 适用航司 | 功能 |
|-----|---------|------|
| POST /waybills/{waybill_id}/execute | 深圳航空 | 深航运单执行/开单 |
| POST /waybills/{waybill_id}/execute-china-southern-air | 南方航空 | 南航运单执行/开单 |
| POST /waybills/{waybill_id}/void | 深圳航空、南方航空 | 运单作废 |

---

### 8. 订舱管理

#### 8.1 提交订舱信息

**接口地址**: `POST /api/v1/bookings`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

`form_data` 是一个字典结构，包含航司和订舱信息数组（支持批量订舱，所有键名使用英文，遵循snake_case命名规范）：

**南方航空完整数据结构示例（单条订舱）**:

```json
{
  "form_data": {
    "airline": "南方航空",
    "bookings": [
      {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-04-25",
        "flight_number": "CZ8735",
        "booking_remark_wide": "宽体备注（非必填）",
        "booking_remark_narrow": "窄体备注（非必填）",
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "衣物",
        "quantity": "1",
        "weight": "5",
        \"product_name\": \"产品名称\",
        \"booking_volume\": \"2.5\",
        \"oversized_cargo\": \"0\",
        \"special_cargo_code\": \"ACO\",
        \"no_dangerous_goods\": \"0\",
      }
    ]
  }
}
```

**南方航空完整数据结构示例（批量订舱）**:

```json
{
  "form_data": {
    "airline": "南方航空",
    "bookings": [
      {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-04-25",
        "flight_number": "CZ8735",
        "booking_remark_wide": "宽体备注1",
        "booking_remark_narrow": "窄体备注1",
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "衣物",
        "quantity": "1",
        "weight": "5",
        \"product_name\": \"产品名称1\",
        \"booking_volume\": \"2.5\",
        \"oversized_cargo\": \"0\",
        \"special_cargo_code\": \"ACO\",
        \"no_dangerous_goods\": \"0\",
      },
      {
        "origin_station": "SZX",
        "destination": "PEK",
        "flight_date": "2026-04-26",
        "flight_number": "CZ3210",
        "booking_remark_wide": "宽体备注2",
        "booking_remark_narrow": "窄体备注2",
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "电子产品",
        "quantity": "2",
        "weight": "10",
        \"product_name\": \"产品名称2\",
        \"booking_volume\": \"5.0\",
        \"oversized_cargo\": \"0\",
        \"special_cargo_code\": \"ACO\",
        \"no_dangerous_goods\": \"0\",
      }
    ]
  }
}
```

**响应示例**（单条订舱）:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760649",
    "form_data": {
      "airline": "南方航空",
      "bookings": [
        {
          "origin_station": "CAN",
          "destination": "PEK",
          "flight_date": "2025-01-15",
          "shipper_unit": "XX物流公司",
          "flight_number": "CZ1234",
          "booking_remark": "备注信息",
          "cargo_type": "普通货物",
          "cargo_code": "0001",
          "cargo_name": "货物名称",
          "quantity": "10",
          "weight": "100.5",
          \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
        }
      ]
    },
    "booking_status": "0",
    "invoice_status": "0",
    "booking_time": "2025-01-01T12:00:00+08:00",
    "master_airwaybill_number": null,
    "rpa_work_uuid": "a93a8be06f6b0a51b886de685b3996e0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "订舱信息提交成功"
}
```

**form_data字段结构详细说明**:

- **airline**（必填）：航司名称，值为 `"南方航空"` 或其他航司（目前仅支持南方航空，其他航司字段结构待定义）

- **bookings**（必填）：订舱信息数组，支持批量提交多条订舱记录

**南方航空bookings数组中的每条记录包含以下字段**：

- `origin_station`：始发站（三字码，如：SZX）
- `destination`：到达站（三字码，如：TAO）
- `flight_date`：航班日期（格式：YYYY-MM-DD）
- `flight_number`：航班号
- `booking_remark_wide`：订舱备注_宽体（非必填）
- `booking_remark_narrow`：订舱备注_窄体（非必填）
- `cargo_type`：货物类型
- `cargo_code`：货物代码
- `cargo_name`：货物名称
- `quantity`：件数
- `weight`：重量
- `product_name`：产品名称（如果是非空列表自动提取第一项）
- `booking_volume`：订舱体积
- `oversized_cargo`：超规货
- `booking_volume`：订舱体积（可选）
  - `product_name`：产品名称（如果是非空列表自动提取第一项）
  - `oversized_cargo`：超规货
  - `special_cargo_code`：特货码
  - `storage_and_transportation_precautions`：储运注意事项（可选）
- `no_dangerous_goods`：无危险品
- `storage_and_transportation_precautions`：储运注意事项（可选）

**说明**:

- `form_data` 包含航司和订舱信息，支持南航订舱数据结构
- 所有字段的值都是字符串类型
- 不同航司的字段结构可能不同，前端需要根据 `airline` 字段来展示对应的表单字段
- 目前仅支持南方航空，其他航司字段结构待定义
- **批量提交说明**：
  - 如果`form_data.bookings`数组包含多个元素，系统会自动拆分为多条记录存储
  - 每条记录对应数据库中的一条订舱记录
  - 每条记录的`form_data.bookings`仍然是一个数组，但只包含一个元素（长度为1）
  - 例如：如果提交2条订舱信息，会创建2条数据库记录，每条记录的`form_data.bookings`数组长度为1
- `booking_time`：自动设置为当前时间（中国时间）
- 订舱状态默认为"0"（未执行，数据字典值）
- 开单状态默认为"0"（未开单，数据字典值）
- `master_airwaybill_number` 由RPA后续写入，初始为 `null`
- `booking_status`: 订舱状态，默认为"0"（数据字典值：0=未执行，1=执行中，2=失败，3=成功）
- `invoice_status`: 开单状态，默认为"0"（数据字典值：0=未开单，1=开单中，2=失败，3=成功）
- `master_airwaybill_number`: 主单号，初始为 `null`，RPA成功后写入（如：784-47888190）
- `rpa_work_uuid`: RPA任务workUuid（执行订舱时保存，用于查询RPA执行状态）
- **此接口仅保存订舱信息，不调用RPA接口。如需执行订舱，请调用"确认并执行订舱"接口**

**响应示例**（批量提交，返回多条记录）:

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "260819415803760649",
        "form_data": {
          "airline": "南方航空",
          "bookings": [
            {
              "origin_station": "CAN",
              "destination": "PEK",
              "flight_date": "2025-01-15",
              "shipper_unit": "XX物流公司",
              "flight_number": "CZ1234",
              "booking_remark": "备注信息1",
              "cargo_type": "普通货物",
              "cargo_code": "0001",
              "cargo_name": "货物名称1",
              "quantity": "10",
              "weight": "100.5",
              \"product_name\": \"产品名称1\",
              \"booking_volume\": \"2.5\",
              \"oversized_cargo\": \"否\",
              \"special_cargo_code\": \"\",
              \"no_dangerous_goods\": \"是\",
              \"consignee\": \"收货人1\",
              \"consignee_phone\": \"13800138000\",
            }
          ]
        },
        "booking_status": "0",
        "invoice_status": "0",
        "booking_time": "2025-01-01T12:00:00+08:00",
        "master_airwaybill_number": null,
        "rpa_work_uuid": null,
        "rpa_queue_uuid": null,
        "rpa_queue_id": null,
        "rpa_queue_uuids": null,
        "booking_cancel_status": "0",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      },
      {
        "id": "260819415803760650",
        "form_data": {
          "airline": "南方航空",
          "bookings": [
            {
              "origin_station": "CAN",
              "destination": "SHA",
              "flight_date": "2025-01-16",
              "shipper_unit": "YY物流公司",
              "flight_number": "CZ5678",
              "booking_remark": "备注信息2",
              "cargo_type": "普通货物",
              "cargo_code": "0002",
              "cargo_name": "货物名称2",
              "quantity": "20",
              "weight": "200.0",
              \"product_name\": \"产品名称2\",
              \"booking_volume\": \"5.0\",
              \"oversized_cargo\": \"是\",
              \"special_cargo_code\": \"\",
              \"no_dangerous_goods\": \"是\",
              \"consignee\": \"收货人2\",
              \"consignee_phone\": \"13900139000\",
            }
          ]
        },
        "booking_status": "0",
        "invoice_status": "0",
        "booking_time": "2025-01-01T12:00:00+08:00",
        "master_airwaybill_number": null,
        "rpa_work_uuid": null,
        "rpa_queue_uuid": null,
        "rpa_queue_id": null,
        "rpa_queue_uuids": null,
        "booking_cancel_status": "0",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ],
    "count": 2
  },
  "msg": "订舱信息提交成功，共创建2条记录"
}
```

#### 8.1.1 下载南航订舱模板

**接口地址**: `GET /api/v1/bookings/china-southern-air/template`

**请求头**: `Authorization: Bearer <token>`

**功能说明**:

- 下载南方航空订舱模板文件（Excel）
- 前端可在南航订舱页面提供“下载模板”按钮调用此接口
- 返回文件流，响应类型为 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

**响应说明**:

- 成功时直接返回 `.xlsx` 文件下载流（attachment）
- 失败时返回统一错误响应

**错误场景**:

- 模板文件不存在：返回 404（`南航订舱模板不存在，请联系管理员上传模板文件`）
- 未登录或Token无效：返回 401

---

#### 8.2 获取订舱信息

**接口地址**: `GET /api/v1/bookings/{booking_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**功能说明**:

- 此接口用于获取单个订舱的详细信息，用于前端表单回显
- 返回完整的订舱信息，包括`form_data`中的所有字段

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760649",
    "form_data": {
      "airline": "南方航空",
      "bookings": [
        {
          "origin_station": "CAN",
          "destination": "PEK",
          "flight_date": "2025-01-15",
          "shipper_unit": "XX物流公司",
          "flight_number": "CZ1234",
          "booking_remark": "备注信息",
          "cargo_type": "普通货物",
          "cargo_code": "0001",
          "cargo_name": "货物名称",
          "quantity": "10",
          "weight": "100.5",
          \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
        }
      ]
    },
    "booking_status": "0",
    "invoice_status": "0",
    "booking_time": "2025-01-01T12:00:00+08:00",
    "master_airwaybill_number": null,
    "rpa_work_uuid": null,
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "rpa_queue_uuids": null,
    "booking_cancel_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**:

- 返回的`form_data.bookings`是一个数组，通常只包含一个元素（长度为1）
- 如果订舱不存在，会返回404错误

#### 8.2.1 获取订舱数据转运单form_data（回显接口）

**接口地址**: `GET /api/v1/bookings/{booking_id}/waybill-form`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**功能说明**:

- 此接口用于将订舱数据转换为运单form_data结构，用于运单管理界面的数据回显
- 用户在订舱执行成功后，可以选择：
  - **直接开单**：调用 `POST /api/v1/bookings/{booking_id}/direct-invoice` 接口
  - **来到运单管理界面开单**：先调用此接口获取回显数据，用户可以修改后再调用 `POST /api/v1/waybills` 新增运单
- 将订舱数据（扁平结构）转换为运单数据（嵌套结构）
- 结合业务参数配置补充必要的字段（如shipper、shipper_phone、address等）
- 当前仅支持南方航空的订舱数据转换

**参数优先级**：

- 优先使用订舱时用户填写的数据
- 如果订舱数据中没有，则从业务参数配置的南航部分获取

**数据转换规则**：

订舱数据结构（扁平结构，数据在`bookings[0]`中）：

```json
{
  "airline": "2",
  "bookings": [
    {
      "origin_station": "CAN",
      "destination": "PEK",
      "flight_date": "2025-01-15",
      "shipper_unit": "XX物流公司",
      "flight_number": "CZ1234",
      "booking_remark_wide": "宽体备注（非必填）",
      "booking_remark_narrow": "窄体备注（非必填）",
      "cargo_type": "普通货物",
      "cargo_code": "0001",
      "cargo_name": "货物名称",
      "quantity": "10",
      "weight": "100.5",
      \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
    }
  ]
}
```

转换为运单数据结构（嵌套结构，按功能分组）：

```json
{
  "airline": "2",
  "flight_info": {
    "origin_station": "CAN",
    "destination": "PEK",
    "flight_date": "2025-01-15",
    "flight_number": "CZ1234",
    "booking_remark": "备注信息",
    "booking_remark_wide": "宽体备注",
    "booking_remark_narrow": "窄体备注"
  },
  "cargo_info": {
    "cargo_type": "普通货物",
    "cargo_code": "0001",
    "cargo_name": "货物名称",
    "quantity": "10",
    "weight": "100.5",
    "booking_volume": "",
    "product_name": "产品名称",
          "booking_volume": "2.5",
    "oversized_cargo": "否",
    "special_cargo_code": "",
      "storage_and_transportation_precautions": "",
  },
  "contact_info": {
    "consignee": "收货人",
    "consignee_phone": "13800138000",
    "shipper_unit": "XX物流公司",
    "shipper": "托运人（来自业务参数配置）",
    "shipper_phone": "13900139000（来自业务参数配置）",
    "address": {
      "region": "广东省/深圳市/南山区（来自业务参数配置）",
      "detail": "科技园南区（来自业务参数配置）"
    }
  },
  "dangerous_goods_declaration": {
    "no_hidden_dangerous_goods": "是",
    "agent_checker_signature": "检查人签字（来自业务参数配置）",
    "agent_consignor_signature": "交运人签字（来自业务参数配置）"
  },
  "other_info": {
    "order_contact": "订单联系人（来自业务参数配置）",
    "contact_phone": "联系人电话（来自业务参数配置）",
    "settlement_file_number": "结算文件号（来自业务参数配置）"
  },
  "other_fees": {
    "packaging_fee": "",
    "pickup_fee": "",
    "delivery_fee": ""
  }
}
```

**字段映射表**:

| 订舱字段（bookings[0]） | 运单字段 | 说明 |
|----------------------|---------|------|
| `origin_station` | `flight_info.origin_station` | 优先订舱数据，否则取业务参数配置 |
| `destination` | `flight_info.destination` | 来自订舱数据 |
| `flight_date` | `flight_info.flight_date` | 来自订舱数据 |
| `flight_number` | `flight_info.flight_number` | 来自订舱数据 |
| `booking_remark` / `booking_remark_wide` | `flight_info.booking_remark` | 优先booking_remark，其次booking_remark_wide，否则取业务参数配置的`booking_remark` |
| `booking_remark_wide` | `flight_info.booking_remark_wide` | 优先订舱数据，否则取业务参数配置的`booking_remark_wide` |
| `booking_remark_narrow` | `flight_info.booking_remark_narrow` | 优先订舱数据，否则取业务参数配置的`booking_remark_narrow` |
| `cargo_type` | `cargo_info.cargo_type` | 优先订舱数据，否则取业务参数配置 |
| `cargo_code` | `cargo_info.cargo_code` | 优先订舱数据，否则取业务参数配置 |
| `cargo_name` | `cargo_info.cargo_name` | 来自订舱数据 |
| `quantity` | `cargo_info.quantity` | 来自订舱数据 |
| `weight` | `cargo_info.weight` | 来自订舱数据 |
| `product_name` | `cargo_info.product_name` | 来自订舱数据 |
| `oversized_cargo` | `cargo_info.oversized_cargo` | 来自订舱数据 |
| `special_cargo_code` | `cargo_info.special_cargo_code` | 优先订舱数据，否则取业务参数配置 |
| `consignee` | `contact_info.consignee` | 来自订舱数据 |
| `consignee_phone` | `contact_info.consignee_phone` | 来自订舱数据 |
| `shipper_unit` | `contact_info.shipper_unit` | 来自订舱数据 |
| 业务参数配置的shipper | `contact_info.shipper` | 来自业务参数配置 |
| 业务参数配置的phone | `contact_info.shipper_phone` | 来自业务参数配置 |
| 业务参数配置的address | `contact_info.address` | 来自业务参数配置（region和detail） |
| `no_dangerous_goods` | `dangerous_goods_declaration.no_hidden_dangerous_goods` | 来自订舱数据 |
| 业务参数配置的agent_checker_name | `dangerous_goods_declaration.agent_checker_signature` | 来自业务参数配置 |
| 业务参数配置的agent_consignor_name | `dangerous_goods_declaration.agent_consignor_signature` | 来自业务参数配置 |
| 业务参数配置的order_contact_name | `other_info.order_contact` | 来自业务参数配置 |
| 业务参数配置的order_contact_phone | `other_info.contact_phone` | 来自业务参数配置 |
| 业务参数配置的settlement_file_number | `other_info.settlement_file_number` | 来自业务参数配置 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "booking_id": "260819415803760649",
    "form_data": {
      "airline": "2",
      "flight_info": {
        "origin_station": "CAN",
        "destination": "PEK",
        "flight_date": "2025-01-15",
        "flight_number": "CZ1234",
        "booking_remark": "备注信息"
      },
      "cargo_info": {
        "cargo_type": "普通货物",
        "cargo_code": "0001",
        "cargo_name": "货物名称",
        "quantity": "10",
        "weight": "100.5",
        "booking_volume": "",
        "product_name": "产品名称",
          "booking_volume": "2.5",
        "oversized_cargo": "否",
        "booking_volume": "2.5",
      "product_name": "产品名称",
      "oversized_cargo": "否",
      "special_cargo_code": "",
      "storage_and_transportation_precautions": "",
      },
      "contact_info": {
        "consignee": "收货人",
        "consignee_phone": "13800138000",
        "shipper_unit": "XX物流公司",
        "shipper": "托运人",
        "shipper_phone": "13900139000",
        "address": {
          "region": "广东省/深圳市/南山区",
          "detail": "科技园南区"
        }
      },
      "dangerous_goods_declaration": {
        "no_hidden_dangerous_goods": "是",
        "agent_checker_signature": "检查人签字",
        "agent_consignor_signature": "交运人签字"
      },
      "other_info": {
        "order_contact": "订单联系人",
        "contact_phone": "13700137000",
        "settlement_file_number": "SF001"
      },
      "other_fees": {
        "packaging_fee": "",
        "pickup_fee": "",
        "delivery_fee": ""
      }
    },
    "master_airwaybill_number": "784-47888190",
    "booking_status": "3",
    "invoice_status": "0"
  },
  "msg": "查询成功"
}
```

**响应字段详细说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `booking_id` | string | 订舱ID（BigInteger转字符串） |
| `form_data` | object | 符合运单新增接口所需的form_data数据结构 |
| `form_data.airline` | string | 航司标识（"2"表示南方航空） |
| `form_data.flight_info` | object | 航班信息 |
| `form_data.cargo_info` | object | 货物信息 |
| `form_data.contact_info` | object | 联系人信息（包含shipper、address等来自业务参数配置的字段） |
| `form_data.dangerous_goods_declaration` | object | 危险品声明 |
| `form_data.other_info` | object | 其他信息（来自业务参数配置） |
| `form_data.other_fees` | object | 其他费用（默认为空，用户可填写） |
| `master_airwaybill_number` | string\|null | 主单号（订舱成功后才有值） |
| `booking_status` | string | 订舱状态（数据字典值：0=未执行，1=执行中，2=失败，3=成功） |
| `invoice_status` | string | 开单状态（数据字典值：0=未开单，1=开单中，2=失败，3=成功） |

**说明**:

- 返回的`form_data`结构完全符合运单新增接口（`POST /api/v1/waybills`）的数据结构要求
- 用户可以在前端修改回显的数据后，调用修改数据后开单接口提交
- 如果订舱不存在，会返回404错误
- 如果订舱的airline不是南方航空，会返回400错误（当前仅支持南航）
- 即使业务参数配置不存在或为空，接口也会正常返回，只是来自业务参数配置的字段会为空字符串

**前端完整流程**:

1. 调用回显接口 `GET /api/v1/bookings/{booking_id}/waybill-form` 获取数据
2. 用户在前端界面修改数据
3. 调用修改数据后开单接口 `POST /api/v1/bookings/{booking_id}/invoice-with-data`，请求体需要包含修改后的`form_data`
4. 系统会自动：
   - 更新订舱的`invoice_status`状态
   - 开单成功后同步创建运单记录到`waybills`表
   - 创建结算单记录

---

#### 8.2.2 南航修改数据后开单

**接口地址**: `POST /api/v1/bookings/{booking_id}/invoice-with-data`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**功能说明**:

- 此接口用于用户从订舱回显数据后修改再开单的场景
- 与直接开单接口不同，此接口允许用户传入修改后的业务数据
- 开单成功后，系统会自动同步创建运单记录到waybills表，并创建结算单

**使用场景**:

1. 用户订舱执行成功后，调用回显接口获取数据
2. 用户在前端修改数据
3. 调用此接口传入修改后的form_data进行开单

**请求参数**:

```json
{
  "form_data": {
    "airline": "2",
    "flight_info": {
      "origin_station": "CAN",
      "destination": "PEK",
      "flight_date": "2026-01-24",
      "flight_number": "CZ3923",
      "booking_remark": "这是我的订舱备注"
    },
    "cargo_info": {
      "cargo_type": "普通货物",
      "cargo_code": "9000",
      "cargo_name": "上衣",
      "quantity": "1",
      "weight": "10",
      "booking_volume": "0.05",
      "product_name": "",
      "oversized_cargo": "0",
      "special_cargo_code": "ACO,TAO"
    },
    "contact_info": {
      "consignee": "李四",
      "consignee_phone": "13800138000",
      "shipper_unit": "XX物流公司",
      "shipper": "张三",
      "shipper_phone": "18979681111",
      "address": {
        "region": "江西省/吉安市/泰和县",
        "detail": "科技园南区"
      }
    },
    "dangerous_goods_declaration": {
      "no_hidden_dangerous_goods": "是",
      "agent_checker_signature": "检查人签字",
      "agent_consignor_signature": "交运人签字"
    },
    "other_info": {
      "order_contact": "陈xx",
      "contact_phone": "18979681112",
      "settlement_file_number": "123"
    },
    "other_fees": {
      "packaging_fee": "",
      "pickup_fee": "",
      "delivery_fee": ""
    }
  }
}
```

**必填参数**（在form_data中）:

- flight_info.flight_number: 航班号
- flight_info.flight_date: 航班日期
- cargo_info.cargo_name: 货物名称
- cargo_info.weight: 重量
- cargo_info.quantity: 件数
- contact_info.shipper: 发货人
- contact_info.shipper_phone: 发货人电话
- contact_info.consignee: 收货人

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760649",
    "form_data": {
      "airline": "2",
      "bookings": [...]
    },
    "submitted_form_data": {
      "airline": "2",
      "flight_info": {...},
      "cargo_info": {...},
      "contact_info": {...}
    },
    "booking_status": "3",
    "invoice_status": "1",
    "booking_time": "2025-01-01T12:00:00+08:00",
    "master_airwaybill_number": "784-47888190",
    "rpa_work_uuid": null,
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "booking_cancel_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00",
    "task_id": "260819415803760700"
  },
  "msg": "修改数据后开单已加入执行队列，请等待处理"
}
```

**RPA参数映射说明**:

- 接口会将form_data中的数据映射为RPA接口所需的参数，优先使用form_data中的值，如果没有则从业务参数配置获取
- 主要参数映射关系：
  - `flight_info.flight_number` → RPA参数 `flight_number`
  - `flight_info.flight_date` → RPA参数 `flight_date`
  - `flight_info.booking_remark` → RPA参数 `booking_remark`
  - `cargo_info.cargo_code` → RPA参数 `cargo_code`
  - `cargo_info.cargo_name` → RPA参数 `cargo_name`
  - `cargo_info.weight` → RPA参数 `weight`
  - `cargo_info.quantity` → RPA参数 `quantity`
  - `cargo_info.booking_volume` → RPA参数 `volume`
  - `cargo_info.special_cargo_code` → RPA参数 `special_cargo_code`
  - `cargo_info.oversized_cargo` → RPA参数 `oversized_cargo`
  - `contact_info.shipper` → RPA参数 `shipper`
  - `contact_info.shipper_phone` → RPA参数 `shipper_phone`
  - `contact_info.consignee` → RPA参数 `consignee`
  - `contact_info.consignee_phone` → RPA参数 `consignee_phone`
  - `contact_info.address.region` → RPA参数 `region_province_shipper`、`region_city_shipper`、`region_city_district`（按"/"分割）
  - `contact_info.address.detail` → RPA参数 `address_detail`
  - `other_info.contact_phone` → RPA参数 `order_contact_phone`
  - `other_info.order_contact` → RPA参数 `order_contact_name`
  - `other_info.settlement_file_number` → RPA参数 `settlement_file_number`

**说明**:

- 接口调用成功后，`invoice_status`会更新为"1"（开单中）
- `task_id`字段返回RPA任务ID，可用于查询任务执行状态
- 后台任务会自动轮询RPA状态，当状态变为成功(5)或失败(3)时，会更新`invoice_status`为对应的数据字典值
- 当RPA执行成功时：
  - 系统会从4个队列中获取费率、运费、燃油费、延伸服务费数据
  - 系统会自动创建结算单，包含上述费用信息，结算单默认值：
    - `settlement_status`: "0"（未结算）
    - `financial_review`: "0"（未审核）
  - 提交的`form_data.other_fees`中的费用会自动同步到结算单：
    - `other_fees.packaging_fee` → `settlement.form_data.sub_packaging_fee`（包装费）
    - `other_fees.pickup_fee` → `settlement.form_data.sub_pickup_fee`（上门提货费）
    - `other_fees.delivery_fee` → `settlement.form_data.sub_delivery_fee`（派送费）
  - 系统会自动同步创建运单记录到waybills表，运单号为`master_airwaybill_number`，运单状态为成功("3")
  - 最后销毁所有队列
- 当RPA执行失败或超时时：
  - 直接销毁所有队列
  - 更新`invoice_status`为"2"（失败）
- 如果订舱的airline不是南方航空，会返回错误
- 如果订舱尚未完成（无master_airwaybill_number），会返回错误
- 如果该订舱已有待执行或执行中的开单任务，会返回错误

**队列管理说明**:

- 系统会在调用RPA接口之前创建4个队列：
  - `nanhang_air_dingcang_kaidan_queue_rate`（费率队列）
  - `nanhang_air_dingcang_kaidan_queue_freight`（运费队列）
  - `nanhang_air_dingcang_kaidan_queue_fuel_costs`（燃油费队列）
  - `nanhang_air_dingcang_kaidan_queue_extended_service_fee`（延伸服务费队列）
- RPA执行过程中会将数据存入这4个队列
- 无论成功还是失败，流程结束后都会删除所有队列

**与直接开单接口的区别**:

| 接口 | 适用场景 | 是否允许修改数据 |
|-----|---------|----------------|
| POST /bookings/{id}/direct-invoice | 直接开单，不需要修改数据 | 否，只需要booking_id |
| POST /bookings/{id}/invoice-with-data | 修改数据后开单 | 是，需要传入修改后的form_data |

---

#### 8.3 修改订舱信息

**接口地址**: `PUT /api/v1/bookings/{booking_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**请求参数**:

```json
{
  "form_data": {
    "airline": "南方航空",
    "bookings": [
      {
        "origin_station": "CAN",
        "destination": "PEK",
        "flight_date": "2025-01-15",
        "shipper_unit": "XX物流公司",
        "flight_number": "CZ1234",
        "booking_remark": "修改后的备注信息",
        "cargo_type": "普通货物",
        "cargo_code": "0001",
        "cargo_name": "货物名称",
        "quantity": "10",
        "weight": "100.5",
        \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
      }
    ]
  }
}
```

**功能说明**:

- 此接口用于修改订舱信息，修改后可以重新执行订舱
- **只能修改未执行（booking_status="0"）的订舱记录**
- 如果订舱已经执行或正在执行，不允许修改
- `form_data.bookings`数组通常只包含一条记录（长度为1）
- 修改后，`booking_time`保持不变，`updated_at`会自动更新

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760649",
    "form_data": {
      "airline": "南方航空",
      "bookings": [
        {
          "origin_station": "CAN",
          "destination": "PEK",
          "flight_date": "2025-01-15",
          "shipper_unit": "XX物流公司",
          "flight_number": "CZ1234",
          "booking_remark": "修改后的备注信息",
          "cargo_type": "普通货物",
          "cargo_code": "0001",
          "cargo_name": "货物名称",
          "quantity": "10",
          "weight": "100.5",
          \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
        }
      ]
    },
    "booking_status": "0",
    "invoice_status": "0",
    "booking_time": "2025-01-01T12:00:00+08:00",
    "master_airwaybill_number": null,
    "rpa_work_uuid": null,
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "rpa_queue_uuids": null,
    "booking_cancel_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:05:00+08:00"
  },
  "msg": "订舱信息修改成功"
}
```

**说明**:

- 如果订舱不存在，会返回404错误
- 如果订舱状态不是"0"（未执行），会返回400错误，提示只能修改未执行的订舱
- 如果`form_data.bookings`数组包含多条记录，会返回400错误，提示只能包含一条记录
- 修改后，`booking_time`保持不变，`updated_at`会自动更新为当前时间

#### 8.4 确认并执行订舱（批量，队列模式）

**接口地址**: `POST /api/v1/bookings/execute`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "booking_ids": ["260819415803760649", "260819415803760650"]
}
```

**参数说明**:

- `booking_ids`: 订舱ID列表（字符串格式，至少包含一个ID）

**功能说明**:

- 此接口支持批量执行订舱，接收一个或多个订舱ID列表
- 对每个订舱ID，系统会独立验证和处理
- 当前仅支持南方航空的订舱（airline="2"或"南方航空"）
- 此接口用于执行订舱，会调用RPA接口进行自动化处理
- 当前仅支持南方航空的订舱（airline="2"或"南方航空"）
- **队列管理流程**：
  1. **流程运行开始-新增队列**：在调用RPA接口之前，系统会先创建一个队列，队列名称为`nanhang_air_dingcang_kaidan_queue_waybill_number`（配置在`RPA_CHINA_SOUTHERN_AIR_QUEUE_WAYBILL_NUMBER`，与南航新增运单、南航直接开单共用），每个订舱都会创建独立的队列实例
  2. **流程运行过程中-数据存入队列**：RPA执行过程中会将运单号数据存入队列
  3. **流程运行结束-用本次新增的队列id查询队列数据**：当RPA执行状态变为"执行成功"（status=5，系统状态为"3"）时，系统会使用本次创建的queueUUID调用获取运单号接口，获取运单号后八位，对于南航会自动加上前缀"784-"，完整运单号格式为"784-XXXXXXXX"（如：784-47888190），并保存到`master_airwaybill_number`字段
  4. **流程运行结束-队列删除**：
     - **成功时**：获取运单号后，系统会自动删除本次创建的队列
     - **失败时**：如果RPA执行失败（status=3，系统状态为"2"），系统也会自动清理队列
     - **无论成功还是失败，只要流程结束，都会删除队列**
- 接口会从业务参数管理中获取南航相关配置，结合form_data中的数据，映射到RPA接口参数
- 调用成功后，会保存RPA返回的workUuid和队列信息（queueUUID、queueID）到数据库（覆盖之前的rpa_work_uuid）
- 同时启动后台任务自动轮询RPA执行状态，并更新订舱的booking_status字段
- **运单号自动获取**：当RPA执行状态变为"执行成功"（status=5）时，系统会使用本次创建的queueUUID调用获取运单号接口，获取运单号后八位，对于南航会自动加上前缀"784-"，完整运单号格式为"784-XXXXXXXX"（如：784-47888190），并保存到`master_airwaybill_number`字段
- 允许重复执行，会覆盖之前的rpa_work_uuid和队列信息

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "booking_id": "260819415803760649",
        "task_id": "270123456789012345",
        "success": true,
        "error_message": null
      },
      {
        "booking_id": "260819415803760650",
        "task_id": "270123456789012346",
        "success": true,
        "error_message": null
      },
      {
        "booking_id": "260819415803760651",
        "task_id": null,
        "success": false,
        "error_message": "当前仅支持南方航空的订舱执行"
      }
    ],
    "total": 3,
    "success_count": 2,
    "failed_count": 1
  },
  "msg": "批量执行完成，成功: 2，失败: 1"
}
```

**响应字段说明**:

- `items`: 每个订舱的执行结果列表
  - `booking_id`: 订舱ID（字符串格式）
  - `task_id`: RPA任务ID（成功时返回，可用于查询任务状态）
  - `success`: 是否成功（true/false）
  - `error_message`: 错误信息（失败时返回，成功时为null）
- `total`: 总数量
- `success_count`: 成功数量
- `failed_count`: 失败数量

**说明**:

- 接口会遍历每个booking_id，独立验证和处理
- 对于每个成功的订舱，会创建独立的RPA任务并加入队列
- 对于失败的订舱，会在响应中返回具体的错误信息，但不影响其他订舱的处理
- 如果`booking_ids`列表为空或长度小于1，会返回400错误
- 如果业务参数配置不存在，会返回400错误（所有订舱都会失败）
- 如果某个订舱的airline不是南方航空，该订舱会失败，但不影响其他订舱
- 如果某个订舱已有待执行或执行中的任务，该订舱会失败，但不影响其他订舱
- 如果某个订舱缺少必填参数，该订舱会失败，但不影响其他订舱
- 每个成功的订舱，其`booking_status`会在Worker处理时更新为"1"（执行中，数据字典值）
- 每个成功的订舱，都会创建独立的队列和RPA任务

**南航订舱RPA调用说明**:

- 系统会从业务参数管理中获取南航相关配置（config_data.china_southern_air），结合form_data中的数据，映射到RPA接口参数
- **参数优先级**：优先使用form_data.bookings[0]中的值，如果form_data.bookings[0]中没有，则从业务参数配置中的南航数据部分获取
- **form_data数据结构**：

  ```json
  {
    "airline": "南方航空",
    "bookings": [
      {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-04-25",
        "flight_number": "CZ8735",
        "booking_remark_wide": "宽体备注（非必填）",
        "booking_remark_narrow": "窄体备注（非必填）",
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "衣物",
        "quantity": "1",
        "weight": "5",
        "oversized_cargo": "0",
        "special_cargo_code": "ACO",
        "no_dangerous_goods": "0",
        "storage_and_transportation_precautions": "",
      }
    ]
  }
  ```

- 参数映射关系：
  - **从业务参数配置获取**（这些参数通常不在form_data中）：
    - `tangi_login.address_of_the_application_executable_file_tangyi`（如果不存在则使用`tangi_login.app_name`） → `address_of_the_application_executable_file_tangyi`
    - `china_southern_air_login.system_account` → `system_account`
    - `china_southern_air_login.login_password` → `login_password`
    - `china_southern_air_login.system_url` → `system_url`
  - **优先使用form_data.bookings[0]，如果没有则使用业务参数配置**：
    - `form_data.order_contact_name` 或 `business_default.order_contact_name`（如果包含"/"，会分割提取姓名和电话） → `order_contact_name`
    - `form_data.order_contact_phone` 或 `business_default.order_contact_phone`（如果不存在，会从`order_contact_name`中提取） → `order_contact_phone`
    - `form_data.agent_checker_name` 或 `business_default.agent_checker_name` → `agent_checker_name`
    - `form_data.agent_consignor_name` 或 `business_default.agent_consignor_name` → `agent_consignor_name`
    - `form_data.settlement_file_number` 或 `business_default.settlement_file_number` → `settlement_file_number`
    - `form_data.bookings[0].origin_station` 或 `business_default.origin_station` → `origin_station`
    - `form_data.bookings[0].destination` → `destination`
    - `form_data.bookings[0].flight_date` → `flight_date`
    - `form_data.bookings[0].flight_number` → `flight_number`
    - `form_data.bookings[0].booking_remark_wide` 或 `business_default.booking_remark_wide` → `booking_remark_wide`（非必填）
    - `form_data.bookings[0].booking_remark_narrow` 或 `business_default.booking_remark_narrow` → `booking_remark_narrow`（非必填）
    - `form_data.bookings[0].cargo_type` 或 `business_default.cargo_type` → `cargo_type`
    - `form_data.bookings[0].cargo_code` 或 `business_default.cargo_code` → `cargo_code`
    - `form_data.bookings[0].cargo_name` → `cargo_name`
    - `form_data.bookings[0].quantity` → `quantity`
    - `form_data.bookings[0].weight` → `weight`
    - `form_data.bookings[0].special_cargo_code` 或 `business_default.special_cargo_code` → `special_cargo_code`
    - `form_data.bookings[0].oversized_cargo` → `oversized_cargo`（默认"0"）
    - `form_data.bookings[0].no_dangerous_goods` → `no_dangerous_goods`（默认"0"）
  - **从系统业务配置获取（机型配置）**:
    - `china_southern_air.booking.booking_config.wide` → `wide_body_aircraft_rules` (数组，如：["4", "5", "6"])
    - `china_southern_air.booking.booking_config.narrow` → `narrow_body_aircraft_rules` (数组，如：["1", "2", "3"])
- 调用成功后，`booking_status`会更新为"1"（执行中，数据字典值），`rpa_work_uuid`字段会保存RPA返回的workUuid
- 后台任务会自动轮询RPA状态，当状态变为成功(5)或失败(3)时，会更新`booking_status`为对应的状态
- **运单号自动获取**：当RPA执行状态变为"执行成功"（status=5）时，系统会使用本次创建的queueUUID调用获取运单号接口，获取运单号后八位，对于南航会自动加上前缀"784-"，完整运单号格式为"784-XXXXXXXX"（如：784-47888190），并保存到`master_airwaybill_number`字段
- **队列自动清理**：获取运单号成功后，系统会自动删除本次创建的队列。如果RPA执行失败（status=3），系统也会自动清理队列，避免队列资源浪费
- 如果业务参数配置不存在，会返回错误

**RPA状态映射说明**:

- `booking_status`字段存储的是数据字典的值，不是中文描述。前端通过数据字典（dict_type="invoice_status"）将值转换为对应的中文显示
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (执行中) -> booking_status="1"（对应数据字典：value="1", label="执行中"）
  - status=3 (失败) -> booking_status="2"（对应数据字典：value="2", label="失败"）
  - status=5 (运行成功) -> booking_status="3"（对应数据字典：value="3", label="成功"），同时自动获取运单号并保存到`master_airwaybill_number`字段
- **重要**：即使RPA返回成功（status=5），如果获取主单号失败（`master_airwaybill_number`为空），系统会将`booking_status`设置为"2"（失败），因为主单号是订舱成功的必要条件

**轮询配置说明**:

- 轮询间隔和最大轮询次数可在配置文件中配置（`RPA_POLL_INTERVAL`和`RPA_POLL_MAX_COUNT`）
- 默认配置：每5秒轮询一次，最多轮询60次（即最多轮询5分钟）
- 当RPA状态变为成功(5)或失败(3)时，停止轮询

#### 8.3 订舱列表

**接口地址**: `GET /api/v1/bookings`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `airline`: 航司（数据字典值精确匹配，可选：`"1"`=深圳航空，`"2"`=南方航空）
- `booking_status`: 订舱状态筛选（数据字典值精确匹配，可选：`"0"`=未执行，`"1"`=执行中，`"2"`=失败，`"3"`=成功）
- `invoice_status`: 开单状态筛选（数据字典值精确匹配，可选：`"0"`=未开单，`"1"`=开单中，`"2"`=失败，`"3"`=成功）
- `booking_date_start`: 订舱日期开始（格式：YYYY-MM-DD，可选，作用于`booking_time`）
- `booking_date_end`: 订舱日期结束（格式：YYYY-MM-DD，可选，作用于`booking_time`）
- `page`: 页码（默认1）
- `pageSize`: 每页数量（默认10，最大200）

**请求示例**: `GET /api/v1/bookings?airline=2&booking_status=0&booking_date_start=2026-01-01&booking_date_end=2026-01-31&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 10,
    "items": [
      {
        "id": "260819415803760649",
        "form_data": {
          "airline": "2",
          "origin_station": "CAN",
          "destination": "PEK",
          "flight_date": "2025-01-15",
          "shipper_unit": "XX物流公司",
          "flight_number": "CZ1234",
          "booking_remark": "备注信息",
          "cargo_type": "普通货物",
          "cargo_code": "0001",
          "cargo_name": "货物名称",
          "quantity": "10",
          "weight": "100.5",
          \"product_name\": \"产品名称\",
          \"booking_volume\": \"2.5\",
          \"oversized_cargo\": \"否\",
          \"special_cargo_code\": \"\",
          \"no_dangerous_goods\": \"是\",
          \"consignee\": \"收货人\",
          \"consignee_phone\": \"13800138000\",
        },
        "booking_status": "0",
        "invoice_status": "0",
        "booking_time": "2025-01-01T12:00:00+08:00",
        "master_airwaybill_number": "784-47888190",
        "rpa_work_uuid": "a93a8be06f6b0a51b886de685b3996e0",
        "rpa_queue_uuid": null,
        "rpa_queue_id": null,
        "booking_cancel_status": "0",
        "booking_feedback": "机型识别失败",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**说明**:

- 支持多条件组合筛选
- `airline`（航司）使用数据字典值精确匹配（`"1"`=深圳航空，`"2"`=南方航空），从 `form_data` JSON中提取
- `booking_status`（订舱状态）、`invoice_status`（开单状态）使用数据字典值精确匹配
- 日期筛选作用于`booking_time`字段（DateTime）：`booking_date_start`按当天`00:00:00`开始，`booking_date_end`按结束日次日`00:00:00`左闭右开比较，确保结束日期当天数据被完整包含

**响应字段详细说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `total` | integer | 总记录数 |
| `items` | array[object] | 订舱记录列表 |
| `items[].id` | string | 订舱ID（BigInteger转字符串） |
| `items[].form_data` | object | 表单数据（**已展开，不包含bookings字段**），包含航司和订舱信息字段 |
| `items[].form_data.airline` | string | 航司名称（如：南方航空） |
| `items[].form_data.origin_station` | string | 始发站（三字码，如：CAN） |
| `items[].form_data.destination` | string | 到达站（三字码，如：PEK） |
| `items[].form_data.flight_date` | string | 航班日期（格式：YYYY-MM-DD） |
| `items[].form_data.shipper_unit` | string | 托运单位 |
| `items[].form_data.flight_number` | string | 航班号 |
| `items[].form_data.booking_remark` | string | 订舱备注 |
| `items[].form_data.cargo_type` | string | 货物类型 |
| `items[].form_data.cargo_code` | string | 货物代码 |
| `items[].form_data.cargo_name` | string | 货物名称 |
| `items[].form_data.quantity` | string | 件数 |
| `items[].form_data.weight` | string | 重量 |
| `items[].form_data.product_name` | string/array | 产品名称 |
| `items[].form_data.oversized_cargo` | string | 超规货 |
| `items[].form_data.special_cargo_code` | string | 特货码 |
| `items[].form_data.no_dangerous_goods` | string | 无危险品 |
| `items[].form_data.consignee` | string | 收货人 |
| `items[].form_data.consignee_phone` | string | 收货人手机号 |
| `items[].booking_status` | string | 订舱状态（数据字典值：0=未执行，1=执行中，2=失败，3=成功） |
| `items[].invoice_status` | string | 开单状态（数据字典值：0=未开单，1=开单中，2=失败，3=成功） |
| `items[].booking_time` | string | 订舱时间（中国时间，UTC+8，ISO 8601格式） |
| `items[].master_airwaybill_number` | string\|null | 主单号（RPA成功后写入，如：784-47888190） |
| `items[].rpa_work_uuid` | string\|null | RPA任务workUuid（用于查询RPA执行状态） |
| `items[].rpa_queue_uuid` | string\|null | RPA队列UUID（本次创建的队列UUID，用于获取运单号，获取成功后会被清空） |
| `items[].rpa_queue_id` | string\|null | RPA队列ID（本次创建的队列ID，用于删除队列，获取成功后会被清空） |
| `items[].booking_cancel_status` | string | 退舱状态（数据字典值：0=未退舱，1=退舱中，2=退舱失败，3=退舱成功） |
| `items[].booking_feedback` | string\|null | 订舱反馈信息（如：机型识别失败，南航专用） |
| `items[].created_at` | string | 创建时间（中国时间，UTC+8，ISO 8601格式） |
| `items[].updated_at` | string | 更新时间（中国时间，UTC+8，ISO 8601格式） |

**说明**:

- **数据结构说明**：返回的 `form_data` 中**不包含 `bookings` 字段**，`bookings` 数组中的订舱信息字段已直接展开到 `form_data` 中，避免列表套列表的结构
- **数据展开规则**：
  - 如果原始数据中 `bookings` 是数组，取第一个元素的字段展开到 `form_data` 中
  - 如果原始数据中 `bookings` 是对象（包含 `fullData`、`visibleData`、`tableData` 等），优先提取 `fullData` 的第一个元素，如果没有则使用 `visibleData`，再没有则使用 `tableData`
- 支持多条件组合筛选
- 航司从 `form_data` JSON中提取进行模糊搜索
- 订舱状态和开单状态在数据库层面筛选，性能更好
- 按创建时间倒序排列（同一时间按ID倒序，确保分页结果稳定）
- 所有时间字段使用中国时间（UTC+8），格式为 ISO 8601 标准格式
- 所有ID字段（订舱ID等）都是 `BigInteger` 类型，在API响应中统一转换为字符串格式返回

#### 8.4 退舱

**接口地址**: `POST /api/v1/bookings/{booking_id}/cancel`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**功能说明**:

- 此接口用于退舱，会调用RPA接口进行自动化处理
- 当前仅支持南方航空的退舱（airline="2"或"南方航空"）
- 接口会从订舱记录中获取`master_airwaybill_number`（主单号）
- 对于南航，需要去除前面的"784-"前缀，获取后8位作为`waybill_number_8`参数
- 从业务参数配置中获取`system_url`、`system_account`、`login_password`
- 调用成功后，会保存RPA返回的workUuid到数据库（覆盖之前的rpa_work_uuid）
- 同时启动后台任务自动轮询RPA执行状态，并更新订舱的`booking_cancel_status`字段
- 当RPA退舱成功时，更新退舱状态为"3"（退舱成功），保留记录用于留痕
- 允许重复执行，会覆盖之前的rpa_work_uuid

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "269479386711986176",
    "form_data": {
      "airline": "2",
      "flight_info": {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-01-15",
        "flight_number": "CZ3963"
      },
      "cargo_info": {
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "衣物",
        "quantity": "1",
        "weight": "5",
        "special_cargo_code": "ACO",
        "oversized_cargo": "0"
      },
      "contact_info": {
        "consignee": "李四",
        "consignee_phone": "18979681223"
      },
      "dangerous_goods_declaration": {
        "no_hidden_dangerous_goods": "0"
      }
    },
    "booking_status": "3",
    "invoice_status": "0",
    "booking_time": "2026-01-13T22:54:52+08:00",
    "master_airwaybill_number": "784-47888190",
    "rpa_work_uuid": "2af6d154fc527cee63418f830c3ca88d",
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "booking_cancel_status": "1",
    "booking_feedback": null,
    "created_at": "2026-01-13T22:54:52+08:00",
    "updated_at": "2026-01-13T22:54:54+08:00"
  },
  "msg": "退舱成功，正在处理中"
}
```

**说明**:

- 接口调用成功后，`booking_cancel_status`会更新为"1"（退舱中，数据字典值："1"=退舱中）
- `rpa_work_uuid`字段会保存RPA返回的workUuid，用于后续查询RPA执行状态
- 后台任务会自动轮询RPA状态，当状态变为成功(5)或失败(3)时，会更新`booking_cancel_status`为对应的数据字典值
- 如果主单号不存在，会返回错误
- 如果订舱的airline不是南方航空，会返回错误
- 如果业务参数配置不存在或缺少南航登录信息，会返回错误

**RPA状态映射说明**:

- `booking_cancel_status`字段存储的是数据字典的值，不是中文描述。前端通过数据字典（dict_type="invoice_status"）将值转换为对应的中文显示
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (执行中) -> booking_cancel_status="1"（对应数据字典：value="1", label="退舱中"）
  - status=3 (失败) -> booking_cancel_status="2"（对应数据字典：value="2", label="退舱失败"）
  - status=5 (运行成功) -> booking_cancel_status="3"（对应数据字典：value="3", label="退舱成功"）

**轮询配置说明**:

- 轮询间隔和最大轮询次数可在配置文件中配置（`RPA_POLL_INTERVAL`和`RPA_POLL_MAX_COUNT`）
- 默认配置：每5秒轮询一次，最多轮询60次（即最多轮询5分钟）
- 当RPA状态变为成功(5)或失败(3)时，停止轮询

**业务参数配置说明**:

- 系统会从业务参数配置中获取南航登录信息：
  - `config_data.china_southern_air.booking_and_create.china_southern_air_login.system_url` → `system_url`
  - `config_data.china_southern_air.booking_and_create.china_southern_air_login.system_account` → `system_account`
  - `config_data.china_southern_air.booking_and_create.china_southern_air_login.login_password` → `login_password`

---

#### 8.4 南航直接开单

**接口地址**: `POST /api/v1/bookings/{booking_id}/direct-invoice`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**请求示例**:

```bash
curl -X POST "http://localhost:8000/api/v1/bookings/269479386711986176/direct-invoice" \
  -H "Authorization: Bearer <token>"
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "269479386711986176",
    "form_data": {
      "airline": "2",
      "flight_info": {
        "origin_station": "SZX",
        "destination": "TAO",
        "flight_date": "2026-01-15",
        "flight_number": "CZ3963"
      },
      "cargo_info": {
        "cargo_type": "普货",
        "cargo_code": "9000",
        "cargo_name": "衣物",
        "quantity": "1",
        "weight": "5"
      },
      "contact_info": {
        "consignee": "李四",
        "consignee_phone": "18979681223"
      }
    },
    "booking_status": "3",
    "invoice_status": "3",
    "booking_time": "2026-01-13T22:54:52+08:00",
    "master_airwaybill_number": "784-47888190",
    "rpa_work_uuid": "a93a8be06f6b0a51b886de685b3996e0",
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "booking_cancel_status": "0",
    "booking_feedback": null,
    "created_at": "2026-01-13T22:54:52+08:00",
    "updated_at": "2026-01-13T22:54:54+08:00"
  },
  "msg": "直接开单成功，正在处理中"
}
```

**说明**:

- 接口调用成功后，会创建4个队列（费率、运费、燃油费、延伸服务费），调用南航直接开单RPA接口
- `rpa_work_uuid`字段会保存RPA返回的workUuid，用于后续查询RPA执行状态
- `rpa_queue_uuids`字段会保存4个队列的UUID和ID信息（JSON格式）
- 后台任务会自动轮询RPA状态，当状态变为成功(5)时，会从4个队列中获取数据，创建结算单，然后删除队列
- 当状态变为失败(3)时，也会删除队列
- 如果订舱尚未完成（没有master_airwaybill_number），会返回错误
- 如果订舱的airline不是南方航空，会返回错误
- 如果业务参数配置不存在或缺少南航登录信息，会返回错误

**南航直接开单RPA调用说明**:

- 系统会从业务参数配置中获取南航登录信息，从订舱的master_airwaybill_number中提取waybill_number_8
- RPA接口参数：
  - `system_url`: 从业务参数配置获取（`config_data.china_southern_air.booking_and_create.china_southern_air_login.system_url`）
  - `system_account`: 从业务参数配置获取（`config_data.china_southern_air.booking_and_create.china_southern_air_login.system_account`）
  - `login_password`: 从业务参数配置获取（`config_data.china_southern_air.booking_and_create.china_southern_air_login.login_password`）
  - `waybill_number_8`: 从`booking.master_airwaybill_number`提取（以"-"分割，取最后一部分）

**队列管理说明**:

- 系统会在调用RPA接口之前创建4个队列（与南航新增运单共用队列名称）：
  - `nanhang_air_dingcang_kaidan_queue_rate`（费率队列）
  - `nanhang_air_dingcang_kaidan_queue_freight`（运费队列）
  - `nanhang_air_dingcang_kaidan_queue_fuel_costs`（燃油费队列）
  - `nanhang_air_dingcang_kaidan_queue_extended_service_fee`（延伸服务费队列）
- RPA执行过程中会将数据存入这4个队列
- 当RPA执行成功（status=5）时，系统会从4个队列中获取数据，用于构建结算单：
  - 费率队列数据 → `settlement.form_data.master_rate`
  - 运费队列数据 → `settlement.form_data.master_airline_fee`
  - 燃油费队列数据 → `settlement.form_data.master_fuel_surcharge`
  - 延伸服务费队列数据 → `settlement.form_data.master_transit_fee`
- 无论RPA执行成功还是失败，系统都会删除这4个队列

**结算单创建说明**:

- 当RPA执行成功（status=5）时，系统会自动创建结算单，结算单的form_data包含以下信息：
  - `airline_record_time`: RPA调用时间（格式：年-月-日，精确到日）
  - `settlement_status`: "0"（未结算）
  - `financial_review`: "0"（未审核）
  - `transport_method`: "2"
  - `master_airwaybill_number`: 从`booking.master_airwaybill_number`获取
  - `airline`: "2"（南航）
  - `origin_station`, `destination`, `flight_number`, `flight_date`: 从`booking.form_data.bookings[0]`获取
  - `customer_name`: 从`booking.form_data.bookings[0].shipper_unit`获取
  - `recipient_name`: 从`booking.form_data.bookings[0].consignee`获取
  - `cargo_name`, `quantity`, `weight`: 从`booking.form_data.bookings[0]`获取
  - `master_rate`: 从费率队列获取
  - `master_airline_fee`: 从运费队列获取
  - `master_fuel_surcharge`: 从燃油费队列获取
  - `master_transit_fee`: 从延伸服务费队列获取
  - 其他字段（包括`sub_packaging_fee`、`sub_pickup_fee`、`sub_delivery_fee`等）使用默认空值
- **注意**：订舱的form_data结构是扁平的（`{"airline": "2", "bookings": [...]}`），不包含`other_fees`字段，因此直接开单创建的结算单不会包含用户自定义的其他费用
- 创建结算单后，会更新订舱的`invoice_status`为"3"（成功，数据字典值）
- `invoice_status`字段存储的是数据字典的值，不是中文描述。前端通过数据字典将值转换为对应的中文显示
- RPA接口返回的status会映射到系统的数据字典值：
  - status=1 (执行中) -> invoice_status="1"（对应数据字典：value="1", label="开单中"）
  - status=3 (失败) -> invoice_status="2"（对应数据字典：value="2", label="失败"）
  - status=5 (运行成功) -> invoice_status="3"（对应数据字典：value="3", label="成功"）

**同步创建运单说明**:

- 当RPA执行成功（status=5）时，系统会同步在运单管理（waybills表）中创建一条运单记录
- 订舱的form_data结构（扁平结构，数据在`bookings[0]`中）会自动转换为运单的form_data结构（嵌套结构，按`flight_info`、`cargo_info`等分组）
- 运单记录的字段设置：
  - `waybill_number`: 从`booking.master_airwaybill_number`获取
  - `airline_record_status`: "3"（成功，因为直接开单已成功）
  - `cargo_station_record_status`: "0"（未执行）或 "3"（已录单，如果开关为"0"且货站录单成功）
  - `document_print_status`: "0"（未执行）
  - `waybill_void_status`: "0"（未作废）
  - `booking_date`: 当前日期
  - `rpa_work_uuid`: 同步`booking.rpa_work_uuid`
- 运单form_data字段映射：

| 订舱字段（bookings[0]） | 运单字段 |
|----------------------|---------|
| `origin_station` | `flight_info.origin_station` |
| `destination` | `flight_info.destination` |
| `flight_date` | `flight_info.flight_date` |
| `flight_number` | `flight_info.flight_number` |
| `booking_remark` | `flight_info.booking_remark` |
| `cargo_type` | `cargo_info.cargo_type` |
| `cargo_code` | `cargo_info.cargo_code` |
| `cargo_name` | `cargo_info.cargo_name` |
| `quantity` | `cargo_info.quantity` |
| `weight` | `cargo_info.weight` |
| `product_name` | `cargo_info.product_name` |
| `oversized_cargo` | `cargo_info.oversized_cargo` |
| `special_cargo_code` | `cargo_info.special_cargo_code` |
| `consignee` | `contact_info.consignee` |
| `consignee_phone` | `contact_info.consignee_phone` |
| `shipper_unit` | `contact_info.shipper_unit` |
| 业务参数配置的shipper | `contact_info.shipper` |
| `no_dangerous_goods` | `dangerous_goods_declaration.no_hidden_dangerous_goods` |

**自动触发南航货站录单说明**:

- 当同步创建运单成功后，系统会检查运单form_data中的`oxygenated_aquatic_animal_goods_receipt_inspection_form_switch`字段
- 如果该字段值为"0"，系统会自动触发南航货站录单（生成充氧类水生动物货物收运检查单.xlsx）
- **注意**：由于直接开单的订舱form_data（扁平结构`{"airline": "2", "bookings": [...]}`）通常不包含`oxygenated_aquatic_animal_goods_receipt_inspection_form_switch`字段，因此直接开单通常**不会**触发货站录单
- 如需触发南航货站录单，建议使用"修改数据后开单"接口（`POST /api/v1/bookings/{booking_id}/invoice-with-data`），并在`form_data`中传入`oxygenated_aquatic_animal_goods_receipt_inspection_form_switch: "0"`

---

#### 8.5 南航修改数据后开单

**接口地址**: `POST /api/v1/bookings/{booking_id}/invoice-with-data`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `booking_id`: 订舱ID（字符串格式）

**请求体**（JSON格式）:

```json
{
  "form_data": {
    "airline": "2",
    "flight_info": {
      "origin_station": "SZX",
      "destination": "TAO",
      "flight_date": "2026-01-31",
      "flight_number": "CZ3963",
      "booking_remark": "订舱备注"
    },
    "cargo_info": {
      "cargo_type": "普货",
      "cargo_code": "9000",
      "cargo_name": "上衣",
      "quantity": "1",
      "weight": "10",
      "booking_volume": "0.05",
      "product_name": "商品",
      "oversized_cargo": "0",
      "special_cargo_code": "ACO,AKA"
    },
    "contact_info": {
      "consignee": "李四",
      "consignee_phone": "13800138000",
      "shipper_unit": "XX物流公司",
      "shipper": "张三",
      "shipper_phone": "18979681111",
      "address": {
        "region": "江西省/吉安市/万安县",
        "detail": "科技园南区"
      }
    },
    "dangerous_goods_declaration": {
      "no_hidden_dangerous_goods": "0",
      "agent_checker_signature": "陈晶晶",
      "agent_consignor_signature": "华长水"
    },
    "other_info": {
      "order_contact": "陈xx",
      "contact_phone": "18979681112",
      "settlement_file_number": "123"
    },
    "other_fees": {
      "packaging_fee": "1",
      "pickup_fee": "2",
      "delivery_fee": "3"
    },
    "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "0"
      "pickup_method": "1"
  }
}
```

**请求参数说明**:

- `form_data`: 用户修改后的表单数据（嵌套结构），与运单新增接口的南航`form_data`结构相同
- `oxygenated_aquatic_animal_goods_receipt_inspection_form_switch`: 充氧类水生动物货物收运检查单开关
  - `"0"`: 需要生成充氧类水生动物货物收运检查单（会触发南航货站录单）
  - `"1"` 或不传: 不需要生成

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "269479386711986176",
    "form_data": {...},
    "submitted_form_data": {...},
    "booking_status": "3",
    "invoice_status": "1",
    "booking_time": "2026-01-13T22:54:52+08:00",
    "master_airwaybill_number": "784-47888190",
    "rpa_work_uuid": null,
    "rpa_queue_uuid": null,
    "rpa_queue_id": null,
    "booking_cancel_status": "0",
    "booking_feedback": null,
    "created_at": "2026-01-13T22:54:52+08:00",
    "updated_at": "2026-01-13T22:54:54+08:00",
    "task_id": "274883497007648769"
  },
  "msg": "修改数据后开单已加入执行队列，请等待处理"
}
```

**使用场景**:

1. 用户订舱执行成功后，调用回显接口（`GET /api/v1/bookings/{booking_id}/echo`）获取数据
2. 用户在前端修改数据（如添加`oxygenated_aquatic_animal_goods_receipt_inspection_form_switch: "0"`）
3. 调用此接口传入修改后的`form_data`进行开单
4. 开单成功后，系统会自动同步创建运单记录到waybills表，并自动触发南航货站录单（如果开关为"0"）

**与直接开单的区别**:

| 功能 | 直接开单 | 修改数据后开单 |
|------|---------|--------------|
| 是否需要传入form_data | 否 | 是 |
| form_data来源 | 从订舱的bookings[0]自动转换 | 用户提交的修改后数据 |
| 是否支持other_fees | 否（订舱结构不包含） | 是 |
| 是否支持货站录单开关 | 通常不支持（订舱结构不包含） | 是 |
| 货站录单自动触发 | 通常不触发 | 当开关为"0"时自动触发 |

**自动触发南航货站录单说明**:

- 当RPA执行成功并同步创建运单后，系统会检查用户提交的`form_data`中的`oxygenated_aquatic_animal_goods_receipt_inspection_form_switch`字段
- 如果该字段值为"0"，系统会自动触发南航货站录单
- 货站录单会生成一个xlsx文件：充氧类水生动物货物收运检查单.xlsx（及对应PDF）
- 文档中的运单号、航班号等字段会被替换为实际值
- 货站录单状态变化：`cargo_station_record_status`从"0"变为"1"（执行中），最终变为"3"（已录单）或"2"（失败）

**结算单创建说明**:

- 当RPA执行成功（status=5）时，系统会自动创建结算单
- 结算单的`form_data`会包含用户提交的`other_fees`中的费用：
  - `other_fees.packaging_fee` → `settlement.form_data.sub_packaging_fee`（包装费）
  - `other_fees.pickup_fee` → `settlement.form_data.sub_pickup_fee`（上门提货费）
  - `other_fees.delivery_fee` → `settlement.form_data.sub_delivery_fee`（派送费）

---

### 9. 结算单管理

#### 9.1 新增结算单

**接口地址**: `POST /api/v1/settlements`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

`form_data` 是一个字典结构，包含三大块信息：基础信息、分单信息、主单信息（所有键名使用英文，遵循snake_case命名规范）：

**完整数据结构示例**:

```json
{
  "form_data": {
    "transport_method": "航空运输",
    "airline": "南方航空",
    "origin_station": "CAN",
    "destination": "北京",
    "flight_number": "CZ1234",
    "flight_date": "2025-01-15",
    "airline_record_time": "2025-01-01",
    "master_airwaybill_number": "475-65665",
    "customer_name": "XX物流公司",
    "recipient_name": "收货人名称",
    "cargo_name": "普通货物",
    "quantity": "10",
    "weight": "100.5",
    "chargeable_weight": "105.0",
    "sub_rate": "10.50",
    "sub_airline_fee": "1000.00",
    "sub_document_fee": "50.00",
    "sub_telegraph_fee": "30.00",
    "sub_telegraph_number": "TELE123456",
    "sub_cca_fee": "20.00",
    "sub_packaging_fee": "100.00",
    "sub_pickup_fee": "150.00",
    "sub_airport_pickup_fee": "80.00",
    "sub_delivery_fee": "200.00",
    "sub_carrier_deduction": "50.00",
    "sub_other_fee": "30.00",
    "sub_other_fee_remark": "其他费用说明",
    "sub_total_amount": "1630.00",
    "settlement_method": "月结",
    "sub_remark": "分单备注信息",
    "settlement_status": "未结算",
    "master_airwaybill_number": "475-65665",
    "master_rate": "8.50",
    "master_airline_fee": "850.00",
    "master_fuel_surcharge": "100.00",
    "master_transit_weight": "105.0",
    "master_transit_fee": "50.00",
    "master_cca_cost": "15.00",
    "master_packaging_fee": "80.00",
    "master_telegraph_fee": "25.00",
    "master_pickup_unit": "XX物流公司",
    "master_pickup_fee": "120.00",
    "master_delivery_unit": "YY物流公司",
    "master_airport_pickup_fee": "60.00",
    "master_delivery_fee": "180.00",
    "master_other_fee": "20.00",
      "master_total_cost": "1500.00",
      "master_remark": "主单备注信息",
      "financial_review": "未审核"
    }
}
```

**数据结构详细说明**:

结算单数据主要分为三大块：

**1. 基础信息**（Basic Information）：

- `transport_method`（string，可选）：运输方式，如："航空运输"、"陆运"等
- `airline`（string，必填）：所属航司，如："南方航空"、"深圳航空"等
- `origin_station`（string，可选）：始发站（三字码），如："CAN"、"SZX"等
- `destination`（string，可选）：目的站，如："北京"、"上海"等
- `flight_number`（string，可选）：航班号，如："CZ1234"、"ZH5678"等
- `flight_date`（string，可选）：航班日期（格式：YYYY-MM-DD），如："2025-01-15"
- `airline_record_time`（string，可选）：航司录单时间（格式：YYYY-MM-DD），如："2025-01-01"。如果未提供，列表接口会尝试通过主单号关联运单表获取
- `master_airwaybill_number`（string，可选）：主单号，如："475-65665"（建议包含，用于关联运单表查询航司录单时间）
- `customer_name`（string，可选）：客户名称，如："XX物流公司"
- `recipient_name`（string，可选）：收件人名称
- `cargo_name`（string，可选）：货物名称，如："普通货物"
- `quantity`（string，可选）：件数，如："10"
- `weight`（string，可选）：重量（单位：公斤），如："100.5"
- `chargeable_weight`（string，可选）：计费重量（单位：公斤），如："105.0"

**2. 分单信息**（Sub Waybill Information）：

- `sub_rate`（string，可选）：费率（单价），如："10.50"
- `sub_airline_fee`（string，可选）：航空费用，如："1000.00"
- `sub_document_fee`（string，可选）：制单费，如："50.00"
- `sub_telegraph_fee`（string，可选）：电报费，如："30.00"
- `sub_telegraph_number`（string，可选）：电报号，如："TELE123456"
- `sub_cca_fee`（string，可选）：CCA费用，如："20.00"
- `sub_packaging_fee`（string，可选）：包装费，如："100.00"
- `sub_pickup_fee`（string，可选）：上门提货费，如："150.00"
- `sub_airport_pickup_fee`（string，可选）：机场提货费，如："80.00"
- `sub_delivery_fee`（string，可选）：派送费，如："200.00"
- `sub_carrier_deduction`（string，可选）：承运扣款，如："50.00"
- `sub_other_fee`（string，可选）：其他费用，如："30.00"
- `sub_other_fee_remark`（string，可选）：其他费用备注，如："其他费用说明"
- `sub_total_amount`（string，可选）：总金额，如："1630.00"
- `settlement_method`（string，可选）：结算方式，如："月结"、"现结"等
- `sub_remark`（string，可选）：备注信息
- `settlement_status`（string，可选）：结算状态，可选值：`未结算`、`已结算`（前端点选）

**3. 主单信息**（Master Waybill Information）：

- `master_rate`（string，可选）：费率（单价），如："8.50"
- `master_airline_fee`（string，可选）：航空费用，如："850.00"
- `master_fuel_surcharge`（string，可选）：航空燃油费，如："100.00"
- `master_transit_weight`（string，可选）：过站重量（单位：公斤），如："105.0"
- `master_transit_fee`（string，可选）：过站费，如："50.00"
- `master_cca_cost`（string，可选）：CCA成本，如："15.00"
- `master_packaging_fee`（string，可选）：包装费，如："80.00"
- `master_telegraph_fee`（string，可选）：电报费，如："25.00"
- `master_pickup_unit`（string，可选）：上门提货单位，如："XX物流公司"
- `master_pickup_fee`（string，可选）：上门提货费，如："120.00"
- `master_delivery_unit`（string，可选）：派送单位，如："YY物流公司"
- `master_airport_pickup_fee`（string，可选）：机场提货费，如："60.00"
- `master_delivery_fee`（string，可选）：派送费，如："180.00"
- `master_other_fee`（string，可选）：其他费用，如："20.00"
- `master_total_cost`（string，可选）：成本总金额，如："1500.00"
- `master_remark`（string，可选）：备注信息
- `financial_review`（string，可选）：财务审核状态，可选值：`未审核`、`已审核`（前端点选）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "form_data": {
      "transport_method": "航空运输",
      "airline": "南方航空",
      "origin_station": "CAN",
      "destination": "北京",
      "flight_number": "CZ1234",
      "flight_date": "2025-01-15",
      "airline_record_time": "2025-01-01",
      "master_airwaybill_number": "475-65665",
      "customer_name": "XX物流公司",
      "recipient_name": "收货人名称",
      "cargo_name": "普通货物",
      "quantity": "10",
      "weight": "100.5",
      "chargeable_weight": "105.0",
      "sub_rate": "10.50",
      "sub_airline_fee": "1000.00",
      "sub_document_fee": "50.00",
      "sub_telegraph_fee": "30.00",
      "sub_telegraph_number": "TELE123456",
      "sub_cca_fee": "20.00",
      "sub_packaging_fee": "100.00",
      "sub_pickup_fee": "150.00",
      "sub_airport_pickup_fee": "80.00",
      "sub_delivery_fee": "200.00",
      "sub_carrier_deduction": "50.00",
      "sub_other_fee": "30.00",
      "sub_other_fee_remark": "其他费用说明",
      "sub_total_amount": "1630.00",
      "settlement_method": "月结",
      "sub_remark": "分单备注信息",
      "settlement_status": "未结算",
      "master_rate": "8.50",
      "master_airline_fee": "850.00",
      "master_fuel_surcharge": "100.00",
      "master_transit_weight": "105.0",
      "master_transit_fee": "50.00",
      "master_cca_cost": "15.00",
      "master_packaging_fee": "80.00",
      "master_telegraph_fee": "25.00",
      "master_pickup_unit": "XX物流公司",
      "master_pickup_fee": "120.00",
      "master_delivery_unit": "YY物流公司",
      "master_airport_pickup_fee": "60.00",
      "master_delivery_fee": "180.00",
      "master_other_fee": "20.00",
      "master_total_cost": "1500.00",
      "master_remark": "主单备注信息",
      "financial_review": "未审核"
    },
    "waybill_void_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "结算单创建成功"
}
```

**说明**:

- `form_data`: 表单数据（JSON格式），包含基础信息、分单信息、主单信息三大块
- 所有字段都是可选的，前端可以根据实际业务需要传入相应的字段
- 所有字段的值都是字符串类型（包括数字类型的值也以字符串形式传入，如："100.5"）
- 所有键名使用英文，遵循snake_case命名规范
- **主单号（`master_airwaybill_number`）**：属于基础信息部分，建议包含，用于关联运单表查询航司录单时间
- **结算状态（`settlement_status`）**：属于分单信息部分，前端点选，可选值：`未结算`、`已结算`
- **财务审核（`financial_review`）**：属于主单信息部分，前端点选，可选值：`未审核`、`已审核`
- **运单作废状态（`waybill_void_status`）**：响应中的独立字段（不在form_data中），数据库字段，系统自动同步，无需前端手动维护。当执行运单成功后，系统会自动将运单的作废状态同步到结算单的数据库字段；当运单作废成功后，系统会自动更新结算单中的此字段。数据字典值：`0`=未作废，`1`=作废中，`2`=作废失败，`3`=作废成功

#### 9.2 结算单列表

**接口地址**: `GET /api/v1/settlements`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `airline`: 所属航司（模糊搜索，从form_data JSON中提取，可选）
- `destination`: 目的站（模糊搜索，从form_data JSON中提取，可选）
- `customer_name`: 客户名称/发货人名称（模糊搜索，从form_data JSON中提取，可选）
- `flight_number`: 航班号（模糊搜索，从form_data JSON中提取，可选）
- `master_airwaybill_number`: 主单号（模糊搜索，从form_data JSON中提取，可选）
- `settlement_status`: 结算状态（精确匹配，从form_data JSON中提取，可选值：未结算、已结算，可选）
- `financial_review`: 财务审核状态（精确匹配，从form_data JSON中提取，可选值：未审核、已审核，可选）
- `airline_record_time_start`: 航司录单时间开始（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选，可选）
- `airline_record_time_end`: 航司录单时间结束（格式：YYYY-MM-DD，从 form_data.airline_record_time 筛选，可选）
- `page`: 页码（默认1）
- `pageSize`: 每页数量（默认10，最大200）

**请求示例**: `GET /api/v1/settlements?airline=南方航空&settlement_status=未结算&financial_review=未审核&airline_record_time_start=2025-01-01&airline_record_time_end=2025-01-31&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 10,
    "items": [
      {
        "id": "260819415803760650",
        "airline_record_time": "2025-01-01",
        "airline": "南方航空",
        "master_airwaybill_number": "475-65665",
        "flight_number": "CZ1234",
        "destination": "北京",
        "flight_date": "2025-01-15",
        "shipper_unit": "XX物流公司",
        "quantity": "10",
        "weight": "100.5",
        "chargeable_weight": "105.0",
        "transit_weight": "105.0",
        "cargo_name": "普通货物",
        "customer_name": "XX物流公司",
        "airline_rate": "10.50",
        "airline_fee": "1000.00",
        "packaging_fee": "100.00",
        "pickup_fee": "150.00",
        "waybill_void_status": "0",
        "created_at": "2025-01-01T12:00:00+08:00",
        "updated_at": "2025-01-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**响应字段详细说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `total` | integer | 总记录数 |
| `items` | array[object] | 结算单记录列表 |
| `items[].id` | string | 结算单ID（BigInteger转字符串） |
| `items[].airline_record_time` | string\|null | 航司录单时间（格式：YYYY-MM-DD，通过主单号关联运单表获取，如果主单号不存在或未关联到运单则为null） |
| `items[].airline` | string\|null | 所属航司（从form_data中提取） |
| `items[].master_airwaybill_number` | string\|null | 主单号（从form_data中提取） |
| `items[].flight_number` | string\|null | 航班号（从form_data中提取） |
| `items[].destination` | string\|null | 目的站（从form_data中提取） |
| `items[].flight_date` | string\|null | 航班日期（从form_data中提取，格式：YYYY-MM-DD） |
| `items[].shipper_unit` | string\|null | 托运单位（从form_data.customer_name中提取，托运单位就是客户名称） |
| `items[].quantity` | string\|null | 件数（从form_data中提取） |
| `items[].weight` | string\|null | 重量（从form_data中提取，单位：公斤） |
| `items[].chargeable_weight` | string\|null | 计费重量（从form_data中提取，单位：公斤） |
| `items[].transit_weight` | string\|null | 过站重量（从form_data.master_transit_weight中提取，单位：公斤） |
| `items[].cargo_name` | string\|null | 货物名称（从form_data中提取） |
| `items[].customer_name` | string\|null | 客户名称（从form_data中提取） |
| `items[].airline_rate` | string\|null | 航空费率（从form_data.sub_rate中提取） |
| `items[].airline_fee` | string\|null | 航空运价（从form_data.sub_airline_fee中提取） |
| `items[].packaging_fee` | string\|null | 包装费（从form_data.sub_packaging_fee中提取） |
| `items[].pickup_fee` | string\|null | 上门提货费（从form_data.sub_pickup_fee中提取） |
| `items[].waybill_void_status` | string | 运单作废状态（数据库字段，系统自动同步，数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功） |
| `items[].created_at` | string | 创建时间（中国时间，UTC+8，ISO 8601格式） |
| `items[].updated_at` | string | 更新时间（中国时间，UTC+8，ISO 8601格式） |

**说明**:

- 列表**不包含**运单作废成功的结算单：`waybill_void_status='3'`（作废成功）的数据会被排除，仅展示未作废、作废中、作废失败的记录
- 支持多条件组合筛选
- 航司、目的站、客户名称、航班号、主单号从 `form_data` JSON中提取进行模糊搜索
- 结算状态（`settlement_status`）和财务审核状态（`financial_review`）进行精确匹配筛选
- 航司录单时间（`airline_record_time_start`、`airline_record_time_end`）从结算单 `form_data` JSON 的 `airline_record_time` 字段（格式 YYYY-MM-DD）进行日期范围筛选
- **筛选逻辑说明**：仅按 `form_data.airline_record_time` 筛选，不考虑关联运单。若某条结算单的 form_data 中无 `airline_record_time` 或值为空，则该条不命中时间筛选
- 按创建时间倒序排列（同一时间按ID倒序，确保分页结果稳定）
- **返回数据说明**：列表接口返回的是从form_data中提取的指定字段，而不是完整的form_data。航司录单时间（`airline_record_time`）的获取逻辑：如果通过主单号关联运单表查询到了并且有值，则优先使用运单表的booking_date；如果没有关联上或没有值，则使用form_data中用户输入的airline_record_time；如果都没有，则该字段为`null`
- **字段提取规则**：所有字段都是从结算单的form_data JSON中提取，如果字段不存在则返回`null`
- **托运单位说明**：托运单位（`shipper_unit`）从`customer_name`字段中提取，因为托运单位就是客户名称

#### 9.3 查看结算单详情

**接口地址**: `GET /api/v1/settlements/{settlement_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `settlement_id`: 结算单ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "form_data": {
      "transport_method": "航空运输",
      "airline": "南方航空",
      "origin_station": "CAN",
      "destination": "北京",
      "flight_number": "CZ1234",
      "flight_date": "2025-01-15",
      "customer_name": "XX物流公司",
      "recipient_name": "收货人名称",
      "cargo_name": "普通货物",
      "quantity": "10",
      "weight": "100.5",
      "chargeable_weight": "105.0",
      "sub_rate": "10.50",
      "sub_airline_fee": "1000.00",
      "sub_document_fee": "50.00",
      "sub_telegraph_fee": "30.00",
      "sub_telegraph_number": "TELE123456",
      "sub_cca_fee": "20.00",
      "sub_packaging_fee": "100.00",
      "sub_pickup_fee": "150.00",
      "sub_airport_pickup_fee": "80.00",
      "sub_delivery_fee": "200.00",
      "sub_carrier_deduction": "50.00",
      "sub_other_fee": "30.00",
      "sub_other_fee_remark": "其他费用说明",
      "sub_total_amount": "1630.00",
      "settlement_method": "月结",
      "sub_remark": "分单备注信息",
      "settlement_status": "未结算",
      "master_rate": "8.50",
      "master_airline_fee": "850.00",
      "master_fuel_surcharge": "100.00",
      "master_transit_weight": "105.0",
      "master_transit_fee": "50.00",
      "master_cca_cost": "15.00",
      "master_packaging_fee": "80.00",
      "master_telegraph_fee": "25.00",
      "master_pickup_unit": "XX物流公司",
      "master_pickup_fee": "120.00",
      "master_delivery_unit": "YY物流公司",
      "master_airport_pickup_fee": "60.00",
      "master_delivery_fee": "180.00",
      "master_other_fee": "20.00",
      "master_total_cost": "1500.00",
      "master_remark": "主单备注信息",
      "financial_review": "未审核"
    },
    "waybill_void_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-01T12:00:00+08:00"
  },
  "msg": "查询成功"
}
```

**说明**:

- 返回结算单的完整信息，包括所有表单数据（基础信息、分单信息、主单信息）
- 所有字段都是可选的，实际返回的字段取决于创建时传入的数据
- `waybill_void_status`：运单作废状态（数据库字段，系统自动同步，数据字典值：0=未作废，1=作废中，2=作废失败，3=作废成功）

#### 9.4 修改结算单

**接口地址**: `PUT /api/v1/settlements/{settlement_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `settlement_id`: 结算单ID（字符串格式）

**请求体**:
与新增结算单（9.1）相同，请求体为包含 `form_data` 的对象。`form_data` 为完整表单数据（基础信息、分单信息、主单信息），会**整体替换**该结算单原有的 form_data。字段说明见 9.1 新增结算单。

**请求示例**:

```json
{
  "form_data": {
    "transport_method": "航空运输",
    "airline": "南方航空",
    "origin_station": "CAN",
    "destination": "北京",
    "flight_number": "CZ1234",
    "flight_date": "2025-01-15",
    "airline_record_time": "2025-01-01",
    "master_airwaybill_number": "475-65665",
    "customer_name": "XX物流公司",
    "recipient_name": "收货人名称",
    "cargo_name": "普通货物",
    "quantity": "10",
    "weight": "100.5",
    "chargeable_weight": "105.0",
    "sub_rate": "10.50",
    "sub_airline_fee": "1000.00",
    "sub_document_fee": "50.00",
    "sub_telegraph_fee": "30.00",
    "sub_telegraph_number": "TELE123456",
    "sub_cca_fee": "20.00",
    "sub_packaging_fee": "100.00",
    "sub_pickup_fee": "150.00",
    "sub_airport_pickup_fee": "80.00",
    "sub_delivery_fee": "200.00",
    "sub_carrier_deduction": "50.00",
    "sub_other_fee": "30.00",
    "sub_other_fee_remark": "其他费用说明",
    "sub_total_amount": "1630.00",
    "settlement_method": "月结",
    "sub_remark": "分单备注信息",
    "settlement_status": "未结算",
    "master_rate": "8.50",
    "master_airline_fee": "850.00",
    "master_fuel_surcharge": "100.00",
    "master_transit_weight": "105.0",
    "master_transit_fee": "50.00",
    "master_cca_cost": "15.00",
    "master_packaging_fee": "80.00",
    "master_telegraph_fee": "25.00",
    "master_pickup_unit": "XX物流公司",
    "master_pickup_fee": "120.00",
    "master_delivery_unit": "YY物流公司",
    "master_airport_pickup_fee": "60.00",
    "master_delivery_fee": "180.00",
    "master_other_fee": "20.00",
    "master_total_cost": "1500.00",
    "master_remark": "主单备注信息",
    "financial_review": "未审核"
  }
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "260819415803760650",
    "form_data": { ... },
    "waybill_void_status": "0",
    "created_at": "2025-01-01T12:00:00+08:00",
    "updated_at": "2025-01-02T14:30:00+08:00"
  },
  "msg": "结算单修改成功"
}
```

**说明**:

- 仅更新 `form_data`，`waybill_void_status` 由系统根据运单作废状态同步，不可通过本接口修改
- 请求体中的 `form_data` 会整体替换原结算单的 form_data，建议前端先调用「查看结算单详情」获取当前数据，修改后再提交
- 若结算单不存在（无效的 settlement_id），返回 404 及「结算单不存在」
- 响应结构与「查看结算单详情」一致，便于前端刷新详情

---

### 11. RPA任务队列

RPA任务队列用于管理所有RPA相关操作（订舱、退舱、开单、运单作废等）的执行。系统采用队列模式，所有RPA操作先入队列，然后由后台Worker按顺序执行。

#### 11.1 队列模式说明

**工作流程**：

```
用户触发操作 → 创建任务入队 → 返回任务ID → Worker取任务执行 → 更新目标状态
       ↓                                            ↑
  前端轮询任务状态或目标状态（运单/订舱状态）
```

**任务类型**：

| 任务类型 | 描述 | 目标类型 |
|---------|------|---------|
| `SHENZHEN_AIR_WAYBILL_EXECUTE` | 深航开单 | waybill |
| `SHENZHEN_AIR_WAYBILL_VOID` | 深航作废 | waybill |
| `SHENZHEN_AIR_BILLING_TIME_CONTAINER` | 深航计飞时间-集装器数据获取 | waybill |
| `SHENZHEN_AIR_TRANSIT_LOADING` | 深航过机-装机数据获取 | waybill |
| `CHINA_SOUTHERN_AIR_BOOKING_EXECUTE` | 南航订舱 | booking |
| `CHINA_SOUTHERN_AIR_BOOKING_CANCEL` | 南航退舱 | booking |
| `CHINA_SOUTHERN_AIR_DIRECT_INVOICE` | 南航直接开单 | booking |
| `SHENZHEN_AIR_KEEP_LOGIN` | 深航保持登录（定时入队） | keep_login |
| `CHINA_SOUTHERN_AIR_KEEP_LOGIN` | 南航保持登录（定时入队） | keep_login |
| `TANGYI_KEEP_LOGIN` | 唐翼保持登录（定时入队） | keep_login |

**任务状态**：

| 状态 | 描述 |
|-----|------|
| `pending` | 待执行（在队列中等待） |
| `running` | 执行中（已被Worker取出正在执行） |
| `success` | 执行成功 |
| `failed` | 执行失败 |
| `timeout` | 执行超时 |

**配置项**（`app/config.py`）：

| 配置项 | 说明 | 默认值 |
|-------|------|-------|
| `RPA_QUEUE_ENABLED` | 是否启用队列模式 | `True` |
| `RPA_QUEUE_POLL_INTERVAL` | Worker轮询队列间隔（秒） | `2` |
| `RPA_QUEUE_DEFAULT_PRIORITY` | 默认任务优先级 | `1` |
| `RPA_QUEUE_WORKER_COUNT` | Worker数量（对应RPA机器人数量） | `1` |
| `RPA_QUEUE_TASK_TIMEOUT` | RPA接口调用超时时间（秒） | `30` |
| `RPA_QUEUE_CLEANUP_DAYS` | 已完成任务保留天数 | `7` |
| `RPA_KEEP_LOGIN_ENABLED` | 是否启用保持登录定时入队 | `True` |
| `RPA_SHENZHEN_AIR_KEEP_LOGIN_INTERVAL_SECONDS` | 深航保持登录执行间隔（秒，未配置则不入队） | （默认不启用） |
| `RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_INTERVAL_SECONDS` | 南航保持登录执行间隔（秒，未配置则不入队） | （默认不启用） |
| `RPA_TANGYI_KEEP_LOGIN_INTERVAL_SECONDS` | 唐翼保持登录执行间隔（秒，未配置则不入队） | （默认不启用） |
| `ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_INTERVAL_SECONDS` | 南航出港状态通知同步任务执行间隔（秒） | `600` |
| `ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_FIXED_TIMES` | 南航出港状态通知按时间点触发（HH:MM格式） | `""` |

#### 11.2 查询任务状态

**接口地址**: `GET /api/v1/rpa-tasks/{task_id}`

**请求参数**:

- `task_id`: 任务ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "270123456789012345",
    "task_type": "SHENZHEN_AIR_WAYBILL_EXECUTE",
    "target_type": "waybill",
    "target_id": "269012345678901234",
    "status": "running",
    "priority": 1,
    "work_uuid": "abc123def456...",
    "job_uuid": "e1b259766b97e5e115c21b2614158a5f",
    "result": null,
    "error_message": null,
    "created_by": "265404865910542336",
    "created_at": "2026-01-16T10:00:00+08:00",
    "started_at": "2026-01-16T10:00:05+08:00",
    "finished_at": null
  },
  "msg": "查询成功"
}
```

**说明**:

- 任务完成（成功或失败）后会自动从队列中删除
- 如果返回404，表示任务不存在或已完成

#### 11.3 查询任务列表

**接口地址**: `GET /api/v1/rpa-tasks`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|-----|------|-----|------|
| `task_type` | string | 否 | 任务类型 |
| `target_type` | string | 否 | 目标类型（waybill/booking） |
| `target_id` | string | 否 | 目标ID |
| `status` | string | 否 | 任务状态 |
| `page` | int | 否 | 页码，默认1 |
| `pageSize` | int | 否 | 每页数量，默认10，最大200 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 5,
    "page": 1,
    "pageSize": 10,
    "list": [
      {
        "id": "270123456789012345",
        "task_type": "SHENZHEN_AIR_WAYBILL_EXECUTE",
        "target_type": "waybill",
        "target_id": "269012345678901234",
        "status": "pending",
        "priority": 1,
        "work_uuid": null,
        "error_message": null,
        "created_at": "2026-01-16T10:00:00+08:00",
        "started_at": null,
        "finished_at": null
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 11.4 获取队列统计信息

**接口地址**: `GET /api/v1/rpa-tasks/stats/queue`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "pending_count": 3,
    "running_count": 1,
    "worker_count": 1,
    "queue_enabled": true
  },
  "msg": "查询成功"
}
```

#### 11.5 取消/删除任务

**接口地址**: `DELETE /api/v1/rpa-tasks/{task_id}`

**说明**:

- 只能删除`pending`状态的任务
- `running`状态的任务无法取消

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "任务已删除"
}
```

#### 11.6 运单/订舱接口变更说明

启用队列模式后，以下接口的行为发生变化：

| 接口 | 变更说明 |
|-----|---------|
| `POST /api/v1/waybills/{id}/execute` | 不再直接调用RPA，而是创建任务入队，返回`task_id` |
| `POST /api/v1/waybills/{id}/void` | 不再直接调用RPA，而是创建任务入队，返回`task_id` |
| `POST /api/v1/bookings/execute` | 不再直接调用RPA，而是批量创建任务入队，返回每个订舱的执行结果（包含`task_id`） |
| `POST /api/v1/bookings/{id}/cancel` | 不再直接调用RPA，而是创建任务入队，返回`task_id` |
| `POST /api/v1/bookings/{id}/direct-invoice` | 不再直接调用RPA，而是创建任务入队，返回`task_id` |

**响应示例**（以运单执行为例）:

```json
{
  "code": 0,
  "data": {
    "id": "269012345678901234",
    "waybill_number": null,
    "form_data": {...},
    "airline_record_status": "0",
    "cargo_station_record_status": "0",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2026-01-16T10:00:00+08:00",
    "cargo_station_record_time": "2026-01-16T10:00:00+08:00",
    "document_print_time": "2026-01-16T10:00:00+08:00",
    "departure_time": null,
    "booking_date": "2026-01-16",
    "rpa_work_uuid": null,
    "rpa_queue_uuids": null,
    "created_at": "2026-01-16T10:00:00+08:00",
    "updated_at": "2026-01-16T10:00:00+08:00",
    "task_id": "270123456789012345"
  },
  "msg": "运单已加入执行队列，请等待处理"
}
```

**前端轮询策略**:

1. 可以轮询任务状态接口 `GET /api/v1/rpa-tasks/{task_id}`
2. 也可以轮询运单/订舱详情接口，查看状态是否更新
3. 当任务完成后，目标（运单/订舱）的状态会自动更新

---

## 12. 运单管理扩展接口

### 12.1 深航货站录单（自动执行机制）

**自动执行说明**:

- 当深圳航空的运单航司录单成功（`airline_record_status = "3"`）后，系统会**自动**执行货站录单
- 自动执行过程中会根据条件生成以下文档：
  - 交接单（仅当 `cargo_info.cargo_code == "044"` 时生成）
  - 航空货物明细表（仅当 `form_data.declaration_list == "0"` 时生成）
  - 货物收运检查清单（仅当 `cargo_info.cargo_code == "044"` 时生成）
  - 标签单（必生成）
  - 充氧类水生动物货物收运检查单（仅当 `oxygenated_aquatic_animal_goods_receipt_inspection_form_switch == "0"` 时生成）
- 生成的Excel和PDF文件会自动保存到 `generated_files/{waybill_id}/` 目录
- 文件使用固定命名（不带时间戳），如：`交接单.xlsx`、`交接单.pdf`、`标签单.xlsx`
- **前端无需调用任何接口触发货站录单**，只需轮询运单状态即可

**货站录单状态说明**:

- `0`: 未执行
- `1`: 执行中
- `2`: 执行失败
- `3`: 已录单（执行成功）

**条件生成字段说明**:

- **declaration_list**：航空货物明细表开关，`"0"` 表示需要生成，其他值或不传表示不需要
- **airline_consent_certificate**：航空公司同意运输证明编号，非空时替换交接单中的"深航安检编号：74"
- **oxygen_supply_test_results**：充氧类检查结果（蔬菜品名等），用于充氧类水生动物货物收运检查单中的检查结果替换
- **oxygenated_aquatic_animal_goods_receipt_inspection_form_switch**：`"0"` 表示需要生成充氧类文档
  - **pickup_method**：可选。提货方式（独立字段，不参与RPA开单）

### 12.1.1 南航货站录单（自动执行机制）

**自动执行说明**:

- **南航货站录单仅在 `oxygenated_aquatic_animal_goods_receipt_inspection_form_switch = "0"` 时才会执行**
- 当南方航空的运单航司录单成功（`airline_record_status = "3"`）且开关为"0"时，系统会**自动**执行货站录单
- 自动执行过程中会生成以下文档：
  - 充氧类水生动物货物收运检查单.xlsx（Excel格式，同时转换为PDF）
- 生成的xlsx和PDF文件会自动保存到 `generated_files/{waybill_id}/` 目录
- 文件使用固定命名（不带时间戳），如：`充氧类水生动物货物收运检查单.xlsx`
- **前端无需调用任何接口触发货站录单**，只需轮询运单状态即可

**货站录单状态说明**:

- `0`: 未执行
- `1`: 执行中
- `2`: 执行失败
- `3`: 已录单（执行成功）

**与深航货站录单的区别**:

| 对比项 | 深圳航空 | 南方航空 |
|--------|---------|---------|
| 触发条件 | 开单成功后始终执行 | 开单成功且开关为"0"时才执行 |
| 文档数量 | 4-5个（取决于开关） | 1个 |
| 文档格式 | Excel + PDF | Excel + PDF |
| 文档存储目录 | `generated_files/{waybill_id}/` | `generated_files/{waybill_id}/` |
| 文件命名 | 固定命名（如`交接单.xlsx`） | 固定命名（如`充氧类水生动物货物收运检查单.xlsx`） |

### 12.2 深航货站录单重新执行

**接口地址**: `POST /api/v1/waybills/{waybill_id}/cargo-station-record`

**说明**:

- **正常情况下，货站录单会自动执行，无需调用此接口**
- 此接口用于以下场景：
  1. 货站录单自动执行失败后的重新执行
  2. 需要重新生成文档的情况（会覆盖原有文件）
- 仅针对深圳航空
- 使用纯Python实现Excel转PDF，无需安装Microsoft Excel
- 文件使用固定命名（不带时间戳），重新执行会覆盖原有文件

**前提条件**:

- 运单必须是深圳航空（`airline = "1"` 或 `"深圳航空"`）
- 航司录单状态必须为成功（`airline_record_status = "3"`）
- 运单号（`waybill_number`）必须已存在

**请求头**:

```
Authorization: Bearer <access_token>
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "269012345678901234",
    "waybill_number": "479-12345678",
    "form_data": {...},
    "airline_record_status": "3",
    "cargo_station_record_status": "3",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2026-01-21T10:10:00+08:00",
    "cargo_station_record_time": "2026-01-21T10:30:00+08:00",
    "document_print_time": "2026-01-21T10:00:00+08:00",
    "departure_time": null,
    "booking_date": "2026-01-21",
    "rpa_work_uuid": null,
    "created_at": "2026-01-21T10:00:00+08:00",
    "updated_at": "2026-01-21T10:30:00+08:00",
    "documents": {
      "handover": {
        "excel": "generated_files/269012345678901234/交接单.xlsx",
        "pdf": "generated_files/269012345678901234/交接单.pdf"
      },
      "cargo_detail": {
        "excel": "generated_files/269012345678901234/航空货物明细表.xlsx",
        "pdf": "generated_files/269012345678901234/航空货物明细表.pdf"
      },
      "cargo_checklist": {
        "excel": "generated_files/269012345678901234/货物收运检查清单.xlsx",
        "pdf": "generated_files/269012345678901234/货物收运检查清单.pdf"
      },
      "label": {
        "excel": "generated_files/269012345678901234/标签单.xlsx",
        "pdf": "generated_files/269012345678901234/标签单.pdf"
      }
    }
  },
  "msg": "货站录单执行成功"
}
```

**错误响应示例**:

```json
{
  "code": 400,
  "data": null,
  "msg": "货站录单功能仅支持深圳航空"
}
```

### 12.3 获取运单相关文档

**接口地址**: `GET /api/v1/waybills/{waybill_id}/documents`

**说明**:

- 获取运单关联的货站录单文档信息或下载文档
- 支持深圳航空和南方航空的货站录单文档
- 不传`doc_type`参数时，返回所有文档的路径信息（根据航司类型返回对应文档）
- 传`doc_type`参数时，返回指定文档的文件内容（用于下载）

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| doc_type | string | 否 | 文档类型（见下方说明），不传则返回所有文档列表 |
| file_format | string | 否 | 文件格式：支持 `pdf`（默认）或 `excel` |

**深圳航空文档类型**:

| doc_type | 对应文档 | 说明 |
|----------|---------|------|
| handover | 交接单 | 货物交接记录（仅当 cargo_code == "044" 时生成） |
| cargo_detail | 航空货物明细表 | 货物详细信息（仅当 declaration_list == "0" 时生成） |
| cargo_checklist | 货物收运检查清单 | 收运检查记录（仅当 cargo_code == "044" 时生成） |
| label | 标签单 | 货物标签信息（必生成） |
| aquatic_animal_checklist | 充氧类水生动物货物收运检查单 | 水生动物收运检查记录（仅当开关为"0"时生成） |

**南方航空文档类型**:

| doc_type | 对应文档 | 说明 |
|----------|---------|------|
| csa_aquatic_animal_checklist | 充氧类水生动物货物收运检查单 | 水生动物收运检查记录（xlsx格式，仅当开关为"0"时生成） |

**请求头**:

```
Authorization: Bearer <access_token>
```

**响应示例（深航 - 列出所有文档）**:

请求：`GET /api/v1/waybills/269012345678901234/documents`

```json
{
  "code": 0,
  "data": {
    "waybill_id": "269012345678901234",
    "waybill_number": "479-12345678",
    "airline": "1",
    "documents": {
      "handover": {
        "excel": "generated_files/269012345678901234/交接单.xlsx",
        "pdf": "generated_files/269012345678901234/交接单.pdf"
      },
      "cargo_detail": {
        "excel": "generated_files/269012345678901234/航空货物明细表.xlsx",
        "pdf": "generated_files/269012345678901234/航空货物明细表.pdf"
      },
      "cargo_checklist": {
        "excel": "generated_files/269012345678901234/货物收运检查清单.xlsx",
        "pdf": "generated_files/269012345678901234/货物收运检查清单.pdf"
      },
      "label": {
        "excel": "generated_files/269012345678901234/标签单.xlsx",
        "pdf": "generated_files/269012345678901234/标签单.pdf"
      },
      "aquatic_animal_checklist": {
        "excel": "generated_files/269012345678901234/充氧类水生动物货物收运检查单.xlsx",
        "pdf": "generated_files/269012345678901234/充氧类水生动物货物收运检查单.pdf"
      }
    }
  },
  "msg": "查询成功"
}
```

> **注意**: `aquatic_animal_checklist` 只有在运单的 `form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch = "0"` 时才会出现在列表中。

**响应示例（南航 - 列出所有文档）**:

请求：`GET /api/v1/waybills/269012345678901235/documents`

```json
{
  "code": 0,
  "data": {
    "waybill_id": "269012345678901235",
    "waybill_number": "784-12345678",
    "airline": "2",
    "documents": {
      "csa_aquatic_animal_checklist": {
        "excel": "generated_files/269012345678901235/充氧类水生动物货物收运检查单.xlsx",
        "pdf": "generated_files/269012345678901235/充氧类水生动物货物收运检查单.pdf"
      }
    }
  },
  "msg": "查询成功"
}
```

> **注意**: 南航的 `csa_aquatic_animal_checklist` 只有在运单的 `form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch = "0"` 时才会出现在列表中。

**响应示例（下载指定文档 - 深航）**:

请求：`GET /api/v1/waybills/269012345678901234/documents?doc_type=handover&file_format=pdf`

返回：PDF文件下载流，Content-Type为`application/pdf`，文件名为`交接单_479-12345678.pdf`

请求：`GET /api/v1/waybills/269012345678901234/documents?doc_type=cargo_detail&file_format=excel`

返回：Excel文件下载流，Content-Type为`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`，文件名为`航空货物明细表_479-12345678.xlsx`

**响应示例（下载指定文档 - 南航）**:

请求：`GET /api/v1/waybills/269012345678901235/documents?doc_type=csa_aquatic_animal_checklist&file_format=pdf`

返回：PDF文件下载流，Content-Type为`application/pdf`，文件名为`充氧类水生动物货物收运检查单_784-12345678.pdf`

**文档类型说明（深航）**:

| doc_type | 对应文档 | 支持格式 | 说明 |
|----------|---------|---------|------|
| handover | 交接单 | pdf, excel | 货物交接记录（仅当 cargo_code == "044" 时生成） |
| cargo_detail | 航空货物明细表 | pdf, excel | 货物详细信息（仅当 declaration_list == "0" 时生成） |
| cargo_checklist | 货物收运检查清单 | pdf, excel | 收运检查记录（仅当 cargo_code == "044" 时生成） |
| label | 标签单 | pdf, excel | 货物标签信息（必生成） |
| aquatic_animal_checklist | 充氧类水生动物货物收运检查单 | pdf, excel | 水生动物收运检查记录（仅当开关为"0"时生成） |

**文档类型说明（南航）**:

| doc_type | 对应文档 | 支持格式 | 说明 |
|----------|---------|---------|------|
| csa_aquatic_animal_checklist | 充氧类水生动物货物收运检查单 | pdf, excel | 水生动物收运检查记录（仅当开关为"0"时生成） |

**错误响应示例**:

```json
{
  "code": 404,
  "data": null,
  "msg": "文档不存在: 交接单"
}
```

---

### 12.4 单据打印（自动触发）

**说明**:

- 打单功能在航司录单成功后**自动触发**，不需要手动调用接口
- 系统会根据航司类型自动执行对应的打印流程
- **打单延迟**：货站录单成功后，系统会等待一段时间再执行打单（等待文件生成和传输完成）。延迟时间通过业务参数配置中的 `config_data.{航司}.document.print_delay_after_cargo_station_record` 配置，单位为秒，默认30，设为0则不延迟

**自动打单流程说明**:

航司录单 → 货站录单(制单) → （延迟等待文件传输）→ 打单 是一条龙服务，自动串联执行：

**深圳航空**:

1. 航司录单成功（`airline_record_status = "3"`）→ 自动触发货站录单
2. 货站录单成功（`cargo_station_record_status = "3"`）→ 延迟等待 → 自动触发打单

**南方航空**:

1. 航司录单成功（`airline_record_status = "3"`）→ 自动触发货站录单（仅当 `oxygenated_aquatic_animal_goods_receipt_inspection_form_switch = "0"` 时）
2. 货站录单成功（`cargo_station_record_status = "3"`）→ 延迟等待 → 自动触发打单（制单文档打印 + 固定打印流程）
3. 如果不需要制单（开关不为 "0"），航司录单成功后**直接触发固定打印流程**（无延迟，因为没有生成文件需要传输）

**注意**：南航订舱后的开单（直接开单 `/direct-invoice` 和修改数据后开单 `/invoice-with-data`）成功后也会自动触发上述制单和打单流程。

**深圳航空打单流程**:

1. **制单后打印流程**：遍历 `generated_files/{waybill_id}/` 目录下的所有文件（仅 xlsx 和 docx，跳过 pdf），对每个文件调用文件打印RPA接口
2. **货运主单打印流程（固定）**：调用深航货运主单打印RPA接口

**南方航空打单流程**:

1. **制单后打印流程（可选）**：如果 `generated_files/{waybill_id}/` 目录存在，遍历目录下的所有文件（仅 xlsx 和 docx，跳过 pdf），对每个文件调用文件打印RPA接口
2. **货运主单打印流程（固定）**：调用南航货运主单打印RPA接口
3. **货运安检申报单打印流程（固定）**：调用南航货运安检申报单打印RPA接口
4. **标签打印流程（固定）**：调用南航标签打印RPA接口

**打印机配置说明**:

- 打印机名称从业务参数配置中的 `print.printer_config` 获取
- 配置格式：`[{"document_type": "文档类型", "printer_name": "打印机名称"}]`
- 深航配置路径：`shenzhen_air.print.printer_config`
- 南航配置路径：`china_southern_air.print.printer_config`

**打单执行策略**:

- 打单包含多个子任务（制单文档打印 + 固定打印流程），所有子任务**均会被执行**，不会因为某个子任务失败而中断后续任务
- 全部子任务执行完成后，只要**有一个子任务失败**，整体打单状态即为失败（`document_print_status = "2"`）
- 只有全部子任务都成功，整体打单状态才为成功（`document_print_status = "3"`）

**打单状态说明（document_print_status）**:

- `0`: 未执行
- `1`: 执行中
- `2`: 失败（全部子任务执行完毕后，存在至少一个失败的子任务）
- `3`: 成功（全部子任务均执行成功）

---

### 12.5 单个文档打印

**接口地址**: `POST /api/v1/waybills/{waybill_id}/print-document`

**说明**:

- 用于单个文档的重新打印（打印失败后重试或需要再打印一份时使用）
- 支持文件打印和固定打印流程
- 文件打印仅支持 xlsx 和 docx 格式，pdf 文件不参与打印
- 需要先完成航司录单（`airline_record_status = "3"`）且运单号存在

**请求参数**:

| 参数名 | 类型 | 必填 | 说明 |
|-------|------|------|------|
| waybill_id | String | 是 | 运单ID（路径参数） |
| print_type | String | 是 | 打印类型 |
| doc_type | String | 否 | 文档类型（当 print_type 为 "file" 时必填） |

**print_type 可选值**:

| 值 | 说明 | 适用航司 |
|-----|------|---------|
| file | 文件打印（指定 doc_type 从 generated_files 目录查找文件） | 深航/南航 |
| main_waybill | 航司货运主单打印 | 深航/南航 |
| security_declaration | 安检申报单打印 | 仅南航 |
| label | 标签打印 | 仅南航 |

**doc_type 可选值（当 print_type 为 "file" 时）**:

| 文档类型 | 说明 | 适用航司 |
|---------|------|---------|
| 交接单 | 深航制单文档（仅当 cargo_code == "044" 时生成） | 深航 |
| 航空货物明细表 | 深航制单文档（仅当 declaration_list == "0" 时生成） | 深航 |
| 货物收运检查清单 | 深航制单文档（仅当 cargo_code == "044" 时生成） | 深航 |
| 标签单 | 深航制单文档（必生成） | 深航 |
| 充氧类水生动物货物收运检查单 | 深航/南航制单文档 | 深航/南航 |

**请求示例（文件打印）**:

```
POST /api/v1/waybills/269012345678901234/print-document?print_type=file&doc_type=交接单
```

**请求示例（航司货运主单打印）**:

```
POST /api/v1/waybills/269012345678901234/print-document?print_type=main_waybill
```

**请求示例（南航安检申报单打印）**:

```
POST /api/v1/waybills/269012345678901235/print-document?print_type=security_declaration
```

**请求示例（南航标签打印）**:

```
POST /api/v1/waybills/269012345678901235/print-document?print_type=label
```

**响应示例（成功 - 文件打印）**:

```json
{
  "code": 0,
  "data": {
    "id": "269012345678901234",
    "waybill_number": "479-12345678",
    "form_data": {...},
    "airline_record_status": "3",
    "cargo_station_record_status": "3",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-15T10:05:00+08:00",
    "cargo_station_record_time": "2025-01-15T10:10:00+08:00",
    "document_print_time": "2025-01-15T10:00:00+08:00",
    "booking_date": "2025-01-15",
    "created_at": "2025-01-15T10:00:00+08:00",
    "updated_at": "2025-01-15T10:00:00+08:00",
    "print_task": {
      "task_id": "275000000000000001",
      "print_type": "file",
      "doc_type": "交接单",
      "description": "文档打印-交接单",
      "airline": "shenzhen_air"
    }
  },
  "msg": "打印任务已提交：文档打印-交接单"
}
```

**响应示例（成功 - 航司货运主单打印）**:

```json
{
  "code": 0,
  "data": {
    "id": "269012345678901234",
    "waybill_number": "479-12345678",
    "form_data": {...},
    "airline_record_status": "3",
    "cargo_station_record_status": "3",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-15T10:05:00+08:00",
    "cargo_station_record_time": "2025-01-15T10:10:00+08:00",
    "document_print_time": "2025-01-15T10:00:00+08:00",
    "booking_date": "2025-01-15",
    "created_at": "2025-01-15T10:00:00+08:00",
    "updated_at": "2025-01-15T10:00:00+08:00",
    "print_task": {
      "task_id": "275000000000000002",
      "print_type": "main_waybill",
      "doc_type": null,
      "description": "深航-货运主单打印",
      "airline": "shenzhen_air"
    }
  },
  "msg": "打印任务已提交：深航-货运主单打印"
}
```

**响应示例（成功 - 南航安检申报单打印）**:

```json
{
  "code": 0,
  "data": {
    "id": "269012345678901235",
    "waybill_number": "784-12345678",
    "form_data": {...},
    "airline_record_status": "3",
    "cargo_station_record_status": "3",
    "document_print_status": "0",
    "waybill_void_status": "0",
    "airline_record_time": "2025-01-15T10:05:00+08:00",
    "cargo_station_record_time": "2025-01-15T10:10:00+08:00",
    "document_print_time": "2025-01-15T10:00:00+08:00",
    "booking_date": "2025-01-15",
    "created_at": "2025-01-15T10:00:00+08:00",
    "updated_at": "2025-01-15T10:00:00+08:00",
    "print_task": {
      "task_id": "275000000000000003",
      "print_type": "security_declaration",
      "doc_type": null,
      "description": "南航-货运安检申报单打印",
      "airline": "china_southern_air"
    }
  },
  "msg": "打印任务已提交：南航-货运安检申报单打印"
}
```

**错误响应示例**:

```json
{
  "code": 400,
  "data": null,
  "msg": "无效的打印类型，有效值：file, main_waybill, security_declaration, label"
}
```

```json
{
  "code": 400,
  "data": null,
  "msg": "文件打印类型必须指定 doc_type 参数"
}
```

```json
{
  "code": 400,
  "data": null,
  "msg": "运单尚未完成航司录单，无法执行打印"
}
```

```json
{
  "code": 400,
  "data": null,
  "msg": "未找到文档：交接单，请确认货站录单已完成"
}
```

```json
{
  "code": 400,
  "data": null,
  "msg": "安检申报单打印仅支持南航"
}
```

```json
{
  "code": 400,
  "data": null,
  "msg": "未配置文档 交接单 的打印机，请检查业务参数中的打印机配置"
}
```

---

### 10. 通知管理

#### 10.1 获取通知数据

**接口地址**: `GET /api/v1/notifications`

**接口说明**: 获取通知数据，用于系统右上角小铃铛通知功能。返回待执行任务和异常任务的详细数据。

**权限要求**: 需要登录认证

**待执行任务来源**:

- waybills表中 `airline_record_status = "0"`（未开单）的数据
- bookings表中 `booking_status = "0"`（未执行）的数据

**异常任务来源**:

- waybills表中 `airline_record_status = "2"`（失败）的数据
- bookings表中 `booking_status = "2"`（失败）的数据

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "pending_tasks": {
      "total": 3,
      "items": [
        {
          "id": "269012345678901234",
          "task_type": "开单",
          "source_table": "waybills",
          "airline": "1",
          "airline_name": "深圳航空",
          "flight_number": "ZH9801",
          "task_date": "2025-01-15",
          "customer_name": "XX物流公司",
          "quantity": "10",
          "weight": "100.5",
          "cargo_type": "普通货物",
          "exception_time": null
        },
        {
          "id": "269012345678901235",
          "task_type": "订舱",
          "source_table": "bookings",
          "airline": "2",
          "airline_name": "南方航空",
          "flight_number": "CZ1234",
          "task_date": "2025-01-15T10:30:00+08:00",
          "customer_name": "",
          "quantity": "5",
          "weight": "50.0",
          "cargo_type": "电子产品",
          "exception_time": null
        }
      ]
    },
    "exception_tasks": {
      "total": 2,
      "items": [
        {
          "id": "269012345678901236",
          "task_type": "开单",
          "source_table": "waybills",
          "airline": "1",
          "airline_name": "深圳航空",
          "flight_number": "ZH9802",
          "task_date": "2025-01-14",
          "customer_name": "YY货运公司",
          "quantity": "20",
          "weight": "200.0",
          "cargo_type": "普通货物",
          "exception_time": "2025-01-14T15:30:00+08:00"
        },
        {
          "id": "269012345678901237",
          "task_type": "订舱",
          "source_table": "bookings",
          "airline": "2",
          "airline_name": "南方航空",
          "flight_number": "CZ5678",
          "task_date": "2025-01-14T09:00:00+08:00",
          "customer_name": "",
          "quantity": "8",
          "weight": "80.0",
          "cargo_type": "服装",
          "exception_time": "2025-01-14T16:45:00+08:00"
        }
      ]
    }
  },
  "msg": "查询成功"
}
```

**响应字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| pending_tasks | Object | 待执行任务 |
| pending_tasks.total | Integer | 待执行任务总数 |
| pending_tasks.items | Array | 待执行任务列表 |
| exception_tasks | Object | 异常任务 |
| exception_tasks.total | Integer | 异常任务总数 |
| exception_tasks.items | Array | 异常任务列表 |

**任务项字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | String | 任务ID（waybill_id 或 booking_id） |
| task_type | String | 任务类型："开单" 或 "订舱" |
| source_table | String | 来源表："waybills" 或 "bookings" |
| airline | String | 航空公司（数据字典值：1=深圳航空，2=南方航空） |
| airline_name | String | 航空公司名称 |
| flight_number | String | 航班号 |
| task_date | String | 任务日期（开单为日期格式，订舱为时间格式） |
| customer_name | String | 客户名称（仅开单有，订舱为空） |
| quantity | String | 数量 |
| weight | String | 重量 |
| cargo_type | String | 货物类型/名称 |
| exception_time | String | 异常时间（仅异常任务有，取自 updated_at 字段） |

**数据来源说明**:

| 字段 | 开单(waybills) | 订舱(bookings) |
|------|---------------|----------------|
| airline | form_data.airline | form_data.airline |
| flight_number | form_data.flight_info.flight_number | form_data.bookings[0].flight_number |
| task_date | booking_date（日期） | booking_time（时间） |
| customer_name | 深航: form_data.shipper_consignee_info.shipper_unit<br>南航: form_data.contact_info.shipper_unit | 无（为空） |
| quantity | form_data.cargo_info.quantity | form_data.bookings[0].quantity |
| weight | form_data.cargo_info.weight | form_data.bookings[0].weight |
| cargo_type | 深航: form_data.cargo_info.cargo_name<br>南航: form_data.cargo_info.cargo_type | form_data.bookings[0].cargo_type |
| exception_time | updated_at | updated_at |

**说明**: 通过 `approval_data_id`（即 `china_southern_air_approval_data.id`）判断是否已存在，存在则更新，不存在则新增。手动数据与南航批复主表通过 `approval_data_id` 进行关联，与 `csa_product_information`、`csa_lalamove_information` 保持一致。

#### 深航出港运单单据审核与暂存

**接口地址**: `POST /api/v1/departure-tracking/shenzhen-air/audit`

**请求参数**:

- `waybill_number_8`: 必填，单号后8位。
- `action`: 必填，`draft`（暂存）或 `submit`（提交审核）。
- 其他与手动数据（如 `customer_name`）相同的可选字段。

**请求示例**:

```json
{
  "waybill_number_8": "12345678",
  "action": "draft",
  "customer_name": "某测试客户",
  "cargo_type": "普货",
  "packaging_fee": "100",
  "delivery_fee": "200",
  "manual_total_amount": "300",
  "remark": "这是一个暂存的测试备注"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "暂存成功" // 或 "审核成功"
}
```

#### 南航出港运单单据审核与暂存

**接口地址**: `POST /api/v1/departure-tracking/china-southern-air/audit`

**请求参数**:

- `approval_data_id`: 必填，关联的 `china_southern_air_approval_data.id`。
- `action`: 必填，`draft`（暂存）或 `submit`（提交审核）。
- 其他与手动数据相同的可选字段。

**请求示例**:

```json
{
  "approval_data_id": "260819415803760650",
  "action": "submit",
  "customer_name": "某测试客户",
  "cargo_type": "电子产品",
  "door_pickup_fee": "150",
  "airport_pickup_fee": "50",
  "manual_total_amount": "200",
  "remark": "确认审核无误"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "审核成功" // 或 "暂存成功"
}
```

---

#### 10.2 获取通知数量摘要

**接口地址**: `GET /api/v1/notifications/summary`

**接口说明**: 获取通知数量摘要，用于小铃铛显示未读数量徽章。只返回数量，不返回详细数据，性能更好。

**权限要求**: 需要登录认证

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "pending_count": 3,
    "exception_count": 2,
    "total_count": 5
  },
  "msg": "查询成功"
}
```

**响应字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| pending_count | Integer | 待执行任务数量 |
| exception_count | Integer | 异常任务数量 |
| total_count | Integer | 总数量（pending_count + exception_count） |

---

#### 10.3 取消等待中的队列任务

**接口地址**: `DELETE /api/v1/notifications/cancel-task`

**接口说明**: 取消通知列表中等待执行的队列任务，同时删除对应的源数据（waybills 或 bookings 表中的记录）。支持批量操作，一次可取消多个任务。

**权限要求**: 需要登录认证

**请求参数**（JSON Body）:

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| ids | Array[String] | 是 | 任务目标ID列表，即通知接口返回的 id 字段列表（waybill_id 或 booking_id），至少1个 |
| source_table | String | 是 | 来源表，即通知接口返回的 source_table 字段（"waybills" 或 "bookings"） |

**请求示例**:

```json
{
  "ids": ["274883497007648768", "274883497007648770", "274883497007648111"],
  "source_table": "bookings"
}
```

**执行逻辑**:

1. 根据 source_table 确定目标类型和源数据模型
   - waybills → target_type = "waybill"，源数据模型 = Waybill
   - bookings → target_type = "booking"，源数据模型 = Booking
2. 遍历每个 ID：
   - 检查 rpa_tasks 表中是否有 running 状态的任务，如有则跳过该 ID
   - 查找 rpa_tasks 表中对应的 pending 状态的任务
   - **安全校验**：如果该 ID 没有任何等待中（pending）任务存在，说明其不可取消（如已成功/失败等状态），强行保护，跳过该 ID
   - 仅在存在 pending 任务的情况下：删除关联的 pending 任务，并连带删除 waybills 或 bookings 表中对应的源记录
3. 统一提交事务，返回操作结果大盘

**注意事项**:

- **仅待执行安全清理机制**：本接口强行挂钩 RPA 等待队列，没有队列堆积的数据均不应当被操作。已成功（或其他不存在 pending 任务）的数据会被机制自动保护免删。
- 如果某个 ID 对应的 RPA 任务正在执行中（running），该 ID 会被无损跳过并记录为 `skipped_ids`。
- 如果某个 ID 不拥有 pending RPA 记录对象，会跳过并记录为 `not_found_ids`。
- **消息提示（msg）专为前端设计**：返回的 `msg`（如"取消成功"、"任务正在执行中，无法取消"）可直接用作前端友好的 Toast 弹窗提示。

**响应示例（成功、跳过、未找到混合场景）**:

```json
{
  "code": 0,
  "data": {
    "deleted_count": 1,
    "deleted_ids": ["274883497007648768"],
    "deleted_rpa_task_ids": ["274883497007648769"],
    "skipped_ids": ["274883497007648770"],
    "not_found_ids": ["274883497007648111"]
  },
  "msg": "成功取消 1 个任务，跳过 2 个不可取消的任务"
}
```

**响应示例（没有找到任何需要删除的任务情况）**:

```json
{
  "code": 0,
  "data": {
    "deleted_count": 0,
    "deleted_ids": [],
    "deleted_rpa_task_ids": [],
    "skipped_ids": [],
    "not_found_ids": ["274883497007648111", "274883497007648112"]
  },
  "msg": "所选任务均正在执行或状态已刷新，无法取消"
}
```

**响应字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| deleted_count | Integer | 成功删除的目标数量 |
| deleted_ids | Array[String] | 成功删除的目标ID列表（waybill_id 或 booking_id） |
| deleted_rpa_task_ids | Array[String] | 删除的 RPA 任务ID列表 |
| skipped_ids | Array[String] | 因任务正在执行中而被跳过的目标ID列表 |
| not_found_ids | Array[String] | 因为不存在 pending 任务而被保护免删的目标ID列表 |

---

### 10. 单号库管理

#### 10.0 创建单号库

**接口地址**: `POST /api/v1/waybill-stocks/pools`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "airline_name": "china_southern_air",
  "total_authorized_count": 50000
}
```

**请求参数说明**:

| 字段名 | 类型 | 是否必填 | 说明 |
|--------|------|---------|------|
| airline_name | string | 是 | 航司名称（如 `china_southern_air`） |
| total_authorized_count | integer | 否 | 核定单号总数 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "280000000000000001"
  },
  "msg": "创建单号库成功"
}
```

---

#### 10.1A 单号预览

**接口地址**: `POST /api/v1/waybill-stocks/preview`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "first_number": "13349851",
  "last_number": "13353126",
  "stock_id": "280000000000000001"
}
```

**请求参数说明**:

| 字段名 | 类型 | 是否必填 | 说明 |
|--------|------|---------|------|
| first_number | string | 是 | 首单号（数字后缀部分） |
| last_number | string | 是 | 尾单号（数字后缀部分） |
| stock_id | string | 是 | 关联单号库ID |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total_count": 20,
    "full_numbers": [
      "784-13349851",
      "784-13349862",
      "..."
    ]
  },
  "msg": "预览成功"
}
```

**说明**:

- 用于在正式提交领单前，根据编码规则预览即将生成的完整单号列表及其总数
- 系统会自动根据 `stock_id` 关联的单号库所属航司匹配前缀

---

#### 10.1 新增单号（领单）

**接口地址**: `POST /api/v1/waybill-stocks`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "claim_date": "2026-12-30",
  "first_number": "13349851",
  "last_number": "13353126",
  "claim_quantity": 20,
  "stock_id": "280000000000000001"
}
```

**请求参数说明**:

| 字段名 | 类型 | 是否必填 | 说明 |
|--------|------|---------|------|
| claim_date | string (date) | 是 | 领单日期，格式：YYYY-MM-DD |
| first_number | string | 是 | 首单号（数字后缀部分），最长50字符 |
| last_number | string | 是 | 尾单号（数字后缀部分），最长50字符 |
| claim_quantity | integer | 是 | 领单数量（必须与首尾单号计算结果一致） |
| stock_id | string | 是 | 关联单号库ID（字符串格式） |

**单号生成规则说明**:

- 个位数从 0-6 循环（共7个有效值）
- 个位数每变一次，十位数递增1
- 百位及以上正常十进制递进
- 首单号个位数必须在 0-6 范围内
- 系统会根据关联单号库所属航司自动匹配单号前缀（如南航对应 `784-`）
- 生成的单号不得超过尾单号

**生成示例**（从 13349851 开始生成 20 个）:

```
784-13349851, 784-13349862, 784-13349873, 784-13349884, 784-13349895,
784-13349906, 784-13349910, 784-13349921, 784-13349932, 784-13349943,
784-13349954, 784-13349965, 784-13349976, 784-13349980, 784-13349991,
784-13350002, 784-13350013, 784-13350024, 784-13350035, 784-13350046
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "280000000000000001",
    "batch_id": "280000000000000001",
    "claim_date": "2026-12-30",
    "first_number": "13349851",
    "last_number": "13353126",
    "claim_quantity": 20,
    "airline_name": "china_southern_air",
    "number_prefix": "784-",
    "total_authorized_count": 50000,
    "created_at": "2026-12-30T10:00:00+08:00",
    "updated_at": "2026-12-30T10:00:00+08:00"
  },
  "msg": "新增单号成功"
}
```

**说明**:

- 新增领单时会同步批量生成所有单号详情记录，使用状态默认为 `0`（未使用）
- **强校验**: 提交的 `claim_quantity` 必须与 `first_number` 和 `last_number` 之间按规则生成的有效单号数量完全一致，否则返回 400 错误并提示正确数量
- 航司名称通过 `stock_id` 自动关联，无需再次传递
- 生成的单号数量超过首尾号范围时返回 400 错误

---

#### 10.2 单号详情列表

**接口地址**: `GET /api/v1/waybill-stocks/{stock_id}/items`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `stock_id`: 关联单号库ID（字符串格式）

**查询参数**:

- `batch_id`: 领单批次ID精确筛选（可选，字符串格式）
- `claim_date_range`: 领单日期范围（可选，格式：YYYY-MM-DD,YYYY-MM-DD）
- `usage_date_range`: 用单日期范围（可选，格式：YYYY-MM-DD,YYYY-MM-DD）
- `usage_status`: 使用状态筛选（可选，0=未使用，1=已使用）
- `is_abnormal`: 异常状态筛选（可选，0=异常，1=正常）
- `is_invalid`: 失效状态筛选（可选，0=未失效，1=已失效）
- `is_all`: 是否获取全部数据，传 `true` 时忽略分页参数直接返回该筛选条件下的全量数据（可选，布尔值）
- `page`: 页码（可选，默认1）
- `pageSize`: 每页数量（可选，默认10，最大200）

**请求示例**: `GET /api/v1/waybill-stocks/280000000000000001/items?usage_status=0&is_abnormal=1&is_invalid=0&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 20,
    "items": [
      {
        "id": "280000000000000101",
        "batch_id": "280000000000000001",
        "claim_date": "2026-12-30",
        "number_prefix": "784-",
        "number_suffix": "13349851",
        "full_number": "784-13349851",
        "usage_status": "0",
        "is_abnormal": "1",
        "is_invalid": "0",
        "invalid_reason": null,
        "usage_date": null,
        "created_at": "2026-12-30T10:00:00+08:00",
        "updated_at": "2026-12-30T10:00:00+08:00"
      },
      {
        "id": "280000000000000102",
        "batch_id": "280000000000000001",
        "claim_date": "2026-12-30",
        "number_prefix": "784-",
        "number_suffix": "13349862",
        "full_number": "784-13349862",
        "usage_status": "0",
        "is_abnormal": "1",
        "is_invalid": "0",
        "invalid_reason": null,
        "usage_date": null,
        "created_at": "2026-12-30T10:00:00+08:00",
        "updated_at": "2026-12-30T10:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**响应字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 单号详情ID（BigInteger转字符串） |
| batch_id | string | 关联领单批次ID |
| claim_date | string | 领单日期（YYYY-MM-DD） |
| number_prefix | string | 单号前缀（如 `784-`） |
| number_suffix | string | 单号后缀（数字部分） |
| full_number | string | 完整单号（前缀+后缀，如 `784-13349851`） |
| usage_status | string | 使用状态：`0`=未使用，`1`=已使用 |
| is_abnormal | string | 异常状态：`0`=异常，`1`=正常 |
| is_invalid | string | 失效状态：`0`=未失效，`1`=已失效 |
| invalid_reason | string | 失效原因登记 |
| usage_date | string | 用单日期（YYYY-MM-DD） |
| created_at | string | 创建时间（中国时间UTC+8） |
| updated_at | string | 更新时间（中国时间UTC+8） |

**说明**:

- 单号详情列表按单号后缀升序排列
- 如果领单批次不存在，返回 404 错误

---

#### 10.3 单号详情获取

**接口地址**: `GET /api/v1/waybill-stocks/items/{item_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `item_id`: 单号详情ID（字符串格式）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "280000000000000101",
    "batch_id": "280000000000000001",
    "claim_date": "2026-12-30",
    "number_prefix": "784-",
    "number_suffix": "13349851",
    "full_number": "784-13349851",
    "usage_status": "0",
    "is_abnormal": "1",
    "is_invalid": "0",
    "invalid_reason": null,
    "usage_date": null,
    "created_at": "2026-12-30T10:00:00+08:00",
    "updated_at": "2026-12-30T10:00:00+08:00"
  },
  "msg": "查询单号详情成功"
}
```

---

#### 10.4 单号编辑

**接口地址**: `PUT /api/v1/waybill-stocks/items/{item_id}`

**请求头**: `Authorization: Bearer <token>`

**路径参数**:

- `item_id`: 单号详情ID（字符串格式）

**请求参数**:

```json
{
  "claim_date": "2026-12-31",
  "number_prefix": "784-",
  "number_suffix": "13349852",
  "usage_status": "1",
  "is_abnormal": "1",
  "is_invalid": "0",
  "invalid_reason": "信息录入错误",
  "usage_date": "2026-12-31"
}
```

**请求参数说明**:

| 字段名 | 类型 | 是否必填 | 说明 |
|--------|------|---------|------|
| claim_date | string (date) | 否 | 领单日期，格式：YYYY-MM-DD |
| number_prefix | string | 否 | 单号前缀（如 `784-`），最长20字符 |
| number_suffix | string | 否 | 单号后缀（数字部分），最长50字符 |
| usage_status | string | 否 | 使用状态：`0`=未使用，`1`=已使用 |
| is_abnormal | string | 否 | 异常状态：`0`=异常，`1`=正常 |
| is_invalid | string | 否 | 失效状态：`0`=未失效，`1`=已失效 |
| invalid_reason | string | 否 | 失效原因登记 |
| usage_date | string | 否 | 用单日期，格式：YYYY-MM-DD |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "280000000000000101",
    "batch_id": "280000000000000001",
    "claim_date": "2026-12-31",
    "number_prefix": "784-",
    "number_suffix": "13349852",
    "full_number": "784-13349852",
    "usage_status": "1",
    "is_abnormal": "1",
    "is_invalid": "0",
    "invalid_reason": "信息录入错误",
    "usage_date": "2026-12-31",
    "created_at": "2026-12-30T10:00:00+08:00",
    "updated_at": "2026-12-31T09:00:00+08:00"
  },
  "msg": "单号编辑成功"
}
```

**说明**:

- 单号编辑仅能针对未使用状态(`usage_status=0`)的单号，如果提交非未使用的单号会返回 400 错误
- 即使前端上传了所有字段，系统目前仅允许修改 `is_abnormal`、`is_invalid` 和 `invalid_reason` 这三个字段，其他字段将被忽略
- 如果单号详情不存在，返回 404 错误
- `is_abnormal` 只接受 `0`、`1` 两个值
- `is_invalid` 只接受 `0`、`1` 两个值

---

#### 10.5 批量删除单号

**接口地址**: `DELETE /api/v1/waybill-stocks/items`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "item_ids": [
    "280000000000000101",
    "280000000000000102"
  ]
}
```

**请求参数说明**:

| 字段名 | 类型 | 是否必填 | 说明 |
|--------|------|---------|------|
| item_ids | array (string) | 是 | 要删除的单号详情ID列表 |

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "成功删除 2 个单号"
}
```

**说明**:

- 接口接收包含多个 `item_id` 的数组，进行批量删除
- 空列表或没有匹配的单号时，不抛错，返回成功并提示无记录被删除
- 单号删除仅能针对未使用状态(`usage_status=0`)的单号。只要列表中包含任何非未使用状态的单号，接口会直接抛出 400 错误，取消整个批量删除操作
- 成功删除后，所属领单批次的领单数量 (`claim_quantity`) 会相应地减去被删除的数量

---

#### 10.6 领单统计（领单列表）

**接口地址**: `GET /api/v1/waybill-stocks`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `stock_id`: 单号库ID精确筛选（可选）
- `page`: 页码（可选，默认1）
- `pageSize`: 每页数量（可选，默认10，最大200）

**请求示例**: `GET /api/v1/waybill-stocks?stock_id=280000000000000001&page=1&pageSize=10`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 3,
    "items": [
      {
        "id": "280000000000000001",
        "batch_id": "280000000000000001",
        "stock_id": "280000000000000001",
        "claim_date": "2026-12-30",
        "first_number": "13349851",
        "last_number": "13353126",
        "claim_quantity": 20,
        "airline_name": "china_southern_air",
        "number_prefix": "784-",
        "unused_count": 18,
        "used_count": 1,
        "abnormal_count": 1,
        "invalid_count": 0,
        "created_at": "2026-12-30T10:00:00+08:00",
        "updated_at": "2026-12-30T10:00:00+08:00"
      },
      {
        "id": "280000000000000002",
        "batch_id": "280000000000000002",
        "stock_id": "280000000000000001",
        "claim_date": "2026-12-25",
        "first_number": "13355001",
        "last_number": "13360000",
        "claim_quantity": 50,
        "airline_name": "china_southern_air",
        "number_prefix": "784-",
        "unused_count": 50,
        "used_count": 0,
        "abnormal_count": 0,
        "invalid_count": 0,
        "created_at": "2026-12-25T10:00:00+08:00",
        "updated_at": "2026-12-25T10:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

**响应字段说明**:

| 字段名 | 类型 | 说明 |
|--------|------|------|
| id | string | 领单批次ID（BigInteger转字符串） |
| batch_id | string | 领单批次ID（等同于id，方便前端关联） |
| stock_id | string | 关联的单号库ID |
| claim_date | string | 领单日期（YYYY-MM-DD） |
| first_number | string | 首单号（数字后缀部分） |
| last_number | string | 尾单号（数字后缀部分） |
| claim_quantity | integer | 领单数量 |
| airline_name | string | 航司名称 |
| number_prefix | string | 单号前缀（如 `784-`） |
| unused_count | integer | 未使用个数 |
| used_count | integer | 已使用个数 |
| abnormal_count | integer | 异常个数 |
| invalid_count | integer | 失效个数 |
| created_at | string | 创建时间（中国时间UTC+8） |
| updated_at | string | 更新时间（中国时间UTC+8） |

**说明**:

- 领单列表按创建时间倒序排列（同一时间按ID倒序，确保分页结果稳定）
- 支持按航司名称精确筛选
- 不传 `stock_id` 时返回所有库的领单记录

---

## 错误响应格式

所有错误响应都遵循统一格式：

```json
{
  "code": 401,
  "data": null,
  "msg": "无效的token或token已过期"
}
```

## 错误码说明

- `0`: 成功
- `400 Bad Request`: 请求参数错误
- `401 Unauthorized`: 未认证或token无效
- `403 Forbidden`: 无权限访问
- `404 Not Found`: 资源不存在
- `409 Conflict`: 资源冲突（如重复创建）
- `422 Unprocessable Entity`: 请求参数验证失败
- `500 Internal Server Error`: 服务器内部错误

## 权限说明

- **管理员权限（admin）**: 可以访问所有接口，包括账号管理、部门管理等
- **非管理员**: 只能访问用户中心、客户管理等基础功能接口
- 需要管理员权限的接口会在接口说明中标注
- 所有权限相关的输入输出都使用权限代码（如 `admin`, `waybill`, `booking`, `settlement`, `customer`）

## Token说明

- **access_token**: 访问token，用于访问需要认证的接口，默认有效期30天
- **refresh_token**: 刷新token，用于获取新的access_token和refresh_token，默认有效期90天
- 当access_token过期时，使用refresh_token调用刷新接口获取新token
- token需要在请求头中携带：`Authorization: Bearer <access_token>`
- token的时间戳基于中国时间（UTC+8）生成
- **JWT失效机制**: 当用户的权限被修改时，系统会自动使该用户的所有JWT失效，用户需要重新登录。这是为了确保权限变更后，用户必须重新登录以获取新的菜单和权限信息。

## 菜单结构说明

登录接口返回的 `menus` 字段是简化版的菜单结构，只包含 `name` 和 `children` 字段：

```json
{
  "name": "主单管理",
  "children": [
    {"name": "运单管理"},
    {"name": "订舱管理"}
  ]
}
```

菜单根据用户权限动态生成，管理员拥有所有菜单，其他权限根据权限代码映射到对应的菜单。

## 其他系统集成规范

### RPA 数据队列生命周期与自愈机制

针对 RPA 任务强依赖数据队列读取运行的特性，平台实现了针对 RPA 队列生命周期的闭环护航及自愈管理，开发者无需手动关心队列挂起后的清理逻辑：

1. **防呆闭环清理 (try...finally)**：
所有涉及队列管理的 RPA 异步工作流（深航/南航运单，订舱任务，修改数据后开单等）都在核心处理代码使用了严格的 `try...finally` 包裹。无论是系统抛出严重超时还是运行中代码异常错误，`finally` 闭环都会可靠地回收 RPA 队列释放空间。并且提供 3 次重试以保障网络抖动引起的数据堆积，最终将本地 DB 中对应的 ID 置为 Null。

2. **自动自查自愈 (select-queue-list 回收机制)**：
当因为服务端断电重启造成 `finally` 被非正常跨越时（可能造成 RPA 服务留存死锁队列），下次执行 `create_queue` 时若响应 `400 队列已存在` 异常报错，平台会**静默拦截异常**：
   - 使用 RPA 查询接口 `/openAPI/v1/queue/select-queue-list` 查询 `queueName` 对应的挂起队列 ID 列表。
   - 遍历并强制 `delete_queue`。
   - 随后自愈重新创建队列，业务层实现无感化对接处理。

---

# 机器人管理

## 1. 新增或修改机器人

**接口地址**: `POST /api/v1/robots`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**请求体**:

```json
{
  "id": "1234567890123456789",
  "robot_id": "TjhDVMEhmvG2kQCf0FuNfx2v1FvxQKnQL24GMmju-Qs=",
  "name": "深航制单机器人1号",
  "location": "深圳宝安机场",
  "location_required": 1,
  "task_permissions": ["SHENZHEN_AIR_WAYBILL_EXECUTE", "FILE_PRINT"],
  "extra_config": {
    "shenzhen_air_account": {
      "account": "sz_account1",
      "password": "sz_password1"
    },
    "printer_service": {
      "normal_a4_printer": "A4打印机01",
      "dot_matrix_printer": "针式打印机01",
      "label_printer": "标签打印机01"
    },
    "tangyi_program": {
      "executable_path": "C:\\Program Files\\Tangyi\\tangyi.exe"
    }
  },
  "status": 1
}
```

**请求字段说明**:

| 字段名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| id | string | 否 | 机器人记录ID（传入则为修改已有机器人，不传则为新增） |
| robot_id | string | 是 | 机器人真实ID（必须是通过加密工具加密后的字符串） |
| name | string | 是 | 机器人名称 |
| location | string | 是 | 机器人所在位置 |
| location_required | integer | 否 | 是否启用location区域限制（1=开启，0=关闭，默认为1） |
| task_permissions | array | 是 | 机器人可执行的任务权限列表（参考任务权限列表接口获取有效值） |
| extra_config | object | 否 | 机器人其他配置（JSON对象） |
| status | integer | 否 | 机器人状态（1=启用，0=未启用，默认为1） |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "1234567890123456789",
    "robot_id": "TjhDVMEhmvG2kQCf0FuNfx2v1FvxQKnQL24GMmju-Qs=",
    "name": "深航制单机器人1号",
    "location": "深圳宝安机场",
    "location_required": 1,
    "task_permissions": ["SHENZHEN_AIR_WAYBILL_EXECUTE", "FILE_PRINT"],
    "job_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": "1c1d2f422fe13fae4ea1620b5a0b0ffe",
      "FILE_PRINT": "8aef03178d04720fdbcc7ea66c7cb00d"
    },
    "job_name_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": "深航开单_qm9HeDCH9bi6xRotCrP3Joi51uM6YWvP_2026_05_06_19_24_38",
      "FILE_PRINT": "制单文件打印_qm9HeDCH9bi6xRotCrP3Joi51uM6YWvP_2026_05_06_19_24_38"
    },
    "queue_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": {
        "waybill_number": "shenzhen_air_waybill_execute_queue_waybill_number_1234567890123456789",
        "freight_rate": "shenzhen_air_waybill_execute_queue_freight_rate_1234567890123456789",
        "freight": "shenzhen_air_waybill_execute_queue_freight_1234567890123456789",
        "delivery_fee": "shenzhen_air_waybill_execute_queue_delivery_fee_1234567890123456789"
      }
    },
    "extra_config": { ... },
    "status": 1,
    "created_at": "2026-05-02T10:00:00+08:00",
    "updated_at": "2026-05-02T10:00:00+08:00"
  },
  "msg": "机器人新增成功"
}
```

> **注意**：修改机器人时，系统会先清理旧的远程 RPA Job 和本地 robot_jobs/robot_queues 记录，再根据新的数据重新创建。

---

## 2. 获取机器人列表

**接口地址**: `GET /api/v1/robots`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**查询参数**:

- `status`: 机器人状态筛选（可选，0=未启用，1=启用）
- `page`: 页码（可选，默认1）
- `pageSize`: 每页数量（可选，默认10，最大200）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "1234567890123456789",
        "robot_id": "TjhDVMEhmvG2kQCf0FuNfx2v1FvxQKnQL24GMmju-Qs=",
        "name": "深航制单机器人1号",
        "location": "深圳宝安机场",
        "location_required": 1,
        "task_permissions": ["SHENZHEN_AIR_WAYBILL_EXECUTE", "FILE_PRINT"],
        "extra_config": {
          "shenzhen_air_account": {
            "account": "sz_account1",
            "password": "sz_password1"
          },
          "printer_service": {
            "normal_a4_printer": "A4打印机01",
            "dot_matrix_printer": "针式打印机01",
            "label_printer": "标签打印机01"
          },
          "tangyi_program": {
            "executable_path": "C:\\Program Files\\Tangyi\\tangyi.exe"
          }
        },
        "status": 1,
        "created_at": "2026-05-02T10:00:00+08:00",
        "updated_at": "2026-05-02T10:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

---

## 3. 获取可分配任务权限列表

**接口地址**: `GET /api/v1/robots/task-types`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**功能说明**:
返回系统中现有的 RPA 任务类型及其对应中文描述，用于前端在配置机器人 `task_permissions` 时提供复选框或下拉列表的选项数据源。

**响应示例**:

```json
{
  "code": 0,
  "data": [
    {
      "value": "SHENZHEN_AIR_WAYBILL_EXECUTE",
      "label": "SHENZHEN_AIR_WAYBILL_EXECUTE",
      "description": "深航开单"
    },
    {
      "value": "SHENZHEN_AIR_BILLING_TIME_CONTAINER",
      "label": "SHENZHEN_AIR_BILLING_TIME_CONTAINER",
      "description": "深航计飞时间-集装器数据获取"
    },
    {
      "value": "SHENZHEN_AIR_TRANSIT_LOADING",
      "label": "SHENZHEN_AIR_TRANSIT_LOADING",
      "description": "深航过机-装机数据获取"
    },
            {
                "value": "SHENZHEN_AIR_APPROVAL_DATA",
                "label": "SHENZHEN_AIR_APPROVAL_DATA",
                "description": "深航订舱-批复数据获取"
            },
    {
      "value": "FILE_PRINT",
      "label": "FILE_PRINT",
      "description": "单据打印"
    }
  ],
  "msg": "查询成功"
}
```

---

## 13. 单号库管理扩展接口

### 13.1 单号库总览

**接口地址**: `GET /api/v1/waybill-stocks/overview`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `bill` 或 `admin` 权限

**功能说明**:
返回包括航司名称、核定单号总数、已领用单号数、可领用单号数、未使用单号数、已使用单号数。
返回结构为一个数组，支持查询所有航司（如果不传airline_name）或特定航司。
可领用单号数计算规则：多个批次的领单首尾号区间的最大领用数之和 - 已领用单号数。
核定单号总数取该航司最新一次领单中输入的总数。

**查询参数**:

- `airline_name`: 航司名称（可选，如 `china_southern_air`）

**响应示例**:

```json
{
  "code": 0,
  "data": [
    {
      "stock_id": "280000000000000001",
      "airline_name": "china_southern_air",
      "total_authorized_count": 50000,
      "claimed_count": 1000,
      "claimable_count": 12000,
      "unused_count": 950,
      "used_count": 50
    }
  ],
  "msg": "获取单号库总览成功"
}
```

---

### 13.2 获取单号库核定单号总数

**接口地址**: `GET /api/v1/waybill-stocks/{stock_id}/authorized-count`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `bill` 或 `admin` 权限

**功能说明**:
获取指定单号库的最新核定单号总数，用于在新增单号页面自动带入之前输入的数值。

**路径参数**:

- `airline_name`: 航司名称（必填，如 `china_southern_air`）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total_authorized_count": 50000
  },
  "msg": "获取成功"
}
```

---

### 13.3 获取机器人详情

**接口地址**: `GET /api/v1/robots/{robot_id}`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**功能说明**:
根据主键ID获取机器人详情。

**路径参数**:

- `robot_id`: 机器人主键ID（数字形式，不是加密的robot_id）

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "1",
    "robot_id": "TjhDVMEhmvG2kQCf0FuNfx2v1FvxQKnQL24GMmju-Qs=",
    "name": "测试机器人",
    "location": "深圳",
    "location_required": 1,
    "task_permissions": ["SHENZHEN_AIR_WAYBILL_EXECUTE"],
    "job_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": "1c1d2f422fe13fae4ea1620b5a0b0ffe"
    },
    "job_name_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": "深航开单_qm9HeDCH9bi6xRotCrP3Joi51uM6YWvP_2026_05_06_19_24_38"
    },
    "queue_mapping": {
      "SHENZHEN_AIR_WAYBILL_EXECUTE": {
        "waybill_number": "shenzhen_air_waybill_execute_queue_waybill_number_1",
        "freight_rate": "shenzhen_air_waybill_execute_queue_freight_rate_1",
        "freight": "shenzhen_air_waybill_execute_queue_freight_1",
        "delivery_fee": "shenzhen_air_waybill_execute_queue_delivery_fee_1"
      }
    },
    "extra_config": null,
    "status": 1,
    "created_at": "2026-05-02T10:00:00+08:00",
    "updated_at": "2026-05-02T10:00:00+08:00"
  },
  "msg": "查询成功"
}
```

---

### 13.4 删除机器人

**接口地址**: `DELETE /api/v1/robots/{robot_id}`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**功能说明**:
删除机器人及其所有关联资源。执行以下清理步骤：

1. 远程调用 RPA 接口删除该机器人的所有 Job
2. 删除本地 `robot_jobs` 记录
3. 删除本地 `robot_queues` 记录
4. 删除 `robots` 表记录
5. 停止对应的 Worker 线程

**路径参数**:

- `robot_id`: 机器人主键ID（数字形式，不是加密的robot_id）

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "机器人 深航制单机器人1号 删除成功"
}
```

---

## 机器人流程配置管理 (TaskProcess)

### 1. 获取所有任务流程配置

**接口地址**: `GET /api/v1/robots/task-processes`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**响应示例**:

```json
{
  "code": 0,
  "data": [
    {
      "id": "281234567890123456",
      "task_name": "SHENZHEN_AIR_WAYBILL_EXECUTE",
      "chinese_name": "深航开单",
      "process_detail_uuid": "48d171b3599415cfe6ebed3b19c2c4b8",
      "version": "0.0.67",
      "process_param": { ... },
      "created_at": "2026-05-05T10:00:00+08:00",
      "updated_at": "2026-05-05T10:00:00+08:00"
    }
  ],
  "msg": "success"
}
```

---

### 2. 维护任务流程配置 (新增或修改)

**接口地址**: `POST /api/v1/robots/task-processes`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

**功能说明**:
维护任务名称与 RPA 流程 UUID 的映射关系。
**特别注意**：如果修改了 `process_detail_uuid`，系统会自动触发所有拥有该权限的机器人的 RPA Job 重新生成。

**请求参数**:

```json
{
  "task_name": "SHENZHEN_AIR_WAYBILL_EXECUTE",
  "chinese_name": "深航开单",
  "process_detail_uuid": "48d171b3599415cfe6ebed3b19c2c4b8",
  "version": "0.0.67",
  "process_param": {
    "system_url": "https://www.kinggo.com/login#362",
    "system_account": "szxfdh005"
  }
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": { ... },
  "msg": "任务流程配置更新成功"
}
```

---

### 3. 删除任务流程配置

**接口地址**: `DELETE /api/v1/robots/task-processes/{task_name}`

**请求头**: `Authorization: Bearer <token>`

**权限要求**: 需要 `robot` 或 `admin` 权限

---

### 14. 客户管理（三期需求）

#### 14.1 新增客户（三期扩展）

**接口地址**: `POST /api/v1/customers`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "company_name": "千方航空",
  "rate": 15.5,
  "contact_person": "张三",
  "contact_phone": "13800138000",
  "minimum_ticket_fee": 100.0,
  "document_fee": 50.0,
  "minimum_ticket_fee_condition": 100.0,
  "document_fee_condition": 0.0,
  "weight_range_operation_fee_rate": {
    "≤ 45公斤": 5.0,
    "45 - 100公斤（不含100）": 4.5,
    "100 - 300公斤（不含300）": 4.0,
    "300 - 500公斤（不含500）": 3.5,
    "500 - 1000公斤（不含1000）": 3.0,
    "1000 - 2000公斤（不含2000）": 2.5,
    "≥ 2000公斤": 2.0,
    "不限重量": 3.0
  },
  "cargo_type_transit_fee_rate": {
    "普货": 1.0,
    "生鲜": 1.5,
    "锂电池": 2.0
  },
  "settlement_cycle": 3,
  "is_invoiced": true,
        "creator_id": "987654321",
        "creator_name": "张三"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "1234567890",
    "customer_code": "QFAK20260601",
    "company_name": "千方航空",
    "rate": 15.5,
    "contact_person": "张三",
    "contact_phone": "13800138000",
    "minimum_ticket_fee": 100.0,
    "document_fee": 50.0,
    "minimum_ticket_fee_condition": 100.0,
    "document_fee_condition": 0.0,
    "weight_range_operation_fee_rate": {
      "≤ 45公斤": 5.0,
      "45 - 100公斤（不含100）": 4.5,
      "100 - 300公斤（不含300）": 4.0,
      "300 - 500公斤（不含500）": 3.5,
      "500 - 1000公斤（不含1000）": 3.0,
      "1000 - 2000公斤（不含2000）": 2.5,
      "≥ 2000公斤": 2.0,
      "不限重量": 3.0
    },
    "cargo_type_transit_fee_rate": {
      "普货": 1.0,
      "生鲜": 1.5,
      "锂电池": 2.0
    },
    "settlement_cycle": 3,
    "is_invoiced": true,
        "creator_id": "987654321",
        "creator_name": "张三",
    "created_at": "2026-06-01T12:00:00+08:00",
    "updated_at": "2026-06-01T12:00:00+08:00"
  },
  "msg": "客户创建成功"
}
```

**说明**：

- `customer_code` 由系统自动生成（规则：公司名拼音首字母大写 + 当日日期 YYYYMMDD）。
- `minimum_ticket_fee_condition` 与 `document_fee_condition` 已变更为数字类型（代表条件数值，例如重量阈值等）。
- `settlement_cycle` 变更为数字选项：1=周结, 2=半月结, 3=月结, 4=现结。

#### 14.2 编辑客户信息（三期扩展）

**接口地址**: `PUT /api/v1/customers/{customer_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。允许对三期新增字段置空或传 `null` 进行清空。

#### 14.3 获取客户详情与列表（三期扩展）

**接口地址**: `GET /api/v1/customers` / `GET /api/v1/customers/{customer_id}`

**响应示例**: 返回的数据体中增加了三期所有的字段（包含 `customer_code`, JSON 配置字典等），字段结构与新增时的请求体保持一致。

---

### 15. 公司信息管理

#### 15.1 获取公司信息及账户列表

**接口地址**: `GET /api/v1/companies`

**请求头**: `Authorization: Bearer <token>`

**请求参数**: 无

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "company_name": "丰德航空物流有限公司",
    "company_location": "深圳市宝安区宝安机场领航二路148号",
    "payment_qr_codes": [
      "/static/uploads/202607/uuid-1.png",
      "/static/uploads/202607/uuid-2.png"
    ],
    "accounts": [
      {
        "id": "123456789",
        "account_name": "丰德航空物流有限公司对公账户",
        "account_number": "1234567890123456",
        "bank_name": "招商银行深圳分行",
        "created_at": "2026-06-01T12:00:00+08:00",
        "updated_at": "2026-06-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 15.2 修改公司基本信息

**接口地址**: `PUT /api/v1/companies/info`

**请求头**: `Authorization: Bearer <token>`

**功能说明**: 更新公司基本信息（支持部分更新），包括公司名称、地址以及上传好的收款码URL列表。

**请求参数**:

```json
{
  "company_name": "丰德航空物流有限公司",
  "company_location": "深圳市宝安区宝安机场领航二路148号",
  "payment_qr_codes": [
    "/static/uploads/202607/uuid-1.png"
  ]
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "公司信息更新成功"
}
```

#### 15.3 新增公司账户

**接口地址**: `POST /api/v1/companies/accounts`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "account_name": "丰德航空物流有限公司对公账户",
  "account_number": "1234567890123456",
  "bank_name": "招商银行深圳分行"
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "123456789",
    "account_name": "丰德航空物流有限公司对公账户",
    "account_number": "1234567890123456",
    "bank_name": "招商银行深圳分行",
    "created_at": "2026-06-01T12:00:00+08:00",
    "updated_at": "2026-06-01T12:00:00+08:00"
  },
  "msg": "公司账户创建成功"
}
```

#### 15.4 编辑公司账户

**接口地址**: `PUT /api/v1/companies/accounts/{account_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。

#### 15.5 获取公司账户详情

**接口地址**: `GET /api/v1/companies/accounts/{account_id}`

**响应示例**: 同新增账户返回的 `data` 结构。

#### 15.6 删除公司账户

**接口地址**: `DELETE /api/v1/companies/accounts/{account_id}`

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "公司账户删除成功"
}
```

---

### 16. 代理管理

#### 16.1 获取代理列表

**接口地址**: `GET /api/v1/agents`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| agent_name | string | 否 | 代理名称（模糊搜索） |
| agent_type | integer | 否 | 代理类型（精确匹配） |
| page | integer | 否 | 页码，默认1 |
| pageSize | integer | 否 | 每页数量，默认10 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "123456789",
        "agent_code": "AG001",
        "agent_type": 1,
        "agent_name": "某某代理公司",
        "contact_person": "李四",
        "contact_phone": "13900139000",
        "document_fee": 50.0,
        "settlement_method": 1,
        "creator_id": "987654321",
        "creator_name": "张三",
        "created_at": "2026-06-01T12:00:00+08:00",
        "updated_at": "2026-06-01T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 16.2 新增代理

**接口地址**: `POST /api/v1/agents`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "agent_code": "AG001",
  "agent_type": 1,
  "agent_name": "某某代理公司",
  "contact_person": "李四",
  "contact_phone": "13900139000",
  "document_fee": 50.0,
  "settlement_method": 1
}
```

**响应示例**: 同列表项结构。

#### 16.3 编辑代理

**接口地址**: `PUT /api/v1/agents/{agent_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。

#### 16.4 获取代理详情

**接口地址**: `GET /api/v1/agents/{agent_id}`

**响应示例**: 同新增代理返回的 `data` 结构。

#### 16.5 删除代理

**接口地址**: `DELETE /api/v1/agents/{agent_id}`

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "代理删除成功"
}
```

---

### 17. 提货单位管理

#### 17.1 获取提货单位列表

**接口地址**: `GET /api/v1/pickup-units`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| pickup_name | string | 否 | 提货单位名称（模糊搜索） |
| page | integer | 否 | 页码，默认1 |
| pageSize | integer | 否 | 每页数量，默认10 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "123456789",
        "pickup_code": "PU001",
        "pickup_name": "某提货单位",
        "contact_person": "张三",
        "contact_phone": "13800138000",
        "settlement_method": 1,
        "creator_id": "987654321",
        "creator_name": "管理员",
        "created_at": "2026-06-03T12:00:00+08:00",
        "updated_at": "2026-06-03T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 17.2 新增提货单位

**接口地址**: `POST /api/v1/pickup-units`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "pickup_code": "PU001",
  "pickup_name": "某提货单位",
  "contact_person": "张三",
  "contact_phone": "13800138000",
  "settlement_method": 1
}
```

**响应示例**: 同列表项结构。

#### 17.3 编辑提货单位

**接口地址**: `PUT /api/v1/pickup-units/{unit_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。

#### 17.4 获取提货单位详情

**接口地址**: `GET /api/v1/pickup-units/{unit_id}`

**响应示例**: 同新增返回的 `data` 结构。

#### 17.5 删除提货单位

**接口地址**: `DELETE /api/v1/pickup-units/{unit_id}`

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "提货单位删除成功"
}
```

---

### 18. 派送单位管理

#### 18.1 获取派送单位列表

**接口地址**: `GET /api/v1/delivery-units`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| delivery_name | string | 否 | 派送单位名称（模糊搜索） |
| page | integer | 否 | 页码，默认1 |
| pageSize | integer | 否 | 每页数量，默认10 |

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "123456789",
        "delivery_code": "DU001",
        "delivery_name": "某派送单位",
        "contact_person": "李四",
        "contact_phone": "13900139000",
        "settlement_method": 1,
        "creator_id": "987654321",
        "creator_name": "管理员",
        "created_at": "2026-06-03T12:00:00+08:00",
        "updated_at": "2026-06-03T12:00:00+08:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 18.2 新增派送单位

**接口地址**: `POST /api/v1/delivery-units`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "delivery_code": "DU001",
  "delivery_name": "某派送单位",
  "contact_person": "李四",
  "contact_phone": "13900139000",
  "settlement_method": 1
}
```

**响应示例**: 同列表项结构。

#### 18.3 编辑派送单位

**接口地址**: `PUT /api/v1/delivery-units/{unit_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。

#### 18.4 获取派送单位详情

**接口地址**: `GET /api/v1/delivery-units/{unit_id}`

**响应示例**: 同新增返回的 `data` 结构。

#### 18.5 删除派送单位

**接口地址**: `DELETE /api/v1/delivery-units/{unit_id}`

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "派送单位删除成功"
}
```

---

### 19. 天气服务

#### 19.1 获取机场指定日期天气

**接口地址**: `GET /api/v1/weather`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| airport_code | string | 是 | 机场三字码，如 TAO |
| date | string | 是 | 目标日期，格式为 YYYY-MM-DD |

> [!NOTE]
> **关于参数映射转换**:
> 后端会自动将机场三字码转换为对应的标准行政区划名称进行天气查询，以确保高德天气 API 能够正常返回数据（高德 API 仅支持标准行政区划名称，无法直接查询如“北京大兴”、“上海虹桥”等非标准区划名称）。
> 转换规则示例如下：
> - `PKX` (北京大兴) / `PEK` (北京首都) $\rightarrow$ `"北京"`
> - `SHA` (上海虹桥) / `PVG` (上海浦东) $\rightarrow$ `"上海"`
> - `CTU` (成都双流) / `TFU` (成都天府) $\rightarrow$ `"成都"`
> - `JNZ` (锦州湾) $\rightarrow$ `"锦州"`
> - `JHG` (西双版纳) $\rightarrow$ `"西双版纳傣族自治州"`
> - `NLH` (宁蒗) $\rightarrow$ `"宁蒗彝族自治县"`
> - `LFH` (怒江) $\rightarrow$ `"怒江傈僳族自治州"`
> - `DIG` (迪庆) $\rightarrow$ `"迪庆藏族自治州"`
> - `GMQ` (果洛) $\rightarrow$ `"果洛藏族自治州"`
> - `WNH` (文山) $\rightarrow$ `"文山壮族苗族自治州"`
> - `NBS` (长白山) $\rightarrow$ `"抚松县"`
> - `HEW` (横店) $\rightarrow$ `"东阳市"`
> - `NLT` (那拉提) $\rightarrow$ `"新源县"`
> - `HTT` (花土沟) $\rightarrow$ `"茫崖市"`
> - `JSJ` (建三江) $\rightarrow$ `"佳木斯"`

**响应示例 (查询成功)**:

```json
{
  "code": 0,
  "data": {
    "date": "2026-06-04",
    "week": "4",
    "dayweather": "雷阵雨",
    "nightweather": "晴",
    "daytemp": "24",
    "nighttemp": "15",
    "daywind": "东北",
    "nightwind": "东北",
    "daypower": "1-3",
    "nightpower": "1-3",
    "daytemp_float": "24.0",
    "nighttemp_float": "15.0"
  },
  "msg": "查询成功"
}
```

**响应示例 (未查到指定日期)**:

```json
{
  "code": 0,
  "data": null,
  "msg": "暂无天气预报"
}
```

---

### 20. 托运书管理

#### 20.1 新增托运书

**接口地址**: `POST /api/v1/consignment-notes`

**请求头**: `Authorization: Bearer <token>`

**请求体 (JSON)**:

**空运示例**:

```json
{
  "transport_type": "0",
  "company_name": "代理公司A",
  "customer_name": "客户A",
  "form_data": {
    "airline": "国航",
    "flight_date": "2026-05-06",
    "flight_number": "CA1234",
    "origin_station": "PEK",
    "destination_station": "SHA",
    "estimated_flight_time": "14:00",
    "quantity": "100",
    "weight": "2000",
    "chargeable_weight": "2050",
    "cabin_type": "普通",
    "cabin_grade": "A",
    "volume": "10",
    "pickup_method": "自提",
    "consignee": "张三",
    "cargo_name": "电子产品",
    "rate": "10.5",
    "air_freight": "21525",
    "other_fees": "100",
    "telegraph_fee": "50",
    "destination_weather": "晴"
  }
}
```

**汽运示例**:

```json
{
  "transport_type": "1",
  "company_name": "代理公司B",
  "customer_name": "客户B",
  "form_data": {
    "transport_date": "2026-05-06",
    "quantity": "50",
    "weight": "1000",
    "volume": "5",
    "vehicle_type": "9.6米厢车",
    "cargo_name": "服装",
    "total_freight": "5000",
    "other_fees": "200",
    "origin_city": "北京",
    "origin_address": "朝阳区某街道",
    "destination_city": "上海",
    "destination_address": "浦东新区某街道",
    "destination_weather": "多云"
  }
}
```

#### 20.2 查询托运书列表

**接口地址**: `GET /api/v1/consignment-notes`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| transport_type | string | 否 | 托运方式筛选：0=空运，1=汽运 |
| date_start | string | 否 | 托运日期范围-开始（格式：YYYY-MM-DD） |
| date_end | string | 否 | 托运日期范围-结束（格式：YYYY-MM-DD） |
| company_name | string | 否 | 代理公司（模糊搜索） |
| customer_name | string | 否 | 客户名称（模糊搜索，主要用于汽运） |
| destination | string | 否 | 目的站（模糊搜索，主要用于空运） |
| flight_number | string | 否 | 航班号（模糊搜索，主要用于空运） |
| airline | string | 否 | 航司（模糊搜索，主要用于空运） |
| audit_status | integer | 否 | 审核状态(0:未审, 1:暂存, 2:已审，支持空运/汽运) |
| flight_date | string | 否 | 航班日期/托运日期（精确匹配，格式：YYYY-MM-DD） |
| origin_station | string | 否 | 始发站（模糊搜索，仅空运） |
| origin_city | string | 否 | 始发城市（模糊搜索，仅汽运） |
| destination_city | string | 否 | 目的城市（模糊搜索，仅汽运） |
| waybill_number | string | 否 | 主单号（模糊搜索，仅空运有效） |
| is_financial | boolean | 否 | 是否是财务审核列表（若为True，则展示财务审核模块数据，支持包括未审核运单在内的所有单据） |
| financial_audit_status | integer | 否 | 财务审核状态(0:未审, 1:暂存, 2:已审) |
| page | integer | 否 | 页码，默认1 |
| pageSize | integer | 否 | 每页数量，默认10 |

#### 20.3 修改托运书

**接口地址**: `PUT /api/v1/consignment-notes/{note_id}`

与新增接口结构完全一致。

#### 20.4 删除托运书

**接口地址**: `DELETE /api/v1/consignment-notes/{note_id}`

#### 20.5 托运书详情

**接口地址**: `GET /api/v1/consignment-notes/{note_id}`

#### 20.6 生成托运书PDF (打印排版)

**接口地址**: `GET /api/v1/consignment-notes/{note_id}/pdf`

**说明**:
该接口后端会结合系统字体与 `xhtml2pdf` / `jinja2` 模板引擎，将 JSON 数据转换为格式精美的 A4 PDF 文档。
前端只需使用 `window.open('/api/v1/consignment-notes/1/pdf')` 或利用 `<a>` 标签下载，即可弹出 PDF 预览及打印窗口。

#### 20.7 暂存/审核同行空运/汽运承运单据

**接口地址**: `POST /api/v1/consignment-notes/audit`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| action | string | 是 | 操作类型: save (暂存), submit (审核提交) |

**请求体 (JSON)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| consignment_note_id | string | 是 | 关联托运书ID |
| waybill_number | string | 否 | 主单号 (仅空运) |
| customer_name | string | 否 | 客户名称 (仅空运) |
| cargo_type | string | 否 | 货物类型 (仅空运) |
| packaging_fee | string | 否 | 包装费 (仅空运) |
| telegram_fee | string | 否 | 电报费 (仅空运) |
| telegram_code | string | 否 | 电报号 (仅空运) |
| cca | string | 否 | CCA (仅空运) |
| door_pickup_fee | string | 否 | 上门提货费 (仅空运) |
| door_pickup_company | string | 否 | 上门提货单位 (仅空运) |
| airport_pickup_fee | string | 否 | 机场提货费 (仅空运) |
| airport_pickup_company | string | 否 | 机场提货单位 (仅空运) |
| delivery_fee | string | 否 | 派送费 (仅空运) |
| delivery_company | string | 否 | 派送单位 (仅空运) |
| carrier_deduction | string | 否 | 承运扣款 (仅空运) |
| other_fees | string | 否 | 其他费用 (仅空运) |
| manual_total_amount | string | 否 | 总金额 (仅空运) |
| remark | string | 否 | 备注 (仅空运) |

**说明**: 该接口用于为同行空运/汽运承运单据（根据 consignment_note_id 关联单据的 transport_type 自动路由）更新暂存 and 审核状态。对于汽运（transport_type=1），请求体除 consignment_note_id 外的财务字段均不生效。暂存后 audit_status 为 1，审核提交后 audit_status 为 2。

#### 20.8 财务单据暂存/确认审核

**接口地址**: `POST /api/v1/consignment-notes/financial/audit`

**请求参数 (Query)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| action | string | 是 | 操作类型: save (暂存), submit (审核提交) |

**请求体 (JSON)**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| consignment_note_id | string | 是 | 关联托运书ID |

**说明**: 该接口用于对单据进行财务暂存/审核。目前支持未通过运单审核的单据直接进行财务审核（自动创建缺省的审核记录）。暂存后 `financial_audit_status` 变为 1，审核提交后 `financial_audit_status` 变为 2。

### 21. 出港跟踪模块

#### 21.1 深航出港列表

**接口地址**: `GET /api/v1/departure-tracking/shenzhen-air`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

- `waybill_number` (String, 可选): 运单号，支持输入多个单号，英文逗号 `,` 分隔。
- `flight_date_start` (String, 可选): 航班日期开始，格式例如 `2026-03-10`。
- `flight_date_end` (String, 可选): 航班日期结束，格式例如 `2026-03-15`。
- `flight_number` (String, 可选): 航班号，深航仅根据 billing_flight 过滤。
- `audit_status` (Integer, 可选): 审核状态 (0:未审, 1:暂存, 2:已审)。
- `origin` (String, 可选): 始发站。
- `destination` (String, 可选): 目的站。
- `customer_name` (String, 可选): 客户名称 (仅查询已暂存/审核的单据信息)。
- `is_suspected_abnormal` (Boolean, 可选): 是否疑似异常 (基于预警发信记录)。
- `page` (Integer, 可选): 页码，默认 1。
- `pageSize` (Integer, 可选): 每页数量，默认 10。

**响应示例**:

```json
{
  "code": 0,
  "msg": "查询成功",
  "data": {
    "total": 100,
    "items": [
      {
        "id": "260819415803760640",
        "prefix": "479",
        "waybill_number": "479-61476365",
        "flight_date": "2026-03-10",
        "flight_number": "ZH9109",
        "billing_time_containers": [
          {
             "id": "260819415803760641",
             "sequence": "1",
             "billing_time": "1615",
             "container": "ZH6416"
          }
        ]
      }
    ]
  }
}
```

**说明**:

- 以 `shenzhen_air_booking_exports`（深航过机装机数据）为主表。
- 每条记录包含一个嵌套的 `billing_time_containers` 列表，存放关联的计飞时间集装器数据（基于主表 ID `booking_export_id` 精准关联）。
- 所有 ID 均作为字符串类型返回，防止精度丢失。

---

### 出港追踪 (Departure Tracking)

#### 获取深航出港追踪列表

**接口地址**: `GET /api/v1/departure-tracking/shenzhen-air`

**接口描述**: 分页获取深航出港追踪运单及配载信息列表。

**响应示例**:

```json
{
  "code": 0,
  "msg": "查询成功",
  "data": {
    "total": 17,
    "items": [
      {
        "id": "322270936650878976",
        "prefix": "479",
        "waybill_number": "61476483",
        "waybill_status": "已制单",
        "creation_time": "2026-06-08 14:42:24",
        "creator": "陈晶晶",
        "agent": "SZXFDH",
        "routing": "SZX-SJW",
        "flight_date": "2026-06-08",
        "billing_flight": "ZH9145",
        "actual_flight": "None",
        "shipper": "深圳市旭德供应链...",
        "consignee": "张庆国...",
        "carrier": "ZH",
        "storage_precautions": "普货",
        "cargo_name": "LED模组",
        "cabin": "C舱",
        "quantity": "2",
        "weight": "50",
        "chargeable_weight": "50",
        "freight_rate": "2.8",
        "air_freight": "140",
        "fuel_surcharge": "13",
        "airport_management_fee": "0",
        "total_amount": "153",
        "price_code": "A1(GEN)",
        "handling_code": "GEN",
        "payment_method": "现金",
        "waybill_type": "电子运单",
        "quantity_difference": "None",
        "weight_difference": "None",
        "container": "None",
        "created_at": "2026-06-08T07:09:38",
        "updated_at": "2026-06-08T07:09:38",
        "billing_time_containers": [
          {
            "id": "322271201659588608",
            "booking_export_id": "322270936650878976",
            "waybill_number_8": "61476461",
            "sequence": "1",
            "flight_number": "CA1384",
            "flight_date": "2026-06-08",
            "billing_time": "1500",
            "origin": "SZX",
            "destination": "北京首都",
            "quantity": "12",
            "weight": "290.0",
            "container": "ZH6905"
          }
        ]
      }
    ]
  }
}
```

**返回字段详细说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `prefix` | String | 前缀 |
| `waybill_number` | String | 单号 |
| `waybill_status` | String | 运单状态 |
| `creation_time` | String | 制单时间 |
| `creator` | String | 制单人 |
| `agent` | String | 代理人 |
| `routing` | String | 航程 |
| `flight_date` | String | 航班日期 |
| `billing_flight` | String | 开单航班 |
| `actual_flight` | String | 走货航班 |
| `shipper` | String | 发货人 |
| `consignee` | String | 收货人 |
| `carrier` | String | 承运人 |
| `storage_precautions` | String | 储运事项 |
| `cargo_name` | String | 品名 |
| `cabin` | String | 舱位 |
| `quantity` | String | 件数 |
| `weight` | String | 重量 |
| `chargeable_weight` | String | 计费重量 |
| `freight_rate` | String | 费率 |
| `air_freight` | String | 航空运费 |
| `fuel_surcharge` | String | 燃油费 |
| `airport_management_fee` | String | 机管费 |
| `total_amount` | String | 总金额 |
| `price_code` | String | 运价代码 |
| `handling_code` | String | 处理代码 |
| `payment_method` | String | 支付方式 |
| `waybill_type` | String | 运单类型 |
| `quantity_difference` | String | 运输件数差额 |
| `weight_difference` | String | 运输重量差额 |
| `container` | String | 集装器 |
| `billing_time_containers` | Array | **关键数组：具体航班配载和打单时间记录（一对多关联）** |

**`billing_time_containers`（计飞时间集装器数据）字段详细说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `booking_export_id` | String | 关联深航主表ID (`shenzhen_air_booking_exports.id`) |
| `waybill_number_8` | String | 运单号(8位) |
| `sequence` | String | 序号 |
| `flight_number` | String | 航班号 |
| `flight_date` | String | 航班日期 |
| `billing_time` | String | 计飞时间 |
| `origin` | String | 起飞站 |
| `destination` | String | 目的站 |
| `quantity` | String | 件数 |
| `weight` | String | 重量 |
| `container` | String | 集装器 |

**前端业务理解提示**:
此接口数据结构表现了航空货运中的 **一票到底** 或 **分批打单装机** 的业务逻辑。外层对象为该运单的总体计费、收发货人信息，内部的 `billing_time_containers` 数组则详细展示了这票货被分配到了哪些具体的航班、航班时间、以及分别装在哪些集装板/箱（`container`）里。前端在展示表格时，通常可以对外层数据使用主行显示，对 `billing_time_containers` 数组使用“展开子表格”的形式呈现。

## 深航订舱批复跟踪模块

### 1. 深航订舱批复跟踪查询列表

- **接口地址**: `/api/v1/shenzhen-air-approvals`
- **请求方法**: `GET`
- **接口说明**: 查询深航订舱批复数据。支持动态根据 `cabin_type` 切换宽体机与非宽体机数据表，支持航班号模糊查询及日期范围过滤。

#### 请求参数 (Query)

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
| --- | --- | --- | --- | --- |
| `flight_date_start` | String | 否 | - | 航班日期开始，如 `2026-03-10` |
| `flight_date_end` | String | 否 | - | 航班日期结束，如 `2026-04-20` |
| `flight_number` | String | 否 | - | 航班号，如 `CA1306`，支持模糊匹配 |
| `cabin_type` | Integer | 否 | `0` | **仓位类型：`0`=散仓(非宽体机数据)，`1`=版/箱/散卡(宽体机数据)** |
| `page` | Integer | 否 | `1` | 页码 |
| `pageSize` | Integer | 否 | `10` | 每页数量 |

#### 响应数据

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `total` | Integer | 总记录数 |
| `items` | Array | 当前页数据列表。具体字段根据 `cabin_type` 而有所差异 |

**当 `cabin_type` = `0` (散仓/非宽体机) 时，`items` 中的对象结构：**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `parent_id` | String | 父级ID |
| `flight_number` | String | 航班号 |
| `flight_date` | String | 航班日期 |
| `aircraft_type` | String | 机型 |
| `departure_time` | String | 起飞时间 |
| `routing` | String | 航程 |
| `agent` | String | 代理人 |
| `f_booking` | String | F订 |
| `f_approval` | String | F批 |
| `c_booking` | String | C订 |
| `c_approval` | String | C批 |
| `other_booking` | String | 其他订 |
| `other_approval` | String | 其他批 |
| `status` | String | 状态 |
| `type` | String | 类型 |
| `control` | String | 控制 |
| `open_status` | String | 开放 |
| `remark` | String | 备注 |
| `created_at` | String | 记录创建时间 |

**当 `cabin_type` = `1` (版/箱/散卡/宽体机) 时，`items` 中的对象结构：**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `parent_id` | String | 父级ID |
| `flight_number` | String | 航班号 |
| `flight_date` | String | 航班日期 |
| `aircraft_type` | String | 机型 |
| `departure_time` | String | 起飞时间 |
| `routing` | String | 航程 |
| `agent` | String | 代理人 |
| `board_booking` | String | 板订 |
| `board_approval` | String | 板批 |
| `backup_board` | String | 备份板 |
| `box_booking` | String | 箱订 |
| `box_approval` | String | 箱批 |
| `backup_box` | String | 备份箱 |
| `status` | String | 状态 |
| `type` | String | 类型 |
| `remark` | String | 备注 |
| `created_at` | String | 记录创建时间 |

## 深航出港列表手动数据接口

**接口路径**: `/api/v1/departure-tracking/shenzhen-air/manual-data`
**请求方式**: `POST`
**说明**: 保存或更新深航出港列表的手动录入数据。通过 `booking_export_id` 关联。

**请求体 JSON**:

- `booking_export_id` (String, 必填): 关联深航主表ID
- `customer_name` (String): 客户名称
- `packaging_fee` (String): 包装费
- `telegram_fee` (String): 电报费
- `telegram_code` (String): 电报号
- `cca` (String): CCA
- `door_pickup_fee` (String): 上门提货费
- `door_pickup_company` (String): 上门提货单位
- `airport_pickup_fee` (String): 机场提货费
- `airport_pickup_company` (String): 机场提货单位
- `delivery_fee` (String): 派送费
- `delivery_company` (String): 派送单位
- `carrier_deduction` (String): 承运扣款
- `other_fees` (String): 其他费用
- `manual_total_amount` (String): 总金额
- `remark` (String): 备注

## 南航订舱批复跟踪模块

### 1. 获取南航订舱批复跟踪列表

**GET** `/api/v1/china-southern-air-approvals`

**查询参数：**

- `flight_date_start` (string, 可选): 航班日期开始，如2026-03-10
- `flight_date_end` (string, 可选): 航班日期结束，如2026-04-20
- `flight_number` (string, 可选): 航班号，如CZ6253
- `waybill_number` (string, 可选): 运单号，支持多个单号用英文逗号隔开，如14743864,14743945
- `page` (integer, 默认1): 页码
- `pageSize` (integer, 默认10): 每页数量

## 承运代理管理

### 1. 新增代理

**POST** `/api/v1/agents`

**请求参数（JSON）：**

- `agent_code` (string, 可选): 代理编码（不传时后端自动生成，如 KCYS001）
- `agent_type` (integer, 必填): 代理类型
- `agent_name` (string, 必填): 代理名称
- `contact_person` (string, 必填): 联系人
- `contact_phone` (string, 必填): 联系电话
- `document_fee` (number, 必填): 制单费
- `settlement_method` (integer, 必填): 结算方式

## 提货单位管理

### 1. 新增提货单位

**POST** `/api/v1/pickup-units`

**请求参数（JSON）：**

- `pickup_code` (string, 可选): 提货单位编码（不传时后端自动生成，如 THS001）
- `pickup_name` (string, 必填): 提货单位名称
- `contact_person` (string, 必填): 联系人
- `contact_phone` (string, 必填): 联系电话
- `settlement_method` (integer, 必填): 结算方式

## 派送单位管理

### 1. 新增派送单位

**POST** `/api/v1/delivery-units`

**请求参数（JSON）：**

- `delivery_code` (string, 可选): 派送单位编码（不传时后端自动生成，如 PSS001）
- `delivery_name` (string, 必填): 派送单位名称
- `contact_person` (string, 必填): 联系人
- `contact_phone` (string, 必填): 联系电话
- `settlement_method` (integer, 必填): 结算方式

## 深航出港列表

### 1. 保存或更新深航出港列表手动录入数据

**POST / PUT** `/api/v1/departure-tracking/shenzhen-air/manual-data`

**请求参数（JSON）：**

- `booking_export_id` (string, 必填): 关联深航主表ID
- `customer_name` (string, 可选): 客户名称
- `cargo_type` (string, 可选): 货物类型
- `packaging_fee` (string, 可选): 包装费
- `telegram_fee` (string, 可选): 电报费
- `telegram_code` (string, 可选): 电报号
- `cca` (string, 可选): CCA
- `door_pickup_fee` (string, 可选): 上门提货费
- `door_pickup_company` (string, 可选): 上门提货单位
- `airport_pickup_fee` (string, 可选): 机场提货费
- `airport_pickup_company` (string, 可选): 机场提货单位
- `delivery_fee` (string, 可选): 派送费
- `delivery_company` (string, 可选): 派送单位
- `carrier_deduction` (string, 可选): 承运扣款
- `other_fees` (string, 可选): 其他费用
- `manual_total_amount` (string, 可选): 总金额
- `remark` (string, 可选): 备注

**响应格式：**

```json
{
  "code": 200,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "1234567890",
        "flight_info": "CZ3649 / 2026-06-10 / SZX - LHW",
        "aircraft_type": "327",
        "waybill_number": "784-14743783",
        "booking_pieces": "27",
        "booking_weight": "238"
      }
    ]
  },
  "msg": "查询成功"
}
```

**返回数据 `items` 中的对象结构：**

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `flight_info` | String | 订舱航班 |
| `aircraft_type` | String | 机型 |
| `aircraft_no` | String | 飞机号 |
| `aircraft_limit` | String | 飞机号限制 |
| `planned_takeoff` | String | 计划起飞时间 |
| `expected_takeoff` | String | 预计起飞时间 |
| `flight_status` | String | 航班状态 |
| `waybill_number` | String | 运单号 |
| `agent_code` | String | 代理人编码 |
| `key_account_code` | String | 大客户编码 |
| `key_account_name` | String | 大客户名称 |
| `sales_channel` | String | 销售渠道 |
| `booking_no` | String | 订舱号 |
| `guarantee_level` | String | 保障等级 |
| `cabin_level` | String | 舱位等级 |
| `product_code` | String | 产品代码 |
| `booking_pieces` | String | 订舱件数 |
| `booking_weight` | String | 订舱重量 |
| `booking_volume` | String | 订舱体积 |
| `goods_name` | String | 品名 |
| `commercial_danger_class` | String | 商用危险品类项 |
| `self_use_material_class` | String | 自用航材类项 |
| `aviation_oil_sample_class` | String | 航油样品类项 |
| `booking_uld` | String | 订舱ULD数量(板/箱) |
| `booking_remark` | String | 订舱备注 |
| `ad_remark` | String | AD备注 |
| `load_guidance` | String | 装载指引 |
| `booking_routing` | String | 订舱航程 |
| `special_cargo_code` | String | 特种货物代码 |
| `billing_qty` | String | 制单数量(件数/重量/体积) |
| `goods_qty` | String | 货物数量(件数/重量/体积) |
| `actual_qty` | String | 实走数量(件数/重量/体积) |
| `actual_flight` | String | 实走航班 |
| `container` | String | 所在容器 |
| `cargo_code` | String | 货物代码 |
| `routing_country` | String | 航程国别 |
| `department` | String | 部门 |
| `booking_time` | String | 订舱时间 |
| `ref_rate` | String | 参考运价 |
| `ref_freight` | String | 参考运费 |
| `currency` | String | 货币 |
| `other_fee` | String | 其他费用 |
| `total_control` | String | 总控控制 |
| `auto_approval` | String | 自动批复 |
| `level_auto_k` | String | 等级自动K舱 |
| `size` | String | 尺寸 |
| `settlement_discount_no` | String | 结算折扣号 |
| `customs_clearance_status` | String | 海关放行状态 |
| `single_window_check` | String | 单一窗口查验 |
| `chargeable_weight` | String | 计费重量 |
| `created_at` | String | 记录创建时间 |
| `updated_at` | String | 记录更新时间 |

## 南航出港列表

### 1. 南航出港列表查询

**GET** `/api/v1/departure-tracking/china-southern-air`

**请求头**: `Authorization: Bearer <token>`

**查询参数：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_number | string | 否 | 运单号，多个用英文逗号隔开 |
| flight_date_start | string | 否 | 航班日期开始，如2026-06-16 |
| flight_date_end | string | 否 | 航班日期结束，如2026-06-20 |
| flight_number | string | 否 | 航班号，如CZ8577 |
| audit_status | integer | 否 | 审核状态(0:未审, 1:暂存, 2:已审) |
| origin | string | 否 | 始发站 |
| destination | string | 否 | 目的站 |
| customer_name | string | 否 | 客户名称 (仅查询已暂存/审核的单据信息) |
| waybill_status | string | 否 | 运单状态 (从 booking_no 匹配，例如 UU, KK) |
| is_suspected_abnormal | boolean | 否 | 是否疑似异常 (基于预警发信记录) |
| page | integer | 否 | 页码，默认1 |
| pageSize | integer | 否 | 每页数量，默认10 |

**响应示例**:

```json
{
  "code": 0,
  "msg": "查询成功",
  "data": {
    "total": 50,
    "items": [
      {
        "id": "325280872800587776",
        "flight_info": "CZ8577 / 2026-06-16 / SZX - WUH",
        "aircraft_type": "327",
        "waybill_number": "784-14743864",
        "booking_no": "63687782",
        "booking_pieces": "16",
        "booking_weight": "134.00",
        "booking_volume": "0.80",
        "product_information": [
          {
            "id": "325280900000000001",
            "approval_data_id": "325280872800587776",
            "segment": "SZX-WUH",
            "pieces": "16",
            "weight": "134.00",
            "volume": "0.80",
            "flight_date_info": "CZ8577/2026-06-16",
            "segment_status": "已完成",
            "is_ready": "YES",
            "booked_flight": "CZ8577",
            "booked_flight_date": "2026-06-16",
            "security_status": "未安检",
            "cargo_status": "正常"
          }
        ],
        "lalamove_information": [
          {
            "id": "325280900000000002",
            "approval_data_id": "325280872800587776",
            "capacity_lalamove": "CZ2014/ZCCR",
            "container_type": "CAR",
            "pieces": "16",
            "weight": "134.00",
            "pre_assigned_flight": "CZ8577"
          }
        ],
        "manual_data": {
          "id": "325280900000000003",
          "booking_no": "63687782",
          "customer_name": "客户A",
          "cargo_type": "普货",
          "packaging_fee": "50",
          "remark": "注意轻拿轻放"
        }
      }
    ]
  }
}
```

**说明**:

- 主表为 `china_southern_air_approval_data`（南航订舱批复数据）。
- 每条记录包含嵌套的 `product_information` 列表（本站货物数据，基于 approval_data_id 关联）。
- 每条记录包含嵌套的 `lalamove_information` 列表（货拉数据，基于 approval_data_id 关联）。
- 每条记录包含可选的 `manual_data` 对象（手动录入数据，基于 booking_no 关联）。
- 所有 ID 均作为字符串类型返回，防止精度丢失。

**主表（`china_southern_air_approval_data`）返回字段说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `flight_info` | String | 订舱航班 |
| `aircraft_type` | String | 机型 |
| `aircraft_no` | String | 飞机号 |
| `aircraft_limit` | String | 飞机号限制 |
| `planned_takeoff` | String | 计划起飞时间 |
| `expected_takeoff` | String | 预计起飞时间 |
| `flight_status` | String | 航班状态 |
| `waybill_number` | String | 运单号 |
| `agent_code` | String | 代理人编码 |
| `key_account_code` | String | 大客户编码 |
| `key_account_name` | String | 大客户名称 |
| `sales_channel` | String | 销售渠道 |
| `booking_no` | String | 订舱号 |
| `guarantee_level` | String | 保障等级 |
| `cabin_level` | String | 舱位等级 |
| `product_code` | String | 产品代码 |
| `booking_pieces` | String | 订舱件数 |
| `booking_weight` | String | 订舱重量 |
| `booking_volume` | String | 订舱体积 |
| `goods_name` | String | 品名 |
| `commercial_danger_class` | String | 商用危险品类项 |
| `self_use_material_class` | String | 自用航材类项 |
| `aviation_oil_sample_class` | String | 航油样品类项 |
| `booking_uld` | String | 订舱ULD数量(板/箱) |
| `booking_remark` | String | 订舱备注 |
| `ad_remark` | String | AD备注 |
| `load_guidance` | String | 装载指引 |
| `booking_routing` | String | 订舱航程 |
| `special_cargo_code` | String | 特种货物代码 |
| `billing_qty` | String | 制单数量(件数/重量/体积) |
| `goods_qty` | String | 货物数量(件数/重量/体积) |
| `actual_qty` | String | 实走数量(件数/重量/体积) |
| `actual_flight` | String | 实走航班 |
| `container` | String | 所在容器 |
| `cargo_code` | String | 货物代码 |
| `routing_country` | String | 航程国别 |
| `department` | String | 部门 |
| `booking_time` | String | 订舱时间 |
| `ref_rate` | String | 参考运价 |
| `ref_freight` | String | 参考运费 |
| `currency` | String | 货币 |
| `other_fee` | String | 其他费用 |
| `total_control` | String | 总控控制 |
| `auto_approval` | String | 自动批复 |
| `level_auto_k` | String | 等级自动K舱 |
| `size` | String | 尺寸 |
| `settlement_discount_no` | String | 结算折扣号 |
| `customs_clearance_status` | String | 海关放行状态 |
| `single_window_check` | String | 单一窗口查验 |
| `chargeable_weight` | String | 计费重量 |
| `created_at` | String | 记录创建时间 |
| `updated_at` | String | 记录更新时间 |
| `product_information` | Array | 本站货物数据（一对多，基于 approval_data_id 关联） |
| `lalamove_information` | Array | 货拉数据（一对多，基于 approval_data_id 关联） |
| `manual_data` | Object/null | 手动录入数据（一对一，基于 approval_data_id 关联，无数据时为 null） |

**`product_information`（本站货物数据）字段说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `approval_data_id` | String | 关联批复数据ID |
| `segment` | String | 航段 |
| `pieces` | String | 件数 |
| `weight` | String | 重量 |
| `volume` | String | 体积 |
| `abnormal_remark` | String | 非正常备注 |
| `storage_remark` | String | 存放备注 |
| `flight_date_info` | String | 所上航班/日期 |
| `segment_status` | String | 航段状态 |
| `is_ready` | String | 是否READY |
| `booked_flight` | String | 预定航班 |
| `booked_flight_date` | String | 预定航班日期 |
| `security_status` | String | 安检状态 |
| `cargo_status` | String | 货物状态 |

**`lalamove_information`（货拉数据）字段说明**:

| 字段名 | 类型 | 说明 |
| --- | --- | --- |
| `id` | String | 主键ID |
| `approval_data_id` | String | 关联批复数据ID |
| `capacity_lalamove` | String | 容量/货拉 |
| `guarantee_pre_pull` | String | 保证/预拉 |
| `container_type` | String | 容器类型 |
| `container_position` | String | 容器位置 |
| `pieces` | String | 件数 |
| `weight` | String | 重量 |
| `pre_assigned_flight` | String | 预配航班 |
| `manifest_number` | String | 所在舱单号 |

---

### 2. 保存或更新南航出港列表手动录入数据

**POST / PUT** `/api/v1/departure-tracking/china-southern-air/manual-data`

**请求头**: `Authorization: Bearer <token>`

**请求参数（JSON）：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| approval_data_id | string | 是 | 关联批复数据ID（china_southern_air_approval_data.id） |
| customer_name | string | 否 | 客户名称 |
| cargo_type | string | 否 | 货物类型 |
| packaging_fee | string | 否 | 包装费 |
| telegram_fee | string | 否 | 电报费 |
| telegram_code | string | 否 | 电报号 |
| cca | string | 否 | CCA |
| door_pickup_fee | string | 否 | 上门提货费 |
| door_pickup_company | string | 否 | 上门提货单位 |
| airport_pickup_fee | string | 否 | 机场提货费 |
| airport_pickup_company | string | 否 | 机场提货单位 |
| delivery_fee | string | 否 | 派送费 |
| delivery_company | string | 否 | 派送单位 |
| carrier_deduction | string | 否 | 承运扣款 |
| other_fees | string | 否 | 其他费用 |
| manual_total_amount | string | 否 | 总金额 |
| remark | string | 否 | 备注 |

**请求示例**:

```json
{
  "approval_data_id": "325302908658782208",
  "customer_name": "客户A",
  "cargo_type": "普货",
  "packaging_fee": "50",
  "telegram_fee": "10",
  "delivery_fee": "200",
  "delivery_company": "某派送公司",
  "manual_total_amount": "260",
  "remark": "注意轻拿轻放"
}
```

**响应示例（新增）**:

```json
{
  "code": 0,
  "data": null,
  "msg": "保存成功"
}
```

**响应示例（更新）**:

```json
{
  "code": 0,
  "data": null,
  "msg": "更新成功"
}
```

**说明**: 通过 `approval_data_id`（即 `china_southern_air_approval_data.id`）判断是否已存在，存在则更新，不存在则新增。手动数据与南航批复主表通过 `approval_data_id` 进行关联，与 `csa_product_information`、`csa_lalamove_information` 保持一致。

---

## 12. 财务管理（统一空运财务审核）

### 12.1 统一查询空运单据财务审核列表

**GET** `/api/v1/financial-audit/air`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query String)：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_number | string | 否 | 运单号，支持输入多个，英文逗号隔开 |
| flight_date_start | string | 否 | 航班日期开始，格式：YYYY-MM-DD |
| flight_date_end | string | 否 | 航班日期结束，格式：YYYY-MM-DD |
| agent_name | string | 否 | 代理名称（仅对同行空运过滤，深航/南航数据不查） |
| destination | string | 否 | 目的站（模糊搜索） |
| flight_number | string | 否 | 航班号 |
| audit_status | integer | 否 | 业务审核状态：0=未审, 1=暂存, 2=已审 |
| financial_audit_status | integer | 否 | 财务审核状态：0=未审, 1=暂存, 2=已审 |
| telegram_status | string | 否 | 电报状态：有电报/无电报/全部 |
| cca_status | string | 否 | CCA状态：有CCA/无CCA/全部 |
| airline_type | string | 否 | 航司类型：shenzhen_air (深航) / china_southern_air (南航) / peer_air (同行空运) |
| page | integer | 否 | 页码，默认 1 |
| pageSize | integer | 否 | 每页条数，默认 10 |

**响应示例**:

```json
{
  "code": 0,
  "msg": "success",
  "data": {
    "total": 1,
    "items": [
      {
        "source_type": "shenzhen_air",
        "source_id": "322270936650878976",
        "audit_status": 2,
        "financial_audit_status": 0,
        "flight_date": "2026-06-08",
        "customer_name": "客户A",
        "agent_name": "SZXFDH",
        "airline": "深航",
        "waybill_number": "479-61476483",
        "origin": "SZX",
        "destination": "SJW",
        "flight_number": "ZH9145",
        "cargo_name": "LED模组",
        "billing_quantity": "2",
        "billing_weight": "50",
        "creator": "陈晶晶",
        "creation_time": "2026-06-08 14:42:24",
        "payable": {
          "agent_name": null,
          "cargo_type": "普货",
          "billing_pieces": "2",
          "billing_weight": "50",
          "gate_pieces": "2",
          "chargeable_weight": "50",
          "freight_rate": "1.5",
          "air_freight": "75.00",
          "fuel_surcharge": "10.00",
          "transit_weight": "50.00",
          "transit_fee": "50.00",
          "cca_cost": "",
          "telegraph_cost": "",
          "packaging_fee": "",
          "other_fees": "",
          "other_fee_remark": "",
          "door_pickup_company": "",
          "door_pickup_fee": "",
          "delivery_company": "",
          "airport_pickup_fee": "",
          "delivery_cost": "0.00",
          "total_cost": "185.00"
        },
        "receivable": {
          "waybill_number": null,
          "flight_date": "2026-06-08",
          "customer_name": "客户A",
          "consignee_phone": "0755-85273907",
          "origin": "SZX",
          "airline": "深航",
          "flight_number": "ZH9145",
          "cargo_name": "LED模组",
          "pieces": "2",
          "chargeable_weight": "50",
          "freight_rate": "1.5",
          "document_fee": "",
          "packaging_fee": "",
          "telegram_fee": "",
          "telegram_code": "",
          "other_fee_remark": "",
          "door_pickup_fee": "0.00",
          "airport_pickup_fee": "",
          "carrier_deduction": "",
          "total_amount": "75.00",
          "payment_method": "",
          "consignee": "高云",
          "destination": "SJW",
          "pickup_method": "",
          "weight": "50",
          "freight": "75.00",
          "cca": "",
          "other_fees": "",
          "delivery_fee": "",
          "collection_payment": "",
          "remark": "",
          "gross_profit": "-110.00"
        },
        "extra_data": {
          "pickup_point": "石家庄",
          "pickup_phone": "0311-88027329",
          "billing_time": "2026-06-08 14:30:00"
        }
      }
    ]
  }
}
```

---

### 12.2 空运财务审核暂存/审核

**POST** `/api/v1/financial-audit/air/audit`

**请求头**: `Authorization: Bearer <token>`

**请求参数 (Query String)：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| action | string | 是 | 操作类型：`save` (暂存), `submit` (已审核/提交) |

**请求参数 (JSON Body)：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `source_type` | string | 是 | 来源类型: `shenzhen_air` / `china_southern_air` / `peer_air` |
| `source_id` | string | 是 | 来源主表ID（手工新增的记录传新增接口返回的 `id`） |
| `payable` | object | 否 | 应付板块所有需要修改覆盖的字段（详见下文 12.3.2 字段说明） |
| `receivable` | object | 否 | 应收板块所有需要修改覆盖的字段（详见下文 12.3.3 字段说明） |

**请求示例**:

```json
{
  "source_type": "shenzhen_air",
  "source_id": "322270936650878976",
  "payable": {
    "telegraph_cost": "50.00",
    "other_fee_remark": "加急包装服务",
    "transit_fee": "65.00"
  },
  "receivable": {
    "consignee_phone": "13800138000",
    "consignee": "广州市物流代理有限公司",
    "door_pickup_fee": "120.00",
    "carrier_deduction": "10.00",
    "pickup_method": "机场自提",
    "collection_payment": "0.00",
    "remark": "收货人要求加急"
  }
}
```

**响应示例**:

```json
{
  "code": 0,
  "msg": "操作成功",
  "data": {
    "source_type": "shenzhen_air",
    "source_id": "322270936650878976",
    "financial_audit_status": 2
  }
}
```

### 12.3 列表返回字段详细说明 (前端联调必读)

#### 12.3.1 外层主数据字段说明

| 字段名 | 类型 | 描述 | 数据源映射 / 逻辑 |
| :--- | :--- | :--- | :--- |
| `source_type` | string | 来源类型 | 可选值：`shenzhen_air` (深航), `china_southern_air` (南航), `peer_air` (同行空运) |
| `source_id` | string | 来源主表主键ID | 防止大数精度丢失，固定为字符串格式 |
| `audit_status` | integer | 业务审核状态 | `0`=未审核，`1`=暂存，`2`=已审核 |
| `financial_audit_status` | integer | 财务审核状态 | `0`=未审核，`1`=暂存，`2`=已审核 |
| `flight_date` | string | 航班/托运日期 | 格式：`YYYY-MM-DD` |
| `customer_name` | string | 客户名称 | 各自手动数据表中的 `customer_name`（通常为前端传入的客户ID） |
| `actual_customer_name` | string | 真实客户名称 | 根据 `customer_name` 作为客户ID查询出的客户档案名称 |
| `agent_name` | string | 代理名称 | 深航为 `agent`，南航为 `agent_code`，同行空运为托运书的 `company_name` |
| `airline` | string | 航空公司 | 深航固定为"深航"，南航固定为"南航"，同行空运取托运书的 `airline` |
| `waybill_number` | string | 运单号 | 主单号，同行空运为手动录入的主单号，深航为 `prefix-waybill_number` |
| `origin` | string | 起飞/始发站 | 始发城市三字码 |
| `destination` | string | 目的站 | 目的站三字码 |
| `flight_number` | string | 开单航班号 | 主单对应的执行/开单航班号 |
| `cargo_name` | string | 货物名称 | 品名/品名描述 |
| `billing_quantity` | string | 开单件数 | 主单上的原始录入件数 |
| `billing_weight` | string | 开单重量 | 主单上的原始录入重量 |
| `creator` | string | 制单人 | 录入人员账号/名字 |
| `creation_time` | string | 制单/录单时间 | 格式：`YYYY-MM-DD HH:MM:SS` |

#### 12.3.2 应付板块 (`payable`) 字段说明

| 字段名 | 类型 | 描述 | 数据源映射 / 算法说明 |
| :--- | :--- | :--- | :--- |
| `agent_name` | string | 代理名称 | 仅同行空运有效，深航/南航返回 `null` |
| `cargo_type` | string | 货物类型 | 手动录入的货物类型 (用于过站费计算) |
| `billing_pieces` | string | 开单件数 | 主单上的原始开单件数 |
| `billing_weight` | string | 开单重量 | 主单上的原始开单重量 |
| `gate_pieces` | string | 过机件数 | 深航/南航为容器关联表求和后的件数，同行空运为 `""` |
| `chargeable_weight` | string | 计费重量 | 主单计费重量 (KG) |
| `freight_rate` | string | 主单费率 | 主单费率价格 |
| `air_freight` | string | 主单运费 | 计开运费 |
| `fuel_surcharge` | string | 燃油费用 | 深航为 `fuel_surcharge`，南航/同行空运为 `""` |
| `transit_weight` | string | 过站重量 | 深航/南航为容器关联表求和后的重量，同行空运为 `""` |
| `transit_fee` | string | 过站费用 | `过站重量 × 客户档案的对应货物类型过站费率`，同行空运为 `""` |
| `cca_cost` | string | CCA成本 | 业务手动数据表中的 `cca` 字段 |
| `telegraph_cost` | string | 电报成本 | **优先取财务人工填写**，没有则使用业务填写的电报费 |
| `packaging_fee` | string | 包装费 | 业务手动数据表中的 `packaging_fee` |
| `other_fees` | string | 其他费用 | 业务手动数据表中的 `other_fees` |
| `other_fee_remark` | string | 其他费用说明 | **财务人工填写**的应付其他费用文字备注 |
| `door_pickup_company`| string | 上门提货单位 | 业务手动数据表中的 `door_pickup_company` |
| `door_pickup_fee` | string | 上门提货费 | 业务手动数据表中的 `door_pickup_fee` |
| `delivery_company` | string | 派送单位 | 业务手动数据表中的 `delivery_company` |
| `airport_pickup_fee` | string | 机场提货费 | 业务手动数据表中的 `airport_pickup_fee` |
| `delivery_cost` | string | 派送成本 | 取自业务手动数据表的 `airport_pickup_fee` 字段 |
| `total_cost` | string | 成本合计 | **应付所有的合计** (主单运费 + 燃油费 + 过站费 + CCA成本 + 包装费 + 其他费 + 上门提货费 + 机场提货费 + 派送成本) |

#### 12.3.3 应收板块 (`receivable`) 字段说明

| 字段名 | 类型 | 描述 | 数据源映射 / 算法说明 |
| :--- | :--- | :--- | :--- |
| `waybill_number` | string | 运单号 | 手工新增单据时传入的运单号，其他类型返回 `null` |
| `flight_date` | string | 航班日期 | 格式：`YYYY-MM-DD` |
| `customer_name` | string | 客户名称 | 同外层客户名称 |
| `consignee_phone` | string | 收货电话 | 深航为 `consignee` 字段提取出来的电话，南航为对应运单表提取电话，同行空运为**财务人工填写** |
| `origin` | string | 始发站 | 同外层始发站 |
| `airline` | string | 航空公司 | 同外层航空公司 |
| `flight_number` | string | 航班号 | 同外层航班号 |
| `cargo_name` | string | 货物名称 | 同外层货物名称 |
| `pieces` | string | 件数 | 计件数量 |
| `chargeable_weight` | string | 计费重量 | 计费重量 |
| `freight_rate` | string | 费率 | 计费费率 |
| `document_fee` | string | 制单费 | 固定返回为空字符串 `""` |
| `packaging_fee` | string | 包装费 | 业务手动数据表中的 `packaging_fee` |
| `telegram_fee` | string | 电报费 | 业务手动数据表中的 `telegram_fee` |
| `telegram_code` | string | 电报号 | 业务手动数据表中的 `telegram_code` |
| `other_fee_remark` | string | 其他费用说明 | **财务人工填写**的应收其他费用文字备注 |
| `door_pickup_fee` | string | 上门提货费 | **优先取财务人工填写**，没有则使用业务填写的 `door_pickup_fee` |
| `airport_pickup_fee` | string | 机场提货费 | 业务手动数据表中的 `airport_pickup_fee` |
| `carrier_deduction` | string | 承运扣款 | **优先取财务人工填写**，没有则使用业务填写的 `carrier_deduction` |
| `total_amount` | string | 总金额 | **应收所有的合计** (制单费 + 电报费 + 机场提货费 + 包装费 + 上门提货费 + 运费 + CCA + 其他费用 + 派送费) |
| `payment_method` | string | 付款方式 | 根据 `customer_name` 作为客户 ID 去查询结算周期，映射为（周结/半月结/月结/现结），若非有效 ID 则返回 `""` |
| `consignee` | string | 收货单位/收货人 | 深航为 `consignee` 字段提取的名字，南航为运单表提取的收货人，同行空运为**财务人工填写**的收货单位 |
| `destination` | string | 目的站 | 同外层目的站 |
| `pickup_method` | string | 提货方式 | **财务人工填写**的提货方式 |
| `weight` | string | 重量 | 对应计费重量 |
| `freight` | string | 运费 | 计算值：`计费重量 × 费率` |
| `cca` | string | CCA | 业务手动数据表的 `cca` |
| `other_fees` | string | 其他费用 | 业务手动数据表的 `other_fees` |
| `delivery_fee` | string | 派送费 | 取自业务手动数据表的 `airport_pickup_fee` |
| `collection_payment`| string | 代收货款 | **财务人工填写**的代收货款 |
| `remark` | string | 备注 | **财务人工填写**的应收备注 |
| `gross_profit` | string | 毛利 | 计算值：`应收总金额 - 应付成本合计` (可以是负数) |

#### 12.3.4 扩展信息 (`extra_data`) 字段说明

对于每条财务审核记录，新增的额外辅助信息：

| 字段名 | 类型 | 描述 | 数据源映射 / 逻辑 |
| :--- | :--- | :--- | :--- |
| `pickup_point` | string | 提货点 | 通过 `destination` (三字码) 查询数据字典得到的中文机场名称 |
| `pickup_phone` | string | 提货电话 | 深航查阅深航Excel提取；南航/同行查阅全国提货电话Excel提取；若无则返回空字符串 `""` |
| `billing_time` | string | 计飞时间 | 深航通过关联的 `ShenzhenAirBillingTimeContainer` 提取 `billing_time` 属性格式化，其它情况为空字符串 `""` |

#### 12.3.5 暂存/审核保存响应字段说明

当调用 `POST /api/v1/financial-audit/air/audit` 保存成功时，返回的 `data` 结构如下：

| 字段名 | 类型 | 描述 | 说明 |
| :--- | :--- | :--- | :--- |
| `source_type` | string | 来源数据源渠道 | 同请求参数，标明本次修改的数据来源（`shenzhen_air` / `china_southern_air` / `peer_air`） |
| `source_id` | string | 来源主表ID | 同请求参数，返回主表主键ID（字符串格式）。手工新增记录返回 `air_financial_audit_data` 表自身 ID |
| `financial_audit_status` | integer | 当前最新的财务审核状态 | `1`=已暂存，`2`=已审核 |

### 12.5 新增空运财务审核单据

**POST** `/api/v1/financial-audit/air`

**请求头**: `Authorization: Bearer <token>`

**功能说明**: 手动创建一条空运财务审核单据，不关联源表数据。系统会根据传入的 `receivable.airline`（如"深航"、"南航"）自动判定 `source_type` (`shenzhen_air`、`china_southern_air` 或 `peer_air`)，从而直接融入现有的列表查询中。新增后的记录初始状态为 `financial_audit_status=0`（未审），可通过 12.2 的暂存/审核接口进行后续操作。

**请求参数 (JSON Body)：**

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `payable` | object | 是 | 应付板块全部数据（字段同 12.3.2 应付板块字段说明） |
| `receivable` | object | 是 | 应收板块全部数据（字段同 12.3.3 应收板块字段说明，其中 `waybill_number` 和 `airline` 为**必填**） |

**请求示例**:

```json
{
  "payable": {
    "agent_name": "某代理公司",
    "cargo_type": "普货",
    "billing_pieces": "5",
    "billing_weight": "120",
    "chargeable_weight": "120",
    "freight_rate": "2.0",
    "air_freight": "240.00",
    "fuel_surcharge": "15.00",
    "total_cost": "255.00"
  },
  "receivable": {
    "waybill_number": "999-12345678",
    "airline": "深航",
    "flight_date": "2026-07-06",
    "customer_name": "客户B",
    "consignee_phone": "13900139000",
    "origin": "SZX",
    "flight_number": "ZH9200",
    "cargo_name": "电子元器件",
    "pieces": "5",
    "chargeable_weight": "120",
    "freight_rate": "2.5",
    "destination": "PEK",
    "weight": "120",
    "freight": "300.00",
    "total_amount": "300.00",
    "gross_profit": "45.00"
  }
}
```

**响应示例**:

```json
{
  "code": 0,
  "msg": "新增成功",
  "data": {
    "id": "335001234567890123",
    "source_type": "shenzhen_air",
    "waybill_number": "999-12345678"
  }
}
```

**响应字段说明**:

| 字段名 | 类型 | 描述 | 说明 |
| :--- | :--- | :--- | :--- |
| `id` | string | 新增记录的主键ID | 后续调用暂存/审核接口时，将此 ID 作为 `source_id` 传入，`source_type` 传入返回值对应类型 |
| `source_type` | string | 来源类型 | 系统根据 airline 推导出的类型（`shenzhen_air` / `china_southern_air` / `peer_air`） |
| `waybill_number` | string | 运单号 | 新增时传入的运单号 |

---

### 17. 公共模块

#### 17.1 通用文件上传

**接口地址**: `POST /api/v1/common/upload`

**请求头**: `Authorization: Bearer <token>`
`Content-Type: multipart/form-data`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| `file` | file | 是 | 上传的文件（如收款码图片） |

**功能说明**: 通用文件上传接口。将文件保存在服务器本地 `static/uploads` 目录下，按月份分目录存储，并返回可直接访问的相对静态资源 URL。

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "url": "/static/uploads/202607/a1b2c3d4.png",
    "filename": "qrcode.png"
  },
  "msg": "文件上传成功"
}
```

---

### 17. 公司信息与账户管理

#### 17.1 获取公司信息及账户列表

**接口地址**: `GET /api/v1/companies`

**请求头**: `Authorization: Bearer <token>`

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "company_name": "丰德航空物流有限公司",
    "company_location": "深圳市宝安区宝安机场领航二路148号",
    "payment_qr_codes": [
      {
        "url": "https://example.com/qr1.png",
        "wechat_name": "陈志超",
        "is_active": true
      }
    ],
    "accounts": [
      {
        "id": "123456",
        "account_name": "某某公司",
        "account_number": "6222020202020202",
        "bank_name": "招商银行",
        "is_active": true,
        "created_at": "2026-06-01 12:00:00",
        "updated_at": "2026-06-01 12:00:00"
      }
    ]
  },
  "msg": "查询成功"
}
```

#### 17.2 修改公司基本信息与收款码

**接口地址**: `PUT /api/v1/companies/info`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| company_name | string | 否 | 公司名称 |
| company_location | string | 否 | 公司地址 |
| payment_qr_codes | array | 否 | 收款码对象数组，**必须且只能激活一个** |

**`payment_qr_codes` 数组元素说明**:

| 字段名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| url | string | 是 | 收款码图片的 URL |
| wechat_name | string | 否 | 微信用户名称（默认空字符串） |
| is_active | boolean | 否 | 是否处于激活状态 (默认 false) |

**请求示例**:

```json
{
  "company_name": "丰德航空物流有限公司",
  "company_location": "深圳市宝安区宝安机场领航二路148号",
  "payment_qr_codes": [
    {
      "url": "/static/uploads/202607/c7af02084f644c79bfd764ae4fc53f40.jpg",
      "wechat_name": "陈志超",
      "is_active": true
    },
    {
      "url": "/static/uploads/202607/another_qr_code.jpg",
      "wechat_name": "财务李四",
      "is_active": false
    }
  ]
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "公司信息更新成功"
}
```

#### 17.3 新增公司账户

**接口地址**: `POST /api/v1/companies/accounts`

**请求参数**:

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| account_name | string | 是 | 账户名 |
| account_number | string | 是 | 账号 |
| bank_name | string | 是 | 开户行 |
| is_active | boolean | 否 | 是否激活（若为 true 则将其他账户自动置为不激活） |

**请求示例**:

```json
{
  "account_name": "丰德航空物流财务部",
  "account_number": "6222020202020202",
  "bank_name": "招商银行深圳分行",
  "is_active": true
}
```

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "id": "123456789",
    "account_name": "丰德航空物流财务部",
    "account_number": "6222020202020202",
    "bank_name": "招商银行深圳分行",
    "is_active": true,
    "created_at": "2026-07-06 14:00:00",
    "updated_at": "2026-07-06 14:00:00"
  },
  "msg": "公司账户创建成功"
}
```

#### 17.4 编辑公司账户

**接口地址**: `PUT /api/v1/companies/accounts/{account_id}`

**请求参数**: 支持部分字段更新，如果不传的字段则不修改。

| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| account_name | string | 否 | 账户名 |
| account_number | string | 否 | 账号 |
| bank_name | string | 否 | 开户行 |
| is_active | boolean | 否 | 是否激活（若传 true 则将其他账户自动置为不激活） |

**请求示例**:

```json
{
  "bank_name": "工商银行深圳分行",
  "is_active": false
}
```

**响应示例**: 同新增账户返回结构。

#### 17.5 删除公司账户

**接口地址**: `DELETE /api/v1/companies/accounts/{account_id}`

**请求无 JSON Body，仅在 URL 路径传递 account_id**

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "公司账户删除成功"
}
```

## 18. "R{t - ^N[&


#### 18.1 航司对账列表查询

**接口地址**: `GET /api/v1/reconciliation/airline/air`

**请求参数**:
| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_numbers | string | 否 | 运单号，多个用逗号隔开 |
| flight_date_start | string | 否 | 航班日期起始 |
| flight_date_end | string | 否 | 航班日期结束 |
| airline | string | 否 | 航司 |
| financial_audit_status | int | 否 | 财务审核状态: 0=未审, 1=暂存, 2=已审 |
| customer_name | string | 否 | 客户名称/ID |
| settlement_status | int | 否 | 结算状态: 0=未结算, 1=已结算 |
| page | int | 否 | 页码, 默认 1 |
| pageSize | int | 否 | 每页数量, 默认 10 |

**响应示例**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "source_type": "shenzhen_air",
        "source_id": "123",
        "waybill_number": "475-12345678",
        "financial_audit_status": 0,
        "financial_auditor_name": "",
        "airline_settlement_status": 0,
        "origin": "SZX",
        "destination": "PEK",
        "flight_date": "2026-07-10",
        "airline": "深圳航空",
        "actual_customer_name": "XX代理公司",
        "flight_number": "ZH9001",
        "actual_flight_number": "ZH9001",
        "cargo_name": "普货",
        "billing_quantity": "100",
        "billing_weight": "1000.0",
        "actual_pieces": "100",
        "actual_weight": "1000.0",
        "chargeable_weight": "1000.0",
        "freight_rate": "5.0",
        "air_freight": "5000.0",
        "fuel_surcharge": "100.0",
        "transit_fee": "0.0",
        "telegraph_cost": "50.0",
        "cca_cost": "0.0",
        "penalty_fee": "0.0",
        "total_cost": "5150.0",
        "airline_settlement_auditor_name": ""
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 10
  },
  "msg": "success"
}
```

#### 18.2 确认结算航司对账

**接口地址**: `POST /api/v1/reconciliation/airline/air/{source_type}/{source_id}/settle`

**路径参数**:
- `source_type`: 数据来源类型 (如 shenzhen_air)
- `source_id`: 来源主表ID

**响应示例**:
```json
{
  "code": 0,
  "data": null,
  "msg": "确认结算成功"
}
```

#### 18.3 取消航司对账结算

**接口地址**: `POST /api/v1/reconciliation/airline/air/{source_type}/{source_id}/cancel-settlement`

**路径参数**:同上

**响应示例**:
```json
{
  "code": 0,
  "data": null,
  "msg": "取消结算成功"
}
```

#### 18.4 批量确认结算航司对账

**接口地址**: `POST /api/v1/reconciliation/airline/air/batch-settle`

**请求参数 (Body)**:
```json
{
  "items": [
    {
      "source_type": "shenzhen_air",
      "source_id": "123"
    },
    {
      "source_type": "china_southern_air",
      "source_id": "456"
    }
  ]
}
```

**响应示例**:
```json
{
  "code": 0,
  "data": null,
  "msg": "成功批量结算 2 条单据"
}
```

#### 18.5 导出航司对账列表 (选中下载 / 批量下载)

**接口地址**: `POST /api/v1/reconciliation/airline/air/export`

**业务逻辑**: 
此接口同时支持“选中下载”和“全部下载”：
- **选中下载**：在 `selected_items` 数组中传入勾选的单据，将仅导出被勾选的这些数据。
- **全部下载**：不传或传空 `selected_items` 数组，将根据传入的 `waybill_numbers`, `flight_date_start` 等搜索条件，查询并导出所有符合条件的数据。

**请求参数 (Body)**:
| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_numbers | string | 否 | 运单号，多个用逗号隔开 |
| flight_date_start | string | 否 | 航班日期起始 |
| flight_date_end | string | 否 | 航班日期结束 |
| airline | string | 否 | 航司 |
| financial_audit_status | int | 否 | 财务审核状态: 0=未审, 1=暂存, 2=已审 |
| customer_name | string | 否 | 客户名称/ID |
| settlement_status | int | 否 | 结算状态: 0=未结算, 1=已结算 |
| selected_items | array | 否 | 选中的单据集合 `[{"source_type":"...", "source_id":"..."}]` |

**响应示例**:
返回 Excel 文件流（`application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`），文件名为 `航司对账列表_YYYYMMDDHHMMSS.xlsx`。

## 19. 提货单位对账模块 (应付)

### 19.1 提货单位对账列表查询

**接口地址**: `GET /api/v1/reconciliation/pickup/air`

**业务逻辑**: 仅返回**业务审核已通过**（`audit_status=2`）并且**已录入上门提货单位**的运单单据数据进行对账。

**Query 参数**:
| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_numbers | string | 否 | 运单号，支持输入多个，英文逗号隔开 |
| flight_date_start | string | 否 | 航班日期起始 (YYYY-MM-DD) |
| flight_date_end | string | 否 | 航班日期结束 (YYYY-MM-DD) |
| actual_flight_number | string | 否 | 实走航班号 |
| financial_audit_status | int | 否 | 财务审核：0=未审, 1=暂存, 2=已审 |
| customer_name | string | 否 | 客户名称 |
| settlement_status | int | 否 | 结算状态：0=未结算, 1=已结算 |
| pickup_company | string | 否 | 上门提货单位 |
| page | int | 否 | 页码，默认1 |
| page | int | 否 | 页码，默认1 |
| pageSize | int | 否 | 每页数量，默认10 |

**响应示例**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "source_type": "shenzhen_air",
        "source_id": "123",
        "waybill_number": "475-12345678",
        "financial_audit_status": 0,
        "pickup_settlement_status": 0,
        "customer_name": "265357797422665728",
        "actual_customer_name": "XX代理公司",
        "pickup_company": "某某提货队",
        "flight_date": "2026-07-10",
        "actual_flight_number": "ZH9001",
        "destination": "PEK",
        "actual_pieces": "100",
        "actual_weight": "1000.0",
        "pickup_fee": "150.0"
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 10
  },
  "msg": "success"
}
```

---

### 19.2 确认结算提货单位对账

**接口地址**: `POST /api/v1/reconciliation/pickup/{source_type}/{source_id}/settle`

**路径参数**:
- `source_type`: 来源类型 (`shenzhen_air`, `china_southern_air`, `peer_air`)
- `source_id`: 来源ID

---

### 19.3 取消结算提货单位对账

**接口地址**: `POST /api/v1/reconciliation/pickup/{source_type}/{source_id}/cancel-settlement`

**路径参数**:
- `source_type`: 来源类型
- `source_id`: 来源ID

---

### 19.4 批量确认结算提货单位对账

**接口地址**: `POST /api/v1/reconciliation/pickup/batch-settle`

**请求参数 (Body)**:
```json
{
  "items": [
    {
      "source_type": "shenzhen_air",
      "source_id": "123"
    }
  ]
}
```

---

### 19.5 导出提货单位对账列表 (选中/批量)

**接口地址**: `POST /api/v1/reconciliation/pickup/export`

**业务逻辑**: 同时支持“选中下载”和“批量下载”。传入 `selected_items` 则只导出选中行，否则根据 Query 搜索条件导出所有数据。

**请求参数 (Body)**:
和列表查询一致，外加可选的 `selected_items` 数组。

## 20. 派送单位对账模块 (应付)

### 20.1 派送单位对账列表查询

**接口地址**: `GET /api/v1/reconciliation/delivery/air`

**业务逻辑**: 仅返回**业务审核已通过**（`audit_status=2`）并且**已录入派送单位及派送费**的数据（或者机场提货费不为空的数据）进行对账。机场提货费对应显示单据的“成本合计 (`total_cost`)”。

**Query 参数**:
| 参数名 | 类型 | 必填 | 描述 |
| :--- | :--- | :--- | :--- |
| waybill_numbers | string | 否 | 运单号，支持输入多个，英文逗号隔开 |
| flight_date_start | string | 否 | 航班日期起始 (YYYY-MM-DD) |
| flight_date_end | string | 否 | 航班日期结束 (YYYY-MM-DD) |
| actual_flight_number | string | 否 | 实走航班号 |
| financial_audit_status | int | 否 | 财务审核：0=未审, 1=暂存, 2=已审 |
| customer_name | string | 否 | 客户名称 |
| settlement_status | int | 否 | 结算状态：0=未结算, 1=已结算 |
| delivery_company | string | 否 | 派送单位 |
| page | int | 否 | 页码，默认1 |
| pageSize | int | 否 | 每页数量，默认10 |

**响应示例**:
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "source_type": "shenzhen_air",
        "source_id": "123",
        "waybill_number": "475-12345678",
        "financial_audit_status": 0,
        "delivery_settlement_status": 0,
        "customer_name": "265357797422665728",
        "actual_customer_name": "XX代理公司",
        "delivery_company": "某某派送队",
        "flight_date": "2026-07-10",
        "actual_flight_number": "ZH9001",
        "destination": "PEK",
        "actual_pieces": "100",
        "actual_weight": "1000.0",
        "airport_pickup_fee": "200.0",
        "delivery_fee": "300.0"
      }
    ],
    "total": 1,
    "page": 1,
    "pageSize": 10
  },
  "msg": "success"
}
```

---

### 20.2 确认结算派送单位对账

**接口地址**: `POST /api/v1/reconciliation/delivery/{source_type}/{source_id}/settle`

**路径参数**:
- `source_type`: 来源类型 (`shenzhen_air`, `china_southern_air`, `peer_air`)
- `source_id`: 来源ID

---

### 20.3 取消结算派送单位对账

**接口地址**: `POST /api/v1/reconciliation/delivery/{source_type}/{source_id}/cancel-settlement`

**路径参数**:
- `source_type`: 来源类型
- `source_id`: 来源ID

---

### 20.4 批量确认结算派送单位对账

**接口地址**: `POST /api/v1/reconciliation/delivery/batch-settle`

**请求参数 (Body)**:
```json
{
  "items": [
    {
      "source_type": "shenzhen_air",
      "source_id": "123"
    }
  ]
}
```


---

### 21. 企微预警通知与出港逻辑规范

#### 21.1 物理主键对齐与运单号兼容规范
- **深航 (Shenzhen Air)**：预警任务表已引入源表物理主键 `booking_export_id`（对应 `shenzhen_air_booking_exports.id`，具备 `unique=True` 索引），全面对齐南航架构。系统在排期同步 (`_sync_tasks`) 与关联执行 (`_process_single_task`) 时优先通过 `booking_export_id` 进行物理精准关联与排重，彻底杜绝主键/唯一索引冲突。同时，企微展示运单号统一补齐 `479-` 前缀（如 `479-61752165`），并降级兼容无前缀格式 (`waybill_candidates`)。
- **南航 (China Southern Air)**：任务统一通过源表物理主键 `approval_data_id` 进行关联与排重。

#### 21.2 订舱 UU 状态拦截机制
- 在通知发送前进行二次实时校验。若订舱号包含 `"UU"` 状态（如 `5892347 (UU)`），任务状态立即设为 `ignored` 并直接中止推送，拦截过期或取消订舱的错报。

#### 21.3 预飞时间与时间及数值显示规范
- **【预飞时间】**：装机预警模板中的【预飞时间】字段优先展示携程 API 返回的 `ready_time`。若来自数据库原始 4 位时间（如 `"2320"` 或 `"23:20"`），系统统一结合航班日期格式化为 `"YYYY-MM-DD HH:MM"` 格式（如 `"2026-07-27 23:20"`）；若无预飞时间则输出 `"/"`。
- **【集装器航班时间】**：集装器/航班号列表后缀挂载的时间（如 `CZ6758 (2320)`）保持原始 4 位无冒号格式（如 `2320`），不做冒号隔开转换。
- **【实飞时间】**：出港状态模板展示携程 API 返回的 `actual_time`（若查无数据则展示 `"暂无"`）。
- **【数据整型输出】**：制单数据、过机/实走数据及差额部分统一强制转为 `int` 字符串输出，严禁在企微通知中出现 `.0` 浮点数。

#### 21.4 深/南航出港状态触发条件
- **前提条件 1**：必须存在有效集装器记录（深航 `shenzhen_air_billing_time_containers` / 南航 `csa_lalamove_information`）。
- **前提条件 2**：通过携程 API 获取集装器航班的 `ready_time`，仅当 `当前时间 (now) >= ready_time` 时，系统才触发出港状态分析与企微推送。

#### 21.5 出港状态通知企微模板与航班号提纯去重规范
- **【航班号提纯清洗】**：实走航班字段（如 `actual_flight`）中可能包含 `/日期(重量)` 等后缀杂质（如 `CZ3557/2026-07-26(27.00)`）。系统统一通过 `_clean_flight_no` 函数提取纯航班号（如 `CZ3557`），杜绝杂质字符传入携程 API 或展示在企微推送中。
- **【实走航班模板标签】**：模板标签统一标准化为 `实走航班：{actual_flight_display}`（不包含 `/航程`）。
- **【实飞时间去重与多航班展示】**：
  - 若开单航班与实走航班相同（如均为 `CZ3557`），去重后 `实飞时间` 仅展示 1 组（如 `CZ3557 / 2026-07-26 14:50`）。
  - 若开单航班与实走航班不同（如开单 `ZH9511`，实走 `ZH9515`），`实飞时间` 按顺序合并展示（如 `ZH9511 / 2026-06-09 09:45 ；ZH9515 / 2026-06-09 10:15`）。
- **【出港状态判定标准】**：
  - **出港正常**：满足件数差额为 0 且重量差额 <= 0 且未发生延误。
  - **出港异常**：件数差额 > 0 或重量差额 > 0 或实走航班实飞时间晚于开单航班计飞时间（延误）。

#### 21.6 订舱批复跟踪与出港跟踪全局数据更新时间（data_update_time）规范
- **【设计原则与重构目标】**：列表接口返回的 `data_update_time` 统一代表**对应 RPA 抓取任务最后一次成功执行/打卡的时间点**。即便航司官网数据未发生变更（ORM 未刷新 `updated_at`），只要 RPA 机器人成功运行抓取，`data_update_time` 也会实时更新；且当前端按航班/单号过滤时，`data_update_time` 保持为系统全局最新抓取打卡时间，不再随过滤记录跳变。
- **【打卡持久化表】**：底层新增 `rpa_task_last_success` 数据库表（主键为 `task_type`，存储 `last_success_at`）。当任何 RPA 任务调用 `rpa_task_service.complete_task(..., success=True)` 时，系统自动完成打卡。
- **【精准映射规范】**：
  1. **深航订舱批复跟踪** (`GET /api/v1/shenzhen-air-approval`)：
     - `cabin_type = 0`（窄体机）取 `SHENZHEN_AIR_APPROVAL_DATA` 打卡时间。
     - `cabin_type = 1`（宽体机）取 `SHENZHEN_AIR_APPROVAL_DATA_WIDE_BODY` 打卡时间。
  2. **南航订舱批复跟踪** (`GET /api/v1/china-southern-air-approval`)：
     - 取 `CHINA_SOUTHERN_AIR_APPROVAL_DATA` 打卡时间。
  3. **深航出港跟踪** (`GET /api/v1/departure-tracking/shenzhen-air`)：
     - 取 `SHENZHEN_AIR_BILLING_TIME_CONTAINER` 打卡时间。
  4. **南航出港跟踪** (`GET /api/v1/departure-tracking/china-southern-air`)：
     - 取 `CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING` 打卡时间。
- **【降级兜底机制】**：系统初次部署或尚无 RPA 成功打卡记录时，自动降级回退至原有记录的最后修改时间（`updated_at`），确保 `data_update_time` 绝不为空。

---

### 22. 南航获取Token RPA流程接入与存储规范

#### 22.1 流程配置与数据库表 (`task_processes` 与 `nanhang_token`)

1. **流程定义 (`task_processes`)**:
   - `task_name`: `CHINA_SOUTHERN_AIR_GET_TOKEN`
   - `chinese_name`: `南航获取token`
   - `process_detail_uuid`: `ccd69aab94b92dec70bd05dfd6f3aa21`
   - `version`: `0.0.2`
   - `process_param`: `{"system_url":"https://cargo.csair.com/tangb2gweb/order-management","queue_token_name":""}`

2. **Token 存储表 (`nanhang_token`)**:
   - `id`: BigInt (主键ID, Snowflake)
   - `robot_id`: BigInt (关联机器人ID)
   - `token`: Text (从队列消费出的 Token / Cookie 字符串)
   - `created_at`: DateTime (创建时间 UTC+8)
   - `updated_at`: DateTime (更新时间 UTC+8)

#### 22.2 自动队列关联与机器人权限绑定规范

- 在 API 接口 `POST /api/v1/robots` 或 `PUT /api/v1/robots` 中，在 `task_permissions` 数组中添加 `"CHINA_SOUTHERN_AIR_GET_TOKEN"` 权限。
- 系统后台 `RobotJobService._sync_robot_queues` 会依据系统配置 `TASK_QUEUE_CONFIGS["CHINA_SOUTHERN_AIR_GET_TOKEN"] = ["token_name"]` **自动为关联机器人分配唯一的队列**（队列名规则为 `china_southern_air_get_token_queue_token_name_<robot_id>`），并在任务执行时自动填充并替换入参中的 `queue_token_name`。

#### 22.3 定时调度机制 (`CsaGetTokenScheduler`)

- 系统启动后台服务 `csa_get_token_scheduler`，默认每隔 1800 秒（30分钟，可通过配置 `RPA_CHINA_SOUTHERN_AIR_GET_TOKEN_INTERVAL_SECONDS` 调整）自动为启用的机器人触发 Token 获取任务。
- 任务执行成功后，Worker 会将 Token 更新写入 `nanhang_token` 表，供其他南航业务模块或接口读取使用。


---

### 23. 费用登记台模块 (Cost Service API)

#### 23.1 接口列表

| 接口分类 | HTTP 方法 | 接口路径 | 摘要说明 |
|---|---|---|---|
| 费用信息登记 | GET | `/api/v1/cost-service/cost-registration` | 获取费用信息登记数据（系统唯一数据） |
| 费用信息登记 | PUT | `/api/v1/cost-service/cost-registration` | 编辑并保存费用信息登记数据 |
| 单据信息 | POST | `/api/v1/cost-service/consignments` | 单据信息-新增 |
| 单据信息 | GET | `/api/v1/cost-service/consignments` | 单据信息-列表查询、筛选与排序 |
| 单据信息 | GET | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-详情 |
| 单据信息 | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-修改 |
| 单据信息 | DELETE | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-删除（单个） |
| 单据信息 | POST/DELETE | `/api/v1/cost-service/consignments/batch-delete` | 单据信息-批量删除 |
| 单据信息 | POST | `/api/v1/cost-service/consignments/export-excel` | 单据信息-选中下载为 Excel（三级分组表头、115 列全量字段） |

#### 23.2 数据结构规范说明

1. **`receivables`（应收款项）字段结构**：
   - 包含：`unit_price`（单价）、`freight_method`（运费计算方式）、`freight`（运费）、`lading_info_fee`（提单费/信息录入费）、`split_offset_telex_fee`（分单费/抵账费/电报费）、`customs_fee`（报关费）、`continuation_sheet_fee`（续页费）、`customs_inspection_fee`（海关查验费）、`magnetic_security_fee`（磁检费/安检费）、`tc_express_fee`（TC操作费/快件中心过站费）、`warehouse_ground_fee`（前置仓/国际货站地面费）、`doc_make_fee`（制单费）、`doc_split_fee`（制单分单费）、`skid_fee`（垫板费）、`pallet_packing_fee`（打板/装箱费）、`probe_fee`（探板费）、`consumables_fee`（耗材费）、`first_leg_fee`（一程费用）、`total`（应收合计）。
   - **核心调整**：`receivables` 请求与响应中**不再包含** `agent` 字段（代理字段维护于 `consignor_info` 货主委托信息中）。

2. **`discount_info`（折让信息）字段结构**：
   - 费用登记保存接口、单据新增接口和单据修改接口的顶层请求体新增 `discount_info`；费用登记查询、单据列表、单据详情以及新增/修改成功响应同步返回该对象。
   - `discount_info.discount_person`：折让人员，字符串，可为空。
   - `discount_info.discount_fee`：折让费，数值，可为空。
   - 请求示例：`"discount_info": {"discount_person": "张三", "discount_fee": 100}`。

3. **`payables.customs`（报关信息）字段调整**：
   - 请求和响应中删除 `rebate`（回扣）字段；报关信息保留 `subtotal`、`date`、`agent`、`customs_fee`、`continuation_sheet_fee`、`inspection_delete_fee`、`other_fee`、`remark`。
   - 数据库迁移 `sql/migration_add_cost_discount_info.sql` 只新增折让字段。历史数据库中的 `pay_customs_rebate` 列不再被业务代码映射或读写，但暂不物理删除，以避免迁移时丢失既有历史数据；全新建表脚本已不再创建该列。

4. **`payables.intl_air`（国际空运信息）字段结构**：
   - `PUT /api/v1/cost-service/cost-registration`、`POST /api/v1/cost-service/consignments`、`PUT /api/v1/cost-service/consignments/{consignment_id}` 的请求体中，不再包含 `date`（托运日期）和 `airline`（航空公司）字段。
   - `GET /api/v1/cost-service/cost-registration`、`GET /api/v1/cost-service/consignments`、`GET /api/v1/cost-service/consignments/{consignment_id}` 以及上述保存、新增、修改接口的成功响应中，也不再返回这两个字段。
   - 当前保留字段：`subtotal`、`outsource_unit`、`origin`、`destination`、`flight_doc_no`、`flight_no`、`flight_date`、`pieces`、`weight`、`volume`、`chargeable_weight`、`rate`、`freight_method`（运费计算方式）、`freight`、`lading_fee`、`split_fee`、`borrow_magnetic_fuel_pickup_fee`、`tc_network_disposal_fee`、`customs_fee`、`continuation_sheet_fee`、`consumables_fee`、`front_warehouse`、`other_fee`、`remark`。
   - `freight_method` 位于 `rate`（单价）和 `freight`（运费）之间，可选字符串，同时出现在新增、修改、详情和列表响应中。

5. **`payables.dom_air`（国内空运信息）字段结构**：
   - `freight_method` 位于 `rate`（单价）和 `freight`（运费）之间，可选字符串，同时出现在新增、修改、详情和列表响应中。
   - 旧客户端继续提交 `payables.intl_air.date` 或 `payables.intl_air.airline` 时，服务端将其作为未声明字段忽略，不会写入数据库，也不会在响应中返回。
   - 存量数据库分别通过 `sql/migration_drop_cost_intl_air_date.sql` 和 `sql/migration_drop_cost_intl_air_airline.sql` 删除对应历史列；全新建表脚本不再创建这两个字段。

6. **Excel 导出规范**：
   - 导出文件使用三行分组表头，数据记录从第 4 行开始，共 115 列；应收款项中新增`运费计算方式`列，位于`单价`和`运费`之间；国际空运和国内空运应付款项也各新增一列`运费计算方式`，均位于`单价`和`运费`之间。
   - 一级分组依次为：`货主托运信息`（第 1-17 列）、`应收款项`（第 18-36 列）、`应付款项`（第 37-109 列）、`折让信息`（第 110-111 列）、`业务信息`（第 112-113 列）、`经营信息`（第 114-115 列）。
   - `应付款项`下设置二级分组：`国际空运信息`（第 37-60 列）、`汽运信息`（第 61-71 列）、`国内空运信息`（第 72-88 列）、`报关信息`（第 89-96 列）、`地面操作信息`（第 97-107 列）；第 108 列为独立的`应付合计`。
   - `国际空运信息`不再导出`托运日期`和`航空公司`列；`折让信息`包含第 110 列`折让人员`和第 111 列`折让费`；`报关信息`中不再导出`回扣`列。
   - 原字段标题中的`应收-`、`国空应付-`、`汽运应付-`、`国空内应付-`、`报关应付-`、`地面应付-`前缀已上移到分组表头，第三行仅展示字段名称；`委托备注`显示为`备注`。
   - Excel 第三行表头按产品最新命名展示：应收款项中的`分单费 电报费/底账费`、`TC费`、`前置仓费`；国际空运应付款项中的`实际重量`、`单价`、`燃油费`、`TC费`；国内空运应付款项中的`实际重量`。应收款项新增`运费计算方式`列，位于`单价`和`运费`之间；该字段同时出现在新增、修改、详情、列表及导出数据中。
   - `freight_method` 在 Excel 导出时按编码转换展示：`1` 显示为`实际重量`，`2` 显示为`计费重量`；接口请求、响应及数据库仍保留原始编码值。
   - “提单”列不会直接输出前端保存的编码，而是按页面展示语义转换：
     - 一主多分：`1-0 → 一主`、`1-1 → 一主（一）分`、`1-2 → 一主（二）分`、`1-3 → 一主（三）分`、`1-4 → 一主（四）分`、`1-5 → 一主（五）分`、`1-6 → 一主（六）分`、`1-7 → 一主（七）分`、`1-8 → 一主（八）分`、`1-9 → 一主（九）分`。
     - 直单：`2-0 → 直单（虚拟分单）`、`2-1 → 直单（虚拟分单*1）`、`2-2 → 直单（虚拟分单*2）`、`2-3 → 直单（虚拟分单*3）`、`2-4 → 直单（虚拟分单*4）`、`2-5 → 直单（虚拟分单*5）`、`2-6 → 直单（虚拟分单*6）`、`2-7 → 直单（虚拟分单*7）`、`2-8 → 直单（虚拟分单*8）`、`2-9 → 直单（虚拟分单*9）`。
     - 兼容当前实际入库格式：新增或修改接口会原样保存前端传入的`bill_of_lading`；除上述数字编码外，导出也识别`一主多分-0`至`一主多分-9`、`直单-0`至`直单-9`，例如`一主多分-6 → 一主（六）分`、`直单-3 → 直单（虚拟分单*3）`。
     - 该转换规则同时用于费用登记台导出 `POST /api/v1/cost-service/consignments/export-excel` 和客服接单台导出 `POST /api/v1/customer-service/consignments/export-excel`，保证两个页面与各自下载文件的“提单”展示一致。
     - 转换只作用于 Excel 导出结果，不修改数据库或其他接口的原始字段；空值导出为空，未知编码及真实提单号原样输出。
   - 应收款项层级不包含“应收-代理”列。响应仍为 `.xlsx` 文件，媒体类型和下载响应头保持不变。

7. **列表航班号筛选规范**：
   - `GET /api/v1/cost-service/consignments` 的 `flight_no` 参数支持模糊匹配，并同时作用于响应中的全部三个航班号字段：`consignor_info.flight_no`、`payables.intl_air.flight_no`、`payables.dom_air.flight_no`。
   - 三个字段之间采用“或（OR）”关系；任一字段包含传入的 `flight_no` 即返回该单据。参数首尾空白会被去除，未传或仅传空白时不增加航班号筛选条件。

8. **列表航司单号筛选规范**：
   - `GET /api/v1/cost-service/consignments` 的 `flight_doc_no` 参数支持模糊匹配，并同时作用于响应中的全部三个航司单号字段：`consignor_info.flight_doc_no`、`payables.intl_air.flight_doc_no`、`payables.dom_air.flight_doc_no`。
   - 为保持既有查询能力，`flight_doc_no`同时兼容匹配`consignor_info.bill_of_lading`（提单）。上述四个数据库字段采用“或（OR）”关系；任一字段包含传入值即返回该单据。
   - 参数首尾空白会被去除，未传或仅传空白时不增加航司单号筛选条件。该筛选只决定单据是否入选，不会改写响应中各字段的原始值。

9. **列表排序规范**：
   - `GET /api/v1/cost-service/consignments` 新增 `sort_by` 和 `sort_order` 查询参数，排序在分页前执行。
   - `sort_by` 可选值：`create_time`（按`consignor_info.create_time`制单时间排序）、`warehouse_entry_date`（按`consignor_info.warehouse_entry_date`进仓日期排序）；默认值为 `warehouse_entry_date`。
   - `sort_order` 可选值：`asc`（正序）、`desc`（倒序）；默认值为 `desc`。
   - 不传排序参数时，继续保持原有的“进仓日期倒序、制单时间倒序、ID倒序”顺序，不影响现有调用方。
   - 当主排序字段值相同时，系统依次使用另一个时间字段和 ID 以相同方向排序，保证分页结果稳定且不会因并列值产生随机顺序。
   - 示例：按制单时间正序查询：`GET /api/v1/cost-service/consignments?sort_by=create_time&sort_order=asc&page=1&pageSize=10`；按进仓日期倒序查询：`GET /api/v1/cost-service/consignments?sort_by=warehouse_entry_date&sort_order=desc&page=1&pageSize=10`。

#### 23.3 客服接单台与费用登记台数据双向实时同步规范

1. **共享雪花 ID (Snowflake ID)**：
   - 客服接单台 (`/api/v1/customer-service/consignments`) 与费用登记台 (`/api/v1/cost-service/consignments`) 中对应的单据记录共享相同的全局主键 `id`。

2. **双向实时同步机制**：
   - **新增 (POST)**：
     - 在客服接单台新增委托记录时，系统会在同一个事务中自动在费用登记台表 (`cost_consignments`) 中创建相同 `id` 的单据记录，并同步写入货主委托信息字段；
     - 在费用登记台新增费用单据时，系统亦会自动在客服接单台表 (`consignment_infos`) 中创建相同 `id` 的委托记录，实现无缝互通。
   - **修改 (PUT)**：
     - 在任意一方修改单据的货主委托信息时，系统自动联动更新另一方中对应 `id` 记录的各委托字段（若对方记录不存在则自动补全创建）。
   - **删除 (DELETE / Batch DELETE)**：
     - 在任意一方执行单条删除或批量删除时，系统自动同步物理删除另一方中相同 `id` 的记录，确保两边列表数据时刻保持高度一致。

#### 23.4 客服接单台委托列表排序规范

- `GET /api/v1/customer-service/consignments` 返回的委托信息包含 `create_time`（制单时间）和 `warehouse_entry_date`（进仓日期），现支持通过 `sort_by` 和 `sort_order` 查询参数在分页前排序。
- `sort_by` 可选值：`create_time`、`warehouse_entry_date`；默认值为 `create_time`。
- `sort_order` 可选值：`asc`（正序）、`desc`（倒序）；默认值为 `desc`。
- 不传排序参数时，继续保持原有的“制单时间倒序、ID倒序”顺序，不影响现有调用方。
- 按进仓日期排序时，若进仓日期相同，则依次按制单时间和 ID 使用相同方向排序；按制单时间排序时，ID 作为并列值排序依据，确保分页结果稳定。
- 非法的排序字段或排序方向不进入数据库查询，由接口参数枚举校验直接拒绝。
- 示例：按制单时间正序查询：`GET /api/v1/customer-service/consignments?sort_by=create_time&sort_order=asc&page=1&pageSize=10`；按进仓日期倒序查询：`GET /api/v1/customer-service/consignments?sort_by=warehouse_entry_date&sort_order=desc&page=1&pageSize=10`。
- 为保证进仓日期排序性能，`consignment_infos.warehouse_entry_date` 已增加数据库索引；已有数据库需执行 `sql/migration_add_customer_consignment_warehouse_entry_date_index.sql`。




