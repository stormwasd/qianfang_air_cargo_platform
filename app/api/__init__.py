"""
API路由统一注册
"""
from fastapi import APIRouter
from app.config import settings
from app.api import auth, users, departments, customers, config, user_center

# 创建API v1路由器
api_router = APIRouter(prefix=settings.API_V1_PREFIX)

# 注册所有子路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(config.router, prefix="/config", tags=["业务参数管理"])
api_router.include_router(departments.router, prefix="/departments", tags=["部门管理"])
api_router.include_router(users.router, prefix="/users", tags=["账号管理"])
api_router.include_router(user_center.router, prefix="/user-center", tags=["用户中心"])
api_router.include_router(customers.router, prefix="/customers", tags=["客户管理"])

__all__ = ["api_router"]

