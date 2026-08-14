# 容器//_脚本—接口管理已迁移至///
# 保留此文件返回410，避免旧链接404混淆
import logging

from fastapi import HTTPException
from fastapi.routing import APIRouter

from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/api-keys", tags=["deprecated"])


@require_role("admin")
@router.get("")
def list_api_keys():
    """此接口已废弃，请使用 GET /api/settings/token 获取当前静态令牌。"""
    raise HTTPException(
        status_code=410,
        detail="Gone — API Key management has been moved to /settings. Use GET /api/settings/token",
    )


@require_role("admin")
@router.post("")
def create_api_key():
    """此接口已废弃。静态令牌由管理员在设置页面 /settings 中管理。"""
    raise HTTPException(
        status_code=410,
        detail="Gone — Static token is managed via /settings. Use POST /api/settings/token/refresh to rotate.",
    )


@require_role("admin")
@router.put("/{key_id}")
def update_api_key(key_id: str):
    """此接口已废弃。"""
    raise HTTPException(
        status_code=410,
        detail="Gone — Use /api/settings/token instead.",
    )


@require_role("admin")
@router.delete("/{key_id}")
def revoke_api_key(key_id: str):
    """此接口已废弃（软删除）。静态令牌通过刷新即吊销旧值。"""
    raise HTTPException(
        status_code=410,
        detail="Gone — Static token revocation is done via refresh. "
        "Use POST /api/settings/token/refresh to rotate the token.",
    )


@require_role("admin")
@router.put("/{key_id}/reactivate")
def reactivate_api_key(key_id: str):
    """此接口已废弃。"""
    raise HTTPException(
        status_code=410,
        detail=("Gone — Use POST /api/settings/token/refresh to manage the static token."),
    )
