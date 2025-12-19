"""
统一响应格式
所有接口返回格式：{code: 0, data: {}, msg: "xxx"}
code: 0表示成功，其他使用HTTP状态码
"""
from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')


class ResponseModel(BaseModel, Generic[T]):
    """统一响应格式"""
    code: int = Field(0, description="状态码，0表示成功，其他使用HTTP状态码")
    data: Optional[T] = Field(None, description="返回数据")
    msg: str = Field("success", description="消息描述")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": 0,
                "data": {},
                "msg": "success"
            }
        }


def success_response(data: Any = None, msg: str = "success") -> ResponseModel:
    """
    成功响应
    
    Args:
        data: 返回的数据
        msg: 消息描述
    
    Returns:
        ResponseModel: 统一响应格式
    """
    return ResponseModel(code=0, data=data, msg=msg)


def error_response(code: int, msg: str, data: Any = None) -> ResponseModel:
    """
    错误响应
    
    Args:
        code: HTTP状态码
        msg: 错误消息
        data: 可选的错误数据
    
    Returns:
        ResponseModel: 统一响应格式
    """
    return ResponseModel(code=code, data=data, msg=msg)

