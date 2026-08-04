# 模块：docker/api/announce_detail.py — Phase 3: 公告详情页 API
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.routing import APIRouter

from pilotstd.announcement._content_cleaner import clean_announcement_content  # 防绕过：确保写入前清洗
from pilotstd.constants.announce_types import SOURCE_SITE_TO_ANNC as SOURCE_MAP

from ..manager import get_manager as _get_mgr
from ..manager import get_manager_dep

router = APIRouter(tags=["announce"])
logger = logging.getLogger(__name__)

# 站点域名→中文名映射（后缀匹配兜底）
SITE_NAME_MAP = {
    "std.samr.gov.cn": "国家标准委",
    "openstd.samr.gov.cn": "国家标准全文公开系统",
    "gov.cn": "国家部委",
}

# URL 标识符 → source_site 反向映射
URL_SOURCE_MAP = {v: k for k, v in SOURCE_MAP.items()}


def get_site_name(url: str) -> str:
    """从 URL 提取域名并映射到中文站点名，未知则返回域名。"""
    if not url:
        return "未知来源"
    domain = urlparse(url).netloc
    if domain.startswith("www."):
        domain = domain[4:]
    if domain in SITE_NAME_MAP:
        return SITE_NAME_MAP[domain]
    for suffix, name in SITE_NAME_MAP.items():
        if domain.endswith(suffix):
            return name
    return domain


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ════════════════════════════════════════════════════════════════ 分隔
# 1. 获取公告详情
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/announcements/{announce_no}")
def get_announcement_detail(announce_no: str, mgr=Depends(get_manager_dep)):
    """获取公告头 + 关联的所有标准记录。"""
    db = mgr.db

    # 优先从 announcements 表获取公告头（含 source_url 等字段）
    ann = db.fetchone(
        "SELECT id, title, publish_date, source_url, attachment_url, raw_data, source_site,"
        " COALESCE(parse_status, 'pending') AS parse_status"
        " FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )

    # 公告头信息：announcements 表有则取，无则从 announcement_record 回退
    if ann:
        title = ann["title"] or ""
        publish_date = ann["publish_date"] or ""
        source_url = ann["source_url"] or ""
        attachment_url = ann["attachment_url"] or ""
        content = ann["raw_data"] or ""
        db_parse_status = ann["parse_status"] or "pending"
    else:
        # 回退：从 announcement_record 聚合基本头信息
        header = db.fetchone(
            "SELECT COALESCE(MAX(announcement_title), '公告 ' || announce_no) AS title,"
            " MAX(publish_date) AS publish_date"
            " FROM announcement_record WHERE announce_no = ?"
            " GROUP BY announce_no",
            (announce_no,),
        )
        if not header:
            raise HTTPException(404, "公告不存在")
        title = header["title"] or ""
        publish_date = header["publish_date"] or ""
        source_url = ""
        attachment_url = ""
        content = ""
        db_parse_status = "pending"

    records = db.fetchall(
        "SELECT id, row_index, standard_number, std_name,"
        " publish_date, implement_date, expiry_date, superseded_by,"
        " status, confidence, source_type,"
        " fetched_at AS created_at, approved_at AS updated_at"
        " FROM announcement_record"
        " WHERE announce_no = ?"
        " ORDER BY row_index",
        (announce_no,),
    )

    parse_status = db_parse_status if records else "pending"

    # 公告级 source_type：取记录中的众数来源类型
    source_types = [r["source_type"] for r in records if r.get("source_type")]
    dominant_source_type = max(set(source_types), key=source_types.count) if source_types else ""

    return {
        "announcement": {
            "id": hash(announce_no) & 0x7FFFFFFF,
            "announce_no": announce_no,
            "title": title,
            "publish_date": publish_date,
            "source_url": source_url,
            "attachment_url": attachment_url,
            "site_name": get_site_name(source_url),
            "content": content,
            "source": SOURCE_MAP.get(ann["source_site"], "") if ann else "",
            "source_type": dominant_source_type,
        },
        "records": [
            {
                "id": r["id"],
                "row_index": r["row_index"] or 0,
                "standard_number": r["standard_number"] or "",
                "std_name": r["std_name"] or "",
                "publish_date": r["publish_date"] or "",
                "implement_date": r["implement_date"] or "",
                "expiry_date": r["expiry_date"] or "",
                "superseded_by": r["superseded_by"] or "",
                "status": r["status"] or "draft",
                "confidence": r["confidence"] or 0.0,
                "source_type": r["source_type"] or "",
                "created_at": r["created_at"] or "",
                "updated_at": r["updated_at"] or "",
            }
            for r in records
        ],
        "parse_status": parse_status,
    }


# ════════════════════════════════════════════════════════════════ 分隔
# 1a. 获取公告详情（轻量版 — 裁剪 DataTable 冗余字段）
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/announcements/{announce_no}/lite")
def get_announcement_detail_lite(announce_no: str, mgr=Depends(get_manager_dep)):
    """轻量版详情：records 仅返回 DataTable 必需的 9 个字段，省略 confidence/source_type/created_at/updated_at。"""
    db = mgr.db

    ann = db.fetchone(
        "SELECT id, title, publish_date, source_url, attachment_url, raw_data, source_site,"
        " COALESCE(parse_status, 'pending') AS parse_status"
        " FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )

    if ann:
        title = ann["title"] or ""
        publish_date = ann["publish_date"] or ""
        source_url = ann["source_url"] or ""
        attachment_url = ann["attachment_url"] or ""
        content = ann["raw_data"] or ""
        db_parse_status = ann["parse_status"] or "pending"
    else:
        header = db.fetchone(
            "SELECT COALESCE(MAX(announcement_title), '公告 ' || announce_no) AS title,"
            " MAX(publish_date) AS publish_date"
            " FROM announcement_record WHERE announce_no = ?"
            " GROUP BY announce_no",
            (announce_no,),
        )
        if not header:
            raise HTTPException(404, "公告不存在")
        title = header["title"] or ""
        publish_date = header["publish_date"] or ""
        source_url = ""
        attachment_url = ""
        content = ""
        db_parse_status = "pending"

    # 字段白名单：仅查询 DataTable 渲染必需的列 + source_type（聚合统计用）
    records = db.fetchall(
        "SELECT id, row_index, standard_number, std_name,"
        " publish_date, implement_date, expiry_date, superseded_by, status, source_type"
        " FROM announcement_record"
        " WHERE announce_no = ?"
        " ORDER BY row_index",
        (announce_no,),
    )

    parse_status = db_parse_status if records else "pending"

    source_types = [r["source_type"] for r in records if r.get("source_type")]
    dominant_source_type = max(set(source_types), key=source_types.count) if source_types else ""

    return {
        "announcement": {
            "id": hash(announce_no) & 0x7FFFFFFF,
            "announce_no": announce_no,
            "title": title,
            "publish_date": publish_date,
            "source_url": source_url,
            "attachment_url": attachment_url,
            "site_name": get_site_name(source_url),
            "content": content,
            "source": SOURCE_MAP.get(ann["source_site"], "") if ann else "",
            "source_type": dominant_source_type,
        },
        "records": [
            {
                "id": r["id"],
                "row_index": r["row_index"] or 0,
                "standard_number": r["standard_number"] or "",
                "std_name": r["std_name"] or "",
                "publish_date": r["publish_date"] or "",
                "implement_date": r["implement_date"] or "",
                "expiry_date": r["expiry_date"] or "",
                "superseded_by": r["superseded_by"] or "",
                "status": r["status"] or "draft",
            }
            for r in records
        ],
        "parse_status": parse_status,
    }


# ════════════════════════════════════════════════════════════════ 分隔
# 1b. 按公告编号查询所有来源（旧链接兼容）
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/announcements/by-no/{announce_no}")
def get_announcement_by_no(announce_no: str, mgr=Depends(get_manager_dep)):
    """旧链接兼容：返回该编号下所有来源的公告头列表。"""
    db = mgr.db
    rows = db.fetchall(
        "SELECT source_site, announce_no, title FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )
    return [dict(r) for r in rows]


# ════════════════════════════════════════════════════════════════ 分隔
# 2. 触发附件解析
# ════════════════════════════════════════════════════════════════ 分隔


@router.post("/api/announcements/{announce_no}/parse")
def trigger_parse(
    announce_no: str,
    background_tasks: BackgroundTasks,
    mgr=Depends(get_manager_dep),
):
    """异步触发附件解析。先查 announcements，无则从 announcement_record 自愈。"""
    db = mgr.db

    ann = db.fetchone(
        "SELECT id, announce_no, attachment_url, source_site, pid,"
        " title, publish_date, source_url, raw_data"
        " FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )
    if not ann:
        # 自愈：公告只在 announcement_record 中，不在 announcements 表
        rec = db.fetchone(
            "SELECT pid, source_site, announce_no,"
            " MAX(announcement_title) AS title, MAX(publish_date) AS publish_date"
            " FROM announcement_record WHERE announce_no = ?"
            " GROUP BY announce_no",
            (announce_no,),
        )
        if rec:
            # 防绕过：raw_data 经清洗管线后再写入，确保语义 class 补全
            now = _now_iso()
            db.execute(
                "INSERT OR REPLACE INTO announcements"
                " (source_site, pid, announce_no, title, publish_date,"
                "  source_url, attachment_url, raw_data, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, '', '', ?, ?, ?)",
                (
                    rec["source_site"] or "",
                    rec["pid"] or "",
                    rec["announce_no"],
                    rec["title"] or "",
                    rec["publish_date"] or "",
                    clean_announcement_content(""),
                    now,
                    now,
                ),
            )
            ann = db.fetchone(
                "SELECT id, announce_no, attachment_url, source_site, pid,"
                " title, publish_date, source_url, raw_data"
                " FROM announcements WHERE announce_no = ?",
                (announce_no,),
            )

    if not ann or not ann["attachment_url"]:
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
        ann.get("source_site", ""),
        ann.get("pid", ""),
        ann.get("title", ""),
        ann.get("publish_date", ""),
        ann.get("source_url", ""),
    )
    return {"status": "parsing_started", "announce_no": announce_no}


def _parse_attachment_bg(
    announcement_id: int,
    announce_no: str,
    attachment_url: str,
    source_site: str = "",
    pid: str = "",
    ann_title: str = "",
    publish_date: str = "",
    source_url: str = "",
):
    """后台任务：下载附件 → 调用 parser → 写入 announcement_record。
    解析完成后同步更新 announcements 表头信息。"""
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

        # 清理旧记录 + 批量写入新记录，确保 row_index 从 1 开始
        db.execute("DELETE FROM announcement_record WHERE announce_no = ?", (announce_no,))

        records_data = [
            (
                announcement_id,
                announce_no,
                idx + 1,  # row_index 从 1 开始
                item.get("std_code", ""),
                item.get("std_name", ""),
                item.get("publish_date", ""),
                item.get("implementation_date", ""),
                None,
                item.get("replaces_code", ""),
                float(item.get("confidence", 0.0)),
                item.get("raw_text", ""),
                meta.get("source", "attachment"),
                "附件解析",  # 后台解析路径固定为附件解析
                now,
            )
            for idx, item in enumerate(items)
        ]
        db.executemany(
            "INSERT INTO announcement_record"
            " (announcement_id, announce_no, row_index,"
            "  standard_number, std_name, publish_date, implement_date, expiry_date, superseded_by,"
            "  status, confidence, raw_text, parser_engine, source_type, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, ?)",
            records_data,
        )

        # 解析完成后更新 announcements 表头信息 + 解析状态
        resolved_title = ann_title or meta.get("title", "")
        resolved_pub_date = publish_date or meta.get("publish_date", "")
        db.execute(
            "INSERT OR REPLACE INTO announcements"
            " (source_site, pid, announce_no, title, publish_date,"
            "  source_url, attachment_url, raw_data, parse_status, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'completed', ?)",
            (
                source_site,
                pid,
                announce_no,
                resolved_title,
                resolved_pub_date,
                source_url,
                attachment_url,
                clean_announcement_content(""),  # 解析流程无正文，空值经清洗管线保持幂等
                now,
            ),
        )

        logger.info("[解析] 完成: %s, %d 条", announce_no, len(items))
    except Exception as e:
        logger.error("[解析] 失败: %s, %s", announce_no, e, exc_info=True)


# ════════════════════════════════════════════════════════════════ 分隔
# 3. 查询解析状态
# ════════════════════════════════════════════════════════════════ 分隔


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


# ════════════════════════════════════════════════════════════════ 分隔
# 4. 单行更新（单元格编辑）
# ════════════════════════════════════════════════════════════════ 分隔


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
        "publish_date",
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


# ════════════════════════════════════════════════════════════════ 分隔
# 5. 批量确认入库
# ════════════════════════════════════════════════════════════════ 分隔


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
