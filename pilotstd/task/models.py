# pilotstd/task/models.py
# 任务数据模型

from dataclasses import dataclass
from enum import Enum


class TaskType(Enum):
    SCAN = "scan"
    QUERY = "query"
    DOWNLOAD = "download"
    ORGANIZE = "organize"
    EXPIRE = "expire"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskInfo:
    """任务信息（可序列化到 SQLite）。"""

    task_id: str = ""
    task_type: TaskType = TaskType.SCAN
    status: TaskStatus = TaskStatus.PENDING
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    created_at: str = ""
    updated_at: str = ""
    result_json: str = ""  # 批次结果摘要 JSON
    error_log: str = ""  # 错误汇总

    @property
    def progress_pct(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100
