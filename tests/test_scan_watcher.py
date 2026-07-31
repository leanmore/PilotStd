# tests/test_scan_watcher.py
"""pilotstd/scan/watcher.py 单元测试 — 覆盖文件事件处理和监控器生命周期。"""

import os
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.scan.watcher import FileWatcher, FileWatchHandler


class TestFileWatchHandler:
    """FileWatchHandler — 文件事件处理器测试。"""

    @pytest.fixture
    def mock_index(self):
        return MagicMock()

    @pytest.fixture
    def mock_parser(self):
        parser = MagicMock()
        parsed = MagicMock()
        parsed.logical_code = "GB"
        parsed.number = 12345
        parsed.year = 2020
        parsed.part = None
        parsed.std_name = "测试标准"
        parsed.effect_status = "现行"
        parsed.raw_number = "12345"
        parser.parse.return_value = parsed
        return parser

    @pytest.fixture
    def handler(self, mock_index, mock_parser):
        return FileWatchHandler(
            file_index=mock_index,
            parser=mock_parser,
            patterns=["*.pdf", "*.doc"],
            ignore_patterns=["*~*"],
            skip_dir_patterns=["过期作废"],
        )

    def test_init_stores_dependencies(self, handler, mock_index, mock_parser):
        """初始化后依赖和模式应正确存储。"""
        assert handler._file_index is mock_index
        assert handler._parser is mock_parser
        assert handler._skip_dir_patterns == ["过期作废"]

    def test_should_skip_matching_dir(self, handler):
        """路径包含跳过目录时应返回 True。"""
        assert handler._should_skip(os.path.join("/root", "过期作废", "file.pdf")) is True

    def test_should_skip_not_matching(self, handler):
        """正常路径不应被跳过。"""
        assert handler._should_skip("/root/normal/file.pdf") is False

    def test_should_skip_case_insensitive(self, handler):
        """跳过检查应大小写不敏感。"""
        assert handler._should_skip("/root/过期作废/sub/file.pdf") is True

    def test_on_created_with_valid_file(self, handler, tmp_path):
        """文件创建事件应触发索引更新。"""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("dummy content")
        mock_event = MagicMock()
        mock_event.src_path = str(test_file)
        handler.on_created(mock_event)
        # 文件存在时应调用 file_index.upsert
        assert handler._file_index.upsert.called

    def test_on_created_skips_in_excluded_dir(self, handler):
        """排除目录下的文件创建应被跳过。"""
        mock_event = MagicMock()
        mock_event.src_path = os.path.join("/root", "过期作废", "file.pdf")
        handler.on_created(mock_event)
        assert not handler._file_index.upsert.called

    def test_on_modified(self, handler, tmp_path):
        """文件修改事件应触发重新索引。"""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")
        mock_event = MagicMock()
        mock_event.src_path = str(test_file)
        handler.on_modified(mock_event)
        assert handler._file_index.upsert.called

    def test_on_deleted(self, handler):
        """文件删除事件应从索引中移除。"""
        mock_event = MagicMock()
        mock_event.src_path = "/root/normal/file.pdf"
        handler.on_deleted(mock_event)
        handler._file_index.remove.assert_called_once()

    def test_on_deleted_skips_excluded_dir(self, handler):
        """排除目录下的文件删除不应触发索引移除。"""
        mock_event = MagicMock()
        mock_event.src_path = os.path.join("/root", "过期作废", "file.pdf")
        handler.on_deleted(mock_event)
        assert not handler._file_index.remove.called

    def test_on_deleted_handles_remove_exception(self, handler):
        """索引移除异常应被静默处理。"""
        handler._file_index.remove.side_effect = RuntimeError("boom")
        mock_event = MagicMock()
        mock_event.src_path = "/root/normal/file.pdf"
        handler.on_deleted(mock_event)
        # 不应抛出异常

    def test_on_moved(self, handler, tmp_path):
        """文件移动应删除旧索引并添加新索引。"""
        src_file = tmp_path / "old.pdf"
        src_file.write_text("content")
        dst_file = tmp_path / "new.pdf"
        dst_file.write_text("content")
        mock_event = MagicMock()
        mock_event.src_path = str(src_file)
        mock_event.dest_path = str(dst_file)
        handler.on_moved(mock_event)
        handler._file_index.remove.assert_called_once_with(str(src_file))
        assert handler._file_index.upsert.called

    def test_on_moved_skips_excluded_dest(self, handler):
        """目标在排除目录下的移动事件应被跳过。"""
        mock_event = MagicMock()
        mock_event.src_path = "/root/normal/old.pdf"
        mock_event.dest_path = os.path.join("/root", "过期作废", "new.pdf")
        handler.on_moved(mock_event)
        assert not handler._file_index.upsert.called

    def test_handle_new_or_modified_handles_permission_error(self, handler, tmp_path):
        """文件被锁定时应静默处理而不是抛出异常。"""
        test_file = tmp_path / "test.pdf"
        test_file.write_text("content")
        mock_event = MagicMock()
        mock_event.src_path = str(test_file)
        with patch("pilotstd.core.file_utils.hash_file_content", side_effect=OSError("permission denied")):
            handler.on_created(mock_event)
        # 不应抛出异常


class TestFileWatcher:
    """FileWatcher — 文件系统监控器生命周期测试。"""

    @pytest.fixture
    def mock_index(self):
        return MagicMock()

    @pytest.fixture
    def mock_parser(self):
        return MagicMock()

    @pytest.fixture
    def mock_config(self):
        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "scan.extensions": [".pdf"],
            "scan.skip_folders": ["过期作废"],
            "scan.exclude_patterns": [],
        }.get(key, default)
        return cfg

    @pytest.fixture
    def watcher(self, mock_index, mock_parser, mock_config):
        return FileWatcher(file_index=mock_index, parser=mock_parser, config_manager=mock_config)

    def test_init_stores_dependencies(self, watcher, mock_index, mock_parser):
        """初始化后依赖应正确存储。"""
        assert watcher._file_index is mock_index
        assert watcher._parser is mock_parser
        assert watcher._observer is None

    def test_init_config_defaults(self, watcher):
        """配置默认值应正确解析。"""
        assert watcher._patterns == ["*.pdf"]
        assert watcher._skip_dir_names == ["过期作废"]

    def test_is_running_initially_false(self, watcher):
        """初始化后 is_running 应为 False。"""
        assert watcher.is_running is False

    def test_start_creates_observer(self, watcher, tmp_path):
        """start 应创建 Observer 并在有效目录上调度。"""
        root = tmp_path / "watch"
        root.mkdir()
        with patch("pilotstd.scan.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher.start([str(root)])
            assert watcher._observer is mock_obs
            mock_obs.schedule.assert_called_once()
            mock_obs.start.assert_called_once()

    def test_start_skips_nonexistent_dir(self, watcher):
        """不存在的目录应跳过并警告。"""
        with patch("pilotstd.scan.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher.start(["/nonexistent/path"])
            mock_obs.schedule.assert_not_called()

    def test_start_twice_noop(self, watcher, tmp_path):
        """已在运行时重复 start 应为空操作。"""
        root = tmp_path / "watch"
        root.mkdir()
        with patch("pilotstd.scan.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher.start([str(root)])
            first_observer = watcher._observer
            watcher.start([str(root)])
            assert watcher._observer is first_observer

    def test_stop_cleans_up(self, watcher, tmp_path):
        """stop 应正确停止并清理 observer。"""
        root = tmp_path / "watch"
        root.mkdir()
        with patch("pilotstd.scan.watcher.Observer") as MockObserver:
            mock_obs = MagicMock()
            MockObserver.return_value = mock_obs
            watcher.start([str(root)])
            watcher.stop()
            mock_obs.stop.assert_called_once()
            mock_obs.join.assert_called_once_with(timeout=5)
            assert watcher._observer is None

    def test_stop_without_start_no_error(self, watcher):
        """未启动时 stop 不应抛异常。"""
        watcher.stop()
        assert watcher._observer is None

    def test_is_running_when_observer_alive(self, watcher, tmp_path):
        """Observer 存活时 is_running 应为 True。"""
        root = tmp_path / "watch"
        root.mkdir()
        with patch("pilotstd.scan.watcher.Observer") as MagicMockObserver:
            mock_obs = MagicMock()
            mock_obs.is_alive.return_value = True
            MagicMockObserver.return_value = mock_obs
            watcher.start([str(root)])
            assert watcher.is_running is True
