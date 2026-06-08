import io
import re

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the bullet point list
content = content.replace(
    "- `SHENZHEN_AIR_TRANSIT_LOADING`: 深航过机-装机数据获取",
    "- `SHENZHEN_AIR_TRANSIT_LOADING`: 深航过机-装机数据获取\n    - `SHENZHEN_AIR_APPROVAL_DATA`: 深航订舱-批复数据获取"
)

# Replace the JSON array
content = re.sub(
    r'("value": "SHENZHEN_AIR_TRANSIT_LOADING",\s*"label": "SHENZHEN_AIR_TRANSIT_LOADING",\s*"description": "深航过机-装机数据获取"\s*})',
    r'\1,\n            {\n                "value": "SHENZHEN_AIR_APPROVAL_DATA",\n                "label": "SHENZHEN_AIR_APPROVAL_DATA",\n                "description": "深航订舱-批复数据获取"\n            }',
    content
)

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content)
print("Replaced successfully")
