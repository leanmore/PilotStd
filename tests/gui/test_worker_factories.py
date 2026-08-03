# tests/gui/test_worker_factories.py
"""Worker Factory 单元测试 — 纯 Python，不启动 QApplication。

QueryWorkerFactory + ArchiveWorkerFactory 的创建逻辑与信号连接验证。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pilotstd.ui.core.handlers.archive_worker_factory import (
    ArchiveCallbacks,
    ArchiveWorkerFactory,
)
from pilotstd.ui.core.handlers.query_worker_factory import QueryWorkerFactory


# ═══════════════════════════════════════════════════════════
# QueryWorkerFactory
# ═══════════════════════════════════════════════════════════


class TestQueryWorkerFactory:
    def test_connects_all_5_signals(self, monkeypatch):
        """create_query_worker 连接全部 5 个信号到 callbacks。"""
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.query_worker_factory.QueryWorker",
            lambda *a, **kw: mock_worker,
        )
        callbacks = MagicMock()
        factory = QueryWorkerFactory(mgr=MagicMock(), pause_event=MagicMock())

        result = factory.create_query_worker([], callbacks)

        mock_worker.result_ready.connect.assert_called_once_with(callbacks.on_result_ready)
        mock_worker.batch_ready.connect.assert_called_once_with(callbacks.on_batch_ready)
        mock_worker.progress.connect.assert_called_once_with(callbacks.on_progress)
        mock_worker.finished_signal.connect.assert_called_once_with(callbacks.on_finished)
        mock_worker.error.connect.assert_called_once_with(callbacks.on_error)

    def test_passes_constructor_args(self, monkeypatch):
        """QueryWorker 收到 mgr / parsed_list / pause_event / parent。"""
        MockQueryWorker = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.query_worker_factory.QueryWorker",
            MockQueryWorker,
        )
        mgr = MagicMock()
        pause = MagicMock()
        parent = MagicMock()
        parsed = [MagicMock(), MagicMock()]
        factory = QueryWorkerFactory(mgr=mgr, pause_event=pause, parent=parent)

        factory.create_query_worker(parsed, MagicMock())

        MockQueryWorker.assert_called_once_with(
            mgr, parsed, pause_event=pause, parent=parent
        )

    def test_returns_worker_not_started(self, monkeypatch):
        """返回 Worker 但不调用 start()。"""
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.query_worker_factory.QueryWorker",
            lambda *a, **kw: mock_worker,
        )
        factory = QueryWorkerFactory(mgr=MagicMock(), pause_event=MagicMock())

        result = factory.create_query_worker([], MagicMock())

        assert result is mock_worker
        mock_worker.start.assert_not_called()


# ═══════════════════════════════════════════════════════════
# ArchiveWorkerFactory
# ═══════════════════════════════════════════════════════════


class TestArchiveCallbacks:
    def test_stores_all_4_callbacks(self):
        cb = ArchiveCallbacks(
            on_batch_ready="br",
            on_progress="pr",
            on_error="er",
            on_finished="fn",
        )
        assert cb.on_batch_ready == "br"
        assert cb.on_progress == "pr"
        assert cb.on_error == "er"
        assert cb.on_finished == "fn"


class TestArchiveWorkerFactory:
    @pytest.fixture
    def factory(self):
        return ArchiveWorkerFactory(
            mgr=MagicMock(), config=MagicMock(), pause_event=MagicMock()
        )

    def test_create_normalize_worker_connects_4_signals(self, factory, monkeypatch):
        """NormalizeWorker 创建后连接 batch/progress/error/finished 4 信号。"""
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.archive_worker_factory.NormalizeWorker",
            lambda *a, **kw: mock_worker,
        )
        callbacks = ArchiveCallbacks(*[MagicMock() for _ in range(4)])

        result = factory.create_normalize_worker([], callbacks)

        mock_worker.batch_ready.connect.assert_called_once_with(callbacks.on_batch_ready)
        mock_worker.progress.connect.assert_called_once_with(callbacks.on_progress)
        mock_worker.error.connect.assert_called_once_with(callbacks.on_error)
        mock_worker.finished_signal.connect.assert_called_once_with(callbacks.on_finished)

    def test_normalize_worker_constructor_args(self, factory, monkeypatch):
        """NormalizeWorker 收到 mgr / parsed_list / pause_event / parent。"""
        MockNormalize = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.archive_worker_factory.NormalizeWorker",
            MockNormalize,
        )
        parsed = [MagicMock()]

        factory.create_normalize_worker(parsed, ArchiveCallbacks(*[MagicMock() for _ in range(4)]))

        MockNormalize.assert_called_once()
        kwargs = MockNormalize.call_args[1]
        assert kwargs["pause_event"] is factory._pause_event
        assert kwargs["parent"] is factory._parent

    def test_create_archive_worker_connects_4_signals(self, factory, monkeypatch):
        """ArchiveWorker 创建后同样连接 4 信号。"""
        mock_worker = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.archive_worker_factory.ArchiveWorker",
            lambda *a, **kw: mock_worker,
        )
        callbacks = ArchiveCallbacks(*[MagicMock() for _ in range(4)])

        result = factory.create_archive_worker(
            [], "/tmp/root", overwrite=True, callbacks=callbacks
        )

        mock_worker.batch_ready.connect.assert_called_once_with(callbacks.on_batch_ready)
        mock_worker.progress.connect.assert_called_once_with(callbacks.on_progress)
        mock_worker.error.connect.assert_called_once_with(callbacks.on_error)
        mock_worker.finished_signal.connect.assert_called_once_with(callbacks.on_finished)

    def test_archive_worker_constructor_args(self, factory, monkeypatch):
        """ArchiveWorker 收到 root_dir + overwrite + config 参数。"""
        MockArchive = MagicMock()
        monkeypatch.setattr(
            "pilotstd.ui.core.handlers.archive_worker_factory.ArchiveWorker",
            MockArchive,
        )
        parsed = [MagicMock()]

        factory.create_archive_worker(
            parsed, "/lib/std", overwrite=False,
            callbacks=ArchiveCallbacks(*[MagicMock() for _ in range(4)]),
        )

        MockArchive.assert_called_once()
        args = MockArchive.call_args[0]
        kwargs = MockArchive.call_args[1]
        assert args[2] == "/lib/std"
        assert kwargs["overwrite"] is False
        assert kwargs["config"] is factory._config
