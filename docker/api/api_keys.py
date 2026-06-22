# docker/api/api_keys.py — API Key 管理 CRUD（仅管理员）
import hashlib
import json
import logging
import secrets

from fastapi import Body, HTTPException
from fastapi.routing import APIRouter

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

from ..auth import require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/admin/api-keys", tags=["api_keys"])


def _db() -> Database:
    return Database(get_db_path())


@router.post("")
def create_api_key(
    key_id: str = Body(...),
    description: str = Body(""),
    scopes: list = Body(default=["query:read"]),
    expires_at: str = Body(""),
    request=None,  # 注入 require_admin 的 request 依赖
):
    """创建 API Key。返回 raw_key（仅此一次，后续不可查）。"""
    require_admin(request)
    raw_key = "pst_" + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    db = _db()
    existing = db.fetchone("SELECT id FROM api_keys WHERE key_id = ?", (key_id,))
    if existing:
        raise HTTPException(409, f"Key ID '{key_id}' 已存在")
    db.execute(
        "INSERT INTO api_keys (key_id, key_hash, description, scopes, expires_at, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            key_id,
            key_hash,
            description,
            json.dumps(scopes, ensure_ascii=False),
            expires_at or None,
            "admin",
        ),
    )
    logger.info("API Key 已创建: key_id=%s", key_id)
    return {"ok": True, "key_id": key_id, "raw_key": raw_key}


@router.get("")
def list_api_keys(request=None):
    """列出所有 API Key（不含 hash 和 raw_key）。"""
    require_admin(request)
    db = _db()
    rows = db.fetchall(
        "SELECT id, key_id, description, scopes, created_at, expires_at, "
        "last_used_at, is_active, created_by FROM api_keys ORDER BY created_at DESC"
    )
    items = []
    for row in rows:
        item = dict(row)
        try:
            item["scopes"] = json.loads(item["scopes"]) if item["scopes"] else []
        except (json.JSONDecodeError, TypeError):
            item["scopes"] = []
        items.append(item)
    return {"api_keys": items}


@router.put("/{key_id}")
def update_api_key(
    key_id: str,
    description: str = Body(None),
    scopes: list = Body(None),
    expires_at: str = Body(None),
    request=None,
):
    """更新 API Key 元数据（不修改原始 Key 值）。"""
    require_admin(request)
    db = _db()
    row = db.fetchone("SELECT id FROM api_keys WHERE key_id = ?", (key_id,))
    if row is None:
        raise HTTPException(404, f"Key ID '{key_id}' 不存在")
    updates: list[str] = []
    params: list[str] = []
    if description is not None:
        updates.append("description = ?")
        params.append(description)
    if scopes is not None:
        updates.append("scopes = ?")
        params.append(json.dumps(scopes, ensure_ascii=False))
    if expires_at is not None:
        updates.append("expires_at = ?")
        params.append(expires_at or "")
    if not updates:
        return {"ok": True, "key_id": key_id, "msg": "无变更"}
    params.append(key_id)
    db.execute(
        f"UPDATE api_keys SET {', '.join(updates)} WHERE key_id = ?", tuple(params)
    )
    logger.info("API Key 已更新: key_id=%s", key_id)
    return {"ok": True, "key_id": key_id}


@router.delete("/{key_id}")
def revoke_api_key(key_id: str, request=None):
    """软删除 API Key（is_active=0）。"""
    require_admin(request)
    db = _db()
    row = db.fetchone("SELECT id FROM api_keys WHERE key_id = ?", (key_id,))
    if row is None:
        raise HTTPException(404, f"Key ID '{key_id}' 不存在")
    db.execute("UPDATE api_keys SET is_active = 0 WHERE key_id = ?", (key_id,))
    logger.info("API Key 已吊销: key_id=%s", key_id)
    return {"ok": True, "key_id": key_id, "msg": "已吊销"}


@router.put("/{key_id}/reactivate")
def reactivate_api_key(key_id: str, request=None):
    """重新激活 API Key（is_active=1）。"""
    require_admin(request)
    db = _db()
    row = db.fetchone("SELECT id FROM api_keys WHERE key_id = ?", (key_id,))
    if row is None:
        raise HTTPException(404, f"Key ID '{key_id}' 不存在")
    db.execute("UPDATE api_keys SET is_active = 1 WHERE key_id = ?", (key_id,))
    logger.info("API Key 已重新激活: key_id=%s", key_id)
    return {"ok": True, "key_id": key_id, "msg": "已重新激活"}
