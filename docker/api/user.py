# docker/api/user.py — 用户配置 API（v22：统一首选项 + 布局兼容）
import json
import logging

from fastapi import Depends, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter

from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

from ..auth import get_current_username

logger = logging.getLogger(__name__)
router = APIRouter(tags=["user"])


def _get_user_id(username: str) -> int | None:
    db = Database(get_db_path())
    row = db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
    return row["id"] if row else None


# ── 布局（保留向后兼容） ──────────────────────


@router.get("/api/user/layout")
def get_layout(request: Request, username: str = Depends(get_current_username)):
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    db = Database(get_db_path())
    row = db.fetchone(
        "SELECT layout_data FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
        (user_id,),
    )
    if row is None:
        return {"layout": None}
    return {"layout": row["layout_data"]}


@router.put("/api/user/layout")
def put_layout(data: dict, request: Request, username: str = Depends(get_current_username)):
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    layout_data = data.get("layout", "")
    if not layout_data:
        return JSONResponse({"error": "缺少 layout 字段"}, 400)
    db = Database(get_db_path())
    db.execute(
        "INSERT OR REPLACE INTO user_layouts (user_id, layout_key, layout_data, updated_at) "
        "VALUES (?, 'dashboard', ?, datetime('now'))",
        (user_id, layout_data),
    )
    return {"ok": True}


@router.delete("/api/user/layout")
def delete_layout(request: Request, username: str = Depends(get_current_username)):
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    db = Database(get_db_path())
    db.execute(
        "DELETE FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
        (user_id,),
    )
    return {"ok": True}


# ── 统一首选项（v22） ──────────────────────


@router.get("/api/user/preferences")
def get_all_preferences(request: Request, username: str = Depends(get_current_username)):
    """获取当前用户的所有配置项。"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    db = Database(get_db_path())
    rows = db.fetchall(
        "SELECT preference_key, preference_value, updated_at "
        "FROM user_preferences WHERE user_id=? ORDER BY preference_key",
        (user_id,),
    )
    return {"preferences": {r["preference_key"]: json.loads(r["preference_value"]) for r in rows}}


@router.get("/api/user/preferences/{key:path}")
def get_preference(key: str, request: Request, username: str = Depends(get_current_username)):
    """获取指定配置项。"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    db = Database(get_db_path())
    row = db.fetchone(
        "SELECT preference_key, preference_value, updated_at "
        "FROM user_preferences WHERE user_id=? AND preference_key=?",
        (user_id, key),
    )
    if row is None:
        return {"key": key, "value": None}
    return {
        "key": row["preference_key"],
        "value": json.loads(row["preference_value"]),
        "updated_at": row["updated_at"],
    }


@router.put("/api/user/preferences/{key:path}")
def put_preference(key: str, data: dict, request: Request, username: str = Depends(get_current_username)):
    """保存单个配置项。Body: {"value": <any>}"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    if "value" not in data:
        return JSONResponse({"error": "缺少 value 字段"}, 400)
    value = json.dumps(data["value"], ensure_ascii=False)
    db = Database(get_db_path())
    db.execute(
        "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at) "
        "VALUES (?, ?, ?, datetime('now'))",
        (user_id, key, value),
    )
    return {"ok": True, "key": key}


@router.put("/api/user/preferences")
def put_preferences_batch(data: dict, request: Request, username: str = Depends(get_current_username)):
    """批量保存配置项。Body: {"preferences": {"key1": val1, ...}}"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    preferences = data.get("preferences", {})
    if not isinstance(preferences, dict) or not preferences:
        return JSONResponse({"error": "缺少 preferences 字段"}, 400)
    db = Database(get_db_path())
    for key, val in preferences.items():
        db.execute(
            "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at) "
            "VALUES (?, ?, ?, datetime('now'))",
            (user_id, key, json.dumps(val, ensure_ascii=False)),
        )
    return {"ok": True, "count": len(preferences)}


@router.delete("/api/user/preferences/{key:path}")
def delete_preference(key: str, request: Request, username: str = Depends(get_current_username)):
    """删除指定配置项（恢复默认）。"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)
    db = Database(get_db_path())
    db.execute(
        "DELETE FROM user_preferences WHERE user_id=? AND preference_key=?",
        (user_id, key),
    )
    return {"ok": True, "key": key}
