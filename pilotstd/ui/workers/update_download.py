# 模块：pilotstd/ui/workers/update_download.py
"""UpdateDownloadWorker — 后台下载更新文件，通过信号通知进度。"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class UpdateDownloadWorker(QThread):
    """后台线程：下载更新文件 + 生成更新脚本。"""

    progress_msg = pyqtSignal(str)  # 状态栏消息
    download_ready = pyqtSignal(str)  # bat 脚本路径（成功）
    download_failed = pyqtSignal(str)  # 错误信息（失败）

    def __init__(self, release: dict[str, Any], parent: Any = None) -> None:
        super().__init__(parent)
        self._release = release

    def run(self) -> None:
        """在线程中下载更新文件、校验 SHA256、生成更新脚本。"""
        from pilotstd.platform.updater import download_update, extract_sha256_from_body, generate_update_script

        download_url = self._release["download_url"]
        filename = self._release["filename"]
        self.progress_msg.emit(f"正在下载 {filename} ...")

        dl_path = os.path.join(os.environ.get("TEMP", os.path.expanduser("~")), filename)
        sha256_expected = extract_sha256_from_body(self._release["body"])

        try:
            ok = download_update(download_url, dl_path, sha256_expected)
            if not ok:
                self.download_failed.emit("下载或校验失败")
                return
        except Exception as e:
            self.download_failed.emit(str(e))
            return

        exe_dir = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(__file__)
        if not os.access(exe_dir, os.W_OK):
            self.download_failed.emit(f"无法写入 {exe_dir}\n请以管理员身份运行")
            return

        bat_path = generate_update_script(dl_path, exe_dir)
        self.download_ready.emit(bat_path)
