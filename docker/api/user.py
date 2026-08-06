# 用户配置 API — 统一偏好设置 + 已废弃的 layout/settings 别名
import logging

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from ..auth import get_current_user_id
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)
router = APIRouter(tags=["user"])


def _deprecated_warn(request: Request, endpoint: str, replacement: str) -> None:
    """输出废弃端点调用警告日志。"""
    client_ip = request.client.host if request.client else "unknown"
    logger.warning(
        "DEPRECATED endpoint %s called from %s — 请迁移到 %s",
        endpoint, client_ip, replacement,
    )


# ── 布局（已废弃：请使用 /api/user/preferences/layout:dashboard）──


@router.get("/api/user/layout")
def get_layout(request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)):
    """[DEPRECATED] 获取布局 — 请使用 GET /api/user/preferences/layout:dashboard"""
    _deprecated_warn(request, "/api/user/layout", "GET /api/user/preferences/layout:dashboard")
    user_id = int(username)
    row = mgr.db.fetchone(
        "SELECT preference_value FROM user_preferences WHERE user_id=? AND preference_key='layout:dashboard'",
        (user_id,),
    )
    if not row:
        return mgr.user_service.get_layout(user_id)
    return {"layout": row["preference_value"]}


@router.put("/api/user/layout")
def put_layout(
    data: dict, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """[DEPRECATED] 保存布局 — 请使用 PUT /api/user/preferences/layout:dashboard"""
    _deprecated_warn(request, "/api/user/layout", "PUT /api/user/preferences/layout:dashboard")
    user_id = int(username)
    result = mgr.user_service.save_layout(user_id, data.get("layout", ""))
    if "error" in result:
        return JSONResponse(result, 400)
    # 同步写入统一表
    mgr.db.execute(
        "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at)"
        " VALUES (?, 'layout:dashboard', ?, datetime('now', 'localtime'))",
        (user_id, data.get("layout", "")),
    )
    return result


@router.delete("/api/user/layout")
def delete_layout(request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)):
    """[DEPRECATED] 删除布局 — 请使用 DELETE /api/user/preferences/layout:dashboard"""
    _deprecated_warn(request, "/api/user/layout", "DELETE /api/user/preferences/layout:dashboard")
    user_id = int(username)
    return mgr.user_service.delete_layout(user_id)


# ──统一首选项（22）──────────────────────


@router.get("/api/user/preferences")
def get_all_preferences(request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)):
    """获取当前用户的所有首选项（键值对字典）。"""
    user_id = int(username)
    return mgr.user_service.get_preferences(user_id)


@router.get("/api/user/preferences/{key:path}")
def get_preference(
    key: str, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """获取当前用户指定 key 的首选项值。"""
    user_id = int(username)
    return mgr.user_service.get_preference(user_id, key)


@router.put("/api/user/preferences/{key:path}")
def put_preference(
    key: str, data: dict, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """保存或更新当前用户指定 key 的首选项值，body.value 为具体值。"""
    user_id = int(username)
    if "value" not in data:
        return JSONResponse({"error": "缺少 value 字段"}, 400)
    return mgr.user_service.save_preference(user_id, key, data["value"])


@router.put("/api/user/preferences")
def put_preferences_batch(
    data: dict, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """批量保存或更新当前用户的多项首选项，body.preferences 为键值对字典。"""
    user_id = int(username)
    preferences = data.get("preferences", {})
    result = mgr.user_service.save_preferences_batch(user_id, preferences)
    if "error" in result:
        return JSONResponse(result, 400)
    return result


@router.delete("/api/user/preferences/{key:path}")
def delete_preference(
    key: str, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """删除当前用户指定 key 的首选项。"""
    user_id = int(username)
    return mgr.user_service.delete_preference(user_id, key)


# ──统一设置（已废弃：请使用 /api/user/preferences/{key}）──


@router.get("/api/user/settings")
def get_settings(request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)):
    """[DEPRECATED] 获取统一设置 — 请使用 GET /api/user/preferences/{key}"""
    _deprecated_warn(request, "/api/user/settings", "GET /api/user/preferences/{key}")
    user_id = int(username)
    return mgr.user_service.get_user_settings(user_id)


@router.put("/api/user/settings")
def put_settings(
    data: dict, request: Request, username: int = Depends(get_current_user_id), mgr=Depends(get_manager_dep)
):
    """[DEPRECATED] 保存统一设置 — 请使用 PUT /api/user/preferences/{key}"""
    _deprecated_warn(request, "/api/user/settings", "PUT /api/user/preferences/{key}")
    user_id = int(username)
    return mgr.user_service.save_user_settings(user_id, data)
