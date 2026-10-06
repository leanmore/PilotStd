"""任务视角的数据投影（阶段 2 · P4b）——`Task` / `TaskItem` / `TaskProgress`。

**定位**：本包只做**内存投影与通知编排**，权威状态源仍是既有 `task_queue` 表；
**不新建主表、不写任务状态**（写状态由现有业务代码负责）⇒ 避免双源/双写（见 `02-目标架构.md §2.3`）。

**与执行队列的分工（双 SSOT）**：
- `pilotstd/task/`＝**执行队列视角**（哪个任务在跑、调度与重试）；
- 本包＝**通知视角**（用户交办的是哪类事、该发哪条通知）；
  两者的桥接值域见 `pilotstd/core/notification/mapping.py::TASK_KINDS`（禁止自由新增取值）。
"""

from __future__ import annotations

from .manager import TaskManager
from .model import Task, TaskItem, TaskProgress

__all__ = ["Task", "TaskItem", "TaskManager", "TaskProgress"]
