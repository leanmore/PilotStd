"""API 层当前用户解析（多用户 P1）。

优先取请求上下文里的 user_id（`AuthMiddleware` 在每个请求里设置 ContextVar）；
没有上下文时（直接调用路由函数 / 单测未挂中间件）退回解析 JWT cookie 的 `sub`，
仍然得到真实用户，**不回落 system(0)**——否则多用户归属判据会被静默破坏。
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from pilotstd.core.context import get_current_user_id
from pilotstd.i18n import t


def resolve_user_id(request: Request) -> int:
    """返回当前请求的 user_id；无法确定时 401，绝不返回 0。"""
    uid = get_current_user_id()
    if uid:
        return int(uid)
    try:
        from ..auth import _resolve_identity

        _role, subject = _resolve_identity(request)
        return int(subject)
    except (TypeError, ValueError) as exc:  # cookie 缺失/解析失败
        raise HTTPException(401, t("auth.api.unauthorized")) from exc
