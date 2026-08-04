# tests/test_ui_core.py
"""MainWindowCore 单元测试 — Handler 初始化、属性存储、回调包装。"""

import threading
import unittest
from unittest.mock import MagicMock, patch

from pilotstd.ui.core._core import MainWindowCore


class TestMainWindowCoreInit(unittest.TestCase):
    """MainWindowCore.__init__ — 属性存储和 _init_all_handlers 调用"""

    def setUp(self):
        self.mgr = MagicMock()
        self.work_table = MagicMock()
        self.progress_cb = MagicMock()
        self.status_cb = MagicMock()
        self.parsed = []
        self.config = MagicMock()
        self.pause = threading.Event()
        self.parent = MagicMock()

    @patch.object(MainWindowCore, "_init_all_handlers")
    def test_stores_basic_attributes(self, _mock_init):
        core = MainWindowCore(
            mgr=self.mgr,
            work_table=self.work_table,
            progress_callback=self.progress_cb,
            status_callback=self.status_cb,
            parsed_results=self.parsed,
            config=self.config,
            pause_event=self.pause,
            parent_widget=self.parent,
        )
        self.assertIs(core._mgr, self.mgr)
        self.assertIs(core._work_table, self.work_table)
        self.assertIs(core._parsed_results, self.parsed)
        self.assertIs(core._config, self.config)
        self.assertIs(core._pause_event, self.pause)
        self.assertIs(core._parent, self.parent)
        self.assertIs(core._status_callback, self.status_cb)
        self.assertIs(core._progress_callback, self.progress_cb)

    @patch.object(MainWindowCore, "_init_all_handlers")
    def test_stores_all_callbacks(self, _mock_init):
        cb = MagicMock()
        core = MainWindowCore(
            mgr=self.mgr,
            work_table=self.work_table,
            progress_callback=self.progress_cb,
            status_callback=self.status_cb,
            parsed_results=self.parsed,
            config=self.config,
            pause_event=self.pause,
            parent_widget=self.parent,
            show_stage_dialog=cb,
            stage_prereq_dialog=cb,
            register_task=cb,
            project_mark_dirty=cb,
            suppress_dialogs=cb,
            add_table_row=cb,
            find_row_by_seq=cb,
            clear_table=cb,
            update_button_states=cb,
            stop_workers_cb=cb,
            on_auto_save_cb=cb,
            question_dlg=cb,
            reset_progress=cb,
            force_finish_progress=cb,
            on_raw_progress=cb,
            run_scan_cb=cb,
            run_query_cb=cb,
            get_selected_path_cb=cb,
            get_scan_source_root_cb=cb,
            get_unrecognized_files_cb=cb,
            clear_unrecognized_files_cb=cb,
            set_suppress_dialogs=cb,
            set_query_btn_enabled=cb,
            set_download_btn_enabled=cb,
            set_cancel_btn_enabled=cb,
            set_progress_format=cb,
            set_progress_bar_visible=cb,
            show_auto_error_style=cb,
            get_parsed_results_cb=cb,
            get_work_table_cb=cb,
            get_log_view_cb=cb,
            project=cb,
            add_row_from_dict_cb=cb,
            navigate_to_cb=cb,
            get_work_state_cb=cb,
            set_unrecognized_files_cb=cb,
        )
        self.assertIs(core._show_stage_dialog, cb)
        self.assertIs(core._stage_prereq_dialog, cb)
        self.assertIs(core._register_task, cb)
        self.assertIs(core._project_mark_dirty, cb)
        self.assertIs(core._add_table_row, cb)
        self.assertIs(core._find_row_by_seq, cb)
        self.assertIs(core._clear_table, cb)
        self.assertIs(core._update_button_states, cb)
        self.assertIs(core._stop_workers_cb, cb)
        self.assertIs(core._on_auto_save_cb, cb)
        self.assertIs(core._run_scan_cb, cb)
        self.assertIs(core._run_query_cb, cb)

    @patch.object(MainWindowCore, "_init_all_handlers")
    def test_suppress_dialogs_default_none(self, _mock_init):
        core = MainWindowCore(
            mgr=self.mgr,
            work_table=self.work_table,
            progress_callback=self.progress_cb,
            status_callback=self.status_cb,
            parsed_results=self.parsed,
            config=self.config,
            pause_event=self.pause,
            parent_widget=self.parent,
        )
        self.assertIsNone(core._suppress_dialogs)

    @patch.object(MainWindowCore, "_init_all_handlers")
    def test_get_unrecognized_files_cb_lambda_is_none(self, _mock_init):
        core = MainWindowCore(
            mgr=self.mgr,
            work_table=self.work_table,
            progress_callback=self.progress_cb,
            status_callback=self.status_cb,
            parsed_results=self.parsed,
            config=self.config,
            pause_event=self.pause,
            parent_widget=self.parent,
        )
        self.assertIsNone(core._get_unrecognized_files_cb)
        self.assertIsNone(core._clear_unrecognized_files_cb)


class TestInitAllHandlers(unittest.TestCase):
    """_init_all_handlers — 调用所有 _init_* 方法"""

    def setUp(self):
        self.mgr = MagicMock()
        self.work_table = MagicMock()
        self.progress_cb = MagicMock()
        self.status_cb = MagicMock()
        self.parsed = []
        self.config = MagicMock()
        self.pause = threading.Event()
        self.parent = MagicMock()

    def test_calls_all_init_methods(self):
        with (
            patch.object(MainWindowCore, "_init_scan") as m1,
            patch("pilotstd.ui.core._core.init_query_subsystem") as m2,
            patch.object(MainWindowCore, "_init_download") as m3,
            patch.object(MainWindowCore, "_init_archive") as m4,
            patch.object(MainWindowCore, "_init_auto") as m5,
            patch.object(MainWindowCore, "_init_announce") as m6,
            patch.object(MainWindowCore, "_init_cleanup") as m7,
            patch.object(MainWindowCore, "_init_persistence") as m8,
            patch.object(MainWindowCore, "_init_project") as m9,
        ):
            MainWindowCore(
                mgr=self.mgr,
                work_table=self.work_table,
                progress_callback=self.progress_cb,
                status_callback=self.status_cb,
                parsed_results=self.parsed,
                config=self.config,
                pause_event=self.pause,
                parent_widget=self.parent,
            )
        for name, m in [
            ("scan", m1),
            ("query", m2),
            ("download", m3),
            ("archive", m4),
            ("auto", m5),
            ("announce", m6),
            ("cleanup", m7),
            ("persistence", m8),
            ("project", m9),
        ]:
            m.assert_called_once(), f"_init_{name} 未被调用"


class TestInitIndividualHandlers(unittest.TestCase):
    """各 _init_* 方法单独测试"""

    def setUp(self):
        self.mgr = MagicMock()
        self.config = MagicMock()
        self.pause = threading.Event()
        self.parent = MagicMock()
        self.work_table = MagicMock()
        self.parsed = []
        self.status_cb = MagicMock()
        self.progress_cb = MagicMock()

    def _make_core(self, **overrides):
        kwargs = dict(
            mgr=self.mgr,
            work_table=self.work_table,
            progress_callback=self.progress_cb,
            status_callback=self.status_cb,
            parsed_results=self.parsed,
            config=self.config,
            pause_event=self.pause,
            parent_widget=self.parent,
            **overrides,
        )
        with patch.object(MainWindowCore, "_init_all_handlers"):
            return MainWindowCore(**kwargs)

    @patch("pilotstd.ui.core._core.ScanUIHandler")
    def test_init_scan(self, mock_handler_cls):
        core = self._make_core(get_unrecognized_files_cb=lambda: ["f1.pdf"], get_scan_source_root_cb=lambda: "/root")
        core._init_scan()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["mgr"], self.mgr)
        self.assertIs(call_kwargs["config"], self.config)
        self.assertEqual(call_kwargs["unrecognized_files"], ["f1.pdf"])
        self.assertEqual(call_kwargs["scan_source_root"], "/root")

    @patch("pilotstd.ui.core._core.ScanUIHandler")
    def test_init_scan_no_callbacks(self, mock_handler_cls):
        core = self._make_core()
        core._init_scan()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertEqual(call_kwargs["unrecognized_files"], [])
        self.assertEqual(call_kwargs["scan_source_root"], "")

    @patch("pilotstd.ui.core.handlers._query.QueryUIHandler")
    def test_init_query(self, mock_handler_cls):
        from pilotstd.ui.core._core_init_query import init_query_subsystem

        core = self._make_core()
        init_query_subsystem(core)
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["mgr"], self.mgr)
        self.assertIs(call_kwargs["config"], self.config)
        self.assertIsNotNone(call_kwargs.get("deps"))

    @patch("pilotstd.ui.core._core.DownloadUIHandler")
    def test_init_download(self, mock_handler_cls):
        core = self._make_core()
        core._init_download()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["mgr"], self.mgr)

    @patch("pilotstd.ui.core._core.ArchiveUIHandler")
    def test_init_archive(self, mock_handler_cls):
        core = self._make_core(run_scan_cb=lambda: None, run_query_cb=lambda: None, get_selected_path_cb=lambda: "/p")
        core._init_archive()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["mgr"], self.mgr)
        self.assertIs(call_kwargs["parsed_results"], self.parsed)

    @patch("pilotstd.ui.core._core.AutoUIHandler")
    def test_init_auto(self, mock_handler_cls):
        core = self._make_core()
        core.scan = MagicMock()
        core.query = MagicMock()
        core.download = MagicMock()
        core.archive = MagicMock()
        core._init_auto()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["scan_handler"], core.scan)
        self.assertIs(call_kwargs["query_handler"], core.query)

    @patch("pilotstd.ui.core._core.AnnounceUIHandler")
    def test_init_announce(self, mock_handler_cls):
        core = self._make_core()
        core._init_announce()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertIs(call_kwargs["mgr"], self.mgr)

    @patch("pilotstd.ui.core._core.CleanupHandler")
    @patch("pilotstd.ui.core._core.get_library_root")
    def test_init_cleanup(self, mock_get_root, mock_handler_cls):
        mock_get_root.return_value = "/lib"
        core = self._make_core(
            get_unrecognized_files_cb=lambda: ["f.pdf"],
            clear_unrecognized_files_cb=lambda: None,
            get_scan_source_root_cb=lambda: "/src",
        )
        core._init_cleanup()
        mock_handler_cls.assert_called_once()
        call_kwargs = mock_handler_cls.call_args[1]
        self.assertEqual(call_kwargs["get_library_root"](), "/lib")

    @patch("pilotstd.ui.core._core.PersistenceHandler")
    def test_init_persistence(self, mock_handler_cls):
        core = self._make_core()
        core._init_persistence()
        mock_handler_cls.assert_called_once_with(config=self.config)

    @patch("pilotstd.ui.core._core.ProjectHandler")
    def test_init_project(self, mock_handler_cls):
        fake_project = MagicMock()
        core = self._make_core(
            project=fake_project,
            add_row_from_dict_cb=lambda d: None,
            navigate_to_cb=lambda p: None,
            get_work_state_cb=lambda: {},
            set_unrecognized_files_cb=lambda f: None,
        )
        core._init_project()
        mock_handler_cls.assert_called_once()

    @patch("pilotstd.ui.core._core.PersistenceHandler")
    def test_init_persistence_stores_on_core(self, mock_handler_cls):
        mock_handler = MagicMock()
        mock_handler_cls.return_value = mock_handler
        core = self._make_core()
        core._init_persistence()
        self.assertIs(core.persistence, mock_handler)
