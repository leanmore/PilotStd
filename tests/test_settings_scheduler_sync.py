# tests/test_settings_scheduler_sync.py
"""PUT /api/settings 的定时任务重排契约（技术债 #20）。

背景：`auto_archive_retry`（收藏→下载链路唯一入口）此前不在重排列表里 —— 改配置
只落盘、不重排，必须重启容器才生效；设置页也没有该字段。修复后要求：
  1. 5 个定时任务全部进重排列表（与 docker/scheduler.py 的任务表一一对应）；
  2. 前端漏发某个键时，用**当前配置值**兜底，绝不把任务静默禁用或改点
     （收藏下载链被静默禁用 = 链路停摆）；
  3. GET /api/settings 的 `tasks` 必须把重排列表里每个任务的 enabled/cron **都读出来**：
     读侧漏键时前端只能显示组件默认值，保存时该默认值又被回写 → 用户改过的值
     被静默覆盖（与 2 同源的"读写不对称"缺陷）。
"""

from __future__ import annotations

import os
import sys
from typing import Any

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from docker.api.settings import (  # noqa: E402
    _SCHEDULED_JOBS,
    _sync_task_schedules,
    get_settings,
)

EXPECTED_JOBS = {
    "auto_scan",
    "auto_announce",
    "date_reminder",
    "auto_health_check",
    "auto_archive_retry",
}


class _FakeConfig:
    """最小 ConfigManager 替身：点分隔键的 get/set/save。"""

    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self._data = dict(initial or {})

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def save(self) -> None:
        pass


class _FakeMgr:
    def __init__(self, initial: dict[str, Any] | None = None) -> None:
        self.cfg = _FakeConfig(initial)


def _call(monkeypatch, data: dict, initial: dict[str, Any] | None = None) -> list[tuple[str, str, bool]]:
    """调 _sync_task_schedules，返回 update_job 的调用序列。"""
    calls: list[tuple[str, str, bool]] = []
    monkeypatch.setattr(
        "docker.api.settings.update_job",
        lambda job_id, cron, enabled: calls.append((job_id, cron, enabled)),
    )
    _sync_task_schedules(_FakeMgr(initial).cfg, data.get("tasks", {}))
    return calls


def test_scheduled_jobs_table_matches_scheduler():
    """设置侧任务表必须覆盖 scheduler 注册的全部任务（防止再次漏项）。"""
    from docker.scheduler import start_scheduler  # noqa: F401  （仅确认可导入）

    assert {job for job, _ in _SCHEDULED_JOBS} == EXPECTED_JOBS


def test_all_five_jobs_are_rescheduled(monkeypatch):
    """5 个任务必须全部进重排列表（#20：漏一个就是"改了不生效"）。"""
    calls = _call(
        monkeypatch,
        {
            "tasks": {
                "auto_scan_cron": "0 3 * * *",
                "auto_scan_enabled": False,
                "auto_announce_cron": "0 1 * * *",
                "auto_announce_enabled": False,
                "date_reminder_cron": "0 2 * * *",
                "date_reminder_enabled": False,
                "auto_health_check_cron": "0 * * * *",
                "auto_health_check_enabled": True,
                "auto_archive_retry_cron": "* * * * *",
                "auto_archive_retry_enabled": True,
            }
        },
    )

    assert {job for job, _, _ in calls} == EXPECTED_JOBS
    retry = next(c for c in calls if c[0] == "auto_archive_retry")
    assert retry == ("auto_archive_retry", "* * * * *", True), "改 cron 必须真的重排该任务"


def test_missing_keys_fall_back_to_current_config(monkeypatch):
    """前端漏发 auto_archive_retry_* 时，必须沿用当前配置（True / 0 4 * * *），不得静默禁用。"""
    calls = _call(
        monkeypatch,
        {"tasks": {"auto_scan_cron": "0 3 * * *", "auto_scan_enabled": False}},
        initial={
            "tasks.auto_archive_retry_enabled": True,
            "tasks.auto_archive_retry_cron": "0 4 * * *",
        },
    )

    retry = next(c for c in calls if c[0] == "auto_archive_retry")
    assert retry == ("auto_archive_retry", "0 4 * * *", True), "缺键时必须沿用配置值，而不是默认 False/0 0 * * *"


def test_health_check_keeps_default_true(monkeypatch):
    """健康检查缺省仍为启用（历史默认值），不被缺键逻辑改坏。"""
    calls = _call(monkeypatch, {"tasks": {}})

    health = next(c for c in calls if c[0] == "auto_health_check")
    assert health[2] is True, "auto_health_check 缺省应为启用"


def _settings_body(initial: dict[str, Any] | None = None) -> dict:
    """取 GET /api/settings 的返回体。

    `get_settings` 被 `@require_role("admin")` 包裹，且装饰器只在实参里找到真正的
    `Request` 时才校验角色 —— 本用例只测载荷形状，故直接取 `__wrapped__`，
    不伪造 request（避免测试绕过角色校验的错觉：真正的鉴权由 docker/auth.py 单测覆盖）。
    """
    inner = get_settings.__wrapped__  # type: ignore[attr-defined]
    return inner(None, _FakeMgr(initial))  # type: ignore[arg-type]


def test_get_settings_exposes_every_reschedulable_key():
    """读侧必须给出重排列表里每个任务的 enabled+cron（读写成对，否则保存即覆盖）。"""
    body = _settings_body()
    exposed = set(body["tasks"])

    expected: set[str] = set()
    for _job_id, cron_key in _SCHEDULED_JOBS:
        expected.add(cron_key)
        expected.add(cron_key.replace("_cron", "_enabled"))

    missing = expected - exposed
    assert not missing, f"GET /api/settings 缺少任务键（前端会显示默认值并回写覆盖）：{sorted(missing)}"


def test_get_settings_reports_stored_values_not_defaults():
    """存过的值必须原样读出——这是"设置页显示真实状态"的前提。"""
    body = _settings_body(
        {
            "tasks.auto_archive_retry_enabled": False,
            "tasks.auto_archive_retry_cron": "0 6 * * *",
        }
    )

    assert body["tasks"]["auto_archive_retry_enabled"] is False
    assert body["tasks"]["auto_archive_retry_cron"] == "0 6 * * *"
