# 模块：项目//__脚本
# 公告正文存储—从脚本拆分

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _store_raw_content(
    announce_no: str,
    pid: str,
    title: str,
    notice_date: str,
    source_site: str,
    raw_html: str,
) -> None:
    """提取公告正文并写入 announcements 表（线程安全，失败静默）。"""
    from .matcher import clean_announcement_content
    from .parser import extract_content

    content = extract_content(raw_html)
    content = clean_announcement_content(content)
    if not announce_no:
        return
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database

        now = datetime.now(timezone.utc).isoformat()
        db = Database(get_db_path())
        db.execute(
            "INSERT OR REPLACE INTO announcements"
            " (source_site, pid, announce_no, title, publish_date,"
            "  source_url, attachment_url, raw_data, updated_at)"
            " VALUES (?, ?, ?, ?, ?, '', '', ?, ?)",
            (source_site, pid, announce_no, title, notice_date, content, now),
        )
        db.close()
    except Exception:
        # 正文没落盘 ⇒ 事后无法复核原文，排障证据链断裂（U-3/U-4 批 2b 升 warning）
        logger.warning("公告正文落盘失败: announce_no=%s", announce_no, exc_info=True)
