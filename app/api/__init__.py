"""
API路由统一注册
"""
from fastapi import APIRouter
from app.config import settings
from app.api import auth, users, departments, customers, config, user_center, waybills, bookings, settlements, rpa_tasks, notifications, waybill_stocks, robots, companies, agents, pickup_units, delivery_units, weather, consignment_notes, departure_tracking, shenzhen_air_approval, china_southern_air_approval, financial_audit, common, reconciliation_airline

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
api_router.include_router(common.router, prefix="/common", tags=["公共模块"])
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
api_router.include_router(consignment_notes.router, prefix="/consignment-notes", tags=["托运书管理"])
api_router.include_router(departure_tracking.router, prefix="/departure-tracking", tags=["出港跟踪模块"])
api_router.include_router(shenzhen_air_approval.router, prefix="/shenzhen-air-approvals", tags=["深航订舱批复跟踪模块"])
api_router.include_router(china_southern_air_approval.router, prefix="/china-southern-air-approvals", tags=["南航订舱批复跟踪模块"])
api_router.include_router(financial_audit.router, prefix="/financial-audit", tags=["财务单据审核"])
api_router.include_router(reconciliation_airline.router, prefix="/reconciliation/airline", tags=["应付对账-航司对账"])

__all__ = ["api_router"]

