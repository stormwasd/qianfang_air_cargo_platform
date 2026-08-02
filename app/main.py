"""
FastAPI应用主入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.api import api_router
from app.core.middleware import setup_cors_middleware
from app.core.exceptions import BaseAPIException
from app.core.response import error_response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时启动RPA Worker，关闭时停止Worker
    """
    if settings.RPA_QUEUE_ENABLED:
        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.start_workers()
        print(f"RPA任务队列已启用，启动了 {len(rpa_worker_manager.workers)} 个Worker")
        from app.services.keep_login_scheduler import rpa_keep_login_scheduler
        rpa_keep_login_scheduler.start()
        from app.services.transit_loading_manager import transit_loading_manager
        transit_loading_manager.start()
        from app.services.shenzhen_air_approval_scheduler import shenzhen_air_approval_scheduler
        shenzhen_air_approval_scheduler.start()
        from app.services.china_southern_air_approval_scheduler import china_southern_air_approval_scheduler
        china_southern_air_approval_scheduler.start()
        from app.services.shenzhen_air_approval_alert import shenzhen_air_approval_alert
        shenzhen_air_approval_alert.start()
        from app.services.shenzhen_air_departure_alert import shenzhen_air_departure_alert_manager
        shenzhen_air_departure_alert_manager.start()
        from app.services.csa_departure_alert import csa_departure_alert_manager
        csa_departure_alert_manager.start()
        from app.services.shenzhen_air_loading_alert import shenzhen_air_loading_alert_manager
        shenzhen_air_loading_alert_manager.start()
        from app.services.csa_loading_alert import csa_loading_alert_manager
        csa_loading_alert_manager.start()
        from app.services.shenzhen_air_departure_status_alert import shenzhen_air_departure_status_alert
        shenzhen_air_departure_status_alert.start()
        from app.services.csa_departure_status_alert import csa_departure_status_alert
        csa_departure_status_alert.start()
        from app.services.csa_get_token_scheduler import csa_get_token_scheduler
        csa_get_token_scheduler.start()
    else:
        print("RPA任务队列已禁用")
    
    yield
    
    if settings.RPA_QUEUE_ENABLED:
        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.stop_workers()
        print("RPA Worker已停止")
        from app.services.keep_login_scheduler import rpa_keep_login_scheduler
        rpa_keep_login_scheduler.stop()
        from app.services.transit_loading_manager import transit_loading_manager
        transit_loading_manager.stop()
        from app.services.shenzhen_air_approval_scheduler import shenzhen_air_approval_scheduler
        shenzhen_air_approval_scheduler.stop()
        from app.services.china_southern_air_approval_scheduler import china_southern_air_approval_scheduler
        china_southern_air_approval_scheduler.stop()
        from app.services.shenzhen_air_approval_alert import shenzhen_air_approval_alert
        shenzhen_air_approval_alert.stop()
        from app.services.shenzhen_air_departure_alert import shenzhen_air_departure_alert_manager
        shenzhen_air_departure_alert_manager.stop()
        from app.services.csa_departure_alert import csa_departure_alert_manager
        csa_departure_alert_manager.stop()
        from app.services.shenzhen_air_loading_alert import shenzhen_air_loading_alert_manager
        shenzhen_air_loading_alert_manager.stop()
        from app.services.csa_loading_alert import csa_loading_alert_manager
        csa_loading_alert_manager.stop()
        from app.services.shenzhen_air_departure_status_alert import shenzhen_air_departure_status_alert
        shenzhen_air_departure_status_alert.stop()
        from app.services.csa_departure_status_alert import csa_departure_status_alert
        csa_departure_status_alert.stop()
        from app.services.csa_get_token_scheduler import csa_get_token_scheduler
        csa_get_token_scheduler.stop()


def create_application() -> FastAPI:
    """
    创建FastAPI应用实例
    使用工厂模式，便于测试和配置管理
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="千方航空物流平台后端API",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,  
    )
    
    setup_cors_middleware(app)
    
    register_exception_handlers(app)
    
    app.include_router(api_router)
    
    import os
    os.makedirs("static/uploads", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    
    return app


def register_exception_handlers(app: FastAPI):
    """注册异常处理器，统一响应格式"""
    
    @app.exception_handler(BaseAPIException)
    async def base_api_exception_handler(request: Request, exc: BaseAPIException):
        """处理自定义API异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "data": None,
                "msg": exc.detail
            }
        )
    
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理HTTP异常"""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "data": None,
                "msg": exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证异常"""
        errors = exc.errors()
        error_msg = "请求参数验证失败"
        if errors:
            error_loc = " -> ".join([str(x) for x in errors[0].get("loc", [])])
            error_msg_detail = errors[0].get("msg", error_msg)
            error_msg = f"参数验证失败 ({error_loc}): {error_msg_detail}"
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "code": status.HTTP_422_UNPROCESSABLE_ENTITY,
                "data": None,
                "msg": error_msg
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理其他未捕获的异常"""
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
                "data": None,
                "msg": "服务器内部错误" if not settings.DEBUG else str(exc)
            }
        )


app = create_application()


@app.get("/", summary="根路径")
async def root():
    """根路径"""
    from app.core.response import success_response
    return success_response(
        data={
            "message": "欢迎使用千方航空物流平台API",
            "version": settings.VERSION,
            "docs": "/docs"
        },
        msg="success"
    )


@app.get("/health", summary="健康检查")
async def health_check():
    """健康检查接口"""
    from app.core.response import success_response
    return success_response(data={"status": "ok"}, msg="服务正常")

