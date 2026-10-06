"""任务视角的**投影入口**（阶段 2 · P4b-2）——**只读** `task_queue`，本批**不触发任何通知**。

硬约束（2026-10-05 用户裁定与审核关注点，勿越界）：
1. **只读**：本模块只从 `task_queue` **读**；任务状态的写入仍由现有业务代码负责
   （`pilotstd/task/queue.py::TaskQueue`）。本模块**不写库、不双写**（避免双源）。
2. **不触发通知**：本批只做投影；`task_progress` 维持 2026-10-02 裁决
   "**只加数据结构、不接通知**"。
   （旁注：`TaskProgress.should_push` 是**尚未接线**的节流闸——接线需先经裁定，勿顺手补上。）
3. **不碰聚合与策略**：不改 `aggregate_buffer._group_key`，不改 `notification_policy`（后者属阶段 4）。

性能约定（防 N+1，审核关注点①）：
- 列表一律走 `TaskQueue.get_all()`（**一次批量 `fetchall`**）；**禁止**在循环里逐条 `get(task_id)`；
- `limit` 的语义是"**任务运行条数**"——`task_queue` **一行＝一次任务运行**（`enqueue()` 时生成）
  ⇒ 100 行≈100 次运行，非"100 个标准"；默认 100 与既有口径一致（`get_all(limit=100)`、
  CLI 的 `list_all(limit=50)`）。**本模块自身不额外截断**：截断只来自调用方传入的 `limit`
  （如需全量，调用方显式传更大的 `limit`；本批不引入分页——R-008 最小实现）。

容错（审核关注点②）：
- `result_json` 是**历史 schema 不一的自由 JSON**，且本模块是它的**首个消费方**
  ⇒ `_loads_result_json()` 只**保底不解释**：空/非字符串/解析失败/非字典 **一律回退 `{}`、永不抛**。
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from .model import Task, TaskProgress

if TYPE_CHECKING:  # 只在类型检查时引入（运行时不依赖具体 DAO 实现，便于测试替身）
    from pilotstd.task.queue import TaskQueue

logger = logging.getLogger(__name__)

# 列表投影的默认条数（沿用既有 `get_all` 的默认口径；语义是"任务运行条数"）
DEFAULT_LIST_LIMIT = 100


def _loads_result_json(raw: Any) -> dict[str, Any]:
    """把 `task_queue.result_json` 解析成字典；**任何异常都回退 `{}`，永不抛**。

    为什么"只保底不解释"：该列由各业务写入、**历史 schema 不一致**（本轮调查实测：此前无任何消费方）
    ⇒ 投影层不猜业务语义；拿不到就返回空字典，缺字段由上层按默认值处理。
    为什么不复用 `core/notification/_json_codec.py`：那个 helper 的语义域是通知落库列
    （`actions`/`attachments`），跨包复用会把两个域的契约绑死。
    """
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        # 非法 JSON（含半截写入）——记 debug 即可：这是**数据质量问题**，不是运行故障。
        # 日志文案用 ASCII：G-047（Python 侧 i18n 硬编码）把"新增中文字面量"计为新违规，
        # 而这是给开发者看的诊断、不是用户可见文案 ⇒ 不进 i18n 资源。
        logger.debug("task_queue.result_json is not valid JSON; falling back to empty dict")
        return {}
    return data if isinstance(data, dict) else {}


def _enum_value(value: Any) -> str:
    """把枚举/字符串统一成字符串取值（`TaskInfo.task_type` 是 `TaskType` 枚举）。"""
    return str(getattr(value, "value", value) or "")


class TaskManager:
    """任务投影管理器：**只读** `TaskQueue`，产出通知视角的内存视图。

    用法（投影）：`TaskManager(mgr.task_queue).list_tasks()` ⇒ `list[Task]`。
    本类**不做**：入队/改状态/取消（那些仍走 `TaskQueue`），也**不发通知**（见模块 docstring 约束 2）。
    """

    def __init__(self, queue: "TaskQueue") -> None:
        """注入既有 DAO（**不新建连接、不新建表**）。"""
        self._queue = queue

    # ── 读（批量优先，防 N+1）──────────────────────────────────────────────

    def list_tasks(self, limit: int = DEFAULT_LIST_LIMIT) -> list[Task]:
        """**一次批量读**最近的任务运行，投影为 `list[Task]`（按 `created_at` 倒序，由 DAO 保证）。

        `limit` 语义＝任务运行条数（见模块 docstring）；本方法不做额外截断，也不分页。
        """
        rows = self._queue.get_all(limit=limit)
        return [self._task_from_row(dict(row)) for row in rows]

    def get_task(self, task_id: str) -> Task | None:
        """单条读（进度场景）；不存在返回 `None`。

        与 `list_tasks` 的区别只是数据源形状：DAO 的 `get()` 返回 `TaskInfo` 数据类，
        `get_all()` 返回原始行字典 ⇒ 这里做一次形状归一。
        """
        info = self._queue.get(task_id)
        if info is None:
            return None
        return self._task_from_info(info)

    # ── 投影 ───────────────────────────────────────────────────────────────

    def progress_of(self, task: Task) -> TaskProgress:
        """由 `Task` 生成进度快照（`percent` / `should_push` 由 P4b-1 的数据类提供）。

        **注意**：本方法只产快照，**不投递**——`should_push` 的接线需先经裁定（见模块 docstring）。
        """
        return TaskProgress(
            task_id=task.task_id,
            current=task.completed,
            total=task.total,
            stage=task.task_kind,
            updated_at=task.finished_at or task.started_at,
            is_terminal=task.is_terminal,
        )

    @staticmethod
    def _task_from_row(row: dict[str, Any]) -> Task:
        """原始行字典 → `Task`（字段对应关系见 `_migrate_v16_v49.py` 的建表语句）。"""
        return Task(
            task_id=str(row.get("task_id") or ""),
            task_kind=_enum_value(row.get("task_type")),
            status=_enum_value(row.get("status")),
            total=int(row.get("total_items") or 0),
            completed=int(row.get("completed_items") or 0),
            failed=int(row.get("failed_items") or 0),
            started_at=str(row.get("started_at") or ""),
            finished_at=str(row.get("finished_at") or ""),
        )

    @staticmethod
    def _task_from_info(info: Any) -> Task:
        """`TaskInfo` 数据类 → `Task`（`get()` 的返回形状）。"""
        return Task(
            task_id=str(getattr(info, "task_id", "") or ""),
            task_kind=_enum_value(getattr(info, "task_type", "")),
            status=_enum_value(getattr(info, "status", "")),
            total=int(getattr(info, "total_items", 0) or 0),
            completed=int(getattr(info, "completed_items", 0) or 0),
            failed=int(getattr(info, "failed_items", 0) or 0),
            started_at=str(getattr(info, "started_at", "") or ""),
            finished_at=str(getattr(info, "finished_at", "") or ""),
        )

    @staticmethod
    def result_of(info_or_row: Any) -> dict[str, Any]:
        """便捷读取 `result_json`（防御式，永不抛）——供调用方按需取业务摘要。"""
        raw = getattr(info_or_row, "result_json", None)
        if raw is None and isinstance(info_or_row, dict):
            raw = info_or_row.get("result_json")
        return _loads_result_json(raw)
