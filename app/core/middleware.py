"""
中间件配置
"""
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import settings


def setup_cors_middleware(app):
    """配置CORS中间件"""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


class ProcessTimeMiddleware(BaseHTTPMiddleware):
    """处理时间中间件（可选，用于性能监控）"""
    
    async def dispatch(self, request: Request, call_next):
        import time
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

