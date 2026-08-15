# 容器//_脚本—企业微信可信自动更新接口
# //-/配置→获取配置
# //-/配置→保存配置
# //-/→立即检测并更新
# //-/→当前状态
import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter

from ..auth import require_role
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["wechat-ip"])


@router.get("/api/wechat-ip/config")
@require_role("admin")
def get_config(request: Request, mgr=Depends(get_manager_dep)):
    """获取可信 IP 自动更新配置。"""
    return mgr.wechat_ip_service.get_config()


@router.put("/api/wechat-ip/config")
@require_role("admin")
def put_config(request: Request, body: dict, mgr=Depends(get_manager_dep)):
    """保存可信 IP 配置。"""
    return mgr.wechat_ip_service.update_config(body)


@router.post("/api/wechat-ip/check")
@require_role("admin")
def trigger_check(request: Request, mgr=Depends(get_manager_dep)):
    """立即执行一次 IP 检测 + 更新。"""
    return mgr.wechat_ip_service.run_check()


@router.get("/api/wechat-ip/status")
@require_role("admin")
def get_status(request: Request, mgr=Depends(get_manager_dep)):
    """获取当前状态：公网 IP、Cookie 有效性、上次更新结果。"""
    return mgr.wechat_ip_service.get_status()
