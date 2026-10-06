"""任务视角的三个数据类（阶段 2 · P4b）——**纯数据投影**，不碰数据库。

**字段来源（实测 `pilotstd/core/db/_migrate_v16_v49.py:168-191` 的 `task_queue`）**：
`task_id` / `task_type` / `status` / `total_items` / `completed_items` / `failed_items` /
`started_at` / `finished_at` / `created_at` / `updated_at` / `result_json` / `error_log`
（另有 `retry_count` / `max_retries` / `timeout_seconds` / `priority`）。

**为什么本模块不 import 任何 DB 模块**：读表发生在 `manager.py`（投影入口），
这里保持"纯数据 + 纯计算"⇒ 单测无需数据库、也不与迁移/表结构耦合（R-008 最小依赖）。

**为什么进度通知不是"又一条通知"**：同一个 Task 的进度应复用**同一个 `message_id`** 反复 edit
（见 `02-目标架构.md §2.3/§2.4`）；`TaskProgress.should_push` 就是这条链路的**节流闸**。
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ── 常量（口径集中，避免散落魔法值）───────────────────────────────────────────

# 任务**终局**状态集合：终局必须推送（进度节流对终局不生效）
TERMINAL_STATUSES: frozenset[str] = frozenset({"succeeded", "partial", "failed", "abandoned"})

# 进度推送阈值：百分比较上次推送**变化 ≥ 该值**才推（`02-目标架构.md §2.3` 的节流口径）
PROGRESS_PUSH_DELTA: int = 10


@dataclass
class Task:
    """任务实体：**投影自 `task_queue`**（权威状态源），这里的实例只是通知用的内存视图。

    不写状态：写 `task_queue` 仍由现有业务代码负责（避免双写/双源）。
    """

    task_id: str  # ← task_queue.task_id（唯一键）
    task_kind: str = ""  # ← task_type；值域见 mapping.TASK_KINDS（禁止自由新增）
    status: str = "pending"  # ← status：pending/running/succeeded/partial/failed/abandoned
    total: int = 0  # ← total_items
    completed: int = 0  # ← completed_items
    failed: int = 0  # ← failed_items
    started_at: str = ""  # ← started_at
    finished_at: str = ""  # ← finished_at
    notify_event: str = ""  # 派生：task_kind → 通知事件（由 mapping.project 决定，这里只承载）
    correlation_id: str = ""  # 派生：同一批次（见 derive_correlation_id）
    message_ids: dict[str, str] = field(default_factory=dict)  # 该任务已发出的通知（渠道 → message_id）

    @property
    def is_terminal(self) -> bool:
        """是否已到终局（终局通知不受进度节流约束）。"""
        return self.status in TERMINAL_STATUSES

    def derive_correlation_id(self) -> str:
        """派生成**批次键**：`{task_kind}:{started_at[:19]}`（与 `02-目标架构.md §2.3` 口径一致）。

        **`started_at` 为空时返回空串**——这是有意为之：批次键非空会让聚合器走**①批次路径**
        （整批收敛成一条），若任务尚未真正开始就派生出"看起来像批次"的键，会把不相干的通知并成一条。
        """
        if not self.started_at:
            return ""
        return f"{self.task_kind}:{self.started_at[:19]}"


@dataclass
class TaskItem:
    """任务内的单个条目（内存投影，**不落表**——明细已在 `result_json` / 各业务表内）。"""

    item_key: str  # 标准号 / 公告号 / 文件名 —— 业务主键
    label: str = ""  # 展示名（标准名称等）
    status: str = "pending"  # pending/running/succeeded/failed/skipped/abandoned
    error: str = ""
    attempts: int = 0
    detail_url: str = ""


@dataclass
class TaskProgress:
    """进度快照：驱动 `task_progress` 内容类型与"原地更新"节流。

    `last_pushed_percent` / `last_pushed_stage` 记录**上次推送时**的状态（由 `mark_pushed()` 更新），
    这样 `should_push` 才能在"无历史"（首推）、"跨阈值"、"换阶段"、"终局"四种情况下返回 True。
    """

    task_id: str
    current: int = 0
    total: int = 0
    stage: str = ""  # fetch / parse / download / archive / normalize
    eta_seconds: int = 0
    updated_at: str = ""
    is_terminal: bool = False
    last_pushed_percent: int | None = None  # None ＝尚未推送过（首推必推）
    last_pushed_stage: str = ""

    @property
    def percent(self) -> int:
        """完成百分比（0–100）；`total` 为 0 时返回 0，**不抛异常**（进度未知不等于错误）。"""
        if self.total <= 0:
            return 0
        value = int(self.current * 100 / self.total)
        return max(0, min(100, value))

    @property
    def should_push(self) -> bool:
        """是否该推送这条进度（节流闸）：首推 / 跨阈值 / 换阶段 / 终局 ⇒ True。"""
        if self.is_terminal:
            return True
        if self.last_pushed_percent is None:
            return True
        if self.stage != self.last_pushed_stage:
            return True
        return abs(self.percent - self.last_pushed_percent) >= PROGRESS_PUSH_DELTA

    def mark_pushed(self) -> None:
        """记录"本次已推送"，供下次 `should_push` 比较（调用方在真正投递成功后调用）。"""
        self.last_pushed_percent = self.percent
        self.last_pushed_stage = self.stage
