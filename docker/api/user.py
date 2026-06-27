# docker/api/user.py — 用户布局持久化 API（v21）
# GET  /api/user/layout  → 获取布局
# PUT  /api/user/layout  → 保存布局
# DELETE /api/user/layout → 重置为默认

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
    """通过用户名查找 user_id。"""
    db = Database(get_db_path())
    row = db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
    return row["id"] if row else None


@router.get("/api/user/layout")
def get_layout(request: Request, username: str = Depends(get_current_username)):
    """获取当前用户的仪表板布局。"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)

    db = Database(get_db_path())
    row = db.fetchone(
        "SELECT layout_data FROM user_layouts WHERE user_id = ? AND layout_key = 'dashboard'",
        (user_id,),
    )
    if row is None:
        return {"layout": None}
    return {"layout": row["layout_data"]}


@router.put("/api/user/layout")
def put_layout(data: dict, request: Request, username: str = Depends(get_current_username)):
    """保存当前用户的仪表板布局（覆盖）。"""
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
    """删除布局数据（重置为默认布局）。"""
    user_id = _get_user_id(username)
    if user_id is None:
        return JSONResponse({"error": "用户不存在"}, 404)

    db = Database(get_db_path())
    db.execute(
        "DELETE FROM user_layouts WHERE user_id = ? AND layout_key = 'dashboard'",
        (user_id,),
    )
    return {"ok": True}
