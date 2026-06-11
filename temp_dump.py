import pandas as pd
import json
import math

df = pd.read_excel('d:/Personal/qianfang_air_cargo_platform/订舱查询与处理.xlsx', header=None)

def clean(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return str(v)

data = [[clean(v) for v in row] for row in df.head(10).values.tolist()]

with open('temp_excel_dump.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
