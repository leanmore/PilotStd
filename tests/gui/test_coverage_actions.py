"""覆盖 _actions_ops.py 未覆盖行。"""
import time as _time
from unittest.mock import MagicMock, patch
from PyQt6.QtWidgets import QMessageBox


class TestInitManager:
    def test_init_manager_already_done(self, window, monkeypatch):
        monkeypatch.setattr(window, "_mgr_ready", True)
        monkeypatch.setattr(window, "_mgr", MagicMock())
        window._init_manager()


class TestSwitchToStage:
    def test_switch_to_stage_not_ready(self, window):
        window._mgr_ready = False
        window._switch_to_stage("scan")

    def test_switch_to_stage_ready(self, window, monkeypatch):
        window._mgr_ready = True
        parsed_mock = MagicMock()
        parsed_mock.stage_status = "done"
        monkeypatch.setattr(window._mgr, "get_stage_queue", lambda s: [parsed_mock])
        window._switch_to_stage("scan")


class TestUpdateButtons:
    def test_update_button_states_not_ready(self, window):
        window._mgr_ready = False
        window._update_button_states()


class TestTaskCenter:
    def test_on_task_center_not_ready(self, window):
        window._mgr_ready = False
        window._on_task_center()


class TestUpdateFlow:
    def test_prompt_restart_no(self, window):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No), \
             patch("subprocess.Popen") as mock_popen:
            window._prompt_restart("/tmp/test.bat")
            mock_popen.assert_not_called()

    def test_confirm_update_available_no_newer(self, window):
        with patch("pilotstd.platform.updater.is_newer_version", return_value=False):
            result = window._confirm_update_available("v2.0", {"tag_name": "v1.0", "body": "x"})
            assert result is False

    def test_confirm_update_available_user_accepts(self, window):
        with patch("pilotstd.platform.updater.is_newer_version", return_value=True), \
             patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            result = window._confirm_update_available("v1.0", {"tag_name": "v2.0", "body": "new stuff"})
            assert result is True

    def test_download_update_file(self, window):
        with patch("pilotstd.ui.workers.update_download.UpdateDownloadWorker") as mock_w:
            window._download_update_file({"tag_name": "v2.0", "html_url": "x"})
            mock_w.assert_called_once()
            mock_w.return_value.start.assert_called_once()

    def test_prompt_restart_ok_button(self, window):
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Ok), \
             patch("subprocess.Popen") as mock_popen:
            window._prompt_restart("C:\\test.bat")
            mock_popen.assert_called_once()

    def test_on_check_update_throttled(self, window):
        window._last_check_time = 9999999999
        window._on_check_update()

    def test_on_check_update_api_none(self, window):
        window._last_check_time = 0
        with patch("pilotstd.platform.updater.check_latest_version", return_value=None):
            window._on_check_update()

    def test_on_check_update_exception(self, window):
        window._last_check_time = 0
        with patch("pilotstd.platform.updater.check_latest_version",
                   side_effect=ConnectionError("network down")):
            window._on_check_update()
        window._last_check_time = 0
        with patch("pilotstd.platform.updater.check_latest_version",
                   side_effect=ConnectionError("network down")):
            window._on_check_update()

