"""企业微信预警通知开关的统一判定。"""

from enum import Enum
from typing import Dict

from app.config import settings


class WechatAlertScene(str, Enum):
    """当前系统中会向企业微信群机器人发送消息的业务场景。"""

    SHENZHEN_AIR_APPROVAL = "shenzhen_air_approval"
    SHENZHEN_AIR_DEPARTURE = "shenzhen_air_departure"
    CHINA_SOUTHERN_AIR_DEPARTURE = "china_southern_air_departure"
    SHENZHEN_AIR_LOADING = "shenzhen_air_loading"
    CHINA_SOUTHERN_AIR_LOADING = "china_southern_air_loading"
    SHENZHEN_AIR_DEPARTURE_STATUS = "shenzhen_air_departure_status"
    CHINA_SOUTHERN_AIR_DEPARTURE_STATUS = "china_southern_air_departure_status"


_SCENE_SWITCHES: Dict[WechatAlertScene, str] = {
    WechatAlertScene.SHENZHEN_AIR_APPROVAL:
        "WECHAT_ALERT_SHENZHEN_AIR_APPROVAL_ENABLED",
    WechatAlertScene.SHENZHEN_AIR_DEPARTURE:
        "WECHAT_ALERT_SHENZHEN_AIR_DEPARTURE_ENABLED",
    WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE:
        "WECHAT_ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_ENABLED",
    WechatAlertScene.SHENZHEN_AIR_LOADING:
        "WECHAT_ALERT_SHENZHEN_AIR_LOADING_ENABLED",
    WechatAlertScene.CHINA_SOUTHERN_AIR_LOADING:
        "WECHAT_ALERT_CHINA_SOUTHERN_AIR_LOADING_ENABLED",
    WechatAlertScene.SHENZHEN_AIR_DEPARTURE_STATUS:
        "WECHAT_ALERT_SHENZHEN_AIR_DEPARTURE_STATUS_ENABLED",
    WechatAlertScene.CHINA_SOUTHERN_AIR_DEPARTURE_STATUS:
        "WECHAT_ALERT_CHINA_SOUTHERN_AIR_DEPARTURE_STATUS_ENABLED",
}


def is_wechat_alert_enabled(scene: WechatAlertScene) -> bool:
    """总开关和场景开关均开启时才允许发送。"""
    if not settings.WECHAT_ALERT_ENABLED:
        return False
    return bool(getattr(settings, _SCENE_SWITCHES[scene]))


def should_send_wechat_alert(
    scene: WechatAlertScene,
    *,
    log_prefix: str,
) -> bool:
    """返回是否允许发送，并在关闭时记录清晰日志。"""
    if not settings.WECHAT_ALERT_ENABLED:
        print(f"{log_prefix} 企业微信预警总开关已关闭，跳过发送")
        return False

    switch_name = _SCENE_SWITCHES[scene]
    if not getattr(settings, switch_name):
        print(f"{log_prefix} 场景开关 {switch_name} 已关闭，跳过发送")
        return False
    return True
