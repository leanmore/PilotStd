# docker/api/user.py — 用户配置 API（v23：统一首选项 + 布局兼容，通过 UserService 委派）
import logging

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..auth import get_current_username
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["user"])


# ── 布局（保留向后兼容） ──────────────────────


@router.get("/api/user/layout")
def get_layout(request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.get_layout(user_id)


@router.put("/api/user/layout")
def put_layout(
    data: dict, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    result = mgr.user_service.save_layout(user_id, data.get("layout", ""))
    if "error" in result:
        return JSONResponse(result, 400)
    return result


@router.delete("/api/user/layout")
def delete_layout(request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.delete_layout(user_id)


# ── 统一首选项（v22） ──────────────────────


@router.get("/api/user/preferences")
def get_all_preferences(request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.get_preferences(user_id)


@router.get("/api/user/preferences/{key:path}")
def get_preference(
    key: str, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.get_preference(user_id, key)


@router.put("/api/user/preferences/{key:path}")
def put_preference(
    key: str, data: dict, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    if "value" not in data:
        return JSONResponse({"error": "缺少 value 字段"}, 400)
    return mgr.user_service.save_preference(user_id, key, data["value"])


@router.put("/api/user/preferences")
def put_preferences_batch(
    data: dict, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    preferences = data.get("preferences", {})
    result = mgr.user_service.save_preferences_batch(user_id, preferences)
    if "error" in result:
        return JSONResponse(result, 400)
    return result


@router.delete("/api/user/preferences/{key:path}")
def delete_preference(
    key: str, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.delete_preference(user_id, key)


# ── 统一设置（v31：合并 layout + preferences，减少 HTTP 请求数） ──


@router.get("/api/user/settings")
def get_settings(request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.get_user_settings(user_id)


@router.put("/api/user/settings")
def put_settings(
    data: dict, request: Request, username: str = Depends(get_current_username), mgr=Depends(get_manager_dep)
):
    user_id = mgr.user_service.get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    return mgr.user_service.save_user_settings(user_id, data)
