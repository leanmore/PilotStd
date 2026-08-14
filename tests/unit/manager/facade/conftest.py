"""manager/facade/ handler 共享 fixtures。"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_core():
    """mock ManagerCore — 覆盖 query/download 两个 handler 所需的服务。"""
    core = MagicMock()

    # ── QueryHandler 依赖 ──
    core.query_engine = MagicMock()
    core.query_engine.get_all_sites.return_value = ["ahbz", "std_gov"]
    core.query_engine.get_adapter.return_value = MagicMock()
    core.query_engine.get_site_cooldown.return_value = 1.5
    core.query_engine.is_query_running.return_value = False
    core.query_engine.get_overflow_count.return_value = 0
    core.query_engine.get_csres_status.return_value = {"is_active": True}
    core.query_engine.is_idle.return_value = True
    core.query_engine.set_pause_event.return_value = None
    core.query_engine.get_quota_info.return_value = {"used": 10, "total": 100}
    core.query_engine.plan_batch.return_value = [("ahbz", 5)]

    # ── DownloadHandler 依赖 ──
    core.download_engine = MagicMock()
    core.download_engine.download_batch.return_value = ([], None)
    core.download_engine.download_single.return_value = MagicMock()

    # ── 共享依赖 ──
    core.download_list = []
    core.expire_list = []
    core.pending_list = []
    core.queried_items = None  # None → fallback to parsed_results
    core.parsed_results = []
    core.query_results = []
    core.download_tasks = []

    core.notification_mgr = MagicMock()
    core.cache = MagicMock()
    core.cache.get.return_value = None
    core.cache.put.return_value = None

    core.pending_svc = MagicMock()
    core.pending_svc.resolve_pending.return_value = None
    core.pending_svc.resolve_pending_by_numbers.return_value = None
    core.pending_svc.get_pending_items.return_value = []
    core.pending_svc.increment_requery_count.return_value = 0
    core.pending_svc.is_requery_exhausted.return_value = False
    core.pending_svc.mark_manual_required.return_value = None
    core.pending_svc.get_requery_count.return_value = 0
    core.pending_svc.query_local_cache.return_value = []
    core.pending_svc.enqueue_download_wait.return_value = None
    core.pending_svc.get_due_downloads.return_value = []
    core.pending_svc.remove_download_queue.return_value = None

    core.scheduled_svc = MagicMock()
    core.scheduled_svc.query_by_numbers.return_value = ([], MagicMock())
    core.scheduled_svc.download_by_numbers.return_value = ([], MagicMock())

    core.db = MagicMock()
    core.db.get_adapter_stats_all.return_value = []

    return core
