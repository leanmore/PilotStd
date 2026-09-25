# 模块：容器//脚本
# 阶段4:收藏接口—收藏/状态查询/取消/列表/批量状态

import json as _json
import logging
from typing import Dict, List, Optional, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

from ..auth import get_current_user_id
from ..manager import get_manager_dep

logger = logging.getLogger(__name__)

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


def _get_user_id(user_id: int, db: Database) -> int:
    """校验用户存在性：参数为 get_current_user_id 返回的用户 ID，按主键查询。"""
    row = db.fetchone("SELECT id FROM users WHERE id = ?", (user_id,))
    if row is None:
        raise HTTPException(401, "用户不存在")
    return cast(int, row["id"])


def _find_duplicate_favorite(
    db: Database, user_id: int, record_id: int, std_no: str, standard_type: str
) -> Optional[dict]:
    """批次7：两级去重查重——公告记录级（原逻辑）+ 标准级（用户、标准号、分类联合）。

    返回已存在收藏的 {id, status} 或 None。标准级查重允许同号不同类型并存（跨类型收藏合法）。
    """
    existing = db.fetchone(
        "SELECT id, status FROM user_favorites WHERE user_id = ? AND record_id = ?",
        (user_id, record_id),
    )
    if existing:
        return {"id": existing["id"], "status": existing["status"], "level": "record"}

    dup = db.fetchone(
        "SELECT id, status FROM user_favorites "
        "WHERE user_id = ? AND standard_number = ? AND standard_type = ?",
        (user_id, std_no, standard_type),
    )
    if dup:
        return {"id": dup["id"], "status": dup["status"], "level": "standard"}
    return None


# ════════════════════════════════════════════════════════════════ 分隔
# 1. 收藏标准
# ════════════════════════════════════════════════════════════════ 分隔


@router.post("/api/favorites")
def add_favorite(
    data: FavoriteCreate,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
    mgr=Depends(get_manager_dep),
):
    """收藏标准记录：仅创建收藏关系，不触发下载。
    下载由定时任务 auto_archive_retry（favorite_chain_processor.process_chain）在冷却期后统一调度。

    等待时间：最长 28（冷却期）+ 1（cron 每日执行窗口）= 29 天。
    publish_date 当天收藏 → 首次尝试最早 D+28 04:00，最晚 D+29 04:00。
    """
    user_id = _get_user_id(user_id, db)

    record = db.fetchone(
        "SELECT id, standard_number, std_name, standard_type FROM announcement_record WHERE id = ?",
        (data.record_id,),
    )
    if not record:
        raise HTTPException(404, "标准记录不存在")

    # 批次7：收藏分类——从公告记录读取分类值（迁移后已回填），
    # 并升级去重为（用户、标准号、分类）联合判断
    standard_type = record["standard_type"] or "Unknown"
    std_no = (record["standard_number"] or "") or f"UNKNOWN_{data.record_id}"
    dup = _find_duplicate_favorite(db, user_id, data.record_id, std_no, standard_type)
    if dup:
        return {
            "status": "already_exists",
            "favorite_id": dup["id"],
            "current_status": dup["status"],
        }

    pub_row = db.fetchone("SELECT publish_date FROM announcement_record WHERE id = ?", (data.record_id,))
    publish_date = pub_row["publish_date"] if pub_row else None

    try:
        cursor = db.execute(
            "INSERT INTO user_favorites (user_id, record_id, status, publish_date,"
            " standard_number, standard_type, created_at, updated_at)"
            " VALUES (?, ?, 'pending', ?, ?, ?, datetime('now'), datetime('now'))",
            (user_id, data.record_id, publish_date, std_no, standard_type),
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

    # ── 断链修复（第五十四版迁移）：同步创建下载队列记录，进入待下载状态 ──
    # 修复前新收藏只写收藏关系表，下载队列无新行 → 下载链永不触发
    try:
        db.execute(
            "INSERT INTO favorite_downloads (favorite_id, user_id, record_id, status,"
            " standard_no, standard_name, standard_type, created_at, updated_at)"
            " VALUES (?, ?, ?, 'pending', ?, ?, ?, datetime('now'), datetime('now'))",
            (
                favorite_id,
                user_id,
                data.record_id,
                std_no,
                (record["std_name"] or "") or "未知标准",
                standard_type,
            ),
        )
    except Exception as e:
        # 队列写入失败不阻塞收藏主流程，记录日志由定时任务侧兜底
        logger.warning("创建下载队列记录失败 favorite_id=%s: %s", favorite_id, e)

    # ── 通知专项（第二阶段）：收藏成功事件 ──
    # 通知失败不得阻塞收藏主流程（异常捕获包裹，仅记录日志）
    try:
        if mgr and mgr.notification_mgr:
            mgr.notification_mgr.send_event(
                "favorite_created",
                {
                    "user_id": user_id,
                    "record_id": data.record_id,
                    "standard_no": std_no,
                    "standard_name": (record["std_name"] or "") or "未知标准",
                    "standard_type": standard_type, "publish_date": publish_date or "",
                },
            )
    except Exception as e:
        logger.warning("收藏成功事件通知发送失败 favorite_id=%s: %s", favorite_id, e)

    return {"status": "pending", "favorite_id": favorite_id}


# ════════════════════════════════════════════════════════════════ 分隔
# 2. 查询收藏状态（单条）
# ════════════════════════════════════════════════════════════════ 分隔

# ── /status 的防御性日志（第三轮 #19 附带）──
# 目的：该端点仓内已无消费方，但可能被仓外脚本调用；记录调用来源为将来清理留线索。
# 只记 ua / referer / 路径：不含查询参数（`request.url.path` 天然不含）、请求体与凭证。
_SENSITIVE_MARKERS = ("password", "token", "authorization", "secret", "api_key", "apikey", "bearer")


def _sanitize_header(value: str | None, limit: int = 200) -> str:
    """截断请求头；命中敏感关键字则整段替换，避免把凭证写进日志。"""
    if not value:
        return "-"
    text = value.strip()
    if any(marker in text.lower() for marker in _SENSITIVE_MARKERS):
        return "[redacted]"
    return text[:limit]


def _log_status_api_call(request: Request) -> None:
    """记录 /status 的调用来源（INFO 级）。不记查询参数、不记请求体。"""
    logger.info(
        "[STATUS_API] ua=%s referer=%s path=%s",
        _sanitize_header(request.headers.get("user-agent")),
        _sanitize_header(request.headers.get("referer")),
        request.url.path,
    )



@router.get("/api/favorites/{record_id}/status")
def get_favorite_status(
    record_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    db: Database = Depends(get_db),
):
    """查询指定**公告记录**的收藏 + 下载状态（语义归位版）。

    查询键：`record_id` 是 `announcement_record.id`（前端传的是公告记录的 id，
    见 useFavorite 的 `record.id`），因此按 `favorite_downloads.record_id` 查、
    并带 `user_id` 做多用户隔离——两者缺一都会查错行。

    数据来源分工：`favorite_downloads` 提供下载进度，`user_favorites` 提供"是否收藏"
    （`user_favorites.status` 只表达收藏与否，链路从不更新它，恒为 pending）。

    响应键：标准键 `download_status`/`download_error`/`last_attempt`/
    `download_updated_at`/`retry_count` + `favorite_id`（队列行主键）+ `status`
    （下载状态别名）+ `favorited`（第三轮 #19 新增，取自 user_favorites）。

    `favorited` 解决语义歧义（第三轮登记 #19）：端点按 favorite_downloads 取数时，
    "收藏存在但无队列行"与"从未收藏"会返回同一份 null 体，调用方无法区分。加入
    `favorited` 后三种状态可辨：
      - `favorited=true, status=null` → 收藏存在但无队列行（历史遗留，如 #18）
      - `favorited=false, status=null` → 未收藏
      - `favorited=true, status='abandoned'` → 收藏且已放弃
    """
    _log_status_api_call(request)

    user_id = _get_user_id(user_id, db)

    # 是否收藏：以 user_favorites 为准（与列表/批量接口同源），供调用方区分两种 null
    favorited = (
        db.fetchone(
            "SELECT 1 AS hit FROM user_favorites WHERE user_id = ? AND record_id = ? LIMIT 1",
            (user_id, record_id),
        )
        is not None
    )

    row = db.fetchone(
        "SELECT fd.favorite_id, fd.status, fd.error_message,"
        " fd.last_attempt, fd.updated_at, fd.retry_count"
        " FROM favorite_downloads fd"
        " WHERE fd.record_id = ? AND fd.user_id = ?"
        " ORDER BY COALESCE(fd.last_attempt, '') DESC, fd.id DESC LIMIT 1",
        (record_id, user_id),
    )
    if not row:
        return {"status": None, "favorite_id": None, "download_status": None, "favorited": favorited}

    status = row["status"]
    return {
        "status": status,
        "favorite_id": row["favorite_id"],
        "favorited": favorited,
        # 标准键（与列表/批量接口同名同义）
        "download_status": status,
        "download_error": row["error_message"],
        "last_attempt": row["last_attempt"],
        "download_updated_at": row["updated_at"],
        "retry_count": row["retry_count"] or 0,
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


# 下载队列表的"取最新一条"子查询：同一 favorite_id 存在多行时只取最后尝试的那条
# （ORDER BY last_attempt 倒序、id 倒序兜底，保证取值确定）；用的是
# favorite_downloads 上 UNIQUE(favorite_id, record_id) 的索引，不做全表窗口排序。
_LATEST_DOWNLOAD_JOIN = (
    " LEFT JOIN favorite_downloads fd ON fd.id = ("
    "SELECT id FROM favorite_downloads WHERE favorite_id = f.id"
    " ORDER BY COALESCE(last_attempt, '') DESC, id DESC LIMIT 1)"
)

# 下载状态四字段（列表/批量/单条三个接口共用同一口径，避免前端维护两套映射）
_DOWNLOAD_FIELDS = (
    " fd.status AS download_status,"
    " fd.error_message AS download_error,"
    " fd.last_attempt,"
    " fd.updated_at AS download_updated_at"
)


@router.get("/api/favorites")
def list_favorites(
    user_id: int = Depends(get_current_user_id),
    status: Optional[str] = None,
    db: Database = Depends(get_db),
):
    """获取当前用户的收藏列表，支持按 status 筛选，按创建时间倒序排列。

    额外返回下载队列四字段（`download_status`/`download_error`/`last_attempt`/
    `download_updated_at`）：收藏状态（user_favorites.status）与下载进度
    （favorite_downloads.status）是两件事，前者只表达"是否收藏"，后者才是
    "下到哪一步了"。队列行不存在时四字段为 None（LEFT JOIN 保留收藏行）。
    """
    user_id = _get_user_id(user_id, db)

    sql = (
        "SELECT f.id, f.user_id, f.record_id, f.status, f.local_path,"
        " f.error_message, f.created_at, f.updated_at, f.standard_type,"
        " r.standard_number, r.std_name, r.announce_no,"
        + _DOWNLOAD_FIELDS
        + " FROM user_favorites f"
        " JOIN announcement_record r ON f.record_id = r.id"
        + _LATEST_DOWNLOAD_JOIN
        + " WHERE f.user_id = ?"
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
    """批量查询多条公告记录的收藏状态，单次 SQL 替代 N+1 问题。

    除 `favorite_id`/`status`（是否收藏）外，同时返回下载队列四字段，供公告详情页
    直接显示真实下载进度（与列表、单条接口同名同义）。
    """
    if not req.record_ids:
        return {"statuses": {}}

    user_id = _get_user_id(user_id, db)

    placeholders = ",".join(["?"] * len(req.record_ids))
    sql = (
        "SELECT f.record_id, f.id AS favorite_id, f.status,"
        + _DOWNLOAD_FIELDS
        + " FROM user_favorites f"
        + _LATEST_DOWNLOAD_JOIN
        + f" WHERE f.user_id = ? AND f.record_id IN ({placeholders})"
    )
    rows = db.fetchall(sql, (user_id, *req.record_ids))

    result: Dict[str, Optional[dict]] = {str(rid): None for rid in req.record_ids}
    for row in rows:
        result[str(row["record_id"])] = {
            "favorite_id": row["favorite_id"],
            "status": row["status"],
            "download_status": row["download_status"],
            "download_error": row["download_error"],
            "last_attempt": row["last_attempt"],
            "download_updated_at": row["download_updated_at"],
        }

    return {"statuses": result}


# ════════════════════════════════════════════════════════════════ 分隔
# 6.收藏列表导出（批次7：流式响应 + 按分类筛选）
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/favorites/export")
def export_favorites(
    user_id: int = Depends(get_current_user_id),
    format: str = Query("csv", description="csv 或 json"),
    standard_type: Optional[str] = Query(None, description="按收藏分类筛选：NationalStd/IndustryStd/LocalStd/Unknown"),
    db: Database = Depends(get_db),
):
    """导出当前用户的收藏列表（流式响应防大数据量 OOM）。

    standard_type 可选：缺省导出全部；支持"导出当前分类"与"导出全部"两种交互。
    async=true 参数预留（量级达标后走 task_queue 生成文件），首期同步流式返回。
    """
    import csv as _csv
    import io as _io

    user_id = _get_user_id(user_id, db)

    sql = (
        # standard_number 以 user_favorites 为准，NULL 时回退公告记录（v57 只加列不回填，
        # 历史行该列为 NULL，曾导致导出标准号空白；见技术债 #18 补充项）
        "SELECT f.id, COALESCE(f.standard_number, r.standard_number, '') AS standard_number,"
        " f.standard_type, f.status,"
        " f.local_path, f.publish_date, f.created_at, f.updated_at,"
        " r.source_site, r.std_name"
        " FROM user_favorites f"
        " LEFT JOIN announcement_record r ON f.record_id = r.id"
        " WHERE f.user_id = ?"
    )
    params: list = [user_id]
    if standard_type:
        sql += " AND f.standard_type = ?"
        params.append(standard_type)
    sql += " ORDER BY f.created_at DESC"

    rows = db.fetchall(sql, params)

    if format == "json":
        items = [dict(r) for r in rows]
        return StreamingResponse(
            iter([_json.dumps({"favorites": items}, ensure_ascii=False, indent=2)]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=favorites.json"},
        )

    # 表格流式输出：逐行生成，避免全量拼接占用过多内存
    def _csv_stream():
        """逐行生成表格内容（表头 + 每行记录），供流式响应消费。"""
        buffer = _io.StringIO()
        writer = _csv.writer(buffer)
        writer.writerow(
            ["favorite_id", "standard_number", "standard_name", "standard_type",
             "status", "local_path", "publish_date", "created_at", "updated_at", "source_site"]
        )
        yield buffer.getvalue()
        for r in rows:
            row = _io.StringIO()
            _csv.writer(row).writerow([
                r["id"], r["standard_number"], r["std_name"] or "", r["standard_type"],
                r["status"], r["local_path"] or "", r["publish_date"] or "",
                r["created_at"], r["updated_at"], r["source_site"] or "",
            ])
            yield row.getvalue()

    return StreamingResponse(
        _csv_stream(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=favorites.csv"},
    )
