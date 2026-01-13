"""
项目配置文件
使用Pydantic Settings进行配置管理，提供类型验证和更好的配置管理
"""
from typing import List, Dict
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
    
    # RPA API配置
    RPA_API_BASE_URL: str = "https://z-commander-api.ai-indeed.com"
    RPA_API_APP_KEY: str = "56505085de31411d95c7d55d7d77147c"
    RPA_API_APP_SECRET: str = "iZfoiSTRiBkTSzpiPTxCfcPuiOtXcC"
    RPA_API_COOKIE: str = "JSESSIONID=3251C9354C6364367DF927B56A1E3CCE"
    
    # RPA任务配置
    RPA_SHENZHEN_AIR_JOB_UUID: str = "e1b259766b97e5e115c21b2614158a5f"  # 深航新增运单任务jobUuid
    RPA_SHENZHEN_AIR_VOID_JOB_UUID: str = "a7c653b789a20bb955bf22163a9bd7c9"  # 深航作废运单任务jobUuid
    RPA_SHENZHEN_AIR_QUEUE_UUID: str = "8e53aa16fb8642489e899998283da28f"  # 深航获取运单号队列UUID
    RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID: str = "4971126222078ca6b2fa992432024d99"  # 南航订舱任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_QUEUE_UUID: str = "d5933f787b77482aa486da4fd3ffdcfd"  # 南航获取运单号队列UUID
    
    # RPA轮询配置
    RPA_POLL_INTERVAL: int = Field(default=5, ge=1, le=300, description="RPA状态轮询间隔（秒），默认5秒")
    RPA_POLL_MAX_COUNT: int = Field(default=60, ge=1, le=1000, description="RPA状态最大轮询次数，默认60次（即最多轮询5分钟）")
    
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

