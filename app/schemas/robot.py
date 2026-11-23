"""
机器人管理相关的Pydantic schemas
"""
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, List, Dict, Any


class ShenzhenAirAccount(BaseModel):
    """深圳航空物流系统账号密码"""
    account: str = Field(..., description="深航系统账号", min_length=1, max_length=200)
    password: str = Field(..., description="深航系统密码", min_length=1, max_length=200)


class PrinterService(BaseModel):
    """打印机服务配置"""
    normal_a4_printer: str = Field("", description="普通A4纸打印机名称", max_length=200)
    dot_matrix_printer: str = Field("", description="针式打印机名称", max_length=200)
    label_printer: str = Field("", description="标签打印机名称", max_length=200)


class TangyiProgram(BaseModel):
    """唐翼程序配置"""
    executable_path: str = Field("", description="唐翼应用的可执行文件路径", max_length=500)


class RobotExtraConfig(BaseModel):
    """机器人其他配置"""
    shenzhen_air_account: Optional[ShenzhenAirAccount] = Field(None, description="深圳航空物流系统账号密码")
    printer_service: Optional[PrinterService] = Field(None, description="打印机服务配置")
    tangyi_program: Optional[TangyiProgram] = Field(None, description="唐翼程序配置")


class RobotCreateOrUpdate(BaseModel):
    """新增或修改机器人请求schema"""
    id: Optional[str] = Field(None, description="机器人记录ID（传入则修改，不传则新增）")
    robot_id: str = Field(..., description="机器人ID（加密后的字符串）", min_length=1, max_length=500)
    name: str = Field(..., description="机器人名称", min_length=1, max_length=200)
    location: str = Field(..., description="机器人所在位置", min_length=1, max_length=200)
    location_required: Optional[int] = Field(1, description="是否启用location区域限制（1=开启，0=关闭）")
    task_permissions: List[str] = Field(..., description="可执行任务权限列表", min_length=1)
    extra_config: Optional[RobotExtraConfig] = Field(None, description="机器人其他配置")
    status: Optional[int] = Field(1, description="机器人状态（1=启用，0=未启用）")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (0, 1):
            raise ValueError("状态值无效，有效值为：0=未启用，1=启用")
        return v

    @field_validator("location_required")
    @classmethod
    def validate_location_required(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (0, 1):
            raise ValueError("location_required值无效，有效值为：0=关闭，1=开启")
        return v

    @field_validator("task_permissions")
    @classmethod
    def validate_task_permissions(cls, v: List[str]) -> List[str]:
        from app.models.rpa_task import RPATaskType
        valid_types = {e.value for e in RPATaskType}
        for perm in v:
            if perm not in valid_types:
                raise ValueError(f"无效的任务权限类型: {perm}，有效值请参考任务权限列表接口")
        return v


class RobotListQuery(BaseModel):
    """机器人列表查询schema"""
    model_config = ConfigDict(populate_by_name=True)

    status: Optional[int] = Field(None, description="机器人状态筛选（0=未启用，1=启用）")
    page: int = Field(1, ge=1, description="页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页数量")


class TaskProcessCreateUpdate(BaseModel):
    """新增或修改任务流程请求schema"""
    task_name: str = Field(..., description="任务名称（如 SHENZHEN_AIR_WAYBILL_EXECUTE）", min_length=1, max_length=100)
    chinese_name: str = Field(..., description="中文名称", min_length=1, max_length=200)
    process_detail_uuid: str = Field(..., description="RPA流程详情UUID", min_length=1, max_length=100)
    version: str = Field(..., description="版本号", min_length=1, max_length=20)
    process_param: Optional[Dict[str, Any]] = Field(None, description="流程入参（JSON对象）")


class TaskProcessResponse(TaskProcessCreateUpdate):
    """任务流程响应schema"""
    id: str = Field(..., description="记录ID")
    created_at: str = Field(..., description="创建时间")
    updated_at: str = Field(..., description="更新时间")
