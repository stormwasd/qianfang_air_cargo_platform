"""
项目配置文件
使用Pydantic Settings进行配置管理，提供类型验证和更好的配置管理
"""
from typing import List, Dict, Optional
from pydantic_settings import BaseSettings
from pydantic import Field
import os


class Settings(BaseSettings):
    """应用配置"""
    
    PROJECT_NAME: str = "千方航空物流平台"
    VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"
    
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "qianfang_air_cargo"
    
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=100, description="连接池大小")
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, description="连接池最大溢出数")
    DB_POOL_RECYCLE: int = Field(default=3600, ge=0, description="连接回收时间（秒）")
    
    SECRET_KEY: str = "your-secret-key-here-change-in-production"  
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30 * 24 * 60, ge=1, description="访问token过期时间（分钟）")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=90, ge=1, description="刷新token过期时间（天）")
    
    PASSWORD_SALT_ROUNDS: int = Field(default=12, ge=4, le=31, description="密码加密轮数")
    
    PERMISSIONS: Dict[str, str] = {
        "waybill": "运单管理",
        "booking": "订舱管理",
        "settlement": "结算单管理",
        "customer": "客户管理",
        "bill": "单号管理",
        "robot": "机器人管理",
        "admin": "管理员"
    }
    
    PERMISSION_CODES: List[str] = list(PERMISSIONS.keys())
    
    PERMISSION_NAMES: List[str] = list(PERMISSIONS.values())
    
    CORS_ORIGINS: List[str] = ["*"]
    
    RPA_API_BASE_URL: str = "https://z-commander-api.ai-indeed.com"
    RPA_API_APP_KEY: str = "56505085de31411d95c7d55d7d77147c"
    RPA_API_APP_SECRET: str = "iZfoiSTRiBkTSzpiPTxCfcPuiOtXcC"
    RPA_API_COOKIE: str = "JSESSIONID=3251C9354C6364367DF927B56A1E3CCE"
    
    RPA_SHENZHEN_AIR_JOB_UUID: str = "e1b259766b97e5e115c21b2614158a5f"  
    RPA_SHENZHEN_AIR_VOID_JOB_UUID: str = "a7c653b789a20bb955bf22163a9bd7c9"  
    RPA_SHENZHEN_AIR_QUEUE_UUID: str = "8e53aa16fb8642489e899998283da28f"  
    RPA_SHENZHEN_AIR_QUEUE_WAYBILL_NUMBER: str = "shenzhen_air_kaidan_queue_waybill_number"  
    RPA_SHENZHEN_AIR_QUEUE_FREIGHT_RATE: str = "shenzhen_air_kaidan_queue_freight_rate"  
    RPA_SHENZHEN_AIR_QUEUE_FREIGHT: str = "shenzhen_air_kaidan_queue_freight"  
    RPA_SHENZHEN_AIR_QUEUE_DELIVERY_FEE: str = "shenzhen_air_kaidan_queue_delivery_fee"  
    RPA_CHINA_SOUTHERN_AIR_BOOKING_JOB_UUID: str = "4971126222078ca6b2fa992432024d99"  
    RPA_CHINA_SOUTHERN_AIR_CANCEL_JOB_UUID: str = "196dde6fbcfd15e2e0641caf8720c7d7"  
    RPA_CHINA_SOUTHERN_AIR_DIRECT_INVOICE_JOB_UUID: str = "167b4cbefd18d7311d55844cdb36c398"  
    RPA_CHINA_SOUTHERN_AIR_VOID_JOB_UUID: str = "6597981f58eae4a6dd0b025699215c44"  
    RPA_CHINA_SOUTHERN_AIR_WAYBILL_JOB_UUID: str = "cc2bda248c24dbf57fa6cd2534ce5054"  
    RPA_CHINA_SOUTHERN_AIR_INVOICE_WITH_DATA_JOB_UUID: str = "1d8f4e2518e0f2c858853c189873e91d"  
    RPA_CHINA_SOUTHERN_AIR_QUEUE_UUID: str = "d5933f787b77482aa486da4fd3ffdcfd"  
    
    RPA_FILE_PRINT_JOB_UUID: str = "8aef03178d04720fdbcc7ea66c7cb00d"
    RPA_SHENZHEN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID: str = "1fa863b38e0e0741239b7bbf51d196ac"
    RPA_CHINA_SOUTHERN_AIR_MAIN_WAYBILL_PRINT_JOB_UUID: str = "9b4f2e79cf1107f57f6ea7130552ffe5"
    RPA_CHINA_SOUTHERN_AIR_SECURITY_PRINT_JOB_UUID: str = "afd7fa28e46cd61cf26707c98176556e"
    RPA_CHINA_SOUTHERN_AIR_LABEL_PRINT_JOB_UUID: str = "1efafa308b1c7a789117747b56b6e6a2"
    RPA_PRINT_FILE_ROOT_PATH: str = "D:\\generated_files_of_qianfang_air_cargo_platform"
    RPA_CHINA_SOUTHERN_AIR_QUEUE_WAYBILL_NUMBER: str = "nanhang_air_dingcang_kaidan_queue_waybill_number"  
    RPA_CHINA_SOUTHERN_AIR_QUEUE_RATE: str = "nanhang_air_dingcang_kaidan_queue_rate"  
    RPA_CHINA_SOUTHERN_AIR_QUEUE_FREIGHT: str = "nanhang_air_dingcang_kaidan_queue_freight"  
    RPA_CHINA_SOUTHERN_AIR_QUEUE_FUEL_COSTS: str = "nanhang_air_dingcang_kaidan_queue_fuel_costs"  
    RPA_CHINA_SOUTHERN_AIR_QUEUE_EXTENDED_SERVICE_FEE: str = "nanhang_air_dingcang_kaidan_queue_extended_service_fee"  

    RPA_KEEP_LOGIN_ENABLED: bool = Field(
        default=True,
        description="是否启用保持登录定时入队（会创建RPATask，由Worker消费）"
    )

    RPA_CHINA_SOUTHERN_AIR_KEEP_LOGIN_JOB_UUID: str = "946f2c29111a8d6e023ff0a75afb0029"
    RPA_SHENZHEN_AIR_KEEP_LOGIN_JOB_UUID: str = "6d24e496bf1b39af5b77740960d51ca4"
    RPA_TANGYI_KEEP_LOGIN_JOB_UUID: str = "137a3c17c14505dfaac006eab08f16e6"

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
    
    RPA_SHENZHEN_AIR_TRANSIT_LOADING_INTERVAL_SECONDS: Optional[int] = Field(
        default=900, ge=1, le=86400,
        description="深航订舱-过机-装机数据获取任务执行间隔（秒），默认3600秒"
    )
    RPA_SHENZHEN_AIR_APPROVAL_INTERVAL_SECONDS: int = Field(
        default=900, ge=1, le=86400,
        description="深航订舱-批复数据获取任务定时执行间隔（秒），默认900秒（15分钟）"
    )
    RPA_CHINA_SOUTHERN_AIR_APPROVAL_INTERVAL_SECONDS: int = Field(
        default=900, ge=1, le=86400,
        description="南航订舱批复数据定时获取执行间隔（秒），默认900秒（15分钟）"
    )
    RPA_CHINA_SOUTHERN_AIR_DEPARTURE_TRACKING_INTERVAL_SECONDS: int = Field(
        default=900, ge=1, le=86400,
        description="南航出港跟踪数据（本站货物+货拉信息）定时获取执行间隔（秒），默认900秒"
    )
    RPA_GENERATED_FILES_DIR: str = Field(
        default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_files"),
        description="后台扫描的RPA下载文件存放目录"
    )
    
    RPA_POLL_INTERVAL: int = Field(default=5, ge=1, le=300, description="RPA状态轮询间隔（秒），默认5秒")
    RPA_POLL_MAX_COUNT: int = Field(default=60, ge=1, le=1000, description="RPA状态最大轮询次数，默认60次（即最多轮询5分钟）")
    
    RPA_QUEUE_ENABLED: bool = Field(default=True, description="是否启用RPA任务队列模式")
    RPA_QUEUE_POLL_INTERVAL: int = Field(default=2, ge=1, le=60, description="Worker轮询队列间隔（秒），默认2秒")
    RPA_QUEUE_DEFAULT_PRIORITY: int = Field(default=1, ge=1, le=100, description="默认任务优先级，默认1")
    RPA_QUEUE_WORKER_COUNT: int = Field(default=1, ge=1, le=10, description="Worker数量（对应RPA机器人数量），默认1")
    RPA_QUEUE_TASK_TIMEOUT: int = Field(default=30, ge=10, le=300, description="RPA接口调用超时时间（秒），默认30秒，超时则任务失败")
    RPA_QUEUE_CLEANUP_DAYS: int = Field(default=7, ge=1, le=365, description="已完成任务保留天数，默认7天")
    
    WECHAT_WEBHOOK_URL: str = Field(
        default="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=05b6c4d8-5058-4706-8a96-27724683e46e",
        description="企业微信群机器人Webhook地址"
    )
    ALERT_SHENZHEN_AIR_APPROVAL_INTERVAL_SECONDS: int = Field(
        default=0, ge=0, le=86400,
        description="深航订舱批复预警-按间隔触发（秒），默认600秒（10分钟），设0则禁用间隔触发"
    )
    ALERT_SHENZHEN_AIR_APPROVAL_FIXED_TIMES: str = Field(
        default="18:00",
        description="深航订舱批复预警-按时间点触发（HH:MM格式，多个用逗号分隔，如'09:00,14:00,18:00'），为空则禁用定时触发"
    )
    ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_INTERVAL_SECONDS: int = Field(
        default=600, ge=60, le=86400,
        description="深航出港状态通知-同步任务执行间隔（秒），默认600秒（10分钟），负责定时监控和推送"
    )
    ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_FIXED_TIMES: str = Field(
        default="",
        description="深航出港状态通知-按时间点触发（HH:MM格式，多个用逗号分隔），为空则只依赖间隔触发"
    )
    ALERT_SHENZHEN_AIR_DEPARTURE_SYNC_INTERVAL_SECONDS: int = Field(
        default=300, ge=60, le=86400,
        description="深航出港跟踪预警-同步任务执行间隔（秒），默认300秒（5分钟），负责发现新单及获取计飞时间"
    )
    ALERT_SHENZHEN_AIR_DEPARTURE_EXEC_INTERVAL_SECONDS: int = Field(
        default=60, ge=10, le=3600,
        description="深航出港跟踪预警-到点预警执行间隔（秒），默认60秒（1分钟），负责准点触发预警消息"
    )
    ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_SYNC_INTERVAL_SECONDS: int = Field(
        default=300, ge=60, le=86400,
        description="南航出港跟踪预警-同步任务执行间隔（秒），默认300秒（5分钟），负责发现新单及获取计飞时间"
    )
    ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_INTERVAL_SECONDS: int = Field(
        default=600, ge=60, le=86400,
        description="南航出港状态通知-同步任务执行间隔（秒），默认600秒（10分钟），负责定时监控和推送"
    )
    ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_FIXED_TIMES: str = Field(
        default="",
        description="南航出港状态通知-按时间点触发（HH:MM格式，多个用逗号分隔），为空则只依赖间隔触发"
    )
    ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_EXEC_INTERVAL_SECONDS: int = Field(
        default=60, ge=10, le=3600,
        description="南航出港跟踪预警-到点预警执行间隔（秒），默认60秒（1分钟），负责准点触发预警消息"
    )
    ALERT_SHENZHEN_AIR_LOADING_SYNC_INTERVAL_SECONDS: int = Field(
        default=300, ge=60, le=86400,
        description="深航装机状态预警-同步任务执行间隔（秒），默认300秒（5分钟），负责发现新单及获取计飞时间"
    )
    ALERT_SHENZHEN_AIR_LOADING_EXEC_INTERVAL_SECONDS: int = Field(
        default=60, ge=10, le=3600,
        description="深航装机状态预警-到点预警执行间隔（秒），默认60秒（1分钟），负责准点触发预警消息"
    )
    ALERT_CSA_LOADING_SYNC_INTERVAL_SECONDS: int = Field(
        default=300, ge=60, le=86400,
        description="南航装机状态预警-同步任务执行间隔（秒），默认300秒（5分钟），负责发现新单及获取计飞时间"
    )
    ALERT_CSA_LOADING_EXEC_INTERVAL_SECONDS: int = Field(
        default=60, ge=10, le=3600,
        description="南航装机状态预警-到点预警执行间隔（秒），默认60秒（1分钟），负责准点触发预警消息"
    )
    
    AIRLINE_NUMBER_PREFIX: Dict[str, str] = {
        "china_southern_air": "784-",
    }
    
    DEBUG: bool = Field(default=False, description="调试模式")
    
    class Config:
        case_sensitive = True
        env_file = ".env"  
        env_file_encoding = "utf-8"
        extra = "ignore"  
    
    @property
    def DATABASE_URL(self) -> str:
        """构建数据库连接URL"""
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}?charset=utf8mb4"


settings = Settings()

