"""Extracted file tree methods for MainWindow."""

from __future__ import annotations

import logging
import os
from typing import Any

from PyQt6.QtCore import QStandardPaths, Qt
from PyQt6.QtWidgets import QMenu, QTreeWidgetItem

from ....i18n import _
from ...drive_enumerator import DriveEnumerator

logger = logging.getLogger("pilotstd.ui")

_MAX_VISIBLE_ITEMS = 500
_TREE_NODE_KEY = Qt.ItemDataRole.UserRole + 1  # 节点类型标记（用于 _retranslate_ui 纯文本更新）


# ── 快速访问填充 ──


def _populate_quick_access(self) -> None:
    """填充文件树快速访问节点：桌面、文档、下载、此电脑。"""
    self.file_tree.clear()
    self._drive_items: dict[str, QTreeWidgetItem] = {}
    desktop_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DesktopLocation)
    item = self._make_item(_("desktop"), desktop_path)
    item.setData(0, _TREE_NODE_KEY, "desktop")
    self.file_tree.addTopLevelItem(item)
    doc_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
    item = self._make_item(_("documents"), doc_path)
    item.setData(0, _TREE_NODE_KEY, "documents")
    self.file_tree.addTopLevelItem(item)
    dl_path = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
    item = self._make_item(_("downloads"), dl_path)
    item.setData(0, _TREE_NODE_KEY, "downloads")
    self.file_tree.addTopLevelItem(item)
    self.this_pc = QTreeWidgetItem([_("this_pc")])
    self.this_pc.setData(0, Qt.ItemDataRole.UserRole, "")
    self.this_pc.setData(0, _TREE_NODE_KEY, "this_pc")
    self.this_pc.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DriveHDIcon))
    self.file_tree.addTopLevelItem(self.this_pc)
    self._drive_thread = DriveEnumerator()
    self._drive_thread.drives_ready.connect(self._on_drives_ready)
    self._drive_thread.start()


# ── 磁盘驱动器就绪回调 ──


def _on_drives_ready(self, drives: list[Any]) -> None:
    """后台线程返回磁盘列表后，填充此电脑子节点。"""
    # 防御：树被 _retranslate_file_tree 重建后，旧线程回调可能操作无效对象
    if not hasattr(self, "this_pc") or self.this_pc is None:
        return
    try:
        _sip = __import__("PyQt6.sip", fromlist=["isdeleted"])
        if hasattr(_sip, "isdeleted") and _sip.isdeleted(self.this_pc):
            return
    except (ImportError, RuntimeError):
        pass
    self.this_pc.takeChildren()
    for name, path in drives:
        item = self._make_drive_item(name, path)
        self.this_pc.addChild(item)
        self._drive_items[path] = item


# ── 节点创建 ──


def _make_item(self, name: str, path: str) -> QTreeWidgetItem:
    """创建普通目录树节点（含文件夹图标和展开指示器）。"""
    item = QTreeWidgetItem([name])
    item.setData(0, Qt.ItemDataRole.UserRole, path)
    item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DirIcon))
    if os.path.isdir(path):
        item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
    return item


# ── 磁盘节点创建 ──


def _make_drive_item(self, name: str, path: str) -> QTreeWidgetItem:
    """创建磁盘驱动器树节点（含硬盘图标和展开指示器）。"""
    item = QTreeWidgetItem([name])
    item.setData(0, Qt.ItemDataRole.UserRole, path)
    item.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_DriveHDIcon))
    item.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.ShowIndicator)
    return item


# ── 子节点懒加载 ──


def _populate_children(self, parent_item: QTreeWidgetItem) -> None:
    """展开目录节点时懒加载子目录和文件列表。"""
    parent_path = parent_item.data(0, Qt.ItemDataRole.UserRole)
    if not parent_path or not os.path.isdir(parent_path):
        return
    logger.info("展开文件树: %s", parent_path)
    tree = parent_item.treeWidget()
    if tree:
        tree.setUpdatesEnabled(False)
    try:
        entries = sorted(os.scandir(parent_path), key=lambda e: (not e.is_dir(), e.name.lower()))
    except PermissionError:
        logger.warning("无权限访问目录: %s", parent_path)
        if tree:
            tree.setUpdatesEnabled(True)
        return
    except OSError as e:
        logger.warning("无法读取目录 %s: %s", parent_path, e)
        if tree:
            tree.setUpdatesEnabled(True)
        return
    total = len(entries)
    truncated = total > _MAX_VISIBLE_ITEMS
    if truncated:
        logger.warning("目录条目过多(%d)，截断至 %d: %s", total, _MAX_VISIBLE_ITEMS, parent_path)
    added = 0
    try:
        for entry in entries[:_MAX_VISIBLE_ITEMS]:
            if entry.name.startswith(".") or entry.name == "__pycache__":
                continue
            try:
                if entry.is_dir():
                    child = self._make_item(entry.name, entry.path)
                else:
                    child = QTreeWidgetItem([entry.name])
                    child.setData(0, Qt.ItemDataRole.UserRole, entry.path)
                    ext = os.path.splitext(entry.name)[1].lower()
                    try:
                        if ext == ".pdf":
                            child.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
                        elif ext in (".doc", ".docx", ".txt"):
                            child.setIcon(
                                0,
                                self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogDetailedView),
                            )
                        else:
                            child.setIcon(0, self.style().standardIcon(self.style().StandardPixmap.SP_FileIcon))
                    except Exception:
                        pass
                    child.setChildIndicatorPolicy(QTreeWidgetItem.ChildIndicatorPolicy.DontShowIndicator)
                parent_item.addChild(child)
                added += 1
            except OSError:
                pass
            except Exception:
                logger.debug("跳过无法展示的条目: %s", entry.name)
        if truncated:
            hint = QTreeWidgetItem([f"... 还有 {total - added} 项，请使用搜索定位"])
            hint.setFlags(hint.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            parent_item.addChild(hint)
    finally:
        if tree:
            tree.setUpdatesEnabled(True)
    logger.debug("文件树展开完成: %s, 展示 %d/%d 项", parent_path, added, total)


# ── 树节点展开事件 ──


def _on_tree_item_expanded(self, item: QTreeWidgetItem) -> None:
    """目录节点展开时触发懒加载。"""
    first_child = item.child(0)
    if item.childCount() == 1 and first_child is not None and first_child.data(0, Qt.ItemDataRole.UserRole) is None:
        item.takeChildren()
    if item.childCount() == 0:
        self._populate_children(item)


# ── 文件树右键菜单 ──


def _on_file_tree_context_menu(self, pos: Any) -> None:
    """文件树右键菜单：导入工作区选项。"""
    item = self.file_tree.itemAt(pos)
    if not item:
        return
    path = item.data(0, Qt.ItemDataRole.UserRole)
    if not path or not os.path.exists(path):
        return
    menu = QMenu(self)
    import_action = menu.addAction(f"\U0001f4c2 {_('context_import')}")
    import_action.setToolTip(f"将 '{os.path.basename(path)}' 导入工作区并自动扫描")
    chosen = menu.exec(self.file_tree.viewport().mapToGlobal(pos))
    if chosen == import_action:
        self.status_changed.emit(f"导入工作区: {path}")
        self._run_scan(path)


# ── 文件树导航跳转 ──


def _navigate_to(self, path: str) -> None:
    """根据路径在文件树中展开并定位到目标节点。"""
    path = os.path.normpath(path)
    if not os.path.exists(path):
        return

    def _is_ancestor(ancestor: str, descendant: str) -> bool:
        """判断 ancestor 是否为 descendant 的祖先目录。"""
        if descendant == ancestor:
            return True
        ancestor = ancestor.rstrip(os.sep)
        return descendant.startswith(ancestor + os.sep)

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
    remaining = path[len(current_path) :].lstrip(os.sep)
    parts = remaining.split(os.sep) if remaining else []
    for part in parts:
        if current.childCount() == 0:
            self._populate_children(current)
            current.setExpanded(True)
        found = None
        for i in range(current.childCount()):
            child_i = current.child(i)
            if child_i is not None and child_i.text(0) == part:
                found = current.child(i)
                break
        if found is None:
            return
        current = found
    self.file_tree.setCurrentItem(current)
    self.file_tree.scrollToItem(current)


# ── 文件树文本刷新（语言切换）──


def _retranslate_file_tree(self) -> None:
    """仅刷新文件树顶层节点文本，不重建树、不查注册表。"""
    _node_labels = {
        "desktop": _("desktop"),
        "documents": _("documents"),
        "downloads": _("downloads"),
        "this_pc": _("this_pc"),
    }
    for i in range(self.file_tree.topLevelItemCount()):
        item = self.file_tree.topLevelItem(i)
        node_type = item.data(0, _TREE_NODE_KEY)
        if node_type and node_type in _node_labels:
            item.setText(0, _node_labels[node_type])
