"""
API路由统一注册
"""
from fastapi import APIRouter
from app.config import settings
from app.api import auth, users, departments, customers, config, user_center, waybills, bookings, settlements, rpa_tasks, notifications, waybill_stocks, robots, companies, agents, pickup_units, delivery_units, weather

# 创建API v1路由器
api_router = APIRouter(prefix=settings.API_V1_PREFIX)

# 注册所有子路由
api_router.include_router(auth.router, prefix="/auth", tags=["认证"])
api_router.include_router(config.router, prefix="/config", tags=["业务参数管理"])
api_router.include_router(departments.router, prefix="/departments", tags=["部门管理"])
api_router.include_router(users.router, prefix="/users", tags=["账号管理"])
api_router.include_router(user_center.router, prefix="/user-center", tags=["用户中心"])
api_router.include_router(customers.router, prefix="/customers", tags=["客户管理"])
api_router.include_router(companies.router, prefix="/companies", tags=["公司信息管理"])
api_router.include_router(agents.router, prefix="/agents", tags=["代理管理"])
api_router.include_router(pickup_units.router, prefix="/pickup-units", tags=["提货单位管理"])
api_router.include_router(delivery_units.router, prefix="/delivery-units", tags=["派送单位管理"])
api_router.include_router(waybills.router, prefix="/waybills", tags=["运单管理"])
api_router.include_router(bookings.router, prefix="/bookings", tags=["订舱管理"])
api_router.include_router(settlements.router, prefix="/settlements", tags=["结算单管理"])
api_router.include_router(rpa_tasks.router, prefix="/rpa-tasks", tags=["RPA任务队列"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["通知管理"])
api_router.include_router(waybill_stocks.router, prefix="/waybill-stocks", tags=["单号库管理"])
api_router.include_router(robots.router, prefix="/robots", tags=["机器人管理"])
api_router.include_router(weather.router, prefix="/weather", tags=["天气服务"])

__all__ = ["api_router"]

