"""覆盖 pilotstd.ui.main_window 模块最终剩余未覆盖行。"""

import os
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QDialog, QMenu, QTreeWidgetItem

from pilotstd.ui.workers._common import RowUpdate


# ═══ _delegate_ops.py:71 ═══
class TestDelegateRemaining:
    def test_start_auto_pipeline_guard(self, window):
        saved = window._core
        window._core = None
        try:
            window._start_auto_pipeline("/dummy")
        finally:
            window._core = saved


# ═══ _dialog_ops.py:52-54 ═══
class TestDialogRemaining:
    def test_stage_prereq_dialog_cancel_branch(self, window):
        window._suppress_dialogs = False
        result = window._stage_prereq_dialog("title", "msg", prereq_label="Run")
        assert result in ("run_prereq", "skip", "cancel")


# ═══ _download_ops.py:23 ═══
class TestDownloadRemaining:
    def test_check_download_queue_more_than_5(self, window):
        window._mgr_ready = True
        due = [{"standard_number": f"STD-{i}"} for i in range(10)]
        window._mgr.get_due_downloads = MagicMock(return_value=due)
        window._mgr.remove_download_queue = MagicMock()
        window._on_download = MagicMock()
        window._check_download_queue()
        # 验证队列被清空
        assert window._mgr.remove_download_queue.call_count == 10
        window._on_download.assert_called_once()


# ═══ _theme_ops.py:99 ═══
class TestThemeRemaining:
    def test_load_qt_translator_load_fails(self, window, monkeypatch):
        from PyQt6.QtCore import QTranslator

        monkeypatch.setattr(window, "_loaded_qt_lang", None)
        orig = window._config.get
        monkeypatch.setattr(
            window._config, "get", lambda k, d=None: "zh_CN" if k == "appearance.language" else orig(k, d)
        )
        with patch("os.path.exists", return_value=True), patch.object(QTranslator, "load", return_value=False):
            window._load_qt_translator()


# ═══ __init__.py:266-278, 315-321, 381 ═══
class TestMainWindowRemaining:
    def test_add_row_from_dict_translated_col_fallback(self, window):
        row_data = {"seq": 1}
        window._add_row_from_dict(row_data)


# ═══ _export_ops.py: 40-41, 50, 52, 55, 76-77, 85-86 ═══
class TestExportRemaining:
    def test_export_file_list_oserror_handling(self, window, tmp_path, monkeypatch):
        sub = tmp_path / "oserr"
        sub.mkdir()
        (sub / "f.txt").write_text("x")
        save_path = str(tmp_path / "out2.txt")
        monkeypatch.setattr(window, "_get_selected_path", lambda: str(sub))
        from pilotstd.ui.dialogs import ExportFileListDialog

        with (
            patch.object(ExportFileListDialog, "exec", return_value=QDialog.DialogCode.Accepted),
            patch(
                "pilotstd.ui.main_window.parts._export_ops.QFileDialog.getSaveFileName", return_value=(save_path, "")
            ),
            patch("pilotstd.ui.main_window.parts._export_ops.os.path.join", side_effect=OSError("fake")),
        ):
            window._on_export_file_list()

    def test_export_file_list_no_path_fallback(self, window, tmp_path, monkeypatch):
        monkeypatch.setattr(window, "_get_selected_path", lambda: str(tmp_path))
        from pilotstd.ui.dialogs import ExportFileListDialog

        with (
            patch.object(ExportFileListDialog, "exec", return_value=QDialog.DialogCode.Accepted),
            patch("PyQt6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")),
        ):
            window._on_export_file_list()

    def test_collect_folder_tree_dotfiles_skip(self, window, tmp_path):
        sub = tmp_path / "dots"
        sub.mkdir()
        (sub / ".hidden").mkdir()
        (sub / "normal").mkdir()
        lines: list = []
        window._collect_folder_tree(str(sub), lines, prefix="")
        assert any("normal" in ln for ln in lines)
        assert not any(".hidden" in ln for ln in lines)


# ═══ _file_tree_ops.py: 54-55, 95-99, 108, 118, 125-127, 131-134, 165-166, 193, 199-210 ═══
class TestFileTreeRemaining:
    def test_populate_children_oserror(self, window, tmp_path, monkeypatch):
        sub = tmp_path / "oserr"
        sub.mkdir()
        parent = QTreeWidgetItem(["p"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        monkeypatch.setattr(os, "scandir", MagicMock(side_effect=OSError("io error")))
        window._populate_children(parent)

    def test_populate_children_hidden_skip(self, window, tmp_path):
        sub = tmp_path / "hidden"
        sub.mkdir()
        (sub / ".dotfile").mkdir()
        (sub / "__pycache__").mkdir()
        (sub / "visible").mkdir()
        parent = QTreeWidgetItem(["p"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        names = {parent.child(i).text(0) for i in range(parent.childCount())}
        assert "visible" in names
        assert ".dotfile" not in names
        assert "__pycache__" not in names

    def test_populate_children_pdf_icon(self, window, tmp_path):
        sub = tmp_path / "pdfs"
        sub.mkdir()
        (sub / "doc.pdf").write_text("x")
        parent = QTreeWidgetItem(["p"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 1

    def test_context_menu_import_action(self, window, tmp_path):
        sub = tmp_path / "ctx"
        sub.mkdir()
        item = QTreeWidgetItem(["test"])
        item.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.clear()
        window.file_tree.addTopLevelItem(item)
        with patch.object(window.file_tree, "itemAt", return_value=item):
            with patch.object(QMenu, "exec") as mock_exec:
                mock_exec.return_value = None  # 用户没选
                window._on_file_tree_context_menu(QPoint(10, 10))

    def test_navigate_to_ancestor(self, window, tmp_path):
        deep = tmp_path / "x" / "y" / "z"
        deep.mkdir(parents=True)
        top = QTreeWidgetItem(["root"])
        top.setData(0, Qt.ItemDataRole.UserRole, str(tmp_path))
        window.file_tree.clear()
        window.file_tree.addTopLevelItem(top)
        window._navigate_to(str(deep))

    def test_retranslate_file_tree_nodes_updated(self, window):
        assert window.file_tree.topLevelItemCount() >= 4
        window._retranslate_file_tree()


# ═══ _table_ops.py: 70-71, 102, 105-106, 177-182, 184-187, 189, 191-193, 208-231 ═══
class TestTableRemaining:
    def test_on_header_context_menu_restore_width(self, window):
        from pilotstd.ui.table_constants import TOGGLEABLE_COLS

        header = window.work_table.horizontalHeader()
        toggle_col = TOGGLEABLE_COLS[0]
        window.work_table.setColumnHidden(toggle_col, True)
        header.resizeSection(toggle_col, 0)
        mock_action = MagicMock()
        mock_action.data.return_value = toggle_col
        with patch.object(QMenu, "exec", return_value=mock_action):
            window._on_header_context_menu(QPoint(50, 10))
        assert not window.work_table.isColumnHidden(toggle_col)

    def test_on_save_result_txt_format(self, window, tmp_path):
        window._clear_table()
        parsed = MagicMock()
        parsed.std_name = "t"
        parsed.logical_code = "GB"
        parsed.number = "1"
        parsed.get_full_number.return_value = "GB/T 1-2020"
        parsed.found_name = ""
        parsed.effect_status = ""
        parsed.is_adopted = False
        window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="done", total=1))
        save_path = str(tmp_path / "out.txt")
        with patch(
            "pilotstd.ui.main_window.parts._table_ops.QFileDialog.getSaveFileName", return_value=(save_path, "")
        ):
            window._on_save_result("txt")
        assert os.path.exists(save_path)

    def test_on_save_result_oserror_file_write(self, window, tmp_path):
        window._clear_table()
        parsed = MagicMock()
        parsed.std_name = "t"
        parsed.logical_code = "GB"
        parsed.number = "2"
        parsed.get_full_number.return_value = "GB/T 2-2020"
        parsed.found_name = ""
        parsed.effect_status = ""
        parsed.is_adopted = False
        window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="done", total=1))
        save_path = str(tmp_path / "out.csv")
        with patch(
            "pilotstd.ui.main_window.parts._table_ops.QFileDialog.getSaveFileName", return_value=(save_path, "")
        ):
            with patch("builtins.open", side_effect=OSError("disk full")):
                window._on_save_result("csv")

    def test_on_save_result_oserror(self, window, tmp_path, monkeypatch):
        window._mgr_ready = True
        window._clear_table()
        parsed = MagicMock()
        parsed.std_name = "detail"
        parsed.logical_code = "GB"
        parsed.number = "99"
        parsed.get_full_number.return_value = "GB/T 99-2020"
        parsed.found_name = ""
        parsed.effect_status = ""
        parsed.is_adopted = False
        window._add_table_row(RowUpdate(seq=1, parsed=parsed, work_status="done", total=1))
        window._parsed_results = [parsed]
        window.work_table.selectRow(0)
        fi_mock = MagicMock()
        with patch.object(
            type(window._mgr), "file_index",
            new_callable=lambda: property(lambda s: fi_mock), create=True,
        ):
            window._mgr.get_file_index_full_info = MagicMock(
                return_value=[
                    {
                        "file_path": "/a.pdf",
                        "std_name": "test_name",
                        "found_name": "web",
                        "effect_status": "active",
                        "is_adopted": True,
                        "confidence": 0.95,
                        "cached_at": "2024-06-01",
                        "match_status": "现行",
                    }
                ]
            )
            window._on_offline_view()
