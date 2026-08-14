"""conftest.py — AutoPipeline 测试专用 fixtures。"""

from unittest.mock import MagicMock

import pytest

from pilotstd.manager.facade._auto import AutoPipeline
from pilotstd.manager.facade._download import DownloadHandler
from pilotstd.manager.facade._organize import OrganizeHandler
from pilotstd.manager.facade._query import QueryHandler
from pilotstd.manager.facade._scan import ScanHandler


@pytest.fixture
def mock_core():
    """mock ManagerCore — 涵盖 cfg、download_list、last_skipped_dirs。"""
    core = MagicMock()
    core.cfg = MagicMock()
    core.cfg.get.return_value = True
    core.download_list = []
    core.last_skipped_dirs = []
    return core


@pytest.fixture
def mock_scan():
    sh = MagicMock(spec=ScanHandler)
    sh.scan_directory.return_value = []
    sh.scan_directory_stream.return_value = []
    return sh


@pytest.fixture
def mock_query():
    qh = MagicMock(spec=QueryHandler)
    qh.query.return_value = ([], MagicMock(found=0))
    return qh


@pytest.fixture
def mock_download():
    dh = MagicMock(spec=DownloadHandler)
    dh.download.return_value = ([], MagicMock(success=0))
    dh.download_stream.return_value = ([], MagicMock(success=0))
    return dh


@pytest.fixture
def mock_organize():
    oh = MagicMock(spec=OrganizeHandler)
    oh.archive_standards.return_value = {"moved": 0}
    oh.organize_skipped_dirs.return_value = {"moved": 0}
    oh.organize_fallback.return_value = {"moved": 0}
    return oh


@pytest.fixture
def pipeline(mock_core, mock_scan, mock_query, mock_download, mock_organize):
    return AutoPipeline(mock_core, mock_scan, mock_query, mock_download, mock_organize)
