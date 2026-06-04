import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_docs = """
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
"""

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content + new_docs)
print('Updated API_DOCS.md with Consignment Notes Docs')
