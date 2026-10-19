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


def _init_rpa_processes():
    """自动校验建表，并补齐系统内置的 RPA 流程配置。"""
    try:
        from app.database import engine, Base, SessionLocal
        from app.models.robot import TaskProcess
        from app.models.nanhang_token import NanHangToken
        from app.models.china_southern_air_booking_task import ChinaSouthernAirBookingTask
        import random
        from app.utils.helpers import get_china_now

        # 自动创建 SQLAlchemy 模型对应的缺失数据表
        Base.metadata.create_all(bind=engine)

        db = SessionLocal()
        try:
            # 1. 自动清洗数据库中已存在的 nanhang_token 历史记录（清除字面量 \\r\\n 及控制字符）
            from app.services.rpa_worker import RPAWorker
            tokens = db.query(NanHangToken).all()
            cleaned_count = 0
            for t in tokens:
                if t.token:
                    cleaned_val = RPAWorker._clean_single_token_str(t.token)
                    if cleaned_val and cleaned_val != t.token:
                        t.token = cleaned_val
                        t.updated_at = get_china_now()
                        cleaned_count += 1
            if cleaned_count > 0:
                db.commit()
                print(f"[Init] 自动清洗存量 nanhang_token 历史数据: {cleaned_count} 条")

            # 2. 校验补齐 task_processes 流程配置。已有记录由迁移 SQL 或管理接口维护，
            # 启动过程只补缺，避免意外覆盖线上调整。
            process_defaults = (
                {
                    "task_name": "CHINA_SOUTHERN_AIR_GET_TOKEN",
                    "chinese_name": "南航获取token",
                    "process_detail_uuid": "ccd69aab94b92dec70bd05dfd6f3aa21",
                    "version": "0.0.2",
                    "process_param": '{"system_url":"https://cargo.csair.com/tangb2gweb/order-management","queue_token_name":""}',
                },
                {
                    "task_name": "SHENZHEN_AIR_GET_HAR",
                    "chinese_name": "深航获取har",
                    "process_detail_uuid": "9d55ee2fbd0460f44c1dd1c47f5f7e32",
                    "version": "0.0.2",
                    "process_param": '{"system_url":"https://www.kinggo.com/main"}',
                },
            )
            added_processes = []
            for defaults in process_defaults:
                process = db.query(TaskProcess).filter(
                    TaskProcess.task_name == defaults["task_name"]
                ).first()
                if process:
                    continue
                now = get_china_now()
                db.add(TaskProcess(
                    id=random.randint(100000000000000000, 999999999999999999),
                    created_at=now,
                    updated_at=now,
                    **defaults,
                ))
                added_processes.append(defaults["task_name"])

            if added_processes:
                db.commit()
                print(f"[Init] 自动补齐 task_processes 流程配置: {', '.join(added_processes)}")
        except Exception as e:
            db.rollback()
            print(f"[Init] 校验 task_processes 失败: {e}")
        finally:
            db.close()
    except Exception as e:
        print(f"[Init] 初始化 RPA 流程模块异常: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    启动时启动RPA Worker，关闭时停止Worker
    """
    _init_rpa_processes()
    # Seed KingGo times before Shenzhen consumers start. Failures leave the
    # existing data/fallback available and are retried by the independent sync.
    from app.services.shenzhen_air_flight_info import shenzhen_air_flight_info_sync
    from app.utils.helpers import get_china_now
    await shenzhen_air_flight_info_sync.ensure_fresh(get_china_now().date())
    shenzhen_air_flight_info_sync.start()
    # 南航货物类型同步为后端直连接口任务，不依赖 RPA 队列是否启用。
    from app.services.csa_cargo_type_sync import csa_cargo_type_sync_scheduler
    csa_cargo_type_sync_scheduler.start()
    from app.services.csa_waybill_stock_scanner import csa_waybill_stock_scan_scheduler
    csa_waybill_stock_scan_scheduler.start()
    from app.services.direct_booking_worker import direct_booking_worker_manager
    direct_booking_worker_manager.start_workers()
    from app.services.shenzhen_air_direct_waybill_worker import shenzhen_air_direct_waybill_worker_manager
    shenzhen_air_direct_waybill_worker_manager.start_workers()
    # 过机装机直连模式同时负责扫描 Excel 并驱动计飞/集装器直连处理，
    # 不应依赖 RPA 队列开关；RPA 模式仍在下方 RPA 分支中启动。
    transit_loading_started = False
    if not settings.RPA_QUEUE_ENABLED and settings.SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE == "direct":
        from app.services.transit_loading_manager import transit_loading_manager
        transit_loading_manager.start()
        transit_loading_started = True
    approval_scheduler_started = False
    if not settings.RPA_QUEUE_ENABLED and settings.SHENZHEN_AIR_APPROVAL_EXECUTION_MODE == "direct":
        from app.services.shenzhen_air_approval_scheduler import shenzhen_air_approval_scheduler
        shenzhen_air_approval_scheduler.start()
        approval_scheduler_started = True
    if settings.RPA_QUEUE_ENABLED:
        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.start_workers()
        print(f"RPA任务队列已启用，启动了 {len(rpa_worker_manager.workers)} 个Worker")
        from app.services.keep_login_scheduler import rpa_keep_login_scheduler
        rpa_keep_login_scheduler.start()
        if not transit_loading_started:
            from app.services.transit_loading_manager import transit_loading_manager
            transit_loading_manager.start()
        if not approval_scheduler_started:
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
        from app.services.shenzhen_air_get_har_scheduler import shenzhen_air_get_har_scheduler
        shenzhen_air_get_har_scheduler.start()
        from app.services.departure_actual_time_sync import departure_actual_time_sync
        departure_actual_time_sync.start()
    else:
        print("RPA任务队列已禁用")

    
    yield

    shenzhen_air_flight_info_sync.stop()
    csa_cargo_type_sync_scheduler.stop()
    csa_waybill_stock_scan_scheduler.stop()
    from app.services.direct_booking_worker import direct_booking_worker_manager
    direct_booking_worker_manager.stop_workers()
    from app.services.shenzhen_air_direct_waybill_worker import shenzhen_air_direct_waybill_worker_manager
    shenzhen_air_direct_waybill_worker_manager.stop_workers()

    if settings.RPA_QUEUE_ENABLED:
        from app.services.rpa_worker import rpa_worker_manager
        rpa_worker_manager.stop_workers()
        print("RPA Worker已停止")
        from app.services.keep_login_scheduler import rpa_keep_login_scheduler
        rpa_keep_login_scheduler.stop()
        if settings.RPA_QUEUE_ENABLED or settings.SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE == "direct":
            from app.services.transit_loading_manager import transit_loading_manager
            transit_loading_manager.stop()
        if settings.RPA_QUEUE_ENABLED or settings.SHENZHEN_AIR_APPROVAL_EXECUTION_MODE == "direct":
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
        from app.services.shenzhen_air_get_har_scheduler import shenzhen_air_get_har_scheduler
        shenzhen_air_get_har_scheduler.stop()
        from app.services.departure_actual_time_sync import departure_actual_time_sync
        departure_actual_time_sync.stop()
    else:
        if settings.SHENZHEN_AIR_TRANSIT_LOADING_EXECUTION_MODE == "direct":
            from app.services.transit_loading_manager import transit_loading_manager
            transit_loading_manager.stop()
        if settings.SHENZHEN_AIR_APPROVAL_EXECUTION_MODE == "direct":
            from app.services.shenzhen_air_approval_scheduler import shenzhen_air_approval_scheduler
            shenzhen_air_approval_scheduler.stop()


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
                "data": exc.data,
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

