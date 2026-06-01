"""
公司管理接口
"""
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from app.database import get_db
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

from app.models.company import CompanyAccount
from app.schemas.company import (
    CompanyAccountCreate,
    CompanyAccountUpdate,
    CompanyAccountResponse,
    CompanyListResponse
)

router = APIRouter()

# 基础公司信息常量
BASE_COMPANY_NAME = "丰德航空物流有限公司"
BASE_COMPANY_LOCATION = "深圳市宝安区宝安机场领航二路148号"


@router.post("/accounts", summary="新增公司账户", response_model=ResponseModel[CompanyAccountResponse])
async def create_company_account(
    account: CompanyAccountCreate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    新增公司账户接口
    
    - **account_name**: 账户名（必填）
    - **account_number**: 账号（必填）
    - **bank_name**: 开户行（必填）
    """
    new_account = CompanyAccount(
        account_name=account.account_name,
        account_number=account.account_number,
        bank_name=account.bank_name
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    
    account_data = {
        "id": str(new_account.id),
        "account_name": new_account.account_name,
        "account_number": new_account.account_number,
        "bank_name": new_account.bank_name,
        "created_at": format_datetime_china(new_account.created_at),
        "updated_at": format_datetime_china(new_account.updated_at)
    }
    
    return success_response(data=account_data, msg="公司账户创建成功")


@router.put("/accounts/{account_id}", summary="编辑公司账户", response_model=ResponseModel[CompanyAccountResponse])
async def update_company_account(
    account_id: str,
    payload: CompanyAccountUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    编辑公司账户接口（部分更新，仅更新传入的字段）
    
    - **account_id**: 账户ID（字符串格式）
    - **account_name**: 账户名（可选）
    - **account_number**: 账号（可选）
    - **bank_name**: 开户行（可选）
    """
    account = db.query(CompanyAccount).filter(CompanyAccount.id == int(account_id)).first()
    if not account:
        raise NotFoundException("公司账户不存在")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(account, key, value)
            
    db.commit()
    db.refresh(account)
    
    account_data = {
        "id": str(account.id),
        "account_name": account.account_name,
        "account_number": account.account_number,
        "bank_name": account.bank_name,
        "created_at": format_datetime_china(account.created_at),
        "updated_at": format_datetime_china(account.updated_at)
    }
    
    return success_response(data=account_data, msg="公司账户更新成功")


@router.get("/accounts/{account_id}", summary="获取公司账户详情", response_model=ResponseModel[CompanyAccountResponse])
async def get_company_account(
    account_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取公司账户详情接口
    
    - **account_id**: 账户ID（字符串格式）
    """
    account = db.query(CompanyAccount).filter(CompanyAccount.id == int(account_id)).first()
    if not account:
        raise NotFoundException("公司账户不存在")
    
    account_data = {
        "id": str(account.id),
        "account_name": account.account_name,
        "account_number": account.account_number,
        "bank_name": account.bank_name,
        "created_at": format_datetime_china(account.created_at),
        "updated_at": format_datetime_china(account.updated_at)
    }
    
    return success_response(data=account_data, msg="查询成功")


@router.delete("/accounts/{account_id}", summary="删除公司账户", response_model=ResponseModel[Any])
async def delete_company_account(
    account_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    删除公司账户接口
    
    - **account_id**: 账户ID（字符串格式）
    """
    account = db.query(CompanyAccount).filter(CompanyAccount.id == int(account_id)).first()
    if not account:
        raise NotFoundException("公司账户不存在")
        
    db.delete(account)
    db.commit()
    
    return success_response(msg="公司账户删除成功")


@router.get("", summary="获取公司信息及账户列表", response_model=ResponseModel[CompanyListResponse])
async def get_company_list(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    获取公司基础信息及所有账户列表接口
    """
    accounts = db.query(CompanyAccount).order_by(CompanyAccount.created_at.desc(), CompanyAccount.id.desc()).all()
    
    account_list = [
        {
            "id": str(account.id),
            "account_name": account.account_name,
            "account_number": account.account_number,
            "bank_name": account.bank_name,
            "created_at": format_datetime_china(account.created_at),
            "updated_at": format_datetime_china(account.updated_at)
        }
        for account in accounts
    ]
    
    data = {
        "company_name": BASE_COMPANY_NAME,
        "company_location": BASE_COMPANY_LOCATION,
        "accounts": account_list
    }
    
    return success_response(data=data, msg="查询成功")
