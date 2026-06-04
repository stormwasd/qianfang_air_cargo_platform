import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

new_docs = """
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
"""

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content + new_docs)
print('Updated API_DOCS.md with Weather Service')
