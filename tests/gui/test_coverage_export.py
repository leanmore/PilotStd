"""覆盖 _export_ops.py 未覆盖行。所有对话框 exec() 均 mock。"""

import os
from unittest.mock import MagicMock, patch

from PyQt6.QtWidgets import QDialog


class TestExportFileList:
    def test_export_file_list_no_selection(self, window, monkeypatch):
        monkeypatch.setattr(window, "_get_selected_path", lambda: "")
        from pilotstd.ui.dialogs import ExportFileListDialog

        with patch.object(ExportFileListDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            window._on_export_file_list()

    def test_export_file_list_ok(self, window, tmp_path, monkeypatch):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.pdf").write_text("x")
        (sub / "b.txt").write_text("y")
        save_path = str(tmp_path / "out.txt")
        monkeypatch.setattr(window, "_get_selected_path", lambda: str(sub))
        from pilotstd.ui.dialogs import ExportFileListDialog

        with (
            patch.object(ExportFileListDialog, "exec", return_value=QDialog.DialogCode.Accepted),
            patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(save_path, "")),
        ):
            window._on_export_file_list()
        assert os.path.exists(save_path)


class TestExportFolderTree:
    def test_export_folder_tree(self, window, tmp_path, monkeypatch):
        sub = tmp_path / "mydir"
        sub.mkdir()
        (sub / "readme.txt").write_text("hi")
        save_path = str(tmp_path / "tree.txt")
        monkeypatch.setattr(window, "_get_selected_path", lambda: str(sub))
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(save_path, "")):
            window._on_export_folder_tree()
        assert os.path.exists(save_path)

    def test_collect_folder_tree_max_depth(self, window):
        from pilotstd.ui.main_window.parts import _export_ops

        lines: list = []
        with patch.object(_export_ops, "_MAX_FOLDER_DEPTH", 2):
            window._collect_folder_tree("/", lines, prefix="", depth=3)
        assert any("超过最大深度" in ln for ln in lines)

    def test_collect_folder_tree_permission_error(self, window, monkeypatch):
        monkeypatch.setattr(os, "scandir", MagicMock(side_effect=PermissionError))
        lines: list = []
        window._collect_folder_tree("/dummy", lines, prefix="")
        assert len(lines) == 1


class TestExportDiag:
    def test_export_diag(self, window, tmp_path):
        save = str(tmp_path / "diag.log")
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=(save, "")):
            window._on_export_diag()
        assert os.path.exists(save)
        text = open(save, encoding="utf-8").read()
        assert "PilotStd" in text

    def test_export_diag_cancelled(self, window):
        with patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")):
            window._on_export_diag()
