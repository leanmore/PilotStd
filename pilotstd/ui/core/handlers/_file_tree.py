# pilotstd/ui/core/handlers/_file_tree.py
"""FileTreeHandler — 文件导航树，替代 FileTreeMixin。"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from PyQt6.QtCore import QDir, QStandardPaths, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QMenu, QTreeWidget, QTreeWidgetItem, QWidget

from ...i18n import _

logger = logging.getLogger(__name__)


class DriveEnumerator(QThread):
    """后台线程枚举驱动器，避免网络驱动器阻塞 UI 主线程。"""

    drives_ready = pyqtSignal(list)  # type: ignore[type-arg]

    def run(self) -> None:
        """在后台线程中枚举驱动器，将结果通过信号发回主线程。"""
        drives = QDir.drives()
        result = []
        for d in drives:
            path = d.absolutePath()
            name = path.rstrip("/\\")
            result.append((name, path))
        self.drives_ready.emit(result)


class FileTreeHandler:
    """文件导航树：快速访问、懒加载、右键菜单、路径定位。

    通过依赖注入替代多重继承，file_tree 作为方法参数传入，
    Handler 不持有控件引用，不发射 Qt 信号，通过 _status 回调与上层通信。
    """

    _MAX_VISIBLE_ITEMS = 500  # 单次展开最多展示条目数，超出截断避免 Qt 崩溃

    def __init__(
        self,
        config: Any,  # ConfigManager
        status_callback: Any,
        run_scan_callback: Any,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._run_scan = run_scan_callback
        self._parent = parent
        self._drive_items: dict[str, QTreeWidgetItem] = {}
        self._drive_thread: Optional[DriveEnumerator] = None
        self._this_pc: Optional[QTreeWidgetItem] = None

    # ── 快速访问 ─────────────────────────────────────────

    def populate_quick_access(self, file_tree: QTreeWidget) -> None:
        """构建 Win11 风格的文件浏览树：桌面、文档、下载、此电脑(含盘符)。"""
        file_tree.clear()
        self._drive_items.clear()

        # 桌面
        desktop_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
        item = self.make_item(file_tree, _("desktop"), desktop_path)
        file_tree.addTopLevelItem(item)

        # 文档
        doc_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
        item = self.make_item(file_tree, _("documents"), doc_path)
        file_tree.addTopLevelItem(item)

        # 下载
        dl_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        item = self.make_item(file_tree, _("downloads"), dl_path)
        file_tree.addTopLevelItem(item)

        # 此电脑（先创建空节点，盘符由后台线程异步填充）
        self._this_pc = QTreeWidgetItem([_("this_pc")])
        self._this_pc.setData(0, Qt.ItemDataRole.UserRole, "")
        self._this_pc.setIcon(0, file_tree.style().standardIcon(file_tree.style().StandardPixmap.SP_DriveHDIcon))
        file_tree.addTopLevelItem(self._this_pc)
        # 异步枚举驱动器
        self._drive_thread = DriveEnumerator()
        self._drive_thread.drives_ready.connect(lambda drives: self._on_drives_ready(file_tree, drives))
        self._drive_thread.start()

    def _on_drives_ready(self, file_tree: QTreeWidget, drives: list[Any]) -> None:
        """驱动器枚举完成后填充此电脑子树。"""
        if self._this_pc is None:
            return
        self._this_pc.takeChildren()
        for name, path in drives:
            item = self.make_drive_item(file_tree, name, path)
            self._this_pc.addChild(item)
            self._drive_items[path] = item

    def make_item(self, file_tree: QTreeWidget, name: str, path: str) -> QTreeWidgetItem:
        """创建文件夹树节点。"""
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setIcon(0, file_tree.style().standardIcon(file_tree.style().StandardPixmap.SP_DirIcon))
        if os.path.isdir(path):
            item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    def make_drive_item(self, file_tree: QTreeWidget, name: str, path: str) -> QTreeWidgetItem:
        """创建驱动器节点。"""
        item = QTreeWidgetItem([name])
        item.setData(0, Qt.ItemDataRole.UserRole, path)
        item.setIcon(0, file_tree.style().standardIcon(file_tree.style().StandardPixmap.SP_DriveHDIcon))
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
        return item

    # ── 懒加载 ───────────────────────────────────────────

    def populate_children(self, parent_item: QTreeWidgetItem) -> None:
        """懒加载：展开时填充子目录和文件。"""
        parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
        if not parent_path or not os.path.isdir(parent_path):
            return
        logger.info("展开文件树: %s", parent_path)
        try:
            entries = sorted(os.scandir(parent_path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            logger.warning("无权限访问目录: %s", parent_path)
            return
        except OSError as e:
            logger.warning("无法读取目录 %s: %s", parent_path, e)
            return

        total = len(entries)
        truncated = total > self._MAX_VISIBLE_ITEMS
        if truncated:
            logger.warning(
                "目录条目过多(%d)，截断至 %d: %s",
                total,
                self._MAX_VISIBLE_ITEMS,
                parent_path,
            )

        # 获取 file_tree 引用用于 style()
        tree_widget: Optional[QTreeWidget] = parent_item.treeWidget()
        added = 0
        for entry in entries[: self._MAX_VISIBLE_ITEMS]:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            try:
                if entry.is_dir():
                    if tree_widget:
                        child = self.make_item(tree_widget, entry.name, entry.path)
                    else:
                        child = QTreeWidgetItem([entry.name])
                        child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                        child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
                else:
                    child = QTreeWidgetItem([entry.name])
                    child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    ext = os.path.splitext(entry.name)[1].lower()
                    if tree_widget:
                        try:
                            sp_file = tree_widget.style().StandardPixmap.SP_FileIcon
                            sp_detailed = tree_widget.style().StandardPixmap.SP_FileDialogDetailedView
                            if ext == ".pdf":
                                child.setIcon(0, tree_widget.style().standardIcon(sp_file))
                            elif ext in (".doc", ".docx", ".txt"):
                                child.setIcon(0, tree_widget.style().standardIcon(sp_detailed))
                            else:
                                child.setIcon(0, tree_widget.style().standardIcon(sp_file))
                        except Exception:
                            pass  # 图标设置失败不阻塞树展开
                    child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
                parent_item.addChild(child)
                added += 1
            except OSError:
                pass  # 单个条目 stat 失败，跳过
            except Exception:
                logger.debug("跳过无法展示的条目: %s", entry.name)

        if truncated:
            hint = QTreeWidgetItem([f"... 还有 {total - added} 项，请使用搜索定位"])
            hint.setFlags(hint.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            parent_item.addChild(hint)

        logger.debug("文件树展开完成: %s, 展示 %d/%d 项", parent_path, added, total)

    def on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
        """展开时懒加载子目录。"""
        first_child = item.child(0)
        if item.childCount() == 1 and first_child is not None and first_child.data(0, Qt.ItemDataRole.UserRole) is None:
            item.takeChildren()
        if item.childCount() == 0:
            self.populate_children(item)

    # ── 右键菜单 ─────────────────────────────────────────

    def on_file_tree_context_menu(self, file_tree: QTreeWidget, pos: Any) -> None:
        """右键菜单：导入工作区。"""
        item = file_tree.itemAt(pos)
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not os.path.exists(path):
            return
        menu = QMenu(file_tree)
        import_action = menu.addAction(f"📂 {_('context_import')}")
        import_action.setToolTip(f"将 '{os.path.basename(path)}' 导入工作区并自动扫描")
        chosen = menu.exec(file_tree.viewport().mapToGlobal(pos))
        if chosen == import_action:
            self._status(f"导入工作区: {path}")
            self._run_scan(path)

    # ── 导航 ─────────────────────────────────────────────

    def navigate_to(self, file_tree: QTreeWidget, path: str) -> None:
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
        for i in range(file_tree.topLevelItemCount()):
            item = file_tree.topLevelItem(i)
            item_path = item.data(0, Qt.ItemDataRole.UserRole)
            if item_path:
                item_path = os.path.normpath(str(item_path))
                if _is_ancestor(item_path, path):
                    ancestors.append((item, item_path))
        for drive_path, drive_item in self._drive_items.items():
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
                self.populate_children(current)
                current.setExpanded(True)
            found: Optional[QTreeWidgetItem] = None
            for i in range(current.childCount()):
                child_i = current.child(i)
                if child_i is not None and child_i.text(0) == part:
                    found = current.child(i)
                    break
            if found is None:
                return
            current = found

        file_tree.setCurrentItem(current)
        file_tree.scrollToItem(current)
