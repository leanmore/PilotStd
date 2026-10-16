"""渠道回调端点（阶段 B2b-1；企微入站见 T-43）。

- `POST /api/notification/callback/{channel}`：免鉴权（见 `docker/auth_state.py` 白名单注释），
  安全边界＝`pilotstd.core.notification.callback_service` 的验签 + 幂等 + 服务端角色授权；
- `GET /api/notification/callback/wechat`：**企微 URL 验证**专用（企微在保存回调配置时会发一次
  GET，要求原样回显解密后的 `echostr` 明文，`Content-Type: text/plain`）。
  该路径是企微协议要求，与另外三家的 POST-only 形态不冲突（其它渠道无此路由）。

**对外可达地址 / TLS / 反代由部署配置**——代码内不硬编码任何地址（裁决 B2b-1）。
"""

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from pilotstd.core.notification._credentials import SYSTEM_DEFAULT_USER_ID
from pilotstd.core.notification.callback_service import (
    describe_outcome,
    handle_callback,
    verify_wechat_url,
)
from pilotstd.i18n import t

logger = logging.getLogger(__name__)
router = APIRouter()

# 支持的渠道（与能力声明一致；企微自 T-43 起启用）
SUPPORTED_CALLBACK_CHANNELS = ("telegram", "dingtalk", "feishu", "wechat")


def _credentials_for(user_id: int, channel: str = "") -> dict[str, str]:
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


def _wechat_credentials() -> dict[str, str]:
    """读企微**企业级**加解密凭据（`token`/`encoding_aes_key`/`corpid`）。

    企微回调是"一个企业一个应用一个回调地址"，故凭据不按回调内容区分，统一取
    **系统默认用户**（`SYSTEM_DEFAULT_USER_ID`）名下那份——与前端"通知配置"里
    企微应用形态保存的位置一致（同一次 `CredentialHelper` 读取，与另外三家同一取法）。
    """
    return _credentials_for(SYSTEM_DEFAULT_USER_ID, "wechat")


def _db() -> Any:
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    return Database(get_db_path())


@router.get("/api/notification/callback/wechat")
async def wechat_callback_verify(request: Request) -> PlainTextResponse:
    """企微 URL 验证：验签 → 解密 `echostr` → **回显明文**（失败 401，不回显任何内容）。

    企微把 `msg_signature`/`timestamp`/`nonce`/`echostr` 放在**查询串**，
    故此处把它们拼成服务层约定的 headers 形状（服务层不含 HTTP，不解析 URL）。
    """
    params = request.query_params
    headers = {
        "msg_signature": params.get("msg_signature", ""),
        "timestamp": params.get("timestamp", ""),
        "nonce": params.get("nonce", ""),
    }
    plain = verify_wechat_url(headers, params.get("echostr", ""), credentials=_wechat_credentials())
    if not plain:
        logger.warning(t("notification.callback.handled").format(detail="wechat url verification rejected"))
        return PlainTextResponse("", status_code=401, media_type="text/plain")
    logger.info(t("notification.callback.handled").format(detail="wechat url verification ok"))
    # 响应体必须**就是**解密后的明文（企微据此判定回调地址有效），不得包信封、不得加引号
    return PlainTextResponse(plain, media_type="text/plain")


@router.post("/api/notification/callback/{channel}")
async def notification_callback(channel: str, request: Request) -> Response:
    """接收渠道回调：验签 → 幂等 → 授权 → 执行（详见服务层 docstring）。

    企微的消息回调走同一入口：密文 XML 由服务层解密后进入**与另外三家相同的分发链路**，
    默认响应体是明文 `success`（企微要求的应答形态，不带信封）。
    """
    if channel not in SUPPORTED_CALLBACK_CHANNELS:
        return JSONResponse(status_code=501, content={"ok": False})
    raw = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    # 企微的 `msg_signature`/`timestamp`/`nonce` 在查询串里（不是请求头）⇒ 合并进 headers，
    # 使服务层的取值路径与另外三家统一（服务层只认"一个 key→value 映射"）。
    if channel == "wechat":
        for key in ("msg_signature", "timestamp", "nonce"):
            value = request.query_params.get(key)
            if value:
                headers[key] = value
    outcome = handle_callback(
        _db(),
        channel,
        headers,
        raw,
        _credentials_for,
        credentials=_wechat_credentials() if channel == "wechat" else None,
    )
    logger.info(t("notification.callback.handled").format(detail=describe_outcome(outcome)))
    # 企微成功时必须回**明文 `success`**（不带信封、不是 JSON）：企微按"响应体是否
    # 等于 success"判定受理，回 JSON 会被当成失败并触发重投；失败路径仍回 JSON 状态码。
    if channel == "wechat" and outcome.status == 200:
        return _wechat_success_response()
    return JSONResponse(status_code=outcome.status, content=outcome.payload)


def _wechat_success_response() -> PlainTextResponse:
    """企微消息回调的成功应答体（明文 `success`）。"""
    return PlainTextResponse("success", media_type="text/plain")
