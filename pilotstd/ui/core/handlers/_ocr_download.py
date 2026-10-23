# 模块：Windows OCR 模型下载工作线程
"""后台下载模型，避免阻塞设置对话框。"""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class OcrModelDownloadWorker(QThread):
    """执行 wheel 下载/校验/解压，进度与结果通过 Qt 信号回到 UI 线程。"""

    progress = pyqtSignal(str)
    download_done = pyqtSignal(str)
    download_failed = pyqtSignal(str)

    def run(self) -> None:
        """在线程内下载/解压，异常转 failed 信号，不向 Qt 事件循环抛出。"""
        try:
            from pilotstd.announcement.ocr._model_manager import download_and_install

            target = download_and_install(progress=self.progress.emit)
            self.download_done.emit(str(target))
        except Exception as exc:  # 线程边界必须把异常转成信号，不能吞掉
            self.download_failed.emit(str(exc))
