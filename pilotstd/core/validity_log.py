"""时效性检查病历：把每次 L1/L2/L3 结果与失败原因写入 validity_check_log。"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)
# 表名集中在此，调用方只传 db/标准号；新增字段时只改这一处。
_TABLE = "validity_check_log"
# 结果 JSON 截断上限：防止异常返回体把单行撑爆（诊断用，不参与业务判断）。
_RESULT_JSON_LIMIT = 20000


def record(
    db: Any,
    standard_number: str,
    result: Optional[dict[str, Any]] = None,
    error: Optional[BaseException | str] = None,
    checked_at: str | None = None,
) -> None:
    """记录一条检查结果；失败不得中断主检查链路。"""
    if db is None:
        return
    now = checked_at or datetime.now(timezone.utc).isoformat()
    data = result or {}
    try:
        db.execute(
            f"INSERT INTO {_TABLE} (standard_number, checked_at, evidence, status, "
            "previous_status, found_name, source_site, match_status, ok, error, result_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                standard_number,
                now,
                str(data.get("evidence", "") or ""),
                str(data.get("status", "") or ""),
                data.get("previous"),
                str(data.get("new_standard_name", "") or data.get("found_name", "") or ""),
                str(data.get("source_site", "") or ""),
                str(data.get("match_status", "") or ""),
                0 if error is not None else 1,
                str(error or ""),
                json.dumps(data, ensure_ascii=False, default=str)[:_RESULT_JSON_LIMIT],
            ),
        )
    except Exception as exc:
        logger.warning("validity check log write failed: %s (%s)", standard_number, exc)


def cleanup(db: Any, days: int = 90) -> int:
    """删除超过保留期的检查病历，避免无限增长。"""
    if db is None:
        return 0
    # 保留期至少 1 天，避免配置成 0 时把当天记录全删。
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max(1, days))).isoformat()
    try:
        cur = db.execute(f"DELETE FROM {_TABLE} WHERE checked_at < ?", (cutoff,))
        return int(cur.rowcount or 0)
    except Exception as exc:
        logger.warning("validity check log cleanup failed: %s", exc)
        return 0
