# 模块：pilotstd/core/context.py
"""请求级用户身份上下文 — ContextVar 传播，无需显式传参。

用法:
    from pilotstd.core.context import get_current_user_id, set_current_user_id

    token = set_current_user_id(42)
    try:
        uid = get_current_user_id()  # → 42
        ...
    finally:
        _current_user_id.reset(token)  # 防止异步泄漏
"""

from contextvars import ContextVar

_current_user_id: ContextVar[int | None] = ContextVar("current_user_id", default=None)


def get_current_user_id() -> int | None:
    """返回当前请求上下文的 user_id，未设置返回 None。"""
    return _current_user_id.get()


def set_current_user_id(user_id: int) -> ContextVar:
    """设置当前请求上下文的 user_id。

    调用者必须 try/finally reset(token)：
        token = set_current_user_id(uid)
        try:
            ...
        finally:
            _current_user_id.reset(token)
    """
    return _current_user_id.set(user_id)
