"""
承运人信息抓取与导出脚本

功能：
- 遍历 infoccsp 承运人信息接口（共21页），获取全量 406 条承运人数据
- 导出 Excel 文件：承运人信息.xlsx
  数据列包含：承运人代码、运单前缀、承运人简称、中文名、英文名

使用方法：
    python export_carrier_info.py
    # 或自定义导出路径与并发数
    python export_carrier_info.py --output 承运人信息.xlsx --workers 4
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

# 调整 Windows 控制台输出编码
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

API_URL = "https://www.infoccsp.com/iportal/ajax/servicecenter/ajaxsearchcarrierbycondition.aspx"
DEFAULT_TOTAL_PAGES = 21
DEFAULT_OUTPUT_FILE = "承运人信息.xlsx"

HEADERS = {
    "Accept": "text/plain, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "Origin": "https://www.infoccsp.com",
    "Pragma": "no-cache",
    "Referer": "https://www.infoccsp.com/iportal/servicecenter/carrier.aspx",
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
    """清洗文本，包含去除全角空格、\\r\\n、Tab及首尾空格"""
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
    """请求单页承运人数据并解析返回的列表项"""
    expected_count = 6 if page_index == DEFAULT_TOTAL_PAGES else 20

    payload_dict = {
        "Condition": {
            "Code": "",
            "AWBPre": "",
            "Name_CN": "",
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
                    code_elem = row.find("span", {"name": "CarrierCode"})
                    prefix_elem = row.find("span", {"name": "AwbPrefix"})
                    short_elem = row.find("span", {"name": "ShortName"})
                    cn_elem = row.find("span", {"name": "Name_Cn"})
                    en_elem = row.find("span", {"name": "Name_En"})

                    carrier_code = clean_text(code_elem.text) if code_elem else ""
                    awb_prefix = clean_text(prefix_elem.text) if prefix_elem else ""
                    short_name = clean_text(short_elem.text) if short_elem else ""
                    name_cn = clean_text(cn_elem.text) if cn_elem else ""
                    name_en = clean_text(en_elem.text) if en_elem else ""

                    page_items.append({
                        "承运人代码": carrier_code,
                        "运单前缀": awb_prefix,
                        "承运人简称": short_name,
                        "中文名": name_cn,
                        "英文名": name_en,
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
    parser = argparse.ArgumentParser(description="抓取承运人信息导出为Excel表格")
    parser.add_argument(
        "--output",
        "-o",
        default=DEFAULT_OUTPUT_FILE,
        help=f"导出的Excel文件名 (默认: {DEFAULT_OUTPUT_FILE})",
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
        default=4,
        help="并发线程数 (默认: 4)",
    )
    args = parser.parse_args()

    total_pages = args.pages
    output_file = args.output
    max_workers = args.workers

    print(f"=== 开始抓取承运人信息 (共 {total_pages} 页, 并发线程数: {max_workers}) ===")

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

            print(
                f"[进度] 已处理 {completed_count}/{total_pages} 页 ({completed_count / total_pages * 100:.1f}%)"
            )

    # 按照页码顺序汇总所有抓取结果
    all_rows = []
    for p in sorted(all_results.keys()):
        all_rows.extend(all_results[p])

    # 导出到 Excel
    df = pd.DataFrame(all_rows)
    output_path = Path(output_file)
    df.to_excel(output_path, index=False, engine="openpyxl")

    total_time = time.time() - start_time
    print(f"\n=== 抓取与导出完成！ ===")
    print(f"数据总页数: {total_pages}")
    print(f"抓取记录总条数: {len(all_rows)}")
    print(f"Excel 文件已保存至: {output_path.resolve()}")
    print(f"总耗时: {total_time:.2f} 秒")


if __name__ == "__main__":
    main()
