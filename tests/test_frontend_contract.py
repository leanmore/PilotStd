"""E 组契约：前端 interface 字段必须 ⊆ 对应后端 response_model。"""

from __future__ import annotations

import re
from pathlib import Path

from docker.api.backup import BackupCreateResponse, BackupListResponse
from docker.api.download import DownloadImportResponse
from docker.api.normalize import NormalizeResponse
from docker.api.scheduler import SchedulerStatusResponse
from docker.api.system import SystemResourcesResponse
from docker.api.tasks import TaskItem, TaskListResponse

ROOT = Path(__file__).resolve().parents[1]

# (TS 文件, interface 名, Pydantic model)
MAPPINGS = [
    ("web/src/api/system.ts", "SystemResourcesResponse", SystemResourcesResponse),
    ("web/src/api/scheduler.ts", "SchedulerStatusResponse", SchedulerStatusResponse),
    ("web/src/api/backup.ts", "BackupListResponse", BackupListResponse),
    ("web/src/api/backup.ts", "BackupCreateResponse", BackupCreateResponse),
    ("web/src/api/download.ts", "DownloadImportResponse", DownloadImportResponse),
    ("web/src/api/tasks.ts", "TaskItem", TaskItem),
    ("web/src/api/tasks.ts", "TaskListResponse", TaskListResponse),
    ("web/src/api/files.ts", "NormalizeResponse", NormalizeResponse),
]


def _ts_fields(path: str, name: str) -> set[str]:
    text = (ROOT / path).read_text(encoding="utf-8")
    match = re.search(
        rf"export interface {re.escape(name)} \{{(.*?)\n\}}",
        text,
        flags=re.DOTALL,
    )
    assert match, f"{path} 缺少 interface {name}"
    return set(re.findall(r"^\s*([A-Za-z_]\w*)\??:", match.group(1), flags=re.MULTILINE))


def test_frontend_interfaces_are_subset_of_backend_models():
    problems: list[str] = []
    for path, interface, model in MAPPINGS:
        ts = _ts_fields(path, interface)
        backend = set(model.model_fields)
        extra = ts - backend
        if extra:
            problems.append(f"{interface}: 前端多出 {sorted(extra)}")
    assert not problems, "\n".join(problems)
