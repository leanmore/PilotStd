# pilotstd/ui/controllers/file_tree_mixin.py
# 文件树填充（Win11 风格） — 从 main_window.py 提取

import logging
import os

from PyQt6.QtCore import QDir, QStandardPaths, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QMenu,
    QTreeWidgetItem,
)

from ...i18n import _

logger = logging.getLogger(__name__)


class DriveEnumerator(QThread):
    """后台线程枚举驱动器，避免网络驱动器阻塞 UI 主线程。"""

    drives_ready = pyqtSignal(list)

    def run(self):
        """在后台线程中枚举驱动器，将结果通过信号发回主线程。"""
        drives = QDir.drives()
        result = []
        for d in drives:
            path = d.absolutePath()
            name = path.rstrip("/\\")
            result.append((name, path))
        self.drives_ready.emit(result)


class FileTreeMixin:
    """文件导航树相关方法。依赖 self.file_tree, self.style(), self._drive_items。"""

    # ── 快速访问 ─────────────────────────────────────────

    def _populate_quick_access(self):
        """构建 Win11 风格的文件浏览树：桌面、文档、下载、此电脑(含盘符)。
        驱动器枚举移至后台线程，避免网络驱动器阻塞 UI。"""
        self.file_tree.clear()
        self._drive_items: dict[str, QTreeWidgetItem] = {}

        # 桌面
        desktop_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DesktopLocation
        )
        item = self._make_item(_("desktop"), desktop_path)
        self.file_tree.addTopLevelItem(item)

        # 文档
        doc_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        item = self._make_item(_("documents"), doc_path)
        self.file_tree.addTopLevelItem(item)

        # 下载
        dl_path = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DownloadLocation
        )
        item = self._make_item(_("downloads"), dl_path)
        self.file_tree.addTopLevelItem(item)

        # 此电脑（先创建空节点，盘符由后台线程异步填充）
        self.this_pc = QTreeWidgetItem([_("this_pc")])
        self.this_pc.setData(0, Qt.ItemDataRole.UserRole, "")
        self.this_pc.setIcon(
            0, self.style().standardIcon(self.style().StandardPixmap.SP_DriveHDIcon)
        )
        self.file_tree.addTopLevelItem(self.this_pc)
        # 异步枚举驱动器
        self._drive_thread = DriveEnumerator()
        self._drive_thread.drives_ready.connect(self._on_drives_ready)
        self._drive_thread.start()

    def _on_drives_ready(self, drives):
        """驱动器枚举完成后填充此电脑子树。"""
        self.this_pc.takeChildren()
        for name, path in drives:
            item = self._make_drive_item(name, path)
            self.this_pc.addChild(item)
            self._drive_items[path] = item

    def _make_item(self, name: str, path: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setIcon(
            0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon)
        )
        if os.path.isdir(path):
            item.setChildIndicatorPolicy(
                QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator
            )
        return item

    def _make_drive_item(self, name: str, path: str) -> QTreeWidgetItem:
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setIcon(
            0, self.style().standardIcon(self.style().StandardPixmap.SP_DriveHDIcon)
        )
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    # ── 懒加载 ───────────────────────────────────────────

    def _populate_children(self, parent_item: QTreeWidgetItem):
        """懒加载：展开时填充子目录和文件。"""
        parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
        if not parent_path or not os.path.isdir(parent_path):
            return
        try:
            entries = sorted(
                os.scandir(parent_path), key=lambda e: (not e.is_dir(), e.name.lower())
            )
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            if entry.is_dir():
                child = self._make_item(entry.name, entry.path)
            else:
                child = QTreeWidgetItem([entry.name])
                child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                ext = os.path.splitext(entry.name)[1].lower()
                if ext == ".pdf":
                    child.setIcon(
                        0,
                        self.style().standardIcon(
                            self.style().StandardPixmap.SP_FileIcon
                        ),
                    )
                elif ext in (".doc", ".docx", ".txt"):
                    child.setIcon(
                        0,
                        self.style().standardIcon(
                            self.style().StandardPixmap.SP_FileDialogDetailedView
                        ),
                    )
                else:
                    child.setIcon(
                        0,
                        self.style().standardIcon(
                            self.style().StandardPixmap.SP_FileIcon
                        ),
                    )
                child.setChildIndicatorPolicy(
                    QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator
                )
            parent_item.addChild(child)

    def _on_tree_item_expanded(self, item: QTreeWidgetItem):
        """展开时懒加载子目录。"""
        if (
            item.childCount() == 1
            and item.child(0).data(0, Qt.ItemDataRole.UserRole) is None
        ):
            item.takeChildren()
        if item.childCount() == 0:
            self._populate_children(item)

    # ── 右键菜单 ─────────────────────────────────────────

    def _on_file_tree_context_menu(self, pos):
        """右键菜单：导入工作区。"""
        item = self.file_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            return
        menu = QMenu(self)
        import_action = menu.addAction(f"📂 {_('context_import')}")
        import_action.setToolTip(f"将 '{os.path.basename(path)}' 导入工作区并自动扫描")
        chosen = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
        if chosen == import_action:
            self.status_changed.emit(f"导入工作区: {path}")
            self._run_scan(path)

    # ── 导航 ─────────────────────────────────────────────

    def _navigate_to(self, path: str):
        """在文件树中定位到指定路径，必要时展开父节点。"""
        path = os.path.normpath(path)
        if not os.path.exists(path):
            return

        def _is_ancestor(ancestor: str, descendant: str) -> bool:
            if descendant == ancestor:
                return True
            ancestor = ancestor.rstrip(os.sep)
            return descendant.startswith(ancestor + os.sep)

        # 收集候选祖先：所有 topLevel 项 + 驱动器项
        ancestors: list[tuple[QTreeWidgetItem, str]] = []
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            item_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_path:
                item_path = os.path.normpath(str(item_path))
                if _is_ancestor(item_path, path):
                    ancestors.append((item, item_path))
        for drive_path, drive_item in getattr(self, "_drive_items", {}).items():
            drive_norm = os.path.normpath(str(drive_path))
            if _is_ancestor(drive_norm, path):
                ancestors.append((drive_item, drive_norm))

        if not ancestors:
            return
        ancestors.sort(key=lambda x: len(x[1]), reverse=True)
        current, current_path = ancestors[0]

        # 沿路径逐层展开、查找
        remaining = path[len(current_path) :].lstrip(os.sep)
        parts = remaining.split(os.sep) if remaining else []
        for part in parts:
            if current.childCount() == 0:
                self._populate_children(current)
                current.setExpanded(True)
            found = None
            for i in range(current.childCount()):
                if current.child(i).text(0) == part:
                    found = current.child(i)
                    break
            if found is None:
                return
            current = found

        self.file_tree.setCurrentItem(current)
        self.file_tree.scrollToItem(current)
