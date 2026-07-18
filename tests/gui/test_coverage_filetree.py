"""覆盖 _file_tree_ops.py 未覆盖行。"""

import os
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtWidgets import QTreeWidgetItem


class TestDrivesReady:
    def test_drives_ready_sip_deleted(self, window, monkeypatch):
        mock_sip = MagicMock()
        mock_sip.isdeleted.return_value = True
        monkeypatch.setattr("PyQt6.sip.isdeleted", mock_sip.isdeleted)
        monkeypatch.setattr("PyQt6.sip", mock_sip)
        with patch("builtins.__import__", return_value=mock_sip):
            window._on_drives_ready([("C:", "C:\\")])

    def test_drives_ready_no_this_pc(self, window, monkeypatch):
        monkeypatch.delattr(window, "this_pc", raising=False)
        window._on_drives_ready([])


class TestPopulateChildren:
    def test_normal(self, window, tmp_path):
        sub = tmp_path / "d"
        sub.mkdir()
        (sub / "f.txt").write_text("a")
        (sub / "inner").mkdir()
        parent = QTreeWidgetItem(["t"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 2

    def test_over_max(self, window, tmp_path):
        big = tmp_path / "big"
        big.mkdir()
        for i in range(501):
            (big / f"f_{i:04d}.txt").touch()
        parent = QTreeWidgetItem(["b"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(big))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 501
        assert "..." in parent.child(parent.childCount() - 1).text(0)

    def test_empty_dir(self, window, tmp_path):
        empty = tmp_path / "e"
        empty.mkdir()
        parent = QTreeWidgetItem(["e"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(empty))
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 0

    def test_invalid_path(self, window):
        parent = QTreeWidgetItem(["b"])
        parent.setData(0, Qt.ItemDataRole.UserRole, None)
        window.file_tree.addTopLevelItem(parent)
        window._populate_children(parent)
        assert parent.childCount() == 0

    def test_permission_error(self, window, tmp_path, monkeypatch):
        sub = tmp_path / "no"
        sub.mkdir()
        parent = QTreeWidgetItem(["n"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        monkeypatch.setattr(os, "scandir", MagicMock(side_effect=PermissionError))
        window._populate_children(parent)


class TestTreeItemExpanded:
    def test_with_fake_child(self, window):
        parent = QTreeWidgetItem(["p"])
        fake = QTreeWidgetItem(["..."])
        fake.setData(0, Qt.ItemDataRole.UserRole, None)
        parent.addChild(fake)
        window.file_tree.addTopLevelItem(parent)
        with patch.object(window, "_populate_children") as mock_pop:
            window._on_tree_item_expanded(parent)
        mock_pop.assert_called_once()

    def test_no_children(self, window, tmp_path):
        sub = tmp_path / "x"
        sub.mkdir()
        parent = QTreeWidgetItem(["x"])
        parent.setData(0, Qt.ItemDataRole.UserRole, str(sub))
        window.file_tree.addTopLevelItem(parent)
        with patch.object(window, "_populate_children") as mock_pop:
            window._on_tree_item_expanded(parent)
        mock_pop.assert_called_once()


class TestContextMenu:
    def test_no_item(self, window):
        window.file_tree.clear()
        with patch.object(window.file_tree, "itemAt", return_value=None):
            window._on_file_tree_context_menu(QPoint(10, 10))

    def test_path_not_exist(self, window):
        fake = MagicMock(spec=QTreeWidgetItem)
        fake.data.return_value = "/nonexistent"
        with patch.object(window.file_tree, "itemAt", return_value=fake):
            window._on_file_tree_context_menu(QPoint(10, 10))


class TestRetranslate:
    def test_retranslate(self, window):
        assert window.file_tree.topLevelItemCount() >= 4
        window._retranslate_file_tree()


class TestNavigate:
    def test_not_exist(self, window):
        window._navigate_to("/not/exist")

    def test_top_level(self, window):
        item = window.file_tree.topLevelItem(0)
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.exists(str(path)):
            window._navigate_to(str(path))
