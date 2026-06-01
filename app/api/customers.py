"""
客户管理接口
"""
from decimal import Decimal
from typing import Any
from pypinyin import lazy_pinyin

from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate, CustomerQuery, CustomerUpdate, CustomerResponse, CustomerListResponse
)
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china, get_china_now

router = APIRouter()

def generate_customer_code(company_name: str) -> str:
    """生成客户编码：公司名拼音首字母+当前日期"""
    pinyin_list = lazy_pinyin(company_name)
    initials = "".join([p[0].upper() for p in pinyin_list if p and p[0].isalpha()])
    date_str = get_china_now().strftime("%Y%m%d")
    return f"{initials}{date_str}"


@router.post("", summary="新增客户信息", response_model=ResponseModel[CustomerResponse])
async def create_customer(
    customer: CustomerCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增客户信息接口（仅 company_name 必填，其余字段可选）

    - **company_name**: 承运单位/公司名称（必填）
    - **rate**: 费率(元/公斤)（可选，未传默认 0）
    - **contact_person**: 联系人（可选）
    - **contact_phone**: 联系电话（可选）
    """
    new_customer = Customer(
        customer_code=generate_customer_code(customer.company_name),
        company_name=customer.company_name,
        rate=customer.rate if customer.rate is not None else Decimal("0"),
        contact_person=customer.contact_person or "",
        contact_phone=customer.contact_phone or "",
        minimum_ticket_fee=customer.minimum_ticket_fee,
        document_fee=customer.document_fee,
        minimum_ticket_fee_condition=customer.minimum_ticket_fee_condition,
        document_fee_condition=customer.document_fee_condition,
        weight_range_operation_fee_rate=customer.weight_range_operation_fee_rate,
        cargo_type_transit_fee_rate=customer.cargo_type_transit_fee_rate,
        settlement_cycle=customer.settlement_cycle,
        is_invoiced=customer.is_invoiced if customer.is_invoiced is not None else False
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    
    customer_data = {
        "id": str(new_customer.id),
        "customer_code": new_customer.customer_code,
        "company_name": new_customer.company_name,
        "rate": new_customer.rate,
        "contact_person": new_customer.contact_person,
        "contact_phone": new_customer.contact_phone,
        "minimum_ticket_fee": new_customer.minimum_ticket_fee,
        "document_fee": new_customer.document_fee,
        "minimum_ticket_fee_condition": new_customer.minimum_ticket_fee_condition,
        "document_fee_condition": new_customer.document_fee_condition,
        "weight_range_operation_fee_rate": new_customer.weight_range_operation_fee_rate,
        "cargo_type_transit_fee_rate": new_customer.cargo_type_transit_fee_rate,
        "settlement_cycle": new_customer.settlement_cycle,
        "is_invoiced": new_customer.is_invoiced,
        "created_at": format_datetime_china(new_customer.created_at),
        "updated_at": format_datetime_china(new_customer.updated_at)
    }
    
    return success_response(data=customer_data, msg="客户创建成功")


@router.put("/{customer_id}", summary="编辑客户信息", response_model=ResponseModel[CustomerResponse])
async def update_customer(
    customer_id: str,
    payload: CustomerUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    编辑客户信息接口（部分更新，仅更新传入的字段）

    - **customer_id**: 客户ID（字符串格式）
    - **company_name**: 承运单位/公司名称（可选）
    - **rate**: 费率(元/公斤)（可选）
    - **contact_person**: 联系人（可选）
    - **contact_phone**: 联系电话（可选）
    """
    customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not customer:
        raise NotFoundException("客户不存在")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(customer, key, value)
        else:
            nullable_fields = [
                "minimum_ticket_fee", "document_fee", "minimum_ticket_fee_condition",
                "document_fee_condition", "weight_range_operation_fee_rate",
                "cargo_type_transit_fee_rate", "settlement_cycle"
            ]
            if key in nullable_fields:
                setattr(customer, key, None)
            elif key == "is_invoiced":
                setattr(customer, key, False)
            elif key == "rate":
                setattr(customer, key, Decimal("0"))
            else:
                setattr(customer, key, "")

    db.commit()
    db.refresh(customer)

    customer_data = {
        "id": str(customer.id),
        "customer_code": customer.customer_code,
        "company_name": customer.company_name,
        "rate": customer.rate,
        "contact_person": customer.contact_person,
        "contact_phone": customer.contact_phone,
        "minimum_ticket_fee": customer.minimum_ticket_fee,
        "document_fee": customer.document_fee,
        "minimum_ticket_fee_condition": customer.minimum_ticket_fee_condition,
        "document_fee_condition": customer.document_fee_condition,
        "weight_range_operation_fee_rate": customer.weight_range_operation_fee_rate,
        "cargo_type_transit_fee_rate": customer.cargo_type_transit_fee_rate,
        "settlement_cycle": customer.settlement_cycle,
        "is_invoiced": customer.is_invoiced,
        "created_at": format_datetime_china(customer.created_at),
        "updated_at": format_datetime_china(customer.updated_at)
    }
    return success_response(data=customer_data, msg="客户信息更新成功")


@router.get("", summary="客户信息查询", response_model=ResponseModel[CustomerListResponse])
async def get_customers(
    query: CustomerQuery = Depends(),
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    客户信息查询接口（支持模糊搜索）
    
    查询参数：
    - **company_name**: 公司名称（模糊搜索）
    - **contact_person**: 联系人（模糊搜索）
    - **page**: 页码（默认1）
    - **pageSize**: 每页数量（默认10，最大200）
    
    支持按公司名称和联系人进行模糊搜索
    """
    # 构建查询
    query_obj = db.query(Customer)
    
    # 模糊搜索条件
    if query.company_name:
        query_obj = query_obj.filter(
            Customer.company_name.like(f"%{query.company_name}%")
        )
    
    if query.contact_person:
        query_obj = query_obj.filter(
            Customer.contact_person.like(f"%{query.contact_person}%")
        )
    
    # 获取总数
    total = query_obj.count()
    
    # 分页
    offset = (query.page - 1) * query.page_size
    customers = query_obj.order_by(
        Customer.created_at.desc(), Customer.id.desc()
    ).offset(offset).limit(query.page_size).all()
    
    customer_list = [
        {
            "id": str(customer.id),
            "customer_code": customer.customer_code,
            "company_name": customer.company_name,
            "rate": customer.rate,
            "contact_person": customer.contact_person,
            "contact_phone": customer.contact_phone,
            "minimum_ticket_fee": customer.minimum_ticket_fee,
            "document_fee": customer.document_fee,
            "minimum_ticket_fee_condition": customer.minimum_ticket_fee_condition,
            "document_fee_condition": customer.document_fee_condition,
            "weight_range_operation_fee_rate": customer.weight_range_operation_fee_rate,
            "cargo_type_transit_fee_rate": customer.cargo_type_transit_fee_rate,
            "settlement_cycle": customer.settlement_cycle,
            "is_invoiced": customer.is_invoiced,
            "created_at": format_datetime_china(customer.created_at),
            "updated_at": format_datetime_china(customer.updated_at)
        }
        for customer in customers
    ]
    
    return success_response(
        data={"total": total, "items": customer_list},
        msg="查询成功"
    )


@router.get("/{customer_id}", summary="获取客户详情", response_model=ResponseModel[CustomerResponse])
async def get_customer(
    customer_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取客户详情接口
    
    - **customer_id**: 客户ID（字符串格式）
    """
    customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not customer:
        raise NotFoundException("客户不存在")
    
    customer_data = {
        "id": str(customer.id),
        "customer_code": customer.customer_code,
        "company_name": customer.company_name,
        "rate": customer.rate,
        "contact_person": customer.contact_person,
        "contact_phone": customer.contact_phone,
        "minimum_ticket_fee": customer.minimum_ticket_fee,
        "document_fee": customer.document_fee,
        "minimum_ticket_fee_condition": customer.minimum_ticket_fee_condition,
        "document_fee_condition": customer.document_fee_condition,
        "weight_range_operation_fee_rate": customer.weight_range_operation_fee_rate,
        "cargo_type_transit_fee_rate": customer.cargo_type_transit_fee_rate,
        "settlement_cycle": customer.settlement_cycle,
        "is_invoiced": customer.is_invoiced,
        "created_at": format_datetime_china(customer.created_at),
        "updated_at": format_datetime_china(customer.updated_at)
    }
    
    return success_response(data=customer_data, msg="查询成功")


@router.delete("/{customer_id}", summary="删除客户", response_model=ResponseModel[Any])
async def delete_customer(
    customer_id: str,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除客户接口
    
    - **customer_id**: 客户ID（字符串格式）
    """
    customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not customer:
        raise NotFoundException("客户不存在")
    
    db.delete(customer)
    db.commit()
    
    return success_response(msg="客户删除成功")

