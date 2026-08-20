# 模块：容器//脚本
# 阶段4:收藏接口—收藏/状态查询/取消/列表/批量状态

import os
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

from ..auth import get_current_user_id

_COOLDOWN_DAYS = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))

router = APIRouter()


# ════════════════════════════════════════════════════════════════ 分隔
# 依赖注入：请求级实例，避免每次请求新建连接
# ════════════════════════════════════════════════════════════════ 分隔


def get_db():
    """请求级 Database 依赖注入，请求结束自动关闭连接。"""
    db = Database(get_db_path())
    try:
        yield db
    finally:
        db.close()


# ════════════════════════════════════════════════════════════════ 分隔
# 模型
# ════════════════════════════════════════════════════════════════ 分隔


class FavoriteCreate(BaseModel):
    record_id: int


class BatchStatusRequest(BaseModel):
    record_ids: List[int] = Field(..., max_length=500)


# ════════════════════════════════════════════════════════════════ 分隔
# 内部辅助
# ════════════════════════════════════════════════════════════════ 分隔


def _get_user_id(user_id: int, db: Database) -> Optional[int]:
    """校验用户存在性：参数为 get_current_user_id 返回的用户 ID，按主键查询。"""
    row = db.fetchone("SELECT id FROM users WHERE id = ?", (user_id,))
    return row["id"] if row else None


# ════════════════════════════════════════════════════════════════ 分隔
# 1. 收藏标准
# ════════════════════════════════════════════════════════════════ 分隔


@router.post("/api/favorites")
def add_favorite(
    data: FavoriteCreate,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    """收藏标准记录：仅创建收藏关系，不触发下载。
    下载由定时任务 archive_retry_service 在冷却期过后统一调度。

    等待时间：最长 28（冷却期）+ 1（cron 每日执行窗口）= 29 天。
    publish_date 当天收藏 → 首次尝试最早 D+28 04:00，最晚 D+29 04:00。
    """
    user_id = _get_user_id(user_id, db)
    if not user_id:
        raise HTTPException(401, "用户不存在")

    existing = db.fetchone(
        "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
        (user_id, data.record_id),
    )
    if existing:
        return {
            "status": "already_exists",
            "favorite_id": existing["id"],
            "current_status": existing["status"],
        }

    record = db.fetchone("SELECT id FROM announcement_record WHERE id = ?", (data.record_id,))
    if not record:
        raise HTTPException(404, "标准记录不存在")

    pub_row = db.fetchone("SELECT publish_date FROM announcement_record WHERE id = ?", (data.record_id,))
    publish_date = pub_row["publish_date"] if pub_row else None

    try:
        cursor = db.execute(
            "INSERT INTO user_favorites (user_id, record_id, status, publish_date,"
            " created_at, updated_at)"
            " VALUES (?, ?, 'pending', ?, datetime('now'), datetime('now'))",
            (user_id, data.record_id, publish_date),
        )
    except Exception:
        existing2 = db.fetchone(
            "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
            (user_id, data.record_id),
        )
        if existing2:
            return {
                "status": "already_exists",
                "favorite_id": existing2["id"],
                "current_status": existing2["status"],
            }
        raise HTTPException(500, "收藏失败")

    favorite_id = cursor.lastrowid
    return {"status": "pending", "favorite_id": favorite_id}


# ════════════════════════════════════════════════════════════════ 分隔
# 2. 查询收藏状态（单条）
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/favorites/{record_id}/status")
def get_favorite_status(
    record_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    """查询指定记录的收藏状态。"""
    from datetime import date

    user_id = _get_user_id(user_id, db)
    if not user_id:
        raise HTTPException(401, "用户不存在")

    row = db.fetchone(
        "SELECT id, status, local_path, error_message, publish_date, archive_retry_count"
        " FROM user_favorites WHERE user_id = ? AND record_id = ?",
        (user_id, record_id),
    )
    if not row:
        return {"status": None, "favorite_id": None}

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


# ════════════════════════════════════════════════════════════════ 分隔
# 3. 取消收藏
# ════════════════════════════════════════════════════════════════ 分隔


@router.delete("/api/favorites/{record_id}")
def remove_favorite(
    record_id: int,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    """取消收藏：按状态分级处理。"""
    user_id = _get_user_id(user_id, db)
    if not user_id:
        raise HTTPException(401, "用户不存在")

    row = db.fetchone(
        "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
        (user_id, record_id),
    )
    if not row:
        raise HTTPException(404, "收藏记录不存在")

    fav_status = row["status"]
    if fav_status in ("pending", "failed", "abandoned"):
        db.execute("DELETE FROM user_favorites WHERE id = ?", (row["id"],))
        return {"status": "removed"}
    elif fav_status in ("downloading", "archiving"):
        db.execute(
            "UPDATE user_favorites SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
            (row["id"],),
        )
        return {"status": "cancelled", "note": "下载任务已在执行中，无法立即中断，已标记取消"}
    elif fav_status == "done":
        db.execute("DELETE FROM user_favorites WHERE id = ?", (row["id"],))
        return {"status": "removed", "note": "已归档文件保留在标准库中"}
    else:
        db.execute("DELETE FROM user_favorites WHERE id = ?", (row["id"],))
        return {"status": "removed"}


# ════════════════════════════════════════════════════════════════ 分隔
# 4. 获取收藏列表
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/favorites")
def list_favorites(
    user_id: int = Depends(get_current_user_id),
    status: Optional[str] = None,
    db: Database = Depends(get_db),
):
    """获取当前用户的收藏列表，支持按 status 筛选，按创建时间倒序排列。"""
    user_id = _get_user_id(user_id, db)
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

    rows = db.fetchall(sql, params)
    return {"favorites": [dict(r) for r in rows]}


# ════════════════════════════════════════════════════════════════ 分隔
# 5.批量查询收藏状态（替代次单条查询）
# ════════════════════════════════════════════════════════════════ 分隔


@router.post("/api/favorites/batch-status")
def batch_get_favorite_status(
    req: BatchStatusRequest,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    """批量查询多条记录的收藏状态，单次 SQL 替代 N+1 问题。"""
    if not req.record_ids:
        return {"statuses": {}}

    user_id = _get_user_id(user_id, db)
    if not user_id:
        raise HTTPException(401, "用户不存在")

    placeholders = ",".join(["?"] * len(req.record_ids))
    sql = f"SELECT record_id, id, status FROM user_favorites WHERE user_id = ? AND record_id IN ({placeholders})"
    rows = db.fetchall(sql, (user_id, *req.record_ids))

    result: Dict[str, Optional[dict]] = {str(rid): None for rid in req.record_ids}
    for row in rows:
        result[str(row["record_id"])] = {
            "favorite_id": row["id"],
            "status": row["status"],
        }

    return {"statuses": result}
