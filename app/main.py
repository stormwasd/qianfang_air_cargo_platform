"""
FastAPI应用主入口
"""
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.config import settings
from app.api import api_router
from app.core.middleware import setup_cors_middleware
from app.core.exceptions import BaseAPIException
from app.core.response import error_response


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
    )
    
    # 配置中间件
    setup_cors_middleware(app)
    
    # 注册异常处理器
    register_exception_handlers(app)
    
    # 注册API路由
    app.include_router(api_router)
    
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
            error_msg = errors[0].get("msg", error_msg)
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


# 创建应用实例
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

