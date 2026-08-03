"""AnnounceTaskRunner 测试 — ThreadPoolExecutor 任务调度。"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.announce.task_runner import AnnounceTaskRunner


@pytest.fixture
def mock_deps():
    persistence = MagicMock()
    crawler = MagicMock()
    notifier = MagicMock()
    return persistence, crawler, notifier


@pytest.fixture
def runner(mock_deps):
    persistence, crawler, notifier = mock_deps
    return AnnounceTaskRunner(persistence, crawler, notifier, max_workers=1)


class TestTrigger:
    def test_trigger_creates_task_and_submits(self, runner, mock_deps):
        persistence, crawler, notifier = mock_deps
        result = runner.trigger("gb")

        assert "task_id" in result
        assert result["status"] == "pending"
        persistence.create_task.assert_called_once_with(result["task_id"])

    def test_run_success(self, runner, mock_deps):
        persistence, crawler, notifier = mock_deps
        crawler.check_all.return_value = {
            "matched": 5, "updated": 2, "errors": []
        }
        runner._run("task_001", "gb")
        runner._executor.shutdown(wait=True)

        persistence.update_task.assert_any_call("task_001", "running", 10)
        persistence.update_task.assert_any_call("task_001", "success", 100)
        notifier.after_fetch.assert_called_once()

    def test_run_failed_crawler_errors(self, runner, mock_deps):
        persistence, crawler, notifier = mock_deps
        crawler.check_all.return_value = {
            "matched": 0, "updated": 0,
            "errors": [{"source": "samr_gb", "error": "timeout"}],
        }
        runner._run("task_002", "gb")
        runner._executor.shutdown(wait=True)

        statuses = [c[0][1] for c in persistence.update_task.call_args_list]
        assert "failed" in statuses

    def test_run_exception(self, runner, mock_deps):
        persistence, crawler, notifier = mock_deps
        crawler.check_all.side_effect = RuntimeError("引擎崩溃")
        runner._run("task_003", "")
        runner._executor.shutdown(wait=True)

        last_args = persistence.update_task.call_args_list[-1][0]
        assert last_args[1] == "failed"
        assert last_args[2] == 50
        assert "引擎崩溃" in last_args[3]
