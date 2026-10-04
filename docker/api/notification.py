# 容器//脚本—通知接口路由装配（步 C：端点按职责拆至子模块，本文件只做装配与再导出）
"""通知接口的**路由装配**：汇总配置 / 日志 / 策略三组子路由，保留诊断端点与兼容再导出。

拆分（2026-10-03 步 C，`docker/api/notification.py` 有效 395 行 → 本文件 + 4 个子模块）：
- `notification_config.py`：GET/PUT `/api/notification/config`、GET `/api/notification/channels`（含凭据掩码/审计）；
- `notification_logs.py`：GET/DELETE `/api/notification/logs`、POST `/api/notification/read`、
  GET `/api/notification/unread-count`；
- `notification_policy.py`：GET/PUT `/api/notification/policy`；
- `notification_deps.py`：公共依赖注入助手。

**约束 D-1/D-2**：端点路径与请求/响应 schema 逐字未变（路由以子路由装配，路径各自声明全路径）。
**兼容再导出**：`update_config` / `MarkReadRequest` / `_get_user_id` / `get_manager_dep`
（`docker/app.py` 与三个测试文件按这些名字从这里 import / patch）。
"""

import logging

from fastapi import Depends, Request
from fastapi.routing import APIRouter

from pilotstd.core.notification import NotificationMessage
from pilotstd.core.notification.channel_spec import CHANNEL_NAMES
from pilotstd.i18n import t

from ..manager import get_manager_dep as get_manager_dep  # 兼容再导出：tests 的 patch 目标
from . import notification_config, notification_logs, notification_policy
from .notification_config import update_config as update_config  # 兼容再导出
from .notification_deps import _get_notification_mgr
from .notification_deps import _get_user_id as _get_user_id  # 兼容再导出
from .notification_logs import MarkReadRequest as MarkReadRequest  # 兼容再导出

logger = logging.getLogger(__name__)
router = APIRouter(tags=["notification"])
# 子路由自身不声明 tags：父路由的 tags 在 include 时自动叠加（再传一次会重复成两个同名标签）
router.include_router(notification_config.router)
router.include_router(notification_logs.router)
router.include_router(notification_policy.router)

# SEC-001: 本模块（含子路由）的接口移除 @require_role —— 通知是用户级功能，
# 认证由 AuthMiddleware 保证，用户间隔离通过 user_id=Depends(_get_user_id)。


@router.post("/api/notification/test")
def test_notification(request: Request, body: dict, nmgr=Depends(_get_notification_mgr)):
    """发送测试通知到指定渠道。

    body:
      channel: str     — 渠道名: wechat / telegram / feishu / dingtalk
      title: str       — 标题（可选）
      body: str        — 正文（可选）
      params: dict     — 渠道参数覆盖（可选，如临时测试其他 webhook）
    """
    channel = body.get("channel", "")
    if channel not in CHANNEL_NAMES:
        return {"ok": False, "error": t("notification.api.unsupported_channel").format(ch=channel)}

    msg = NotificationMessage(
        title=body.get("title") or t("notification.api.test_title"),
        body=body.get("body") or t("notification.api.test_body"),
        level="info",
        event_type="test",
    )
    # 渠道参数覆盖（如测试前端的临时_）
    params = body.get("params") or {}
    result = nmgr.test_send(channel, msg, params)
    return result


