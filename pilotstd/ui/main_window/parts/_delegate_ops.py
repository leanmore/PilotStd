"""Extracted _core delegate methods for MainWindow — G-010 compliance."""

from __future__ import annotations

import logging

logger = logging.getLogger("pilotstd.ui")


# ── 基础守卫 ──


def _require_core(self) -> bool:
    """检查 _core 是否就绪，未就绪时记录警告并返回 False。"""
    if not hasattr(self, "_core") or self._core is None:
        logger.warning("_core 未就绪，已跳过操作")
        return False
    return True


# ──委托方法：将工具栏按钮操作转发到对应──


def _on_check_announcements(self) -> None:
    """代理 → AnnounceUIHandler。"""
    if not _require_core(self):
        return
    self._core.announce.on_check_announcements()


def _on_download(self) -> None:
    """代理 → DownloadUIHandler。"""
    if not _require_core(self):
        return
    self._core.download.on_download()


def _on_import_download(self) -> None:
    """代理 → DownloadUIHandler。"""
    if not _require_core(self):
        return
    self._core.download.on_import_download()


def _run_scan(self, root_path: str) -> None:
    """代理 → ScanUIHandler。"""
    if not _require_core(self):
        return
    self._core.scan.run_scan(root_path)


def _on_query(self) -> None:
    """代理 → QueryUIHandler。"""
    if not _require_core(self):
        return
    self._core.query.on_query()


def _on_save_to_folder(self) -> None:
    """代理 → ArchiveUIHandler。"""
    if not _require_core(self):
        return
    self._core.archive.on_save_to_folder()


def _on_normalize(self) -> None:
    """代理 → ArchiveUIHandler（规范化是归档的前置步骤）。"""
    if not _require_core(self):
        return
    self._core.archive.on_normalize()


def _start_auto_pipeline(self, source_dir: str) -> None:
    """代理 → AutoUIHandler。"""
    if not _require_core(self):
        return
    self._core.auto.start_auto_pipeline(source_dir)


def _on_cleanup_empty_dirs(self) -> None:
    """代理 → CleanupHandler。"""
    if not _require_core(self):
        return
    self._core.cleanup.on_cleanup_empty_dirs()


def _on_collect_unrecognized(self) -> None:
    """代理 → CleanupHandler。"""
    if not _require_core(self):
        return
    self._core.cleanup.on_collect_unrecognized()
