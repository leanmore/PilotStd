"""覆盖 __init__.py 未覆盖行。"""
from unittest.mock import MagicMock, patch


class TestQuitApp:
    def test_quit_app_db_backup_fails(self, window, monkeypatch):
        monkeypatch.setattr(window, "_mgr_ready", True)
        monkeypatch.setattr(window._mgr.db, "backup", MagicMock(side_effect=Exception("db error")))
        monkeypatch.setattr(window._mgr, "shutdown", MagicMock())
        window._quit_app()

    def test_quit_app_shutdown_fails(self, window, monkeypatch):
        monkeypatch.setattr(window, "_mgr_ready", True)
        monkeypatch.setattr(window._mgr.db, "backup", MagicMock())
        monkeypatch.setattr(window._mgr, "shutdown", MagicMock(side_effect=Exception("shutdown error")))
        window._quit_app()


class TestRunAuto:
    def test_run_auto(self, window):
        with patch.object(window, "_start_auto_pipeline") as mock_start:
            window.run_auto("/test/dir")
            mock_start.assert_called_once_with("/test/dir")


class TestAutoSave:
    def test_on_auto_save_dirty(self, window, monkeypatch):
        monkeypatch.setattr(window, "_collect_state", lambda: {"k": "v"})
        monkeypatch.setattr(type(window._project), "current_path", property(lambda s: "/f.json"))
        monkeypatch.setattr(window._project, "save", MagicMock())
        monkeypatch.setattr(window._project, "_dirty", True)
        monkeypatch.setattr(window._mgr, "stop_watching", MagicMock())
        window._on_auto_save()
        window._project.save.assert_called_once()

    def test_on_auto_save_not_dirty(self, window, monkeypatch):
        monkeypatch.setattr(window._project, "save", MagicMock())
        monkeypatch.setattr(type(window._project), "current_path", property(lambda s: "/f.json"))
        monkeypatch.setattr(window._project, "_dirty", False)
        monkeypatch.setattr(window._mgr, "stop_watching", MagicMock())
        window._on_auto_save()
        window._project.save.assert_not_called()

    def test_on_atexit_save(self, window, monkeypatch):
        monkeypatch.setattr(window, "_collect_state", lambda: {"k": "v"})
        monkeypatch.setattr(window._project, "save", MagicMock())
        monkeypatch.setattr(type(window._project), "current_path", property(lambda s: "/f.json"))
        monkeypatch.setattr(window._project, "_dirty", True)
        window._on_atexit_save()
        window._project.save.assert_called_once()


class TestAddRowFromDict:
    def test_add_row_from_dict_translated_col(self, window):
        window._add_row_from_dict({"seq": 1, "standard_name": "test"})
