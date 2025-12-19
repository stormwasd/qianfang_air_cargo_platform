"""
客户管理接口
"""
from fastapi import APIRouter, Depends
from app.core.exceptions import NotFoundException
from app.core.response import success_response
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.customer import Customer
from app.schemas.customer import (
    CustomerCreate, CustomerQuery
)
from app.api.deps import get_current_active_user

router = APIRouter()


@router.post("", summary="新增客户信息")
async def create_customer(
    customer: CustomerCreate,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增客户信息接口
    
    - **company_name**: 承运单位/公司名称
    - **settlement_method**: 结算方式
    - **rate**: 费率(元/公斤)
    - **contact_person**: 联系人
    - **contact_phone**: 联系电话
    """
    new_customer = Customer(
        company_name=customer.company_name,
        settlement_method=customer.settlement_method,
        rate=customer.rate,
        contact_person=customer.contact_person,
        contact_phone=customer.contact_phone
    )
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    
    customer_data = {
        "id": new_customer.id,
        "company_name": new_customer.company_name,
        "settlement_method": new_customer.settlement_method,
        "rate": float(new_customer.rate),
        "contact_person": new_customer.contact_person,
        "contact_phone": new_customer.contact_phone,
        "created_at": new_customer.created_at.isoformat(),
        "updated_at": new_customer.updated_at.isoformat()
    }
    
    return success_response(data=customer_data, msg="客户创建成功")


@router.get("", summary="客户信息查询")
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
    - **page_size**: 每页数量（默认10，最大100）
    
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
        Customer.created_at.desc()
    ).offset(offset).limit(query.page_size).all()
    
    customer_list = [
        {
            "id": customer.id,
            "company_name": customer.company_name,
            "settlement_method": customer.settlement_method,
            "rate": float(customer.rate),
            "contact_person": customer.contact_person,
            "contact_phone": customer.contact_phone,
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat()
        }
        for customer in customers
    ]
    
    return success_response(
        data={"total": total, "items": customer_list},
        msg="查询成功"
    )


@router.get("/{customer_id}", summary="获取客户详情")
async def get_customer(
    customer_id: int,
    current_user = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取客户详情接口
    
    - **customer_id**: 客户ID
    """
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise NotFoundException("客户不存在")
    
    customer_data = {
        "id": customer.id,
        "company_name": customer.company_name,
        "settlement_method": customer.settlement_method,
        "rate": float(customer.rate),
        "contact_person": customer.contact_person,
        "contact_phone": customer.contact_phone,
        "created_at": customer.created_at.isoformat(),
        "updated_at": customer.updated_at.isoformat()
    }
    
    return success_response(data=customer_data, msg="查询成功")

