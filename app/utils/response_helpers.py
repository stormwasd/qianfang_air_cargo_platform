"""
响应辅助函数
用于将Pydantic模型和数据库模型转换为字典
"""
from typing import Any, List, Dict
from datetime import datetime
from decimal import Decimal


def model_to_dict(model: Any) -> Dict[str, Any]:
    """
    将Pydantic模型或SQLAlchemy模型转换为字典
    
    Args:
        model: Pydantic模型或SQLAlchemy模型实例
    
    Returns:
        Dict: 字典格式的数据
    """
    if hasattr(model, 'model_dump'):
        # Pydantic v2
        return model.model_dump()
    elif hasattr(model, 'dict'):
        # Pydantic v1
        return model.dict()
    elif hasattr(model, '__dict__'):
        # SQLAlchemy模型或其他对象
        result = {}
        for key, value in model.__dict__.items():
            if not key.startswith('_'):
                result[key] = serialize_value(value)
        return result
    else:
        return model


def serialize_value(value: Any) -> Any:
    """
    序列化值，处理datetime、Decimal等特殊类型
    
    Args:
        value: 需要序列化的值
    
    Returns:
        序列化后的值
    """
    if isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, list):
        return [serialize_value(item) for item in value]
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif hasattr(value, '__dict__'):
        return model_to_dict(value)
    else:
        return value


def convert_model_list(models: List[Any]) -> List[Dict[str, Any]]:
    """
    将模型列表转换为字典列表
    
    Args:
        models: 模型列表
    
    Returns:
        字典列表
    """
    return [model_to_dict(model) for model in models]

