# 模块：容器//_脚本—公告附件后台解析（从 announce_detail.py 拆出）
"""公告附件后台解析：下载附件 → parser 解析 → 写入 announcement_record。

拆出原因（G-010 文件规模治理）：announce_detail.py 已达 454 有效行进入警告区；
本模块只承载「后台解析」这一条独立链路（不进请求线程、只被 BackgroundTasks 调度），
与路由层无双向依赖，故可整体外移而不改变任何行为。
"""

import logging
from datetime import datetime, timezone

from pilotstd.announcement._content_cleaner import clean_announcement_content

from ..manager import get_manager as _get_mgr

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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

        # 清理旧记录+批量写入新记录，确保_索引从1开始
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

        # 解析完成后更新表头信息+解析状态
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
