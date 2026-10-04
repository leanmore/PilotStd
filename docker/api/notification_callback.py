"""渠道回调端点（阶段 B2b-1）。

`POST /api/notification/callback/{channel}`：免鉴权（见 `docker/auth_state.py` 白名单注释），
安全边界＝`pilotstd.core.notification.callback_service` 的验签 + 幂等 + 服务端角色授权。

**对外可达地址 / TLS / 反代由部署配置**——代码内不硬编码任何地址（裁决 B2b-1）。
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from pilotstd.core.notification.callback_service import describe_outcome, handle_callback
from pilotstd.i18n import t

logger = logging.getLogger(__name__)
router = APIRouter()

# 支持的渠道（与能力声明一致：企微未启用）
SUPPORTED_CALLBACK_CHANNELS = ("telegram", "dingtalk", "feishu")


def _credentials_for(user_id: int, channel: str) -> dict[str, str]:
    """读取某用户某渠道的解密凭据（失败返回空字典 ⇒ 验签必然失败 ⇒ 401）。"""
    try:
        from pilotstd.core.config import get_db_path
        from pilotstd.core.db import Database
        from pilotstd.core.notification._credentials import CredentialHelper

        helper = CredentialHelper(Database(get_db_path()), str(get_db_path()))
        return helper.get_channel(user_id, channel) or {}
    except Exception:
        logger.warning(
            t("notification.callback.credential_read_failed").format(channel=channel),
            exc_info=True,
        )
        return {}


def _db() -> Any:
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    return Database(get_db_path())


@router.post("/api/notification/callback/{channel}")
async def notification_callback(channel: str, request: Request) -> JSONResponse:
    """接收渠道回调：验签 → 幂等 → 授权 → 执行（详见服务层 docstring）。"""
    if channel not in SUPPORTED_CALLBACK_CHANNELS:
        return JSONResponse(status_code=501, content={"ok": False})
    raw = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    outcome = handle_callback(_db(), channel, headers, raw, _credentials_for)
    logger.info(t("notification.callback.handled").format(detail=describe_outcome(outcome)))
    return JSONResponse(status_code=outcome.status, content=outcome.payload)
