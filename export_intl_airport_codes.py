"""
国际机场三字代码抓取与导出脚本

功能：
- 遍历 infoccsp 接口（共456页），获取全量 9117 条国际机场信息
- 导出 JSON 数据字典文件：intl_airport_three_letter_code.json (供后台数据字典导入)
- 导出 Excel 文件：国际机场三字代码.xlsx (包含 机场代码, 机场四字码, 中文名, 英文名, 城市代码, 城市名称, 国家和地区, 国内/国际 8项数据)

使用方法：
    python export_intl_airport_codes.py
    # 或自定义导出路径与并发数
    python export_intl_airport_codes.py --json-output intl_airport_three_letter_code.json --excel-output 国际机场三字代码.xlsx --workers 6
"""

import sys
import json
import time
import argparse
import requests
import pandas as pd
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup

# 调整 Windows 控制台输出编码，防止打印特殊字符报错
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_URL = "https://www.infoccsp.com/iportal/ajax/servicecenter/ajaxsearchairportbycondition.aspx"
DEFAULT_TOTAL_PAGES = 456
DEFAULT_JSON_FILE = "intl_airport_three_letter_code.json"
DEFAULT_EXCEL_FILE = "国际机场三字代码.xlsx"

HEADERS = {
    "Accept": "text/plain, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.infoccsp.com",
    "Pragma": "no-cache",
    "Referer": "https://www.infoccsp.com/iportal/servicecenter/airport.aspx",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/150.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    'sec-ch-ua': '"Not;A=Brand";v="8", "Chromium";v="150", "Google Chrome";v="150"',
    "sec-ch-ua-mobile": "?0",
    'sec-ch-ua-platform': '"Windows"',
}


def clean_text(text: str) -> str:
    """清洗文本，去除全角空格、\\r\\n、Tab及首尾空格"""
    if not text:
        return ""
    cleaned = (
        text.replace("\u3000", " ")
        .replace("\xa0", " ")
        .replace("\r", "")
        .replace("\n", "")
        .replace("\t", "")
    )
    return cleaned.strip()


def fetch_page(page_index: int, max_retries: int = 5) -> list:
    """请求单页数据并解析返回全量字段"""
    expected_count = 17 if page_index == DEFAULT_TOTAL_PAGES else 20

    payload_dict = {
        "Condition": {
            "Code": "",
            "Airport4Code": "",
            "Name_CN": "",
            "DI": "I",  # 'I' 代表国际
        },
        "Pagination": {"CurrentPageIndex": page_index, "PageSize": 20},
    }

    payload = {"optData": json.dumps(payload_dict, ensure_ascii=False)}

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(
                API_URL, headers=HEADERS, data=payload, timeout=15
            )
            if resp.status_code == 200:
                html_text = resp.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html_text, "html.parser")
                rows = soup.select("#pagingList tr")

                page_items = []
                for row in rows:
                    code_elem = row.find("span", {"name": "AirportCode"})
                    code4_elem = row.find("span", {"name": "Airport4Code"})
                    name_elem = row.find("span", {"name": "Name"})
                    continent_elem = row.find("span", {"name": "Continent"})
                    city_elem = row.find("span", {"name": "City"})
                    city_cn_elem = row.find("span", {"name": "CityName_CN"})
                    country_elem = row.find("span", {"name": "CountryName_CN"})
                    di_elem = row.find("span", {"name": "DI"})

                    airport_code = clean_text(code_elem.text) if code_elem else ""
                    airport4_code = clean_text(code4_elem.text) if code4_elem else ""
                    name_cn = clean_text(name_elem.text) if name_elem else ""
                    name_en = clean_text(continent_elem.text) if continent_elem else ""
                    city_code = clean_text(city_elem.text) if city_elem else ""
                    city_name_cn = clean_text(city_cn_elem.text) if city_cn_elem else ""
                    country_cn = clean_text(country_elem.text) if country_elem else ""
                    di_type = clean_text(di_elem.text) if di_elem else "国际"

                    if airport_code:
                        page_items.append({
                            "AirportCode": airport_code,
                            "Airport4Code": airport4_code,
                            "Name": name_cn,
                            "Continent": name_en,
                            "City": city_code,
                            "CityName_CN": city_name_cn,
                            "CountryName_CN": country_cn,
                            "DI": di_type
                        })

                if len(page_items) == expected_count:
                    return page_items
                else:
                    print(
                        f"[Warn] 第 {page_index} 页数量不匹配 (获取 {len(page_items)}/{expected_count} 条)，正在重试 ({attempt}/{max_retries})..."
                    )
            else:
                print(f"[Warn] 第 {page_index} 页响应异常 HTTP status: {resp.status_code}")
        except Exception as e:
            if attempt == max_retries:
                print(f"[Error] 第 {page_index} 页抓取失败 (重试 {max_retries} 次): {e}")
        
        time.sleep(1)

    return []


def main():
    parser = argparse.ArgumentParser(description="抓取国际机场三字代码导出为JSON及Excel")
    parser.add_argument(
        "--json-output",
        "-j",
        default=DEFAULT_JSON_FILE,
        help=f"导出的JSON文件名 (默认: {DEFAULT_JSON_FILE})",
    )
    parser.add_argument(
        "--excel-output",
        "-e",
        default=DEFAULT_EXCEL_FILE,
        help=f"导出的Excel文件名 (默认: {DEFAULT_EXCEL_FILE})",
    )
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=DEFAULT_TOTAL_PAGES,
        help=f"抓取总页数 (默认: {DEFAULT_TOTAL_PAGES})",
    )
    parser.add_argument(
        "--workers",
        "-w",
        type=int,
        default=6,
        help="并发线程数 (默认: 6)",
    )
    args = parser.parse_args()

    total_pages = args.pages
    json_output_file = args.json_output
    excel_output_file = args.excel_output
    max_workers = args.workers

    print(f"=== 开始抓取国际机场数据 (共 {total_pages} 页, 并发线程数: {max_workers}) ===")

    all_results = {}
    completed_count = 0
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page = {
            executor.submit(fetch_page, p): p for p in range(1, total_pages + 1)
        }

        for future in as_completed(future_to_page):
            page_num = future_to_page[future]
            completed_count += 1
            try:
                items = future.result()
                all_results[page_num] = items
            except Exception as e:
                print(f"[Error] 解析第 {page_num} 页失败: {e}")

            if completed_count % 20 == 0 or completed_count == total_pages:
                elapsed = time.time() - start_time
                print(
                    f"[进度] 已处理 {completed_count}/{total_pages} 页 ({completed_count / total_pages * 100:.1f}%) | 耗时: {elapsed:.1f}s"
                )

    # 按照页码顺序汇总所有抓取结果
    all_items = []
    for p in sorted(all_results.keys()):
        all_items.extend(all_results[p])

    # 1. 构建字典 JSON 格式数据
    json_options = []
    seen_values = set()

    for item in all_items:
        val = item["AirportCode"]
        city_cn = item["CityName_CN"]
        name_cn = item["Name"]
        label = city_cn if city_cn else (name_cn if name_cn else val)

        if val not in seen_values:
            seen_values.add(val)
            json_options.append({
                "label": label,
                "value": val,
                "status": 1
            })

    dict_data = {
        "dict_type": {
            "name": "国际机场三字代码",
            "type": "intl_airport_three_letter_code",
            "status": 1,
        },
        "options": json_options,
    }

    # 写入 JSON 文件
    json_path = Path(json_output_file)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(dict_data, f, ensure_ascii=False, indent=4)

    # 2. 构建 Excel 数据表
    excel_rows = []
    for item in all_items:
        excel_rows.append({
            "机场代码": item["AirportCode"],
            "机场四字码": item["Airport4Code"],
            "中文名": item["Name"],
            "英文名": item["Continent"],
            "城市代码": item["City"],
            "城市名称": item["CityName_CN"],
            "国家和地区": item["CountryName_CN"],
            "国内/国际": item["DI"]
        })

    df = pd.DataFrame(excel_rows)
    excel_path = Path(excel_output_file)
    df.to_excel(excel_path, index=False, engine="openpyxl")

    total_time = time.time() - start_time
    print(f"\n=== 抓取与导出完成！ ===")
    print(f"数据总页数: {total_pages}")
    print(f"抓取记录总条数: {len(all_items)}")
    print(f"JSON 字典文件已保存至: {json_path.resolve()}")
    print(f"Excel 数据文件已保存至: {excel_path.resolve()}")
    print(f"总耗时: {total_time:.2f} 秒")


if __name__ == "__main__":
    main()
