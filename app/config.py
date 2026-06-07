"""
项目配置文件
使用Pydantic Settings进行配置管理，提供类型验证和更好的配置管理
"""
from typing import List, Dict, Optional
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
        "customer": "客户管理",
        "bill": "单号管理",
        "robot": "机器人管理",
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
    RPA_SHENZHEN_AIR_QUEUE_UUID: str = "8e53aa16fb8642489e899998283da28f"  # 深航获取运单号队列UUID（历史遗留，已不使用）
    # 深航开单队列名称（固定队列名称，每次执行开单时都会创建新队列实例）
    RPA_SHENZHEN_AIR_QUEUE_WAYBILL_NUMBER: str = "shenzhen_air_kaidan_queue_waybill_number"  # 深航开单运单号队列名称
    RPA_SHENZHEN_AIR_QUEUE_FREIGHT_RATE: str = "shenzhen_air_kaidan_queue_freight_rate"  # 深航开单费率队列名称
    RPA_SHENZHEN_AIR_QUEUE_FREIGHT: str = "shenzhen_air_kaidan_queue_freight"  # 深航开单运费队列名称
    RPA_SHENZHEN_AIR_QUEUE_DELIVERY_FEE: str = "shenzhen_air_kaidan_queue_delivery_fee"  # 深航开单派送费队列名称
    RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID: str = "4971126222078ca6b2fa992432024d99"  # 南航订舱任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID: str = "196dde6fbcfd15e2e0641caf8720c7d7"  # 南航退舱任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID: str = "167b4cbefd18d7311d55844cdb36c398"  # 南航直接开单任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_VOID_JOB_UUID: str = "6597981f58eae4a6dd0b025699215c44"  # 南航作废运单任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_WAYBILL_JOB_UUID: str = "cc2bda248c24dbf57fa6cd2534ce5054"  # 南航新增运单任务jobUuid
    RPA_CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_JOB_UUID: str = "1d8f4e2518e0f2c858853c189873e91d"  # 南航修改数据后开单任务jobUuid（从订舱回显数据后修改再开单）
    RPA_CHINA_SOUTHERN_AIR_QUEUE_UUID: str = "d5933f787b77482aa486da4fd3ffdcfd"  # 南航获取运单号队列UUID（历史遗留，已不使用）
    
    # ========== 打单RPA配置 ==========
    # 通用文件打印jobUuid（深航和南航共用，用于打印制单后生成的文档文件）
    RPA_FILE_PRINT_JOB_UUID: str = "8aef03178d04720fdbcc7ea66c7cb00d"
    # 深航货运主单打印jobUuid
    RPA_SHENZHEN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID: str = "1fa863b38e0e0741239b7bbf51d196ac"
    # 南航货运主单打印jobUuid
    RPA_CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID: str = "9b4f2e79cf1107f57f6ea7130552ffe5"
    # 南航货运安检申报单打印jobUuid
    RPA_CHINA_SOUTHERN_AIR_SECURITY_PRINT_JOB_UUID: str = "afd7fa28e46cd61cf26707c98176556e"
    # 南航标签单打印jobUuid
    RPA_CHINA_SOUTHERN_AIR_LABEL_PRINT_JOB_UUID: str = "1efafa308b1c7a789117747b56b6e6a2"
    # 打印文件在RPA机器人上的根目录（固定路径）
    RPA_PRINT_FILE_ROOT_PATH: str = "D:\\generated_files_of_qianfang_air_cargo_platform"
    # 南航统一队列名称（所有南航功能共用，每次执行时都会创建新队列实例）
    # - 南航订舱：使用运单号队列（1个）
    # - 南航直接开单：使用费率、运费、燃油费、延伸服务费队列（4个）
    # - 南航新增运单：使用全部5个队列
    RPA_CHINA_SOUTHERN_AIR_QUEUE_WAYBILL_NUMBER: str = "nanhang_air_dingcang_kaidan_queue_waybill_number"  # 南航运单号队列名称
    RPA_CHINA_SOUTHERN_AIR_QUEUE_RATE: str = "nanhang_air_dingcang_kaidan_queue_rate"  # 南航费率队列名称
    RPA_CHINA_SOUTHERN_AIR_QUEUE_FREIGHT: str = "nanhang_air_dingcang_kaidan_queue_freight"  # 南航运费队列名称
    RPA_CHINA_SOUTHERN_AIR_QUEUE_FUEL_COSTS: str = "nanhang_air_dingcang_kaidan_queue_fuel_costs"  # 南航燃油费队列名称
    RPA_CHINA_SOUTHERN_AIR_QUEUE_EXTENDED_SERVICE_FEE: str = "nanhang_air_dingcang_kaidan_queue_extended_service_fee"  # 南航延伸服务费队列名称

    # ========== 保持登录RPA配置 ==========
    RPA_KEEP_LOGIN_ENABLED: bool = Field(
        default=True,
        description="是否启用保持登录定时入队（会创建RPATask，由Worker消费）"
    )

    # jobUuid（产品下发的jobUuid）
    RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_JOB_UUID: str = "946f2c29111a8d6e023ff0a75afb0029"
    RPA_SHENZHEN_AIR_KEEP_LOGIN_JOB_UUID: str = "6d24e496bf1b39af5b77740960d51ca4"
    RPA_TANGYI_KEEP_LOGIN_JOB_UUID: str = "137a3c17c14505dfaac006eab08f16e6"

    # 定时入队间隔（秒）：不填/填None则不入队
    RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_INTERVAL_SECONDS: Optional[int] = Field(
        default=6600, ge=1, le=86400,
        description="南航保持登录执行间隔（秒），默认不启用"
    )
    RPA_SHENZHEN_AIR_KEEP_LOGIN_INTERVAL_SECONDS: Optional[int] = Field(
        default=6600, ge=1, le=86400,
        description="深航保持登录执行间隔（秒），默认不启用"
    )
    RPA_TANGYI_KEEP_LOGIN_INTERVAL_SECONDS: Optional[int] = Field(
        default=1200, ge=1, le=86400,
        description="唐翼保持登录执行间隔（秒），默认不启用"
    )
    
    # ========== 定时获取数据类RPA配置 ==========
    RPA_SHENZHEN_AIR_TRANSIT_LOADING_INTERVAL_SECONDS: Optional[int] = Field(
        default=3600, ge=1, le=86400,
        description="深航订舱-过机-装机数据获取任务执行间隔（秒），默认3600秒"
    )
    # 下载的表格存储目录（使用绝对路径，或者基于项目根目录的相对路径）
    import os
    RPA_GENERATED_FILES_DIR: str = Field(
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_files"),
        description="后台扫描的RPA下载文件存放目录"
    )
    
    # RPA轮询配置
    RPA_POLL_INTERVAL: int = Field(default=5, ge=1, le=300, description="RPA状态轮询间隔（秒），默认5秒")
    RPA_POLL_MAX_COUNT: int = Field(default=60, ge=1, le=1000, description="RPA状态最大轮询次数，默认60次（即最多轮询5分钟）")
    
    # RPA任务队列配置
    RPA_QUEUE_ENABLED: bool = Field(default=True, description="是否启用RPA任务队列模式")
    RPA_QUEUE_POLL_INTERVAL: int = Field(default=2, ge=1, le=60, description="Worker轮询队列间隔（秒），默认2秒")
    RPA_QUEUE_DEFAULT_PRIORITY: int = Field(default=1, ge=1, le=100, description="默认任务优先级，默认1")
    RPA_QUEUE_WORKER_COUNT: int = Field(default=1, ge=1, le=10, description="Worker数量（对应RPA机器人数量），默认1")
    RPA_QUEUE_TASK_TIMEOUT: int = Field(default=30, ge=10, le=300, description="RPA接口调用超时时间（秒），默认30秒，超时则任务失败")
    RPA_QUEUE_CLEANUP_DAYS: int = Field(default=7, ge=1, le=365, description="已完成任务保留天数，默认7天")
    
    
    # 航司单号前缀映射（航司名称 -> 单号前缀）
    AIRLINE_NUMBER_PREFIX: Dict[str, str] = {
        "china_southern_air": "784-",
    }
    
    # 应用配置
    DEBUG: bool = Field(default=False, description="调试模式")
    
    class Config:
        case_sensitive = True
        env_file = ".env"  # 支持从 .env 文件加载配置（Docker 部署需要，本地无 .env 文件时自动忽略）
        env_file_encoding = "utf-8"
        extra = "ignore"  # 忽略 .env 中未在 Settings 中定义的字段，避免报错
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"


settings = Settings()

