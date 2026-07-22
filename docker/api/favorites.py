# docker/api/favorites.py
# Phase 4a: 收藏 API — 收藏/状态查询/取消/列表

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

from ..auth import get_current_username

_COOLDOWN_DAYS = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))

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
    username: str = Depends(get_current_username),
):
    """收藏标准记录：仅创建收藏关系，不触发下载。
    下载由定时任务 archive_retry_service 在冷却期过后统一调度。

    等待时间：最长 28（冷却期）+ 1（cron 每日执行窗口）= 29 天。
    publish_date 当天收藏 → 首次尝试最早 D+28 04:00，最晚 D+29 04:00。
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

        pub_cursor = db.execute("SELECT publish_date FROM announcement_record WHERE id = ?", (data.record_id,))
        pub_row = pub_cursor.fetchone()
        publish_date = pub_row["publish_date"] if pub_row else None

        try:
            cursor = db.execute(
                "INSERT INTO user_favorites (user_id, record_id, status, publish_date,"
                " created_at, updated_at)"
                " VALUES (?, ?, 'pending', ?, datetime('now'), datetime('now'))",
                (user_id, data.record_id, publish_date),
            )
        except Exception:
            # 并发插入触发 UNIQUE(user_id, record_id) 约束 → 回退查现有记录
            cursor = db.execute(
                "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
                (user_id, data.record_id),
            )
            existing2 = cursor.fetchone()
            if existing2:
                return {
                    "status": "already_exists",
                    "favorite_id": existing2["id"],
                    "current_status": existing2["status"],
                }
            raise HTTPException(500, "收藏失败")

        favorite_id = cursor.lastrowid
        return {"status": "pending", "favorite_id": favorite_id}
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# 2. 查询收藏状态
# ════════════════════════════════════════════════════════════════


@router.get("/api/favorites/{record_id}/status")
def get_favorite_status(record_id: int, username: str = Depends(get_current_username)):
    """查询指定记录的收藏状态。
    返回 status/favorite_id/local_path/error_message/in_cooldown/abandoned/archive_retry_count。
    """
    from datetime import date

    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        cursor = db.execute(
            "SELECT id, status, local_path, error_message, publish_date, archive_retry_count"
            " FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, record_id),
        )
        row = cursor.fetchone()
        if not row:
            return {"status": None, "favorite_id": None}

        # 冷却期：publish_date 存在且距今不足 _COOLDOWN_DAYS 天
        in_cooldown = False
        if row["publish_date"]:
            try:
                pub = date.fromisoformat(row["publish_date"])
                in_cooldown = (date.today() - pub).days < _COOLDOWN_DAYS
            except (ValueError, TypeError):
                pass

        return {
            "status": row["status"],
            "favorite_id": row["id"],
            "local_path": row["local_path"],
            "error_message": row["error_message"],
            "in_cooldown": in_cooldown,
            "abandoned": row["status"] == "abandoned",
            "archive_retry_count": row["archive_retry_count"] or 0,
        }
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════
# 3. 取消收藏
# ════════════════════════════════════════════════════════════════


@router.delete("/api/favorites/{record_id}")
def remove_favorite(record_id: int, username: str = Depends(get_current_username)):
    """取消收藏：按状态分级处理。

    - pending/failed/abandoned → 直接删除
    - downloading/archiving    → 标记 cancelled（无法中断已启动的 download_to_inbox）
    - done                     → 仅删除收藏记录，不删除已归档文件
    """
    db = Database(get_db_path())
    try:
        user_id = _get_user_id(username, db)
        if not user_id:
            raise HTTPException(401, "用户不存在")

        cursor = db.execute(
            "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, record_id),
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(404, "收藏记录不存在")

        fav_status = row["status"]
        if fav_status in ("pending", "failed", "abandoned"):
            db.execute(
                "DELETE FROM user_favorites WHERE id = ?",
                (row["id"],),
            )
            return {"status": "removed"}
        elif fav_status in ("downloading", "archiving"):
            db.execute(
                "UPDATE user_favorites SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
            return {"status": "cancelled", "note": "下载任务已在执行中，无法立即中断，已标记取消"}
        elif fav_status == "done":
            db.execute(
                "DELETE FROM user_favorites WHERE id = ?",
                (row["id"],),
            )
            return {"status": "removed", "note": "已归档文件保留在标准库中"}
        else:
            # cancelled 等其余状态直接删除
            db.execute(
                "DELETE FROM user_favorites WHERE id = ?",
                (row["id"],),
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
