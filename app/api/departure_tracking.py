from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import Optional, List
from app.database import get_db
from app.api.deps import get_current_active_user
from app.core.response import success_response
from app.models.transit_loading import ShenzhenAirBookingExport
from app.models.billing_time_container import ShenzhenAirBillingTimeContainer
from app.schemas.departure_tracking import ShenzhenAirDepartureListResponse, ShenzhenAirDepartureItem, ShenzhenAirBillingTimeContainerDTO

router = APIRouter()

@router.get("/shenzhen-air", summary="深航出港列表")
async def get_shenzhen_air_departures(
    waybill_number: Optional[str] = Query(None, description="运单号，多个用逗号隔开"),
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-03-10"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-03-15"),
    flight_number: Optional[str] = Query(None, description="航班号"),
    audit_status: Optional[int] = Query(None, description="审核状态(0:未审, 1:暂存, 2:已审)"),
    origin: Optional[str] = Query(None, description="始发站"),
    destination: Optional[str] = Query(None, description="目的站"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    is_suspected_abnormal: Optional[bool] = Query(None, description="疑似异常"),
    page: int = Query(1, description="页码", ge=1),
    pageSize: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询深航出港列表，主表为 shenzhen_air_booking_exports，附带 shenzhen_air_billing_time_containers 数据。
    """
    query = db.query(ShenzhenAirBookingExport)

    if audit_status is not None or customer_name:
        from app.models.departure_manual_data import ShenzhenAirDepartureManualData
        query = query.outerjoin(
            ShenzhenAirDepartureManualData,
            ShenzhenAirDepartureManualData.booking_export_id == ShenzhenAirBookingExport.id
        )
        
        if audit_status is not None:
            if audit_status == 0:
                query = query.filter(
                    or_(
                        ShenzhenAirDepartureManualData.audit_status == 0,
                        ShenzhenAirDepartureManualData.audit_status.is_(None)
                    )
                )
            else:
                query = query.filter(ShenzhenAirDepartureManualData.audit_status == audit_status)
                
        if customer_name:
            query = query.filter(ShenzhenAirDepartureManualData.customer_name.like(f"%{customer_name}%"))

    if flight_number:
        query = query.filter(ShenzhenAirBookingExport.billing_flight.like(f"%{flight_number}%"))
        
    if flight_date_start:
        query = query.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') >= flight_date_start)
    if flight_date_end:
        query = query.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') <= f"{flight_date_end} 23:59:59")

    if waybill_number:
        waybill_numbers = [wn.strip() for wn in waybill_number.split(",") if wn.strip()]
        if waybill_numbers:
            query = query.filter(ShenzhenAirBookingExport.waybill_number.in_(waybill_numbers))

    if origin:
        query = query.filter(ShenzhenAirBookingExport.routing.like(f"{origin}-%"))
    if destination:
        query = query.filter(ShenzhenAirBookingExport.routing.like(f"%-{destination}"))
        
    if is_suspected_abnormal:
        from app.models.alert_notification_record import AlertNotificationRecord
        query = query.filter(
            func.cast(ShenzhenAirBookingExport.id, String).in_(
                db.query(AlertNotificationRecord.target_id)
                .filter(
                    AlertNotificationRecord.module_name == "shenzhen_air_departure_status",
                    AlertNotificationRecord.state_hash != "0.0_0.0_False"
                )
            )
        )

    total = query.count()

    offset = (page - 1) * pageSize
    exports = query.order_by(
        ShenzhenAirBookingExport.flight_date.desc(), 
        ShenzhenAirBookingExport.id.desc()
    ).offset(offset).limit(pageSize).all()


    if not exports:
        return success_response(
            data={"total": total, "items": [], "data_update_time": None},
            msg="查询成功"
        )

    export_ids = [export.id for export in exports]
    containers = []
    manual_datas = []
    
    if export_ids:
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.booking_export_id.in_(export_ids)
        ).all()
        
        from app.models.departure_manual_data import ShenzhenAirDepartureManualData
        manual_datas = db.query(ShenzhenAirDepartureManualData).filter(
            ShenzhenAirDepartureManualData.booking_export_id.in_(export_ids)
        ).all()

    containers_by_export_id = {export.id: [] for export in exports}
    manual_data_by_export_id = {md.booking_export_id: md for md in manual_datas}
    
    for container in containers:
        if container.booking_export_id in containers_by_export_id:
            containers_by_export_id[container.booking_export_id].append(container)

    items = []
    from app.schemas.departure_tracking import ShenzhenAirDepartureManualDataDTO
    for export in exports:
        export_dict = {k: v for k, v in export.__dict__.items() if not k.startswith('_')}
        export_dict["id"] = str(export.id)  
        
        item_schema = ShenzhenAirDepartureItem(**export_dict)
        
        containers_data = []
        for c in containers_by_export_id[export.id]:
            c_dict = {k: v for k, v in c.__dict__.items() if not k.startswith('_')}
            c_dict["id"] = str(c.id)
            c_dict["booking_export_id"] = str(c.booking_export_id) if c.booking_export_id is not None else None
            containers_data.append(ShenzhenAirBillingTimeContainerDTO(**c_dict))
            
        item_schema.billing_time_containers = containers_data
        
        if export.id in manual_data_by_export_id:
            md = manual_data_by_export_id[export.id]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            md_dict["booking_export_id"] = str(md.booking_export_id)
            item_schema.manual_data = ShenzhenAirDepartureManualDataDTO(**md_dict)
        
        items.append(item_schema.model_dump(mode="json"))

    data_update_time = None
    if exports and hasattr(exports[0], 'updated_at') and exports[0].updated_at:
        data_update_time = exports[0].updated_at.strftime("%Y-%m-%d %H:%M")

    return success_response(
        data={"total": total, "items": items, "data_update_time": data_update_time},
        msg="查询成功"
    )

from app.schemas.departure_tracking import ShenzhenAirDepartureManualDataUpsert

@router.post("/shenzhen-air/manual-data", summary="保存深航出港列表手动录入数据")
@router.put("/shenzhen-air/manual-data", summary="更新深航出港列表手动录入数据")
async def upsert_shenzhen_air_manual_data(
    data: ShenzhenAirDepartureManualDataUpsert,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models.departure_manual_data import ShenzhenAirDepartureManualData
    
    manual_data = db.query(ShenzhenAirDepartureManualData).filter(
        ShenzhenAirDepartureManualData.booking_export_id == data.booking_export_id
    ).first()
    
    if manual_data:
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(manual_data, key, value)
        msg = "更新成功"
    else:
        manual_data = ShenzhenAirDepartureManualData(**data.model_dump())
        db.add(manual_data)
        msg = "保存成功"
        
    db.commit()
    
    return success_response(msg=msg)


from app.schemas.departure_tracking import ShenzhenAirDepartureAuditRequest
from app.utils.helpers import get_china_now

@router.post("/shenzhen-air/audit", summary="深航出港运单单据审核与暂存")
async def audit_shenzhen_air_departure(
    data: ShenzhenAirDepartureAuditRequest,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models.departure_manual_data import ShenzhenAirDepartureManualData
    
    manual_data = db.query(ShenzhenAirDepartureManualData).filter(
        ShenzhenAirDepartureManualData.booking_export_id == data.booking_export_id
    ).first()
    
    update_data = data.model_dump(exclude={"action"}, exclude_unset=True)
    
    if manual_data:
        for key, value in update_data.items():
            setattr(manual_data, key, value)
    else:
        manual_data = ShenzhenAirDepartureManualData(**update_data)
        db.add(manual_data)

    if data.action == "draft":
        manual_data.audit_status = 1
        msg = "暂存成功"
    elif data.action == "submit":
        manual_data.audit_status = 2
        manual_data.auditor_id = current_user.id
        manual_data.auditor_name = current_user.name
        manual_data.audit_time = get_china_now()
        msg = "审核成功"
    else:
        return success_response(code=400, msg="未知的操作类型")

    db.commit()
    return success_response(msg=msg)


from app.schemas.departure_tracking import CsaDepartureItem, CsaProductInformationDTO, CsaLalamoveInformationDTO, CsaDepartureManualDataDTO

@router.get("/china-southern-air", summary="南航出港列表")
async def get_china_southern_air_departures(
    waybill_number: Optional[str] = Query(None, description="运单号，多个用逗号隔开"),
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-06-16"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-06-20"),
    flight_number: Optional[str] = Query(None, description="航班号"),
    audit_status: Optional[int] = Query(None, description="审核状态(0:未审, 1:暂存, 2:已审)"),
    origin: Optional[str] = Query(None, description="始发站"),
    destination: Optional[str] = Query(None, description="目的站"),
    customer_name: Optional[str] = Query(None, description="客户名称"),
    waybill_status: Optional[str] = Query(None, description="运单状态(例如 UU, KK), 对应 booking_no 中的标识"),
    is_suspected_abnormal: Optional[bool] = Query(None, description="疑似异常"),
    page: int = Query(1, description="页码", ge=1),
    pageSize: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询南航出港列表，主表为 china_southern_air_approval_data，
    附带 csa_product_information、csa_lalamove_information 和 csa_departure_manual_data 数据。
    """
    from app.models.china_southern_air_approval import ChinaSouthernAirApprovalData
    from app.models.csa_departure_tracking import CsaProductInformation, CsaLalamoveInformation
    from app.models.csa_departure_manual_data import CsaDepartureManualData
    import re as _re

    query = db.query(ChinaSouthernAirApprovalData)

    if audit_status is not None or customer_name:
        query = query.outerjoin(
            CsaDepartureManualData,
            ChinaSouthernAirApprovalData.id == CsaDepartureManualData.approval_data_id
        )
        
        if audit_status is not None:
            if audit_status == 0:
                query = query.filter(
                    or_(
                        CsaDepartureManualData.audit_status == 0,
                        CsaDepartureManualData.audit_status.is_(None)
                    )
                )
            else:
                query = query.filter(CsaDepartureManualData.audit_status == audit_status)
                
        if customer_name:
            query = query.filter(CsaDepartureManualData.customer_name.like(f"%{customer_name}%"))

    if flight_number:
        query = query.filter(
            ChinaSouthernAirApprovalData.flight_info.like(f"%{flight_number}%")
        )
        
    if waybill_status:
        query = query.filter(
            ChinaSouthernAirApprovalData.booking_no.like(f"%{waybill_status}%")
        )
    
    if flight_date_start or flight_date_end:
        date_str = func.trim(func.substring_index(func.substring_index(ChinaSouthernAirApprovalData.flight_info, ' / ', 2), ' / ', -1))
        if flight_date_start:
            query = query.filter(func.replace(date_str, '/', '-') >= flight_date_start)
        if flight_date_end:
            query = query.filter(func.replace(date_str, '/', '-') <= f"{flight_date_end} 23:59:59")

    if waybill_number:
        waybill_numbers = [wn.strip() for wn in waybill_number.split(",") if wn.strip()]
        if waybill_numbers:
            query = query.filter(ChinaSouthernAirApprovalData.waybill_number.in_(waybill_numbers))

    if origin:
        query = query.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%{origin} -%"))
    if destination:
        query = query.filter(ChinaSouthernAirApprovalData.flight_info.like(f"%- {destination}%"))
        
    if is_suspected_abnormal:
        from app.models.alert_notification_record import AlertNotificationRecord
        query = query.filter(
            func.cast(ChinaSouthernAirApprovalData.id, String).in_(
                db.query(AlertNotificationRecord.target_id)
                .filter(
                    AlertNotificationRecord.module_name == "csa_departure_status",
                    AlertNotificationRecord.state_hash != "0.0_0.0_False"
                )
            )
        )

    total = query.count()

    offset = (page - 1) * pageSize
    records = query.order_by(
        ChinaSouthernAirApprovalData.flight_info.desc(),
        ChinaSouthernAirApprovalData.id.desc()
    ).offset(offset).limit(pageSize).all()

    if not records:
        return success_response(
            data={"total": total, "items": [], "data_update_time": None},
            msg="查询成功"
        )

    record_ids = [r.id for r in records]
    
    product_infos = db.query(CsaProductInformation).filter(
        CsaProductInformation.approval_data_id.in_(record_ids)
    ).all()
    
    lalamove_infos = db.query(CsaLalamoveInformation).filter(
        CsaLalamoveInformation.approval_data_id.in_(record_ids)
    ).all()

    manual_datas = db.query(CsaDepartureManualData).filter(
        CsaDepartureManualData.approval_data_id.in_(record_ids)
    ).all()

    products_by_id = {}
    for p in product_infos:
        products_by_id.setdefault(p.approval_data_id, []).append(p)

    lalamove_by_id = {}
    for l in lalamove_infos:
        lalamove_by_id.setdefault(l.approval_data_id, []).append(l)

    manual_data_by_id = {md.approval_data_id: md for md in manual_datas}

    items = []
    for record in records:
        record_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
        record_dict["id"] = str(record.id)

        item_schema = CsaDepartureItem(**record_dict)

        for p in products_by_id.get(record.id, []):
            p_dict = {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
            p_dict["id"] = str(p.id)
            p_dict["approval_data_id"] = str(p.approval_data_id)
            item_schema.product_information.append(CsaProductInformationDTO(**p_dict))

        for l in lalamove_by_id.get(record.id, []):
            l_dict = {k: v for k, v in l.__dict__.items() if not k.startswith('_')}
            l_dict["id"] = str(l.id)
            l_dict["approval_data_id"] = str(l.approval_data_id)
            item_schema.lalamove_information.append(CsaLalamoveInformationDTO(**l_dict))

        if record.id in manual_data_by_id:
            md = manual_data_by_id[record.id]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            md_dict["approval_data_id"] = str(md.approval_data_id)
            item_schema.manual_data = CsaDepartureManualDataDTO(**md_dict)

        items.append(item_schema.model_dump(mode="json"))

    data_update_time = None
    if records and hasattr(records[0], 'updated_at') and records[0].updated_at:
        data_update_time = records[0].updated_at.strftime("%Y-%m-%d %H:%M")

    return success_response(
        data={"total": total, "items": items, "data_update_time": data_update_time},
        msg="查询成功"
    )


from app.schemas.departure_tracking import CsaDepartureManualDataUpsert

@router.post("/china-southern-air/manual-data", summary="保存南航出港列表手动录入数据")
@router.put("/china-southern-air/manual-data", summary="更新南航出港列表手动录入数据")
async def upsert_china_southern_air_manual_data(
    data: CsaDepartureManualDataUpsert,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models.csa_departure_manual_data import CsaDepartureManualData
    
    manual_data = db.query(CsaDepartureManualData).filter(
        CsaDepartureManualData.approval_data_id == int(data.approval_data_id)
    ).first()
    
    if manual_data:
        update_data = data.model_dump(exclude_unset=True, exclude={"approval_data_id"})
        for key, value in update_data.items():
            setattr(manual_data, key, value)
        msg = "更新成功"
    else:
        insert_data = data.model_dump()
        insert_data["approval_data_id"] = int(insert_data["approval_data_id"])
        manual_data = CsaDepartureManualData(**insert_data)
        db.add(manual_data)
        msg = "保存成功"
        
    db.commit()
    
    return success_response(msg=msg)


from app.schemas.departure_tracking import CsaDepartureAuditRequest

@router.post("/china-southern-air/audit", summary="南航出港运单单据审核与暂存")
async def audit_china_southern_air_departure(
    data: CsaDepartureAuditRequest,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    from app.models.csa_departure_manual_data import CsaDepartureManualData
    
    manual_data = db.query(CsaDepartureManualData).filter(
        CsaDepartureManualData.approval_data_id == int(data.approval_data_id)
    ).first()
    
    update_data = data.model_dump(exclude={"action", "approval_data_id"}, exclude_unset=True)
    
    if manual_data:
        for key, value in update_data.items():
            setattr(manual_data, key, value)
    else:
        insert_data = data.model_dump(exclude={"action"})
        insert_data["approval_data_id"] = int(insert_data["approval_data_id"])
        manual_data = CsaDepartureManualData(**insert_data)
        db.add(manual_data)

    if data.action == "draft":
        manual_data.audit_status = 1
        msg = "暂存成功"
    elif data.action == "submit":
        manual_data.audit_status = 2
        manual_data.auditor_id = current_user.id
        manual_data.auditor_name = current_user.name
        manual_data.audit_time = get_china_now()
        msg = "审核成功"
    else:
        return success_response(code=400, msg="未知的操作类型")

    db.commit()
    return success_response(msg=msg)

