from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from typing import List, Dict, Any, Optional
import json
import re
from datetime import date, datetime

from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response

# 导入所有相关模型
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.models.departure_manual_data import ShenzhenAirDepartureManualData
from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
from app.models.csa_departure_tracking import CsaLalamoveInformation
from app.models.csa_departure_manual_data import CsaDepartureManualData
from app.models.consignment_note import ConsignmentNote
from app.models.peer_air_manual_data import PeerAirDepartureManualData
from app.models.air_financial_audit_data import AirFinancialAuditData
from app.models.customer import Customer
from app.models.waybill import Waybill

# 导入 Schemas
from app.schemas.financial_audit import (
    AirFinancialAuditQuery,
    AirFinancialAuditDataUpsert,
    AirFinancialAuditItemResponse,
    PayableResponse,
    ReceivableResponse
)

router = APIRouter()

# ----------------- Helper Functions -----------------

def safe_float(val: Any) -> float:
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        # 移除非数字字符（保留小数点、负号）
        cleaned = re.sub(r'[^\d\.\-]', '', str(val))
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0

def safe_int(val: Any) -> int:
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    try:
        cleaned = re.sub(r'[^\d\-]', '', str(val))
        return int(cleaned) if cleaned else 0
    except ValueError:
        return 0

def safe_str(val: Any) -> str:
    return str(val) if val is not None else ""

def format_decimal(val: float) -> str:
    return f"{val:.2f}"

def parse_csa_qty_weight(billing_qty: str):
    """
    解析南航制单数量，格式如 '25 / 236 / 1.41 (0 / 0 / 0)'
    返回 (pieces_str, weight_str)
    """
    if not billing_qty:
        return "", ""
    parts = [p.strip() for p in billing_qty.split('/')]
    pieces = parts[0] if len(parts) > 0 else ""
    weight = parts[1] if len(parts) > 1 else ""
    return pieces, weight

def parse_csa_flight_info(flight_info: str):
    """
    解析南航航班信息，格式如 'CZ8577 / 2026-06-16 / SZX - WUH'
    返回 (flight_number, flight_date, origin, destination)
    """
    if not flight_info:
        return "", "", "", ""
    parts = [p.strip() for p in flight_info.split('/')]
    flight_number = parts[0] if len(parts) > 0 else ""
    flight_date = parts[1].replace('/', '-') if len(parts) > 1 else ""
    route_str = parts[2] if len(parts) > 2 else ""
    origin, destination = "", ""
    if route_str and '-' in route_str:
        route_parts = [r.strip() for r in route_str.split('-')]
        origin = route_parts[0] if len(route_parts) > 0 else ""
        destination = route_parts[1] if len(route_parts) > 1 else ""
    return flight_number, flight_date, origin, destination

def parse_consignee_phone_name(consignee: str):
    """
    提取深航收货人字符串中的电话和收货人名字，如 '高云0755-85273907'
    返回 (phone, name)
    """
    if not consignee:
        return "", ""
    # 查找末尾的电话号码/手机号格式
    match = re.search(r'([0-9\-+]{7,20})$', consignee.strip())
    if match:
        phone = match.group(1)
        name = consignee.replace(phone, "").strip()
        return phone, name
    return "", consignee

def get_customer_transit_rate(customer: Optional[Customer], cargo_type: str) -> float:
    """从客户的 JSON 费率配置中寻找对应货物类型的过站费率"""
    if not customer or not cargo_type:
        return 0.0
    rates = customer.cargo_type_transit_fee_rate
    if not rates:
        return 0.0
    if isinstance(rates, str):
        try:
            rates = json.loads(rates)
        except Exception:
            return 0.0
    if isinstance(rates, dict):
        try:
            return float(rates.get(cargo_type, 0.0))
        except Exception:
            return 0.0
    return 0.0

# ----------------- API Endpoints -----------------

@router.get("/air", summary="统一空运财务审核列表")
async def get_air_financial_audits(
    query: AirFinancialAuditQuery = Depends(),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    统一查询深航、南航、同行空运的财务单据审核列表，并按照航班日期降序排序、分页返回。
    """
    # 代理名称过滤限制：如果传了代理名称，直接限制只查同行空运，深航/南航直接不查询
    query_shenzhen = not bool(query.agent_name)
    query_southern = not bool(query.agent_name)
    query_peer = True

    # 如果指定了航司类型
    if query.airline_type:
        if query.airline_type == "shenzhen_air":
            query_southern = False
            query_peer = False
        elif query.airline_type == "china_southern_air":
            query_shenzhen = False
            query_peer = False
        elif query.airline_type == "peer_air":
            query_shenzhen = False
            query_southern = False
        else:
            # 未知的航司类型
            query_shenzhen = False
            query_southern = False
            query_peer = False

    # 存储三个渠道返回的候选项目 (基本属性，用于排序分页)
    candidate_items = []

    # 1. 提取公共筛选
    waybill_list = [w.strip() for w in query.waybill_number.split(',') if w.strip()] if query.waybill_number else []

    # ================= 1.1 查询深航 =================
    if query_shenzhen:
        sz_q = db.query(
            ShenzhenAirBookingExport,
            ShenzhenAirDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            ShenzhenAirDepartureManualData,
            ShenzhenAirDepartureManualData.booking_export_id == ShenzhenAirBookingExport.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "shenzhen_air",
                AirFinancialAuditData.source_id == ShenzhenAirBookingExport.id
            )
        )

        # 运单号过滤
        if waybill_list:
            or_filters = []
            for wb in waybill_list:
                if '-' in wb:
                    pref, num = wb.split('-', 1)
                    or_filters.append(
                        and_(
                            ShenzhenAirBookingExport.prefix == pref,
                            ShenzhenAirBookingExport.waybill_number == num
                        )
                    )
                else:
                    or_filters.append(ShenzhenAirBookingExport.waybill_number == wb)
            sz_q = sz_q.filter(or_(*or_filters))

        # 航班日期过滤
        if query.flight_date_start:
            sz_q = sz_q.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') >= str(query.flight_date_start))
        if query.flight_date_end:
            sz_q = sz_q.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') <= str(query.flight_date_end))

        # 目的站过滤
        if query.destination:
            sz_q = sz_q.filter(ShenzhenAirBookingExport.routing.like(f"%{query.destination}%"))

        # 航班号过滤
        if query.flight_number:
            sz_q = sz_q.filter(ShenzhenAirBookingExport.billing_flight.like(f"%{query.flight_number}%"))

        # 业务审核状态
        if query.audit_status is not None:
            if query.audit_status == 0:
                sz_q = sz_q.filter(or_(ShenzhenAirDepartureManualData.audit_status == 0, ShenzhenAirDepartureManualData.audit_status.is_(None)))
            else:
                sz_q = sz_q.filter(ShenzhenAirDepartureManualData.audit_status == query.audit_status)

        # 财务审核状态
        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                sz_q = sz_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                sz_q = sz_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        # 电报状态过滤
        if query.telegram_status:
            if query.telegram_status == "有电报":
                sz_q = sz_q.filter(
                    or_(
                        and_(ShenzhenAirDepartureManualData.telegram_fee != None, ShenzhenAirDepartureManualData.telegram_fee != ""),
                        and_(ShenzhenAirDepartureManualData.telegram_code != None, ShenzhenAirDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                sz_q = sz_q.filter(
                    and_(
                        or_(ShenzhenAirDepartureManualData.telegram_fee == None, ShenzhenAirDepartureManualData.telegram_fee == ""),
                        or_(ShenzhenAirDepartureManualData.telegram_code == None, ShenzhenAirDepartureManualData.telegram_code == "")
                    )
                )

        # CCA状态过滤
        if query.cca_status:
            if query.cca_status == "有CCA":
                sz_q = sz_q.filter(and_(ShenzhenAirDepartureManualData.cca != None, ShenzhenAirDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                sz_q = sz_q.filter(or_(ShenzhenAirDepartureManualData.cca == None, ShenzhenAirDepartureManualData.cca == ""))

        # 提取候选
        for export, md, fa in sz_q.all():
            f_date = safe_str(export.flight_date).replace('/', '-')
            waybill_full = f"{safe_str(export.prefix)}-{safe_str(export.waybill_number)}" if export.prefix else safe_str(export.waybill_number)
            
            # 解析路由起终点
            routing = safe_str(export.routing)
            origin, dest = "", ""
            if '-' in routing:
                rt_parts = [r.strip() for r in routing.split('-')]
                origin = rt_parts[0] if len(rt_parts) > 0 else ""
                dest = rt_parts[1] if len(rt_parts) > 1 else ""
            
            candidate_items.append({
                "source_type": "shenzhen_air",
                "source_id": str(export.id),
                "flight_date": f_date,
                "waybill_number": waybill_full,
                "origin": origin,
                "destination": dest or query.destination or "",
                "flight_number": safe_str(export.billing_flight),
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else "",
                "agent_name": safe_str(export.agent),
                "airline": "深航",
                "cargo_name": safe_str(export.cargo_name),
                "billing_quantity": safe_str(export.quantity),
                "billing_weight": safe_str(export.weight),
                "creator": safe_str(export.creator),
                "creation_time": safe_str(export.creation_time),
                # 附带的db对象，方便直接使用，避免二次查库
                "_main": export,
                "_md": md,
                "_fa": fa
            })

    # ================= 1.2 查询南航 =================
    if query_southern:
        csa_q = db.query(
            ChinaSouthernAirApprovalData,
            CsaDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            CsaDepartureManualData,
            CsaDepartureManualData.approval_data_id == ChinaSouthernAirApprovalData.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "china_southern_air",
                AirFinancialAuditData.source_id == ChinaSouthernAirApprovalData.id
            )
        )

        # 运单号过滤
        if waybill_list:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.waybill_number.in_(waybill_list))

        # 航班信息字段关联的日期范围过滤
        if query.flight_date_start or query.flight_date_end:
            # 正常南航结构 CZ8577 / 2026-06-16 / SZX - WUH，需要用到 like 或者 trim 提取
            # 由于不能直接用 substring_index 在不同数据库上做无缝兼容，这里用 like '%YYYY-MM-DD%' 批量匹配，或加载到内存过滤
            # 为了确保查询稳妥，我们在 python 过滤或者使用 DB 的 substring_index
            pass # 后面用 python 内存过滤

        # 目的站过滤
        if query.destination:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%{query.destination}%"))

        # 航班号过滤
        if query.flight_number:
            csa_q = csa_q.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%{query.flight_number}%"))

        # 业务审核状态
        if query.audit_status is not None:
            if query.audit_status == 0:
                csa_q = csa_q.filter(or_(CsaDepartureManualData.audit_status == 0, CsaDepartureManualData.audit_status.is_(None)))
            else:
                csa_q = csa_q.filter(CsaDepartureManualData.audit_status == query.audit_status)

        # 财务审核状态
        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                csa_q = csa_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                csa_q = csa_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        # 电报状态过滤
        if query.telegram_status:
            if query.telegram_status == "有电报":
                csa_q = csa_q.filter(
                    or_(
                        and_(CsaDepartureManualData.telegram_fee != None, CsaDepartureManualData.telegram_fee != ""),
                        and_(CsaDepartureManualData.telegram_code != None, CsaDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                csa_q = csa_q.filter(
                    and_(
                        or_(CsaDepartureManualData.telegram_fee == None, CsaDepartureManualData.telegram_fee == ""),
                        or_(CsaDepartureManualData.telegram_code == None, CsaDepartureManualData.telegram_code == "")
                    )
                )

        # CCA状态过滤
        if query.cca_status:
            if query.cca_status == "有CCA":
                csa_q = csa_q.filter(and_(CsaDepartureManualData.cca != None, CsaDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                csa_q = csa_q.filter(or_(CsaDepartureManualData.cca == None, CsaDepartureManualData.cca == ""))

        # 提取候选
        for approval, md, fa in csa_q.all():
            fl_num, fl_date, orig, dest = parse_csa_flight_info(approval.flight_info)
            
            # 日期内存过滤
            if query.flight_date_start and fl_date < str(query.flight_date_start):
                continue
            if query.flight_date_end and fl_date > str(query.flight_date_end):
                continue
                
            pieces, weight = parse_csa_qty_weight(approval.billing_qty)

            candidate_items.append({
                "source_type": "china_southern_air",
                "source_id": str(approval.id),
                "flight_date": fl_date,
                "waybill_number": safe_str(approval.waybill_number),
                "origin": orig,
                "destination": dest or query.destination or "",
                "flight_number": fl_num,
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else "",
                "agent_name": safe_str(approval.agent_code),
                "airline": "南航",
                "cargo_name": safe_str(approval.goods_name),
                "billing_quantity": pieces,
                "billing_weight": weight,
                "creator": "",
                "creation_time": safe_str(approval.booking_time),
                "_main": approval,
                "_md": md,
                "_fa": fa
            })

    # ================= 1.3 查询同行空运 =================
    if query_peer:
        peer_q = db.query(
            ConsignmentNote,
            PeerAirDepartureManualData,
            AirFinancialAuditData
        ).outerjoin(
            PeerAirDepartureManualData,
            PeerAirDepartureManualData.consignment_note_id == ConsignmentNote.id
        ).outerjoin(
            AirFinancialAuditData,
            and_(
                AirFinancialAuditData.source_type == "peer_air",
                AirFinancialAuditData.source_id == ConsignmentNote.id
            )
        ).filter(
            ConsignmentNote.transport_type == "0"
        )

        # 运单号过滤
        if waybill_list:
            peer_q = peer_q.filter(PeerAirDepartureManualData.waybill_number.in_(waybill_list))

        # 航班日期过滤
        if query.flight_date_start:
            peer_q = peer_q.filter(ConsignmentNote.consignment_date >= query.flight_date_start)
        if query.flight_date_end:
            peer_q = peer_q.filter(ConsignmentNote.consignment_date <= query.flight_date_end)

        # 代理名称模糊匹配
        if query.agent_name:
            peer_q = peer_q.filter(ConsignmentNote.company_name.like(f"%{query.agent_name}%"))

        # 目的站过滤
        if query.destination:
            peer_q = peer_q.filter(ConsignmentNote.destination.like(f"%{query.destination}%"))

        # 航班号过滤
        if query.flight_number:
            peer_q = peer_q.filter(ConsignmentNote.flight_number.like(f"%{query.flight_number}%"))

        # 业务审核状态
        if query.audit_status is not None:
            if query.audit_status == 0:
                peer_q = peer_q.filter(or_(PeerAirDepartureManualData.audit_status == 0, PeerAirDepartureManualData.audit_status.is_(None)))
            else:
                peer_q = peer_q.filter(PeerAirDepartureManualData.audit_status == query.audit_status)

        # 财务审核状态
        if query.financial_audit_status is not None:
            if query.financial_audit_status == 0:
                peer_q = peer_q.filter(or_(AirFinancialAuditData.financial_audit_status == 0, AirFinancialAuditData.financial_audit_status.is_(None)))
            else:
                peer_q = peer_q.filter(AirFinancialAuditData.financial_audit_status == query.financial_audit_status)

        # 电报状态过滤
        if query.telegram_status:
            if query.telegram_status == "有电报":
                peer_q = peer_q.filter(
                    or_(
                        and_(PeerAirDepartureManualData.telegram_fee != None, PeerAirDepartureManualData.telegram_fee != ""),
                        and_(PeerAirDepartureManualData.telegram_code != None, PeerAirDepartureManualData.telegram_code != "")
                    )
                )
            elif query.telegram_status == "无电报":
                peer_q = peer_q.filter(
                    and_(
                        or_(PeerAirDepartureManualData.telegram_fee == None, PeerAirDepartureManualData.telegram_fee == ""),
                        or_(PeerAirDepartureManualData.telegram_code == None, PeerAirDepartureManualData.telegram_code == "")
                    )
                )

        # CCA状态过滤
        if query.cca_status:
            if query.cca_status == "有CCA":
                peer_q = peer_q.filter(and_(PeerAirDepartureManualData.cca != None, PeerAirDepartureManualData.cca != ""))
            elif query.cca_status == "无CCA":
                peer_q = peer_q.filter(or_(PeerAirDepartureManualData.cca == None, PeerAirDepartureManualData.cca == ""))

        # 提取候选
        for note, md, fa in peer_q.all():
            f_date = note.consignment_date.isoformat() if note.consignment_date else ""
            
            # 解析 form_data 为 dict
            form_dict = {}
            if note.form_data:
                try:
                    form_dict = json.loads(note.form_data)
                except Exception:
                    pass

            candidate_items.append({
                "source_type": "peer_air",
                "source_id": str(note.id),
                "flight_date": f_date,
                "waybill_number": md.waybill_number if md else "",
                "origin": form_dict.get("origin_station", ""),
                "destination": note.destination or "",
                "flight_number": safe_str(note.flight_number),
                "audit_status": md.audit_status if md else 0,
                "financial_audit_status": fa.financial_audit_status if fa else 0,
                "customer_name": md.customer_name if md else note.customer_name,
                "agent_name": note.company_name or "",
                "airline": note.airline or "",
                "cargo_name": form_dict.get("cargo_name", ""),
                "billing_quantity": safe_str(form_dict.get("quantity", "")),
                "billing_weight": safe_str(form_dict.get("weight", "")),
                "creator": safe_str(note.creator_name),
                "creation_time": note.created_at.strftime("%Y-%m-%d %H:%M:%S") if note.created_at else "",
                "_main": note,
                "_form_dict": form_dict,
                "_md": md,
                "_fa": fa
            })

    # ================= 2. 内存全局排序 (按航班日期降序，若日期相同，按主表主键降序) =================
    candidate_items.sort(key=lambda x: (x["flight_date"] or "", x["source_id"]), reverse=True)

    # 3. 统计总数
    total = len(candidate_items)

    # 4. 执行内存分页切片
    offset = (query.page - 1) * query.pageSize
    paged_items = candidate_items[offset : offset + query.pageSize]

    # ================= 5. 为本页切片数据批量提取/组装详细子表与财务数据 =================
    
    # 5.1 加载过站费用计算依赖的客户费率映射字典
    customers = db.query(Customer).all()
    customer_map = {c.company_name: c for c in customers if c.company_name}

    # 5.2 提取本页所有的运单号、审批表ID以批量查询子项 (避免N+1查询)
    sz_waybill_8s = []
    csa_approval_ids = []
    csa_waybills = []

    for item in paged_items:
        if item["source_type"] == "shenzhen_air":
            export = item["_main"]
            if export.waybill_number and len(export.waybill_number) >= 8:
                sz_waybill_8s.append(export.waybill_number[-8:])
        elif item["source_type"] == "china_southern_air":
            csa_approval_ids.append(int(item["source_id"]))
            if item["waybill_number"]:
                csa_waybills.append(item["waybill_number"])

    # 批量拉取深航的集装器数据
    sz_containers_map = {}
    if sz_waybill_8s:
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.waybill_number_8.in_(sz_waybill_8s)
        ).all()
        for cont in containers:
            sz_containers_map.setdefault(cont.waybill_number_8, []).append(cont)

    # 批量拉取南航的 Lalamove 数据
    csa_lalamoves_map = {}
    if csa_approval_ids:
        lalamoves = db.query(CsaLalamoveInformation).filter(
            CsaLalamoveInformation.approval_data_id.in_(csa_approval_ids)
        ).all()
        for lm in lalamoves:
            csa_lalamoves_map.setdefault(lm.approval_data_id, []).append(lm)

    # 批量拉取南航匹配的运单 Waybill 数据
    csa_waybill_map = {}
    if csa_waybills:
        wb_records = db.query(Waybill).filter(Waybill.waybill_number.in_(csa_waybills)).all()
        for wb in wb_records:
            csa_waybill_map[wb.waybill_number] = wb

    # 5.3 迭代组装每个结果项
    result_items = []
    for item in paged_items:
        source_type = item["source_type"]
        md = item["_md"]
        fa = item["_fa"]
        cust_name = item["customer_name"]
        customer = customer_map.get(cust_name)

        # 预定义应付、应收结构
        payable_data = {}
        receivable_data = {}

        if source_type == "shenzhen_air":
            export = item["_main"]
            # 取深航相关的子表 pieces/weight
            wb_8 = export.waybill_number[-8:] if export.waybill_number and len(export.waybill_number) >= 8 else ""
            related_conts = sz_containers_map.get(wb_8, [])
            
            gate_pieces_val = sum(safe_int(c.quantity) for c in related_conts)
            transit_weight_val = sum(safe_float(c.weight) for c in related_conts)
            
            # 过站费率与费用
            cargo_type = md.cargo_type if md else ""
            transit_rate = get_customer_transit_rate(customer, cargo_type)
            transit_fee_val = transit_weight_val * transit_rate

            # 电报成本：优先人工录入，无则使用 md 中的电报费
            telegraph_cost_val = fa.payable_telegraph_cost if (fa and fa.payable_telegraph_cost is not None) else (md.telegram_fee if md else "")

            # 成本合计 (air_freight + fuel_surcharge + transit_fee + cca + packaging_fee + other_fees + door_pickup_fee + airport_pickup_fee + delivery_cost)
            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.airport_pickup_fee if md else 0.0) # 深航派送成本对应 airport_pickup_fee

            total_cost_val = (
                safe_float(export.air_freight) +
                safe_float(export.fuel_surcharge) +
                transit_fee_val +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=None,
                cargo_type=cargo_type,
                billing_pieces=safe_str(export.quantity),
                billing_weight=safe_str(export.weight),
                gate_pieces=str(gate_pieces_val) if related_conts else "0",
                chargeable_weight=safe_str(export.chargeable_weight),
                freight_rate=safe_str(export.freight_rate),
                air_freight=safe_str(export.air_freight),
                fuel_surcharge=safe_str(export.fuel_surcharge),
                transit_weight=format_decimal(transit_weight_val),
                transit_fee=format_decimal(transit_fee_val),
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark=safe_str(fa.payable_other_fee_remark if fa else ""),
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            # 应收板块组装
            consignee_phone, consignee_name = parse_consignee_phone_name(export.consignee)
            
            # 收货人与收货电话：若是手工表中填写过则优先使用，但由于深航目前不开放人工修改电话，所以还是直接取解析值
            phone_final = consignee_phone
            consignee_final = consignee_name

            # 运费
            receivable_freight = safe_float(export.chargeable_weight) * safe_float(export.freight_rate)

            # 应收中的提货方式、代收货款、上门提货费、承运扣款等：使用财务扩展表
            carrier_deduction_val = fa.receivable_carrier_deduction if (fa and fa.receivable_carrier_deduction is not None) else (md.carrier_deduction if md else "")
            door_pickup_fee_val = fa.receivable_pickup_fee if (fa and fa.receivable_pickup_fee is not None) else (md.door_pickup_fee if md else "")
            pickup_method_val = fa.receivable_pickup_method if (fa and fa.receivable_pickup_method is not None) else ""
            collection_val = fa.receivable_collection_payment if (fa and fa.receivable_collection_payment is not None) else ""

            # 应收总金额合计
            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(door_pickup_fee_val) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) # 派送费对应 airport_pickup_fee
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone=phone_final,
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=safe_str(export.quantity),
                chargeable_weight=safe_str(export.chargeable_weight),
                freight_rate=safe_str(export.freight_rate),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark=safe_str(fa.receivable_other_fee_remark if fa else ""),
                door_pickup_fee=format_decimal(safe_float(door_pickup_fee_val)),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(carrier_deduction_val),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee=consignee_final,
                destination=item["destination"],
                pickup_method=pickup_method_val,
                weight=safe_str(export.chargeable_weight),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.airport_pickup_fee if md else ""), # 派送费
                collection_payment=collection_val,
                remark=safe_str(fa.receivable_remark if fa else ""),
                gross_profit=format_decimal(gross_profit_val)
            )

        elif source_type == "china_southern_air":
            approval = item["_main"]
            # 取南航相关的子表 pieces/weight
            related_lms = csa_lalamoves_map.get(approval.id, [])
            
            gate_pieces_val = sum(safe_int(l.pieces) for l in related_lms)
            transit_weight_val = sum(safe_float(l.weight) for l in related_lms)
            
            # 过站费率与费用
            cargo_type = md.cargo_type if md else ""
            transit_rate = get_customer_transit_rate(customer, cargo_type)
            transit_fee_val = transit_weight_val * transit_rate

            # 电报成本：优先人工，无则使用 md 中的电报费
            telegraph_cost_val = fa.payable_telegraph_cost if (fa and fa.payable_telegraph_cost is not None) else (md.telegram_fee if md else "")

            # 成本合计
            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.airport_pickup_fee if md else 0.0) # 南航派送成本对应 airport_pickup_fee

            total_cost_val = (
                safe_float(approval.ref_freight) +
                transit_fee_val +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=None,
                cargo_type=cargo_type,
                billing_pieces=item["billing_quantity"],
                billing_weight=item["billing_weight"],
                gate_pieces=str(gate_pieces_val) if related_lms else "0",
                chargeable_weight=safe_str(approval.chargeable_weight),
                freight_rate=safe_str(approval.ref_rate),
                air_freight=safe_str(approval.ref_freight),
                fuel_surcharge="",
                transit_weight=format_decimal(transit_weight_val),
                transit_fee=format_decimal(transit_fee_val),
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark=safe_str(fa.payable_other_fee_remark if fa else ""),
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            # 获取南航运单中的收货人信息
            wb_phone = ""
            wb_consignee = ""
            if approval.waybill_number and approval.waybill_number in csa_waybill_map:
                waybill_obj = csa_waybill_map[approval.waybill_number]
                if waybill_obj.form_data:
                    try:
                        wb_form = json.loads(waybill_obj.form_data)
                        wb_phone = wb_form.get("contact_info", {}).get("consignee_phone", "")
                        wb_consignee = wb_form.get("contact_info", {}).get("consignee", "")
                    except Exception:
                        pass

            # 运费
            receivable_freight = safe_float(approval.chargeable_weight) * safe_float(approval.ref_rate)

            # 应收中的提货方式、代收货款、上门提货费、承运扣款等：使用财务扩展表
            carrier_deduction_val = fa.receivable_carrier_deduction if (fa and fa.receivable_carrier_deduction is not None) else (md.carrier_deduction if md else "")
            door_pickup_fee_val = fa.receivable_pickup_fee if (fa and fa.receivable_pickup_fee is not None) else (md.door_pickup_fee if md else "")
            pickup_method_val = fa.receivable_pickup_method if (fa and fa.receivable_pickup_method is not None) else ""
            collection_val = fa.receivable_collection_payment if (fa and fa.receivable_collection_payment is not None) else ""

            # 应收总金额合计
            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(door_pickup_fee_val) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) # 派送费对应 airport_pickup_fee
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone=wb_phone,
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=item["billing_quantity"],
                chargeable_weight=safe_str(approval.chargeable_weight),
                freight_rate=safe_str(approval.ref_rate),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark=safe_str(fa.receivable_other_fee_remark if fa else ""),
                door_pickup_fee=format_decimal(safe_float(door_pickup_fee_val)),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(carrier_deduction_val),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee=wb_consignee,
                destination=item["destination"],
                pickup_method=pickup_method_val,
                weight=safe_str(approval.chargeable_weight),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.airport_pickup_fee if md else ""),
                collection_payment=collection_val,
                remark=safe_str(fa.receivable_remark if fa else ""),
                gross_profit=format_decimal(gross_profit_val)
            )

        elif source_type == "peer_air":
            note = item["_main"]
            form_dict = item["_form_dict"]

            # 同行空运没有过机件数与过站重量，为空
            gate_pieces_val = ""
            transit_fee_val = 0.0

            # 电报成本：优先人工，无则使用 md 中的电报费
            telegraph_cost_val = fa.payable_telegraph_cost if (fa and fa.payable_telegraph_cost is not None) else (md.telegram_fee if md else "")

            # 成本合计
            cca_cost = safe_float(md.cca if md else 0.0)
            pack_fee = safe_float(md.packaging_fee if md else 0.0)
            oth_fee = safe_float(md.other_fees if md else 0.0)
            door_fee = safe_float(md.door_pickup_fee if md else 0.0)
            airport_fee = safe_float(md.airport_pickup_fee if md else 0.0)
            delivery_cost = safe_float(md.airport_pickup_fee if md else 0.0) # 派送成本对应 airport_pickup_fee

            total_cost_val = (
                safe_float(form_dict.get("air_freight", 0.0)) +
                cca_cost +
                pack_fee +
                oth_fee +
                door_fee +
                airport_fee +
                delivery_cost
            )

            payable_data = PayableResponse(
                agent_name=note.company_name,
                cargo_type=md.cargo_type if md else "",
                billing_pieces=safe_str(form_dict.get("quantity", "")),
                billing_weight=safe_str(form_dict.get("weight", "")),
                gate_pieces="",
                chargeable_weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight_rate=safe_str(form_dict.get("rate", "")),
                air_freight=safe_str(form_dict.get("air_freight", "")),
                fuel_surcharge="",
                transit_weight="",
                transit_fee="",
                cca_cost=safe_str(md.cca if md else ""),
                telegraph_cost=safe_str(telegraph_cost_val),
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                other_fee_remark=safe_str(fa.payable_other_fee_remark if fa else ""),
                door_pickup_company=safe_str(md.door_pickup_company if md else ""),
                door_pickup_fee=safe_str(md.door_pickup_fee if md else ""),
                delivery_company=safe_str(md.delivery_company if md else ""),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                delivery_cost=format_decimal(delivery_cost),
                total_cost=format_decimal(total_cost_val)
            )

            # 运费
            receivable_freight = safe_float(form_dict.get("chargeable_weight", 0.0)) * safe_float(form_dict.get("rate", 0.0))

            # 应收中的提货方式、代收货款、上门提货费、承运扣款、收货电话、收货单位等：使用财务扩展表
            carrier_deduction_val = fa.receivable_carrier_deduction if (fa and fa.receivable_carrier_deduction is not None) else (md.carrier_deduction if md else "")
            door_pickup_fee_val = fa.receivable_pickup_fee if (fa and fa.receivable_pickup_fee is not None) else (md.door_pickup_fee if md else "")
            pickup_method_val = fa.receivable_pickup_method if (fa and fa.receivable_pickup_method is not None) else ""
            collection_val = fa.receivable_collection_payment if (fa and fa.receivable_collection_payment is not None) else ""
            consignee_phone_val = fa.receivable_consignee_phone if (fa and fa.receivable_consignee_phone is not None) else ""
            consignee_unit_val = fa.receivable_consignee_unit if (fa and fa.receivable_consignee_unit is not None) else ""

            # 应收总金额合计
            total_amount_val = (
                safe_float(md.telegram_fee if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) +
                safe_float(md.packaging_fee if md else 0.0) +
                safe_float(door_pickup_fee_val) +
                receivable_freight +
                safe_float(md.cca if md else 0.0) +
                safe_float(md.other_fees if md else 0.0) +
                safe_float(md.airport_pickup_fee if md else 0.0) # 派送费对应 airport_pickup_fee
            )

            gross_profit_val = total_amount_val - total_cost_val

            receivable_data = ReceivableResponse(
                flight_date=item["flight_date"],
                customer_name=cust_name,
                consignee_phone=consignee_phone_val,
                origin=item["origin"],
                airline=item["airline"],
                flight_number=item["flight_number"],
                cargo_name=item["cargo_name"],
                pieces=safe_str(form_dict.get("quantity", "")),
                chargeable_weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight_rate=safe_str(form_dict.get("rate", "")),
                document_fee="",
                packaging_fee=safe_str(md.packaging_fee if md else ""),
                telegram_fee=safe_str(md.telegram_fee if md else ""),
                telegram_code=safe_str(md.telegram_code if md else ""),
                other_fee_remark=safe_str(fa.receivable_other_fee_remark if fa else ""),
                door_pickup_fee=format_decimal(safe_float(door_pickup_fee_val)),
                airport_pickup_fee=safe_str(md.airport_pickup_fee if md else ""),
                carrier_deduction=safe_str(carrier_deduction_val),
                total_amount=format_decimal(total_amount_val),
                payment_method="",
                consignee=consignee_unit_val,
                destination=item["destination"],
                pickup_method=pickup_method_val,
                weight=safe_str(form_dict.get("chargeable_weight", "")),
                freight=format_decimal(receivable_freight),
                cca=safe_str(md.cca if md else ""),
                other_fees=safe_str(md.other_fees if md else ""),
                delivery_fee=safe_str(md.airport_pickup_fee if md else ""),
                collection_payment=collection_val,
                remark=safe_str(fa.receivable_remark if fa else ""),
                gross_profit=format_decimal(gross_profit_val)
            )

        # 组装完整的项目并加入列表
        result_items.append(AirFinancialAuditItemResponse(
            source_type=source_type,
            source_id=item["source_id"],
            audit_status=item["audit_status"],
            financial_audit_status=item["financial_audit_status"],
            flight_date=item["flight_date"],
            customer_name=cust_name,
            agent_name=item["agent_name"],
            airline=item["airline"],
            waybill_number=item["waybill_number"],
            origin=item["origin"],
            destination=item["destination"],
            flight_number=item["flight_number"],
            cargo_name=item["cargo_name"],
            billing_quantity=item["billing_quantity"],
            billing_weight=item["billing_weight"],
            creator=item["creator"],
            creation_time=item["creation_time"],
            payable=payable_data,
            receivable=receivable_data
        ))

    return success_response(data={
        "total": total,
        "items": [item.model_dump() for item in result_items]
    })


@router.post("/air/audit", summary="统一空运财务审核暂存/提交")
async def audit_air_financial(
    req: AirFinancialAuditDataUpsert,
    action: str = Query(..., description="操作类型：save (暂存), submit (已审核/提交)"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_active_user)
):
    """
    空运财务审核提交或暂存接口。
    - action == 'save': 状态更新为 1 (暂存)
    - action == 'submit': 状态更新为 2 (已审核)
    并将人工填写的电报费、其他费用、上门提货、派送、承运扣款等字段持久化保存。
    """
    if action not in ["save", "submit"]:
        raise HTTPException(status_code=400, detail="Invalid action. Must be 'save' or 'submit'")

    source_type = req.source_type
    source_id = int(req.source_id)

    # 1. 验证对应的源主表是否存在
    if source_type == "shenzhen_air":
        exists = db.query(ShenzhenAirBookingExport.id).filter(ShenzhenAirBookingExport.id == source_id).first()
    elif source_type == "china_southern_air":
        exists = db.query(ChinaSouthernAirApprovalData.id).filter(ChinaSouthernAirApprovalData.id == source_id).first()
    elif source_type == "peer_air":
        exists = db.query(ConsignmentNote.id).filter(ConsignmentNote.id == source_id, ConsignmentNote.transport_type == "0").first()
    else:
        raise HTTPException(status_code=400, detail="Invalid source_type")

    if not exists:
        raise HTTPException(status_code=404, detail="Source record not found")

    # 2. 查询现有的财务扩展表数据，没有则新建
    fa_data = db.query(AirFinancialAuditData).filter(
        AirFinancialAuditData.source_type == source_type,
        AirFinancialAuditData.source_id == source_id
    ).first()

    if not fa_data:
        fa_data = AirFinancialAuditData(
            source_type=source_type,
            source_id=source_id
        )
        db.add(fa_data)

    # 3. 更新人工填写字段
    # 应付
    fa_data.payable_telegraph_cost = req.payable_telegraph_cost
    fa_data.payable_other_fee_remark = req.payable_other_fee_remark
    
    # 应收
    fa_data.receivable_consignee_phone = req.receivable_consignee_phone
    fa_data.receivable_consignee_unit = req.receivable_consignee_unit
    fa_data.receivable_other_fee_remark = req.receivable_other_fee_remark
    fa_data.receivable_pickup_fee = req.receivable_pickup_fee
    fa_data.receivable_carrier_deduction = req.receivable_carrier_deduction
    fa_data.receivable_pickup_method = req.receivable_pickup_method
    fa_data.receivable_collection_payment = req.receivable_collection_payment
    fa_data.receivable_remark = req.receivable_remark

    # 4. 根据动作设置审核状态与审核人信息
    target_status = 1 if action == "save" else 2
    fa_data.financial_audit_status = target_status
    fa_data.financial_auditor_id = current_user.id
    fa_data.financial_auditor_name = current_user.nickname or current_user.username
    fa_data.financial_audit_time = datetime.now()

    db.commit()
    db.refresh(fa_data)

    return success_response(msg="操作成功", data={
        "source_type": fa_data.source_type,
        "source_id": str(fa_data.source_id),
        "financial_audit_status": fa_data.financial_audit_status
    })
