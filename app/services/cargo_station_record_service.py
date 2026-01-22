"""
货站录单服务

用于处理深圳航空和南方航空的货站录单功能：

深圳航空：
1. 根据waybill数据填充Excel模板（交接单、航空货物明细表、货物收运检查清单、充氧类水生动物货物收运检查单）
2. 将Excel转换为PDF（使用纯Python方案：openpyxl + reportlab）
3. 保存文件到指定目录
4. 更新waybill的cargo_station_record_status字段
5. 注意：充氧类水生动物货物收运检查单只有当 form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要生成

南方航空：
1. 只有当 form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要进行货站录单
2. 只需要处理一个docx文件（充氧类水生动物货物收运检查单.docx）
3. 不需要转换为PDF，直接提供docx下载
4. 更新waybill的cargo_station_record_status字段
"""
import os
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import MergedCell

from app.utils.airport_code_mapper import get_city_name_by_code


# 文件存储根目录（相对于项目根目录）
GENERATED_FILES_DIR = "generated_files"

# 深航货站录单文件子目录
SHENZHEN_AIR_CARGO_STATION_DIR = "shenzhen_air_cargo_station"
# 南航货站录单文件子目录
CHINA_SOUTHERN_AIR_CARGO_STATION_DIR = "china_southern_air_cargo_station"

# 深航Excel模板目录（相对于项目根目录）
TEMPLATE_DIR = "documents/shenzhen_air"
# 南航模板目录（相对于项目根目录）
CHINA_SOUTHERN_AIR_TEMPLATE_DIR = "documents/china_southern_air"

# ======== 深航文档类型常量 ========
DOC_TYPE_HANDOVER = "handover"  # 交接单
DOC_TYPE_CARGO_DETAIL = "cargo_detail"  # 航空货物明细表
DOC_TYPE_CARGO_CHECKLIST = "cargo_checklist"  # 货物收运检查清单
DOC_TYPE_AQUATIC_ANIMAL_CHECKLIST = "aquatic_animal_checklist"  # 充氧类水生动物货物收运检查单（深航Excel版）

# ======== 南航文档类型常量 ========
DOC_TYPE_CSA_AQUATIC_ANIMAL_CHECKLIST = "csa_aquatic_animal_checklist"  # 南航充氧类水生动物货物收运检查单（docx版）

# 深航文档类型到文件名的映射
DOC_TYPE_TO_FILENAME = {
    DOC_TYPE_HANDOVER: "交接单",
    DOC_TYPE_CARGO_DETAIL: "航空货物明细表",
    DOC_TYPE_CARGO_CHECKLIST: "货物收运检查清单",
    DOC_TYPE_AQUATIC_ANIMAL_CHECKLIST: "充氧类水生动物货物收运检查单",
}

# 南航文档类型到文件名的映射
CSA_DOC_TYPE_TO_FILENAME = {
    DOC_TYPE_CSA_AQUATIC_ANIMAL_CHECKLIST: "充氧类水生动物货物收运检查单",
}


def _get_project_root() -> Path:
    """获取项目根目录"""
    # 从当前文件位置向上三级就是项目根目录
    # app/services/cargo_station_record_service.py -> app/services -> app -> 项目根目录
    return Path(__file__).parent.parent.parent


def _ensure_waybill_dir(waybill_id: int) -> Path:
    """
    确保waybill的文件存储目录存在
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        waybill的文件存储目录路径
    """
    project_root = _get_project_root()
    waybill_dir = project_root / GENERATED_FILES_DIR / SHENZHEN_AIR_CARGO_STATION_DIR / str(waybill_id)
    waybill_dir.mkdir(parents=True, exist_ok=True)
    return waybill_dir


def _parse_flight_date(flight_date: str) -> Tuple[str, str, str]:
    """
    解析航班日期，返回年、月、日
    
    Args:
        flight_date: 航班日期字符串，格式如 "2025-01-15" 或 "2025/01/15"
    
    Returns:
        元组 (year, month, day)
    """
    if not flight_date:
        return "", "", ""
    
    # 尝试多种日期格式
    date_str = flight_date.strip()
    
    # 替换可能的分隔符
    date_str = date_str.replace("/", "-")
    
    parts = date_str.split("-")
    if len(parts) == 3:
        year = parts[0]
        month = parts[1].lstrip("0") or "0"  # 去除前导零，但保留至少一个字符
        day = parts[2].lstrip("0") or "0"
        return year, month, day
    
    return "", "", ""


def _replace_cell_value(ws: Worksheet, search_value: str, replace_value: str) -> int:
    """
    在工作表中查找并替换单元格值
    
    Args:
        ws: 工作表对象
        search_value: 要查找的值
        replace_value: 替换后的值
    
    Returns:
        替换的单元格数量
    """
    replaced_count = 0
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                cell_str = str(cell.value)
                if search_value in cell_str:
                    # 执行替换
                    cell.value = cell_str.replace(search_value, replace_value)
                    replaced_count += 1
    return replaced_count


def _convert_excel_to_pdf(excel_path: Path, pdf_path: Path) -> bool:
    """
    将Excel文件转换为PDF（纯Python实现）
    
    使用openpyxl读取Excel内容，使用reportlab生成PDF
    
    Args:
        excel_path: Excel文件路径
        pdf_path: 输出PDF文件路径
    
    Returns:
        是否转换成功
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm, cm
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        
        # 尝试注册中文字体
        chinese_font_name = "SimSun"
        font_registered = False
        
        # 尝试常见的中文字体路径
        font_paths = [
            "C:/Windows/Fonts/simsun.ttc",  # Windows
            "C:/Windows/Fonts/simhei.ttf",  # Windows
            "C:/Windows/Fonts/msyh.ttc",    # Windows 微软雅黑
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
            "/System/Library/Fonts/PingFang.ttc",  # macOS
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    if font_path.endswith('.ttc'):
                        pdfmetrics.registerFont(TTFont(chinese_font_name, font_path, subfontIndex=0))
                    else:
                        pdfmetrics.registerFont(TTFont(chinese_font_name, font_path))
                    font_registered = True
                    break
                except Exception:
                    continue
        
        if not font_registered:
            # 如果没有找到中文字体，使用默认字体（可能无法显示中文）
            chinese_font_name = "Helvetica"
            print(f"警告：未找到中文字体，PDF中的中文可能无法正确显示")
        
        # 加载Excel文件
        wb = load_workbook(excel_path)
        ws = wb.active
        
        # 获取Excel数据
        data = []
        merge_cells_info = []  # 存储合并单元格信息
        
        # 获取合并单元格信息
        for merged_range in ws.merged_cells.ranges:
            merge_cells_info.append({
                'min_row': merged_range.min_row,
                'max_row': merged_range.max_row,
                'min_col': merged_range.min_col,
                'max_col': merged_range.max_col
            })
        
        # 获取实际使用的行列范围
        max_row = ws.max_row
        max_col = ws.max_column
        
        # 读取数据
        for row_idx in range(1, max_row + 1):
            row_data = []
            for col_idx in range(1, max_col + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                # 跳过合并单元格中非左上角的单元格
                cell_value = ""
                if isinstance(cell, MergedCell):
                    # 查找这个单元格属于哪个合并区域，获取主单元格的值
                    for merge_info in merge_cells_info:
                        if (merge_info['min_row'] <= row_idx <= merge_info['max_row'] and
                            merge_info['min_col'] <= col_idx <= merge_info['max_col']):
                            if row_idx == merge_info['min_row'] and col_idx == merge_info['min_col']:
                                # 这是合并区域的左上角
                                main_cell = ws.cell(row=merge_info['min_row'], column=merge_info['min_col'])
                                cell_value = str(main_cell.value) if main_cell.value is not None else ""
                            break
                else:
                    cell_value = str(cell.value) if cell.value is not None else ""
                row_data.append(cell_value)
            data.append(row_data)
        
        wb.close()
        
        # 如果没有数据，返回失败
        if not data:
            print(f"Excel文件没有数据: {excel_path}")
            return False
        
        # 创建PDF文档（使用横向A4）
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=landscape(A4),
            rightMargin=10*mm,
            leftMargin=10*mm,
            topMargin=10*mm,
            bottomMargin=10*mm
        )
        
        # 创建样式
        styles = getSampleStyleSheet()
        
        # 创建中文段落样式
        chinese_style = ParagraphStyle(
            'Chinese',
            parent=styles['Normal'],
            fontName=chinese_font_name,
            fontSize=8,
            leading=10,
            wordWrap='CJK',
        )
        
        # 将数据转换为Paragraph对象以支持自动换行
        table_data = []
        for row in data:
            row_paragraphs = []
            for cell in row:
                if cell:
                    p = Paragraph(str(cell), chinese_style)
                else:
                    p = Paragraph("", chinese_style)
                row_paragraphs.append(p)
            table_data.append(row_paragraphs)
        
        # 计算列宽（根据页面宽度平均分配）
        page_width = landscape(A4)[0] - 20*mm  # 减去左右边距
        if max_col > 0:
            col_width = page_width / max_col
            col_widths = [col_width] * max_col
        else:
            col_widths = None
        
        # 创建表格
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        
        # 创建表格样式
        style_commands = [
            ('FONTNAME', (0, 0), (-1, -1), chinese_font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        
        # 处理合并单元格
        for merge_info in merge_cells_info:
            row_span = merge_info['max_row'] - merge_info['min_row'] + 1
            col_span = merge_info['max_col'] - merge_info['min_col'] + 1
            
            if row_span > 1 or col_span > 1:
                # reportlab使用0索引
                start_row = merge_info['min_row'] - 1
                start_col = merge_info['min_col'] - 1
                end_row = merge_info['max_row'] - 1
                end_col = merge_info['max_col'] - 1
                
                style_commands.append(
                    ('SPAN', (start_col, start_row), (end_col, end_row))
                )
        
        table.setStyle(TableStyle(style_commands))
        
        # 构建PDF
        elements = [table]
        doc.build(elements)
        
        return True
        
    except ImportError as e:
        print(f"缺少必要的库: {str(e)}")
        print("请安装 reportlab: pip install reportlab")
        return False
    except Exception as e:
        import traceback
        print(f"Excel转PDF失败: {str(e)}")
        print(f"错误详情: {traceback.format_exc()}")
        return False


def generate_handover_document(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Tuple[Path, Path]:
    """
    生成交接单文档
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        元组 (Excel文件路径, PDF文件路径)
    """
    project_root = _get_project_root()
    template_path = project_root / TEMPLATE_DIR / "交接单.xlsx"
    
    # 确保目录存在
    waybill_dir = _ensure_waybill_dir(waybill_id)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    excel_filename = f"交接单_{timestamp}.xlsx"
    pdf_filename = f"交接单_{timestamp}.pdf"
    excel_path = waybill_dir / excel_filename
    pdf_path = waybill_dir / pdf_filename
    
    # 复制模板到目标目录
    shutil.copy2(template_path, excel_path)
    
    # 加载Excel文件
    wb = load_workbook(excel_path)
    ws = wb.active
    
    # 提取数据
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    
    flight_number = flight_info.get("flight_number", "")
    destination_code = flight_info.get("destination", "")
    destination_city = get_city_name_by_code(destination_code)
    flight_date = flight_info.get("flight_date", "")
    year, month, day = _parse_flight_date(flight_date)
    
    quantity = str(cargo_info.get("quantity", ""))
    weight = str(cargo_info.get("weight", ""))
    chargeable_weight = str(cargo_info.get("chargeable_weight", ""))
    cargo_name = str(cargo_info.get("cargo_name", ""))
    package = str(cargo_info.get("package", ""))
    
    # 从业务参数配置中获取shipper_or_agent
    shenzhen_air_config = business_config.get("shenzhen_air", {})
    document_config = shenzhen_air_config.get("document", {})
    domestic_cargo_checklist = document_config.get("domestic_cargo_checklist", {})
    shipper_or_agent = domestic_cargo_checklist.get("shipper_or_agent", "")
    
    # 执行替换（按照用户指定的替换规则）
    _replace_cell_value(ws, "ZH9929", flight_number)
    _replace_cell_value(ws, "济南", destination_city)
    _replace_cell_value(ws, "2025", year)
    _replace_cell_value(ws, "10", month)
    _replace_cell_value(ws, "7", day)
    _replace_cell_value(ws, "110", quantity)
    _replace_cell_value(ws, "400", weight)
    _replace_cell_value(ws, "600", chargeable_weight)
    _replace_cell_value(ws, "拉链 背光源 鞋子 塑胶壳 海报 螺丝 线路板 服装 显示器 广告画 布匹 纸巾 数据线 鞋 内存卡 五金件 塑胶件 支撑架 画册 说明书 手机屏 贴膜 电源模块 五金模具 线材 (内含氧化银电池364SR621SW，根据特殊规定A123，不受限制）", cargo_name)
    _replace_cell_value(ws, "纸箱", package)
    _replace_cell_value(ws, "唐文旭", shipper_or_agent)
    _replace_cell_value(ws, "479-57515651", waybill_number)
    
    # 保存Excel文件
    wb.save(excel_path)
    wb.close()
    
    # 转换为PDF
    _convert_excel_to_pdf(excel_path, pdf_path)
    
    return excel_path, pdf_path


def generate_cargo_detail_document(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Tuple[Path, Path]:
    """
    生成航空货物明细表文档
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        元组 (Excel文件路径, PDF文件路径)
    """
    project_root = _get_project_root()
    template_path = project_root / TEMPLATE_DIR / "航空货物明细表.xlsx"
    
    # 确保目录存在
    waybill_dir = _ensure_waybill_dir(waybill_id)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    excel_filename = f"航空货物明细表_{timestamp}.xlsx"
    pdf_filename = f"航空货物明细表_{timestamp}.pdf"
    excel_path = waybill_dir / excel_filename
    pdf_path = waybill_dir / pdf_filename
    
    # 复制模板到目标目录
    shutil.copy2(template_path, excel_path)
    
    # 加载Excel文件
    wb = load_workbook(excel_path)
    ws = wb.active
    
    # 提取数据
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    
    flight_number = flight_info.get("flight_number", "")
    flight_date = flight_info.get("flight_date", "")
    year, month, day = _parse_flight_date(flight_date)
    
    quantity = str(cargo_info.get("quantity", ""))
    weight = str(cargo_info.get("weight", ""))
    
    # 执行替换（按照用户指定的替换规则）
    _replace_cell_value(ws, "ZH9949", flight_number)
    _replace_cell_value(ws, "479-57110642", waybill_number)
    _replace_cell_value(ws, "18", quantity)
    _replace_cell_value(ws, "296", weight)
    _replace_cell_value(ws, "2025", year)
    _replace_cell_value(ws, "12", month)
    _replace_cell_value(ws, "11", day)
    
    # 保存Excel文件
    wb.save(excel_path)
    wb.close()
    
    # 转换为PDF
    _convert_excel_to_pdf(excel_path, pdf_path)
    
    return excel_path, pdf_path


def generate_cargo_checklist_document(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Tuple[Path, Path]:
    """
    生成货物收运检查清单文档
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        元组 (Excel文件路径, PDF文件路径)
    """
    project_root = _get_project_root()
    template_path = project_root / TEMPLATE_DIR / "货物收运检查清单.xlsx"
    
    # 确保目录存在
    waybill_dir = _ensure_waybill_dir(waybill_id)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    excel_filename = f"货物收运检查清单_{timestamp}.xlsx"
    pdf_filename = f"货物收运检查清单_{timestamp}.pdf"
    excel_path = waybill_dir / excel_filename
    pdf_path = waybill_dir / pdf_filename
    
    # 复制模板到目标目录
    shutil.copy2(template_path, excel_path)
    
    # 加载Excel文件
    wb = load_workbook(excel_path)
    ws = wb.active
    
    # 提取数据
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    
    flight_number = flight_info.get("flight_number", "")
    destination_code = flight_info.get("destination", "")
    destination_city = get_city_name_by_code(destination_code)
    flight_date = flight_info.get("flight_date", "")
    year, month, day = _parse_flight_date(flight_date)
    
    quantity = str(cargo_info.get("quantity", ""))
    weight = str(cargo_info.get("weight", ""))
    chargeable_weight = str(cargo_info.get("chargeable_weight", ""))
    cargo_name = str(cargo_info.get("cargo_name", ""))
    package = str(cargo_info.get("package", ""))
    
    # 执行替换（按照用户指定的替换规则）
    _replace_cell_value(ws, "ZH9929", flight_number)
    _replace_cell_value(ws, "济南", destination_city)
    _replace_cell_value(ws, "2025", year)
    _replace_cell_value(ws, "10", month)
    _replace_cell_value(ws, "7", day)
    _replace_cell_value(ws, "110", quantity)
    _replace_cell_value(ws, "400", weight)
    _replace_cell_value(ws, "600", chargeable_weight)
    _replace_cell_value(ws, "拉链 背光源 鞋子 塑胶壳 海报 螺丝 线路板 服装 显示器 广告画 布匹 纸巾 数据线 鞋 内存卡 五金件 塑胶件 支撑架 画册 说明书 手机屏 贴膜 电源模块 五金模具 线材 (内含氧化银电池364SR621SW，根据特殊规定A123，不受限制）", cargo_name)
    _replace_cell_value(ws, "纸箱", package)
    _replace_cell_value(ws, "479-57515651", waybill_number)
    
    # 保存Excel文件
    wb.save(excel_path)
    wb.close()
    
    # 转换为PDF
    _convert_excel_to_pdf(excel_path, pdf_path)
    
    return excel_path, pdf_path


def generate_aquatic_animal_checklist_document(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Tuple[Path, Path]:
    """
    生成充氧类水生动物货物收运检查单文档
    
    注意：此文档只有当 form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要生成
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        元组 (Excel文件路径, PDF文件路径)
    """
    project_root = _get_project_root()
    template_path = project_root / TEMPLATE_DIR / "充氧类水生动物货物收运检查单.xlsx"
    
    # 确保目录存在
    waybill_dir = _ensure_waybill_dir(waybill_id)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    excel_filename = f"充氧类水生动物货物收运检查单_{timestamp}.xlsx"
    pdf_filename = f"充氧类水生动物货物收运检查单_{timestamp}.pdf"
    excel_path = waybill_dir / excel_filename
    pdf_path = waybill_dir / pdf_filename
    
    # 复制模板到目标目录
    shutil.copy2(template_path, excel_path)
    
    # 加载Excel文件
    wb = load_workbook(excel_path)
    ws = wb.active
    
    # 提取数据
    flight_info = form_data.get("flight_info", {})
    cargo_info = form_data.get("cargo_info", {})
    shipper_consignee_info = form_data.get("shipper_consignee_info", {})
    
    # 获取托运单位
    shipper_unit = shipper_consignee_info.get("shipper_unit", "")
    
    # 航班信息
    flight_number = flight_info.get("flight_number", "")
    destination_code = flight_info.get("destination", "")
    destination_city = get_city_name_by_code(destination_code)
    flight_date = flight_info.get("flight_date", "")
    year, month, day = _parse_flight_date(flight_date)
    
    # 货物信息
    quantity = str(cargo_info.get("quantity", ""))
    weight = str(cargo_info.get("weight", ""))
    
    # 执行替换（按照用户指定的替换规则）
    _replace_cell_value(ws, "深圳丰德航空物流有限公司", shipper_unit)
    _replace_cell_value(ws, "2025", year)
    _replace_cell_value(ws, "13", month)
    _replace_cell_value(ws, "15", day)
    _replace_cell_value(ws, "479-58405616", waybill_number)
    _replace_cell_value(ws, "14", quantity)
    _replace_cell_value(ws, "128", weight)
    _replace_cell_value(ws, "CA4314", flight_number)
    _replace_cell_value(ws, "成都", destination_city)
    
    # 保存Excel文件
    wb.save(excel_path)
    wb.close()
    
    # 转换为PDF
    _convert_excel_to_pdf(excel_path, pdf_path)
    
    return excel_path, pdf_path


def generate_all_documents(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    生成所有货站录单文档
    
    根据 form_data 中的配置决定生成哪些文档：
    - 交接单（必生成）
    - 航空货物明细表（必生成）
    - 货物收运检查清单（必生成）
    - 充氧类水生动物货物收运检查单（仅当 oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时生成）
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        生成结果字典，格式如：
        {
            "handover": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "cargo_detail": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "cargo_checklist": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "aquatic_animal_checklist": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"}  # 仅当开关为"0"时
        }
    """
    results = {}
    
    # 生成交接单
    try:
        excel_path, pdf_path = generate_handover_document(
            waybill_id, waybill_number, form_data, business_config
        )
        results[DOC_TYPE_HANDOVER] = {
            "excel": str(excel_path),
            "pdf": str(pdf_path) if pdf_path.exists() else None
        }
    except Exception as e:
        print(f"生成交接单失败: {str(e)}")
        results[DOC_TYPE_HANDOVER] = {"excel": None, "pdf": None, "error": str(e)}
    
    # 生成航空货物明细表
    try:
        excel_path, pdf_path = generate_cargo_detail_document(
            waybill_id, waybill_number, form_data, business_config
        )
        results[DOC_TYPE_CARGO_DETAIL] = {
            "excel": str(excel_path),
            "pdf": str(pdf_path) if pdf_path.exists() else None
        }
    except Exception as e:
        print(f"生成航空货物明细表失败: {str(e)}")
        results[DOC_TYPE_CARGO_DETAIL] = {"excel": None, "pdf": None, "error": str(e)}
    
    # 生成货物收运检查清单
    try:
        excel_path, pdf_path = generate_cargo_checklist_document(
            waybill_id, waybill_number, form_data, business_config
        )
        results[DOC_TYPE_CARGO_CHECKLIST] = {
            "excel": str(excel_path),
            "pdf": str(pdf_path) if pdf_path.exists() else None
        }
    except Exception as e:
        print(f"生成货物收运检查清单失败: {str(e)}")
        results[DOC_TYPE_CARGO_CHECKLIST] = {"excel": None, "pdf": None, "error": str(e)}
    
    # 生成充氧类水生动物货物收运检查单（仅当开关为"0"时生成）
    # 注意：oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 表示需要生成
    aquatic_switch = form_data.get("oxygenated_aquatic_animal_goods_receipt_inspection_form_switch", "1")
    if aquatic_switch == "0":
        try:
            excel_path, pdf_path = generate_aquatic_animal_checklist_document(
                waybill_id, waybill_number, form_data, business_config
            )
            results[DOC_TYPE_AQUATIC_ANIMAL_CHECKLIST] = {
                "excel": str(excel_path),
                "pdf": str(pdf_path) if pdf_path.exists() else None
            }
        except Exception as e:
            print(f"生成充氧类水生动物货物收运检查单失败: {str(e)}")
            results[DOC_TYPE_AQUATIC_ANIMAL_CHECKLIST] = {"excel": None, "pdf": None, "error": str(e)}
    
    return results


def get_document_path(
    waybill_id: int,
    doc_type: str,
    file_format: str = "pdf"
) -> Optional[Path]:
    """
    获取指定运单的指定文档路径
    
    Args:
        waybill_id: 运单ID
        doc_type: 文档类型 (handover, cargo_detail, cargo_checklist, aquatic_animal_checklist)
        file_format: 文件格式 (pdf 或 excel)
    
    Returns:
        文件路径，如果不存在则返回None
    """
    project_root = _get_project_root()
    waybill_dir = project_root / GENERATED_FILES_DIR / SHENZHEN_AIR_CARGO_STATION_DIR / str(waybill_id)
    
    if not waybill_dir.exists():
        return None
    
    # 获取文档名称前缀
    doc_name = DOC_TYPE_TO_FILENAME.get(doc_type)
    if not doc_name:
        return None
    
    # 确定文件扩展名
    extension = ".pdf" if file_format == "pdf" else ".xlsx"
    
    # 查找最新的文件（按时间戳排序）
    matching_files = list(waybill_dir.glob(f"{doc_name}_*{extension}"))
    if not matching_files:
        return None
    
    # 按文件名排序（时间戳在文件名中，所以字典序即时间序）
    matching_files.sort(reverse=True)
    return matching_files[0]


def list_documents(waybill_id: int) -> Dict[str, Dict[str, Optional[str]]]:
    """
    列出指定运单的所有已生成文档（深航）
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        文档列表字典，格式如：
        {
            "handover": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "cargo_detail": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "cargo_checklist": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"},
            "aquatic_animal_checklist": {"excel": "/path/to/excel", "pdf": "/path/to/pdf"}
        }
    """
    results = {}
    
    # 遍历所有文档类型
    for doc_type in [DOC_TYPE_HANDOVER, DOC_TYPE_CARGO_DETAIL, DOC_TYPE_CARGO_CHECKLIST, DOC_TYPE_AQUATIC_ANIMAL_CHECKLIST]:
        excel_path = get_document_path(waybill_id, doc_type, "excel")
        pdf_path = get_document_path(waybill_id, doc_type, "pdf")
        
        # 只有当文件存在时才添加到结果中
        if excel_path or pdf_path:
            results[doc_type] = {
                "excel": str(excel_path) if excel_path else None,
                "pdf": str(pdf_path) if pdf_path else None
            }
    
    return results


# ======== 南航货站录单相关函数 ========

def _ensure_csa_waybill_dir(waybill_id: int) -> Path:
    """
    确保南航waybill的文件存储目录存在
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        waybill的文件存储目录路径
    """
    project_root = _get_project_root()
    waybill_dir = project_root / GENERATED_FILES_DIR / CHINA_SOUTHERN_AIR_CARGO_STATION_DIR / str(waybill_id)
    waybill_dir.mkdir(parents=True, exist_ok=True)
    return waybill_dir


def _replace_text_in_docx(doc_path: Path, search_text: str, replace_text: str) -> int:
    """
    在docx文件中替换文本
    
    使用python-docx库处理docx文件
    
    Args:
        doc_path: docx文件路径
        search_text: 要查找的文本
        replace_text: 替换后的文本
    
    Returns:
        替换的数量
    """
    try:
        from docx import Document
    except ImportError:
        raise ImportError("需要安装 python-docx 库: pip install python-docx")
    
    doc = Document(doc_path)
    replaced_count = 0
    
    # 遍历所有段落
    for para in doc.paragraphs:
        if search_text in para.text:
            # 处理段落中的runs
            for run in para.runs:
                if search_text in run.text:
                    run.text = run.text.replace(search_text, replace_text)
                    replaced_count += 1
            # 如果runs中没找到，可能文本被分割了，需要特殊处理
            if replaced_count == 0 and search_text in para.text:
                # 合并所有runs的文本，替换后重新设置
                full_text = para.text
                new_text = full_text.replace(search_text, replace_text)
                if full_text != new_text:
                    # 清空所有runs
                    for run in para.runs:
                        run.text = ""
                    # 在第一个run中设置新文本
                    if para.runs:
                        para.runs[0].text = new_text
                    replaced_count += 1
    
    # 遍历所有表格
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if search_text in para.text:
                        for run in para.runs:
                            if search_text in run.text:
                                run.text = run.text.replace(search_text, replace_text)
                                replaced_count += 1
                        # 如果runs中没找到
                        if replaced_count == 0 and search_text in para.text:
                            full_text = para.text
                            new_text = full_text.replace(search_text, replace_text)
                            if full_text != new_text:
                                for run in para.runs:
                                    run.text = ""
                                if para.runs:
                                    para.runs[0].text = new_text
                                replaced_count += 1
    
    doc.save(doc_path)
    return replaced_count


def generate_csa_aquatic_animal_checklist_document(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Path:
    """
    生成南航充氧类水生动物货物收运检查单文档（docx格式）
    
    注意：此文档只有当 form_data.oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要生成
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        生成的docx文件路径
    """
    project_root = _get_project_root()
    template_path = project_root / CHINA_SOUTHERN_AIR_TEMPLATE_DIR / "充氧类水生动物货物收运检查单.docx"
    
    if not template_path.exists():
        raise FileNotFoundError(f"南航模板文件不存在: {template_path}")
    
    # 确保目录存在
    waybill_dir = _ensure_csa_waybill_dir(waybill_id)
    
    # 生成带时间戳的文件名
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    docx_filename = f"充氧类水生动物货物收运检查单_{timestamp}.docx"
    docx_path = waybill_dir / docx_filename
    
    # 复制模板到目标目录
    shutil.copy2(template_path, docx_path)
    
    # 执行替换（按照用户指定的替换规则）
    # "784- 44697343" 替换为 waybill_number
    _replace_text_in_docx(docx_path, "784- 44697343", waybill_number)
    
    return docx_path


def generate_csa_all_documents(
    waybill_id: int,
    waybill_number: str,
    form_data: dict,
    business_config: dict
) -> Dict[str, Dict[str, Optional[str]]]:
    """
    生成南航所有货站录单文档
    
    南航货站录单只有当 oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要生成
    只需要生成一个文档：充氧类水生动物货物收运检查单.docx
    
    Args:
        waybill_id: 运单ID
        waybill_number: 运单号
        form_data: 运单表单数据
        business_config: 业务参数配置
    
    Returns:
        生成结果字典，格式如：
        {
            "csa_aquatic_animal_checklist": {"docx": "/path/to/docx"}
        }
    """
    results = {}
    
    # 检查开关，只有为"0"时才需要生成
    aquatic_switch = form_data.get("oxygenated_aquatic_animal_goods_receipt_inspection_form_switch", "1")
    if aquatic_switch != "0":
        # 开关不为"0"，南航不需要货站录单
        return results
    
    # 生成充氧类水生动物货物收运检查单
    try:
        docx_path = generate_csa_aquatic_animal_checklist_document(
            waybill_id, waybill_number, form_data, business_config
        )
        results[DOC_TYPE_CSA_AQUATIC_ANIMAL_CHECKLIST] = {
            "docx": str(docx_path)
        }
    except Exception as e:
        print(f"生成南航充氧类水生动物货物收运检查单失败: {str(e)}")
        results[DOC_TYPE_CSA_AQUATIC_ANIMAL_CHECKLIST] = {"docx": None, "error": str(e)}
    
    return results


def get_csa_document_path(
    waybill_id: int,
    doc_type: str,
    file_format: str = "docx"
) -> Optional[Path]:
    """
    获取指定南航运单的指定文档路径
    
    Args:
        waybill_id: 运单ID
        doc_type: 文档类型 (csa_aquatic_animal_checklist)
        file_format: 文件格式 (docx)
    
    Returns:
        文件路径，如果不存在则返回None
    """
    project_root = _get_project_root()
    waybill_dir = project_root / GENERATED_FILES_DIR / CHINA_SOUTHERN_AIR_CARGO_STATION_DIR / str(waybill_id)
    
    if not waybill_dir.exists():
        return None
    
    # 获取文档名称前缀
    doc_name = CSA_DOC_TYPE_TO_FILENAME.get(doc_type)
    if not doc_name:
        return None
    
    # 确定文件扩展名
    extension = ".docx"
    
    # 查找最新的文件（按时间戳排序）
    matching_files = list(waybill_dir.glob(f"{doc_name}_*{extension}"))
    if not matching_files:
        return None
    
    # 按文件名排序（时间戳在文件名中，所以字典序即时间序）
    matching_files.sort(reverse=True)
    return matching_files[0]


def list_csa_documents(waybill_id: int) -> Dict[str, Dict[str, Optional[str]]]:
    """
    列出指定南航运单的所有已生成文档
    
    Args:
        waybill_id: 运单ID
    
    Returns:
        文档列表字典，格式如：
        {
            "csa_aquatic_animal_checklist": {"docx": "/path/to/docx"}
        }
    """
    results = {}
    
    # 遍历南航文档类型
    for doc_type in [DOC_TYPE_CSA_AQUATIC_ANIMAL_CHECKLIST]:
        docx_path = get_csa_document_path(waybill_id, doc_type, "docx")
        
        # 只有当文件存在时才添加到结果中
        if docx_path:
            results[doc_type] = {
                "docx": str(docx_path) if docx_path else None
            }
    
    return results


def is_csa_cargo_station_record_required(form_data: dict) -> bool:
    """
    判断南航是否需要进行货站录单
    
    只有当 oxygenated_aquatic_animal_goods_receipt_inspection_form_switch 为 "0" 时才需要
    
    Args:
        form_data: 运单表单数据
    
    Returns:
        是否需要进行货站录单
    """
    aquatic_switch = form_data.get("oxygenated_aquatic_animal_goods_receipt_inspection_form_switch", "1")
    return aquatic_switch == "0"
