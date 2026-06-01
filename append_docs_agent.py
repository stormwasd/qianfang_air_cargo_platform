import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_docs = """
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
"""

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content + new_docs)
print('Updated API_DOCS.md with Agent Management')
