"""通知批次上下文（通知聚合 B1 · E1）：让"**一次导入**"的多个阶段共用同一个批次键。

为什么需要它：需求① 原文是"大批量导入（查询/下载/规范化/存档）→ 汇总成 **1 条**通知；
**一次导入 = 一个批次**"。若每个阶段各自生成批次键，一次导入就会产生多条（每阶段一条），
不满足"1 条"；而把批次键**当成参数层层透传**要改动查询/下载/整理/归档四条调用链的每一层签名，
侵入面大且易漏。

做法：用 `contextvars`（**上下文隔离**，线程/异步任务各自独立，不会串批次）保存当前批次键：
- **导入入口**用 `with batch_scope("imp")` 包住整段流程 ⇒ 内部所有阶段**自动共用**同一个键；
- 各阶段的发送点调用 `ensure_batch_key("qry"/"dl"/"norm"/"arch")`：
  有上下文键就用它（⇒ 与同一次导入的其它阶段合并成一条），没有就按前缀生成一个
  （⇒ 退化为"一次操作 = 一个批次"，与接线前行为一致，**零行为变更**）。
"""

from __future__ import annotations

import contextlib
import contextvars
import uuid as _uuid
from collections.abc import Iterator

# 当前批次键；默认空串＝"没有外层导入上下文"
_batch_key: contextvars.ContextVar[str] = contextvars.ContextVar("pilotstd_notify_batch_key", default="")


def new_batch_key(prefix: str) -> str:
    """生成 `前缀-<uuid8>` 形式的批次键（够唯一且短，便于日志与人工排查）。"""
    return f"{prefix}-{_uuid.uuid4().hex[:8]}"


def current_batch_key() -> str:
    """读取当前上下文的批次键（空串表示不在导入上下文内）。"""
    return _batch_key.get()


def ensure_batch_key(prefix: str) -> str:
    """取当前批次键；**没有则在本次上下文里生成并记住**。

    记住的意义：同一阶段（如同一批归档）内的多次发送共用同一个键，
    这样聚合器的①批次键（`correlation_id × notify_event`）才会把它们收敛成一条。
    """
    key = _batch_key.get()
    if key:
        return key
    key = new_batch_key(prefix)
    _batch_key.set(key)
    return key


@contextlib.contextmanager
def batch_scope(prefix: str = "imp") -> Iterator[str]:
    """导入作用域：进入时生成一个批次键并压栈，退出时恢复（异常也恢复）。

    用法（导入入口）：`with batch_scope("imp") as batch_key: ... 查询 → 下载 → 规范化 → 存档 ...`
    ⇒ 该次导入的四阶段通知全部落在同一个批次键上，被聚合器收敛为**一条**。
    """
    token = _batch_key.set(new_batch_key(prefix))
    try:
        yield _batch_key.get()
    finally:
        _batch_key.reset(token)
