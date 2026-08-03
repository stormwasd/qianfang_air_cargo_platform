"""
国际机场三字代码抓取与导出脚本

功能：
- 遍历 infoccsp 接口（共456页），获取全量国际机场三字代码及其对应中文城市/名称
- 按照项目统一的数据字典结构生成 intl_airport_three_letter_code.json
- 支持多线程并发与自动重试机制，抓取高效且稳定

使用方法：
    python export_intl_airport_codes.py
    # 或指定输出路径
    python export_intl_airport_codes.py --output intl_airport_three_letter_code.json
"""

import sys
import json
import time
import argparse
import requests
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
DEFAULT_OUTPUT_FILE = "intl_airport_three_letter_code.json"

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
    """清洗文本，包含去除全角空格、\r\n、Tab及首尾空格"""
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


def fetch_page(page_index: int, max_retries: int = 3) -> list:
    """请求单页数据并解析返回的列表项"""
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
                API_URL, headers=HEADERS, data=payload, timeout=12
            )
            if resp.status_code == 200:
                html_text = resp.content.decode("utf-8", errors="ignore")
                soup = BeautifulSoup(html_text, "html.parser")
                rows = soup.select("#pagingList tr")

                page_items = []
                for row in rows:
                    code_elem = row.find("span", {"name": "AirportCode"})
                    city_elem = row.find("span", {"name": "CityName_CN"})
                    name_elem = row.find("span", {"name": "Name"})

                    airport_code = clean_text(code_elem.text) if code_elem else ""
                    city_name = clean_text(city_elem.text) if city_elem else ""
                    name_cn = clean_text(name_elem.text) if name_elem else ""

                    # label 优先使用 CityName_CN（城市名称），若为空则降级使用 Name（中文名）
                    label = city_name if city_name else name_cn

                    if airport_code and label:
                        page_items.append(
                            {"label": label, "value": airport_code, "status": 1}
                        )

                return page_items
            else:
                print(f"[Warn] 第 {page_index} 页响应异常 HTTP status: {resp.status_code}")
        except Exception as e:
            if attempt == max_retries:
                print(f"[Error] 第 {page_index} 页抓取失败 (重试 {max_retries} 次): {e}")
            else:
                time.sleep(1)

    return []


def main():
    parser = argparse.ArgumentParser(description="抓取国际机场三字代码导出为JSON字典")
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT_FILE,
        help=f"导出的JSON文件名 (默认: {DEFAULT_OUTPUT_FILE})",
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
        default=8,
        help="并发线程数 (默认: 8)",
    )
    args = parser.parse_args()

    total_pages = args.pages
    output_file = args.output
    max_workers = args.workers

    print(f"=== 开始抓取国际机场三字代码 (共 {total_pages} 页, 并发线程数: {max_workers}) ===")

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
    raw_options = []
    for p in sorted(all_results.keys()):
        raw_options.extend(all_results[p])

    # 去重处理（相同 airport_code 保留首次出现的数据）
    unique_options = []
    seen_values = set()

    for item in raw_options:
        val = item["value"]
        if val not in seen_values:
            seen_values.add(val)
            unique_options.append(item)

    dict_data = {
        "dict_type": {
            "name": "国际机场三字代码",
            "type": "intl_airport_three_letter_code",
            "status": 1,
        },
        "options": unique_options,
    }

    # 写入 JSON 文件
    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dict_data, f, ensure_ascii=False, indent=4)

    total_time = time.time() - start_time
    print(f"\n=== 抓取完成！ ===")
    print(f"数据总页数: {total_pages}")
    print(f"抓取记录条数: {len(raw_options)}")
    print(f"去重后选项数: {len(unique_options)}")
    print(f"文件已保存至: {output_path.resolve()}")
    print(f"总耗时: {total_time:.2f} 秒")


if __name__ == "__main__":
    main()
