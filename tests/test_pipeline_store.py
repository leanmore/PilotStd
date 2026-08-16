# tests/test_pipeline_store.py — 管道运行 step_results 存储往返测试
"""验证 step_results 按步骤嵌套合并，且 files/results 数组可 JSON 还原。

对应任务进度恢复的后端改动：各步骤 update_step 补全 files/results，
前端通过 GET /api/tasks/runs/{run_id} 的 step_results（json.loads 后）重建详情。
"""

import json
import os
import sys

import pytest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.task.pipeline_store import PipelineRunStore


@pytest.fixture
def store(shared_db):
    shared_db.execute("DELETE FROM pipeline_runs")
    return PipelineRunStore(shared_db)


class TestPipelineStoreStepResults:
    def test_update_step_merges_nested_step_results(self, store):
        run_id = store.create()
        store.update_step(
            run_id, "scan", "completed", 20,
            step_results={"total": 3, "files": [{"name": "a.pdf", "standard_number": "GB/T 1"}]},
        )
        store.update_step(
            run_id, "query", "completed", 40,
            step_results={"found": 2, "downloadable": 1, "results": [{"standard_number": "GB/T 1"}]},
        )

        run = store.get(run_id)
        step_results = json.loads(run["step_results"])
        assert step_results["scan"]["files"] == [{"name": "a.pdf", "standard_number": "GB/T 1"}]
        assert step_results["scan"]["total"] == 3
        assert step_results["query"]["results"] == [{"standard_number": "GB/T 1"}]
        assert step_results["query"]["found"] == 2

    def test_step_results_archive_roundtrip(self, store):
        run_id = store.create()
        store.update_step(
            run_id, "archive", "completed", 100,
            step_results={"count": 1, "results": {"moved": 1}},
        )
        run = store.get(run_id)
        # 模拟 get_pipeline_run 的 json.loads 还原
        parsed = json.loads(run["step_results"] or "{}")
        assert parsed["archive"]["results"] == {"moved": 1}

    def test_default_step_results_is_empty_dict(self, store):
        run_id = store.create()
        run = store.get(run_id)
        parsed = json.loads(run["step_results"] or "{}")
        assert parsed == {}

    def test_update_step_overwrites_same_step(self, store):
        """同一步骤二次更新应覆盖而非追加。"""
        run_id = store.create()
        store.update_step(run_id, "scan", "running", 0, step_results={"count": 10})
        store.update_step(run_id, "scan", "completed", 20, step_results={"total": 3, "files": []})
        run = store.get(run_id)
        parsed = json.loads(run["step_results"])
        assert parsed["scan"] == {"total": 3, "files": []}
        assert "count" not in parsed["scan"]
