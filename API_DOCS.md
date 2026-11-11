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

### 4. 账号管理（除 4.9 业务员选项外，需要管理员权限）

#### 4.0 提成百分比字段规范

- 字段名：`commission_percentage`，表示账号的提成百分比，JSON 类型为数值或 `null`。
- 取值范围：`0` 至 `100`（包含边界），最多保留两位小数；`0` 是有效值。负数、超过 `100` 或超过两位小数时返回 HTTP 422。
- 新增账号 `POST /api/v1/users`：请求体非必填；省略或显式传 `null` 时保存为空，创建成功响应的 `data.commission_percentage` 返回 `null`；传入有效数值时保存并返回该值（包括 `0`）。
- 账号列表 `GET /api/v1/users`：每条记录在 `data.items[].commission_percentage` 返回该值。
- 账号详情 `GET /api/v1/users/{user_id}`：在 `data.commission_percentage` 返回该值。
- 修改用户 `PUT /api/v1/users/{user_id}`：请求体可选；传入数值（包括 `0`）时更新，省略或显式传 `null` 时保留原值；成功响应在 `data.commission_percentage` 返回更新后的值。
- 数据库字段允许为空；未填写提成百分比的新账号，以及尚未维护该字段的历史账号，在列表和详情响应中均返回 `null`，不自动赋值为 `0`。
- 本字段不影响账号权限、启停状态和 JWT，不会因为提成百分比变更而使登录凭证失效。
- 存量数据库上线前需执行 `sql/migration_add_user_commission_percentage.sql`；通过当前 ORM 新建的数据库会直接包含该字段。

#### 4.1 新增账号

**接口地址**: `POST /api/v1/users`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "phone": "13800138001",
  "password": "password123",
  "name": "张三",
  "commission_percentage": 12.5,
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
    "commission_percentage": 12.5,
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
- `commission_percentage` 非必填；省略或传 `null` 时保存为空，创建、列表和详情响应返回 `null`；传入数值时范围为 `0-100`，最多两位小数，`0` 是有效值
- 未填写时，前端应省略 `commission_percentage` 或传 `null`；空字符串 `""` 不是有效数值，会返回 HTTP 422
- 支持多个部门（`department_ids` 为数组）
- 权限使用固定权限代码（如 `organizational_management`, `expense_registration`）
- 权限列表中任意一项不在后端权限白名单时，接口返回 `400` 和“权限列表包含无效的权限”，账号不会创建

#### 4.2 查看已创建账号

**接口地址**: `GET /api/v1/users`

**请求头**: `Authorization: Bearer <token>`

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 用户名称关键字，按 `users.name` 包含匹配；去除首尾空白，不传、空字符串或纯空白时不筛选 |

**请求示例**: `GET /api/v1/users?name=张`，匹配“张三”“小张”等姓名（实际请求需对中文和特殊字符进行 URL 编码）。

**搜索与返回规则**:

- 筛选在数据库查询中执行，覆盖全部账号；仅按用户姓名搜索，不匹配手机号或部门名称。
- `%`、`_` 等 SQL 通配符按普通字符匹配，无需调用方手动添加通配符。
- `data.total` 为筛选后的匹配账号数量，`data.items` 返回全部匹配账号，按创建时间倒序排列；无匹配时返回 `{"total": 0, "items": []}`。
- 当前接口无服务端分页参数；前端如需分页，应对返回的筛选结果分页。未传 `name` 时保持原有全量返回行为。
- 管理员权限要求及账号字段（包括 `commission_percentage`、部门、权限、状态和时间）保持不变。

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
        "commission_percentage": null,
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
        "commission_percentage": 12.5,
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
    "commission_percentage": 12.5,
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

**说明**: 返回指定账号的详细信息，包括提成百分比、所属部门和权限信息；未维护提成百分比的历史账号返回 `null`

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
  "commission_percentage": 15.75,
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
    "commission_percentage": 15.75,
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
- `commission_percentage` 传入数值（包括 `0`）时更新；省略或传 `null` 时保留原值
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

#### 4.9 获取费用登记台业务员选项

**接口地址**: `GET /api/v1/users/salespersons`

**请求头**: `Authorization: Bearer <access_token>`

**权限**: 需要 `expense_registration`（费用登记台）或 `admin`（管理员）权限。兼容历史保存的 `cost_service` 和中文权限名称；仅有客服接单台、组织管理或系统管理权限不可访问。

**用途**: 费用登记台初始化、搜索和展开业务员下拉框时使用。本接口只提供选择业务员所需数据，不授予账号管理权限。

**查询参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 否 | 按账号姓名包含匹配，去除首尾空白；省略、空字符串或纯空白时不筛选；`%`、`_`、`/` 等字符按字面值匹配 |

**请求示例**: `GET /api/v1/users/salespersons?name=张`（实际请求需 URL 编码）。

**响应示例**:

```json
{
  "code": 0,
  "data": {
    "total": 2,
    "items": [
      {
        "id": "260819415803760645",
        "name": "小张",
        "commission_percentage": null
      },
      {
        "id": "260819415803760644",
        "name": "张三",
        "commission_percentage": 12.5
      }
    ]
  },
  "msg": "查询成功"
}
```

**返回规则**:

- `data.items[]` 每项仅含 `id`（字符串）、`name`（字符串）、`commission_percentage`（数值或 `null`）；不返回手机号、密码哈希、部门、权限、启停状态、Token 版本及时间字段。
- `commission_percentage` 表示账号当前提成百分比，范围 `0-100`，最多两位小数；`0` 为有效数值，未维护时保留 `null`，不转换为 `0`。
- 与原账号列表保持相同的候选范围：返回全部匹配账号（包括已停用账号），不按部门、权限或是否维护提成比例进行额外筛选；按账号创建时间倒序，不分页，`total` 为匹配总数。`page`、`pageNo`、`pageSize` 不是本接口的分页参数，前端无需传入。
- 无匹配时仍返回 HTTP 200：`{"code":0,"data":{"total":0,"items":[]},"msg":"查询成功"}`。
- 接口只读，不修改账号、登录凭证、费用记录或提成金额，无需新增数据库字段或迁移。

**错误响应**:

- HTTP 403：已登录但缺少费用登记台及管理员权限，统一响应为：

  ```json
  {
    "code": 403,
    "data": null,
    "msg": "需要「expense_registration」权限或管理员权限"
  }
  ```

- HTTP 401：Token 无效、过期、版本失效，或当前登录账号已停用；沿用现有认证规则。
- 未携带 Bearer 凭证时由现有 `HTTPBearer` 拦截，当前返回 HTTP 403。

**前端接入说明**:

1. 仅将费用登记台内加载、搜索业务员选项的调用，从 `GET /api/v1/users` 改为 `GET /api/v1/users/salespersons`（包含页面初始化和下拉框搜索、展开使用的调用）。如果复用账号列表 API 函数，应新增业务员选项 API 函数，不要修改共享账号列表函数的地址。
2. 保留 `name` 搜索参数，继续读取 `data.items`；使用 `name` 作为选项的展示文本和提交值，`id` 为账号标识。继续将选中的 `name` 写入 `sales_commission.salesperson`，不要改传账号 ID。
3. `commission_percentage` 可继续用于前端提成金额计算，注意区分 `0` 与 `null`。后端保存费用时仍按现有规则读取账号提成比例并生成快照，不修改提成金额计算逻辑。
4. 账号管理页面继续使用原 `GET /api/v1/users` 及其他账号管理接口，其管理员限制、输入输出和原行为保持不变。有费用登记台权限的非管理员可以读取业务员选项，仍不能读取完整账号列表或账号详情。
5. 上线需配合前端替换费用登记台调用；只上线后端不会改变旧前端对 `/api/v1/users` 的请求。权限刚调整的账号仍须按原规则重新登录。

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
- **费用登记台权限（expense_registration）**: 可访问业务员选项 `GET /api/v1/users/salespersons`（详见 4.9），不因此获得完整账号列表、详情或账号管理权限；历史 `cost_service` 权限兼容。
- **其他非管理员**: 按各接口标注的权限访问；不具备费用登记台权限时，不能读取业务员选项。
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
| 单据信息 | POST | `/api/v1/cost-service/consignments/draft` | 单据信息-暂存新增 |
| 单据信息 | GET | `/api/v1/cost-service/consignments` | 单据信息-列表查询、筛选与排序 |
| 单据信息 | GET | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-详情 |
| 单据信息 | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-修改 |
| 单据信息 | PUT | `/api/v1/cost-service/consignments/{consignment_id}/draft` | 单据信息-暂存修改 |
| 单据信息 | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | 单据信息-作废（保留数据，详见 23.8） |
| 操作记录 | GET | `/api/v1/cost-service/consignments/{consignment_id}/operation-logs` | 单据跨台完整操作记录（详见 23.7） |
| 单据信息 | DELETE | `/api/v1/cost-service/consignments/{consignment_id}` | 单据信息-删除（单个） |
| 单据信息 | POST/DELETE | `/api/v1/cost-service/consignments/batch-delete` | 单据信息-批量删除 |
| 单据信息 | POST | `/api/v1/cost-service/consignments/export-excel` | 单据信息-选中下载为 Excel（118列、单行表头，第1列序号、第2列状态；详见23.11.9） |

#### 23.2 数据结构规范说明

2026-10-30：两台扩展录入、新增20字段及完整请求/响应字典见23.11；旧字段键名保留。

1. **`receivables`（应收款项）字段结构**：
   - 包含：`unit_price`（单价）、`freight_method`（运费计算方式）、`freight`（运费）、`lading_info_fee`（提单费/信息录入费）、`split_offset_telex_fee`（分单费/抵账费/电报费）、`customs_fee`（报关费）、`continuation_sheet_fee`（续页费）、`customs_inspection_fee`（海关查验费）、`magnetic_security_fee`（磁检费/安检费）、`tc_express_fee`（TC操作费/快件中心过站费）、`warehouse_ground_fee`（前置仓/国际货站地面费）、`doc_make_fee`（制单费）、`doc_split_fee`（制单分单费）、`skid_fee`（垫板费）、`pallet_packing_fee`（打板/装箱费）、`probe_fee`（探板费）、`consumables_fee`（耗材费）、`first_leg_fee`（一程费用）、`total`（应收合计）。
   - **核心调整**：`receivables` 请求与响应中新增 `receivable_fuel_fee`（燃油费）；同时**不再包含** `agent` 字段（代理字段维护于 `consignor_info` 货主委托信息中）。

2. **`discount_info`（折让信息）字段结构**：
   - 费用登记保存接口，以及费用单据新增、修改和对应暂存接口的顶层请求体均包含 `discount_info`；费用登记查询、单据列表、单据详情以及新增、修改、暂存、作废成功响应同步返回该对象。
   - `discount_info.discount_person`：折让人员，字符串，可为空。
   - `discount_info.discount_rate`：费率，数值，可为空；`0` 是有效值，不会按空值处理。
   - `discount_info.discount_fee`：折让费，数值，可为空。
   - 新增记录时未传费率则保存为数据库 `NULL`，响应返回 `null`。修改已有记录时，省略 `discount_rate` 或显式传 `null` 均保留原值；传入数值（包括 `0`）则覆盖原值。
   - 请求对象示例：

     ```json
     {
       "discount_info": {
         "discount_person": "张三",
         "discount_rate": 7.25,
         "discount_fee": 100
       }
     }
     ```

   - 单条数据响应片段（费用登记查询、保存，单据新增、暂存新增、详情、修改、暂存修改和作废接口）：

     ```json
     {
       "code": 0,
       "data": {
         "discount_info": {
           "discount_person": "张三",
           "discount_rate": 7.25,
           "discount_fee": 100.0
         }
       },
       "msg": "查询成功"
     }
     ```

   - 列表响应中的字段位于 `data.items[].discount_info.discount_rate`：

     ```json
     {
       "code": 0,
       "data": {
         "total": 1,
         "items": [
           {
             "id": "358000000000000001",
             "discount_info": {
               "discount_person": "张三",
               "discount_rate": 7.25,
               "discount_fee": 100.0
             }
           }
         ],
         "page": 1,
         "pageSize": 10
       },
       "msg": "查询成功"
     }
     ```

   - 受影响接口明细：

     | HTTP 方法 | 接口路径 | 请求变化 | 响应变化 |
     |---|---|---|---|
     | GET | `/api/v1/cost-service/cost-registration` | 无 | `data.discount_info.discount_rate` |
     | PUT | `/api/v1/cost-service/cost-registration` | `discount_info.discount_rate` | `data.discount_info.discount_rate` |
     | POST | `/api/v1/cost-service/consignments` | `discount_info.discount_rate` | `data.discount_info.discount_rate` |
     | POST | `/api/v1/cost-service/consignments/draft` | `discount_info.discount_rate` | `data.discount_info.discount_rate` |
     | GET | `/api/v1/cost-service/consignments` | 无 | `data.items[].discount_info.discount_rate` |
     | GET | `/api/v1/cost-service/consignments/{consignment_id}` | 无 | `data.discount_info.discount_rate` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | `discount_info.discount_rate` | `data.discount_info.discount_rate` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/draft` | `discount_info.discount_rate` | `data.discount_info.discount_rate` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | 无；作废不修改费率 | `data.discount_info.discount_rate` |
     | POST | `/api/v1/cost-service/consignments/export-excel` | 无 | Excel 折让信息新增“费率”列 |

   - 存量数据库需执行 `sql/migration_add_cost_discount_rate.sql`，同时为 `cost_registrations` 和 `cost_consignments` 增加可空的 `discount_rate` 字段；全新建表脚本已包含该字段。

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

6. **Excel 导出规范（2026-11-02更新）**：
   - 两台均改为单行表头，第1列“序号”、第2列“状态”，数据从第2行开始，无合并单元格和空白占位列。客服94列（A至CP），费用118列（A至DN）。完整入参、响应及逐列字段来源以23.11.9为准。
   - 状态读取本台单据status，0/1/2显示未提交/已提交/作废。客服导出按制单时间倒序；序号按导出结果从1连续生成。
   - 应收金额表头使用客户原文，如“应收提单费/信息录入费”“应收分单费 电报费/底账费”；基础“航班单号”改称“主单号”，金额不重算，0保留为数值，null留空。
   - 费用保留应收运费费率、运费计算方式和运费；五个应付分组末尾均为“应付小计”。业务员和提成金额位于第110-111列；末尾为应收合计、应付合计、利润、利润率%。
   - 客服不导出应收运费费率/应收运费计算方式/运费、各分组单价与小计、各项合计、折让及销售提成；汽运运费计算方式单独导出。两台都不导出内部单据ID、制单时间等新表头未列出的字段，CRUD保存/查询字段不变。
   - 费用应收 `freight_method` 仅在第18列导出时转换：1=实际重量、2=计费重量；国际和国内空运同名字段不再导出，燃油取重方式也不导出。
   - “提单”列不会直接输出前端保存的编码，而是按页面展示语义转换：
     - 一主多分：`1-0 → 一主`、`1-1 → 一主（一）分`、`1-2 → 一主（二）分`、`1-3 → 一主（三）分`、`1-4 → 一主（四）分`、`1-5 → 一主（五）分`、`1-6 → 一主（六）分`、`1-7 → 一主（七）分`、`1-8 → 一主（八）分`、`1-9 → 一主（九）分`。
     - 直单：`2-0 → 直单`；`2-1`不再作为提单类型编码；`2-2`至`2-9`继续分别映射为`直单（虚拟分单*2）`至`直单（虚拟分单*9）`。
     - 兼容当前实际入库格式：新增或修改接口会原样保存前端传入的`bill_of_lading`；除上述数字编码外，导出也识别`一主多分-0`至`一主多分-9`和`直单-0`、`直单-2`至`直单-9`（例如`一主多分-6 → 一主（六）分`、`直单-0 → 直单`、`直单-3 → 直单（虚拟分单*3）`）。`直单-1`不再作为提单类型编码，导出时按未知值原样保留。
     - 该转换规则同时用于费用登记台导出 `POST /api/v1/cost-service/consignments/export-excel` 和客服接单台导出 `POST /api/v1/customer-service/consignments/export-excel`，保证两个页面与各自下载文件的“提单”展示一致。
     - 转换只作用于 Excel 导出结果，不修改数据库或其他接口的原始字段；空值导出为空，未知编码及真实提单号原样输出。
   - 费用登记台导出 `POST /api/v1/cost-service/consignments/export-excel` 的数据行按货主委托信息中的`flight_date`（航班日期）升序排列，即从较早日期到较晚日期；未填写航班日期的记录排在最后，同一航班日期按单据 ID 升序排列。该排序只作用于 Excel 导出，不改变费用登记台列表及客服接单台导出顺序。
   - 应收款项层级不包含“应收-代理”列。响应仍为 `.xlsx` 文件，媒体类型和下载响应头保持不变。

7. **列表日期筛选规范**：
   - `GET /api/v1/cost-service/consignments` 支持以下四个可选日期查询参数，格式均为 `YYYY-MM-DD`：

     | 参数名 | 必填 | 数据字段 | 说明 |
     |---|---|---|---|
     | `start_warehouse_date` | 否 | `consignor_info.warehouse_entry_date` | 进仓日期下限，包含当天 |
     | `end_warehouse_date` | 否 | `consignor_info.warehouse_entry_date` | 进仓日期上限，包含当天 |
     | `start_flight_date` | 否 | `consignor_info.flight_date` | 委托信息航班日期下限，包含当天 |
     | `end_flight_date` | 否 | `consignor_info.flight_date` | 委托信息航班日期上限，包含当天 |

   - 进仓日期和航班日期是两组相互独立的可选条件。前端可以只传 `start_flight_date`、只传 `end_flight_date`，或同时传航班日期上下限，而无需传任何进仓日期参数。
   - 同一组只传开始日期时查询该日期及之后的数据，只传结束日期时查询该日期及之前的数据；开始和结束日期相同时可精确查询某一天。
   - 两组日期同时传入时采用 AND 关系，记录必须同时满足进仓日期范围和委托信息航班日期范围。均不传时不进行日期筛选。
   - 航班日期条件仅匹配 `consignor_info.flight_date`（委托信息区），为空时不满足任何有效日期边界，不回退国际/国内空运日期。完整约定及示例见23.20；23.17为已被替代的历史规则。
   - 范围查询使用既有 `cost_consignments.flight_date` 列及其索引。本次无新增迁移；旧库若缺少该索引，可按23.20说明核查补齐。既有导出排序保持原规则。
   - 示例：只查询委托信息航班日期为 2026-09-20 的记录：`GET /api/v1/cost-service/consignments?start_flight_date=2026-09-20&end_flight_date=2026-09-20&page=1&pageSize=10`。

8. **列表航班号筛选规范**：
   - `GET /api/v1/cost-service/consignments` 的 `flight_no` 参数支持模糊匹配，并同时作用于响应中的全部三个航班号字段：`consignor_info.flight_no`、`payables.intl_air.flight_no`、`payables.dom_air.flight_no`。
   - 三个字段之间采用“或（OR）”关系；任一字段包含传入的 `flight_no` 即返回该单据。参数首尾空白会被去除，未传或仅传空白时不增加航班号筛选条件。

9. **列表主单号筛选规范（2026-11-02更新）**：
   - `GET /api/v1/cost-service/consignments` 保留查询参数 `flight_doc_no`，前端搜索框显示名称改为“主单号”；仅模糊匹配国际空运应付款项 `payables.intl_air.flight_doc_no`，数据库列为 `cost_consignments.pay_intl_air_flight_doc_no`。
   - 不再通过货主委托信息 `consignor_info.flight_doc_no`、提单 `consignor_info.bill_of_lading` 或国内空运 `payables.dom_air.flight_doc_no` 匹配，汽运主单号也不在此筛选范围内。国际空运主单号为空、仅其他分组有相同号码时不入选。
   - 参数首尾空白会被去除，未传、空字符串或仅传空白时不增加主单号筛选条件；与其他查询条件按AND组合。返回对象、分页、排序及其他筛选逻辑延续。参数及返回示例详见23.16。

10. **列表排序规范**：
   - `GET /api/v1/cost-service/consignments` 新增 `sort_by` 和 `sort_order` 查询参数，排序在分页前执行。
   - `sort_by` 可选值：`create_time`（按`consignor_info.create_time`制单时间排序）、`warehouse_entry_date`（按`consignor_info.warehouse_entry_date`进仓日期排序）；默认值为 `warehouse_entry_date`。
   - `sort_order` 可选值：`asc`（正序）、`desc`（倒序）；默认值为 `desc`。
   - 不传排序参数时，继续保持原有的“进仓日期倒序、制单时间倒序、ID倒序”顺序，不影响现有调用方。
   - 当主排序字段值相同时，系统依次使用另一个时间字段和 ID 以相同方向排序，保证分页结果稳定且不会因并列值产生随机顺序。
   - 示例：按制单时间正序查询：`GET /api/v1/cost-service/consignments?sort_by=create_time&sort_order=asc&page=1&pageSize=10`；按进仓日期倒序查询：`GET /api/v1/cost-service/consignments?sort_by=warehouse_entry_date&sort_order=desc&page=1&pageSize=10`。

11. **`payables.ground`（地面操作信息）字段调整**：
   - 原“运费”展示名称改为“前置仓”，继续使用 `payables.ground.freight` 入参和返回字段，数据库列仍为 `pay_ground_freight`；不新增替代字段、不迁移或清空原金额。前端应修改该字段的显示文字，并在其后依次新增“TC费”和“提货费”。
   - 新增字段定义（登记模板和费用单据一致）：

     | 字段路径 | 类型 | 必填 | 数据库列 | 说明 |
     |---|---|---|---|---|
     | `payables.ground.tc_fee` | number / null | 否 | `pay_ground_tc_fee` | TC费，数据库金额精度为 `decimal(10,2)` |
     | `payables.ground.pickup_fee` | number / null | 否 | `pay_ground_pickup_fee` | 提货费，数据库金额精度为 `decimal(10,2)` |

   - 新建时未传或传 `null`，数据库保存为 `NULL`，响应返回 `null`；更新时省略字段或显式传 `null` 均保留原值，传入数值（包括 `0`）则覆盖原值。省略整个 `payables` 或 `ground` 对象也不改变原有金额。
   - `subtotal`（地面应付小计）、`pay_total`（应付合计）、利润等仍按现有规则由客户端提交；后端不因新增这两个字段自动重算或覆盖合计。
   - 地面操作完整字段为：`subtotal`、`date`、`outsource_unit`、`chargeable_weight`、`rate`、`freight`（前置仓）、`tc_fee`、`pickup_fee`、`lading_express_fee`、`security_customs_fee`、`pallet_exit_fee`、`other_fee`、`remark`。
   - 保存、新增、暂存和修改的请求片段：

     ```json
     {
       "payables": {
         "ground": {
           "freight": 120,
           "tc_fee": 35.5,
           "pickup_fee": 20
         }
       }
     }
     ```

   - 查询或写入成功后的单条响应片段：

     ```json
     {
       "code": 0,
       "data": {
         "payables": {
           "ground": {
             "freight": 120.0,
             "tc_fee": 35.5,
             "pickup_fee": 20.0
           }
         }
       },
       "msg": "查询成功"
     }
     ```

   - 列表中的对应字段位于 `data.items[].payables.ground.tc_fee` 和 `data.items[].payables.ground.pickup_fee`；无新金额的历史记录也返回这两个键，值为 `null`。费用登记模板尚不存在时仍返回 `data: null`。
   - 受影响接口明细（以下“新字段”指 `payables.ground.tc_fee` 和 `payables.ground.pickup_fee`）：

     | HTTP 方法 | 接口路径 | 请求变化 | 响应变化 |
     |---|---|---|---|
     | GET | `/api/v1/cost-service/cost-registration` | 无 | `data` 中新增两个字段 |
     | PUT | `/api/v1/cost-service/cost-registration` | 可传新字段 | `data` 中新增两个字段 |
     | POST | `/api/v1/cost-service/consignments` | 可传新字段 | `data` 中新增两个字段 |
     | POST | `/api/v1/cost-service/consignments/draft` | 可传新字段 | `data` 中新增两个字段 |
     | GET | `/api/v1/cost-service/consignments` | 查询参数不变 | `data.items[]` 中新增两个字段 |
     | GET | `/api/v1/cost-service/consignments/{consignment_id}` | 无 | `data` 中新增两个字段 |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | 可传新字段 | `data` 中新增两个字段 |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/draft` | 可传新字段 | `data` 中新增两个字段 |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | 无；作废不改金额 | `data` 中新增两个字段 |
     | POST | `/api/v1/cost-service/consignments/export-excel` | `ids` 入参不变 | 单行表头118列，地面前置仓费/TC费/提货费及完整顺序详见23.11.9 |

   - 上线代码前，存量数据库需执行 `sql/migration_add_cost_ground_fees.sql`，为 `cost_registrations` 和 `cost_consignments` 同时增加两个可空金额列；历史记录默认 `NULL`。全新建表脚本 `sql/migration_create_cost_service_consignments.sql` 已包含新列，新库不再重复执行增量脚本。
   - 地面TC费及提货费原先仅属于费用台；2026-10-30起客服也可通过payables.ground录入和提交。客服未录入这些字段时，仍不覆盖费用台已有金额，详见23.11。

12. **`sales_commission`（销售提成）提成百分比**：
   - 销售提成对象新增 `commission_percentage` 字段，完整结构为 `salesperson`（业务员）、`commission_percentage`（提成百分比）、`commission_amount`（提成金额）。列表返回路径为 `data.items[].sales_commission.commission_percentage`，其他单条响应返回路径为 `data.sales_commission.commission_percentage`。
   - `commission_percentage` 是后端派生并保存的响应字段，不是费用登记台请求字段。其响应类型为数值或 `null`，取值来源于账号管理中对应用户的提成百分比（账号字段范围为 `0-100`、最多两位小数，`0` 是有效值）。
   - 前端业务员下拉框的数据来源为专用接口 `GET /api/v1/users/salespersons`（详见 4.9，费用登记台或管理员权限可访问），费用页面不再复用管理员专用的完整账号列表 `GET /api/v1/users`。选择账号后，费用保存请求只需将该账号的 `name` 写入 `sales_commission.salesperson`；保存时后端按 `users.name` 精确匹配账号，将账号当前的 `commission_percentage` 固化为费用记录的提成百分比快照并在响应中返回。账号日后修改提成百分比不会反向改写历史费用数据。
   - 提交空字符串业务员时，同时清空费用记录中的提成百分比；提交的非空业务员未匹配到账号时，为兼容历史自由文本业务员，仍保存业务员文本，但提成百分比保存为 `NULL`，不会沿用上一位业务员的旧百分比。修改时未提交 `salesperson`，则业务员及其百分比都保持原值。
   - **提成金额计算边界**：后端不根据利润和提成百分比计算、重算或覆盖 `commission_amount`。`commission_amount` 仍完全按前端提交值保存；“利润 × 提成百分比”的计算由前端完成。即使请求提供了 `operating_info.profit`，且业务员成功匹配出提成百分比，但未提供 `commission_amount`，后端也不会自动生成提成金额。
   - 请求示例：

     ```json
     {
       "sales_commission": {
         "salesperson": "张三",
         "commission_amount": 100
       }
     }
     ```

   - 响应片段：

     ```json
     {
       "sales_commission": {
         "salesperson": "张三",
         "commission_percentage": 12.5,
         "commission_amount": 100.0
       }
     }
     ```

   - 受影响接口明细：

     | HTTP 方法 | 接口路径 | 请求变化 | 响应变化 |
     |---|---|---|---|
     | GET | `/api/v1/cost-service/cost-registration` | 无 | `data.sales_commission.commission_percentage` |
     | PUT | `/api/v1/cost-service/cost-registration` | `sales_commission.salesperson` 触发后台匹配；无新增请求字段 | `data.sales_commission.commission_percentage` |
     | POST | `/api/v1/cost-service/consignments` | `sales_commission.salesperson` 触发后台匹配；无新增请求字段 | `data.sales_commission.commission_percentage` |
     | POST | `/api/v1/cost-service/consignments/draft` | `sales_commission.salesperson` 触发后台匹配；无新增请求字段 | `data.sales_commission.commission_percentage` |
     | GET | `/api/v1/cost-service/consignments` | 查询参数不变 | `data.items[].sales_commission.commission_percentage` |
     | GET | `/api/v1/cost-service/consignments/{consignment_id}` | 无 | `data.sales_commission.commission_percentage` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | `sales_commission.salesperson` 触发后台匹配；无新增请求字段 | `data.sales_commission.commission_percentage` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/draft` | `sales_commission.salesperson` 触发后台匹配；无新增请求字段 | `data.sales_commission.commission_percentage` |
     | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | 无；作废不修改提成数据 | `data.sales_commission.commission_percentage` |
     | POST | `/api/v1/cost-service/consignments/export-excel` | `ids` 入参不变 | 不导出提成百分比；单行表头118列，详见23.11.9 |

   - `commission_percentage` 仍由接口返回供前端计算，不导出 Excel。当前Excel第113-114列（DI-DJ）依次为业务员、提成金额；第115-118列（DK-DN）依次为应收合计、应付合计、利润、利润率%；单行表头共118列。
   - 存量数据库上线前需执行 `sql/migration_add_cost_sales_commission_percentage.sql`，同时为 `cost_registrations` 和 `cost_consignments` 增加可空的 `decimal(5,2)` 字段；全新建表脚本已包含该字段。

#### 23.3 客服接单台与费用登记台提交同步规范

1. **共享雪花 ID (Snowflake ID)**：
   - 客服接单台 (`/api/v1/customer-service/consignments`) 与费用登记台 (`/api/v1/cost-service/consignments`) 中对应的单据记录共享相同的全局主键 `id`。

2. **双向实时同步机制**：
   - **新增 (POST)**：
     - 在客服接单台点击“保存”新增委托记录时，客服单据状态设为 `status=1`（已提交）；系统会在同一个事务中自动在费用登记台表 (`cost_consignments`) 中创建相同 `id` 的单据记录并同步写入货主委托信息字段，但费用单据状态设为 `status=0`（未提交），等待费用人员核对并保存；
     - 在客服接单台点击“暂存”时，仅写入客服接单台，状态为`0`（未提交），不创建或更新费用登记台记录；
     - 在费用登记台新增费用单据时，系统亦会自动在客服接单台表 (`consignment_infos`) 中创建相同 `id` 的委托记录，实现无缝互通。
   - **修改 (PUT)**：
     - 客服接单台点击“保存”时，客服单据状态变为 `status=1`（已提交），并自动联动更新费用登记台相同 `id` 的各委托字段（若不存在则补全创建）；同步后的费用单据状态统一变为 `status=0`（未提交），不会直接标记为费用已提交；
     - 客服接单台在editable=true时可“暂存”修改，暂存后为`0`（未提交）；费用保存提交锁定客服后，客服保存/暂存均返回409；客服暂存时费用登记台已有数据保持不变；费用登记台暂存也不更新客服记录。费用登记台点击“保存”时，按既有代码同步覆盖同 ID 客服记录（包括未提交客服草稿），并将客服状态设为 `1`；客服记录不存在时会同步创建。费用保存同时回写应收/应付快照；详见23.11。
   - **作废 (PUT /void)**：
     - 从任意一台作废时，将来源台记录设置为 `status=2`；同 ID 对端记录存在时在同一事务中同步设置为 `status=2`，不存在时不补建。作废只改变状态，不清空业务字段、不删除记录；详情、列表和导出仍可查询。
     - 作废是终态。已作废单据不能再通过保存或暂存接口改回 `0/1`；重复作废及作废后保存/暂存均返回 HTTP 409。系统目前不提供恢复作废接口。
   - **删除 (DELETE / Batch DELETE)**：
     - 删除已提交客服单据时会删除同 ID 的费用记录；删除未提交客服草稿时仅删除客服记录。删除已提交费用单据时，只同步删除同 ID 且已提交的客服记录；删除未提交费用草稿时仅删除费用记录。
     - 原物理删除接口继续保留。删除作废单据时，仅联动删除同 ID 且同为 `status=2` 的对端记录；操作记录独立保留，不随上述删除清除。

3. **客服接单台数值字段清空语义**：
   - `PUT /api/v1/customer-service/consignments/{consignment_id}` 的数值字段 `pieces`、`actual_weight`、`chargeable_weight`、`volume`、`first_leg_weight` 支持显式传 `null`，将对应字段清空为数据库 `NULL`，并同步到费用登记台同 ID 的单据。
   - 请求体中未提供上述字段时，保持该字段已有值不变；传 `0` 时保存数值 `0`，不会被视为清空。
   - 数值字段不接受空字符串。前端清空“实际重量”的示例：`{"actual_weight": null}`。

4. **客服保存时预填费用登记台国际空运信息**：
   - 该规则仅作用于客服接单台的保存接口：新增 `POST /api/v1/customer-service/consignments` 和修改 `PUT /api/v1/customer-service/consignments/{consignment_id}`；客服暂存接口不触发该同步。
   - 客服保存时，费用登记台对应记录仍保持 `status=0`（未提交），并在同步货主委托信息的同时覆盖预填 `payables.intl_air` 中以下字段：

   | 客服/费用货主委托字段 | 费用登记台响应字段 | 数据库字段 |
   |---|---|---|
   | `pieces`（件数） | `payables.intl_air.pieces` | `pay_intl_air_pieces` |
   | `actual_weight`（实际重量） | `payables.intl_air.weight` | `pay_intl_air_weight` |
   | `flight_date`（航班日期） | `payables.intl_air.flight_date` | `pay_intl_air_flight_date` |
   | `chargeable_weight`（计费重量） | `payables.intl_air.chargeable_weight` | `pay_intl_air_chargeable_weight` |
   | `flight_no`（航班号） | `payables.intl_air.flight_no` | `pay_intl_air_flight_no` |
   | `volume`（体积） | `payables.intl_air.volume` | `pay_intl_air_volume` |
   | `flight_doc_no`（航班单号） | `payables.intl_air.flight_doc_no` | `pay_intl_air_flight_doc_no` |

   - 上述字段采用覆盖语义；客服草稿提交时，会使用保存后货主委托信息中的当前值预填费用登记台对应国际空运字段；分组中明确填写的字段（含null）优先于预填值；航班号例外：本次明确填写委托flight_no时，先同步客服国际空运快照，同次请求以委托航班号为准（23.25节）。客服editable=true时可重复保存，费用保存提交锁定后不得再次保存。同步时当前值为 `null` 或空值的，目标字段也写入对应空值。
   - 原7字段预填规则保留，新增财务分组覆盖优先级与提交锁定以23.11为准。

#### 23.4 客服接单台委托列表排序规范

客服列表另支持可选主单号参数 `flight_doc_no`，仅匹配客服委托信息顶层主单号；参数、规则和响应示例见23.21。

- `GET /api/v1/customer-service/consignments` 返回的委托信息包含 `create_time`（制单时间）和 `warehouse_entry_date`（进仓日期），现支持通过 `sort_by` 和 `sort_order` 查询参数在分页前排序。
- `sort_by` 可选值：`create_time`、`warehouse_entry_date`；默认值为 `create_time`。
- `sort_order` 可选值：`asc`（正序）、`desc`（倒序）；默认值为 `desc`。
- 不传排序参数时，继续保持原有的“制单时间倒序、ID倒序”顺序，不影响现有调用方。
- 按进仓日期排序时，若进仓日期相同，则依次按制单时间和 ID 使用相同方向排序；按制单时间排序时，ID 作为并列值排序依据，确保分页结果稳定。
- 非法的排序字段或排序方向不进入数据库查询，由接口参数枚举校验直接拒绝。

#### 23.5 费用登记台暂存与状态筛选规范

- 费用登记台单据状态使用数值字段 `status`：`0`=未提交，`1`=已提交，`2`=作废；前端负责转换为对应中文展示。
- 原保存接口保持不变：新增使用 `POST /api/v1/cost-service/consignments`，修改使用 `PUT /api/v1/cost-service/consignments/{consignment_id}`；保存成功后响应字段 `status=1`，并按原有逻辑同步客服接单台对应记录。
- 新增暂存接口：`POST /api/v1/cost-service/consignments/draft`，请求体与原新增接口一致，只创建费用登记台记录，响应字段 `status=0`，不创建客服接单台记录。
- 修改暂存接口：`PUT /api/v1/cost-service/consignments/{consignment_id}/draft`，请求体与原修改接口一致，只更新费用登记台记录，客服接单台相同 ID 的已有数据保持不变，响应字段 `status=0`。
- 费用登记台列表、详情、新增、修改、暂存和作废响应均返回 `status` 字段。
- `GET /api/v1/cost-service/consignments` 的可选查询参数 `status` 接受 `0`（未提交）、`1`（已提交）和 `2`（作废）；不传时查询全部状态。示例：`GET /api/v1/cost-service/consignments?status=2&page=1&pageSize=10`。其他值由枚举校验拒绝并返回 HTTP 422。
- 状态接口范围：暂存使用 `POST /api/v1/cost-service/consignments/draft`、`PUT /api/v1/cost-service/consignments/{consignment_id}/draft`；作废使用 `PUT /api/v1/cost-service/consignments/{consignment_id}/void`；列表 `GET /api/v1/cost-service/consignments` 支持 `status` 筛选。作废接口详见 23.8。
- 对已提交费用单据执行保存时，客服接单台对应记录会同步更新为最新数据并标记 `status=1`；对未提交费用单据执行暂存或删除时，不会覆盖或删除客服接单台中已有的已提交记录。
- 历史费用单据统一按 `status=1`（已提交）处理；存量数据库需执行 `sql/migration_add_cost_consignment_status.sql`。
- 示例：按制单时间正序查询：`GET /api/v1/customer-service/consignments?sort_by=create_time&sort_order=asc&page=1&pageSize=10`；按进仓日期倒序查询：`GET /api/v1/customer-service/consignments?sort_by=warehouse_entry_date&sort_order=desc&page=1&pageSize=10`。
- 为保证进仓日期排序性能，`consignment_infos.warehouse_entry_date` 已增加数据库索引；已有数据库需执行 `sql/migration_add_customer_consignment_warehouse_entry_date_index.sql`。

#### 23.6 客服接单台暂存与状态筛选规范

- 原保存接口保持不变：新增使用 `POST /api/v1/customer-service/consignments`，修改使用 `PUT /api/v1/customer-service/consignments/{consignment_id}`（仅editable=true可执行，费用保存提交已锁定或作废返回409）；保存成功后客服接口响应字段为 `status=1`（已提交），同步到费用登记台的对应记录为 `status=0`（未提交），等待费用人员后续保存。
- 新增暂存接口：`POST /api/v1/customer-service/consignments/draft`，请求体与原新增接口一致，只创建客服接单台记录，响应字段 `status=0`（未提交）。
- 修改暂存接口：`PUT /api/v1/customer-service/consignments/{consignment_id}/draft`（仅editable=true可执行，费用保存提交已锁定或作废返回409），请求体与原修改接口一致，只更新客服接单台记录，费用登记台相同 ID 的数据保持不变，响应字段 `status=0`（未提交）。
- 客服接单台列表、详情、新增、修改、暂存和作废响应均返回数值字段 `status`：`0`=未提交，`1`=已提交，`2`=作废；前端可将其转换为中文展示。
- `GET /api/v1/customer-service/consignments` 的可选查询参数 `status` 接受数值 `0`（未提交）、`1`（已提交）和 `2`（作废），筛选在统计总数和分页之前执行。例如：`GET /api/v1/customer-service/consignments?status=2&page=1&pageSize=10`。其他值返回 HTTP 422。
- 状态接口范围：暂存使用 `POST /api/v1/customer-service/consignments/draft`、`PUT /api/v1/customer-service/consignments/{consignment_id}/draft`；作废使用 `PUT /api/v1/customer-service/consignments/{consignment_id}/void`；列表 `GET /api/v1/customer-service/consignments` 支持 `status` 筛选。作废接口详见 23.8。
- 历史客服单据统一按 `status=1`（已提交）处理；存量数据库需执行 `sql/migration_add_customer_consignment_status.sql`。

#### 23.7 客服接单台与费用登记台单据完整操作记录

**功能范围**：按两台共用的单据 `id` 查询完整用户操作时间线，解决多人查看和修改同一单据时无法追溯操作人的问题。记录真实操作，不将自动同步伪装成另一位用户的点击。

**新增查询接口**（两入口返回相同单据的同一时间线）：

| HTTP 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/customer-service/consignments/{consignment_id}/operation-logs` | 客服接单台列表查看操作记录 |
| GET | `/api/v1/cost-service/consignments/{consignment_id}/operation-logs` | 费用登记台列表查看操作记录 |

**认证与可见性**：必须携带有效 Bearer Token，账号必须处于启用状态。沿用两台现有的全用户数据可见规则，不按创建者或操作人过滤；不需要管理员权限。不能通过此接口新增、编辑或删除操作记录。

**参数**：

| 参数 | 位置 | 类型 | 必填 | 默认值/约束 |
|---|---|---|---|---|
| `consignment_id` | Path | string | 是 | 两台列表数据返回的 `id`，不是 `internal_doc_id`；必须为正整数且小于 `9223372036854775808` |
| `page` | Query | integer | 否 | 默认 `1`，最小 `1` |
| `pageSize` | Query | integer | 否 | 默认 `20`，范围 `1-100` |

示例：`GET /api/v1/customer-service/consignments/358000000000000001/operation-logs?page=1&pageSize=20`。

**响应示例**：

```json
{
  "code": 0,
  "data": {
    "consignment_id": "358000000000000001",
    "internal_doc_id": "YT123456789CN",
    "total": 2,
    "items": [
      {
        "id": "358000000000000103",
        "consignment_id": "358000000000000001",
        "source": "cost_service",
        "action": "save",
        "operation_name": "费用信息保存",
        "operator_id": "358000000000000011",
        "operator_name": "李四",
        "operated_at": "2026-09-14T15:02:00+08:00"
      },
      {
        "id": "358000000000000102",
        "consignment_id": "358000000000000001",
        "source": "customer_service",
        "action": "save",
        "operation_name": "货主委托信息保存",
        "operator_id": "358000000000000010",
        "operator_name": "张三",
        "operated_at": "2026-09-14T15:00:00+08:00"
      }
    ],
    "page": 1,
    "pageSize": 20
  },
  "msg": "查询成功"
}
```

**响应字段**：

| 字段 | 类型 | 说明 |
|---|---|---|
| `data.consignment_id` | string | 两台共用的单据 ID |
| `data.internal_doc_id` | string | 操作记录弹窗顶部的内部单据ID；未保存编号时为空字符串，独立于分页；来源及删除后追溯见23.13 |
| `data.total` | integer | 此单据已留存的操作记录总数，不是本页条数 |
| `data.items` | array | 当前页操作记录，操作时间倒序，同一时间按记录 ID 倒序 |
| `data.page` / `data.pageSize` | integer | 当前页码和每页条数 |
| `items[].id` | string | 操作记录 ID，用于前端稳定标识 |
| `items[].consignment_id` | string | 所属单据 ID |
| `items[].source` | string | `customer_service`=客服接单台，`cost_service`=费用登记台，表示用户实际操作来源 |
| `items[].action` | string | `draft`=暂存，`save`=保存，`void`=作废，`delete`=删除 |
| `items[].operation_name` | string | 当次操作名称，见下表；可直接展示 |
| `items[].operator_id` | string | 当前登录操作用户 ID，不是单据最初创建者 |
| `items[].operator_name` | string | 操作当时的用户姓名快照，用户改名或删除账号不改变已有记录 |
| `items[].operated_at` | string | 服务端生成的中国时间 ISO 8601，包含 `+08:00`，不是业务制单时间 |

**记录触发接口**（原接口请求体与成功响应结构不变）：

| 用户操作 | 接口 | `source` | `action` | 操作名称 |
|---|---|---|---|---|
| 客服暂存新增 | `POST /api/v1/customer-service/consignments/draft` | `customer_service` | `draft` | 货主委托信息暂存 |
| 客服暂存修改 | `PUT /api/v1/customer-service/consignments/{consignment_id}/draft` | `customer_service` | `draft` | 货主委托信息暂存 |
| 客服保存新增 | `POST /api/v1/customer-service/consignments` | `customer_service` | `save` | 货主委托信息保存 |
| 客服保存修改 | `PUT /api/v1/customer-service/consignments/{consignment_id}` | `customer_service` | `save` | 货主委托信息保存 |
| 客服作废 | `PUT /api/v1/customer-service/consignments/{consignment_id}/void` | `customer_service` | `void` | 货主委托信息作废 |
| 费用暂存新增 | `POST /api/v1/cost-service/consignments/draft` | `cost_service` | `draft` | 费用信息暂存 |
| 费用暂存修改 | `PUT /api/v1/cost-service/consignments/{consignment_id}/draft` | `cost_service` | `draft` | 费用信息暂存 |
| 费用保存新增 | `POST /api/v1/cost-service/consignments` | `cost_service` | `save` | 费用信息保存 |
| 费用保存修改 | `PUT /api/v1/cost-service/consignments/{consignment_id}` | `cost_service` | `save` | 费用信息保存 |
| 费用作废 | `PUT /api/v1/cost-service/consignments/{consignment_id}/void` | `cost_service` | `void` | 费用信息作废 |
| 客服单个删除 | `DELETE /api/v1/customer-service/consignments/{consignment_id}` | `customer_service` | `delete` | 货主委托信息删除 |
| 客服批量删除 | `POST /api/v1/customer-service/consignments/batch-delete` | `customer_service` | `delete` | 货主委托信息删除 |
| 费用单个删除 | `DELETE /api/v1/cost-service/consignments/{consignment_id}` | `cost_service` | `delete` | 费用信息删除 |
| 费用批量删除 | `POST` 或 `DELETE /api/v1/cost-service/consignments/batch-delete` | `cost_service` | `delete` | 费用信息删除 |

**同步及事务规则**：

- 客服保存成功时只新增一条“货主委托信息保存”；同事务同步费用数据并将费用状态设为未提交，不额外新增“费用信息保存”。
- 费用保存成功时只新增一条“费用信息保存”；同事务同步客服数据并将客服状态设为已提交，不额外新增“货主委托信息保存”。
- 暂存只修改来源台的数据，但仍记录在共用单据时间线中。另一台查询可见该暂存事件，不代表其数据已经被同步修改；前端应展示 `source` 或操作名称以区分。
- 作废成功只记录发起台的一条真实用户操作；系统自动将已存在的对端记录同步为作废，不追加第二条虚构作废操作。重复作废返回 409，不写入重复记录。
- 新建先生成单据 ID，再在同一事务加入记录；保存、暂存、同步数据和操作记录一起提交或回滚。记录写入失败将使当次业务操作失败，不允许“业务成功但追溯丢失”。
- 单个删除保留一条删除记录；批量删除对实际存在于来源台的每个单据记录一条，重复 ID 不重复记录，不存在的 ID 不产生虚构删除记录。同步删除不追加第二条用户操作。
- 对同一内容重复点击暂存或保存，每次成功请求都会留下一条记录；本功能不改变接口既有的重复提交行为。
- 仅覆盖列表单据操作；系统唯一的登记编辑区（`consignment-registration`、`cost-registration`）、列表查询、详情查询、Excel 导出不写入本时间线。当前不包含字段修改前后的差异内容。

**空结果与错误**：

- 已存在的历史单据尚无记录：HTTP 200，`total=0`、`items=[]`，不伪造历史。
- 页码超过记录页数：HTTP 200，`items=[]`，`total` 仍为实际总数。
- 单据已删除但留有记录：仍可按原 ID 查询历史；只有一台记录或只有历史记录时，两入口都可查询。
- 单据在两台均不存在且无历史记录：HTTP 404，`code=404`、`data=null`。
- 非数字、非正整数或超出有符号 bigint 范围的 ID：HTTP 400，`code=400`、`data=null`。
- `page`、`pageSize` 类型或范围非法：HTTP 422，由参数校验拒绝；按应用统一格式返回错误。
- 未携带 Bearer 凭据沿用现有认证行为（HTTP 403）；无效/过期 Token、账号不存在或停用等返回 HTTP 401。

**部署与历史边界**：已建操作记录表另需执行23.13的编号快照增量迁移；新建表脚本已包含快照列，勿重复加列。上线前执行 `sql/migration_create_consignment_operation_logs.sql` 创建 `consignment_operation_logs`，并对已存在两台 `status` 字段的数据库执行 `sql/migration_add_consignment_void_status.sql` 更新状态语义注释；两脚本均不回填或修改历史业务状态。新库初始化通过已注册 ORM 模型创建操作记录表。仅从本功能上线后的成功操作开始记录，旧系统没有记录的操作人和操作时间无法可靠还原，不能从创建者或更新时间推测补录。表不对单据或账号设置级联外键；查询使用 `(consignment_id, operated_at, id)` 复合索引和最多 100 条的单页限制，无逐条查询操作人信息。

**前端接入**：两台列表为每条单据增加“操作记录”入口，传本行 `id` 调用对应 GET 接口。弹窗顶部展示 `data.internal_doc_id`；两台编辑区和列表列隐藏此字段，但保留原接口传参与回显。弹窗按返回顺序展示 `operation_name`、`operator_name`、`operated_at`；超过一页时继续翻页，读取至完整记录，不只展示第一屏。历史为空时提示“暂无操作记录（仅记录功能上线后的操作）”，不要提示“从未修改”。

#### 23.8 客服接单台与费用登记台作废接口

**用途**：作废用于停止单据后续编辑并保留完整业务数据，与原 DELETE 物理删除是两种独立操作。作废后记录继续出现在列表和详情中，可通过 `status=2` 筛选，也可继续导出或查看操作记录。

| 来源台 | HTTP 方法 | 路径 | 请求体 |
|---|---|---|---|
| 客服接单台 | PUT | `/api/v1/customer-service/consignments/{consignment_id}/void` | 无 |
| 费用登记台 | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | 无 |

**认证与路径参数**：接口沿用两台现有认证规则，必须携带有效 Bearer Token且账号处于启用状态。`consignment_id` 取列表返回的单据 `id`；非数字格式返回 HTTP 400，来源台中不存在该 ID 时返回 HTTP 404。

请求示例：

```http
PUT /api/v1/customer-service/consignments/358000000000000001/void
Authorization: Bearer <access_token>
```

接口不接收 JSON 请求体。成功时 HTTP 200，并返回来源台修改后的完整单据结构；客服响应结构与客服详情一致，费用响应结构与费用详情一致，其中 `status` 固定为 `2`。以下仅节选状态相关字段：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 2,
    "updated_at": "2026-09-15T10:30:00+08:00"
  },
  "msg": "委托信息作废成功"
}
```

费用入口成功响应的 `msg` 为`费用信息作废成功`。

**状态与同步规则**：

- 来源台记录无论原状态是 `0`（未提交）还是 `1`（已提交），作废成功后均变为 `2`（作废）。业务字段保持原值。
- 同 ID 对端记录已经存在时，同一事务将其同步设置为 `2`；对端记录不存在时不创建新记录。因此，单边暂存草稿可以直接作废，另一台不会凭空出现数据。
- 作废、对端状态同步和操作记录写入使用同一数据库事务，任一步失败时全部回滚，不会出现“状态已作废但无操作记录”或只有一台提交成功的情况。
- 客服入口写入一条 `action=void`、操作名称为`货主委托信息作废`的记录；费用入口写入一条 `action=void`、操作名称为`费用信息作废`的记录。自动同步的对端不额外写第二条记录。
- 同一来源记录已经是 `status=2` 时，再次调用作废接口返回 HTTP 409，响应 `msg` 为`委托信息已作废，请勿重复操作`或`费用信息已作废，请勿重复操作`，不新增操作记录。
- 作废为不可逆终态，当前无恢复接口。对已作废记录调用该台保存或暂存修改接口均返回 HTTP 409；响应 `msg` 为`已作废的委托信息不能暂存或保存`或`已作废的费用信息不能暂存或保存`，请求字段不会写入数据库，也不新增保存/暂存记录。

**列表、导出与删除兼容**：

- 两台列表查询的 `status` 参数新增枚举值 `2`；不传 `status` 仍查询全部状态，不会默认隐藏作废记录。详情接口原样返回 `status=2`。
- 两台 Excel 第1列为`序号`，第2列为`状态`，作废记录显示为`作废`；当前单行表头、列顺序详见23.11.9。
- 原单个及批量 DELETE 接口继续可用。物理删除 `status=2` 的来源记录时，仅联动删除同 ID 且同为 `status=2` 的对端记录；若异常历史数据中对端不是作废状态，则保留对端，避免误删仍有效版本。删除操作记录继续独立保留。

**部署**：存量数据库先确保已执行两台原 `status` 字段迁移，再执行 `sql/migration_add_consignment_void_status.sql`。该迁移不新增字段、不改默认值、不改变已有 `0/1` 数据，只将数据库字段注释统一为 `0=未提交，1=已提交，2=作废`。操作记录功能同时需要 `sql/migration_create_consignment_operation_logs.sql`。

#### 23.9 客服接单台列表目的站模糊搜索

**接口地址**：`GET /api/v1/customer-service/consignments`

列表接口新增以下可选 Query 参数，原有请求和响应结构保持不变：

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `destination` | string | 否 | 目的站模糊搜索；仅匹配 `origin_destination` 中最后一个 `-` 后的内容 |

**匹配规则**：

- `origin_destination` 存储完整航线，可能包含始发站和多个经停站。接口按最后一个英文半角连字符 `-` 分隔，取最后一段作为目的站。例如 `SZX-CKG-KUL` 的目的站是 `KUL`。
- 搜索采用包含式模糊匹配。对目的站 `KUL`，传 `K`、`U`、`L`、`KU`、`UL` 或 `KUL` 均可匹配；英文字母不区分大小写。
- 支持中文目的站及中文片段。例如航线 `深圳-广州-吉隆坡国际机场` 的目的站为`吉隆坡国际机场`，传`隆坡`或`国际`均可匹配。
- 始发站及中间经停站不参与匹配。例如 `KUL-SIN` 不会因传入 `destination=KUL` 而返回，`深圳-广州-吉隆坡` 也不会因传入 `destination=广州` 而返回。
- 参数首尾空白会被去除；不传、传空字符串或仅传空白时不增加目的站筛选条件。输入中的 `%`、`_` 按普通字符匹配，不作为数据库通配符。
- `destination` 可独立使用，也可与日期、客户名称、状态和排序参数组合；多个筛选条件之间为 AND 关系。目的站筛选在总数统计和分页之前执行，因此 `data.total` 是筛选后的记录总数。
- 本功能不改变 `origin_destination` 的写入格式、列表响应字段或 Excel 导出规则，无需数据库迁移。

**请求示例**：

```http
GET /api/v1/customer-service/consignments?destination=UL&page=1&pageSize=10
Authorization: Bearer <token>
```

若数据库存在 `origin_destination=SZX-CKG-KUL`，上述请求会返回该记录；返回数据仍在 `items[].origin_destination` 中提供完整航线 `SZX-CKG-KUL`。

#### 23.10 客服接单台列表航班号模糊搜索

**接口地址**：`GET /api/v1/customer-service/consignments`

列表接口新增以下可选 Query 参数，原有请求和响应结构保持不变：

| 参数名 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `flight_no` | string | 否 | 客服接单台列表航班号模糊搜索 |

**匹配规则**：

- `flight_no` 仅匹配客服接单台列表数据自身的 `items[].flight_no`，即数据库 `consignment_infos.flight_no`；不扩展匹配费用登记台中的国际空运应付或国内空运应付航班号。
- 搜索采用包含式模糊匹配。例如列表航班号为 `ZH1234` 时，传 `ZH`、`123`、`H12` 或完整的 `ZH1234` 均可匹配；英文字母不区分大小写，也支持中文内容及中文片段。
- 参数首尾空白会被去除；不传、传空字符串或仅传空白时不增加航班号筛选条件。输入中的 `%`、`_` 按普通字符匹配，不作为数据库通配符。
- `flight_no` 可独立使用，也可与日期、客户名称、目的站、状态和排序参数组合；多个筛选条件之间为 AND 关系。航班号筛选在总数统计和分页之前执行，因此 `data.total` 是筛选后的记录总数。
- 本功能不改变航班号的写入格式、列表响应字段或 Excel 导出规则，无需数据库迁移。

**请求示例**：

```http
GET /api/v1/customer-service/consignments?flight_no=H12&page=1&pageSize=10
Authorization: Bearer <token>
```

若数据库存在 `flight_no=ZH1234`，上述请求会返回该记录，响应中的 `items[].flight_no` 仍为完整航班号 `ZH1234`。






#### 23.11 客服扩展录入、费用字段补齐与提交锁定（2026-10-30）

本节为本次前端对接的完整契约。三张需求截图按“第一套=客服接单台，第二套=费用登记台”落实。
旧字段键名继续沿用；客服委托信息仍在 JSON 顶层，增加 `receivables` 与 `payables` 两个对象。
费用登记台仍使用 `consignor_info`、`receivables`、`payables` 等既有分组。所有接口均需有效 Bearer Token；路由地址没有新增或改名。

**编辑锁定规则（2026-11-09更新）**：客服保存后 `status=1`、`editable=true`，可再次PUT保存或暂存；费用保存提交成功后客服 `editable=false`，届时才锁定。不得只根据status禁用编辑。完整契约、迁移说明见23.19。
费用保存提交后锁定客服，上述两个PUT均返回HTTP409，管理员也遵守；客服status=2始终不可编辑。
费用台暂存、保存、既有作废和物理删除流程保持原语义；本次锁定针对客服的字段编辑与退回暂存，不取消作废/删除接口。
前端应根据客服响应 `status` 控制编辑按钮，服务端也会校验，不能仅靠禁用按钮。
系统唯一登记模板与列表单据相互独立，模板 PUT 仍可编辑，不解除任何已提交列表单据的锁定。

##### 23.11.1 受影响接口清单

以下路径均带 `/api/v1` 前缀；表中 `S` 表示完整客服对象（23.11.6），`C` 表示完整费用对象（23.11.7）。
成功响应仍为 `{ "code": 0, "data": ..., "msg": "..." }`；ID 一律为字符串。

| 方法 | 路径 | 本次入参变化 | 成功响应 data / 副作用 |
|---|---|---|---|
| GET | `/customer-service/consignment-registration` | 无 | S；无模板时仍为 null |
| PUT | `/customer-service/consignment-registration` | 客服请求结构 S 的业务字段，新增两个分组 | S；更新唯一模板，不流转 |
| POST | `/customer-service/consignments` | 客服请求结构，新增两个分组 | S，status=1；同事务同步费用 C，费用 status=0 |
| POST | `/customer-service/consignments/draft` | 同客服新增 | S，status=0；只写客服 |
| GET | `/customer-service/consignments` | 查询条件不变 | `{items:[S],total,page,pageSize}`；每条增加两个分组 |
| GET | `/customer-service/consignments/{consignment_id}` | 无 | S，增加两个分组 |
| PUT | `/customer-service/consignments/{consignment_id}` | 同客服请求，可只传变更字段；仅 editable=true 可执行 | S，status=1、editable=true；同步费用status=0；费用提交锁定或作废返回409 |
| PUT | `/customer-service/consignments/{consignment_id}/draft` | 同上；仅 editable=true 可执行 | S，status=0、editable=true；不写费用；费用提交锁定或作废返回409 |
| PUT | `/customer-service/consignments/{consignment_id}/void` | 无请求体 | S，status=2；新增分组随业务数据保留 |
| POST | `/customer-service/consignments/export-excel` | `{ids:[string]}` 不变 | xlsx 二进制；94列，单行表头，第2行开始为数据 |
| GET | `/cost-service/cost-registration` | 无 | C；无模板时仍为 null |
| PUT | `/cost-service/cost-registration` | 既有费用请求增加20个叶字段 | C；只更新模板 |
| POST | `/cost-service/consignments` | 同费用请求 | C，status=1；回写客服基本信息及应收/应付快照，客服锁定 |
| POST | `/cost-service/consignments/draft` | 同费用请求 | C，status=0；不创建客服记录 |
| GET | `/cost-service/consignments` | 查询条件不变 | `{items:[C],total,page,pageSize}`；每条补齐新增字段 |
| GET | `/cost-service/consignments/{consignment_id}` | 无 | C，补齐新增字段 |
| PUT | `/cost-service/consignments/{consignment_id}` | 同费用请求，可只传变更字段 | C，status=1；回写客服基本信息及应收/应付快照 |
| PUT | `/cost-service/consignments/{consignment_id}/draft` | 同费用请求 | C，status=0；不回写客服，也不改变客服现有editable（费用曾保存后不会解锁） |
| PUT | `/cost-service/consignments/{consignment_id}/void` | 无请求体 | C，status=2；新增业务字段保留 |
| POST | `/cost-service/consignments/export-excel` | `{ids:[string]}` 不变 | xlsx 二进制；118列，单行表头，第2行开始为数据 |

路径参数 `consignment_id` 为列表返回的 `id`；非法数字返回400，不存在返回404。
列表仍支持原有分页、状态、日期、航班及排序条件，响应分页键名称不变；操作记录、删除接口的请求及响应结构不变。

##### 23.11.2 20个新增字段（两台相同分组路径）

全部可选，历史数据返回 null。金额/费率为 JSON number，费用台数据库精度 decimal(10,2)；国内空运体积为 decimal(10,3)。
数值0有效；不要传空字符串。燃油取重方式沿用运费取重编码习惯，以字符串 `"1"` 表示实重、`"2"` 表示计费重，不提交中文或数字1/2。
新增备注为不定长文本；汽运主单号及城市为最多100字符的字符串（数据库限制）。

| 完整JSON路径 | 类型 | 必填 | 页面字段 / 含义 |
|---|---|---|---|
| `receivables.buy_order_fee` | number / null | 否 | 买单费/单 |
| `receivables.document_fee` | number / null | 否 | 单证费/单 |
| `receivables.fuel_rate` | number / null | 否 | 燃油费率 |
| `receivables.fuel_weight_method` | string（1/2） / null | 否 | 燃油费取重方式：1=实重，2=计费重 |
| `receivables.tc_rate` | number / null | 否 | TC费率 |
| `receivables.front_warehouse_rate` | number / null | 否 | 前置仓费率 |
| `receivables.remark` | string / null | 否 | 应收备注 |
| `payables.intl_air.buy_order_fee` | number / null | 否 | 买单费/单 |
| `payables.intl_air.document_fee` | number / null | 否 | 单证费/单 |
| `payables.intl_air.fuel_rate` | number / null | 否 | 燃油费率 |
| `payables.intl_air.fuel_weight_method` | string（1/2） / null | 否 | 燃油费取重方式：1=实重，2=计费重 |
| `payables.intl_air.tc_rate` | number / null | 否 | TC费率 |
| `payables.intl_air.front_warehouse_rate` | number / null | 否 | 前置仓费率 |
| `payables.customs.buy_order_fee` | number / null | 否 | 买单费/单 |
| `payables.customs.document_fee` | number / null | 否 | 单证费/单 |
| `payables.ground.tc_rate` | number / null | 否 | TC费率 |
| `payables.trucking.flight_doc_no` | string / null | 否 | 主单号 |
| `payables.trucking.origin_city` | string / null | 否 | 始发城市 |
| `payables.trucking.destination_city` | string / null | 否 | 目的城市 |
| `payables.dom_air.volume` | number / null | 否 | 体积 |

`buy_order_fee` 和 `document_fee` 是每单单价；数量仍从委托信息 `customs_declaration`（例如 `1买单+3单证`）由前端识别。
后端不解析该字符串、不计算报关费、不根据费率计算燃油费/TC费/前置仓费，也不自动计算应收、应付小计、合计、折让、提成或利润。
例如前端提交 `fuel_rate=0`、`receivable_fuel_fee=65`，后端仍保存65，不主动改成0。

##### 23.11.3 页面名称与既有字段对应（请不要重复新增金额字段）

| 页面字段 | 使用的JSON路径 | 说明 |
|---|---|---|
| 委托主单号 | 客服顶层 `flight_doc_no`；费用 `consignor_info.flight_doc_no` | 沿用旧“航班单号”字段；不是内部单据ID，也不是提单 |
| 应收运费费率 | `receivables.unit_price` | 沿用旧单价字段 |
| 应收燃油费 | `receivables.receivable_fuel_fee` | 沿用旧金额字段 |
| 应收TC费 | `receivables.tc_express_fee` | 旧字段名保留，页面展示TC费 |
| 应收前置仓费 | `receivables.warehouse_ground_fee` | 旧字段名保留 |
| 国际/国内空运、汽运、地面代理名称 | 各分组 `outsource_unit` | 不新增 agent_name 字段 |
| 报关代理名称 | `payables.customs.agent` | 沿用报关代理字段 |
| 国际/国内空运主单号 | 各分组 `flight_doc_no` | 沿用旧航班单号/航空单号 |
| 国际/国内空运实际重量 | 各分组 `weight` | `chargeable_weight` 为对应计费重量 |
| 国际/国内空运单价 | 各分组 `rate` | 沿用旧费率字段 |
| 国际空运燃油费 | `payables.intl_air.borrow_magnetic_fuel_pickup_fee` | 沿用旧合并命名字段作为当前燃油金额，不新增 fuel_fee |
| 国际空运TC费 | `payables.intl_air.tc_network_disposal_fee` | 沿用旧金额字段 |
| 国际空运前置仓费 | `payables.intl_air.front_warehouse` | 沿用旧金额字段 |
| 地面操作日期 | `payables.ground.date` | 沿用旧托运日期字段 |
| 地面前置仓费率 / 前置仓费 | `payables.ground.rate` / `payables.ground.freight` | 原有金额列继续使用，不重复存储 |
| 地面TC费 / 提货费 | `payables.ground.tc_fee` / `payables.ground.pickup_fee` | 本次客服也支持录入与提交 |
| 地面提单费 | `payables.ground.lading_express_fee` | 保留旧提单/快件处置费字段 |
| 汽运计费重量 | `payables.trucking.weight` | 沿用旧重量字段，不新增 chargeable_weight |
| 经营应收合计 / 应付合计 | `receivables.total` / `payables.pay_total` | 经营信息展示这两个值，不在 operating_info 重复新增 |

##### 23.11.4 字段缺省、清空及同步优先级

1. 客服新增分组：省略整个 `receivables`、`payables` 或其中子对象，或将分组设为 null，表示本次不修改该分组；传 `{}` 也不清空。
   分组内只提交变更叶字段即可，未提交的叶字段保留；显式传叶字段 null 表示清空；字符串 `""` 表示保存空串；数值0正常保存。
   此规则也适用于客服唯一登记模板的新增分组；模板原有顶层委托信息继续按原整体保存规则处理。
2. 客服顶层既有字段保留原语义：修改时数值字段省略保留、null清空；日期和文本null保持原值。保存只允许未提交单据。
3. 费用台本次新增20个叶字段：修改时省略保留、null清空；新增时省略或null保存NULL。既有费用字段沿用“省略或null均保留旧值”的规则，不能将新字段规则误用于旧金额。
4. 客服提交顺序：先同步原顶层委托信息，再按原规则预填国际空运7个字段，再覆盖客服明确录入的应收及应付字段。本次请求填写委托flight_no时，先将它同步到客服国际空运快照，航班号按23.25节以委托值优先；其他6个预填字段保持原规则。
   例如顶层 `actual_weight=100`、`payables.intl_air.weight=105`，费用台货主重量为100，国际空运重量为105；若分组未明确填weight则仍按100预填。
   在此前暂存请求中明确保存过的字段也属于已录入字段；叶字段null同样有覆盖效力；未录入的费用字段不被清空。
5. 客服提交与费用同步、操作记录在同一事务完成。成功后客服1、费用0。客服两个修改接口使用行锁后校验状态，防止并发暂存把已提交状态退回0。
6. 费用保存继续回写同ID客服基本信息，额外回写应收及应付快照，客服状态为1；费用暂存不回写。费用台独有的折让、业务员提成、经营信息不加入客服请求。
   业务员提成百分比继续由后端匹配账号并固化，提成金额仍由前端提交，规则不变。
7. 旧记录没有客服财务快照时，客服新增分组返回全部已知键，数值和文本均为null；应付子分组返回对象。
   费用台既有文本仍按原规则可能返回空串，新20字段的数据库NULL返回null。
   不从历史费用金额倒推出费率，也不在部署时覆盖历史记录；费用后续保存才回写客服快照。

局部修改示例（仅对未提交客服单据）：

```json
{
  "receivables": {
    "fuel_rate": 0,
    "remark": null
  },
  "payables": {
    "ground": {
      "tc_fee": null
    }
  }
}
```

##### 23.11.5 全部业务字段字典

以下字段在请求中均为可选。客服用顶层委托信息，费用用 `consignor_info`；两台共用应收/应付字段字典。
本次客服新增的是整套应收/应付录入能力，除截图展示字段外也兼容这些分组内已有费用字段；页面可以只提交所需字段。
日期建议 `YYYY-MM-DD`，制单时间 `YYYY-MM-DD HH:MM:SS`。主单号、代理名称等沿用原有string限制；件数为integer；其他重量、金额、费率为number。

**委托信息（客服顶层；费用在consignor_info对象中）**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `create_time` | string | 制单时间 (YYYY-MM-DD HH:MM:SS) |
| `internal_doc_id` | string | 内部单据ID，仍由前端传入及原路径回显，编辑区/列表隐藏，操作记录弹窗展示，不进入Excel；详见23.13 |
| `warehouse_entry_date` | string | 进仓日期 (YYYY-MM-DD) |
| `customer_name` | string | 客户名称 |
| `origin_destination` | string | 始发站-目的站 |
| `customs_declaration` | string | 报关 |
| `bill_of_lading` | string | 提单 |
| `flight_date` | string | 航班日期 (YYYY-MM-DD) |
| `flight_no` | string | 航班号 |
| `flight_doc_no` | string | 航班单号 |
| `pieces` | integer | 件数 |
| `actual_weight` | number | 实际重量 |
| `chargeable_weight` | number | 计费重量 |
| `volume` | number | 体积 |
| `first_leg_weight` | number | 一程重量 |
| `agent` | string | 代理 |
| `remark` | string | 备注 |

**应收款项**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `receivables.unit_price` | number | 运费费率 |
| `receivables.freight_method` | string | 运费计算方式 |
| `receivables.freight` | number | 运费 |
| `receivables.receivable_fuel_fee` | number | 燃油费 |
| `receivables.lading_info_fee` | number | 提单费/信息录入费 |
| `receivables.split_offset_telex_fee` | number | 分单费/抵账费/电报费 |
| `receivables.customs_fee` | number | 报关费 |
| `receivables.continuation_sheet_fee` | number | 续页费 |
| `receivables.customs_inspection_fee` | number | 海关查验费 |
| `receivables.magnetic_security_fee` | number | 磁检费/安检费 |
| `receivables.tc_express_fee` | number | TC费 |
| `receivables.warehouse_ground_fee` | number | 前置仓费 |
| `receivables.doc_make_fee` | number | 制单费 |
| `receivables.doc_split_fee` | number | 制单分单费 |
| `receivables.skid_fee` | number | 垫板费 |
| `receivables.pallet_packing_fee` | number | 打板/装箱费 |
| `receivables.probe_fee` | number | 探板费 |
| `receivables.consumables_fee` | number | 耗材费 |
| `receivables.first_leg_fee` | number | 一程费用 |
| `receivables.total` | number | 应收合计 |
| `receivables.buy_order_fee` | number | 买单费/单 |
| `receivables.document_fee` | number | 单证费/单 |
| `receivables.fuel_rate` | number | 燃油费率 |
| `receivables.fuel_weight_method` | string | 燃油费取重方式：1=实重，2=计费重 |
| `receivables.tc_rate` | number | TC费率 |
| `receivables.front_warehouse_rate` | number | 前置仓费率 |
| `receivables.remark` | string | 应收备注 |

**国际空运**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `payables.intl_air.subtotal` | number | 应付小计 |
| `payables.intl_air.outsource_unit` | string | 代理名称 |
| `payables.intl_air.origin` | string | 始发站 |
| `payables.intl_air.destination` | string | 到达站 |
| `payables.intl_air.flight_doc_no` | string | 主单号 |
| `payables.intl_air.flight_no` | string | 航班号 |
| `payables.intl_air.flight_date` | string | 航班日期 (YYYY-MM-DD) |
| `payables.intl_air.pieces` | integer | 件数 |
| `payables.intl_air.weight` | number | 实际重量 |
| `payables.intl_air.volume` | number | 体积 |
| `payables.intl_air.chargeable_weight` | number | 计费重量 |
| `payables.intl_air.rate` | number | 单价 |
| `payables.intl_air.freight_method` | string | 运费计算方式 |
| `payables.intl_air.freight` | number | 运费 |
| `payables.intl_air.lading_fee` | number | 提单费 |
| `payables.intl_air.split_fee` | number | 分单 |
| `payables.intl_air.borrow_magnetic_fuel_pickup_fee` | number | 燃油费 |
| `payables.intl_air.tc_network_disposal_fee` | number | TC费 |
| `payables.intl_air.customs_fee` | number | 报关费 |
| `payables.intl_air.continuation_sheet_fee` | number | 续页费 |
| `payables.intl_air.consumables_fee` | number | 耗材费 |
| `payables.intl_air.front_warehouse` | number | 前置仓费 |
| `payables.intl_air.other_fee` | number | 其他费用 |
| `payables.intl_air.remark` | string | 备注 |
| `payables.intl_air.buy_order_fee` | number | 买单费/单 |
| `payables.intl_air.document_fee` | number | 单证费/单 |
| `payables.intl_air.fuel_rate` | number | 燃油费率 |
| `payables.intl_air.fuel_weight_method` | string | 燃油费取重方式：1=实重，2=计费重 |
| `payables.intl_air.tc_rate` | number | TC费率 |
| `payables.intl_air.front_warehouse_rate` | number | 前置仓费率 |

**报关**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `payables.customs.subtotal` | number | 应付小计 |
| `payables.customs.date` | string | 报关日期 (YYYY-MM-DD) |
| `payables.customs.agent` | string | 代理名称 |
| `payables.customs.customs_fee` | number | 报关费 |
| `payables.customs.continuation_sheet_fee` | number | 续页费 |
| `payables.customs.inspection_delete_fee` | number | 查验费/删单费 |
| `payables.customs.other_fee` | number | 其他费用 |
| `payables.customs.remark` | string | 备注 |
| `payables.customs.buy_order_fee` | number | 买单费/单 |
| `payables.customs.document_fee` | number | 单证费/单 |

**地面操作**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `payables.ground.subtotal` | number | 应付小计 |
| `payables.ground.date` | string | 操作日期 (YYYY-MM-DD) |
| `payables.ground.outsource_unit` | string | 代理名称 |
| `payables.ground.chargeable_weight` | number | 计费重量 |
| `payables.ground.rate` | number | 前置仓费率 |
| `payables.ground.freight` | number | 前置仓费 |
| `payables.ground.tc_fee` | number | TC费 |
| `payables.ground.pickup_fee` | number | 提货费 |
| `payables.ground.lading_express_fee` | number | 提单费/快件处置费 |
| `payables.ground.security_customs_fee` | number | 安检费/报关费 |
| `payables.ground.pallet_exit_fee` | number | 打板费/退场费 |
| `payables.ground.other_fee` | number | 其他费用 |
| `payables.ground.remark` | string | 备注 |
| `payables.ground.tc_rate` | number | TC费率 |

**汽运**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `payables.trucking.subtotal` | number | 应付小计 |
| `payables.trucking.date` | string | 托运日期 (YYYY-MM-DD) |
| `payables.trucking.outsource_unit` | string | 代理名称 |
| `payables.trucking.pieces` | integer | 件数 |
| `payables.trucking.weight` | number | 计费重量 |
| `payables.trucking.volume` | number | 体积 |
| `payables.trucking.unit_price` | number | 单价 |
| `payables.trucking.freight_method` | string / null | 运费计算方式，前端定义选项，原样保存，最多50字符，未传保留/null清空；详见23.15 |
| `payables.trucking.freight` | number | 运费 |
| `payables.trucking.doc_fee` | number | 制单费 |
| `payables.trucking.other_fee` | number | 其他费用 |
| `payables.trucking.remark` | string | 备注 |
| `payables.trucking.flight_doc_no` | string | 主单号 |
| `payables.trucking.origin_city` | string | 始发城市 |
| `payables.trucking.destination_city` | string | 目的城市 |

**国内空运**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `payables.dom_air.subtotal` | number | 应付小计 |
| `payables.dom_air.date` | string | 托运日期 (YYYY-MM-DD) |
| `payables.dom_air.outsource_unit` | string | 代理名称 |
| `payables.dom_air.origin` | string | 始发站 |
| `payables.dom_air.destination` | string | 到达站 |
| `payables.dom_air.airline` | string | 航空公司 |
| `payables.dom_air.airline_unit` | string | 航空单位 |
| `payables.dom_air.flight_doc_no` | string | 主单号 |
| `payables.dom_air.flight_no` | string | 航班号 |
| `payables.dom_air.flight_date` | string | 航班日期 (YYYY-MM-DD) |
| `payables.dom_air.pieces` | integer | 件数 |
| `payables.dom_air.weight` | number | 实际重量 |
| `payables.dom_air.chargeable_weight` | number | 计费重量 |
| `payables.dom_air.rate` | number | 单价 |
| `payables.dom_air.freight_method` | string | 运费计算方式 |
| `payables.dom_air.freight` | number | 运费 |
| `payables.dom_air.other_fee` | number | 其他费用 |
| `payables.dom_air.remark` | string | 备注 |
| `payables.dom_air.volume` | number | 体积 |

| 字段路径 | 类型 | 页面含义 |
|---|---|---|
| `payables.pay_total` | number / null | 应付合计 |

**费用台独有：折让信息**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `discount_info.discount_person` | string | 折让人员 |
| `discount_info.discount_rate` | number | 费率 |
| `discount_info.discount_fee` | number | 折让费 |

**费用台独有：销售提成**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `sales_commission.salesperson` | string | 业务员 |
| `sales_commission.commission_amount` | number | 提成金额 |

**费用台独有：经营信息**

| 字段路径 | 类型（均可null） | 页面含义 |
|---|---|---|
| `operating_info.profit` | number | 利润 |
| `operating_info.profit_margin` | number | 利润率 |

费用响应额外包含 `sales_commission.commission_percentage`（number/null，只读），不能通过请求直接修改百分比。

##### 23.11.6 客服完整请求与响应示例（S）

`POST /api/v1/customer-service/consignments` 的请求如下；POST暂存、PUT保存、PUT暂存、PUT登记模板共用同样的业务字段。
PUT列表单据可只提交变更字段；不得提交id、status、creator_id、created_at、updated_at作为可写字段。

```json
{
  "create_time": "2026-10-30 09:00:00",
  "internal_doc_id": "QF-20261030-001",
  "warehouse_entry_date": "2026-10-30",
  "customer_name": "示例客户",
  "origin_destination": "CAN-NRT",
  "customs_declaration": "1买单+3单证",
  "bill_of_lading": "1-1",
  "flight_date": "2026-10-31",
  "flight_no": "CZ385",
  "flight_doc_no": "784-12345678",
  "pieces": 10,
  "actual_weight": 100,
  "chargeable_weight": 120,
  "volume": 1.234,
  "first_leg_weight": null,
  "agent": "示例代理",
  "remark": "委托备注",
  "receivables": {
    "buy_order_fee": 300,
    "document_fee": 150,
    "customs_fee": 750,
    "fuel_rate": 0.65,
    "fuel_weight_method": "1",
    "receivable_fuel_fee": 65,
    "tc_rate": 0.3,
    "tc_express_fee": 36,
    "front_warehouse_rate": 0.2,
    "warehouse_ground_fee": 24,
    "remark": "应收单独备注",
    "unit_price": 26.67,
    "freight_method": "2",
    "freight": 3200,
    "lading_info_fee": 50,
    "split_offset_telex_fee": 20,
    "total": 4095
  },
  "payables": {
    "intl_air": {
      "outsource_unit": "国际代理",
      "weight": 105,
      "flight_doc_no": "999-00000001",
      "buy_order_fee": 280,
      "document_fee": 140,
      "customs_fee": 700,
      "fuel_rate": 0.5,
      "fuel_weight_method": "2",
      "borrow_magnetic_fuel_pickup_fee": 60,
      "tc_rate": 0.25,
      "tc_network_disposal_fee": 30,
      "front_warehouse_rate": 0.1,
      "front_warehouse": 12,
      "flight_date": "2026-10-30",
      "remark": "国际备注",
      "rate": 8.33,
      "freight_method": "2",
      "freight": 1000,
      "lading_fee": 50,
      "split_fee": 20,
      "subtotal": 1872
    },
    "customs": {
      "agent": "报关代理",
      "buy_order_fee": 260,
      "document_fee": 130,
      "customs_fee": 650,
      "subtotal": 650
    },
    "ground": {
      "rate": 0.12,
      "freight": 14.4,
      "tc_rate": 0.15,
      "tc_fee": 18,
      "pickup_fee": 0,
      "subtotal": 32.4
    },
    "trucking": {
      "flight_doc_no": "ROAD-001",
      "origin_city": "广州",
      "destination_city": "深圳",
      "weight": 120,
      "unit_price": 2,
      "freight": 240,
      "doc_fee": 10,
      "subtotal": 250
    },
    "dom_air": {
      "volume": 1.234,
      "rate": 2.5,
      "freight_method": "2",
      "freight": 300,
      "subtotal": 300
    },
    "pay_total": 3104.4
  },
  "customer_tags": [],
  "expense_tags": []
}
```

保存成功响应（列表/详情/暂存/作废也使用相同data结构，status及msg按操作变化）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "create_time": "2026-10-30 09:00:00",
    "internal_doc_id": "QF-20261030-001",
    "warehouse_entry_date": "2026-10-30",
    "customer_name": "示例客户",
    "origin_destination": "CAN-NRT",
    "customs_declaration": "1买单+3单证",
    "bill_of_lading": "1-1",
    "flight_date": "2026-10-31",
    "flight_no": "CZ385",
    "flight_doc_no": "784-12345678",
    "pieces": 10,
    "actual_weight": 100.0,
    "chargeable_weight": 120.0,
    "volume": 1.234,
    "first_leg_weight": null,
    "agent": "示例代理",
    "remark": "委托备注",
    "status": 1,
    "editable": true,
    "created_at": "2026-10-30T09:00:00+08:00",
    "updated_at": "2026-10-30T09:00:00+08:00",
    "creator_id": "99",
    "receivables": {
      "unit_price": 26.67,
      "freight_method": "2",
      "freight": 3200.0,
      "receivable_fuel_fee": 65.0,
      "lading_info_fee": 50.0,
      "split_offset_telex_fee": 20.0,
      "customs_fee": 750.0,
      "continuation_sheet_fee": null,
      "customs_inspection_fee": null,
      "magnetic_security_fee": null,
      "tc_express_fee": 36.0,
      "warehouse_ground_fee": 24.0,
      "doc_make_fee": null,
      "doc_split_fee": null,
      "skid_fee": null,
      "pallet_packing_fee": null,
      "probe_fee": null,
      "consumables_fee": null,
      "first_leg_fee": null,
      "total": 4095.0,
      "buy_order_fee": 300.0,
      "document_fee": 150.0,
      "fuel_rate": 0.65,
      "fuel_weight_method": "1",
      "tc_rate": 0.3,
      "front_warehouse_rate": 0.2,
      "remark": "应收单独备注"
    },
    "payables": {
      "intl_air": {
        "subtotal": 1872.0,
        "outsource_unit": "国际代理",
        "origin": null,
        "destination": null,
        "flight_doc_no": "999-00000001",
        "flight_no": null,
        "flight_date": "2026-10-30",
        "pieces": null,
        "weight": 105.0,
        "volume": null,
        "chargeable_weight": null,
        "rate": 8.33,
        "freight_method": "2",
        "freight": 1000.0,
        "lading_fee": 50.0,
        "split_fee": 20.0,
        "borrow_magnetic_fuel_pickup_fee": 60.0,
        "tc_network_disposal_fee": 30.0,
        "customs_fee": 700.0,
        "continuation_sheet_fee": null,
        "consumables_fee": null,
        "front_warehouse": 12.0,
        "other_fee": null,
        "remark": "国际备注",
        "buy_order_fee": 280.0,
        "document_fee": 140.0,
        "fuel_rate": 0.5,
        "fuel_weight_method": "2",
        "tc_rate": 0.25,
        "front_warehouse_rate": 0.1
      },
      "trucking": {
        "subtotal": 250.0,
        "date": null,
        "outsource_unit": null,
        "pieces": null,
        "weight": 120.0,
        "volume": null,
        "unit_price": 2.0,
        "freight": 240.0,
        "doc_fee": 10.0,
        "other_fee": null,
        "remark": null,
        "flight_doc_no": "ROAD-001",
        "origin_city": "广州",
        "destination_city": "深圳"
      },
      "dom_air": {
        "subtotal": 300.0,
        "date": null,
        "outsource_unit": null,
        "origin": null,
        "destination": null,
        "airline": null,
        "airline_unit": null,
        "flight_doc_no": null,
        "flight_no": null,
        "flight_date": null,
        "pieces": null,
        "weight": null,
        "chargeable_weight": null,
        "rate": 2.5,
        "freight_method": "2",
        "freight": 300.0,
        "other_fee": null,
        "remark": null,
        "volume": 1.234
      },
      "customs": {
        "subtotal": 650.0,
        "date": null,
        "agent": "报关代理",
        "customs_fee": 650.0,
        "continuation_sheet_fee": null,
        "inspection_delete_fee": null,
        "other_fee": null,
        "remark": null,
        "buy_order_fee": 260.0,
        "document_fee": 130.0
      },
      "ground": {
        "subtotal": 32.4,
        "date": null,
        "outsource_unit": null,
        "chargeable_weight": null,
        "rate": 0.12,
        "freight": 14.4,
        "tc_fee": 18.0,
        "pickup_fee": 0.0,
        "lading_express_fee": null,
        "security_customs_fee": null,
        "pallet_exit_fee": null,
        "other_fee": null,
        "remark": null,
        "tc_rate": 0.15
      },
      "pay_total": 3104.4
    },
    "customer_tags": [],
    "expense_tags": []
  },
  "msg": "委托信息创建成功"
}
```

`POST /consignments/draft` 和 `PUT /{id}/draft` 成功时 data结构相同，`status=0`，msg为“委托信息暂存成功”；
PUT保存成功msg为“委托信息更新成功”。GET详情msg为“查询成功”；GET模板或PUT模板的data为相同业务结构，
模板没有creator_id，历史兼容字段status仍按原接口为1，它不表示任何列表单据已提交。作废成功status=2，msg为“委托信息作废成功”。

GET列表示例 `GET /api/v1/customer-service/consignments?status=1&page=1&pageSize=10`：
data为 `{ "items": [S], "total": 1, "page": 1, "pageSize": 10 }`，其中每个S为上面的完整data对象，msg为“查询成功”。
GET单据没有请求体；查询参数和此前相同。模板不存在时为 `{ "code":0, "data":null, "msg":"暂无委托信息登记数据" }`。

##### 23.11.7 费用完整请求与响应示例（C）

以下为 `POST /api/v1/cost-service/consignments` 的请求；POST暂存、PUT保存、PUT暂存、PUT登记模板共用同样结构，PUT可只传变更字段：

```json
{
  "consignor_info": {
    "create_time": "2026-10-30 09:00:00",
    "internal_doc_id": "QF-20261030-001",
    "warehouse_entry_date": "2026-10-30",
    "customer_name": "示例客户",
    "origin_destination": "CAN-NRT",
    "customs_declaration": "1买单+3单证",
    "bill_of_lading": "1-1",
    "flight_date": "2026-10-31",
    "flight_no": "CZ385",
    "flight_doc_no": "784-12345678",
    "pieces": 10,
    "actual_weight": 100,
    "chargeable_weight": 120,
    "volume": 1.234,
    "first_leg_weight": null,
    "agent": "示例代理",
    "remark": "委托备注"
  },
  "receivables": {
    "buy_order_fee": 300,
    "document_fee": 150,
    "customs_fee": 750,
    "fuel_rate": 0.65,
    "fuel_weight_method": "1",
    "receivable_fuel_fee": 65,
    "tc_rate": 0.3,
    "tc_express_fee": 36,
    "front_warehouse_rate": 0.2,
    "warehouse_ground_fee": 24,
    "remark": "应收单独备注",
    "unit_price": 26.67,
    "freight_method": "2",
    "freight": 3200,
    "lading_info_fee": 50,
    "split_offset_telex_fee": 20,
    "total": 4095
  },
  "payables": {
    "intl_air": {
      "outsource_unit": "国际代理",
      "weight": 105,
      "flight_doc_no": "999-00000001",
      "buy_order_fee": 280,
      "document_fee": 140,
      "customs_fee": 700,
      "fuel_rate": 0.5,
      "fuel_weight_method": "2",
      "borrow_magnetic_fuel_pickup_fee": 60,
      "tc_rate": 0.25,
      "tc_network_disposal_fee": 30,
      "front_warehouse_rate": 0.1,
      "front_warehouse": 12,
      "flight_date": "2026-10-30",
      "remark": "国际备注",
      "rate": 8.33,
      "freight_method": "2",
      "freight": 1000,
      "lading_fee": 50,
      "split_fee": 20,
      "subtotal": 1872
    },
    "customs": {
      "agent": "报关代理",
      "buy_order_fee": 260,
      "document_fee": 130,
      "customs_fee": 650,
      "subtotal": 650
    },
    "ground": {
      "rate": 0.12,
      "freight": 14.4,
      "tc_rate": 0.15,
      "tc_fee": 18,
      "pickup_fee": 0,
      "subtotal": 32.4
    },
    "trucking": {
      "flight_doc_no": "ROAD-001",
      "origin_city": "广州",
      "destination_city": "深圳",
      "weight": 120,
      "unit_price": 2,
      "freight": 240,
      "doc_fee": 10,
      "subtotal": 250
    },
    "dom_air": {
      "volume": 1.234,
      "rate": 2.5,
      "freight_method": "2",
      "freight": 300,
      "subtotal": 300
    },
    "pay_total": 3104.4
  },
  "discount_info": {
    "discount_person": "示例折让人",
    "discount_rate": 0,
    "discount_fee": 0
  },
  "sales_commission": {
    "salesperson": "",
    "commission_amount": 0
  },
  "operating_info": {
    "profit": 990.6,
    "profit_margin": 24.19
  },
  "expense_tags": [],
  "customer_tags": []
}
```

保存成功响应（GET模板、详情、列表条目及各写入接口共用这个data结构）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 1,
    "consignor_info": {
      "create_time": "2026-10-30 09:00:00",
      "internal_doc_id": "QF-20261030-001",
      "warehouse_entry_date": "2026-10-30",
      "customer_name": "示例客户",
      "origin_destination": "CAN-NRT",
      "customs_declaration": "1买单+3单证",
      "bill_of_lading": "1-1",
      "flight_date": "2026-10-31",
      "flight_no": "CZ385",
      "flight_doc_no": "784-12345678",
      "pieces": 10,
      "actual_weight": 100.0,
      "chargeable_weight": 120.0,
      "volume": 1.234,
      "first_leg_weight": null,
      "agent": "示例代理",
      "remark": "委托备注"
    },
    "receivables": {
      "unit_price": 26.67,
      "freight_method": "2",
      "freight": 3200.0,
      "receivable_fuel_fee": 65.0,
      "lading_info_fee": 50.0,
      "split_offset_telex_fee": 20.0,
      "customs_fee": 750.0,
      "continuation_sheet_fee": null,
      "customs_inspection_fee": null,
      "magnetic_security_fee": null,
      "tc_express_fee": 36.0,
      "warehouse_ground_fee": 24.0,
      "doc_make_fee": null,
      "doc_split_fee": null,
      "skid_fee": null,
      "pallet_packing_fee": null,
      "probe_fee": null,
      "consumables_fee": null,
      "first_leg_fee": null,
      "total": 4095.0,
      "buy_order_fee": 300.0,
      "document_fee": 150.0,
      "fuel_rate": 0.65,
      "fuel_weight_method": "1",
      "tc_rate": 0.3,
      "front_warehouse_rate": 0.2,
      "remark": "应收单独备注"
    },
    "payables": {
      "intl_air": {
        "subtotal": 1872.0,
        "outsource_unit": "国际代理",
        "origin": "",
        "destination": "",
        "flight_doc_no": "999-00000001",
        "flight_no": "",
        "flight_date": "2026-10-30",
        "pieces": null,
        "weight": 105.0,
        "volume": null,
        "chargeable_weight": null,
        "rate": 8.33,
        "freight_method": "2",
        "freight": 1000.0,
        "lading_fee": 50.0,
        "split_fee": 20.0,
        "borrow_magnetic_fuel_pickup_fee": 60.0,
        "tc_network_disposal_fee": 30.0,
        "customs_fee": 700.0,
        "continuation_sheet_fee": null,
        "consumables_fee": null,
        "front_warehouse": 12.0,
        "other_fee": null,
        "remark": "国际备注",
        "buy_order_fee": 280.0,
        "document_fee": 140.0,
        "fuel_rate": 0.5,
        "fuel_weight_method": "2",
        "tc_rate": 0.25,
        "front_warehouse_rate": 0.1
      },
      "trucking": {
        "subtotal": 250.0,
        "date": null,
        "outsource_unit": "",
        "pieces": null,
        "weight": 120.0,
        "volume": null,
        "unit_price": 2.0,
        "freight": 240.0,
        "doc_fee": 10.0,
        "other_fee": null,
        "remark": "",
        "flight_doc_no": "ROAD-001",
        "origin_city": "广州",
        "destination_city": "深圳"
      },
      "dom_air": {
        "subtotal": 300.0,
        "date": null,
        "outsource_unit": "",
        "origin": "",
        "destination": "",
        "airline": "",
        "airline_unit": "",
        "flight_doc_no": "",
        "flight_no": "",
        "flight_date": null,
        "pieces": null,
        "weight": null,
        "chargeable_weight": null,
        "rate": 2.5,
        "freight_method": "2",
        "freight": 300.0,
        "other_fee": null,
        "remark": "",
        "volume": 1.234
      },
      "customs": {
        "subtotal": 650.0,
        "date": null,
        "agent": "报关代理",
        "customs_fee": 650.0,
        "continuation_sheet_fee": null,
        "inspection_delete_fee": null,
        "other_fee": null,
        "remark": "",
        "buy_order_fee": 260.0,
        "document_fee": 130.0
      },
      "ground": {
        "subtotal": 32.4,
        "date": null,
        "outsource_unit": "",
        "chargeable_weight": null,
        "rate": 0.12,
        "freight": 14.4,
        "tc_fee": 18.0,
        "pickup_fee": 0.0,
        "lading_express_fee": null,
        "security_customs_fee": null,
        "pallet_exit_fee": null,
        "other_fee": null,
        "remark": "",
        "tc_rate": 0.15
      },
      "pay_total": 3104.4
    },
    "discount_info": {
      "discount_person": "示例折让人",
      "discount_rate": 0.0,
      "discount_fee": 0.0
    },
    "sales_commission": {
      "salesperson": "",
      "commission_percentage": null,
      "commission_amount": 0.0
    },
    "operating_info": {
      "profit": 990.6,
      "profit_margin": 24.19
    },
    "created_at": "2026-10-30T10:00:00+08:00",
    "updated_at": "2026-10-30T10:00:00+08:00",
    "creator_id": "99",
    "expense_tags": [],
    "customer_tags": []
  },
  "msg": "单据信息创建成功"
}
```

POST暂存/PUT暂存成功时status=0，msg为“单据信息暂存成功”；PUT保存status=1，msg为“单据信息更新成功”；
作废status=2，msg为“费用信息作废成功”；GET详情msg为“查询成功”。
GET列表 `GET /api/v1/cost-service/consignments?page=1&pageSize=10` 返回
`{ "code":0, "data":{ "items":[C], "total":1, "page":1, "pageSize":10 }, "msg":"查询成功" }`，C为上面的完整data对象。
唯一模板没有creator_id，仍兼容返回status=1；模板不存在时data=null。

##### 23.11.8 错误响应和前端状态处理

对费用保存提交后已锁定的客服单据（editable=false）保存或暂存：HTTP409，无论提交顶层字段、财务分组或空对象均拒绝，不写入操作记录、不改变两台数据。客服仅自身已提交（status=1）但editable=true时允许重复保存。

```json
{
  "code": 409,
  "data": null,
  "msg": "费用登记台已保存提交，客服委托信息不能修改或暂存，请在费用登记台维护"
}
```

已作废客服单据保存/暂存：HTTP409，msg为“已作废的委托信息不能暂存或保存”；非法燃油取重编码、数值字段空字符串等由请求Schema校验，返回HTTP422。
鉴权401、停用账号403、非法ID400、记录不存在404沿用统一错误格式。

##### 23.11.9 Excel导出契约（2026-11-09更新）

两个现有导出接口仅调整下载文件的表头、列顺序与取值范围，不新增路由。2026-11-01改为单行表头；2026-11-02两台汽运分组补充“运费计算方式”；2026-11-09委托信息区在进仓日期后恢复“航班日期”；2026-11-11应收耗材费后增加“一程费用”，当前契约如下。

| 方法 | 完整接口路径 | 总列数 | 表头行 | 首条数据行 |
|---|---|---|---|---|
| POST | `/api/v1/customer-service/consignments/export-excel` | 94（A至CP） | 第1行 | 第2行 |
| POST | `/api/v1/cost-service/consignments/export-excel` | 118（A至DN） | 第1行 | 第2行 |

**请求**：沿用当前登录认证（`Authorization: Bearer <token>`），`Content-Type: application/json`。两台相同：

```json
{"ids":["358000000000000001","358000000000000002"]}
```

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `ids` | string[] | 是 | 选中的单据主键，前端以数字字符串传递，至少一项；不是内部单据ID。仅导出本台匹配记录，重复ID不会重复输出；不存在的ID忽略。排序不采用请求数组顺序。 |

**成功返回**：HTTP 200，xlsx文件二进制，**没有JSON的code/data/msg包裹**。响应头示例：

```http
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=consignment_export_20261101100000.xlsx
Access-Control-Expose-Headers: Content-Disposition
```

费用文件名示例为 `cost_consignment_export_20261101100000.xlsx`；实际时间取服务端生成时间。前端继续按blob下载，并先检查HTTP状态和Content-Type。

**文件规则**：

- 两台均第1列“序号”、第2列“状态”。序号按最终导出结果从1连续编号，状态读取本台单据自身的status：0=未提交、1=已提交、2=作废。
- 仅一行表头，无分组标题行、合并单元格或空白占位列，客户表格中的空白项全部忽略。下方表头文字及顺序为完整契约，重复名称按所在列区分。
- 客服排序仍为制单时间 `create_time` 倒序；费用仍按货主航班日期 `consignor_info.flight_date` 升序，空日期最后，同日期按主键ID升序。委托航班日期在第8列（H）展示，费用排序继续使用该字段。
- 客服财务列读取客服自身财务快照；费用列读取费用自身保存值。标签不增加列，也不裁剪数据。只导出新表头列出的字段：内部单据ID、制单时间、基础代理等不再进入Excel；未列出的费率、取重方式等字段仍按原接口保存和查询。
- 金额、重量、体积、件数、费率均为数值（含0），null/未填写为空单元格；日期显示YYYY-MM-DD。“提单”按23.2规则转中文，未知值原样保留。
- 费用第18列应收“运费计算方式”继续转换1=实际重量、2=计费重量，未知值原样保留。两台新增汽运“运费计算方式”：客服第79列（CA），费用第89列（CK），均读取 `payables.trucking.freight_method` 原样输出字符串，不转换1/2，不推断“计费重/体积重”；null或空字符串为空单元格。费用该列位于汽运单价与运费之间，客服位于汽运体积与制单费之间，后续列顺延1列。两台仍不导出燃油取重方式及国际/国内空运的运费计算方式。
- 费用第36列（AJ）和第115列（DK）均为“应收合计”，都读取 `receivables.total`，按客户模板保留两次。五个“应付小计”依次位于第59（BG）、67（BO）、79（CA）、94（CP）、109（DE）列，分别来自国际空运、报关、地面操作、汽运、国内空运的subtotal。第116列“应付合计”读取 `payables.pay_total`。
- 汽运“计费重量”读取 `payables.trucking.weight`；地面操作“前置仓费”读取 `payables.ground.freight`、“提单费”读取 `payables.ground.lading_express_fee`；国际空运“燃油费”读取 `borrow_magnetic_fuel_pickup_fee`、“TC费”读取 `tc_network_disposal_fee`，不新增同义字段。
- 所有运费、报关费、小计、总计、利润、利润率直接使用已保存值，不重算、不写Excel计算公式；修改导出格式不会修改业务记录、提交状态或操作记录。
- 没有匹配记录时仍成功返回完整第1行表头，不生成空白数据行。已有暂存、提交锁定、两台同步及标签覆盖逻辑不变。导出布局调整本身无需额外迁移；汽运新增字段的存储列仍需按23.15执行数据库迁移。

**失败响应**：沿用原校验逻辑。`ids`缺省、类型不合法返回422；`ids=[]`客服在Schema校验返回422、费用返回400；非数字字符串如 `"abc"` 返回400；登录/权限失败沿用认证规则。失败返回JSON，前端不能当作Excel保存。例如：

```json
{"code":400,"data":null,"msg":"ID 'abc' 格式无效"}
```

**客服完整列顺序（94列）**：路径均相对客服详情 `data`。序号由导出生成。

| 列号（1起） | Excel列 | 表头原文 | 对应详情data中的字段 / 来源 |
|---|---|---|---|
| 1 | A | 序号 | 按最终导出顺序从1连续生成 |
| 2 | B | 状态 | `status` |
| 3 | C | 进仓日期 | `warehouse_entry_date` |
| 4 | D | 客户名称 | `customer_name` |
| 5 | E | 始发站-目的站 | `origin_destination` |
| 6 | F | 报关 | `customs_declaration` |
| 7 | G | 提单 | `bill_of_lading` |
| 8 | H | 航班日期 | `flight_date` |
| 9 | I | 航班号 | `flight_no` |
| 10 | J | 主单号 | `flight_doc_no` |
| 11 | K | 件数 | `pieces` |
| 12 | L | 实际重量 | `actual_weight` |
| 13 | M | 计费重量 | `chargeable_weight` |
| 14 | N | 体积 | `volume` |
| 15 | O | 一程重量 | `first_leg_weight` |
| 16 | P | 备注 | `remark` |
| 17 | Q | 应收提单费/信息录入费 | `receivables.lading_info_fee` |
| 18 | R | 应收分单费 电报费/底账费 | `receivables.split_offset_telex_fee` |
| 19 | S | 应收报关费 | `receivables.customs_fee` |
| 20 | T | 应收续页费 | `receivables.continuation_sheet_fee` |
| 21 | U | 应收海关查验费 | `receivables.customs_inspection_fee` |
| 22 | V | 应收磁检费/安检费 | `receivables.magnetic_security_fee` |
| 23 | W | 应收燃油费 | `receivables.receivable_fuel_fee` |
| 24 | X | 应收TC费 | `receivables.tc_express_fee` |
| 25 | Y | 应收前置仓费 | `receivables.warehouse_ground_fee` |
| 26 | Z | 应收制单费 | `receivables.doc_make_fee` |
| 27 | AA | 应收制单分单费 | `receivables.doc_split_fee` |
| 28 | AB | 应收垫板费 | `receivables.skid_fee` |
| 29 | AC | 应收打板/装箱费 | `receivables.pallet_packing_fee` |
| 30 | AD | 应收探板费 | `receivables.probe_fee` |
| 31 | AE | 应收耗材费 | `receivables.consumables_fee` |
| 32 | AF | 一程费用 | `receivables.first_leg_fee` |
| 33 | AG | 国际空运代理名称 | `payables.intl_air.outsource_unit` |
| 34 | AH | 始发站 | `payables.intl_air.origin` |
| 35 | AI | 到达站 | `payables.intl_air.destination` |
| 36 | AJ | 主单号 | `payables.intl_air.flight_doc_no` |
| 37 | AK | 航班号 | `payables.intl_air.flight_no` |
| 38 | AL | 航班日期 | `payables.intl_air.flight_date` |
| 39 | AM | 件数 | `payables.intl_air.pieces` |
| 40 | AN | 实际重量 | `payables.intl_air.weight` |
| 41 | AO | 体积 | `payables.intl_air.volume` |
| 42 | AP | 计费重量 | `payables.intl_air.chargeable_weight` |
| 43 | AQ | 提单费 | `payables.intl_air.lading_fee` |
| 44 | AR | 分单 | `payables.intl_air.split_fee` |
| 45 | AS | 燃油费 | `payables.intl_air.borrow_magnetic_fuel_pickup_fee` |
| 46 | AT | TC费 | `payables.intl_air.tc_network_disposal_fee` |
| 47 | AU | 报关费 | `payables.intl_air.customs_fee` |
| 48 | AV | 续页费 | `payables.intl_air.continuation_sheet_fee` |
| 49 | AW | 耗材费 | `payables.intl_air.consumables_fee` |
| 50 | AX | 前置仓费 | `payables.intl_air.front_warehouse` |
| 51 | AY | 其他费用 | `payables.intl_air.other_fee` |
| 52 | AZ | 备注 | `payables.intl_air.remark` |
| 53 | BA | 报关代理名称 | `payables.customs.agent` |
| 54 | BB | 报关日期 | `payables.customs.date` |
| 55 | BC | 报关费 | `payables.customs.customs_fee` |
| 56 | BD | 续页费 | `payables.customs.continuation_sheet_fee` |
| 57 | BE | 查验费/删单费 | `payables.customs.inspection_delete_fee` |
| 58 | BF | 其他费用 | `payables.customs.other_fee` |
| 59 | BG | 备注 | `payables.customs.remark` |
| 60 | BH | 地面操作代理名称 | `payables.ground.outsource_unit` |
| 61 | BI | 操作日期 | `payables.ground.date` |
| 62 | BJ | 计费重量 | `payables.ground.chargeable_weight` |
| 63 | BK | 前置仓费 | `payables.ground.freight` |
| 64 | BL | TC费 | `payables.ground.tc_fee` |
| 65 | BM | 提货费 | `payables.ground.pickup_fee` |
| 66 | BN | 提单费 | `payables.ground.lading_express_fee` |
| 67 | BO | 安检费/报关费 | `payables.ground.security_customs_fee` |
| 68 | BP | 打板费/退场费 | `payables.ground.pallet_exit_fee` |
| 69 | BQ | 其他费用 | `payables.ground.other_fee` |
| 70 | BR | 备注 | `payables.ground.remark` |
| 71 | BS | 汽运代理名称 | `payables.trucking.outsource_unit` |
| 72 | BT | 托运日期 | `payables.trucking.date` |
| 73 | BU | 主单号 | `payables.trucking.flight_doc_no` |
| 74 | BV | 始发城市 | `payables.trucking.origin_city` |
| 75 | BW | 目的城市 | `payables.trucking.destination_city` |
| 76 | BX | 件数 | `payables.trucking.pieces` |
| 77 | BY | 计费重量 | `payables.trucking.weight` |
| 78 | BZ | 体积 | `payables.trucking.volume` |
| 79 | CA | 运费计算方式 | `payables.trucking.freight_method` |
| 80 | CB | 制单费 | `payables.trucking.doc_fee` |
| 81 | CC | 其他费用 | `payables.trucking.other_fee` |
| 82 | CD | 备注 | `payables.trucking.remark` |
| 83 | CE | 国内空运代理名称 | `payables.dom_air.outsource_unit` |
| 84 | CF | 始发站 | `payables.dom_air.origin` |
| 85 | CG | 到达站 | `payables.dom_air.destination` |
| 86 | CH | 主单号 | `payables.dom_air.flight_doc_no` |
| 87 | CI | 航班号 | `payables.dom_air.flight_no` |
| 88 | CJ | 航班日期 | `payables.dom_air.flight_date` |
| 89 | CK | 件数 | `payables.dom_air.pieces` |
| 90 | CL | 实际重量 | `payables.dom_air.weight` |
| 91 | CM | 计费重量 | `payables.dom_air.chargeable_weight` |
| 92 | CN | 体积 | `payables.dom_air.volume` |
| 93 | CO | 其他费用 | `payables.dom_air.other_fee` |
| 94 | CP | 备注 | `payables.dom_air.remark` |

**费用完整列顺序（118列）**：路径均相对费用详情 `data`。重复表头对应的分组、列号见下表，勿按表头名称去重。

| 列号（1起） | Excel列 | 表头原文 | 对应详情data中的字段 / 来源 |
|---|---|---|---|
| 1 | A | 序号 | 按最终导出顺序从1连续生成 |
| 2 | B | 状态 | `status` |
| 3 | C | 进仓日期 | `consignor_info.warehouse_entry_date` |
| 4 | D | 客户名称 | `consignor_info.customer_name` |
| 5 | E | 始发站-目的站 | `consignor_info.origin_destination` |
| 6 | F | 报关 | `consignor_info.customs_declaration` |
| 7 | G | 提单 | `consignor_info.bill_of_lading` |
| 8 | H | 航班日期 | `consignor_info.flight_date` |
| 9 | I | 航班号 | `consignor_info.flight_no` |
| 10 | J | 主单号 | `consignor_info.flight_doc_no` |
| 11 | K | 件数 | `consignor_info.pieces` |
| 12 | L | 实际重量 | `consignor_info.actual_weight` |
| 13 | M | 计费重量 | `consignor_info.chargeable_weight` |
| 14 | N | 体积 | `consignor_info.volume` |
| 15 | O | 一程重量 | `consignor_info.first_leg_weight` |
| 16 | P | 备注 | `consignor_info.remark` |
| 17 | Q | 运费费率 | `receivables.unit_price` |
| 18 | R | 运费计算方式 | `receivables.freight_method` |
| 19 | S | 运费 | `receivables.freight` |
| 20 | T | 应收提单费/信息录入费 | `receivables.lading_info_fee` |
| 21 | U | 应收分单费 电报费/底账费 | `receivables.split_offset_telex_fee` |
| 22 | V | 应收报关费 | `receivables.customs_fee` |
| 23 | W | 应收续页费 | `receivables.continuation_sheet_fee` |
| 24 | X | 应收海关查验费 | `receivables.customs_inspection_fee` |
| 25 | Y | 应收磁检费/安检费 | `receivables.magnetic_security_fee` |
| 26 | Z | 应收燃油费 | `receivables.receivable_fuel_fee` |
| 27 | AA | 应收TC费 | `receivables.tc_express_fee` |
| 28 | AB | 应收前置仓费 | `receivables.warehouse_ground_fee` |
| 29 | AC | 应收制单费 | `receivables.doc_make_fee` |
| 30 | AD | 应收制单分单费 | `receivables.doc_split_fee` |
| 31 | AE | 应收垫板费 | `receivables.skid_fee` |
| 32 | AF | 应收打板/装箱费 | `receivables.pallet_packing_fee` |
| 33 | AG | 应收探板费 | `receivables.probe_fee` |
| 34 | AH | 应收耗材费 | `receivables.consumables_fee` |
| 35 | AI | 一程费用 | `receivables.first_leg_fee` |
| 36 | AJ | 应收合计 | `receivables.total` |
| 37 | AK | 国际空运代理名称 | `payables.intl_air.outsource_unit` |
| 38 | AL | 始发站 | `payables.intl_air.origin` |
| 39 | AM | 到达站 | `payables.intl_air.destination` |
| 40 | AN | 主单号 | `payables.intl_air.flight_doc_no` |
| 41 | AO | 航班号 | `payables.intl_air.flight_no` |
| 42 | AP | 航班日期 | `payables.intl_air.flight_date` |
| 43 | AQ | 件数 | `payables.intl_air.pieces` |
| 44 | AR | 实际重量 | `payables.intl_air.weight` |
| 45 | AS | 体积 | `payables.intl_air.volume` |
| 46 | AT | 计费重量 | `payables.intl_air.chargeable_weight` |
| 47 | AU | 提单费 | `payables.intl_air.lading_fee` |
| 48 | AV | 单价 | `payables.intl_air.rate` |
| 49 | AW | 运费 | `payables.intl_air.freight` |
| 50 | AX | 分单 | `payables.intl_air.split_fee` |
| 51 | AY | 燃油费 | `payables.intl_air.borrow_magnetic_fuel_pickup_fee` |
| 52 | AZ | TC费 | `payables.intl_air.tc_network_disposal_fee` |
| 53 | BA | 报关费 | `payables.intl_air.customs_fee` |
| 54 | BB | 续页费 | `payables.intl_air.continuation_sheet_fee` |
| 55 | BC | 耗材费 | `payables.intl_air.consumables_fee` |
| 56 | BD | 前置仓费 | `payables.intl_air.front_warehouse` |
| 57 | BE | 其他费用 | `payables.intl_air.other_fee` |
| 58 | BF | 备注 | `payables.intl_air.remark` |
| 59 | BG | 应付小计 | `payables.intl_air.subtotal` |
| 60 | BH | 报关代理名称 | `payables.customs.agent` |
| 61 | BI | 报关日期 | `payables.customs.date` |
| 62 | BJ | 报关费 | `payables.customs.customs_fee` |
| 63 | BK | 续页费 | `payables.customs.continuation_sheet_fee` |
| 64 | BL | 查验费/删单费 | `payables.customs.inspection_delete_fee` |
| 65 | BM | 其他费用 | `payables.customs.other_fee` |
| 66 | BN | 备注 | `payables.customs.remark` |
| 67 | BO | 应付小计 | `payables.customs.subtotal` |
| 68 | BP | 地面操作代理名称 | `payables.ground.outsource_unit` |
| 69 | BQ | 操作日期 | `payables.ground.date` |
| 70 | BR | 计费重量 | `payables.ground.chargeable_weight` |
| 71 | BS | 前置仓费 | `payables.ground.freight` |
| 72 | BT | TC费 | `payables.ground.tc_fee` |
| 73 | BU | 提货费 | `payables.ground.pickup_fee` |
| 74 | BV | 提单费 | `payables.ground.lading_express_fee` |
| 75 | BW | 安检费/报关费 | `payables.ground.security_customs_fee` |
| 76 | BX | 打板费/退场费 | `payables.ground.pallet_exit_fee` |
| 77 | BY | 其他费用 | `payables.ground.other_fee` |
| 78 | BZ | 备注 | `payables.ground.remark` |
| 79 | CA | 应付小计 | `payables.ground.subtotal` |
| 80 | CB | 汽运代理名称 | `payables.trucking.outsource_unit` |
| 81 | CC | 托运日期 | `payables.trucking.date` |
| 82 | CD | 主单号 | `payables.trucking.flight_doc_no` |
| 83 | CE | 始发城市 | `payables.trucking.origin_city` |
| 84 | CF | 目的城市 | `payables.trucking.destination_city` |
| 85 | CG | 件数 | `payables.trucking.pieces` |
| 86 | CH | 计费重量 | `payables.trucking.weight` |
| 87 | CI | 体积 | `payables.trucking.volume` |
| 88 | CJ | 单价 | `payables.trucking.unit_price` |
| 89 | CK | 运费计算方式 | `payables.trucking.freight_method` |
| 90 | CL | 运费 | `payables.trucking.freight` |
| 91 | CM | 制单费 | `payables.trucking.doc_fee` |
| 92 | CN | 其他费用 | `payables.trucking.other_fee` |
| 93 | CO | 备注 | `payables.trucking.remark` |
| 94 | CP | 应付小计 | `payables.trucking.subtotal` |
| 95 | CQ | 国内空运代理名称 | `payables.dom_air.outsource_unit` |
| 96 | CR | 始发站 | `payables.dom_air.origin` |
| 97 | CS | 到达站 | `payables.dom_air.destination` |
| 98 | CT | 主单号 | `payables.dom_air.flight_doc_no` |
| 99 | CU | 航班号 | `payables.dom_air.flight_no` |
| 100 | CV | 航班日期 | `payables.dom_air.flight_date` |
| 101 | CW | 件数 | `payables.dom_air.pieces` |
| 102 | CX | 实际重量 | `payables.dom_air.weight` |
| 103 | CY | 计费重量 | `payables.dom_air.chargeable_weight` |
| 104 | CZ | 体积 | `payables.dom_air.volume` |
| 105 | DA | 单价 | `payables.dom_air.rate` |
| 106 | DB | 运费 | `payables.dom_air.freight` |
| 107 | DC | 其他费用 | `payables.dom_air.other_fee` |
| 108 | DD | 备注 | `payables.dom_air.remark` |
| 109 | DE | 应付小计 | `payables.dom_air.subtotal` |
| 110 | DF | 折让人 | `discount_info.discount_person` |
| 111 | DG | 费率 | `discount_info.discount_rate` |
| 112 | DH | 折让费 | `discount_info.discount_fee` |
| 113 | DI | 业务员 | `sales_commission.salesperson` |
| 114 | DJ | 提成金额 | `sales_commission.commission_amount` |
| 115 | DK | 应收合计 | `receivables.total` |
| 116 | DL | 应付合计 | `payables.pay_total` |
| 117 | DM | 利润 | `operating_info.profit` |
| 118 | DN | 利润率% | `operating_info.profit_margin` |

##### 23.11.10 数据库部署与兼容说明

已有数据库须在发布代码前执行 `sql/migration_add_consignment_financial_fields.sql` **一次**：
为客服模板及单据表各新增可空JSON财务快照列；为费用模板及单据表各新增20个可空标量列。
迁移只加列，不清空/回算历史金额，不自动搬运历史费用数据；旧记录新增列为NULL。
全新建表脚本已同步包含这些字段，新库使用建表脚本或ORM初始化后无需重复执行此增量脚本。
本次未连接生产数据库执行迁移，部署时仍需执行。原有status及操作记录表迁移是本功能现有前提，不能遗漏。
旧客户端不传新分组/新字段仍可新增、暂存或提交未提交单据；客服编辑锁定时机已改为费用保存提交成功后，详见23.19。

#### 23.12 两台页面勾选项存储与详情回显（2026-10-30）

本节对应页面右上角的“填写更多数据”勾选框。字段名及英文标识数组已确认：
**两台均支持 `customer_tags` 和 `expense_tags` 两个字段**，请求体及响应 `data` 中都位于第一层级。
customer_tags表示5项选项集合，expense_tags表示7项选项集合，字段名不再限制使用页面；不放入业务子对象。客服提交将两个同名字段流转到费用，费用可独立覆盖；详见23.14。

复用现有新增、保存、暂存及登记模板接口传入标签，无新增独立的标签写入路由。
接口认证、单据状态、操作记录和费用计算规则不变；标签流转按23.14执行，客服editable=false时不能修改标签，editable=true时已保存客服仍可修改标签。

##### 23.12.1 字段类型与勾选框对应值

| 字段 | 请求类型 | 必填 | 响应类型 | 说明 |
|---|---|---|---|---|
| `customer_tags` | string[] / null | 否 | string[] | 客服5个勾选框的选中值，数组最多5项 |
| `expense_tags` | string[] / null | 否 | string[] | 费用7个勾选框的选中值，数组最多7项 |

| 标识值（大小写敏感） | 页面勾选框 | customer_tags | expense_tags |
|---|---|---|---|
| `intl_air` | 国际空运 | 支持 | 支持 |
| `customs` | 报关 | 支持 | 支持 |
| `ground` | 地面操作 | 支持 | 支持 |
| `trucking` | 汽运 | 支持 | 支持 |
| `dom_air` | 国内空运 | 支持 | 支持 |
| `discount_info` | 折让人员 | 不支持 | 支持 |
| `sales_commission` | 业务员 | 不支持 | 支持 |

只提交已勾选项，未出现在数组内的选项即未勾选。全部取消时提交 `[]`。
前端不要发送中文选项名、布尔对象、逗号拼接字符串、数字下标或其他未列出的值。

##### 23.12.2 受影响接口清单

全部路径带 `/api/v1` 前缀，需携带有效 Bearer Token。没有新增必填字段、查询参数或修改现有路由地址。

| 方法 | 路径 | 请求变化 | 响应变化 |
|---|---|---|---|
| GET | `/customer-service/consignment-registration` | 无请求体 | `data.customer_tags`及`data.expense_tags`；模板不存在时仍为data:null |
| PUT | `/customer-service/consignment-registration` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags` |
| POST | `/customer-service/consignments` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=1 |
| POST | `/customer-service/consignments/draft` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=0 |
| PUT | `/customer-service/consignments/{consignment_id}` | 顶层可传customer_tags、expense_tags；仅未提交单据可执行 | `data.customer_tags`及`data.expense_tags`，status=1 |
| PUT | `/customer-service/consignments/{consignment_id}/draft` | 顶层可传customer_tags、expense_tags；仅未提交单据可执行 | `data.customer_tags`及`data.expense_tags`，status=0 |
| GET | `/customer-service/consignments/{consignment_id}` | 无请求体 | **`data.customer_tags`及`data.expense_tags`（详情回显入口）** |
| GET | `/customer-service/consignments` | 查询参数不变 | `data.items[].customer_tags`及`data.items[].expense_tags` |
| PUT | `/customer-service/consignments/{consignment_id}/void` | 无请求体 | `data.customer_tags`及`data.expense_tags`保留原值，status=2 |
| GET | `/cost-service/cost-registration` | 无请求体 | `data.customer_tags`及`data.expense_tags`；模板不存在时仍为data:null |
| PUT | `/cost-service/cost-registration` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags` |
| POST | `/cost-service/consignments` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=1 |
| POST | `/cost-service/consignments/draft` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=0 |
| PUT | `/cost-service/consignments/{consignment_id}` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=1 |
| PUT | `/cost-service/consignments/{consignment_id}/draft` | 顶层可传customer_tags、expense_tags | `data.customer_tags`及`data.expense_tags`，status=0 |
| GET | `/cost-service/consignments/{consignment_id}` | 无请求体 | **`data.customer_tags`及`data.expense_tags`（详情回显入口）** |
| GET | `/cost-service/consignments` | 查询参数不变 | `data.items[].customer_tags`及`data.items[].expense_tags` |
| PUT | `/cost-service/consignments/{consignment_id}/void` | 无请求体 | `data.customer_tags`及`data.expense_tags`保留原值，status=2 |

两台详情data同时返回customer_tags及expense_tags两个数组。
列表每项、保存及暂存响应也返回两个数组，前端可直接复用；唯一登记模板与列表单据仍为独立记录。
路径参数 `consignment_id` 为列表返回的字符串ID。删除、操作记录及Excel导出接口结构不变；标签不增加Excel列，也不用于裁剪导出业务数据。

##### 23.12.3 保存、清空与兼容语义

| 请求中的字段 | 新记录 | 修改已有记录 |
|---|---|---|
| 不传标签字段 | 未保存标签，查询返回[] | 保留原数组 |
| 显式传null | 未保存标签，查询返回[] | 保留原数组 |
| 显式传[] | 保存空数组 | 清空全部勾选 |
| 传合法标识数组 | 保存这些选中项 | 整体替换原数组，不做追加合并 |

重复值在请求校验后按第一次出现的顺序去重，例如 `["ground","intl_air","ground"]` 保存并返回 `["ground","intl_air"]`。
数组长度上限在去重前校验，customer_tags最多5项、expense_tags最多7项。响应保留选项提交顺序。
历史记录数据库为NULL时统一返回 `[]`，不根据已有费用金额推断勾选项，也不默认替用户勾选国际空运。
新增或更新模板不会自动更改任何列表单据的勾选项；前端创建新单据时如需沿用模板，须把模板数组带入新增请求。

标签是页面勾选状态，取消勾选不会删除该业务分组的数据，也不会修改金额、合计或利润。
两台分别持久化两个同名字段：客服暂存不流转，客服提交将已保存的非null数组（含[]）复制到费用；客服未保存的字段不清空费用已有值。费用可分别覆盖或清空两个字段，费用保存不反向改写既有客服标签；费用首次新建客服记录时带入两个字段初值。
费用保存提交后的客服锁定仍适用于两个字段；客服仅保存后可编辑。详情查询读取本台存储值，不在查询时重新覆盖费用选择，也不自动将customer_tags重命名为expense_tags。

##### 23.12.4 客服请求与详情响应示例

新增暂存请求 `POST /api/v1/customer-service/consignments/draft`（还可合并提交23.11列出的任意业务字段）：

```json
{
  "customer_name": "示例客户",
  "customer_tags": [
    "intl_air",
    "customs"
  ],
  "expense_tags": []
}
```

对未提交单据修改勾选项，`PUT /api/v1/customer-service/consignments/358000000000000001/draft`：

```json
{
  "customer_tags": [
    "intl_air",
    "ground",
    "dom_air"
  ],
  "expense_tags": []
}
```

只暂存标签时，未提交的其他委托及费用字段保持原值。PUT保存接口使用相同入参，客服置status=1并同步费用草稿，仍可编辑；费用保存提交才锁定客服。它仍不能当成不改状态或不流转的标签更新接口。

详情查询 `GET /api/v1/customer-service/consignments/358000000000000001`，响应节选（其他完整业务字段同23.11.6）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "customer_tags": [
      "intl_air",
      "ground",
      "dom_air"
    ],
    "status": 0,
    "customer_name": "示例客户",
    "expense_tags": []
  },
  "msg": "查询成功"
}
```

全部取消，向未提交客服单据的暂存接口提交：

```json
{
  "customer_tags": [],
  "expense_tags": []
}
```

##### 23.12.5 费用请求与详情响应示例

费用新增 `POST /api/v1/cost-service/consignments`，或费用暂存新增 `POST /api/v1/cost-service/consignments/draft` 请求示例：

```json
{
  "expense_tags": [
    "intl_air",
    "customs",
    "ground",
    "trucking",
    "dom_air",
    "discount_info",
    "sales_commission"
  ],
  "consignor_info": {
    "customer_name": "示例客户"
  },
  "customer_tags": []
}
```

修改费用勾选项，`PUT /api/v1/cost-service/consignments/358000000000000001/draft` 请求示例：

```json
{
  "expense_tags": [
    "intl_air",
    "discount_info",
    "sales_commission"
  ],
  "customer_tags": []
}
```

`PUT /consignments/{consignment_id}` 的入参结构相同。费用暂存及保存仍分别设status=0及status=1；选择接口时沿用原有页面行为。
`customer_tags`、`expense_tags` 与 `consignor_info`、`payables` 等同级；标签可以和业务字段放在同一次请求中原子保存。

费用详情 `GET /api/v1/cost-service/consignments/358000000000000001` 响应节选（其他完整业务字段同23.11.7）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "expense_tags": [
      "intl_air",
      "discount_info",
      "sales_commission"
    ],
    "status": 0,
    "consignor_info": {
      "customer_name": "示例客户"
    },
    "customer_tags": []
  },
  "msg": "查询成功"
}
```

全部取消提交 `{"expense_tags":[]}`。字段省略或null均不清空，旧记录未保存且没有客服流转值时，两个字段均返回[]。

##### 23.12.6 错误及状态约束

请求中标签不是数组、数组元素类型不对、非法标识、超出5/7项、customer_tags传折让/业务员选项（两台expense_tags均支持这两项），均返回HTTP422并拒绝整次请求，不写入业务或操作记录。
错误响应沿用统一 `{code:422,data:null,msg:参数验证失败信息}`；msg中定位到 `body -> customer_tags` 或 `body -> expense_tags` 及具体错误元素。
合法标签请求仍需通过原有状态校验：客服费用提交锁定后或作废后PUT保存/暂存返回409；费用作废后PUT保存或暂存返回409；不存在的单据返回404。
即使只提交标签或伪造请求status=0，也不能绕过后端锁定。

费用保存提交已锁定客服单据的标签修改失败示例（HTTP409）：

```json
{
  "code": 409,
  "data": null,
  "msg": "费用登记台已保存提交，客服委托信息不能修改或暂存，请在费用登记台维护"
}
```

##### 23.12.7 数据库部署

存量数据库发布代码前执行 `sql/migration_add_consignment_tags.sql` 一次，分别为：

- `consignment_registrations`、`consignment_infos` 增加可空JSON列 `customer_tags`；
- `cost_registrations`、`cost_consignments` 增加可空JSON列 `expense_tags`。

迁移只加列，不覆盖历史业务、状态或费用；历史值为NULL，接口映射为[]。
原增量脚本仅包含每台原先的一个标签列；存量库另需执行 `sql/migration_sync_consignment_tags.sql` 补齐另一标签列及历史客服标签，详见23.14。
两台全新建表SQL及ORM模型已包含每台两个标签列，新库通过建表脚本/ORM初始化后不再执行上述增量加列。
这与23.11的财务字段迁移是两个独立脚本，两项需求同时上线的存量库需要依次执行两个脚本；未在生产库代为执行。


#### 23.13 内部单据ID移至操作记录展示（2026-10-30）

##### 23.13.1 展示范围及原有接口兼容

本次仅调整内部单据ID的展示位置。编号仍由前端生成/提供，后端按原有规则保存、返回和跨台同步，不生成替代编号，不删除已有业务表或登记模板中的编号。
`internal_doc_id` 是业务展示编号，不能代替接口路径、删除、下载请求中的数字字符串主键 `id` / `consignment_id`。

| 场景 | 客服字段路径 | 费用字段路径 | 本次规则 |
|---|---|---|---|
| 新增/暂存新增请求 | `internal_doc_id` | `consignor_info.internal_doc_id` | 保留，string，可选；不传时不自动生成编号 |
| 修改保存/修改暂存请求 | `internal_doc_id` | `consignor_info.internal_doc_id` | 保留；省略或null沿用原编号，字符串按原逻辑保存（包括空字符串）；客服提交后仍禁止修改 |
| 登记模板保存请求 | `internal_doc_id` | `consignor_info.internal_doc_id` | 保留既有保存语义；客服模板为完整保存，不传时可清空，费用模板省略或null保留旧值 |
| 新增、暂存、保存、作废成功响应及详情/模板查询 | `data.internal_doc_id` | `data.consignor_info.internal_doc_id` | 保留原路径，未填写映射为 `""`，前端作为隐藏数据维护 |
| 列表响应 | `data.items[].internal_doc_id` | `data.items[].consignor_info.internal_doc_id` | 保留兼容，前端删除对应列表展示列 |
| 操作记录查询 | `data.internal_doc_id` | `data.internal_doc_id` | 两个入口均新增此顶层字段，供弹窗顶部展示 |
| Excel下载 | 不输出编号表头和编号值 | 不输出编号表头和编号值 | 表格列整体调整，见23.13.4及23.11.9 |

原有请求和回显路径适用于以下接口（均带 `/api/v1` 前缀）：

| 台 | 方法与路径 |
|---|---|
| 客服模板 | `GET /customer-service/consignment-registration`、`PUT /customer-service/consignment-registration` |
| 客服单据 | `POST /customer-service/consignments`、`POST /customer-service/consignments/draft`、`PUT /customer-service/consignments/{consignment_id}`、`PUT /customer-service/consignments/{consignment_id}/draft` |
| 客服查询/作废 | `GET /customer-service/consignments`、`GET /customer-service/consignments/{consignment_id}`、`PUT /customer-service/consignments/{consignment_id}/void` |
| 费用模板 | `GET /cost-service/cost-registration`、`PUT /cost-service/cost-registration` |
| 费用单据 | `POST /cost-service/consignments`、`POST /cost-service/consignments/draft`、`PUT /cost-service/consignments/{consignment_id}`、`PUT /cost-service/consignments/{consignment_id}/draft` |
| 费用查询/作废 | `GET /cost-service/consignments`、`GET /cost-service/consignments/{consignment_id}`、`PUT /cost-service/consignments/{consignment_id}/void` |

前端移除两台编辑区的编号输入控件和列表中的编号列，同时继续维护、传递上述隐藏字段；不要因不渲染控件而丢弃原编号。原有完整业务请求和响应示例见23.11.6、23.11.7，其编号路径继续有效。
例如客服新增/暂存新增可继续传入：

```json
{"internal_doc_id":"YT123456789CN","customer_name":"示例客户"}
```

费用新增/暂存新增的相应请求：

```json
{"consignor_info":{"internal_doc_id":"YT123456789CN","customer_name":"示例客户"}}
```

上述字符串原样保存；保存提交时与单据基础信息一起同步到对端，暂存仍仅保存到来源台。其余状态、金额、标签、删除规则保持各自既有契约。

##### 23.13.2 操作记录查询入参及返回字段

本次没有新增独立查询接口，扩展现有两个GET接口：

- `GET /api/v1/customer-service/consignments/{consignment_id}/operation-logs`
- `GET /api/v1/cost-service/consignments/{consignment_id}/operation-logs`

两接口沿用有效Bearer Token及启用账号校验，无请求体。入参如下：

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `Authorization` | Header | string | 是 | `Bearer <access_token>` |
| `consignment_id` | Path | string | 是 | 列表/详情的数字字符串主键id，正整数且小于9223372036854775808；不是内部单据ID |
| `page` | Query | integer | 否 | 默认1，最小1 |
| `pageSize` | Query | integer | 否 | 默认20，范围1至100 |

新增 `data.internal_doc_id`，类型string，始终返回。现存单据优先读取费用台非空编号，其次客服台非空编号；两台都未保存编号时返回空字符串。
两台单据都已物理删除时，读取此单据最近一条具有非空编号的操作快照；历史单据已删除且无法恢复编号时返回空字符串，不推测或生成历史编号。
编号的查询独立于操作记录分页，即使 `items=[]` 或查询页码超过总页数也返回编号。操作记录每一项的结构保持不变，无需逐条取编号。

请求示例（费用入口只需替换路径中的台名）：

```http
GET /api/v1/customer-service/consignments/358000000000000001/operation-logs?page=1&pageSize=20
Authorization: Bearer <access_token>
```

两入口成功响应结构完全相同：

```json
{
  "code": 0,
  "data": {
    "consignment_id": "358000000000000001",
    "internal_doc_id": "YT123456789CN",
    "total": 1,
    "items": [
      {
        "id": "358000000000000102",
        "consignment_id": "358000000000000001",
        "source": "customer_service",
        "action": "save",
        "operation_name": "货主委托信息保存",
        "operator_id": "358000000000000010",
        "operator_name": "张三",
        "operated_at": "2026-10-30T15:00:00+08:00"
      }
    ],
    "page": 1,
    "pageSize": 20
  },
  "msg": "查询成功"
}
```

现存历史单据还没有操作记录时的完整响应示例：

```json
{
  "code": 0,
  "data": {
    "consignment_id": "358000000000000001",
    "internal_doc_id": "YT123456789CN",
    "total": 0,
    "items": [],
    "page": 1,
    "pageSize": 20
  },
  "msg": "查询成功"
}
```

`internal_doc_id` 为 `""` 时，前端可显示“内部单据ID：未填写”；不影响时间线展示。弹窗顶部按截图展示“内部单据ID：YT123456789CN”。
其余分页字段及items字段逐项说明见23.7；非法主键400、单据和记录均不存在404、非法分页422及认证失败规则均沿用23.7。业务异常仍使用 `{code,data,msg}` 统一包裹。

##### 23.13.3 操作快照与删除追溯

保存、暂存、作废及删除成功时，在原操作记录中同时存储当时的编号快照，与业务写入共用事务。跨台同步不增加重复操作记录，失败请求不留下成功操作。
单个及批量删除均先保留来源单据真实编号，之后即使两台业务数据均被删除，仍可使用原数字字符串id查询历史及编号。批量删除一次读取来源记录的id、状态、编号，无逐条补查。
当前操作记录响应只返回弹窗头部编号，不暴露每次操作的编号变化明细。

##### 23.13.4 Excel下载变化

两个导出接口继续不输出内部单据ID（表头及值均不输出）。2026-11-01客户重新确认完整列顺序后，两台均改为单行表头；按当前含委托航班日期、一程费用及一程重量的布局，客服94列、费用118列，数据从第2行开始，不保留空白占位列。

| 方法与路径（含 `/api/v1` 前缀） | 入参 | 下载结果 |
|---|---|---|
| `POST /api/v1/customer-service/consignments/export-excel` | `{"ids":["358000000000000001"]}`，必填数字字符串数组 | 94列、单行表头、A列序号、B列状态 |
| `POST /api/v1/cost-service/consignments/export-excel` | 同上 | 118列、单行表头、A列序号、B列状态 |

逐列顺序、字段路径、重复表头规则、下载响应示例及校验规则详见23.11.9。仍返回xlsx二进制，下载文件名、排序及中文转换规则延续。前端继续传入隐藏的内部编号，操作记录展示逻辑不受导出变更影响。

##### 23.13.5 数据库迁移及前端联调

已有 `consignment_operation_logs` 表的环境，发布前执行 `sql/migration_add_operation_internal_doc_id.sql` **一次**，新增可空varchar(100)编号快照列，并从仍存在的费用/客服单据回填真实编号。
新建环境执行已更新的 `sql/migration_create_consignment_operation_logs.sql` 或通过ORM建表，已包含此列，不再重复执行增量加列。
四张业务/模板表的 `internal_doc_id` 列继续保留，不删除原编号；历史操作人及时间仍不虚构补录。已删除且没有可恢复编号的旧记录保留NULL，接口映射为空字符串。
本次未连接生产数据库执行迁移。与前两项需求一起发布时，财务字段迁移、勾选项迁移及本节操作快照迁移都需按数据库现状执行。
本仓库为后端项目；前端需自行完成编辑区控件及列表列隐藏、隐藏值继续传入、操作记录弹窗顶部展示的页面改动。后端已提供相应查询字段及下载内容调整。

#### 23.14 两组标签从客服流转至费用，费用可覆盖（2026-10-30）

本节为前端最新确认的标签契约：**客服和费用两台均接受并返回customer_tags、expense_tags，客服提交时两个字段按同名传递至费用，费用可分别覆盖。**
这是对原先“客服仅customer_tags、费用仅expense_tags，互不流转”的明确调整。不是把customer_tags重命名为expense_tags；两个字段各自保留含义与选项范围。
没有新增接口URL，以下JSON字段都在请求体顶层、响应data第一层，列表则在每个items元素第一层。

##### 23.14.1 受影响接口与入参

均需有效Bearer Token；以下路径已包含 `/api/v1` 前缀。GET无请求体，PUT作废无请求体；其余写入接口可在原业务请求中带两个可选标签字段。

| 台 | 方法 | 路径 | 请求/返回变化 |
|---|---|---|---|
| 客服 | GET / PUT | `/api/v1/customer-service/consignment-registration` | 模板PUT接受两个标签；GET/PUT的data返回两个数组，无模板仍为null |
| 客服 | POST | `/api/v1/customer-service/consignments` | 两个标签入参；返回两个数组，status=1，同事务流转费用 |
| 客服 | POST | `/api/v1/customer-service/consignments/draft` | 两个标签入参；返回两个数组，status=0，不流转 |
| 客服 | PUT | `/api/v1/customer-service/consignments/{consignment_id}` | 两个标签入参；仅客服0可用，提交并流转 |
| 客服 | PUT | `/api/v1/customer-service/consignments/{consignment_id}/draft` | 两个标签入参；仅客服0可用，只保存客服 |
| 客服 | GET | `/api/v1/customer-service/consignments/{consignment_id}` | data同时含两个数组 |
| 客服 | GET | `/api/v1/customer-service/consignments` | data.items每项同时含两个数组；筛选/分页参数不变 |
| 客服 | PUT | `/api/v1/customer-service/consignments/{consignment_id}/void` | data保留两个数组，status=2 |
| 费用 | GET / PUT | `/api/v1/cost-service/cost-registration` | 模板PUT接受两个标签；GET/PUT的data返回两个数组，无模板仍为null |
| 费用 | POST | `/api/v1/cost-service/consignments` | 接受及返回两个数组，status=1 |
| 费用 | POST | `/api/v1/cost-service/consignments/draft` | 接受及返回两个数组，status=0 |
| 费用 | PUT | `/api/v1/cost-service/consignments/{consignment_id}` | 接受两个字段覆盖本台值，status=1；不回写既有客服标签 |
| 费用 | PUT | `/api/v1/cost-service/consignments/{consignment_id}/draft` | 接受两个字段覆盖本台值，status=0，不回写客服 |
| 费用 | GET | `/api/v1/cost-service/consignments/{consignment_id}` | data同时含两个数组，读取费用已保存的值 |
| 费用 | GET | `/api/v1/cost-service/consignments` | data.items每项同时含两个数组；筛选/分页参数不变 |
| 费用 | PUT | `/api/v1/cost-service/consignments/{consignment_id}/void` | data保留两个数组，status=2 |

路径consignment_id仍为列表返回的数字字符串id，非internal_doc_id；业务金额字段、操作记录接口和Excel文件结构不变，标签不增加Excel列。

| JSON字段（两台均顶层） | 类型 | 必填 | 取值/含义 |
|---|---|---|---|
| `customer_tags` | string[] / null | 否 | 最多5项：intl_air、customs、ground、trucking、dom_air；表示客服标签集合 |
| `expense_tags` | string[] / null | 否 | 最多7项：上述5项及discount_info、sales_commission；表示费用标签集合 |

intl_air=国际空运，customs=报关，ground=地面操作，trucking=汽运，dom_air=国内空运，discount_info=折让信息，sales_commission=销售提成。
两字段均：省略或null保留原值，[]明确清空，合法数组整体覆盖，去重并保留第一次出现的顺序。数组长度限制仍在去重前校验。
两字段分别校验：即使在费用台，customer_tags也不能传discount_info；即使在客服台，expense_tags也允许discount_info及sales_commission。

##### 23.14.2 流转及覆盖规则

1. 客服暂存只保存本台两组标签，不创建/修改费用台。客服提交时读取本单据已保存的两个数组，复制到同ID费用单据；包含此前草稿保存过的值，不要求最终提交请求重复携带。
2. 每个字段独立复制：数据库非NULL数组（含[]）覆盖费用同名字段；客服一直未保存的NULL字段不清空费用已有值。仅传customer_tags不会自动填充expense_tags，前端如需两个分组均选中，应分别提交。
3. 费用暂存或保存可独立替换两组标签；省略其中一组不修改该组。费用详情、列表读取已存的费用值，不在查询时重新用客服数组覆盖，因此费用覆盖及明确清空均可持续保留。
4. 费用修改标签不反向改写既有客服标签。费用保存仍按旧逻辑同步基本信息和财务快照；只有费用首次创建或补建客服记录时，两个标签作为初值一起带入，之后两台可各自保留值。
5. 客服editable=false锁定、两台status=2作废不可编辑的规则对两个字段都有效。不能通过仅发标签、传空对象或伪造status=0绕过。
6. 唯一登记模板分别存储两个数组，不自动同步对端模板，也不修改列表单据；前端需在新建时把所需模板值带入请求。
7. 同步与业务保存共用事务，不增加标签专用操作记录。标签不参与金额计算，也不因[]删除已填写的财务分组。

##### 23.14.3 客服提交、费用详情及覆盖示例

客服保存新增：`POST /api/v1/customer-service/consignments`（可以同时携带23.11的财务字段）：

```json
{
  "customer_name": "示例客户",
  "customer_tags": ["intl_air", "customs"],
  "expense_tags": ["ground", "discount_info"]
}
```

客服成功响应节选（其余字段仍按23.11.6完整返回）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 1,
    "customer_name": "示例客户",
    "customer_tags": ["intl_air", "customs"],
    "expense_tags": ["ground", "discount_info"]
  },
  "msg": "委托信息创建成功"
}
```

费用详情：`GET /api/v1/cost-service/consignments/358000000000000001`，成功响应节选：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 0,
    "customer_tags": ["intl_air", "customs"],
    "expense_tags": ["ground", "discount_info"],
    "consignor_info": {"customer_name": "示例客户"}
  },
  "msg": "查询成功"
}
```

费用覆盖并暂存：`PUT /api/v1/cost-service/consignments/358000000000000001/draft`：

```json
{
  "customer_tags": ["dom_air"],
  "expense_tags": []
}
```

暂存成功响应节选：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 0,
    "customer_tags": ["dom_air"],
    "expense_tags": [],
    "consignor_info": {"customer_name": "示例客户"}
  },
  "msg": "单据信息暂存成功"
}
```

之后费用GET详情仍返回customer_tags=["dom_air"]、expense_tags=[]；客服GET详情仍是提交时的两个数组。
费用若改用PUT保存接口（去掉/draft），请求同上，返回status=1、msg="单据信息更新成功"，两个字段覆盖结果一致。
只清空费用customer_tags可传 `{"customer_tags":[]}`，此时expense_tags不变；传null不能清空。

##### 23.14.4 错误、历史回填及部署

参数类型/选项/长度错误返回HTTP422，按统一结构 `{code:422,data:null,msg:"参数验证失败..."}` 返回，整次请求不写业务或操作记录。
费用保存提交已锁定客服修改/暂存仍409；作废两台修改/暂存仍409；不存在记录404、非法数字格式id400、鉴权沿用原规则。

已有旧标签列的存量库，发布前执行 **`sql/migration_sync_consignment_tags.sql` 一次**：

- 客服模板、客服单据各加expense_tags；费用模板、费用单据各加customer_tags，均为可空JSON。
- 从同ID已提交/已作废客服单据回填费用NULL（含JSON null）的同名标签，不覆盖费用已经保存的数组（包括[]）。不根据费用金额猜测标签，不把customer_tags转换成expense_tags。
- 回填保留业务updated_at，不新增虚构用户操作，不复制模板，也不从客服未提交草稿回填。
- 原库若连旧标签列都没有，先执行migration_add_consignment_tags.sql，再执行本脚本。全新库使用已更新建表SQL或ORM，不重复执行这些增量加列。

历史费用数据中新加customer_tags为空、客服存在原选择时，迁移会补齐该值，使截图中的老单据也能回显；费用原先expense_tags=[]会保留，不将其误判为“没选择过”。
未执行迁移前不要先发布依赖新列的代码；本次未代为连接或修改生产数据库。


#### 23.15 汽运新增运费计算方式（2026-11-02）

费用登记台“汽运信息”新增可选字段 `payables.trucking.freight_method`，位于汽运单价与运费之间。沿用现有接口，无需新增独立保存路由。字段属于汽运分组，**不是**应收 `receivables.freight_method`，也不是国际/国内空运分组的同名字段，四者分别保存。

##### 23.15.1 字段契约

| 字段路径（请求体 / 响应data） | 类型 | 必填 | 长度 | 说明 |
|---|---|---|---|---|
| `payables.trucking.freight_method` | string / null | 否 | 最多50个字符 | 汽运运费计算方式，前端设置“计费重/体积重”等选项并传入所需字符串；后端不维护枚举、不转换编码、不自动选择或推断该值 |

- 前端可传 `"计费重"`、`"体积重"` 或其约定的字符串编码，例如 `"1"`、`"2"`；后端仅原样保存，**不规定1/2对应哪个选项**。前端提交值和回显值应使用同一套格式。
- 新增未传或显式传null：保存为NULL，返回 `null`；历史未填写记录也返回 `null`，不虚构默认选项。
- 修改时不传叶字段，或 `payables` / `trucking` 分组未传或为null：保留旧值；显式 `{"payables":{"trucking":{"freight_method":null}}}` 清空为NULL，响应返回null。
- 显式传 `""`：保存空字符串，响应返回 `""`。不会将空字符串和null互相转换。
- 非字符串值（如数字、数组、对象）、超过50字符的值返回HTTP422，沿用 `{code,data,msg}` 错误格式，整次请求不修改业务、状态或操作记录。
- 更改计算方式不会自动重算 `unit_price`、`weight`、`volume`、`freight`、`subtotal`、`pay_total`、利润等字段；运费等仍由前端计算并提交。

##### 23.15.2 受影响接口

以下路径均带 `/api/v1` 前缀，沿用有效Bearer Token认证。写入字段路径为 `payables.trucking.freight_method`，单条响应路径为 `data.payables.trucking.freight_method`；列表响应为 `data.items[].payables.trucking.freight_method`，其余字段、分页和错误规范不变。

| 方法 | 接口路径 | 请求与响应变化 |
|---|---|---|
| GET | `/cost-service/cost-registration` | 无新参数；已保存模板返回新增字段，模板不存在仍返回data:null |
| PUT | `/cost-service/cost-registration` | 可选传入新字段；保存响应回显 |
| POST | `/cost-service/consignments` | 可选传入新字段；创建响应回显；按原流程同步客服快照 |
| POST | `/cost-service/consignments/draft` | 可选传入新字段；暂存响应回显，不流转客服 |
| PUT | `/cost-service/consignments/{consignment_id}` | 可选修改新字段；保存响应回显，并按原流程回写客服快照 |
| PUT | `/cost-service/consignments/{consignment_id}/draft` | 可选修改新字段；暂存响应回显，不回写客服 |
| GET | `/cost-service/consignments/{consignment_id}` | 详情data中的汽运分组增加字段 |
| GET | `/cost-service/consignments` | 列表items每条汽运分组增加字段；查询参数不变 |
| PUT | `/cost-service/consignments/{consignment_id}/void` | 无新请求参数；作废响应保留并返回该字段 |
| GET | `/customer-service/consignment-registration` | 共用汽运结构，已保存模板新增同名字段，模板不存在仍data:null |
| PUT | `/customer-service/consignment-registration` | 可选传入新字段；模板响应回显 |
| POST | `/customer-service/consignments` | 可选传入新字段；响应回显，提交时同名流转至费用 |
| POST | `/customer-service/consignments/draft` | 可选传入新字段；暂存响应回显，不流转费用 |
| PUT | `/customer-service/consignments/{consignment_id}` | 仅未提交客服单据可保存；新字段一并流转费用 |
| PUT | `/customer-service/consignments/{consignment_id}/draft` | 仅未提交客服单据可暂存；响应回显 |
| GET | `/customer-service/consignments/{consignment_id}` | 汽运快照增加同名字段，费用保存后的值可从此回显 |
| GET | `/customer-service/consignments` | items每条汽运快照增加字段；查询参数不变 |
| PUT | `/customer-service/consignments/{consignment_id}/void` | 无新请求参数；作废响应保留并返回该字段 |

路径参数 `consignment_id` 仍为单据主键的数字字符串，不是内部单据ID。没有新增查询参数、必填参数、状态或计算规则。客服共用 `PayableTrucking` 结构，因此同步支持此可选字段，避免已有财务快照流转时丢失；不要求客服页面增加控件。

费用与客服导出接口也同步增加该列：

| 方法 | 完整路径 | 入参 | 返回变化 |
|---|---|---|---|
| POST | `/api/v1/cost-service/consignments/export-excel` | `{"ids":["358000000000000001"]}`，必填数字字符串数组 | xlsx文件二进制，118列；汽运第89列“运费计算方式”取本费用单据保存值 |
| POST | `/api/v1/customer-service/consignments/export-excel` | 同上 | xlsx文件二进制，94列；汽运第79列“运费计算方式”取本客服单据财务快照 |

两个导出均继续单行表头，第2行开始写数据；认证、文件名、Content-Type、排序、错误规则不变，成功响应没有JSON包裹。完整下载请求/响应示例及全列路径见23.11.9。

##### 23.15.3 前端调用及响应示例

费用详情修改保存：

```http
PUT /api/v1/cost-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "payables": {
    "trucking": {
      "unit_price": 2,
      "freight_method": "体积重",
      "weight": 100,
      "volume": 1.2,
      "freight": 123.45,
      "subtotal": 133.45,
      "doc_fee": 10
    }
  }
}
```

`unit_price`为单价、`weight`为汽运计费重量、`volume`为体积、`freight`为前端已计算的运费、`doc_fee`为制单费、`subtotal`为前端已计算的汽运应付小计。示例中后端按传入值保存123.45，不根据单价、重量或体积回算。
成功HTTP200，**响应片段**（原有其他字段省略）：

```json
{
  "code": 0,
  "data": {
    "id": "358000000000000001",
    "status": 1,
    "payables": {
      "trucking": {
        "unit_price": 2.0,
        "freight_method": "体积重",
        "weight": 100.0,
        "volume": 1.2,
        "freight": 123.45,
        "subtotal": 133.45,
        "doc_fee": 10.0
      }
    }
  },
  "msg": "单据信息更新成功"
}
```

只修改计算方式时可只传 `{"payables":{"trucking":{"freight_method":"计费重"}}}`，其他汽运数据不变。
如需暂存，调用相同路径加 `/draft`，结构相同，返回status=0、msg="单据信息暂存成功"；不会将暂存结果同步给客服。
随后GET详情时，请求无body，HTTP200、msg="查询成功"，上述字段位于 `data.payables.trucking.freight_method`；GET列表位于 `data.items[].payables.trucking.freight_method`。
模板使用 `PUT /api/v1/cost-service/cost-registration`，新增使用 `POST /api/v1/cost-service/consignments`（或 `/draft`），均使用同样的汽运分组请求。

清空请求示例：

```json
{"payables":{"trucking":{"freight_method":null}}}
```

保存/暂存成功后该字段返回null；旧客户端完全不传本字段仍兼容。错误示例：

```json
{"code":422,"data":null,"msg":"参数验证失败 (body -> payables -> trucking -> freight_method): Input should be a valid string"}
```

费用保存提交已锁定客服保存/暂存仍409，两台已作废保存/暂存仍409，不存在单据404、非法主键400、认证失败规则均延续。

##### 23.15.4 流转、Excel与部署

- 客服保存提交时，若汽运快照实际包含该字段，则按原同步规则写入费用列，显式null/空字符串也一并同步；客服未传此字段时不覆盖费用已有值。客服暂存不流转。
- 费用保存提交时，按原逻辑将该值写入客服财务快照；费用暂存只保存费用自身。两台提交、作废及锁定规则不变。
- **Excel同步增加汽运运费计算方式**：客服共94列（A至CP），该字段在第79列（CA）；费用共118列（A至DN），该字段在第89列（CK），位于汽运单价和运费之间。均为单行表头，数据从第2行开始。新增列直接读取 `payables.trucking.freight_method` 原样展示，不转换字符串编码、不参与运费计算；后续列顺延1列，完整列映射见23.11.9。
- 存量数据库须在发布代码前执行 `sql/migration_add_cost_trucking_freight_method.sql` 一次，分别为 `cost_registrations` 和 `cost_consignments` 新增可空 `varchar(50)` 列 `pay_trucking_freight_method`。历史记录默认为NULL，不推断或回填计算方式，不回算金额。
- 客服继续使用已有 `financial_data` JSON，无需新增数据库列。全新库使用已更新的 `sql/migration_create_cost_service_consignments.sql` 或ORM建表，已包含该字段，不再执行此增量加列。
- 本次未连接生产数据库执行迁移；既有财务快照、标签、状态及操作记录表等历史迁移仍需按数据库现状执行。

#### 23.16 费用列表主单号仅搜索国际空运主单号（2026-11-02）

**涉及接口**：`GET /api/v1/cost-service/consignments`。使用原列表接口及原认证方式 `Authorization: Bearer <token>`，只修改主单号查询范围。前端将搜索框标题和提示从“航司单号”改为“主单号”，仍使用 `flight_doc_no` 查询参数，无需更改参数名或新增请求字段。

##### 23.16.1 参数与匹配规则

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `flight_doc_no` | query | string | 否 | 主单号关键字，去除首尾空白后，仅对国际空运应付款项主单号 `payables.intl_air.flight_doc_no` 进行包含式模糊匹配，对应数据库列 `pay_intl_air_flight_doc_no` |
| `page` | query | integer | 否 | 页码，默认1，最小1，沿用原规则 |
| `pageSize` | query | integer | 否 | 每页数量，默认10，最小1，沿用原规则 |

其他既有参数如 `customer_name`、`agent`、`status`、`flight_no`、进仓/航班日期范围、`sort_by`、`sort_order` 均继续支持；航班日期范围按23.20筛选委托信息航班日期，其余含义和默认值不变：

- 关键字 `123456` 可匹配国际空运主单号 `784-12345678`；完整号码也按包含方式搜索。
- 此参数**仅搜索国际空运主单号**。货主主单号、货主提单、国内空运主单号、汽运主单号包含关键字而国际空运主单号不包含时，该记录不匹配；国际空运主单号为NULL/空字符串时，不回退其他字段。
- 未传、传空字符串或仅空白时不启用主单号筛选。数据仍可被其他筛选条件选中，包括国际空运主单号为空的单据。
- 与客户、代理、状态、航班号、日期等其他有效条件按AND组合。航班号 `flight_no` 的原多分组OR查询范围不变。
- 先按全部条件筛选并计算 `total`，再按原排序及分页返回。默认仍进仓日期倒序、制单时间倒序、ID倒序；显式排序规则沿用23.2。
- 筛选不改写记录，也不改变响应字段名称或值：货主 `consignor_info.flight_doc_no` 仍按原值返回，搜索实际对应 `payables.intl_air.flight_doc_no`。前端如需展示或回填此次搜索对应的号码，应读取国际空运分组字段。

##### 23.16.2 请求与响应示例

请求无body，示例：

```http
GET /api/v1/cost-service/consignments?flight_doc_no=784-12345678&page=1&pageSize=10
Authorization: Bearer <token>
```

若仅单据 `358000000000000001` 的国际空运主单号匹配，成功HTTP200，以下为**响应片段**（其余单据业务字段省略，实际结构不裁剪）：

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "358000000000000001",
        "status": 0,
        "consignor_info": {
          "flight_doc_no": "货主单号原值",
          "bill_of_lading": "提单原值"
        },
        "payables": {
          "intl_air": {"flight_doc_no": "784-12345678"},
          "dom_air": {"flight_doc_no": "国内单号原值"}
        }
      }
    ],
    "page": 1,
    "pageSize": 10
  },
  "msg": "查询成功"
}
```

多个条件示例：`GET /api/v1/cost-service/consignments?flight_doc_no=123456&status=0&start_flight_date=2026-11-01&end_flight_date=2026-11-02&page=1&pageSize=10`，要求国际空运主单号包含123456、费用状态为未提交，且委托信息航班日期处于给定区间，三个条件同时成立。
没有匹配数据时成功HTTP200，完整返回：

```json
{"code":0,"data":{"total":0,"items":[],"page":1,"pageSize":10},"msg":"查询成功"}
```

分页、状态或排序参数非法仍HTTP422，认证失败沿用现有错误格式；没有新增错误码。
本次不修改客服接单台列表筛选、单据新增/修改、同步、状态、导出表头及字段取值；无需数据库迁移。此为后端仓库，搜索框“主单号”文字及提示由前端调整。

#### 23.17 费用列表航班日期改为搜索国际空运应付款项（2026-11-02，历史规则已替代）

**历史说明：本节保留旧版规则与示例，已由23.20（2026-11-09）替代，不再作为当前接口契约。当前费用列表航班日期范围筛选仅使用委托信息区 `consignor_info.flight_date`；本次不要求执行本节旧索引脚本。**

**涉及接口**：`GET /api/v1/cost-service/consignments`，继续使用 `Authorization: Bearer <token>`。请求无body；保留现有查询参数名，航班日期筛选字段改为 `payables.intl_air.flight_date`，对应数据库列 `cost_consignments.pay_intl_air_flight_date`。

##### 23.17.1 查询参数与匹配规则

| 参数 | 位置 | 类型/格式 | 必填 | 含义 |
|---|---|---|---|---|
| `start_flight_date` | query | string，YYYY-MM-DD | 否 | 应付款项-国际空运航班日期下限，包含当天 |
| `end_flight_date` | query | string，YYYY-MM-DD | 否 | 应付款项-国际空运航班日期上限，包含当天 |
| `start_warehouse_date` | query | string，YYYY-MM-DD | 否 | 货主委托信息进仓日期下限，包含当天，规则不变 |
| `end_warehouse_date` | query | string，YYYY-MM-DD | 否 | 货主委托信息进仓日期上限，包含当天，规则不变 |
| `page` | query | integer | 否 | 页码，默认1，最小1 |
| `pageSize` | query | integer | 否 | 每页数量，默认10，最小1 |

- 两个航班日期参数可独立使用：只传开始日期为“大于等于”，只传结束日期为“小于等于”；同时传入为闭区间，同一天可精确查询。均不传时不启用航班日期筛选。
- 只检查国际空运应付款项航班日期。该字段为NULL时，不符合任何有效日期边界；货主或国内空运日期即使在区间内，也不会代替国际空运日期参与匹配。未启用此筛选时，日期为空的记录仍可被其他条件选中。
- 进仓日期继续使用 `consignor_info.warehouse_entry_date`，与航班日期独立；客户、代理、主单号、航班号、状态等有效筛选条件按AND组合。主单号仍仅搜索国际空运主单号，航班号仍保持原多分组OR匹配。
- 沿用现有日期解析兼容行为：未传、空字符串、无法解析的日期边界均忽略；若只有一端能解析，则只应用有效的一端。前端应传有效 `YYYY-MM-DD` 日期。有效开始日期晚于有效结束日期时返回空列表，不新增错误码。
- 先筛选并计算 `total`，再按原列表排序和分页返回；默认仍按进仓日期倒序、制单时间倒序、ID倒序。响应结构、字段原值、状态和业务数据不变。

##### 23.17.2 请求与返回示例

查询国际空运应付款项航班日期为2026-11-02的单据：

```http
GET /api/v1/cost-service/consignments?start_flight_date=2026-11-02&end_flight_date=2026-11-02&page=1&pageSize=10
Authorization: Bearer <token>
```

成功HTTP200，以下为**响应片段**，其余既有业务字段省略，实际接口不裁剪字段。示例说明货主、国际空运、国内空运日期可以不同，筛选只看国际空运日期：

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "358000000000000001",
        "status": 0,
        "consignor_info": {
          "warehouse_entry_date": "2026-10-30",
          "flight_date": "2026-11-01"
        },
        "payables": {
          "intl_air": {
            "flight_doc_no": "784-12345678",
            "flight_date": "2026-11-02"
          },
          "dom_air": {"flight_date": "2026-11-03"}
        }
      }
    ],
    "page": 1,
    "pageSize": 10
  },
  "msg": "查询成功"
}
```

单边条件示例：`GET /api/v1/cost-service/consignments?start_flight_date=2026-11-02`，查询国际空运航班日期为当天及之后的记录。

组合条件示例：`GET /api/v1/cost-service/consignments?start_warehouse_date=2026-10-01&end_warehouse_date=2026-10-31&start_flight_date=2026-11-01&end_flight_date=2026-11-02&flight_doc_no=123456&status=0&page=1&pageSize=10`，要求进仓日期在10月、国际空运航班日期在11月1日至2日、国际空运主单号包含123456且状态为未提交，全部条件同时满足。

无匹配记录时成功HTTP200，完整响应：

```json
{"code":0,"data":{"total":0,"items":[],"page":1,"pageSize":10},"msg":"查询成功"}
```

分页、状态、排序参数的校验错误仍HTTP422，认证失败沿用现有格式；没有新增错误码或请求字段。

##### 23.17.3 数据库索引与发布

业务字段已存在，无需新增字段、回填历史日期或重算费用。为支持新的日期范围查询，存量库发布时需执行 `sql/migration_add_cost_consignment_intl_air_flight_date_index.sql` 一次，为 `pay_intl_air_flight_date` 增加索引。全新库使用已更新建表SQL或ORM建表时已包含索引，无需重复执行。该脚本未在生产数据库执行。

保留原货主 `flight_date` 及其索引；本次仅调整费用列表查询，客服列表、保存/同步、Excel列内容和费用Excel按货主航班日期的既有排序不变。

#### 23.18 恢复委托信息航班日期及Excel基础列（2026-11-09）

两台编辑区、列表区的委托信息“航班日期”放在“进仓日期”之后。后端原字段始终保留，前端恢复原字段的填写和回显即可；本仓库不包含两台前端页面。两台Excel当前第8列（H）输出“航班日期”，取原委托信息日期；委托段落顺序以23.26节为准。仍为单行表头，第2行起为数据，不增加分组标题或空白列。

##### 23.18.1 编辑、列表与详情字段

| 页面 | 保存请求字段 | 详情/模板响应路径 | 列表响应路径 | 类型与含义 |
|---|---|---|---|---|
| 客服接单台 | `flight_date`，请求body第一层 | `data.flight_date` | `data.items[].flight_date` | 可选string，建议YYYY-MM-DD；响应string/null；委托信息原航班日期 |
| 费用登记台 | `consignor_info.flight_date` | `data.consignor_info.flight_date` | `data.items[].consignor_info.flight_date` | 可选string，建议YYYY-MM-DD；响应string/null；委托信息原航班日期 |

继续使用原认证方式 `Authorization: Bearer <token>`。无新增路由、请求字段或响应字段，恢复使用的现有接口如下（前缀均为 `/api/v1`）：

| 页面 | 接口 | 用途 |
|---|---|---|
| 客服 | `GET/PUT /customer-service/consignment-registration` | 委托模板查询、保存，字段为顶层flight_date |
| 客服 | `POST /customer-service/consignments`、`POST /customer-service/consignments/draft` | 保存新增、暂存新增 |
| 客服 | `PUT /customer-service/consignments/{id}`、`PUT /customer-service/consignments/{id}/draft` | 保存修改、暂存修改 |
| 客服 | `GET /customer-service/consignments`、`GET /customer-service/consignments/{id}` | 列表、详情 |
| 费用 | `GET/PUT /cost-service/cost-registration` | 费用模板查询、保存，字段位于consignor_info内 |
| 费用 | `POST /cost-service/consignments`、`POST /cost-service/consignments/draft` | 保存新增、暂存新增 |
| 费用 | `PUT /cost-service/consignments/{id}`、`PUT /cost-service/consignments/{id}/draft` | 保存修改、暂存修改 |
| 费用 | `GET /cost-service/consignments`、`GET /cost-service/consignments/{id}` | 列表、详情 |

客服暂存编辑请求示例（其他字段可按原契约合并）：

```http
PUT /api/v1/customer-service/consignments/358000000000000001/draft
Authorization: Bearer <token>
Content-Type: application/json

{"flight_date":"2026-11-09"}
```

费用暂存编辑请求示例：

```http
PUT /api/v1/cost-service/consignments/358000000000000001/draft
Authorization: Bearer <token>
Content-Type: application/json

{"consignor_info":{"flight_date":"2026-11-09"}}
```

对应详情HTTP200响应片段（实际仍返回其他原业务字段）：

```json
{"code":0,"data":{"id":"358000000000000001","flight_date":"2026-11-09"},"msg":"查询成功"}
```

```json
{"code":0,"data":{"id":"358000000000000001","consignor_info":{"flight_date":"2026-11-09"}},"msg":"查询成功"}
```

列表同一字段分别位于 `data.items[].flight_date` 和 `data.items[].consignor_info.flight_date`，日期未填为null，分页包裹结构不变。新增不传则为空；原部分修改接口不传此字段或传null保留原值，其他日期解析规则延续。客服费用保存提交已锁定（editable=false）或作废时禁止编辑，客服仅保存后仍可编辑，详见23.19。

##### 23.18.2 原有同步及历史数据规则

- 客服暂存仍只写客服，不同步费用；客服确认提交时，委托 `flight_date` 同步到费用 `consignor_info.flight_date`，并按既有规则预填费用 `payables.intl_air.flight_date`。
- 若客服明确录入了 `payables.intl_air.flight_date`（含显式null），该分组值继续优先于委托日期预填，保留此前扩展录入规则。本次不新增强制双向覆盖规则。
- 费用暂存不回写客服；费用保存时将费用委托日期回写客服顶层日期，财务快照按原逻辑回写。仅编辑费用委托日期不会强制覆盖费用国际空运日期；两个字段的实际保存值分别展示。
- 直接读取历史委托日期，无需将其搬运到国际空运或国内空运日期，不回填或改写历史数据。即使客服 `financial_data` 为NULL、费用国际空运日期为空，只要原委托日期有值，新版Excel第8列就会正常显示。
- 费用列表搜索参数 `start_flight_date`、`end_flight_date` 已按23.20改为筛选委托信息航班日期 `consignor_info.flight_date`。费用Excel继续按委托航班日期升序排列，客服Excel继续按制单时间倒序排列。

##### 23.18.3 修改的Excel接口及新列位置

| 方法 | 接口 | 请求body | 成功响应 |
|---|---|---|---|
| POST | `/api/v1/customer-service/consignments/export-excel` | `{"ids":["358000000000000001"]}` | xlsx二进制，94列（A至CP） |
| POST | `/api/v1/cost-service/consignments/export-excel` | 同上 | xlsx二进制，118列（A至DN） |

`ids` 必填string[]，至少一项，元素为数字形式的单据主键。认证、校验、文件名规则及媒体类型延续23.11.9，成功HTTP200无JSON包裹：

```http
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=consignment_export_20261109100000.xlsx
Access-Control-Expose-Headers: Content-Disposition
```

费用文件名同规则、前缀为 `cost_consignment_export_`。基础列顺序为“序号、状态、客户名称、进仓日期、航班日期、主单号……”；新增日期以YYYY-MM-DD文本显示，空日期为空单元格，后续列仅顺延，所有业务值仍取各自原字段。

| 分组 | 客服Excel位置及来源 | 费用Excel位置及来源 |
|---|---|---|
| 委托信息航班日期 | 第8列H，`flight_date` | 第8列H，`consignor_info.flight_date` |
| 国际空运航班日期 | 第38列AL，`payables.intl_air.flight_date` | 第42列AP，同名国际空运字段 |
| 国内空运航班日期 | 第88列CJ，`payables.dom_air.flight_date` | 第100列CV，同名国内空运字段 |

同名表头按所在列区分，不可按名称去重。完整列号和取值表已同步更新23.11.9。本次复用原数据库日期列，无需新迁移、不重算金额；此前版本所需的字段迁移仍须完成。

#### 23.19 客服可重复编辑，费用保存提交后锁定（2026-11-09）

本节替代此前“客服保存立即锁定”的规则。**客服保存成功仍可编辑；费用登记台保存提交成功后，客服才不可编辑。**原有status含义、搜索/导出、保存同步、暂存不流转、标签覆盖及作废/删除规则保留。前端必须用客服单据响应新增的 `editable` 控制编辑、暂存和保存，不能再用 `status===1` 判定锁定。

##### 23.19.1 新增响应字段与接口范围

| 字段 | 类型 | 位置 | 说明 |
|---|---|---|---|
| `editable` | boolean | 客服单据响应 `data.editable`；列表 `data.items[].editable` | 只读。费用未成功保存提交且客服未作废为true；费用已成功保存提交或客服作废为false。覆盖全部客服业务字段，包括基础信息、两组标签和财务分组 |
| `status` | integer | 原位置不变 | 0未提交、1已提交、2作废，继续表示本台单据状态。客服保存后的status=1与editable=true可以同时出现 |

无新增请求字段；`editable`、内部持久化列 `edit_locked` 不可由前端设置，伪造 `status:0`、`editable:true`、`edit_locked:false` 均不能解除锁定。仅客服单据响应新增editable（含列表项），登记模板和费用响应不新增该字段，费用接口通过既有路径影响客服权限。

| 方法及完整路径 | 本次行为/响应变化 |
|---|---|
| `POST /api/v1/customer-service/consignments` | 客服保存新增，返回status=1、editable=true；同事务流转费用草稿status=0 |
| `POST /api/v1/customer-service/consignments/draft` | 客服暂存新增，status=0、editable=true，不流转费用 |
| `PUT /api/v1/customer-service/consignments/{consignment_id}` | editable=true可反复保存，status=1、editable=true，每次按原规则同步费用草稿 |
| `PUT /api/v1/customer-service/consignments/{consignment_id}/draft` | editable=true可暂存，status=0、editable=true，仅保存客服，不覆盖费用已有版本 |
| `GET /api/v1/customer-service/consignments/{consignment_id}` | data第一层增加editable，反映持久化锁定及作废状态 |
| `GET /api/v1/customer-service/consignments` | items每项第一层增加editable，无额外逐条查费用表；status筛选仍按客服status执行 |
| `PUT /api/v1/customer-service/consignments/{consignment_id}/void` | 原有联动作废规则不变，返回status=2、editable=false |
| `POST /api/v1/cost-service/consignments` | 费用保存新增时，同时创建客服记录并锁定，后续客服详情/列表editable=false |
| `PUT /api/v1/cost-service/consignments/{consignment_id}` | 费用保存提交、回写客服业务数据、客服锁定、真实操作记录在同一事务提交 |
| `POST /api/v1/cost-service/consignments/draft` | 仅创建费用草稿，不创建客服、不触发锁定 |
| `PUT /api/v1/cost-service/consignments/{consignment_id}/draft` | 只暂存费用，不新增客服锁定；费用此前已保存提交时，既有客服锁定不会解除 |
| `PUT /api/v1/cost-service/consignments/{consignment_id}/void` | 原有联动作废规则不变，客服查询editable=false |

##### 23.19.2 参数说明及请求示例

继续使用 `Authorization: Bearer <token>`，带body的写入请求使用 `Content-Type: application/json`。业务字段仍按23.11及后续扩展章节填写，GET无body。

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `consignment_id` | path | string | 单条查询/修改/作废必填 | 两台共用的数字字符串主键，取接口返回id；不是内部单据编号 |
| `customer_name` | 客服body第一层 | string/null | 否 | 客户名称，沿用原部分更新规则 |
| `flight_date` | 客服body第一层 | string/null | 否 | 委托信息航班日期，建议YYYY-MM-DD，客服保存时仍预填费用国际空运日期，明确分组值优先 |
| `pieces` | 客服body第一层 | integer/null | 否 | 件数，未传保留，显式null清空 |
| `customer_tags` | 两台body第一层 | string[]/null | 否 | 最多5项，原英文标识数组；省略/null保留，[]清空 |
| `expense_tags` | 两台body第一层 | string[]/null | 否 | 最多7项，原英文标识数组；省略/null保留，[]清空 |
| `consignor_info` | 费用body第一层 | object/null | 否 | 原货主委托信息分组，可包含customer_name、flight_date、pieces等 |
| `receivables`、`payables` | 两台body第一层 | object/null | 否 | 原应收应付业务分组，字段与计算责任不变 |

客服保存新增：

```http
POST /api/v1/customer-service/consignments
Authorization: Bearer <token>
Content-Type: application/json

{"customer_name":"客户A","flight_date":"2026-11-09","pieces":8,"customer_tags":["intl_air"],"expense_tags":["ground"]}
```

HTTP200响应片段（实际仍返回原完整业务字段）：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":true,"customer_name":"客户A","flight_date":"2026-11-09","pieces":8,"customer_tags":["intl_air"],"expense_tags":["ground"]},"msg":"委托信息创建成功"}
```

费用未保存提交前，客服可再次保存：

```http
PUT /api/v1/customer-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json

{"pieces":9}
```

HTTP200响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":true,"pieces":9},"msg":"委托信息更新成功"}
```

费用人员保存提交：

```http
PUT /api/v1/cost-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json

{"consignor_info":{"pieces":10},"receivables":{"total":1000}}
```

费用HTTP200响应片段，费用结构不增加editable：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"consignor_info":{"pieces":10},"receivables":{"total":1000}},"msg":"单据信息更新成功"}
```

随后 `GET /api/v1/customer-service/consignments/358000000000000001` 的HTTP200响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":false,"pieces":10,"receivables":{"total":1000}},"msg":"查询成功"}
```

客服列表请求仍为 `GET /api/v1/customer-service/consignments?page=1&pageSize=10`，可选page/pageSize均为integer，默认1/10、最小1；其余原有查询参数不变。HTTP200响应片段如下：

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","status":1,"editable":false,"pieces":10}],"page":1,"pageSize":10},"msg":"查询成功"}
```

费用后续暂存将费用status置0，但上述客服editable继续为false。前端选择单据时读取editable；其他人员可能同时保存费用，客服操作遇到409时应刷新详情/列表更新按钮，不能只相信页面缓存。

##### 23.19.3 错误、同步与事务边界

费用保存提交后，客服PUT保存、PUT暂存（包括空对象或仅改标签）均HTTP409，完整响应：

```json
{"code":409,"data":null,"msg":"费用登记台已保存提交，客服委托信息不能修改或暂存，请在费用登记台维护"}
```

作废客服仍HTTP409，msg仍为“已作废的委托信息不能暂存或保存”；不存在单据404、主键非数字400、请求校验422、认证规则沿用原实现。异常存量状态若费用已经提交/作废而客服锁尚未正确设置，客服保存还会拒绝覆盖费用，HTTP409，msg为“费用登记台已提交或作废，客服不能覆盖该单据”。

- 客服重复保存同步同ID费用基础信息、国际空运预填及明确录入的财务字段和两组标签；未录入财务叶字段继续沿用原不覆盖规则，费用独有分组不被客服请求清空。客服暂存不流转。
- 费用保存将业务回写、客服锁定及操作日志放在同一数据库事务中；校验失败、日志写入失败或数据库提交失败回滚时，不留下新增锁定。客服失败保存也不消耗后续编辑机会。若数据库已提交但客户端因网络中断未收到响应，应重新查详情确认结果，不能根据客户端报错自动解锁。
- 两台保存统一按客服行、费用行顺序加行锁，防止客服在费用提交期间覆盖或重置费用状态；费用暂存也锁定费用行。SQLite测试验证流程和加锁语句顺序，生产MySQL执行实际行锁。
- 锁定为独立持久化事实，不从费用当前status=0推断解锁。唯一登记模板仍可保存，保存模板不改变任何单据锁定；Excel仍按本台status显示原状态，不增加editable列；删除/作废与既有联动规则不变。

##### 23.19.4 存量数据库迁移与历史边界

**存量库发布前须执行 `sql/migration_add_customer_edit_lock.sql` 一次**，给 `consignment_infos` 增加非空布尔列 `edit_locked`，默认0。前提为已有两台状态字段和操作记录表。请在两台暂停写入的发布窗口执行迁移并更新服务，避免旧服务写入与锁定回填交错。模板、费用表不加该列；全新库通过已更新建表SQL或ORM建表已包含该列，不重复执行增量加列。

历史回填规则：同ID费用当前status=1，或存在真实 `source=cost_service/action=save` 操作记录时设置锁定；包括费用保存后又暂存为0的情形。其余默认不锁定，客服status=1本身不构成锁定依据，作废客服仍由status=2禁止编辑。不改变业务状态、金额、日期、标签、更新时间或历史日志。

在操作记录功能上线前已经费用保存、之后又暂存为0且没有保存日志的历史记录，无法仅凭现有状态还原是否曾提交；脚本不虚构依据，保留未锁定，若需保持个别记录锁定须根据真实历史证据另行核对。执行前已存在edit_locked列时勿重复ADD COLUMN；回填UPDATE仅将符合依据的未锁记录设为锁定，不重置已有锁，允许单独重跑。脚本尚未在生产库执行。


#### 23.20 费用列表航班日期范围改用委托信息日期（2026-11-09）

替代23.17的历史筛选规则。仅调整 `GET /api/v1/cost-service/consignments` 的航班日期范围筛选，匹配委托信息区 `consignor_info.flight_date`，对应数据库列 `cost_consignments.flight_date`。客服接单台继续沿用原查询逻辑。

##### 23.20.1 请求参数

使用 `Authorization: Bearer <token>`，请求无body。参数名、类型及可选性保持原约定：

| 参数 | 位置 | 类型/格式 | 必填 | 说明 |
|---|---|---|---|---|
| `start_flight_date` | query | string，YYYY-MM-DD | 否 | 委托信息航班日期下限，包含当天；仅传此项时查询当天及之后 |
| `end_flight_date` | query | string，YYYY-MM-DD | 否 | 委托信息航班日期上限，包含当天；仅传此项时查询当天及之前 |
| `page` | query | integer | 否 | 页码，默认1，最小1 |
| `pageSize` | query | integer | 否 | 每页条数，默认10，最小1 |

其他原有条件（进仓日期范围、客户名称、代理单位、主单号、航班号、状态）和排序参数继续支持，有效条件按AND组合。主单号仍仅匹配国际空运 `payables.intl_air.flight_doc_no`。

- 开始和结束日期同时有效时为闭区间，传相同日期可精确查一天；开始晚于结束返回空列表。
- 只看委托信息日期，不回退或混用国际空运、国内空运日期。委托日期为空时不满足有效日期条件，即使国际空运日期在范围内也不入选；委托日期在范围内、国际空运日期为空或在范围外时仍可入选。
- 两端均未传时不启用航班日期筛选，日期为空的记录可正常返回。沿用原兼容行为：空字符串、空白及无法解析的日期边界被忽略；仅一端有效时只应用该端。前端应传有效YYYY-MM-DD日期。
- 先筛选再计算total、排序和分页。默认进仓日期倒序、制单时间倒序、ID倒序，原错误码与响应字段不变。

##### 23.20.2 请求及响应示例

查询委托信息航班日期为2026-11-09的费用单据：

```http
GET /api/v1/cost-service/consignments?start_flight_date=2026-11-09&end_flight_date=2026-11-09&page=1&pageSize=10
Authorization: Bearer <token>
```

成功HTTP200。以下为响应片段，实际仍返回原完整字段。国际空运日期为11月12日的记录也可返回，因为委托信息日期为11月9日：

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "358000000000000001",
        "status": 0,
        "consignor_info": {
          "warehouse_entry_date": "2026-11-08",
          "flight_date": "2026-11-09"
        },
        "payables": {
          "intl_air": {
            "flight_doc_no": "784-12345678",
            "flight_date": "2026-11-12"
          },
          "dom_air": {"flight_date": "2026-11-15"}
        }
      }
    ],
    "page": 1,
    "pageSize": 10
  },
  "msg": "查询成功"
}
```

列表委托航班日期的读取路径为 `data.items[].consignor_info.flight_date`，返回string/null，各分组原日期保持原值。前端沿用原参数名，仅按委托信息区日期理解筛选结果。

组合查询示例：`GET /api/v1/cost-service/consignments?start_warehouse_date=2026-11-01&end_warehouse_date=2026-11-08&start_flight_date=2026-11-09&end_flight_date=2026-11-09&flight_doc_no=123456&status=0`，要求委托进仓日期在11月1日至8日、委托航班日期为11月9日、国际空运主单号包含123456、费用状态未提交，全部条件同时满足。

无匹配时成功HTTP200，完整响应：

```json
{"code":0,"data":{"total":0,"items":[],"page":1,"pageSize":10},"msg":"查询成功"}
```

##### 23.20.3 数据与发布说明

本次仅修改查询条件及接口参数说明，不修改或搬运历史日期，不改两台的日期保存/同步、Excel列值和排序、客服锁定规则。继续使用既有委托航班日期列和索引，无新增表字段或迁移脚本。已有 `flight_date` 索引时无需执行SQL；若旧库尚未加过索引，可先用 `SHOW INDEX FROM cost_consignments` 核查，缺少以flight_date为首列的索引时再执行既有 `sql/migration_add_cost_consignment_flight_date_index.sql`，避免重复加索引。无需为本次查询变更执行旧国际空运日期索引脚本，也不删除既有索引。本次未执行生产数据库操作。


#### 23.21 客服接单台新增主单号查询条件（2026-11-09）

**接口**：`GET /api/v1/customer-service/consignments`。新增可选Query参数 `flight_doc_no`，使用 `Authorization: Bearer <token>`，请求无body。

##### 23.21.1 参数及筛选规则

| 参数名 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `flight_doc_no` | query | string | 否 | 本次新增。客服委托信息主单号的包含式模糊查询，对应数据库 `consignment_infos.flight_doc_no`，响应路径 `data.items[].flight_doc_no` |
| `start_date` | query | string，YYYY-MM-DD | 否 | 原制单日期下限，含当天，按create_time筛选 |
| `end_date` | query | string，YYYY-MM-DD | 否 | 原制单日期上限，含当天，按create_time筛选 |
| `customer_name` | query | string | 否 | 原客户名称模糊查询 |
| `destination` | query | string | 否 | 原目的站模糊查询，仅匹配origin_destination最后一个“-”之后的内容 |
| `flight_no` | query | string | 否 | 原客服自身航班号模糊查询 |
| `status` | query | integer | 否 | 原状态筛选，0未提交、1已提交、2作废，不传全部；编辑权限仍按editable判断 |
| `sort_by` | query | string | 否 | 原排序字段，create_time或warehouse_entry_date，默认create_time |
| `sort_order` | query | string | 否 | 原排序方向，asc或desc，默认desc |
| `page` | query | integer | 否 | 页码，默认1，最小1 |
| `pageSize` | query | integer | 否 | 每页条数，默认10，最小1 |

- 主单号仅查询客服委托信息顶层字段 `flight_doc_no`。提单 `bill_of_lading`、内部单据ID、财务分组中的国际空运/国内空运/汽运主单号不参与匹配。
- 包含式匹配：例如主单号为784-12345678时，传784、123456或完整号码均可匹配。英文字母不区分大小写，支持中文内容。
- 自动去除参数首尾空白；未传、空字符串、仅空白时不增加该条件，保持原列表行为。有有效查询值时，顶层主单号为null或空字符串的记录不匹配。
- 输入中的百分号和下划线按普通字符处理，不作为SQL通配符；查询使用绑定参数，不将输入拼接为SQL语句。特殊字符应由前端标准URL编码（例如百分号编码为%25）。
- 新条件与其他有效筛选条件按AND组合，在total统计和分页之前应用。默认仍按制单时间、ID倒序，原其他排序方式、响应字段和编辑锁定规则不变。

##### 23.21.2 请求及响应示例

按主单号片段查询：

```http
GET /api/v1/customer-service/consignments?flight_doc_no=123456&page=1&pageSize=10
Authorization: Bearer <token>
```

HTTP200响应片段（其余原业务字段省略，实际仍返回完整对象）：

```json
{
  "code": 0,
  "data": {
    "total": 1,
    "items": [
      {
        "id": "358000000000000001",
        "status": 1,
        "editable": true,
        "create_time": "2026-11-09 10:00:00",
        "customer_name": "客户A",
        "flight_doc_no": "784-12345678",
        "flight_no": "CZ1234",
        "origin_destination": "CAN-KUL",
        "bill_of_lading": "一主三分",
        "payables": {
          "intl_air": {"flight_doc_no": "999-87654321"}
        }
      }
    ],
    "page": 1,
    "pageSize": 10
  },
  "msg": "查询成功"
}
```

上述记录按顶层784-12345678匹配，分组中999-87654321不会影响匹配或被覆盖。前端列表“主单号”继续读取 `data.items[].flight_doc_no`，无需新增返回字段。

组合查询：`GET /api/v1/customer-service/consignments?flight_doc_no=123456&start_date=2026-11-01&end_date=2026-11-09&customer_name=客户A&destination=KUL&flight_no=CZ&status=1&page=1&pageSize=10`，要求所有条件同时成立；中文由调用方标准URL编码。

无匹配记录时HTTP200，完整响应：

```json
{"code":0,"data":{"total":0,"items":[],"page":1,"pageSize":10},"msg":"查询成功"}
```

错误格式不变：非法status、排序枚举或分页值仍HTTP422，认证沿用原规则。本次无需数据库迁移，保存、详情、同步、Excel及费用登记台查询保持既有实现。费用登记台的同名参数仍查询国际空运主单号（见23.16），不要与本客服接口的顶层主单号混用。


#### 23.22 两台应收款项“一程费用”展示及Excel导出（2026-11-11）

客服接单台、费用登记台编辑区在应收“耗材费”后展示“一程费用”，继续绑定既有字段 `receivables.first_leg_fee`。该字段原本已支持保存、查询及两台同步；本次补齐两台Excel导出列，不另起同义字段，不复用基础信息中的一程重量。仓库不含前端页面，前端需在两台应收编辑区补上对应输入框。

##### 23.22.1 字段及更新语义

| 字段 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `receivables.first_leg_fee` | 两台写入body/单条响应data | number/null | 否 | 应收一程费用，金额。费用表持久化为receivable_first_leg_fee，decimal(10,2)；建议前端传两位小数，范围遵循该数据库列，不新增请求精度校验 |
| `receivables.first_leg_fee` | 两台列表data.items[]中 | number/null | 响应字段 | 同一单据已保存的一程费用，历史未填为null；费用模板未创建时整个data仍按原规则为null |
| `receivables.total` | 原位置 | number/null | 否 | 原应收合计，后台不根据一程费用重新计算，前端计算后按原接口传入 |

`first_leg_fee`与基础 `first_leg_weight`（一程重量）是不同字段。后端保存传入金额，不将其乘以重量、费率或纳入自动合计，不重算利润和提成。

| 场景 | 不传first_leg_fee | 显式null | 传0 |
|---|---|---|---|
| 客服模板/单据更新 | 保留已有值 | 清空客服财务快照；下次客服正常保存会将清空同步至费用 | 保存为0，正常流转和导出 |
| 费用模板/单据更新 | 保留已有值 | 沿用费用已有数值字段规则，保留已有值；如要置零传0 | 保存为0 |
| 两台新增 | 未填为null | 初始为空 | 保存为0 |

整个receivables未传或传null沿用原规则，不清空已有分组。客服只暂存时不流转；客服正常保存将明确填写的一程费用同步至同ID费用记录，未明确填写则不覆盖费用已有值。费用正常保存时把一程费用随财务快照回写客服并锁定客服，费用暂存不回写、不改变客服锁定。客服能否编辑仍按23.19的editable控制。

##### 23.22.2 接口范围

以下接口原本就支持该字段，本次不新增路由/请求字段，明确供前端编辑和回显使用。路径均以 `/api/v1` 开头，认证继续使用Bearer token；写入JSON请求使用Content-Type: application/json。

| 方法 | 路径（相对/api/v1） | 字段行为 |
|---|---|---|
| GET、PUT | `/customer-service/consignment-registration` | 客服模板读取/保存，data.receivables.first_leg_fee |
| POST | `/customer-service/consignments`、`/customer-service/consignments/draft` | 客服保存新增/暂存新增，可提交receivables.first_leg_fee，响应同路径回显 |
| PUT | `/customer-service/consignments/{id}`、`/customer-service/consignments/{id}/draft` | 客服保存/暂存修改，费用提交锁定或作废后仍拒绝修改 |
| GET | `/customer-service/consignments/{id}` | 客服详情data.receivables.first_leg_fee |
| GET | `/customer-service/consignments` | 客服列表data.items[].receivables.first_leg_fee |
| GET、PUT | `/cost-service/cost-registration` | 费用模板读取/保存，data.receivables.first_leg_fee |
| POST | `/cost-service/consignments`、`/cost-service/consignments/draft` | 费用保存新增/暂存新增，可提交该字段并回显 |
| PUT | `/cost-service/consignments/{id}`、`/cost-service/consignments/{id}/draft` | 费用保存/暂存修改，遵循原同步规则 |
| GET | `/cost-service/consignments/{id}` | 费用详情data.receivables.first_leg_fee |
| GET | `/cost-service/consignments` | 费用列表data.items[].receivables.first_leg_fee |
| PUT | 两台 `/consignments/{id}/void` | 作废响应保留已有金额，不因作废改写该字段 |
| POST | 两台 `/consignments/export-excel` | 本次实际变更：应收耗材费后补一程费用列，后续列顺延 |

`{id}`/`ids[]`继续使用单据数字字符串主键，不是内部单据ID。GET无body，列表其他筛选、状态、分页规则不变。

##### 23.22.3 前端请求与响应示例

客服正常保存（新增同样可带该应收对象）：

```http
PUT /api/v1/customer-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json

{"receivables":{"first_leg_fee":123.45,"total":1000}}
```

成功HTTP200响应片段，实际保留原完整业务字段：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":true,"receivables":{"first_leg_fee":123.45,"total":1000}},"msg":"委托信息更新成功"}
```

费用正常保存覆盖该金额：

```http
PUT /api/v1/cost-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json

{"receivables":{"first_leg_fee":200,"total":1076.55}}
```

成功HTTP200响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"receivables":{"first_leg_fee":200,"total":1076.55}},"msg":"单据信息更新成功"}
```

此时客服详情响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":false,"receivables":{"first_leg_fee":200,"total":1076.55}},"msg":"查询成功"}
```

两台列表的已保存金额在items中读取，例如费用 `GET /api/v1/cost-service/consignments?page=1&pageSize=10`，HTTP200片段：

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","status":1,"receivables":{"first_leg_fee":200,"total":1076.55}}],"page":1,"pageSize":10},"msg":"查询成功"}
```

金额置零请求为 `{"receivables":{"first_leg_fee":0}}`。客服明确清空用 `{"receivables":{"first_leg_fee":null}}`；费用传null沿用保留旧值规则。金额类型错误仍HTTP422、客服锁定/作废仍HTTP409、不存在单据404，其他原错误格式不变。

##### 23.22.4 Excel变更

| 接口 | 请求body | 新列位置及表头 | 总列数 |
|---|---|---|---|
| `POST /api/v1/customer-service/consignments/export-excel` | `{"ids":["358000000000000001"]}` | 第32列AF“一程费用”，前一列AE“应收耗材费”，后一列AG“国际空运代理名称” | 94，A至CP |
| `POST /api/v1/cost-service/consignments/export-excel` | 同上 | 第35列AI“一程费用”，前一列AH“应收耗材费”，后一列AJ“应收合计” | 118，A至DN |

成功HTTP200直接返回xlsx二进制，无JSON包裹，媒体类型为application/vnd.openxmlformats-officedocument.spreadsheetml.sheet。继续单行表头、数据从第2行开始，文件名及排序沿用原规则。金额读取本台已保存值，客服取自己的财务快照，费用取receivable_first_leg_fee；0为数值0，null/历史未填为空单元格，不写Excel公式。后续所有列顺延1列，委托航班日期仍第8列H，完整列映射同步更新23.11.9。

##### 23.22.5 数据库与部署

现有ORM及 `sql/migration_create_cost_service_consignments.sql` 已包含两张费用表的receivable_first_leg_fee，因此本次不新增字段、不重复ALTER TABLE；客服沿用financial_data JSON，不新增列。若需核查生产结构，可执行只读SQL：

```sql
SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE
FROM information_schema.COLUMNS
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME IN ('cost_registrations', 'cost_consignments')
  AND COLUMN_NAME = 'receivable_first_leg_fee';
```

应分别返回两张表该列，类型decimal(10,2)、可空。没有做生产数据库操作；历史金额不做回填或清空。先前锁定字段、财务快照等版本迁移仍须按对应发布说明完成，本次导出补列不替代那些迁移。


#### 23.23 客服新增及修改时国际空运主单号近30天查重（2026-11-11）

客服新增运单，在国际空运区录入主单号后点击“暂存”或“保存”，后端检查近30天客服运单的国际空运主单号；重复时拒绝写入并返回msg“该运单已存在”。按已确认口径，近30天使用系统创建时间；客服暂存后补填/更换号码也校验，排除当前运单自身。不新增单独查重接口，四个既有写入接口直接校验。

##### 23.23.1 受影响接口及请求参数

以下路径均包含 `/api/v1` 前缀，使用 `Authorization: Bearer <token>`，JSON请求使用 `Content-Type: application/json`。

| 方法 | 完整路径 | 本次变化 |
|---|---|---|
| POST | `/api/v1/customer-service/consignments` | 新增保存前检查国际空运主单号；不重复才创建客服并同步费用草稿 |
| POST | `/api/v1/customer-service/consignments/draft` | 新增暂存前同样检查；不重复才创建客服草稿 |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}` | 明确提交非空国际空运主单号时校验，排除本ID；不重复才更新并同步费用 |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}/draft` | 明确提交非空国际空运主单号时校验，排除本ID；不重复才更新客服草稿 |

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `payables` | body第一层 | object/null | 否 | 原应付款项分组 |
| `payables.intl_air` | body分组 | object/null | 否 | 原国际空运分组 |
| `payables.intl_air.flight_doc_no` | body分组叶字段 | string/null | 否 | 本次查重对象，国际空运主单号；不是顶层flight_doc_no，也不是提单或内部单据ID |
| `consignment_id` | path | string | PUT必填 | 当前客服运单数字字符串主键，用于排除自己；非数字、不存在沿用原400/404 |

其他请求字段保持原定义；不新增请求字段、前端时间参数、跳过校验开关或成功响应字段。未传号码时不将顶层委托主单号作为查重输入。

##### 23.23.2 匹配、时间和范围

- 以校验时的中国时间UTC+8计算 `[当前时间-30×24小时, 当前时间]` 闭区间，比较客服记录 `consignment_infos.created_at`。起点当天的具体时刻包含在内，不是自然月，也不按制单时间create_time、航班日期flight_date、进仓日期或最后修改时间updated_at判断。
- 检查客服接单台已有运单，跨账号，不按创建人过滤。包括暂存0、已保存1、作废2的仍存在记录；物理删除的记录不参与。费用保存后回写形成的客服记录也属于已有客服运单；只有费用草稿、没有客服记录的独立费用单不在本次范围内。模板不作为运单查重。
- 比较已有客服财务快照 `financial_data.payables.intl_air.flight_doc_no`。顶层委托主单号flight_doc_no、提单bill_of_lading、内部单据ID、国内空运/汽运主单号都不参与匹配，不查询费用表替代该字段。
- 采用完整号码相等判断，忽略首尾半角空格，英文字母不区分大小写。中间空格、连字符、前导0保留；百分号和下划线按普通字符参与相等比较，不是模糊查询通配符。例如784-001与784001、784-1是不同号码。
- 原始输入仍按原接口保存，不为查重改写用户填写的号码。未传、null、空字符串、仅半角空格时不触发号码查重；其保存/清空/保留语义沿用原接口。此规则不将国际空运主单号改为必填。
- PUT请求明确携带非空号码时触发检查（即使与当前值相同），排除当前单据ID。自己重存不冲突；其他近30天记录有同号则409。因此暂存后补填/更换同号也无法绕过。仅修改其他字段、未传该号码时不新加查重，以保留原部分更新行为；历史已有重复不做批量清理。
- 近30天以外的同号记录不阻止本次写入；旧记录今天编辑过也不会因此重新进入30天窗口。当前运单本身是否超过30天不影响“检查其他近30天记录”的规则。

##### 23.23.3 新增暂存、保存及修改请求示例

新增暂存：

```http
POST /api/v1/customer-service/consignments/draft
Authorization: Bearer <token>
Content-Type: application/json

{"customer_name":"客户A","payables":{"intl_air":{"flight_doc_no":"784-12345678"}}}
```

新增保存使用完全相同的body，路径改为 `POST /api/v1/customer-service/consignments`。此处填写的是国际空运区主单号，如同时传顶层flight_doc_no，顶层值不影响本次校验。

暂存新增后再次编辑/保存，使用返回的id调用PUT，不要再次POST创建另一条：

```http
PUT /api/v1/customer-service/consignments/358000000000000001
Authorization: Bearer <token>
Content-Type: application/json

{"payables":{"intl_air":{"flight_doc_no":"784-12345678"}}}
```

修改暂存使用 `PUT /api/v1/customer-service/consignments/358000000000000001/draft`。两种修改均排除当前ID。

##### 23.23.4 重复失败响应：前端弹窗契约

只要上述四个接口检测到重复，均返回 **HTTP 409 Conflict**，完整JSON如下（不是HTTP200，也不返回成功id）：

```json
{
  "code": 409,
  "data": null,
  "msg": "该运单已存在"
}
```

前端收到该响应后显示msg弹窗“该运单已存在”，本次暂存/保存失败，保留用户输入，不执行成功回调、不切换为已保存状态、不清空表单。PUT失败时已有数据、状态、客服editable、费用数据及操作记录均保持原值；POST失败时不新增客服/费用单据或操作记录。没有“一次修改机会”的消耗，修正号码后可再次提交。

409也可能是原有客服锁定或作废错误，前端应展示实际msg，不能把所有409都替换为“该运单已存在”。未找到单据404、数字ID错误400、请求类型校验422、认证错误均保留。费用已提交锁定或客服作废时仍优先返回原禁止编辑提示。

##### 23.23.5 不重复的成功响应

成功仍HTTP200、code=0，保留原完整业务字段。以下均为响应片段：

新增暂存成功：

```json
{"code":0,"data":{"id":"358000000000000001","status":0,"editable":true,"customer_name":"客户A","payables":{"intl_air":{"flight_doc_no":"784-12345678"}}},"msg":"委托信息暂存成功"}
```

新增保存成功：

```json
{"code":0,"data":{"id":"358000000000000001","status":1,"editable":true,"customer_name":"客户A","payables":{"intl_air":{"flight_doc_no":"784-12345678"}}},"msg":"委托信息创建成功"}
```

修改保存成功仍msg“委托信息更新成功”；修改暂存成功仍msg“委托信息暂存成功”。客服保存仍可编辑，费用保存提交后才锁定，查重不改变23.19的锁定时机。详情、列表、搜索及Excel响应结构不增加字段。

##### 23.23.6 并发、事务及数据库发布

同号客服写入使用数据库事务互斥键，覆盖多个服务进程；业务校验前结束认证/预检查产生的只读快照，获锁后重新查询近30天数据，避免MySQL默认REPEATABLE READ漏掉刚提交的同号运单。查重不锁历史运单或整段日期范围。号码检查、客服写入、费用同步及操作记录处在同一业务事务内；校验/数据库保存失败回滚，不留下运单或号码占用。数据库实际提交后网络响应丢失，仍需按已有id查询结果，不能按网络报错推断数据库已回滚。

范围为上述客服写入接口，费用接口和模板接口不新增查重拦截，不把这条规则扩展为系统所有写入口的永久唯一约束。历史有重复的数据仍保留；近30天之外同号可以重新录入。

**存量库上线前执行** `sql/migration_add_customer_intl_number_duplicate_check.sql`：

1. 创建 `consignment_number_guards` 事务互斥键表；该表仅保存规范化号码的SHA256用于事务行锁，不是运单数据，不会永久占用号码。
2. 在 `consignment_infos.created_at` 增加 `ix_consignment_infos_created_at` 索引，让服务器只在近30天范围内查JSON号码；不加载全部历史运单到应用内比较。

脚本CREATE TABLE可重跑；ALTER ADD INDEX仅执行一次。执行前可 `SHOW INDEX FROM consignment_infos`，若已有同名索引或以created_at为首列的索引，则跳过脚本中的ALTER。新库通过已更新建表SQL/ORM包含该表和索引，不再重复执行增量加索引。无需新增业务字段，不回填或覆盖financial_data、创建时间、历史状态及已有重复数据。本次没有执行生产SQL。


#### 23.24 两台委托信息区“一程重量”、列表回显及Excel（2026-11-11）

客服接单台、费用登记台的委托信息编辑区与列表区展示“一程重量”，两台Excel在委托信息区补列。复用已有 `first_leg_weight`；现有四张业务表、请求模型、保存/暂存、详情、列表及两台同步原本均已支持该字段，本次不新增同义字段，不迁移或改写历史重量。仓库没有前端页面代码，前端需按下方路径增加编辑输入框与列表列；后端补齐Excel导出并完善OpenAPI字段说明。

##### 23.24.1 参数、响应位置与保存规则

| 场景 | 参数或响应路径 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| 客服模板、新增、暂存、修改请求 | `first_leg_weight` | number/null | 否 | JSON body顶层的委托信息一程重量，例如120.5；不是应收一程费用 |
| 客服模板、单据写入与详情响应 | `data.first_leg_weight` | number/null | — | 数据库存储数值原样回显；历史未填写返回null；0返回数值0 |
| 客服列表响应 | `data.items[].first_leg_weight` | number/null | — | 每条客服记录自己的重量，前端增加“一程重量”列 |
| 费用模板、新增、暂存、修改请求 | `consignor_info.first_leg_weight` | number/null | 否 | 位于body的货主委托信息对象内，不接收为费用body顶层字段 |
| 费用模板、单据写入与详情响应 | `data.consignor_info.first_leg_weight` | number/null | — | 每条费用记录自己的重量，类型、精度同客服 |
| 费用列表响应 | `data.items[].consignor_info.first_leg_weight` | number/null | — | 前端按该嵌套路径渲染列表列 |

数据库沿用 `decimal(10,2)`，最多两位小数；前端按该存储精度录入和展示。后端不据此计算运费、一程费用、合计、利润或提成，也不将实际重量或计费重量自动写入本字段。`receivables.first_leg_fee`（一程费用）仍为另一个独立字段。

- 客服单据修改：未传 `first_leg_weight` 保留原值；显式null清空；0有效。客服唯一登记模板PUT沿用完整覆盖基础字段语义，未传该字段会置空，不等同于单据的部分修改。
- 费用模板/单据修改：未传 `consignor_info`、未传其中的 `first_leg_weight` 或显式null，均沿用原逻辑保留已存重量；0可保存覆盖。新建时未填或null保存为空。不因本次导出补列改变原数值字段的null规则。
- 客服正常保存同步到同ID费用单据；客服暂存只写客服。费用正常保存将该重量回写客服并锁定客服编辑；费用暂存只写费用。客服保存后仍可编辑，费用保存提交后才锁定；查重与作废规则继续有效。
- 详情、列表、导出均读取本台已保存值；费用暂存后两台重量可以暂时不同，不在读取或导出时强制覆盖。历史已存重量直接显示和导出；历史空值仍为空，不以其他重量回填。

##### 23.24.2 接口范围

下列路径均含 `/api/v1`，继续使用Bearer认证。JSON写入使用 `Content-Type: application/json`，不新增必填参数、独立接口或成功/失败码。

| 方法 | 客服接单台 | 费用登记台 | 本字段的使用 |
|---|---|---|---|
| GET、PUT | `/api/v1/customer-service/consignment-registration` | `/api/v1/cost-service/cost-registration` | 已有唯一编辑模板读取/保存支持本字段 |
| POST | `/api/v1/customer-service/consignments` | `/api/v1/cost-service/consignments` | 已有新增保存接收重量并按原流程同步 |
| POST | `/api/v1/customer-service/consignments/draft` | `/api/v1/cost-service/consignments/draft` | 已有新增暂存接收重量，只保存本台 |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}` | `/api/v1/cost-service/consignments/{consignment_id}` | 已有修改保存覆盖重量并同步 |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}/draft` | `/api/v1/cost-service/consignments/{consignment_id}/draft` | 已有修改暂存覆盖本台重量 |
| GET | `/api/v1/customer-service/consignments/{consignment_id}` | `/api/v1/cost-service/consignments/{consignment_id}` | 已有详情响应含本字段，供编辑区回显 |
| GET | `/api/v1/customer-service/consignments` | `/api/v1/cost-service/consignments` | 已有列表items含本字段；本次不新增按一程重量筛选/排序参数 |
| POST | `/api/v1/customer-service/consignments/export-excel` | `/api/v1/cost-service/consignments/export-excel` | 本次导出增加“一程重量”列，详见23.24.4 |

`consignment_id`仍为path中的数字字符串运单ID，既有未找到、作废、锁定、查重、认证、参数错误等响应不变。写入成功仍HTTP200、code=0；GET成功仍msg“查询成功”。

##### 23.24.3 前端请求和响应示例

客服新增暂存请求：

```http
POST /api/v1/customer-service/consignments/draft
Authorization: Bearer <token>
Content-Type: application/json

{"customer_name":"客户A","first_leg_weight":120.5,"actual_weight":180,"chargeable_weight":200,"receivables":{"first_leg_fee":123.45}}
```

HTTP200响应片段（实际保留原完整业务字段）：

```json
{"code":0,"data":{"id":"358000000000000001","status":0,"editable":true,"customer_name":"客户A","first_leg_weight":120.5,"actual_weight":180,"chargeable_weight":200,"receivables":{"first_leg_fee":123.45}},"msg":"委托信息暂存成功"}
```

客服后续保存使用 `PUT /api/v1/customer-service/consignments/358000000000000001`，例如body `{"first_leg_weight":0}`。修改成功msg“委托信息更新成功”，status=1、editable=true；相同ID费用详情中的 `consignor_info.first_leg_weight` 变为0。未传保持原值；客服body `{"first_leg_weight":null}` 可清空该重量。

费用修改暂存请求：

```http
PUT /api/v1/cost-service/consignments/358000000000000001/draft
Authorization: Bearer <token>
Content-Type: application/json

{"consignor_info":{"first_leg_weight":321.09}}
```

HTTP200响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":0,"consignor_info":{"first_leg_weight":321.09}},"msg":"单据信息暂存成功"}
```

费用正常保存使用不带 `/draft` 的PUT，body结构相同；成功msg“单据信息更新成功”，status=1，回写并锁定客服。费用body `{"consignor_info":{"first_leg_weight":null}}` 沿用保留原值，不能作为清空指令；0可覆盖。

列表响应片段（分页字段与完整业务对象保持原定义）：

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","first_leg_weight":120.5}],"page":1,"pageSize":10},"msg":"查询成功"}
```

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","consignor_info":{"first_leg_weight":321.09}}],"page":1,"pageSize":10},"msg":"查询成功"}
```

##### 23.24.4 Excel位置、数据及SQL

两个导出请求仍为 `{"ids":["358000000000000001"]}`，成功仍HTTP200、xlsx文件二进制，没有JSON包装；单行表头，第2行开始为数据。两台当前第7列G“提单”、第15列O“一程重量”、第16列P“备注”；完整委托段落按23.26节的新顺序排列。

| 导出 | 完整列数/范围 | 一程重量来源 | 应收一程费用的新坐标 |
|---|---|---|---|
| 客服 | 94列，A至CP | 本客服记录 `first_leg_weight`，对应 `data.first_leg_weight` | 第32列AF，`receivables.first_leg_fee` |
| 费用 | 118列，A至DN | 本费用记录 `first_leg_weight`，对应 `data.consignor_info.first_leg_weight` | 第35列AI，`receivables.first_leg_fee` |

历史120.5直接输出数值120.5；0输出数值0；null/未填写输出空单元格。不写公式、不重新计算、不修改单据或操作记录。完整列顺序及所有后续字段坐标已同步23.11.9节。

**本字段无需执行新增迁移SQL**：`consignment_registrations`、`consignment_infos`、`cost_registrations`、`cost_consignments` 及既有两台建表SQL均已有可空 `first_leg_weight decimal(10,2)`。可在发布前只读核对：

```sql
SHOW COLUMNS FROM `consignment_registrations` LIKE 'first_leg_weight';
SHOW COLUMNS FROM `consignment_infos` LIKE 'first_leg_weight';
SHOW COLUMNS FROM `cost_registrations` LIKE 'first_leg_weight';
SHOW COLUMNS FROM `cost_consignments` LIKE 'first_leg_weight';
```

四条各应返回对应的decimal(10,2)、可空列；不要重复ADD COLUMN或回填历史重量。本次未执行生产数据库操作。此前国际空运主单号查重的独立迁移仍按23.23节执行，不能用本字段“无需迁移”替代其他版本的发布步骤。


#### 23.25 两台委托航班号、国际空运联动及Excel（2026-11-11）

客服接单台、费用登记台的委托编辑区和列表展示“航班号”，位置在委托“航班日期”之后。复用现有基础字段 `flight_no`，两台Excel新增同名列。本次补齐客服本台国际空运快照及费用本台国际空运航班号的写入联动，覆盖模板、新增、暂存和保存。基础字段及国际空运字段已有数据库列，不新增业务字段，不批量改写历史数据。

##### 23.25.1 请求和返回字段

| 场景 | JSON路径 | 类型 | 必填 | 描述 |
|---|---|---|---|---|
| 客服模板、新增、暂存、修改请求 | `flight_no` | string/null | 否 | body顶层委托航班号，例如CZ1001；填写后同步本台国际空运航班号 |
| 客服详情及写入响应 | `data.flight_no` | string | — | 委托航班号，数据库未填/null沿用空字符串返回 |
| 客服列表 | `data.items[].flight_no` | string | — | 前端委托列表新增“航班号”列读取位置 |
| 费用模板、新增、暂存、修改请求 | `consignor_info.flight_no` | string/null | 否 | body货主委托分组中的航班号；不新增费用body顶层flight_no参数 |
| 费用详情及写入响应 | `data.consignor_info.flight_no` | string | — | 委托航班号，数据库未填/null沿用空字符串返回 |
| 费用列表 | `data.items[].consignor_info.flight_no` | string | — | 前端费用列表新增“航班号”列读取位置 |
| 两台国际空运请求/返回 | `payables.intl_air.flight_no` / `data.payables.intl_air.flight_no` | string/null | 否 | 同步目标；列表返回在 `data.items[].payables.intl_air.flight_no` |

沿用已有varchar(50)存储，前端按字段长度录入；不增加新的必填约束或改变错误响应格式。委托主单号flight_doc_no、航班日期flight_date、国内空运航班号及国际空运主单号均保持各自含义，不因本次航班号联动互相覆盖。

##### 23.25.2 联动、优先级及部分更新

1. **本次明确填写委托航班号时，委托值优先。** 客服请求 `flight_no="CZ1001"` 或费用请求 `consignor_info.flight_no="CZ1001"`，本台委托及国际空运航班号都保存为CZ1001。同一body还携带不同的 `payables.intl_air.flight_no` 时，仍以委托值为准，避免旧页面分组值把刚填写的委托值覆盖。
2. **空字符串也是明确输入。** 委托传 `""` 时，委托和本台国际空运航班号一并清空为 `""`；同次国际空运旧值或null均不能覆盖该清空。只存原始字符串，不擅自拆分、转换大小写或清洗航班号。
3. **未传或显式null不触发委托联动。** 单据修改未传委托航班号或传null，沿用原“保留委托原值”规则；本次仅改国际空运航班号时按原分组规则保存，允许与委托值不同。即使前端重复传入与当前值相同的非null委托值，也触发同步；如只希望修改国际空运，请不要同时传委托字段。
4. 客服唯一模板PUT仍完整覆盖基础字段：未传/null会将模板委托航班号置null，但不因该空值触发国际空运同步；国际分组按原快照合并规则处理。费用模板PUT仍按原部分更新语义，未传/null保留。前端不要将模板PUT与列表单据修改PUT混用。
5. 客服模板和客服暂存均同步本台国际空运快照；客服暂存不流转费用。客服正常保存仍同步同ID费用的委托和国际空运字段，费用仍待提交。费用模板和费用暂存同步本台国际空运；费用暂存不回写客服。费用正常保存将两处实际保存值回写客服并锁定客服编辑，后续费用暂存不解锁。
6. 只在写入时处理本次输入；GET详情、列表、Excel不补值、不做两字段强制一致。历史两处航班号不同或一处为空仍分别展示，未传委托的修改不会触发新的强制联动；客服保存原有国际空运预填规则仍保留。其他重量、日期、费用、标签、查重、作废、权限和操作记录规则不变。

**前端即时联动**：仓库没有前端页面代码，前端需在两台增加委托航班号输入框/列表列，并在该输入框变化时同步表单的 `payables.intl_air.flight_no`。后端在上述写入接口做同样的保存兜底；仅调用GET无法实现用户键入时的实时页面联动。

##### 23.25.3 涉及接口

全部使用原Bearer认证和JSON body，不新增URL。以下既有接口新增上述委托航班号联动行为：

| 方法 | 客服接口 | 费用接口 |
|---|---|---|
| PUT | `/api/v1/customer-service/consignment-registration` | `/api/v1/cost-service/cost-registration` |
| POST | `/api/v1/customer-service/consignments` | `/api/v1/cost-service/consignments` |
| POST | `/api/v1/customer-service/consignments/draft` | `/api/v1/cost-service/consignments/draft` |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}` | `/api/v1/cost-service/consignments/{consignment_id}` |
| PUT | `/api/v1/customer-service/consignments/{consignment_id}/draft` | `/api/v1/cost-service/consignments/{consignment_id}/draft` |

原GET模板、`GET /api/v1/{customer-service或cost-service}/consignments/{consignment_id}` 详情和不带ID的GET列表，继续返回上述既有字段及相同分页结构。新增/暂存的请求字段位置相同，数字字符串path参数consignment_id沿用原规则。锁定/作废409、近30天国际空运主单号重复409、找不到404、非法数字ID400、认证与类型校验错误均不变。

两个 `POST /api/v1/customer-service/consignments/export-excel`、`POST /api/v1/cost-service/consignments/export-excel` 变更Excel布局，见23.25.5。

##### 23.25.4 请求与响应示例

客服新增暂存，同次国际空运值不同时委托值优先：

```http
POST /api/v1/customer-service/consignments/draft
Authorization: Bearer <token>
Content-Type: application/json

{"customer_name":"客户A","flight_no":"CZ1001","payables":{"intl_air":{"flight_no":"旧国际航班号"}}}
```

HTTP200响应片段；实际保留原完整业务字段：

```json
{"code":0,"data":{"id":"358000000000000001","status":0,"editable":true,"flight_no":"CZ1001","payables":{"intl_air":{"flight_no":"CZ1001"}}},"msg":"委托信息暂存成功"}
```

客服后续保存使用 `PUT /api/v1/customer-service/consignments/358000000000000001`，body可为 `{"flight_no":"CZ1002"}`；成功status=1、editable=true、msg“委托信息更新成功”，本台及费用两处航班号均变为CZ1002。

费用修改暂存：

```http
PUT /api/v1/cost-service/consignments/358000000000000001/draft
Authorization: Bearer <token>
Content-Type: application/json

{"consignor_info":{"flight_no":"CZ1003"},"payables":{"intl_air":{"flight_no":"CZ1002"}}}
```

HTTP200响应片段：

```json
{"code":0,"data":{"id":"358000000000000001","status":0,"consignor_info":{"flight_no":"CZ1003"},"payables":{"intl_air":{"flight_no":"CZ1003"}}},"msg":"单据信息暂存成功"}
```

该费用暂存不改客服原值或编辑权限。费用使用不带 `/draft` 的PUT正常保存时，两处实际值回写客服并锁定，成功status=1、msg“单据信息更新成功”。新建保存成功msg仍分别为“委托信息创建成功”和“单据信息创建成功”；暂存成功msg沿用原定义。

客服和费用列表HTTP200响应片段分别为：

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","flight_no":"CZ1002","payables":{"intl_air":{"flight_no":"CZ1002"}}}],"page":1,"pageSize":10},"msg":"查询成功"}
```

```json
{"code":0,"data":{"total":1,"items":[{"id":"358000000000000001","consignor_info":{"flight_no":"CZ1003"},"payables":{"intl_air":{"flight_no":"CZ1003"}}}],"page":1,"pageSize":10},"msg":"查询成功"}
```

##### 23.25.5 Excel、历史数据和SQL

两台第8列H“航班日期”、**第9列I“航班号”**、第10列J“主单号”；第9列读取本台基础委托flight_no。保留国际空运与国内空运原“航班号”列，各读自身分组字段；不按同名表头去重，不用国际空运值替代历史委托值。

| 导出 | 总列数/范围 | 委托航班号 | 国际空运航班号 | 国内空运航班号 |
|---|---|---|---|---|
| 客服 | 94，A至CP | 第9列I，`flight_no` | 第37列AK，`payables.intl_air.flight_no` | 第87列CI，`payables.dom_air.flight_no` |
| 费用 | 118，A至DN | 第9列I，`consignor_info.flight_no` | 第41列AO，`payables.intl_air.flight_no` | 第99列CU，`payables.dom_air.flight_no` |

委托段落按23.26节的新顺序排列，单行表头、数据从第2行开始。委托“一程重量”顺延至第15列O；应收“一程费用”顺延至客服第32列AF、费用第35列AI，完整列顺序及所有列号已更新23.11.9节。历史已存委托航班号直接回显和导出，未填为空单元格，不从国际空运/国内空运回填。Excel导出请求仍 `{"ids":["358000000000000001"]}`，成功HTTP200、xlsx二进制，无JSON包装；导出不修改单据、状态或操作记录。

**无需新增字段迁移SQL**。四张既有表均已有基础 `flight_no varchar(50)`，费用模板和单据表也已有 `pay_intl_air_flight_no varchar(50)`；客服国际空运仍存financial_data快照。可只读核对：

```sql
SHOW COLUMNS FROM `consignment_registrations` LIKE 'flight_no';
SHOW COLUMNS FROM `consignment_infos` LIKE 'flight_no';
SHOW COLUMNS FROM `cost_registrations` LIKE 'flight_no';
SHOW COLUMNS FROM `cost_consignments` LIKE 'flight_no';
SHOW COLUMNS FROM `cost_registrations` LIKE 'pay_intl_air_flight_no';
SHOW COLUMNS FROM `cost_consignments` LIKE 'pay_intl_air_flight_no';
```

本次不重复ADD COLUMN、不回填历史差异、不执行生产数据库操作。此前版本独立迁移仍按各自发布说明执行。


#### 23.26 两台Excel委托信息段落列顺序调整（2026-11-11）

客服接单台、费用登记台导出Excel的前16列统一按本节排列。产品表中的空白项/`<br>`不作为一列，“序号”仍在最前。仅重新排列委托信息字段，列数不增加：客服仍94列A至CP、费用仍118列A至DN。第17列起的应收、各应付分组、费用汇总等字段及顺序保持当前完整列契约；23.11.9的两张完整映射表已同步更新。

##### 23.26.1 接口、请求及响应

| 方法 | 完整接口路径 | 变化 |
|---|---|---|
| POST | `/api/v1/customer-service/consignments/export-excel` | xlsx响应中委托信息前16列重排，字段对应数据一起移动 |
| POST | `/api/v1/cost-service/consignments/export-excel` | 与客服采用相同的委托信息列顺序 |

沿用 `Authorization: Bearer <token>` 和 `Content-Type: application/json`。请求仍为：

```http
POST /api/v1/customer-service/consignments/export-excel
Authorization: Bearer <token>
Content-Type: application/json

{"ids":["358000000000000001","358000000000000002"]}
```

费用导出使用费用接口，body结构相同。

| 参数 | 位置 | 类型 | 必填 | 说明 |
|---|---|---|---|---|
| `ids` | JSON body顶层 | array of string | 是 | 选中的数字字符串运单ID数组，例如上例；不是内部单据ID。不新增查询/排序参数。非法参数继续沿用原400/422等响应 |

成功仍为HTTP200的xlsx二进制文件，**没有JSON code/data/msg包装，也不是JSON数组**。响应头示例：

```http
HTTP/1.1 200 OK
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename=consignment_export_20261111103000.xlsx
Access-Control-Expose-Headers: Content-Disposition
```

费用文件名前缀仍为 `cost_consignment_export_`，实际时间由服务端生成。前端继续按blob下载，不需要构造本次列顺序；认证、参数错误等失败响应仍为原JSON格式。

##### 23.26.2 两台统一的委托信息前16列

| 列号 | Excel列 | 表头 | 客服详情data来源 | 费用详情data来源 |
|---|---|---|---|---|
| 1 | A | 序号 | 按最终导出行顺序从1生成 | 同左 |
| 2 | B | 状态 | `status` | `status` |
| 3 | C | 进仓日期 | `warehouse_entry_date` | `consignor_info.warehouse_entry_date` |
| 4 | D | 客户名称 | `customer_name` | `consignor_info.customer_name` |
| 5 | E | 始发站-目的站 | `origin_destination` | `consignor_info.origin_destination` |
| 6 | F | 报关 | `customs_declaration` | `consignor_info.customs_declaration` |
| 7 | G | 提单 | `bill_of_lading` | `consignor_info.bill_of_lading` |
| 8 | H | 航班日期 | `flight_date` | `consignor_info.flight_date` |
| 9 | I | 航班号 | `flight_no` | `consignor_info.flight_no` |
| 10 | J | 主单号 | `flight_doc_no` | `consignor_info.flight_doc_no` |
| 11 | K | 件数 | `pieces` | `consignor_info.pieces` |
| 12 | L | 实际重量 | `actual_weight` | `consignor_info.actual_weight` |
| 13 | M | 计费重量 | `chargeable_weight` | `consignor_info.chargeable_weight` |
| 14 | N | 体积 | `volume` | `consignor_info.volume` |
| 15 | O | 一程重量 | `first_leg_weight` | `consignor_info.first_leg_weight` |
| 16 | P | 备注 | `remark` | `consignor_info.remark` |

示例文件第1行前16个单元格：

```text
序号 | 状态 | 进仓日期 | 客户名称 | 始发站-目的站 | 报关 | 提单 | 航班日期 | 航班号 | 主单号 | 件数 | 实际重量 | 计费重量 | 体积 | 一程重量 | 备注
```

与之对应的第2行示例：

```text
1 | 已提交 | 2026-09-13 | 客户A | SZX-NRT | 1买单+3单证 | 直单 | 2026-09-16 | MF809 | 731-90064074 | 36 | 123.25 | 125 | 1.25 | 120.5 | 备注内容
```

##### 23.26.3 保留的业务行为与部署

仍只有一行表头，第2行起为数据，无新增空白列或分组标题。表头和对应取值共用有序定义，两台均按上述顺序输出，避免只移动表头造成串列。状态继续显示未提交/已提交/作废，提单按原编码转中文；日期显示YYYY-MM-DD，数值0保留，未填留空。

本次只重排列，不调整记录的导出排序：客服按原制单时间倒序，费用按委托航班日期升序、空日期最后、同日ID升序。两台读取各自已存值，委托与国际/国内空运的航班号、日期继续各取所属字段；财务各分组坐标不变，一程费用仍为客服第32列AF、费用第35列AI。

保存、暂存、两台同步、委托航班号联动、编辑锁定、主单号查重、详情/列表及其筛选条件均不因本次Excel列重排改变。导出过程不改写历史单据或操作记录，**无需新增数据库迁移SQL**。此前版本独立迁移仍按各自说明执行；本次未执行生产数据库操作。
