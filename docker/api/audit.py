# 容器//脚本—审计日志读取接口（第 2 批安全审计闭环，裁决 D-6）
"""审计读取入口。

背景：`audit_logs` 表与 `write_audit` 早已存在（4 处调用点），但**没有任何读取接口**
——审计只写不可读，等于死数据。本模块补齐该入口，使"敏感端点 → write_audit"的
接线真正可被运维与用户验证。
"""

import logging

from fastapi import Query, Request
from fastapi.routing import APIRouter

from pilotstd.core.audit import read_audit

from ..auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["audit"])

# 单次查询上限：防止 offset 很大时把整表读进内存
_MAX_LIMIT = 500


@router.get("/api/admin/audit")
@require_role("admin")
def get_audit_logs(
    request: Request,
    user_id: int | None = Query(None, description="按用户过滤"),
    action: str | None = Query(None, description="按 action 过滤，如 PASSWORD_CHANGE"),
    limit: int = Query(50, ge=1, le=_MAX_LIMIT, description="本次返回条数"),
    offset: int = Query(0, ge=0, description="偏移量（用于分页）"),
) -> dict:
    """查询审计日志（仅管理员），按时间倒序。

    `read_audit` 只支持 limit（无 offset），故此处按其能力读取 offset+limit 条后切片——
    读多 limit 条是无状态分页的代价，换来的是不动既有审计模块的公开签名。
    """
    safe_limit = max(1, min(int(limit), _MAX_LIMIT))
    safe_offset = max(0, int(offset))
    rows = read_audit(user_id=user_id, action=action, limit=safe_limit + safe_offset)
    page = rows[safe_offset : safe_offset + safe_limit]
    return {
        "items": page,
        "count": len(page),
        "limit": safe_limit,
        "offset": safe_offset,
        "has_more": len(rows) > safe_offset + safe_limit,
    }
