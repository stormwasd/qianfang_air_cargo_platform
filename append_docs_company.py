import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_docs = """
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

#### 15.2 新增公司账户

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

#### 15.3 编辑公司账户

**接口地址**: `PUT /api/v1/companies/accounts/{account_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。

#### 15.4 获取公司账户详情

**接口地址**: `GET /api/v1/companies/accounts/{account_id}`

**响应示例**: 同新增账户返回的 `data` 结构。

#### 15.5 删除公司账户

**接口地址**: `DELETE /api/v1/companies/accounts/{account_id}`

**响应示例**:

```json
{
  "code": 0,
  "data": null,
  "msg": "公司账户删除成功"
}
```
"""

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content + new_docs)
print('Updated API_DOCS.md with Company Management')
