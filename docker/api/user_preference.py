# DEPRECATED since v0.93 — use /api/user/preferences/{key} for per-key KV access.
# These endpoints log warnings and forward to the unified user_preferences table.
# All three HTTP methods preserved as backward-compatible aliases.
import logging
from typing import Any, Dict

from fastapi import Depends, HTTPException, Request
from fastapi.routing import APIRouter
from pydantic import BaseModel

from docker.auth import get_current_user_id
from docker.users import get_user_by_id
from pilotstd.manager.settings_manager import UserPreferenceManager

logger = logging.getLogger(__name__)
router = APIRouter()


def _deprecated_warn(request: Request, endpoint: str) -> None:
    """Log a deprecation warning with caller IP for tracking legacy API usage."""
    client_ip = request.client.host if request.client else "unknown"
    logger.warning(
        "DEPRECATED endpoint %s called from %s — 请迁移到 GET/PUT /api/user/preferences/{key}",
        endpoint, client_ip,
    )


class PreferencesUpdate(BaseModel):
    updates: Dict[str, Any]


@router.get("/api/user-preference")
async def get_preferences(request: Request, username: int = Depends(get_current_user_id)):
    """[DEPRECATED] 获取全部偏好 — 请使用 GET /api/user/preferences/{key}"""
    _deprecated_warn(request, "/api/user-preference")
    user = get_user_by_id(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    prefs = UserPreferenceManager.get_preferences(user["id"])
    return {"status": "success", "data": prefs}


@router.patch("/api/user-preference")
async def update_preferences(
    data: PreferencesUpdate,
    request: Request,
    username: int = Depends(get_current_user_id),
):
    """[DEPRECATED] 增量更新偏好 — 请使用 PUT /api/user/preferences/{key}"""
    _deprecated_warn(request, "/api/user-preference")
    user = get_user_by_id(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_prefs = UserPreferenceManager.update_preferences(user["id"], data.updates)
    return {"status": "success", "data": new_prefs}


@router.delete("/api/user-preference")
async def reset_preferences(request: Request, username: int = Depends(get_current_user_id)):
    """[DEPRECATED] 重置偏好 — 请使用 DELETE /api/user/preferences/{key}"""
    _deprecated_warn(request, "/api/user-preference")
    user = get_user_by_id(username)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    default_prefs = UserPreferenceManager.reset_preferences(user["id"])
    return {"status": "success", "data": default_prefs, "message": "已恢复默认设置"}
