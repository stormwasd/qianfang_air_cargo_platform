"""
API路由统一注册（仅保留用户管理、数据字典与公共模块）
"""
from fastapi import APIRouter
from app.config import settings
from app.api import auth, users, departments, config, user_center, common, customer_service, cost_service

api_router = APIRouter(prefix=settings.API_V1_PREFIX)

api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(config.router, prefix="/config", tags=["业务参数管理"])
api_router.include_router(departments.router, prefix="/departments", tags=["部门管理"])
api_router.include_router(users.router, prefix="/users", tags=["账号管理"])
api_router.include_router(user_center.router, prefix="/user-center", tags=["用户中心"])
api_router.include_router(common.router, prefix="/common", tags=["公共模块"])
api_router.include_router(customer_service.router, prefix="/customer-service", tags=["客服接单台"])
api_router.include_router(cost_service.router, prefix="/cost-service", tags=["费用登记台"])


__all__ = ["api_router"]



