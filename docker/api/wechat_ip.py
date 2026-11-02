# 容器//_脚本—企业微信可信自动更新接口
# //-/配置→获取配置
# //-/配置→保存配置
# //-/→立即检测并更新
# //-/→当前状态
import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wechat-ip"])


class WechatIPConfigResponse(BaseModel):
    """可信 IP 配置响应：开关、检测周期、IP 源、Cookie 来源与脱敏状态等全部配置项。"""

    enabled: bool
    interval_hours: int
    ip_sources: list[str]
    cookie_source: str
    cookiecloud_url: str
    cookiecloud_key: str
    cookiecloud_password: str
    cookie_status: str
    app_urls: str
    use_selenium: bool
    update_mode: str
    notify_result: bool
    last_ip: str
    last_check_at: str


class WechatIPConfigUpdateResponse(BaseModel):
    """配置保存结果：成功只返回 ok，密钥缺失时额外给出 error 原因。"""

    ok: bool
    error: str | None = None


class WechatIPCheckResponse(BaseModel):
    """立即检测结果：公网 IP、是否发生变化、是否已更新、失败原因。"""

    ip: str
    changed: bool
    updated: bool
    error: str


class WechatIPStatusResponse(BaseModel):
    """可信 IP 状态响应：当前公网 IP（含是否已探测到的布尔标记）、Cookie 有效性、上次更新结果。"""

    current_ip: str
    current_ip_known: bool
    last_ip: str
    ip_changed: bool
    cookie_valid: bool
    enabled: bool
    last_check_at: str


@router.get("/api/wechat-ip/config", response_model=WechatIPConfigResponse)
@require_role("admin")
def get_config(request: Request, mgr=Depends(get_manager_dep)):
    """获取可信 IP 自动更新配置。"""
    return mgr.wechat_ip_service.get_config()


@router.put(
    "/api/wechat-ip/config",
    response_model=WechatIPConfigUpdateResponse,
    response_model_exclude_none=True,
)
@require_role("admin")
def put_config(request: Request, body: dict, mgr=Depends(get_manager_dep)):
    """保存可信 IP 配置。"""
    return mgr.wechat_ip_service.update_config(body)


@router.post("/api/wechat-ip/check", response_model=WechatIPCheckResponse)
@require_role("admin")
def trigger_check(request: Request, mgr=Depends(get_manager_dep)):
    """立即执行一次 IP 检测 + 更新。"""
    return mgr.wechat_ip_service.run_check()


@router.get("/api/wechat-ip/status", response_model=WechatIPStatusResponse)
@require_role("admin")
def get_status(request: Request, mgr=Depends(get_manager_dep)):
    """获取当前状态：公网 IP、Cookie 有效性、上次更新结果。"""
    return mgr.wechat_ip_service.get_status()
