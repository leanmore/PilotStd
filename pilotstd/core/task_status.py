# pilotstd/core/task_status.py
# 定时任务执行状态内存缓存 — Phase1 基础设施（重启丢失，Phase2 历史表解决持久化）

import functools
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── 内存缓存 ──────────────────────────────────────────────

_task_status_cache: dict[str, dict] = {}


def record_task_result(task_name: str, status: str, error_msg: Optional[str] = None) -> None:
    """记录任务最近一次执行结果（内存缓存，Phase1 API 使用）。"""
    _task_status_cache[task_name] = {
        "last_run_time": datetime.now(timezone.utc).isoformat(),
        "last_run_status": status,
        "last_error_message": error_msg,
    }


def get_task_status(task_name: str) -> Optional[dict]:
    """获取任务最近执行状态，未执行过返回 None。"""
    return _task_status_cache.get(task_name)


def get_all_task_status() -> dict[str, dict]:
    """获取所有任务的最近执行状态。"""
    return dict(_task_status_cache)


# ── 异常捕获装饰器 ────────────────────────────────────────


def capture_task_error(task_name: str):
    """定时任务异常捕获装饰器：DB 持久化 + 内存缓存 + 异常上报。
    不重新抛出异常，保证调度器线程不退出。
    签名和调用方式不变（零侵入）。"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time as _time

            _start = _time.monotonic()
            try:
                result = func(*args, **kwargs)
                _duration_ms = int((_time.monotonic() - _start) * 1000)
                record_task_result(task_name, "success")
                # Phase2: DB 持久化写入
                try:
                    from .task_history import write_execution_record

                    write_execution_record(task_name, "success", duration_ms=_duration_ms)
                except Exception:
                    logger.exception("Failed to write execution record for %s", task_name)
                return result
            except Exception as e:
                _duration_ms = int((_time.monotonic() - _start) * 1000)
                logger.exception("Task %s failed: %s", task_name, e)
                record_task_result(task_name, "error", str(e))
                # Phase2: DB 持久化写入
                try:
                    from .task_history import write_execution_record

                    write_execution_record(task_name, "error", str(e)[:1000], _duration_ms)
                except Exception:
                    logger.exception("Failed to write execution record for %s", task_name)
                # 上报任务异常事件（复用现有通知渠道）
                try:
                    from pilotstd.manager.facade import StandardManager

                    mgr = StandardManager()
                    if mgr and mgr.notification_mgr:
                        mgr.notification_mgr.send_event(
                            "task_execution_failed",
                            {"task_name": task_name, "error": str(e)[:500]},
                        )
                except Exception:
                    logger.exception("Failed to emit error notification for %s", task_name)
            # 不重新抛出，保证 daemon 线程不退出
            return None

        return wrapper

    return decorator
