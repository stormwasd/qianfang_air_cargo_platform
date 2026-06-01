import re
import os

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

# I need to add "creator_id" and "creator_name" to the Customer response JSONs.
# Searching for `"is_invoiced": true,` and replacing with `"is_invoiced": true,\n        "creator_id": "987654321",\n        "creator_name": "张三",`
# Be careful because `is_invoiced` might be true or false.

content = re.sub(
    r'("is_invoiced": (?:true|false))',
    r'\1,\n        "creator_id": "987654321",\n        "creator_name": "张三"',
    content
)

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated API_DOCS.md with Customer creator fields')
