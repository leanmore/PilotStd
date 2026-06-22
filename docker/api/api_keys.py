# docker/api/api_keys.py — API Key 管理已迁移至 /api/settings/token
# 保留此文件返回 410 Gone，避免旧链接 404 混淆
import logging

from fastapi.routing import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/api-keys", tags=["api_keys"])

_GONE_MSG = "API Key management has moved to /api/settings/token"


def _gone():
    from fastapi import HTTPException

    raise HTTPException(410, _GONE_MSG)


@router.post("")
def create_api_key():
    _gone()


@router.get("")
def list_api_keys():
    _gone()


@router.put("/{key_id}")
def update_api_key(key_id: str):
    _gone()


@router.delete("/{key_id}")
def revoke_api_key(key_id: str):
    _gone()


@router.put("/{key_id}/reactivate")
def reactivate_api_key(key_id: str):
    _gone()
