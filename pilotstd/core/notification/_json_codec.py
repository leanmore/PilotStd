# 模块：项目/核心//_脚本
"""通知字段的 JSON 编解码——非标量字段入库/出库的唯一通道。

## 为什么需要它（阶段 1b 引入）

`NotificationMessage` 自 1b 起含非标量字段 `task_context: dict`，而它的两个落库点
都是 **TEXT**：

- `notification_log.task_context`（迁移 63）
- `notification_queue.event_data`（JSON 文本里的一个键）

SQLite 无原生 JSON 类型，且**没有**"JSON1 扩展一定可用"的保证（旧库/精简构建未打包
`json_*` 函数）。故统一按"文本存 JSON、读写各一处转换"处理，把边界收敛到一个模块：

1. **往返保真**：`dumps` → `loads_dict` 后结构/类型/值全等（含嵌套、布尔、浮点、Unicode）；
2. **空值约定（显式，二选一后钉死）**：`{}`、`None`、空串、键缺失 —— **一律得到 `{}`，
   互不可区分**。选"统一为 `{}`"而非"用哨兵区分"的理由：`task_context` 的唯一消费方是
   dataclass 字段，其默认值本就是 `{}`；若引入哨兵（如 None 表示"缺键"），调用方就得写
   `if x is not None: fields["task_context"] = x` 之类的分支，而**收益为零**——需求侧不需要
   区分"没传上下文"与"上下文为空"。**该约定由契约测试钉死**，避免后人误以为能区分；
3. **非法输入**：非 dict（`"abc"` / `123` / `[1,2]` / `null`）、非法 JSON —— 一律回退 `{}`，绝不抛。

## 为什么是"回退"而不是"抛异常"

通知是**旁路链路**：`_manager_ops.log()` 的写入失败只记 warning、静默时段补发路径整段
包在 try/except 里。若此处抛异常，一条格式异常的任务上下文会**吃掉整条通知**（用户什么
都收不到），代价远大于"上下文丢一个字段"。故与 `_manager_ops.log()` 的静默失败、
`security_notifier` 的降级同口径：**宁可丢细节，不可丢通知**。
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["dumps", "loads_dict"]

# 空槽的统一表征：库里的 TEXT 列收到 "" 即视为"无上下文"。
_EMPTY_SLOT = ""


def dumps(value: Any) -> str:
    """把待入库的值转为 JSON 文本。

    - `None` / 空 dict → `""`（空槽；读回得到 `{}`，见模块 docstring 的空值约定）
    - dict / list / 标量 → `json.dumps(..., ensure_ascii=False)`（中文不转义，便于人工排查库内容）
    - 不可序列化的对象 → 记 warning 并返回 `""`（**不抛**）
    """
    if value is None:
        return _EMPTY_SLOT
    if isinstance(value, dict) and not value:
        return _EMPTY_SLOT  # 空上下文不值得写 "{}"，读回同样得到 {}
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        logger.warning("通知字段 JSON 序列化失败，已置空: %s", type(value).__name__)  # i18n-allow: 开发者日志（与 _manager_ops/渠道层的既有告警同口径，不进 i18n）
        return _EMPTY_SLOT


def loads_dict(raw: Any) -> dict[str, Any]:
    """把库中的值还原为 dict；**任何非 dict 结果都回退 `{}`**（空值约定见模块 docstring）。

    接受两种入参形态（覆盖两个落库点）：
    - `str`：TEXT 列 / 队列 JSON 里的字符串值（空串 = 空槽）；
    - `dict`：调用方已解析过（如队列 `event_data` 里未来若改存对象）——原样返回。

    其余类型（`None` / 数字 / 列表 / 非法 JSON / 非 dict 的合法 JSON）一律回退 `{}`。

    **注意**：本函数只保证"得到 dict"，不保证内容可信——调用方不得据此做安全判断。
    """
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError, ValueError):
        logger.warning("通知字段 JSON 反序列化失败，已回退空字典")  # i18n-allow: 开发者日志（同上）
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed
