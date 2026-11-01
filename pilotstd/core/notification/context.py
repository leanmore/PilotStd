"""通知事件上下文（A-21 第三步 3a）。

`scope` 决定通知归属：user=真实用户，admin=管理员手动触发，system=系统任务。
落库规则：user/admin 用真实 user_id；system 写 0（users 表不建 id=0）。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class NotificationContext:
    """事件级通知上下文；不作为全局状态使用。"""

    scope: Literal["user", "admin", "system"]
    user_id: int | None = None

    def __post_init__(self) -> None:
        # user/admin 必须带真实用户 id；system 不允许伪装成某个用户
        if self.scope in ("user", "admin") and self.user_id is None:
            raise ValueError(f"scope={self.scope} requires user_id")
        if self.scope == "system" and self.user_id is not None:
            raise ValueError("scope=system must not carry user_id")
        if self.user_id is not None and self.user_id <= 0:
            raise ValueError("user_id must be positive")

    @property
    def log_user_id(self) -> int:
        """落库使用的 user_id：system → 0。"""
        return self.user_id if self.user_id is not None else 0
