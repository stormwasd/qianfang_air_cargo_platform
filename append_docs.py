import os

new_docs = """

---

### 14. 客户管理（三期需求）

#### 14.1 新增客户（三期扩展）

**接口地址**: `POST /api/v1/customers`

**请求头**: `Authorization: Bearer <token>`

**请求参数**:

```json
{
  "company_name": "千方航空",
  "settlement_method": "月结",
  "rate": 15.5,
  "contact_person": "张三",
  "contact_phone": "13800138000",
  "minimum_ticket_fee": 100.0,
  "document_fee": 50.0,
  "minimum_ticket_fee_condition": "低于100kg收取",
  "document_fee_condition": "每票必收",
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
  "settlement_cycle": "月结",
  "is_invoiced": true
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
    "settlement_method": "月结",
    "rate": 15.5,
    "contact_person": "张三",
    "contact_phone": "13800138000",
    "minimum_ticket_fee": 100.0,
    "document_fee": 50.0,
    "minimum_ticket_fee_condition": "低于100kg收取",
    "document_fee_condition": "每票必收",
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
    "settlement_cycle": "月结",
    "is_invoiced": true,
    "created_at": "2026-06-01T12:00:00+08:00",
    "updated_at": "2026-06-01T12:00:00+08:00"
  },
  "msg": "客户创建成功"
}
```

**说明**：`customer_code` 由系统自动生成（规则：公司名拼音首字母大写 + 当日日期 YYYYMMDD）。

#### 14.2 编辑客户信息（三期扩展）

**接口地址**: `PUT /api/v1/customers/{customer_id}`

**请求参数**: 支持部分字段更新，参数结构与 `POST` 相同。允许对三期新增字段置空或传 `null` 进行清空。

#### 14.3 获取客户详情与列表（三期扩展）

**接口地址**: `GET /api/v1/customers` / `GET /api/v1/customers/{customer_id}`

**响应示例**: 返回的数据体中增加了三期所有的字段（包含 `customer_code`, JSON 配置字典等），字段结构与新增时的请求体保持一致。
"""

with open('API_DOCS.md', 'a', encoding='utf-8') as f:
    f.write(new_docs)

print("Successfully appended to API_DOCS.md")
