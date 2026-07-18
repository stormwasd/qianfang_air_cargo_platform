"""
托运书管理接口
"""
import json
from io import BytesIO
from fastapi import APIRouter, Depends, Response, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from app.database import get_db
from app.models.consignment_note import ConsignmentNote
from app.schemas.consignment_note import (
    ConsignmentNoteCreate, ConsignmentNoteUpdate, ConsignmentNoteQuery,
    ConsignmentNoteFinancialAudit, PeerAirDepartureManualDataUpsert
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

router = APIRouter()


@router.post("", summary="新增托运书")
async def create_consignment_note(
    payload: ConsignmentNoteCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增托运书（空运/汽运）
    """
    form_data = payload.form_data
    
    consignment_date = form_data.get("transport_date") or form_data.get("flight_date")
    destination = form_data.get("destination_city") or form_data.get("destination_station")
    flight_number = form_data.get("flight_number")
    airline = form_data.get("airline")

    form_data_json = json.dumps(form_data, ensure_ascii=False)
    
    new_note = ConsignmentNote(
        transport_type=payload.transport_type,
        company_name=payload.company_name,
        customer_name=payload.customer_name,
        consignment_date=consignment_date,
        destination=destination,
        flight_number=flight_number,
        airline=airline,
        form_data=form_data_json,
        creator_id=str(current_user.id),
        creator_name=current_user.name
    )
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    
    return success_response(data={"id": str(new_note.id)}, msg="托运书创建成功")


@router.get("", summary="查询托运书列表")
async def get_consignment_notes(
    query: ConsignmentNoteQuery = Depends(),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    多条件查询托运书列表（支持空运/汽运不同搜索逻辑）
    """
    query_obj = db.query(ConsignmentNote)
    
    from sqlalchemy import or_
    
    if query.is_financial:
        if not query.transport_type:
            return success_response(code=400, msg="财务审核模式下必须指定托运方式筛选")
            
        if query.transport_type == "1":
            from app.models.peer_road_manual_data import PeerRoadDepartureManualData
            query_obj = query_obj.outerjoin(
                PeerRoadDepartureManualData,
                PeerRoadDepartureManualData.consignment_note_id == ConsignmentNote.id
            )
            if query.financial_audit_status is not None:
                if query.financial_audit_status == 0:
                    query_obj = query_obj.filter(
                        or_(
                            PeerRoadDepartureManualData.financial_audit_status == 0,
                            PeerRoadDepartureManualData.financial_audit_status.is_(None)
                        )
                    )
                else:
                    query_obj = query_obj.filter(PeerRoadDepartureManualData.financial_audit_status == query.financial_audit_status)
        else:
            from app.models.peer_air_manual_data import PeerAirDepartureManualData
            query_obj = query_obj.outerjoin(
                PeerAirDepartureManualData,
                PeerAirDepartureManualData.consignment_note_id == ConsignmentNote.id
            )
            if query.financial_audit_status is not None:
                if query.financial_audit_status == 0:
                    query_obj = query_obj.filter(
                        or_(
                            PeerAirDepartureManualData.financial_audit_status == 0,
                            PeerAirDepartureManualData.financial_audit_status.is_(None)
                        )
                    )
                else:
                    query_obj = query_obj.filter(PeerAirDepartureManualData.financial_audit_status == query.financial_audit_status)
            if query.waybill_number:
                query_obj = query_obj.filter(PeerAirDepartureManualData.waybill_number.like(f"%{query.waybill_number}%"))
    else:
        if query.audit_status is not None or query.waybill_number:
            if query.transport_type == "1":
                from app.models.peer_road_manual_data import PeerRoadDepartureManualData
                query_obj = query_obj.outerjoin(
                    PeerRoadDepartureManualData,
                    PeerRoadDepartureManualData.consignment_note_id == ConsignmentNote.id
                )
                if query.audit_status is not None:
                    if query.audit_status == 0:
                        query_obj = query_obj.filter(
                            or_(
                                PeerRoadDepartureManualData.audit_status == 0,
                                PeerRoadDepartureManualData.audit_status.is_(None)
                            )
                        )
                    else:
                        query_obj = query_obj.filter(PeerRoadDepartureManualData.audit_status == query.audit_status)
            else:
                from app.models.peer_air_manual_data import PeerAirDepartureManualData
                query_obj = query_obj.outerjoin(
                    PeerAirDepartureManualData,
                    PeerAirDepartureManualData.consignment_note_id == ConsignmentNote.id
                )
                if query.audit_status is not None:
                    if query.audit_status == 0:
                        query_obj = query_obj.filter(
                            or_(
                                PeerAirDepartureManualData.audit_status == 0,
                                PeerAirDepartureManualData.audit_status.is_(None)
                            )
                        )
                    else:
                        query_obj = query_obj.filter(PeerAirDepartureManualData.audit_status == query.audit_status)
                if query.waybill_number:
                    query_obj = query_obj.filter(PeerAirDepartureManualData.waybill_number.like(f"%{query.waybill_number}%"))
            
    if query.transport_type:
        query_obj = query_obj.filter(ConsignmentNote.transport_type == query.transport_type)
        
    if query.date_start:
        query_obj = query_obj.filter(ConsignmentNote.consignment_date >= query.date_start)
    if query.date_end:
        query_obj = query_obj.filter(ConsignmentNote.consignment_date <= query.date_end)
        
    if query.company_name:
        query_obj = query_obj.filter(ConsignmentNote.company_name.like(f"%{query.company_name}%"))
        
    if query.customer_name:
        query_obj = query_obj.filter(ConsignmentNote.customer_name.like(f"%{query.customer_name}%"))
        
    if query.destination:
        query_obj = query_obj.filter(ConsignmentNote.destination.like(f"%{query.destination}%"))
    if query.flight_number:
        query_obj = query_obj.filter(ConsignmentNote.flight_number.like(f"%{query.flight_number}%"))
    if query.airline:
        query_obj = query_obj.filter(ConsignmentNote.airline.like(f"%{query.airline}%"))

    if query.origin_city:
        from sqlalchemy import or_
        query_obj = query_obj.filter(
            or_(
                func.json_unquote(func.json_extract(ConsignmentNote.form_data, '$.origin_station')).like(f"%{query.origin_city}%"),
                func.json_unquote(func.json_extract(ConsignmentNote.form_data, '$.origin_city')).like(f"%{query.origin_city}%")
            )
        )

    if query.destination_city:
        query_obj = query_obj.filter(ConsignmentNote.destination.like(f"%{query.destination_city}%"))

    if query.origin_station:
        from sqlalchemy import or_
        query_obj = query_obj.filter(
            or_(
                func.json_unquote(func.json_extract(ConsignmentNote.form_data, '$.origin_station')).like(f"%{query.origin_station}%"),
                func.json_unquote(func.json_extract(ConsignmentNote.form_data, '$.origin_city')).like(f"%{query.origin_station}%")
            )
        )
        
    if query.flight_date:
        query_obj = query_obj.filter(ConsignmentNote.consignment_date == query.flight_date)

    total = query_obj.count()
    offset = (query.page - 1) * query.pageSize
    notes = query_obj.order_by(ConsignmentNote.created_at.desc(), ConsignmentNote.id.desc()).offset(offset).limit(query.pageSize).all()
    
    manual_data_by_note_id = {}
    air_note_ids = [note.id for note in notes if note.transport_type == "0"]
    if air_note_ids:
        from app.models.peer_air_manual_data import PeerAirDepartureManualData
        manual_datas = db.query(PeerAirDepartureManualData).filter(
            PeerAirDepartureManualData.consignment_note_id.in_(air_note_ids)
        ).all()
        manual_data_by_note_id = {md.consignment_note_id: md for md in manual_datas}
        
    road_manual_data_by_note_id = {}
    road_note_ids = [note.id for note in notes if note.transport_type == "1"]
    if road_note_ids:
        from app.models.peer_road_manual_data import PeerRoadDepartureManualData
        rmds = db.query(PeerRoadDepartureManualData).filter(
            PeerRoadDepartureManualData.consignment_note_id.in_(road_note_ids)
        ).all()
        road_manual_data_by_note_id = {md.consignment_note_id: md for md in rmds}
        
    from app.schemas.consignment_note import PeerAirDepartureManualDataDTO, PeerRoadDepartureManualDataDTO
    
    items = []
    for note in notes:
        item_dict = {
            "id": str(note.id),
            "transport_type": note.transport_type,
            "company_name": note.company_name,
            "customer_name": note.customer_name,
            "consignment_date": note.consignment_date.isoformat() if note.consignment_date else None,
            "destination": note.destination,
            "flight_number": note.flight_number,
            "airline": note.airline,
            "form_data": json.loads(note.form_data),
            "creator_id": note.creator_id,
            "creator_name": note.creator_name,
            "created_at": format_datetime_china(note.created_at),
            "updated_at": format_datetime_china(note.updated_at),
            "manual_data": None
        }
        
        if note.transport_type == "0" and note.id in manual_data_by_note_id:
            md = manual_data_by_note_id[note.id]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            md_dict["consignment_note_id"] = str(md.consignment_note_id)
            item_dict["manual_data"] = PeerAirDepartureManualDataDTO(**md_dict).model_dump(mode="json")
            
        elif note.transport_type == "1" and note.id in road_manual_data_by_note_id:
            md = road_manual_data_by_note_id[note.id]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            md_dict["consignment_note_id"] = str(md.consignment_note_id)
            item_dict["manual_data"] = PeerRoadDepartureManualDataDTO(**md_dict).model_dump(mode="json")
            
        items.append(item_dict)
        
    return success_response(data={"total": total, "items": items}, msg="查询成功")


@router.get("/{note_id}", summary="查询托运书详情")
async def get_consignment_note(
    note_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(note_id)).first()
    if not note:
        raise NotFoundException("托运书不存在")
        
    data = {
        "id": str(note.id),
        "transport_type": note.transport_type,
        "company_name": note.company_name,
        "customer_name": note.customer_name,
        "consignment_date": note.consignment_date.isoformat() if note.consignment_date else None,
        "destination": note.destination,
        "flight_number": note.flight_number,
        "airline": note.airline,
        "form_data": json.loads(note.form_data),
        "creator_id": note.creator_id,
        "creator_name": note.creator_name,
        "created_at": format_datetime_china(note.created_at),
        "updated_at": format_datetime_china(note.updated_at)
    }
    return success_response(data=data, msg="查询成功")


@router.put("/{note_id}", summary="修改托运书")
async def update_consignment_note(
    note_id: str,
    payload: ConsignmentNoteUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(note_id)).first()
    if not note:
        raise NotFoundException("托运书不存在")
        
    form_data = payload.form_data
    consignment_date = form_data.get("transport_date") or form_data.get("flight_date")
    destination = form_data.get("destination_city") or form_data.get("destination_station")
    flight_number = form_data.get("flight_number")
    airline = form_data.get("airline")

    note.transport_type = payload.transport_type
    note.company_name = payload.company_name
    note.customer_name = payload.customer_name
    note.consignment_date = consignment_date
    note.destination = destination
    note.flight_number = flight_number
    note.airline = airline
    note.form_data = json.dumps(form_data, ensure_ascii=False)
    
    db.commit()
    return success_response(msg="修改成功")


@router.delete("/{note_id}", summary="删除托运书")
async def delete_consignment_note(
    note_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(note_id)).first()
    if not note:
        raise NotFoundException("托运书不存在")
    
    db.delete(note)
    db.commit()
    return success_response(msg="删除成功")


@router.get("/{note_id}/pdf", summary="生成托运书PDF", response_class=Response)
async def generate_consignment_pdf(
    note_id: str,
    db: Session = Depends(get_db)
):
    """
    使用 xhtml2pdf 和 jinja2 后端渲染托运单 PDF。
    """
    try:
        from xhtml2pdf import pisa
        from jinja2 import Template
    except ImportError:
        raise NotFoundException("后端渲染库未安装，请联系管理员")

    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(note_id)).first()
    if not note:
        raise NotFoundException("托运书不存在")
        
    form_data = json.loads(note.form_data)
    
    import os
    current_dir = os.path.dirname(os.path.abspath(__file__))
    font_path = os.path.join(current_dir, "..", "assets", "fonts", "SimHei.ttf")
    font_path_css = font_path.replace("\\", "/")
    
    html_template = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <style>
            @font-face {{
                font-family: "SimHei";
                src: url("{font_path_css}");
            }}
            body {{
                font-family: "SimHei", sans-serif;
                font-size: 14px;
                line-height: 1.6;
                color: #333;
            }}
            h1 {{
                text-align: center;
                color: #2c3e50;
                font-size: 24px;
                border-bottom: 2px solid #34495e;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }}
            .info-block {{
                margin-bottom: 20px;
            }}
            .info-title {{
                font-weight: bold;
                font-size: 16px;
                color: #2980b9;
                margin-bottom: 10px;
                border-bottom: 1px dashed #bdc3c7;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-bottom: 15px;
            }}
            th, td {{
                border: 1px solid #bdc3c7;
                padding: 8px 12px;
                text-align: left;
            }}
            th {{
                background-color: #ecf0f1;
                width: 30%;
                font-weight: bold;
            }}
            td {{
                width: 70%;
            }}
        </style>
    </head>
    <body>
        <h1>{{{{ "空运托运书" if type == "0" else "汽运托运书" }}}}</h1>
        
        <div class="info-block">
            <div class="info-title">1. 基本信息</div>
            <table>
                <tr><th>代理公司名称</th><td>{{{{ company_name }}}}</td></tr>
                <tr><th>客户名称</th><td>{{{{ customer_name }}}}</td></tr>
                <tr><th>制单人</th><td>{{{{ creator_name }}}}</td></tr>
                <tr><th>制单时间</th><td>{{{{ created_at }}}}</td></tr>
            </table>
        </div>
        
        <div class="info-block">
            <div class="info-title">2. {{{{ "航班信息" if type == "0" else "汽运信息" }}}}</div>
            <table>
                {{% for key, label in fields.items() %}}
                <tr><th>{{{{ label }}}}</th><td>{{{{ form_data.get(key, '') }}}}</td></tr>
                {{% endfor %}}
            </table>
        </div>
    </body>
    </html>
    """
    
    air_fields = {
        "airline": "航司", "flight_date": "航班日期", "flight_number": "航班号", 
        "origin_station": "始发站", "destination_station": "到达站", "estimated_flight_time": "计飞时间", 
        "quantity": "件数", "weight": "重量", "chargeable_weight": "计费重量(KG)", 
        "cabin_type": "舱位类型", "cabin_grade": "舱位等级", "volume": "体积", 
        "pickup_method": "提货方式", "consignee": "收货人", "cargo_name": "货物名称", 
        "rate": "费率", "air_freight": "航空运费", "other_fees": "其他费用", 
        "telegraph_fee": "电报费", "destination_weather": "目的站天气"
    }
    
    road_fields = {
        "transport_date": "托运日期", "quantity": "件数", "weight": "重量", 
        "volume": "体积(立方)", "vehicle_type": "车型", "cargo_name": "货物名称", 
        "total_freight": "总运费", "other_fees": "其他费用", "origin_city": "始发城市", 
        "origin_address": "始发城市详细地址", "destination_city": "终点城市", 
        "destination_address": "终点城市详细地址", "destination_weather": "目的站天气"
    }
    
    template = Template(html_template)
    html_content = template.render(
        type=note.transport_type,
        company_name=note.company_name or "",
        customer_name=note.customer_name or "",
        creator_name=note.creator_name or "",
        created_at=format_datetime_china(note.created_at),
        fields=air_fields if note.transport_type == "0" else road_fields,
        form_data=form_data
    )
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html_content.encode("UTF-8")), result)
    
    if pdf.err:
        raise NotFoundException("生成PDF失败")
        
    headers = {
        "Content-Disposition": f"attachment; filename=consignment_note_{note.id}.pdf"
    }
    return Response(content=result.getvalue(), media_type="application/pdf", headers=headers)


@router.post("/audit", summary="同行空运/汽运承运单据暂存/审核")
async def audit_consignment_note(
    data: PeerAirDepartureManualDataUpsert,
    action: str = Query(..., description="操作类型: save (暂存), submit (审核提交)"),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.utils.helpers import get_china_now
    
    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(data.consignment_note_id)).first()
    if not note:
        return success_response(code=404, msg="托运书不存在")
        
    if note.transport_type == "0":
        from app.models.peer_air_manual_data import PeerAirDepartureManualData
        manual_data = db.query(PeerAirDepartureManualData).filter(
            PeerAirDepartureManualData.consignment_note_id == int(data.consignment_note_id)
        ).first()
        
        if not manual_data:
            manual_data = PeerAirDepartureManualData(
                consignment_note_id=int(data.consignment_note_id)
            )
            db.add(manual_data)
            
        manual_data.waybill_number = data.waybill_number
        manual_data.customer_name = data.customer_name
        manual_data.cargo_type = data.cargo_type
        manual_data.packaging_fee = data.packaging_fee
        manual_data.telegram_fee = data.telegram_fee
        manual_data.telegram_code = data.telegram_code
        manual_data.cca = data.cca
        manual_data.door_pickup_fee = data.door_pickup_fee
        manual_data.door_pickup_company = data.door_pickup_company
        manual_data.airport_pickup_fee = data.airport_pickup_fee
        manual_data.airport_pickup_company = data.airport_pickup_company
        manual_data.delivery_fee = data.delivery_fee
        manual_data.delivery_company = data.delivery_company
        manual_data.carrier_deduction = data.carrier_deduction
        manual_data.other_fees = data.other_fees
        manual_data.manual_total_amount = data.manual_total_amount
        manual_data.remark = data.remark
        
        if action == "save":
            if manual_data.audit_status == 0 or manual_data.audit_status is None:
                manual_data.audit_status = 1
            msg = "暂存成功"
        elif action == "submit":
            manual_data.audit_status = 2
            manual_data.auditor_id = current_user.id
            manual_data.auditor_name = current_user.name
            manual_data.audit_time = get_china_now()
            msg = "审核成功"
        else:
            return success_response(code=400, msg="未知的操作类型")
            
    elif note.transport_type == "1":
        from app.models.peer_road_manual_data import PeerRoadDepartureManualData
        manual_data = db.query(PeerRoadDepartureManualData).filter(
            PeerRoadDepartureManualData.consignment_note_id == int(data.consignment_note_id)
        ).first()
        
        if not manual_data:
            manual_data = PeerRoadDepartureManualData(
                consignment_note_id=int(data.consignment_note_id)
            )
            db.add(manual_data)
            
        if action == "save":
            if manual_data.audit_status == 0 or manual_data.audit_status is None:
                manual_data.audit_status = 1
            msg = "暂存成功"
        elif action == "submit":
            manual_data.audit_status = 2
            manual_data.auditor_id = current_user.id
            manual_data.auditor_name = current_user.name
            manual_data.audit_time = get_china_now()
            msg = "审核成功"
        else:
            return success_response(code=400, msg="未知的操作类型")
    else:
        return success_response(code=400, msg="不支持的托运类型")
        
    db.commit()
    return success_response(msg=msg)


@router.post("/financial/audit", summary="财务单据暂存/确认审核")
async def financial_audit_consignment_note(
    payload: ConsignmentNoteFinancialAudit,
    action: str = Query(..., description="操作类型: save (暂存), submit (审核提交)"),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    财务单据暂存/确认审核接口
    """
    from app.utils.helpers import get_china_now
    
    note = db.query(ConsignmentNote).filter(ConsignmentNote.id == int(payload.consignment_note_id)).first()
    if not note:
        return success_response(code=404, msg="托运书不存在")
        
    if note.transport_type == "0":
        from app.models.peer_air_manual_data import PeerAirDepartureManualData
        manual_data = db.query(PeerAirDepartureManualData).filter(
            PeerAirDepartureManualData.consignment_note_id == int(payload.consignment_note_id)
        ).first()
        if not manual_data:
            manual_data = PeerAirDepartureManualData(
                consignment_note_id=int(payload.consignment_note_id)
            )
            db.add(manual_data)
            
        if action == "save":
            if manual_data.financial_audit_status == 0 or manual_data.financial_audit_status is None:
                manual_data.financial_audit_status = 1
            msg = "暂存成功"
        elif action == "submit":
            manual_data.financial_audit_status = 2
            manual_data.financial_auditor_id = current_user.id
            manual_data.financial_auditor_name = current_user.name
            manual_data.financial_audit_time = get_china_now()
            msg = "审核成功"
        else:
            return success_response(code=400, msg="未知的操作类型")
            
    elif note.transport_type == "1":
        from app.models.peer_road_manual_data import PeerRoadDepartureManualData
        manual_data = db.query(PeerRoadDepartureManualData).filter(
            PeerRoadDepartureManualData.consignment_note_id == int(payload.consignment_note_id)
        ).first()
        
        if not manual_data:
            manual_data = PeerRoadDepartureManualData(
                consignment_note_id=int(payload.consignment_note_id)
            )
            db.add(manual_data)
            
        if action == "save":
            if manual_data.financial_audit_status == 0 or manual_data.financial_audit_status is None:
                manual_data.financial_audit_status = 1
            msg = "暂存成功"
        elif action == "submit":
            manual_data.financial_audit_status = 2
            manual_data.financial_auditor_id = current_user.id
            manual_data.financial_auditor_name = current_user.name
            manual_data.financial_audit_time = get_china_now()
            msg = "审核成功"
        else:
            return success_response(code=400, msg="未知的操作类型")
    else:
        return success_response(code=400, msg="不支持的托运类型")
        
    db.commit()
    return success_response(msg=msg)



