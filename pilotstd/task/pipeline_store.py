# 模块：项目//流水线_脚本
# 流水线_表封装

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from pilotstd.core.db import Database


class PipelineRunStore:
    """管道运行追踪存储。"""

    def __init__(self, db: Database) -> None:
        self._db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """幂等建表（实际创建依赖迁移 v26，此处仅做防御）。"""
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL UNIQUE,
                current_step TEXT NOT NULL DEFAULT 'scan',
                status TEXT NOT NULL DEFAULT 'running',
                progress INTEGER DEFAULT 0,
                step_results TEXT DEFAULT '{}',
                error_message TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

    def _now(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def create(self, run_id: str | None = None) -> str:
        """创建一条新的管道运行记录，返回 run_id。"""
        run_id = run_id or str(uuid.uuid4())
        now = self._now()
        self._db.execute(
            "INSERT INTO pipeline_runs (run_id, current_step, status, progress, "
            "step_results, error_message, created_at, updated_at) "
            "VALUES (?, 'scan', 'running', 0, '{}', '', ?, ?)",
            (run_id, now, now),
        )
        return run_id

    def update_step(
        self,
        run_id: str,
        step: str,
        status: str = "completed",
        progress: int = 0,
        step_results: dict | None = None,
        error: str = "",
    ) -> None:
        """更新当前步骤、进度和结果。"""
        now = self._now()
        existing = self.get(run_id)
        merged = json.loads(existing["step_results"]) if existing and existing.get("step_results") else {}
        if step_results:
            merged[step] = step_results
        self._db.execute(
            "UPDATE pipeline_runs SET current_step=?, status=?, progress=?, "
            "step_results=?, error_message=?, updated_at=? WHERE run_id=?",
            (step, status, progress, json.dumps(merged, ensure_ascii=False), error, now, run_id),
        )

    def get(self, run_id: str) -> dict[str, Any] | None:  # type: ignore[return-value]
        """按 run_id 查询记录。"""
        return self._db.fetchone("SELECT * FROM pipeline_runs WHERE run_id=?", (run_id,))
