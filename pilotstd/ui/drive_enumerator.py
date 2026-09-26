# 模块：项目//_脚本
# 后台线程枚举驱动器，避免网络驱动器阻塞用户界面主线程（从__混入脚本提取）

from PyQt6.QtCore import QDir, QThread, pyqtSignal

from .workers._common import WorkerAborted, check_stop


class DriveEnumerator(QThread):
    """后台线程枚举驱动器，避免网络驱动器阻塞 UI 主线程。"""

    drives_ready = pyqtSignal(list)  # type: ignore[type-arg]

    def run(self) -> None:
        """在后台线程中枚举驱动器，将结果通过信号发回主线程。

        技术债 #17a：网络盘（映射盘/断线盘）会让 `absolutePath()` 长时间阻塞，
        故逐个盘符之间设中断检查点；收到停止请求即放弃本次枚举（不发信号）。
        """
        drives = QDir.drives()
        result = []
        try:
            for d in drives:
                check_stop(self)
                path = d.absolutePath()
                name = path.rstrip("/\\")
                result.append((name, path))
        except WorkerAborted:
            return
        self.drives_ready.emit(result)
