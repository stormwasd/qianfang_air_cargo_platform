"""
统一异常处理
所有异常都会转换为统一响应格式
"""
from fastapi import HTTPException, status
from typing import Any, Dict, Optional


class BaseAPIException(HTTPException):
    """基础API异常类"""
    
    def __init__(
        self,
        status_code: int,
        detail: Any = None,
        headers: Optional[Dict[str, Any]] = None,
    ):
        # 确保detail是字符串
        if detail is None:
            detail = "请求处理失败"
        elif not isinstance(detail, str):
            detail = str(detail)
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class NotFoundException(BaseAPIException):
    """资源未找到异常"""
    
    def __init__(self, detail: str = "资源不存在"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class BadRequestException(BaseAPIException):
    """请求参数错误异常"""
    
    def __init__(self, detail: str = "请求参数错误"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class UnauthorizedException(BaseAPIException):
    """未授权异常"""
    
    def __init__(self, detail: str = "未授权访问"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class ForbiddenException(BaseAPIException):
    """禁止访问异常"""
    
    def __init__(self, detail: str = "无权限访问"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class ConflictException(BaseAPIException):
    """资源冲突异常"""
    
    def __init__(self, detail: str = "资源已存在"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )

