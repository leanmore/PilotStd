"""按用户的渠道实例缓存（A-21 3b-4）。

从 `user_credentials` 构造渠道；system(0) 的投递 owner 由 manager 解析为所有 admin。
"""

from __future__ import annotations

import logging
from typing import Any, cast

from .channel_spec import CHANNEL_SPECS

logger = logging.getLogger(__name__)


def build_channels(host: Any, user_id: int) -> dict[str, Any]:
    """按 user_id 从 user_credentials 构造渠道实例（不写缓存）。"""
    # 渠道类延迟导入，避免 manager 与本模块循环依赖
    from .manager import _CHANNEL_CLASSES

    channels: dict[str, Any] = {}
    creds: dict[str, dict[str, str]] = {}
    if host._cred_helper:
        creds = host._cred_helper.get_all(user_id)
    for spec in CHANNEL_SPECS:
        try:
            # 凭证按 spec 声明的构造字段顺序取值；双形态渠道需任一形态齐全
            ch_cfg = creds.get(spec.name) or {}
            enabled = ch_cfg.get("enabled", True)
            if isinstance(enabled, str):
                enabled = enabled.lower() not in ("false", "0", "")
            if not enabled:
                continue
            args = tuple((ch_cfg.get(f) or "").strip() for f in spec.ctor)
            guards = tuple((ch_cfg.get(f) or "").strip() for f in spec.ctor_required)
            if not all(guards):
                continue
            forms = getattr(spec, "forms", ())
            if forms and not any(
                all((ch_cfg.get(field) or "").strip() for field in form.required)
                for form in forms
            ):
                continue
            channels[spec.name] = _CHANNEL_CLASSES[spec.name](*args)
        except Exception as e:
            logger.warning("notification channel init failed: %s: %s", spec.name, e)
    return channels


def channels_for(host: Any, user_id: int) -> dict[str, Any]:
    """返回该用户的渠道实例（按 user_id 缓存）。"""
    # 默认用户走 _channels，兼容既有测试直接替换该字典
    if user_id == host._user_id:
        return cast(dict[str, Any], host._channels)
    cached = host._channel_cache.get(user_id)
    if cached is not None:
        return cast(dict[str, Any], cached)
    built = host._build_channels(user_id)
    host._channel_cache[user_id] = built
    return cast(dict[str, Any], built)


def invalidate(host: Any, user_id: int) -> None:
    """凭证保存后清该用户缓存。"""
    if user_id == host._user_id:
        host._channels.clear()
        host._channels.update(build_channels(host, user_id))
    else:
        host._channel_cache.pop(user_id, None)


def admin_user_ids(host: Any) -> list[int]:
    """所有管理员 id；users 表不存在时回退默认用户（兼容旧库/测试）。"""
    # 真实空管理员列表 ⇒ 返回空（system 不发送）；仅旧库/测试缺表才回退
    try:
        rows = host._db.fetchall("SELECT id FROM users WHERE role='admin' AND id > 0 ORDER BY id")
    except Exception:
        logger.warning("users table unavailable; fallback to default user for system delivery")
        return [host._user_id]
    if not isinstance(rows, (list, tuple)):
        return [host._user_id]
    if not rows:
        exists = host._db.fetchone("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'")
        if not exists:
            return [host._user_id]
        return []
    return [int(r["id"]) for r in rows]
