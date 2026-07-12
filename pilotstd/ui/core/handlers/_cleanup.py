# pilotstd/ui/core/handlers/_cleanup.py
"""CleanupHandler — 空文件夹清理 + 未识别文件收集，替代 CleanupMixin。"""

from __future__ import annotations

import logging
import os
import shutil
import stat as _stat
from typing import TYPE_CHECKING, Any, Callable

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QWidget

from ....core.file_utils import ensure_long_path, safe_move
from ....i18n import _

logger = logging.getLogger(__name__)


class CleanupHandler:
    """空文件夹清理 + 未识别文件收集。

    通过依赖注入替代 Mixin 继承，所有外部依赖通过构造参数传入。
    """

    def __init__(
        self,
        config: Any,
        status_callback: Callable[[str], None],
        question_dlg: Callable[[str, str], Any],
        get_library_root: Callable[[], str],
        get_unrecognized_files: Callable[[], list[str]],
        clear_unrecognized_files: Callable[[], None],
        get_scan_source_root: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        self._config = config
        self._status = status_callback
        self._question = question_dlg
        self._get_library_root = get_library_root
        self._get_unrecognized_files = get_unrecognized_files
        self._clear_unrecognized_files = clear_unrecognized_files
        self._get_scan_source_root = get_scan_source_root
        self._parent = parent

    # ── 只读属性确认 ─────────────────────────────────────────

    def ensure_clear_readonly(self) -> bool:
        """确认是否可以清除只读属性。首次运行时弹窗询问用户意愿并记忆。"""
        if not self._config.get("file.clear_readonly", True):
            return False
        # 首次询问
        if not self._config.get("file.clear_readonly_asked", False):
            reply = self._question(_("msg_readonly_title"), _("msg_readonly_prompt"))
            self._config.set("file.clear_readonly_asked", True)
            if reply == QMessageBox.StandardButton.No:
                self._config.set("file.clear_readonly", False)
                return False
        return True

    # ── 清理空文件夹 ─────────────────────────────────────────

    def scan_empty_dirs(self, path: str) -> tuple[list[str], list[str], str]:
        """扫描目录：返回 (完全空目录列表, 仅含过期文件夹目录列表, 过期文件夹名)。"""
        expire_folder = self._config.get("storage.expire_folder", "过期作废")
        empty_dirs: list[str] = []
        expire_only: list[str] = []

        for entry in sorted(os.scandir(path), key=lambda e: e.name):
            if not entry.is_dir():
                continue
            try:
                sub_items = list(os.scandir(entry.path))
            except OSError:
                continue
            if not sub_items:
                empty_dirs.append(entry.path)
            elif len(sub_items) == 1 and sub_items[0].is_dir() and sub_items[0].name == expire_folder:
                expire_only.append(entry.path)

        return empty_dirs, expire_only, expire_folder

    def confirm_empty_dirs_deletion(self, empty_dirs: list[str], expire_only: list[str]) -> bool:
        """弹窗确认删除：显示空目录数 + 仅含过期目录数。返回用户是否确认。"""
        total = len(empty_dirs) + len(expire_only)
        if total == 0:
            QMessageBox.information(self._parent, _("dialog_cleanup_title"), _("msg_cleanup_none"))
            return False

        reply = self._question(
            _("dialog_cleanup_title"),
            _("msg_cleanup_confirm").format(empty=len(empty_dirs), expire=len(expire_only)),
        )
        return reply == QMessageBox.StandardButton.Yes

    def delete_empty_dirs(self, empty_dirs: list[str], expire_only: list[str], expire_folder: str) -> int:
        """删除空目录 + 逐条确认删除仅含过期文件夹的目录。返回成功删除数。"""
        deleted = 0
        # 删除完全空的目录
        for d in empty_dirs:
            try:
                os.rmdir(d)
                deleted += 1
                logger.info("删除空目录: %s", d)
            except OSError as e:
                logger.error("删除空目录失败: %s: %s", d, e)

        # 对仅含过期文件夹的目录，逐个确认后 rmtree
        for d in expire_only:
            name = os.path.basename(d)
            reply2 = self._question(
                _("dialog_cleanup_title"),
                _("msg_cleanup_expire_only").format(name=name, expire=expire_folder),
            )
            if reply2 == QMessageBox.StandardButton.Yes:
                if self.ensure_clear_readonly():
                    for _root, _dirs, _files in os.walk(d, followlinks=False):
                        for _f in _files:
                            try:
                                os.chmod(os.path.join(_root, _f), _stat.S_IWRITE)
                            except OSError:
                                pass
                try:
                    shutil.rmtree(d, onerror=lambda _func, _path, _excinfo: None)
                    deleted += 1
                    logger.info("删除仅含过期目录的文件夹: %s", d)
                except OSError as e:
                    logger.error("删除失败: %s: %s", d, e)
                    QMessageBox.warning(
                        self._parent,
                        _("dialog_cleanup_title"),
                        f"删除失败: {name}\n{e}\n\n请检查是否有文件正在被其他程序占用。",
                    )

        QMessageBox.information(self._parent, _("dialog_cleanup_title"), _("msg_cleanup_done").format(count=deleted))
        return deleted

    def on_cleanup_empty_dirs(self) -> None:
        """清理空文件夹：选择目录 → 扫描 → 确认 → 删除 → 汇总。"""
        path = QFileDialog.getExistingDirectory(None, _("dialog_select_cleanup_dir"))
        if not path:
            return
        path = ensure_long_path(path)

        empty_dirs, expire_only, expire_folder = self.scan_empty_dirs(path)
        if not self.confirm_empty_dirs_deletion(empty_dirs, expire_only):
            return

        self.delete_empty_dirs(empty_dirs, expire_only, expire_folder)

    # ── 未识别文件处理 ───────────────────────────────────────

    def build_unrecognized_tree(self, root_dir: str) -> tuple[QTreeWidget, list[QTreeWidgetItem]]:
        """构建未识别文件列表树（含复选框），三列：文件名/源目录/目标目录。"""
        tree = QTreeWidget()
        tree.setHeaderLabels([_("header_file_name"), _("header_source_dir"), _("header_target_dir")])
        tree.setColumnWidth(0, 280)
        tree.setColumnWidth(1, 320)
        tree.setColumnWidth(2, 320)
        checkboxes: list[QTreeWidgetItem] = []
        scan_root = self._get_scan_source_root()
        for fpath in self._get_unrecognized_files():
            try:
                rel = os.path.relpath(fpath, scan_root)
            except ValueError:
                rel = os.path.basename(fpath)
            src_dir = os.path.dirname(fpath)
            tgt_dir = os.path.join(root_dir, os.path.dirname(rel))
            item = QTreeWidgetItem([os.path.basename(fpath), src_dir, tgt_dir])
            item.setCheckState(0, Qt.CheckState.Checked)
            item.setData(0, 1, fpath)
            tree.addTopLevelItem(item)
            checkboxes.append(item)
        return tree, checkboxes

    def collect_selected_files(self, checkboxes: list[QTreeWidgetItem]) -> list[tuple[str, str]]:
        """从勾选的树节点收集 (源路径, 相对路径)。"""
        selected: list[tuple[str, str]] = []
        scan_root = self._get_scan_source_root()
        for item in checkboxes:
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            src = item.data(0, 1)
            if not os.path.exists(src):
                continue
            try:
                rel = os.path.relpath(src, scan_root)
            except ValueError:
                rel = os.path.basename(src)
            selected.append((src, rel))
        return selected

    def move_unrecognized_files(self, selected: list[tuple[str, str]], parent: QDialog) -> int:
        """进度条 + 逐文件搬迁到标准库（保留源目录层级）。返回成功移动数。"""
        root_dir = self._get_library_root()
        progress = QProgressDialog(_("msg_collect_progress"), _("btn_cancel"), 0, len(selected), parent)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        moved = 0
        for i, (src, rel) in enumerate(selected):
            progress.setValue(i + 1)
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            dst = os.path.join(root_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                safe_move(src, dst, on_exists="skip")
                moved += 1
                logger.info("未识别文件已搬迁: %s", rel)
            except OSError as e:
                logger.error("搬迁失败: %s: %s", src, e)
        progress.close()
        return moved

    def on_collect_unrecognized(self) -> None:
        """未识别文件处理：列出扫描中解析失败的文件，用户勾选后搬迁。"""
        files = self._get_unrecognized_files()
        if not files:
            QMessageBox.information(self._parent, _("dialog_collect_unrecognized"), _("msg_collect_none"))
            return

        dlg = QDialog(self._parent)
        dlg.setWindowTitle(_("dialog_collect_unrecognized"))
        dlg.setMinimumSize(700, 400)
        layout = QVBoxLayout(dlg)

        info_label = QLabel(_("msg_collect_confirm").format(count=len(files)))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        root_dir = self._get_library_root()
        tree, checkboxes = self.build_unrecognized_tree(root_dir)
        layout.addWidget(tree)

        btn_layout = QHBoxLayout()
        btn_all = QPushButton(_("select_all"))
        btn_none = QPushButton(_("deselect_all"))
        btn_ok = QPushButton(_("btn_ok"))
        btn_cancel = QPushButton(_("btn_cancel"))
        btn_all.clicked.connect(lambda: [cb.setCheckState(0, Qt.CheckState.Checked) for cb in checkboxes])
        btn_none.clicked.connect(lambda: [cb.setCheckState(0, Qt.CheckState.Unchecked) for cb in checkboxes])
        btn_ok.clicked.connect(dlg.accept)
        btn_cancel.clicked.connect(dlg.reject)
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        selected = self.collect_selected_files(checkboxes)
        if not selected:
            self._clear_unrecognized_files()
            return

        moved = self.move_unrecognized_files(selected, dlg)

        self._clear_unrecognized_files()
        QMessageBox.information(
            self._parent,
            _("dialog_collect_unrecognized"),
            _("msg_collect_done").format(count=moved),
        )
