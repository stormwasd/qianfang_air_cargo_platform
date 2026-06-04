import re

with open('API_DOCS.md', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace in JSON examples (both request and response)
# We find line containing "oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "xxx"
# and add "pickup_method": "1" after it.
content = re.sub(
    r'("oxygenated_aquatic_animal_goods_receipt_inspection_form_switch": "(?:0|1)"(?:,)?(?:  // [^\n]*)?)',
    r'\1\n      "pickup_method": "1"',
    content
)

# Also find parameter table descriptions to add the field description
# We look for `- **oxygenated_aquatic_animal_goods_receipt_inspection_form_switch**` and add `- **pickup_method**` below it.
content = re.sub(
    r'(- \*\*oxygenated_aquatic_animal_goods_receipt_inspection_form_switch\*\*.*)',
    r'\1\n    - **pickup_method**：可选。提货方式（独立字段，不参与RPA开单）',
    content
)

with open('API_DOCS.md', 'w', encoding='utf-8') as f:
    f.write(content)
print('Updated API_DOCS.md successfully.')
