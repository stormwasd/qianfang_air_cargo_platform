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
    page: int = Query(1, description="页码", ge=1),
    pageSize: int = Query(10, description="每页数量", ge=1, le=500),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    查询深航出港列表，主表为 shenzhen_air_booking_exports，附带 shenzhen_air_billing_time_containers 数据。
    """
    query = db.query(ShenzhenAirBookingExport)

    # 1. 航班号查询
    if flight_number:
        query = query.filter(
            or_(
                ShenzhenAirBookingExport.billing_flight.like(f"%{flight_number}%"),
                ShenzhenAirBookingExport.actual_flight.like(f"%{flight_number}%")
            )
        )
        
    # 2. 航班日期区间查询
    if flight_date_start:
        query = query.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') >= flight_date_start)
    if flight_date_end:
        query = query.filter(func.replace(ShenzhenAirBookingExport.flight_date, '/', '-') <= f"{flight_date_end} 23:59:59")

    # 3. 运单号多单号查询
    if waybill_number:
        waybill_numbers = [wn.strip() for wn in waybill_number.split(",") if wn.strip()]
        if waybill_numbers:
            query = query.filter(ShenzhenAirBookingExport.waybill_number.in_(waybill_numbers))

    # 计算总数
    total = query.count()

    # 分页查询主表数据，修复由于 created_at 相同导致的分页乱序问题
    offset = (page - 1) * pageSize
    exports = query.order_by(
        ShenzhenAirBookingExport.flight_date.desc(), 
        ShenzhenAirBookingExport.id.desc()
    ).offset(offset).limit(pageSize).all()


    # 如果当前页没有数据，直接返回
    if not exports:
        return success_response(
            data={"total": total, "items": [], "data_update_time": None},
            msg="查询成功"
        )

    # 4. 提取当前页的所有主表单号的后8位，用于批量查询从表
    # 主表的运单号通常格式为 479-12345678 或 12345678
    # 从表的运单号明确为 waybill_number_8 (12345678)
    waybill_8_list = []
    export_by_wb8 = {}  # 记录后8位与主表实体的对应关系，用于组装
    
    for export in exports:
        if export.waybill_number:
            wb8 = export.waybill_number[-8:] if len(export.waybill_number) >= 8 else export.waybill_number
            waybill_8_list.append(wb8)
            # 建立映射表
            if wb8 not in export_by_wb8:
                export_by_wb8[wb8] = []
            export_by_wb8[wb8].append(export)

    # 5. 批量查询关联的从表数据
    containers = []
    manual_datas = []
    if waybill_8_list:
        containers = db.query(ShenzhenAirBillingTimeContainer).filter(
            ShenzhenAirBillingTimeContainer.waybill_number_8.in_(waybill_8_list)
        ).all()
        
        from app.models.departure_manual_data import ShenzhenAirDepartureManualData
        manual_datas = db.query(ShenzhenAirDepartureManualData).filter(
            ShenzhenAirDepartureManualData.waybill_number_8.in_(waybill_8_list)
        ).all()

    # 6. 在内存中组装数据
    # 按主表对象的ID初始化空列表
    containers_by_export_id = {export.id: [] for export in exports}
    manual_data_by_wb8 = {md.waybill_number_8: md for md in manual_datas}
    
    for container in containers:
        wb8 = container.waybill_number_8
        if wb8 in export_by_wb8:
            for matched_export in export_by_wb8[wb8]:
                containers_by_export_id[matched_export.id].append(container)

    # 构造返回列表
    items = []
    from app.schemas.departure_tracking import ShenzhenAirDepartureManualDataDTO
    for export in exports:
        export_dict = {k: v for k, v in export.__dict__.items() if not k.startswith('_')}
        export_dict["id"] = str(export.id)  # 转字符串防止精度丢失
        
        # 使用 Pydantic 严格按照 Schema 定义的顺序和类型进行序列化
        item_schema = ShenzhenAirDepartureItem(**export_dict)
        
        # 组装子表数据
        containers_data = []
        for c in containers_by_export_id[export.id]:
            c_dict = {k: v for k, v in c.__dict__.items() if not k.startswith('_')}
            c_dict["id"] = str(c.id)
            containers_data.append(ShenzhenAirBillingTimeContainerDTO(**c_dict))
            
        item_schema.billing_time_containers = containers_data
        
        # 组装手动扩展数据
        wb8 = export.waybill_number[-8:] if export.waybill_number and len(export.waybill_number) >= 8 else export.waybill_number
        if wb8 and wb8 in manual_data_by_wb8:
            md = manual_data_by_wb8[wb8]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            item_schema.manual_data = ShenzhenAirDepartureManualDataDTO(**md_dict)
        
        # 转换为字典，保持键顺序一致
        items.append(item_schema.model_dump(mode="json"))

    # 提取数据更新时间（第一条记录的 updated_at，格式化到分钟）
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
    
    # 根据 waybill_number_8 查询是否已存在
    manual_data = db.query(ShenzhenAirDepartureManualData).filter(
        ShenzhenAirDepartureManualData.waybill_number_8 == data.waybill_number_8
    ).first()
    
    if manual_data:
        # 更新
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(manual_data, key, value)
        msg = "更新成功"
    else:
        # 插入
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
        ShenzhenAirDepartureManualData.waybill_number_8 == data.waybill_number_8
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

# ========== 南航出港跟踪接口 ==========

from app.schemas.departure_tracking import CsaDepartureItem, CsaProductInformationDTO, CsaLalamoveInformationDTO, CsaDepartureManualDataDTO

@router.get("/china-southern-air", summary="南航出港列表")
async def get_china_southern_air_departures(
    waybill_number: Optional[str] = Query(None, description="运单号，多个用逗号隔开"),
    flight_date_start: Optional[str] = Query(None, description="航班日期开始，如2026-06-16"),
    flight_date_end: Optional[str] = Query(None, description="航班日期结束，如2026-06-20"),
    flight_number: Optional[str] = Query(None, description="航班号"),
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

    # 1. 航班号查询（从 flight_info 中匹配，如 "CZ8577 / 2026-06-16 / SZX - WUH"）
    if flight_number:
        query = query.filter(
            ChinaSouthernAirApprovalData.flight_info.like(f"%{flight_number}%")
        )
    
    # 2. 航班日期区间查询（从 flight_info 中提取日期部分进行比较）
    # flight_info 格式如: "CZ8577 / 2026-06-16 / SZX - WUH"，第二段是日期
    if flight_date_start or flight_date_end:
        date_str = func.trim(func.substring_index(func.substring_index(ChinaSouthernAirApprovalData.flight_info, ' / ', 2), ' / ', -1))
        if flight_date_start:
            query = query.filter(func.replace(date_str, '/', '-') >= flight_date_start)
        if flight_date_end:
            query = query.filter(func.replace(date_str, '/', '-') <= f"{flight_date_end} 23:59:59")

    # 3. 运单号多单号查询
    if waybill_number:
        waybill_numbers = [wn.strip() for wn in waybill_number.split(",") if wn.strip()]
        if waybill_numbers:
            query = query.filter(ChinaSouthernAirApprovalData.waybill_number.in_(waybill_numbers))

    # 计算总数
    total = query.count()

    # 分页查询
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

    # 4. 提取当前页所有主表 ID，用于批量查询子表
    record_ids = [r.id for r in records]
    
    # 批量查询本站货物数据
    product_infos = db.query(CsaProductInformation).filter(
        CsaProductInformation.approval_data_id.in_(record_ids)
    ).all()
    
    # 批量查询货拉数据
    lalamove_infos = db.query(CsaLalamoveInformation).filter(
        CsaLalamoveInformation.approval_data_id.in_(record_ids)
    ).all()

    # 批量查询手动数据（通过 approval_data_id 关联）
    manual_datas = db.query(CsaDepartureManualData).filter(
        CsaDepartureManualData.approval_data_id.in_(record_ids)
    ).all()

    # 5. 在内存中组装数据
    products_by_id = {}
    for p in product_infos:
        products_by_id.setdefault(p.approval_data_id, []).append(p)

    lalamove_by_id = {}
    for l in lalamove_infos:
        lalamove_by_id.setdefault(l.approval_data_id, []).append(l)

    manual_data_by_id = {md.approval_data_id: md for md in manual_datas}

    # 6. 构造返回列表
    items = []
    for record in records:
        record_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_')}
        record_dict["id"] = str(record.id)

        item_schema = CsaDepartureItem(**record_dict)

        # 组装本站货物数据
        for p in products_by_id.get(record.id, []):
            p_dict = {k: v for k, v in p.__dict__.items() if not k.startswith('_')}
            p_dict["id"] = str(p.id)
            p_dict["approval_data_id"] = str(p.approval_data_id)
            item_schema.product_information.append(CsaProductInformationDTO(**p_dict))

        # 组装货拉数据
        for l in lalamove_by_id.get(record.id, []):
            l_dict = {k: v for k, v in l.__dict__.items() if not k.startswith('_')}
            l_dict["id"] = str(l.id)
            l_dict["approval_data_id"] = str(l.approval_data_id)
            item_schema.lalamove_information.append(CsaLalamoveInformationDTO(**l_dict))

        # 组装手动录入数据
        if record.id in manual_data_by_id:
            md = manual_data_by_id[record.id]
            md_dict = {k: v for k, v in md.__dict__.items() if not k.startswith('_')}
            md_dict["id"] = str(md.id)
            md_dict["approval_data_id"] = str(md.approval_data_id)
            item_schema.manual_data = CsaDepartureManualDataDTO(**md_dict)

        items.append(item_schema.model_dump(mode="json"))

    # 提取数据更新时间（第一条记录的 updated_at，格式化到分钟）
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
    
    # 根据 approval_data_id 查询是否已存在
    manual_data = db.query(CsaDepartureManualData).filter(
        CsaDepartureManualData.approval_data_id == int(data.approval_data_id)
    ).first()
    
    if manual_data:
        # 更新
        update_data = data.model_dump(exclude_unset=True, exclude={"approval_data_id"})
        for key, value in update_data.items():
            setattr(manual_data, key, value)
        msg = "更新成功"
    else:
        # 插入
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

