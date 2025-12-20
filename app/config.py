"""
项目配置文件
使用Pydantic Settings进行配置管理，提供类型验证和更好的配置管理
"""
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """应用配置"""
    
    # 项目信息
    PROJECT_NAME: str = "千方航空物流平台"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # 数据库配置
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "qianfang_air_cargo"
    
    # 数据库连接池配置
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=100, description="连接池大小")
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, description="连接池最大溢出数")
    DB_POOL_RECYCLE: int = Field(default=3600, ge=0, description="连接回收时间（秒）")
    
    # JWT配置
    SECRET_KEY: str = "your-secret-key-here-change-in-production"  # 生产环境需要修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30 * 24 * 60, ge=1, description="访问token过期时间（分钟）")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=90, ge=1, description="刷新token过期时间（天）")
    
    # 密码加密配置
    PASSWORD_SALT_ROUNDS: int = Field(default=12, ge=4, le=31, description="密码加密轮数")
    
    # 权限定义（权限代码 -> 权限名称）
    PERMISSIONS: Dict[str, str] = {
        "waybill": "运单管理",
        "booking": "订舱管理",
        "settlement": "结算单管理",
        "admin": "管理员"
    }
    
    # 权限代码列表（用于验证）
    PERMISSION_CODES: List[str] = list(PERMISSIONS.keys())
    
    # 权限名称列表（用于向后兼容）
    PERMISSION_NAMES: List[str] = list(PERMISSIONS.values())
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]
    
    # 应用配置
    DEBUG: bool = Field(default=False, description="调试模式")
    
    class Config:
        case_sensitive = True
        env_file = None  # 不使用环境变量文件，按用户要求
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"


settings = Settings()

