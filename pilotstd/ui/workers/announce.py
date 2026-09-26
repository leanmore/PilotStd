# 项目//工作者/脚本—，从工作者脚本拆分
# 后台公告检查线程：三个公告适配器逐个抓取，逐条回调进度。
#
# 中断契约（技术债 #17a）：两个回调都是**检查点**——`announce_stream` 的循环由
# 回调驱动，若只"跳过发射"不抛异常，底层仍会把三个适配器全抓完，
# 线程必然拖到 `stop_worker_gracefully` 超时并进入保活（#17b 已接受的代价）。

import logging
from typing import Any

from PyQt6.QtCore import QThread, pyqtSignal

from ._common import WorkerAborted, check_stop, wait_pause_or_abort

logger = logging.getLogger(__name__)


class AnnounceWorker(QThread):
    """后台公告检查线程：分批抓取公告、解析标准、比对缓存、保存附件。"""

    progress = pyqtSignal(int, int, int)
    finished_signal = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, mgr: Any, since_date: Any = None, pause_event: Any = None, parent: Any = None) -> None:
        super().__init__(parent)
        self._mgr = mgr
        self._since_date = since_date
        self._stopped = False
        # 失败明细随信号携带给 UI；_error 保留最后一条错误文案（兼容既有调用方）
        self._error = ""
        self._failures: list[dict[str, Any]] = []
        self._total = 0
        self._matched = 0
        self._pause_event = pause_event

    def stop(self) -> None:
        """置停止标志：回调里的 check_stop 会在下一条公告处抛 WorkerAborted。"""
        self._stopped = True

    def run(self) -> None:
        """在线程中执行公告流式抓取，通过信号通知 UI 进度和错误。"""
        try:

            def on_progress(cur: int, total: int, matched: int) -> None:
                """更新进度计数并发射 progress 信号。"""
                check_stop(self)  # #17a：中止底层公告抓取流
                # 暂停等待带 200ms 切片：用户在暂停状态下取消时也能退出
                wait_pause_or_abort(self._pause_event, self)
                self._matched = matched
                self._total = total
                self.progress.emit(cur, total, matched)

            def on_adapter_done(std_type: Any, result: Any) -> None:
                """单个适配器完成时记录结果或错误。"""
                check_stop(self)  # #17a：适配器之间也设检查点（单适配器超时 15s 为最坏窗口）
                if result is None:
                    self._failures.append({"type": std_type, "error": "无响应"})
                elif "error" in result:
                    self._error = result["error"]
                    self._failures.append({"type": std_type, "error": result["error"]})

            self._mgr.announce_stream(
                since_date=self._since_date or "",
                on_progress=on_progress,
                on_adapter_done=on_adapter_done,
            )
        except WorkerAborted:
            # 停止不是错误：不发 error 信号（否则取消操作会在 UI 上弹一条假故障）
            logger.info("[AnnounceWorker] 收到停止请求，已在中止点退出")
        except Exception as e:
            self._error = str(e)
            self.error.emit(str(e))
        finally:
            # 任何路径（正常/异常/中止）都恰好发射一次，调用方据此收尾
            self.finished_signal.emit()
