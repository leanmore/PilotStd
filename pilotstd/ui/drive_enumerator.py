# 模块：项目//_脚本
# 后台线程枚举驱动器，避免网络驱动器阻塞用户界面主线程（从__混入脚本提取）

from PyQt6.QtCore import QDir, QThread, pyqtSignal


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
