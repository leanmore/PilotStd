# 模块：容器//_脚本—阶段3:公告详情页接口
import logging
from urllib.parse import urlparse

from fastapi import BackgroundTasks, Depends, HTTPException, Query
from fastapi.routing import APIRouter

from pilotstd.announcement._content_cleaner import clean_announcement_content  # 防绕过：确保写入前清洗
from pilotstd.constants.announce_types import SOURCE_SITE_TO_ANNC as SOURCE_MAP

from ..manager import get_manager_dep
from ._announce_detail_parse import _now_iso, _parse_attachment_bg

router = APIRouter(tags=["announce"])
logger = logging.getLogger(__name__)

# 站点域名→中文名映射（后缀匹配兜底）
SITE_NAME_MAP = {
    "std.samr.gov.cn": "国家标准委",
    "openstd.samr.gov.cn": "国家标准全文公开系统",
    "gov.cn": "国家部委",
}

# 链接标识符→_反向映射
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




# ════════════════════════════════════════════════════════════════ 分隔
# 1.获取公告记录（分页版 — 第一阶段分页化，与 /lite 并存向后兼容）
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/announcements/{announce_no}/records")
def get_announcement_records_paginated(
    announce_no: str,
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数，1-200"),
    mgr=Depends(get_manager_dep),
):
    """分页获取公告标准记录。

    排序 standard_number ASC（依赖迁移 v53 复合索引
    idx_announcement_record_announce_no_std，同时命中 WHERE 与 ORDER BY）。
    /lite 端点保留不动，向后兼容。
    """
    # 手动校验：直接调用处理器（绕过 FastAPI 依赖注入）时 Query 校验不生效
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(422, "page 需 >=1，pageSize 需在 1-200 之间")

    db = mgr.db

    total_row = db.fetchone(
        "SELECT COUNT(*) AS cnt FROM announcement_record WHERE announce_no = ?",
        (announce_no,),
    )
    total = total_row["cnt"] if total_row else 0

    offset = (page - 1) * page_size
    rows = db.fetchall(
        "SELECT id, row_index, standard_number, std_name,"
        " publish_date, implement_date, expiry_date, superseded_by, status"
        " FROM announcement_record"
        " WHERE announce_no = ?"
        " ORDER BY standard_number ASC"
        " LIMIT ? OFFSET ?",
        (announce_no, page_size, offset),
    )

    items = [dict(r) for r in rows]
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "hasMore": offset + len(items) < total,
    }


# ════════════════════════════════════════════════════════════════ 分隔
# 1.获取公告详情
# ════════════════════════════════════════════════════════════════ 分隔


@router.get("/api/announcements/{announce_no}")
def get_announcement_detail(announce_no: str, mgr=Depends(get_manager_dep)):
    """获取公告头 + 关联的所有标准记录。"""
    db = mgr.db

    # 优先从表获取公告头（含_等字段）
    ann = db.fetchone(
        "SELECT id, title, publish_date, source_url, attachment_url, raw_data, source_site,"
        " COALESCE(parse_status, 'pending') AS parse_status"
        " FROM announcements WHERE announce_no = ?",
        (announce_no,),
    )

    # 公告头信息：表有则取，无则从_回退
    if ann:
        title = ann["title"] or ""
        publish_date = ann["publish_date"] or ""
        source_url = ann["source_url"] or ""
        attachment_url = ann["attachment_url"] or ""
        content = ann["raw_data"] or ""
        db_parse_status = ann["parse_status"] or "pending"
    else:
        # 回退：从_聚合基本头信息
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

    # 公告级_：取记录中的众数来源类型
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
# 1.获取公告详情（轻量版—裁剪冗余字段）
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

    # 字段白名单：仅查询渲染必需的列+_（聚合统计用）
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
# 1.按公告编号查询所有来源（旧链接兼容）
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
        # 自愈：公告只在_中，不在表
        rec = db.fetchone(
            "SELECT pid, source_site, announce_no,"
            " MAX(announcement_title) AS title, MAX(publish_date) AS publish_date"
            " FROM announcement_record WHERE announce_no = ?"
            " GROUP BY announce_no",
            (announce_no,),
        )
        if rec:
            # 防绕过：_经清洗管线后再写入，确保语义补全
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
