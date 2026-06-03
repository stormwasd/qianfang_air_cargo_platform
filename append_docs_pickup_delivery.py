import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_docs = """
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
"""

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content + new_docs)
print('Updated API_DOCS.md with Pickup and Delivery Unit Management')
