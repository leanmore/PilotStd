# 模块：项目//调度器脚本
"""任务调度器——后台轮询 pending 任务，自动派发到 TaskQueue 执行。"""

import logging
import threading

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2  # 轮询间隔（秒）


class TaskScheduler:
    """后台轮询待处理任务，自动派发到 TaskQueue 执行。"""

    def __init__(self, task_queue=None) -> None:
        self._queue = task_queue  # TaskQueue 实例（启动时注入）
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    @property
    def running(self) -> bool:
        """调度器是否正在运行。"""
        return self._running

    def set_queue(self, q) -> None:
        """运行时注入 TaskQueue 实例。"""
        self._queue = q

    def start(self) -> None:
        """启动后台轮询线程。"""
        if self._running:
            return
        if self._queue is None:
            logger.warning("[TASK-SCHED] TaskQueue 未注入，跳过")
            return
        self._stop.clear()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="task-sched")
        self._thread.start()
        logger.info("[TASK-SCHED] 启动 (间隔=%ds)", POLL_INTERVAL)

    def stop(self) -> None:
        """停止调度器并等待线程结束。"""
        self._stop.set()
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("[TASK-SCHED] 已停止")

    def _run(self) -> None:
        """后台主循环：轮询待处理任务并自动派发执行。"""
        while not self._stop.is_set():
            try:
                pending = self._queue.get_pending()
                for task in pending:
                    if self._stop.is_set():
                        break
                    try:
                        self._queue.start(task)
                    except Exception as e:
                        logger.warning("[TASK-SCHED] 任务启动失败 %s: %s", task.task_id, e)
            except Exception as e:
                logger.error("[TASK-SCHED] 异常: %s", e)
            self._stop.wait(POLL_INTERVAL)


# 全局单例
_scheduler: TaskScheduler | None = None


def get_scheduler() -> TaskScheduler:
    """获取全局单例 TaskScheduler。"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler
