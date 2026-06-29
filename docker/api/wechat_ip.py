# docker/api/wechat_ip.py — 企业微信可信 IP 自动更新 API
# GET  /api/wechat-ip/config   → 获取配置
# PUT  /api/wechat-ip/config   → 保存配置
# POST /api/wechat-ip/check    → 立即检测并更新
# GET  /api/wechat-ip/status   → 当前状态
import logging

from fastapi import Depends
from fastapi.routing import APIRouter

from ..auth import require_admin
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wechat-ip"])


@router.get("/api/wechat-ip/config")
def get_config(mgr=Depends(get_manager_dep)):
    """获取可信 IP 自动更新配置。"""
    return mgr.wechat_ip_service.get_config()


@router.put("/api/wechat-ip/config")
def put_config(body: dict, mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """保存可信 IP 配置。"""
    return mgr.wechat_ip_service.update_config(body)


@router.post("/api/wechat-ip/check")
def trigger_check(mgr=Depends(get_manager_dep), user: str = Depends(require_admin)):
    """立即执行一次 IP 检测 + 更新。"""
    return mgr.wechat_ip_service.run_check()


@router.get("/api/wechat-ip/status")
def get_status(mgr=Depends(get_manager_dep)):
    """获取当前状态：公网 IP、Cookie 有效性、上次更新结果。"""
    return mgr.wechat_ip_service.get_status()
