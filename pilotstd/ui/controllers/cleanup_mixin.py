# pilotstd/ui/controllers/cleanup_mixin.py
# 空文件夹清理 + 未识别文件收集 — 从 main_window.py 提取

import logging
import os
import shutil
import stat as _stat

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

from ...core.file_utils import ensure_long_path, safe_move
from ...i18n import _

logger = logging.getLogger(__name__)


class CleanupMixin:
    """空文件夹清理 + 未识别文件收集。依赖 self._config, self._parsed_results,
    self._unrecognized_files, self._scan_source_root, self._get_library_root()。
    """

    # ── 只读属性确认 ─────────────────────────────────────────

    def _ensure_clear_readonly(self) -> bool:
        """确认是否可以清除只读属性。首次运行时弹窗询问用户意愿并记住。"""
        if not self._config.get("file.clear_readonly", True):
            return False
        # 首次询问
        if not self._config.get("file.clear_readonly_asked", False):
            reply = QMessageBox.question(
                self, _("msg_readonly_title"),
                _("msg_readonly_prompt"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self._config.set("file.clear_readonly_asked", True)
            if reply == QMessageBox.StandardButton.No:
                self._config.set("file.clear_readonly", False)
                return False
        return True

    # ── 清理空文件夹 ─────────────────────────────────────────

    def _on_cleanup_empty_dirs(self):
        """清理空文件夹：用户选择目录 → 扫描空目录和仅含过期文件的目录
        → 弹窗确认 → 删除 → 弹窗汇总。"""
        # 用户选择要清理的目录
        path = QFileDialog.getExistingDirectory(
            self, _("dialog_select_cleanup_dir"))
        if not path:
            return
        path = ensure_long_path(path)  # 长路径支持

        expire_folder = self._config.get("storage.expire_folder", "过期作废")
        empty_dirs = []     # 完全空的目录
        expire_only = []    # 仅含过期文件夹的目录

        # 扫描目录结构
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

        total = len(empty_dirs) + len(expire_only)
        if total == 0:
            QMessageBox.information(self, _("dialog_cleanup_title"),
                                    _("msg_cleanup_none"))
            return

        # 弹窗确认
        reply = QMessageBox.question(
            self, _("dialog_cleanup_title"),
            _("msg_cleanup_confirm").format(empty=len(empty_dirs), expire=len(expire_only)))
        if reply != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        # 删除完全空的目录
        for d in empty_dirs:
            try:
                os.rmdir(d)
                deleted += 1
                logger.info(f"删除空目录: {d}")
            except OSError as e:
                logger.error(f"删除空目录失败: {d}: {e}")

        # 对仅含过期文件夹的目录，逐个确认
        for d in expire_only:
            name = os.path.basename(d)
            reply2 = QMessageBox.question(
                self, _("dialog_cleanup_title"),
                _("msg_cleanup_expire_only").format(name=name, expire=expire_folder))
            if reply2 == QMessageBox.StandardButton.Yes:
                # 清除目录下所有文件的只读属性，防止 rmtree 因只读文件崩溃
                if self._ensure_clear_readonly():
                    for _root, _dirs, _files in os.walk(d):
                        for _f in _files:
                            try:
                                os.chmod(os.path.join(_root, _f), _stat.S_IWRITE)
                            except OSError:
                                pass
                try:
                    shutil.rmtree(d)
                    deleted += 1
                    logger.info(f"删除仅含过期目录的文件夹: {d}")
                except OSError as e:
                    logger.error(f"删除失败: {d}: {e}")
                    QMessageBox.warning(
                        self, _("dialog_cleanup_title"),
                        f"删除失败: {name}\n{e}\n\n请检查是否有文件正在被其他程序占用。")

        # 弹窗汇总
        QMessageBox.information(self, _("dialog_cleanup_title"),
                                _("msg_cleanup_done").format(count=deleted))

    # ── 未识别文件处理 ───────────────────────────────────────

    def _on_collect_unrecognized(self):
        """未识别文件处理：列出扫描中解析失败的文件，用户勾选后
        原封不动搬迁到 标准/未识别文件/，保留源目录层级结构。"""
        if not self._unrecognized_files:
            QMessageBox.information(self, _("dialog_collect_unrecognized"),
                                    _("msg_collect_none"))
            return

        # 弹出自定义对话框：用户勾选要搬迁的文件
        dlg = QDialog(self)
        dlg.setWindowTitle(_("dialog_collect_unrecognized"))
        dlg.setMinimumSize(700, 400)
        layout = QVBoxLayout(dlg)

        info_label = QLabel(_("msg_collect_confirm").format(count=len(self._unrecognized_files)))
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 文件列表（含复选框）
        tree = QTreeWidget()
        # 三列：文件名 | 原文件目录 | 处理后文档目录
        root_dir = self._get_library_root()
        tree.setHeaderLabels([_("header_file_name"), _("header_source_dir"), _("header_target_dir")])
        tree.setColumnWidth(0, 280)
        tree.setColumnWidth(1, 320)
        tree.setColumnWidth(2, 320)
        checkboxes = []
        for fpath in self._unrecognized_files:
            try:
                rel = os.path.relpath(fpath, self._scan_source_root)
            except ValueError:
                rel = os.path.basename(fpath)
            src_dir = os.path.dirname(fpath)
            tgt_dir = os.path.join(root_dir, os.path.dirname(rel))
            item = QTreeWidgetItem([os.path.basename(fpath), src_dir, tgt_dir])
            item.setCheckState(0, Qt.CheckState.Checked)  # 默认全选
            item.setData(0, 1, fpath)  # 存储完整源路径
            tree.addTopLevelItem(item)
            checkboxes.append(item)
        layout.addWidget(tree)

        # 按钮区：全选/取消/确定/关闭
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

        # 收集勾选的文件
        selected = []
        for item in checkboxes:
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            src = item.data(0, 1)
            if not os.path.exists(src):
                continue
            try:
                rel = os.path.relpath(src, self._scan_source_root)
            except ValueError:
                rel = os.path.basename(src)
            selected.append((src, rel))

        if not selected:
            self._unrecognized_files = []
            return

        # 进度条：原封不动镜像移动，保留源目录层级结构
        root_dir = self._get_library_root()
        progress = QProgressDialog(_("msg_collect_progress"), _("btn_cancel"), 0, len(selected), dlg)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        moved = 0
        for i, (src, rel) in enumerate(selected):
            progress.setValue(i + 1)
            QApplication.processEvents()  # 刷新 UI
            if progress.wasCanceled():
                break
            dst = os.path.join(root_dir, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                safe_move(src, dst, on_exists="skip")
                moved += 1
                logger.info(f"未识别文件已搬迁: {rel}")
            except OSError as e:
                logger.error(f"搬迁失败: {src}: {e}")
        progress.close()

        self._unrecognized_files = []
        QMessageBox.information(self, _("dialog_collect_unrecognized"),
                                _("msg_collect_done").format(count=moved))
