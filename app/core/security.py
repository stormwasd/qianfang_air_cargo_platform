"""
安全相关功能：密码加密、JWT token生成和验证
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from app.config import settings
from app.schemas.user import TokenData
from app.utils.helpers import CHINA_TIMEZONE

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
        
        password_bytes = plain_password.encode('utf-8')
        if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
            password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
        
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode('utf-8')
        else:
            hashed_bytes = hashed_password
        
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
    
    password_bytes = password.encode('utf-8')
    if len(password_bytes) > BCRYPT_MAX_PASSWORD_LENGTH:
        import warnings
        warnings.warn(f"密码长度超过{BCRYPT_MAX_PASSWORD_LENGTH}字节，将被截断")
        password_bytes = password_bytes[:BCRYPT_MAX_PASSWORD_LENGTH]
    
    salt = bcrypt.gensalt(rounds=settings.PASSWORD_SALT_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    
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
    now = datetime.now(CHINA_TIMEZONE)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({
        "exp": int(expire.timestamp()),  
        "iat": int(now.timestamp()),      
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
    now = datetime.now(CHINA_TIMEZONE)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode.update({
        "exp": int(expire.timestamp()),  
        "iat": int(now.timestamp()),      
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
        try:
            unverified_payload = jwt.decode(
                token,
                key="",  
                options={"verify_signature": False, "verify_exp": False}
            )
        except Exception as e:
            if settings.DEBUG:
                import logging
                logging.error(f"Token格式错误，无法解码: {str(e)}")
            return None
        
        token_type_in_payload = unverified_payload.get("type")
        if token_type_in_payload != token_type:
            if settings.DEBUG:
                import logging
                logging.warning(f"Token类型不匹配: 期望 {token_type}, 实际 {token_type_in_payload}")
            return None
        
        payload = jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": False,  
                "require_exp": True,
                "require_iat": False
            }
        )
        
        user_id = payload.get("sub")
        phone = payload.get("phone")
        token_version = payload.get("token_version", 0)  
        
        if user_id is None or phone is None:
            if settings.DEBUG:
                import logging
                logging.warning(f"Token缺少必要字段: user_id={user_id}, phone={phone}")
            return None
        
        try:
            user_id_int = int(user_id)
            phone_str = str(phone)
            token_version_int = int(token_version) if token_version is not None else 0
        except (ValueError, TypeError) as e:
            if settings.DEBUG:
                import logging
                logging.error(f"Token字段类型转换失败: {str(e)}")
            return None
        
        return TokenData(user_id=user_id_int, phone=phone_str, token_version=token_version_int)
    except JWTError as e:
        if settings.DEBUG:
            import logging
            logging.error(f"JWT验证失败: {type(e).__name__}: {str(e)}")
        return None
    except Exception as e:
        if settings.DEBUG:
            import logging
            logging.error(f"Token验证异常: {type(e).__name__}: {str(e)}")
        return None

