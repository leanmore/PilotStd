# 容器//脚本—通知日志与已读状态接口（步 C：按职责自 notification.py 拆出）
"""通知日志与已读状态接口：GET/DELETE `/api/notification/logs`、POST `/api/notification/read`、
GET `/api/notification/unread-count`。

**端点路径与请求/响应 schema 与拆分前逐字一致**（约束 D-1/D-2）；本模块只做搬迁，不改逻辑。
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from pilotstd.i18n import t

from .notification_deps import _get_notification_mgr

logger = logging.getLogger(__name__)
# tags 由聚合模块 `notification.py` 在 include_router 时注入——
# 若此处也声明，同一路由会带上两个同名标签（OpenAPI 不再与拆分前一致）。
router = APIRouter()


class MarkReadRequest(BaseModel):
    id: int | None = None  # None 表示全部标记已读


@router.get("/api/notification/logs")
def get_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: str | None = Query(None),
    status: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    is_read: bool | None = Query(None),
    nmgr=Depends(_get_notification_mgr),
):
    """查询通知发送日志（分页+筛选）。"""
    result = nmgr.ops.get_logs(
        page=page,
        size=page_size,
        channel=channel,
        status=status,
        start_date=start_date,
        end_date=end_date,
        is_read=is_read,
    )
    return {
        "total": result["total"],
        "page": result["page"],
        "page_size": result["size"],
        "items": [
            {
                "id": r["id"],
                "event_type": r["event_type"],
                "channel": r["channel"],
                "title": r["title"],
                "body": r["body"],
                "standard_number": r["standard_number"],
                "status": r["status"],
                "error_msg": r["error_msg"],
                "sent_at": r["sent_at"],
                "is_read": r.get("is_read", 0),
            }
            for r in result["items"]
        ],
    }


@router.post("/api/notification/read")
def mark_notification_read(request: MarkReadRequest, nmgr=Depends(_get_notification_mgr)):
    """标记单条或全部通知为已读。id=None 表示全部标记已读。"""
    try:
        ids = [request.id] if request.id is not None else None
        if request.id is not None:
            # 验证存在
            result = nmgr.ops.get_logs(page=1, size=1, start_date=None, end_date=None)
            existing_ids = {r["id"] for r in result["items"]}
            if request.id not in existing_ids:
                return JSONResponse(
                    {"error": t("notification.api.mark_read_not_found").format(id=request.id)},
                    status_code=404,
                )
        count = nmgr.ops.mark_logs_read(ids)
        return {"ok": True, "count": count, "message": t("notification.api.mark_read_success")}
    except Exception as e:
        logger.exception(t("notification.api.log_mark_read_failed"))
        return JSONResponse({"error": str(e)}, status_code=500)


@router.get("/api/notification/unread-count")
def get_unread_count(request: Request, nmgr=Depends(_get_notification_mgr)):
    """获取未读通知数量。"""
    try:
        count = nmgr.ops.get_unread_count()
        return {"count": count}
    except Exception as e:
        logger.exception(t("notification.api.log_unread_count_failed"))
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/api/notification/logs")
def delete_notification_logs(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    nmgr=Depends(_get_notification_mgr),
):
    """清理通知日志（仅管理员）。删除 days 天前的记录。"""
    try:
        deleted = nmgr.ops.cleanup_logs(days)
        return {"ok": True, "deleted": deleted}
    except Exception as e:
        logger.exception(t("notification.api.log_cleanup_failed"))
        return JSONResponse({"error": str(e)}, status_code=500)


