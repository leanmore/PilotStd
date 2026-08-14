"""mirror.py + _organize.py 共享 fixture。"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_cfg():
    """mock config 实例，clear_readonly 默认开启。"""
    cfg = MagicMock()
    cfg.get.return_value = True
    return cfg


@pytest.fixture
def mock_core():
    """mock ManagerCore 实例，供 OrganizeHandler 使用。"""
    core = MagicMock()
    core.db = MagicMock()
    core.db.fetchone = MagicMock(return_value=None)
    core.organizer_svc = MagicMock()
    core.organizer_svc.organize.return_value = {
        "moved": 1, "failed": 0, "skipped_exists": 0,
        "word_mirrored": 0, "skipped_source": 0, "dedup_skipped": 0,
        "details": [],
    }
    core.organizer_svc._dedup_standard = MagicMock()
    core.validity_checker = MagicMock()
    core.notification_mgr = MagicMock()
    core.pending_list = []
    core.parser = MagicMock()
    core.parsed_results = []
    return core
