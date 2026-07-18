"""
公司管理接口
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.exceptions import NotFoundException
from app.core.response import success_response, ResponseModel
from app.database import get_db
from app.api.deps import get_current_active_user
from app.utils.helpers import format_datetime_china

from app.models.company import CompanyAccount, CompanyInfo
from app.schemas.company import (
    CompanyAccountCreate,
    CompanyAccountUpdate,
    CompanyAccountResponse,
    CompanyListResponse,
    CompanyInfoUpdate
)

router = APIRouter()


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
    is_first = db.query(CompanyAccount).count() == 0
    is_active = True if is_first else account.is_active

    new_account = CompanyAccount(
        account_name=account.account_name,
        account_number=account.account_number,
        bank_name=account.bank_name,
        is_active=is_active
    )
    db.add(new_account)
    db.flush() 
    
    if is_active:
        db.query(CompanyAccount).filter(CompanyAccount.id != new_account.id).update({"is_active": False})
        
    db.commit()
    db.refresh(new_account)
    
    account_data = {
        "id": str(new_account.id),
        "account_name": new_account.account_name,
        "account_number": new_account.account_number,
        "bank_name": new_account.bank_name,
        "is_active": new_account.is_active,
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
    
    if update_data.get("is_active") is True:
        db.query(CompanyAccount).filter(CompanyAccount.id != account.id).update({"is_active": False})
        
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
        "is_active": account.is_active,
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
        "is_active": account.is_active,
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
        
    was_active = account.is_active
    db.delete(account)
    db.flush()
    
    if was_active:
        latest = db.query(CompanyAccount).order_by(CompanyAccount.created_at.desc(), CompanyAccount.id.desc()).first()
        if latest:
            latest.is_active = True
            
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
            "is_active": account.is_active,
            "created_at": format_datetime_china(account.created_at),
            "updated_at": format_datetime_china(account.updated_at)
        }
        for account in accounts
    ]
    
    company_info = db.query(CompanyInfo).filter(CompanyInfo.id == 1).first()
    if not company_info:
        company_info = CompanyInfo(id=1)
        db.add(company_info)
        db.commit()
        db.refresh(company_info)
    
    qr_codes = company_info.payment_qr_codes or []
    formatted_qr_codes = []
    if qr_codes and isinstance(qr_codes[0], str):
        formatted_qr_codes = [{"url": url, "wechat_name": "", "is_active": i == 0} for i, url in enumerate(qr_codes)]
    else:
        formatted_qr_codes = []
        for qr in qr_codes:
            if isinstance(qr, dict):
                if "wechat_name" not in qr or qr["wechat_name"] is None:
                    qr["wechat_name"] = ""
                formatted_qr_codes.append(qr)
            else:
                formatted_qr_codes.append(qr)

    data = {
        "company_name": company_info.company_name,
        "company_location": company_info.company_location,
        "payment_qr_codes": formatted_qr_codes,
        "accounts": account_list
    }
    
    return success_response(data=data, msg="查询成功")


@router.put("/info", summary="修改公司基本信息", response_model=ResponseModel[Any])
async def update_company_info(
    payload: CompanyInfoUpdate,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    更新公司基本信息（支持部分更新）。
    可更新公司名称、地址以及上传好的收款码URL列表。
    """
    company_info = db.query(CompanyInfo).filter(CompanyInfo.id == 1).first()
    if not company_info:
        company_info = CompanyInfo(id=1)
        db.add(company_info)
        db.commit()
        db.refresh(company_info)
        
    update_data = payload.model_dump(exclude_unset=True)
    
    if "payment_qr_codes" in update_data and update_data["payment_qr_codes"] is not None:
        qr_codes = update_data["payment_qr_codes"]
        if len(qr_codes) > 0:
            active_count = sum(1 for qr in qr_codes if qr.get("is_active"))
            if active_count != 1:
                return success_response(code=400, msg="收款码必须有且只能激活一个")
                
    for key, value in update_data.items():
        if value is not None:
            setattr(company_info, key, value)
            
    db.commit()
    
    return success_response(msg="公司信息更新成功")
