"""Extracted download/auto-run methods for MainWindow."""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import QMessageBox

from ....i18n import _

logger = logging.getLogger("pilotstd.ui")


def _check_download_queue(self) -> None:
    """检查下载等待队列中是否有到期的标准，弹窗询问是否立即下载。"""
    if not self._mgr_ready:
        return
    due = self._mgr.get_due_downloads()
    if not due:
        return
    nums = [d["standard_number"] for d in due[:5]]
    msg = _("download_queue_ready").format(len(due)) + "\n" + "\n".join(nums)
    if len(due) > 5:
        msg += f"\n... 等共 {len(due)} 条"
    msg += "\n" + _("download_queue_confirm")
    reply = QMessageBox.question(self, _("download_queue_title"), msg)
    if reply == QMessageBox.StandardButton.Yes:
        for d in due:
            self._mgr.remove_download_queue(d["standard_number"])
        self._on_download()


def _on_auto_run(self) -> None:
    """自动运行入口：获取当前选中路径后启动自动管线。"""
    if not self._mgr_ready:
        return
    path = self._get_selected_path()
    if not path:
        QMessageBox.information(self, _("title_hint"), _("import_hint"))
        return
    self._start_auto_pipeline(path)
