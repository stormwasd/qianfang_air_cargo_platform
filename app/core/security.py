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
    """创建访问token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> str:
    """创建刷新token"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """验证token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != token_type:
            return None
        user_id: int = payload.get("sub")
        phone: str = payload.get("phone")
        if user_id is None or phone is None:
            return None
        return TokenData(user_id=user_id, phone=phone)
    except JWTError:
        return None

