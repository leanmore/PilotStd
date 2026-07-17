"""Extracted file dialog methods for MainWindow."""

from __future__ import annotations

import logging
import os

from PyQt6.QtWidgets import QFileDialog

logger = logging.getLogger("pilotstd.ui")


def _on_open_file(self) -> None:
    """打开文件对话框，选择文件后触发扫描。"""
    path, __ = QFileDialog.getOpenFileName(self, "选择文件", "", "标准文件 (*.pdf *.doc *.docx *.txt);;所有文件 (*)")
    if path:
        self._menu_selected_path = path
        self.status_changed.emit(f"已选择文件: {os.path.basename(path)}")
        logger.info("打开文件: %s", path)
        self._run_scan(path)


def _on_open_folder(self) -> None:
    """打开文件夹对话框，选择文件夹后触发扫描。"""
    last = self._config.get("appearance.last_import_path", "")
    path = self._pick_folder("选择文件夹", last)
    if path:
        self._menu_selected_path = path
        self._config.set("appearance.last_import_path", path)
        self._config.save()
        self.status_changed.emit(f"已选择文件夹: {path}")
        logger.info("打开文件夹: %s", path)
        self._run_scan(path)


def _on_select(self) -> None:
    """工具栏"选择"按钮：弹出文件夹选择对话框后触发扫描。"""
    last = self._config.get("appearance.last_import_path", "")
    path = self._pick_folder("选择文件夹", last)
    if path:
        self._menu_selected_path = path
        self._config.set("appearance.last_import_path", path)
        self._config.save()
        self.status_changed.emit(f"已选择: {path}")
        logger.info("选择: %s", path)
        self._run_scan(path)


def _pick_folder(self, title: str, start_dir: str = "") -> str:
    """弹出目录选择对话框，返回选中的路径。"""
    return QFileDialog.getExistingDirectory(None, title, start_dir)
