# docker/api/announce_detail.py — Phase 3: 公告详情页 API
import logging
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.routing import APIRouter

from ..manager import get_manager as _get_mgr
from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])
logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════
# 1. 获取公告详情
# ════════════════════════════════════════════════════════════════


@router.get("/api/announcements/{announce_no}")
def get_announcement_detail(announce_no: str, mgr=Depends(get_manager_dep)):
    """获取公告头 + 关联的所有标准记录。"""
    db = mgr.db

    # announcements 表仅在 v36 迁移时写入一次，新公告不在此表。
    # 直接查 announcement_record（运行时持续写入）获取公告头。
    header = db.fetchone(
        "SELECT announce_no,"
        " COALESCE(MAX(announcement_title), '公告 ' || announce_no) AS title,"
        " MAX(publish_date) AS publish_date"
        " FROM announcement_record WHERE announce_no = ?"
        " GROUP BY announce_no",
        (announce_no,),
    )
    if not header:
        raise HTTPException(404, "公告不存在")

    records = db.fetchall(
        "SELECT id, row_index, standard_number, std_name,"
        " implement_date, expiry_date, superseded_by,"
        " status, confidence, fetched_at AS created_at, approved_at AS updated_at"
        " FROM announcement_record"
        " WHERE announce_no = ?"
        " ORDER BY row_index",
        (announce_no,),
    )

    parse_status = "completed" if records else "pending"

    # announcement_record 不含 source_url/attachment_url，返回空字符串
    return {
        "announcement": {
            "id": hash(announce_no) & 0x7FFFFFFF,
            "announce_no": header["announce_no"],
            "title": header["title"] or "",
            "publish_date": header["publish_date"] or "",
            "source_url": "",
            "attachment_url": "",
        },
        "records": [
            {
                "id": r["id"],
                "row_index": r["row_index"] or 0,
                "standard_number": r["standard_number"] or "",
                "std_name": r["std_name"] or "",
                "implement_date": r["implement_date"] or "",
                "expiry_date": r["expiry_date"] or "",
                "superseded_by": r["superseded_by"] or "",
                "status": r["status"] or "draft",
                "confidence": r["confidence"] or 0.0,
                "created_at": r["created_at"] or "",
                "updated_at": r["updated_at"] or "",
            }
            for r in records
        ],
        "parse_status": parse_status,
    }


# ════════════════════════════════════════════════════════════════
# 2. 触发附件解析
# ════════════════════════════════════════════════════════════════


@router.post("/api/announcements/{announce_no}/parse")
def trigger_parse(
    announce_no: str,
    background_tasks: BackgroundTasks,
    mgr=Depends(get_manager_dep),
):
    """异步触发附件解析。"""
    db = mgr.db

    ann = db.fetchone(
        "SELECT id, announce_no, attachment_url FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )
    if not ann:
        raise HTTPException(404, "公告不存在")
    if not ann["attachment_url"]:
        raise HTTPException(400, "该公告没有附件")

    existing = db.fetchone(
        "SELECT COUNT(*) AS cnt FROM announcement_record WHERE announcement_id = ?",
        (ann["id"],),
    )
    if existing and existing["cnt"] > 0:
        return {"status": "already_parsed", "record_count": existing["cnt"]}

    background_tasks.add_task(
        _parse_attachment_bg,
        ann["id"],
        ann["announce_no"],
        ann["attachment_url"],
    )
    return {"status": "parsing_started", "announce_no": announce_no}


def _parse_attachment_bg(announcement_id: int, announce_no: str, attachment_url: str):
    """后台任务：下载附件 → 调用 parser → 写入 announcement_record。"""
    from pilotstd.announcement.parser import download_attachment, parse_announcement_detail

    mgr = _get_mgr()
    db = mgr.db

    try:
        logger.info("[解析] 下载附件: %s", announce_no)
        data = download_attachment(attachment_url)
        if not data:
            logger.error("[解析] 下载失败: %s", announce_no)
            return

        logger.info("[解析] 开始解析: %s, size=%d", announce_no, len(data))
        filename = attachment_url.rsplit("/", 1)[-1] or "attachment.wps"
        items, meta = parse_announcement_detail(
            html="", attachment_bytes=data, attachment_filename=filename, ocr_provider=None
        )
        if not items:
            logger.warning("[解析] 无标准: %s", announce_no)
            return

        now = _now_iso()
        for idx, item in enumerate(items):
            db.execute(
                "INSERT INTO announcement_record"
                " (announcement_id, announce_no, row_index,"
                "  standard_number, std_name, implement_date, expiry_date, superseded_by,"
                "  status, confidence, raw_text, parser_engine, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?)",
                (
                    announcement_id,
                    announce_no,
                    idx,
                    item.get("std_code", ""),
                    item.get("std_name", ""),
                    item.get("implementation_date", ""),
                    None,
                    item.get("replaces_code", ""),
                    float(item.get("confidence", 0.0)),
                    item.get("raw_text", ""),
                    meta.get("source", "attachment"),
                    now,
                ),
            )

        logger.info("[解析] 完成: %s, %d 条", announce_no, len(items))
    except Exception as e:
        logger.error("[解析] 失败: %s, %s", announce_no, e, exc_info=True)


# ════════════════════════════════════════════════════════════════
# 3. 查询解析状态
# ════════════════════════════════════════════════════════════════


@router.get("/api/announcements/{announce_no}/parse-status")
def get_parse_status(announce_no: str, mgr=Depends(get_manager_dep)):
    """查询解析状态（供前端轮询）。"""
    db = mgr.db

    ann = db.fetchone("SELECT id FROM announcements WHERE announce_no = ?", (announce_no,))
    if not ann:
        raise HTTPException(404, "公告不存在")

    row = db.fetchone(
        "SELECT COUNT(*) AS cnt FROM announcement_record WHERE announcement_id = ?",
        (ann["id"],),
    )
    count = row["cnt"] if row else 0
    return {"status": "completed" if count > 0 else "pending", "record_count": count}


# ════════════════════════════════════════════════════════════════
# 4. 单行更新（单元格编辑）
# ════════════════════════════════════════════════════════════════


@router.patch("/api/announcement-record/{record_id}")
def update_record(record_id: int, data: dict, mgr=Depends(get_manager_dep)):
    """前端双击单元格后调用，保存单行修改。"""
    db = mgr.db

    record = db.fetchone("SELECT id, status FROM announcement_record WHERE id = ?", (record_id,))
    if not record:
        raise HTTPException(404, "记录不存在")
    if record["status"] == "approved":
        raise HTTPException(400, "已确认的记录不可编辑")

    allowed = {
        "standard_number",
        "std_name",
        "implement_date",
        "expiry_date",
        "superseded_by",
    }
    updates = {k: v for k, v in data.items() if k in allowed and v is not None}
    if not updates:
        raise HTTPException(400, "无有效更新字段")

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values())
    new_status = "pending_review" if record["status"] == "draft" else record["status"]
    now = _now_iso()

    db.execute(
        f"UPDATE announcement_record SET {set_clause}, status = ?, updated_at = ? WHERE id = ?",
        values + [new_status, now, record_id],
    )

    return {"id": record_id, "status": new_status, "updated_at": now}


# ════════════════════════════════════════════════════════════════
# 5. 批量确认入库
# ════════════════════════════════════════════════════════════════


@router.post("/api/announcement-record/batch-approve")
def batch_approve(data: dict, mgr=Depends(get_manager_dep)):
    """批量确认：将选中记录状态改为 approved。事务保证原子性。"""
    db = mgr.db
    ids = data.get("ids", [])
    if not ids:
        raise HTTPException(400, "未选择任何记录")

    placeholders = ", ".join("?" for _ in ids)
    records = db.fetchall(
        f"SELECT id, status, standard_number, std_name FROM announcement_record WHERE id IN ({placeholders})",
        ids,
    )
    if not records:
        raise HTTPException(400, "未找到有效记录")

    errors = []
    to_approve = []
    for r in records:
        if r["status"] == "approved":
            continue
        if not r["standard_number"] or not r["std_name"]:
            errors.append(f"ID {r['id']}: 标准号或名称为空")
            continue
        to_approve.append(r["id"])

    if errors:
        raise HTTPException(400, detail={"errors": errors, "approved_count": 0})

    if not to_approve:
        return {"status": "completed", "approved_count": 0, "errors": []}

    now = _now_iso()
    placeholders_approve = ", ".join("?" for _ in to_approve)
    db.execute(
        f"UPDATE announcement_record SET status = 'approved', approved_at = ?, updated_at = ?"
        f" WHERE id IN ({placeholders_approve})",
        [now, now] + to_approve,
    )

    return {"status": "completed", "approved_count": len(to_approve), "errors": []}
