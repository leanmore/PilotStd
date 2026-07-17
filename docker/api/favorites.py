# docker/api/favorites.py
# Phase 4a: 收藏 API — 收藏/状态查询/取消/列表

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database
from pilotstd.tasks.favorite_download import download_to_inbox

from ..auth import get_current_username

router = APIRouter()


class FavoriteCreate(BaseModel):
    record_id: int


def _get_user_id(username: str, db: Database) -> Optional[int]:
    cursor = db.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    return row["id"] if row else None


# ════════════════════════════════════════════════════════════════
# 1. 收藏标准
# ════════════════════════════════════════════════════════════════


@router.post("/api/favorites")
def add_favorite(
    data: FavoriteCreate,
    background_tasks: BackgroundTasks,
    username: str = Depends(get_current_username),
):
    """收藏标准记录：插入 user_favorites 表并触发后台下载任务。

    若已收藏则返回 already_exists 状态；若 record_id 不存在则 404。
    后台通过 download_to_inbox 将标准文件下载到用户收件箱。
    """
    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        cursor = db.execute(
            "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, data.record_id),
        )
        existing = cursor.fetchone()
        if existing:
            return {
                "status": "already_exists",
                "favorite_id": existing["id"],
                "current_status": existing["status"],
            }

        cursor = db.execute("SELECT id FROM announcement_record WHERE id = ?", (data.record_id,))
        if not cursor.fetchone():
            raise HTTPException(404, "标准记录不存在")

        cursor = db.execute(
            "INSERT INTO user_favorites (user_id, record_id, status, created_at, updated_at)"
            " VALUES (?, ?, 'pending', datetime('now'), datetime('now'))",
            (user_id, data.record_id),
        )
        favorite_id = cursor.lastrowid

        background_tasks.add_task(download_to_inbox, favorite_id, user_id, data.record_id)

        return {"status": "pending", "favorite_id": favorite_id}
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# 2. 查询收藏状态
# ════════════════════════════════════════════════════════════════


@router.get("/api/favorites/{record_id}/status")
def get_favorite_status(record_id: int, username: str = Depends(get_current_username)):
    """查询指定记录的收藏状态，返回 status/favorite_id/local_path/error_message。"""
    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        cursor = db.execute(
            "SELECT id, status, local_path, error_message FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, record_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"status": None, "favorite_id": None}

        return {
            "status": row["status"],
            "favorite_id": row["id"],
            "local_path": row["local_path"],
            "error_message": row["error_message"],
        }
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# 3. 取消收藏
# ════════════════════════════════════════════════════════════════


@router.delete("/api/favorites/{record_id}")
def remove_favorite(record_id: int, username: str = Depends(get_current_username)):
    """取消收藏：从 user_favorites 表中删除指定记录。"""
    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        db.execute(
            "DELETE FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, record_id),
        )
        return {"status": "removed"}
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# 4. 获取收藏列表
# ════════════════════════════════════════════════════════════════


@router.get("/api/favorites")
def list_favorites(username: str = Depends(get_current_username), status: Optional[str] = None):
    """获取当前用户的收藏列表，支持按 status 筛选，按创建时间倒序排列。

    返回 user_favorites 与 announcement_record 的 JOIN 结果，含标准号、名称等信息。
    """
    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        sql = (
            "SELECT f.id, f.user_id, f.record_id, f.status, f.local_path,"
            " f.error_message, f.created_at, f.updated_at,"
            " r.standard_number, r.std_name, r.announce_no"
            " FROM user_favorites f"
            " JOIN announcement_record r ON f.record_id = r.id"
            " WHERE f.user_id = ?"
        )
        params: list = [user_id]

        if status:
            sql += " AND f.status = ?"
            params.append(status)

        sql += " ORDER BY f.created_at DESC"

        cursor = db.execute(sql, params)
        rows = cursor.fetchall()
        return {"favorites": [dict(r) for r in rows]}
    finally:
        db.close()
