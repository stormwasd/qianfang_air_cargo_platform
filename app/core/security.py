"""
安全相关功能：密码加密、JWT token生成和验证
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.config import settings
from app.schemas.user import TokenData

# bcrypt 密码最大长度（字节）
BCRYPT_MAX_PASSWORD_LENGTH = 72


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码
    
    Args:
        plain_password: 明文密码
        hashed_password: 哈希密码（字符串格式）
    
    Returns:
        bool: 验证结果
    """
    try:
        if not plain_password or not hashed_password:
            return False
        
        # 处理密码长度限制
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
            password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
        
        # 将哈希密码转换为bytes（如果已经是bytes则直接使用）
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode('utf-8')
        else:
            hashed_bytes = hashed_password
        
        # 验证密码
        return bcrypt.checkpw(password_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    生成密码哈希
    
    Args:
        password: 明文密码
    
    Returns:
        str: 哈希后的密码
    
    Raises:
        ValueError: 密码为空或过长
    """
    if not password:
        raise ValueError("密码不能为空")
    
    # 处理密码长度限制
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
        # 如果密码超过72字节，截断并记录警告
        import warnings
        warnings.warn(f"密码长度超过{BCRYPT_MAX_PASSWORD_LENGTH}字节，将被截断")
        password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
    
    # 生成盐并哈希密码
    salt = bcrypt.gensalt(rounds=settings.PASSWORD_SALT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
    # 返回字符串格式的哈希值
    return hashed.decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问token
    
    Args:
        data: 要编码的数据
        expires_delta: 可选的过期时间增量
    
    Returns:
        str: 编码后的JWT token
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # 将datetime转换为Unix时间戳（整数）
    # 确保exp和iat都是整数时间戳，避免python-jose的兼容性问题
    to_encode.update({
        "exp": int(expire.timestamp()),  # Unix时间戳（整数）
        "iat": int(now.timestamp()),      # 签发时间（整数）
        "type": "access"
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """
    创建刷新token
    
    Args:
        data: 要编码的数据
    
    Returns:
        str: 编码后的JWT refresh token
    """
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    # 将datetime转换为Unix时间戳（整数）
    to_encode.update({
        "exp": int(expire.timestamp()),  # Unix时间戳（整数）
        "iat": int(now.timestamp()),      # 签发时间（整数）
        "type": "refresh"
    })
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    验证token
    
    Args:
        token: JWT token字符串
        token_type: token类型（"access" 或 "refresh"）
    
    Returns:
        Optional[TokenData]: 如果验证成功返回TokenData，否则返回None
    """
    if not token or not isinstance(token, str):
        return None
    
    try:
        # jwt.decode默认会验证签名和过期时间
        # 如果token过期或签名无效，会抛出JWTError异常
        # 注意：options参数可以控制验证行为
        # verify_exp=True: 验证过期时间
        # verify_signature=True: 验证签名（默认开启）
        # leeway: 允许的时间误差（秒），用于处理时钟偏差
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": False,  # 不验证iat，因为可能存在时钟偏差
                "require_exp": True,
                "require_iat": False
            }
        )
        
        # 检查token类型
        token_type_in_payload = payload.get("type")
        if token_type_in_payload != token_type:
            # token类型不匹配（例如：用access_token调用refresh接口）
            return None
        
        # 提取用户信息
        user_id = payload.get("sub")
        phone = payload.get("phone")
        
        if user_id is None or phone is None:
            # 缺少必要的用户信息
            return None
        
        # 确保类型正确
        try:
            user_id_int = int(user_id)
            phone_str = str(phone)
        except (ValueError, TypeError):
            # 类型转换失败
            return None
        
        return TokenData(user_id=user_id_int, phone=phone_str)
    except JWTError as e:
        # JWT验证失败（过期、签名错误、格式错误等）
        # 在调试模式下可以记录错误信息
        if settings.DEBUG:
            import logging
            logging.debug(f"JWT验证失败: {type(e).__name__}: {str(e)}")
        return None
    except Exception as e:
        # 其他异常（如类型转换错误等）
        if settings.DEBUG:
            import logging
            logging.debug(f"Token验证异常: {type(e).__name__}: {str(e)}")
        return None

