# 模块：项目/核心/脚本
"""审计日志写入/读取 — detail 用 json.dumps/loads 保证 SQLite TEXT 兼容。

用法:
    from pilotstd.core.audit import write_audit, read_audit

    write_audit(action="SETTINGS_WRITE", resource="PUT /api/settings",
                detail={"changed_keys": ["storage", "network"]})

    logs = read_audit(user_id=1, limit=50)
"""

from __future__ import annotations

import json
import logging
from typing import Any

from .config.paths import get_db_path
from .context import get_current_user_id
from .db import Database

logger = logging.getLogger(__name__)


def write_audit(
    action: str,
    resource: str = "",
    detail: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> None:
    """写入一条审计日志。

    user_id 从 ContextVar 自动获取；传入则覆盖。
    未认证时为 None → SQLite NULL（无 FK 约束）。
    detail 用 json.dumps 序列化，跨数据库兼容。
    写入失败静默吞异常，不阻断业务。
    """
    uid = user_id if user_id is not None else get_current_user_id()
    # .保证嵌套结构在列中正确存取
    detail_json = json.dumps(detail or {}, ensure_ascii=False)

    try:
        db = Database(get_db_path())
        db.execute(
            "INSERT INTO audit_logs (user_id, action, resource, detail) VALUES (?, ?, ?, ?)",
            (uid, action, resource, detail_json),
        )
        db.close()
    except Exception:
        logger.warning("审计写入失败: action=%s user=%s", action, uid, exc_info=True)


def read_audit(
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """读取审计日志，按时间倒序。

    可选按 user_id / action 过滤。detail 自动 json.loads 反序列化。
    """
    db = Database(get_db_path())
    sql = "SELECT id, user_id, action, resource, detail, timestamp FROM audit_logs WHERE 1=1"
    params: list[Any] = []

    if user_id is not None:
        sql += " AND user_id = ?"
        params.append(user_id)
    if action is not None:
        sql += " AND action = ?"
        params.append(action)

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = db.fetchall(sql, tuple(params))
    result = []
    for r in rows:
        item = dict(r)
        # .反序列化，失败时保留原字符串
        try:
            item["detail"] = json.loads(item["detail"])
        except (json.JSONDecodeError, TypeError):
            pass
        result.append(item)

    db.close()
    return result
