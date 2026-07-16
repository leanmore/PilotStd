# tests/fixtures/manager_core_fixture.py
"""ManagerCore 最小化组装夹具 — 所有依赖用 MagicMock 替换，让 facade/ 方法可独立测试。"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def manager_core() -> MagicMock:
    """组装一个所有字段均已 mock 的 ManagerCore 容器。

    用法:
        def test_query_handler(manager_core):
            from pilotstd.manager.facade._query import QueryHandler
            handler = QueryHandler()
            result = handler.some_method(manager_core, ...)
    """
    core = MagicMock()

    # ── 配置与基础 ──
    core.cfg = MagicMock()
    core.cfg.get.return_value = None
    core.db = MagicMock()

    # ── 扫描与解析 ──
    core.parser = MagicMock()
    core.scanner = MagicMock()

    # ── 查询子系统 ──
    core.query_engine = MagicMock()
    core.cache = MagicMock()
    core.quota_tracker = MagicMock()
    core.adapter_manager = MagicMock()

    # ── 文件索引 ──
    core.file_index = MagicMock()

    # ── 下载子系统 ──
    core.download_engine = MagicMock()
    core.session_mgr = MagicMock()
    core.task_queue = MagicMock()
    core.router = MagicMock()
    core._file_watcher = None

    # ── 服务层 ──
    core.classifier = MagicMock()
    core.organizer_svc = MagicMock()
    core.announce_svc = MagicMock()
    core.pending_svc = MagicMock()
    core.scheduled_svc = MagicMock()

    # ── 其他服务 ──
    core.validity_checker = MagicMock()
    core.notification_mgr = MagicMock()
    core.pipeline_store = MagicMock()

    # ── 运行时状态 ──
    core.parsed_results = []
    core.queried_items = []
    core.query_results = []
    core.download_list = []
    core.expire_list = []
    core.pending_list = []
    core.download_tasks = []
    core.last_skipped_dirs = []

    return core
