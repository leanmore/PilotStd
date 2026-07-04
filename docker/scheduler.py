# docker/scheduler.py — APScheduler 定时任务调度器（含自动备份 + 优雅关闭 + DB 互斥锁）
import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db import Database

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# 调度器互斥锁：多 worker 部署时，只有一个能抢到锁并启动调度器
_HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
_STALE_TIMEOUT = 90  # 心跳超时（秒），超过则认为前 worker 已死
_heartbeat_stop = threading.Event()

# 已注册的任务执行函数表：job_id -> callable
_job_funcs: dict[str, Callable] = {}

# 进程级 DB 连接缓存，避免四个函数各自 new Database
_scheduler_db: Optional[Database] = None


def _get_db() -> Database:
    """返回 scheduler 复用的 Database 实例（惰性创建）。"""
    global _scheduler_db
    if _scheduler_db is None:
        _scheduler_db = Database(get_db_path())
    return _scheduler_db


def register_job_func(job_id: str, func: Callable):
    """注册定时任务执行函数。app.py 启动时调用，将业务函数与 job_id 绑定。
    公告类任务包装为独立线程执行，不占用调度器线程池。"""
    if "announce" in job_id:

        def _wrapped():
            t = threading.Thread(target=func, daemon=True, name=f"sched-{job_id}")
            t.start()

        _job_funcs[job_id] = _wrapped
    else:
        _job_funcs[job_id] = func


def _add_interval_job(job_id: str, interval_seconds: int):
    """向调度器添加 interval 定时任务（唤醒模式）。"""
    from apscheduler.triggers.interval import IntervalTrigger

    func = _job_funcs.get(job_id)
    if func:
        scheduler.add_job(func, IntervalTrigger(seconds=interval_seconds), id=job_id, replace_existing=True)


def _add_cron_job(job_id: str, cron_expr: str):
    """向调度器添加一个 cron 定时任务。若已存在则替换。"""
    func = _job_funcs.get(job_id)
    if func:
        scheduler.add_job(func, CronTrigger.from_crontab(cron_expr), id=job_id, replace_existing=True)


def _backup_database(notification_mgr=None):
    """每周自动备份数据库，保留最近 4 个备份。"""
    db = _get_db()
    backup_dir = os.path.join(os.path.dirname(db.path), "backups")
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backup_dir, f"pilotstd_{timestamp}.bak")
    result = db.backup(backup_path)
    if result:
        all_backups = sorted([f for f in os.listdir(backup_dir) if f.endswith(".bak")], reverse=True)
        for old in all_backups[4:]:
            try:
                os.remove(os.path.join(backup_dir, old))
                logger.info("已清理旧备份: %s", old)
            except OSError:
                pass
        if notification_mgr:
            try:
                size_mb = os.path.getsize(backup_path) / (1024 * 1024)
                notification_mgr.send_event(
                    "auto_backup",
                    {
                        "success": True,
                        "backup_path": backup_path,
                        "size_mb": size_mb,
                    },
                )
            except Exception:
                pass
    else:
        if notification_mgr:
            try:
                notification_mgr.send_event(
                    "auto_backup",
                    {
                        "success": False,
                        "error": "数据库备份返回 False",
                    },
                )
            except Exception:
                pass


# 注册自动备份任务（每周日凌晨 3 点执行）
register_job_func("auto_backup", _backup_database)


def _cleanup_notification_logs(notification_mgr=None):
    """定时清理过期通知日志。"""
    if notification_mgr is None:
        from .manager import get_manager

        notification_mgr = get_manager().notification_mgr
    cfg = ConfigManager()
    retention_days = int(cfg.get("notification.log_retention_days", 30))
    try:
        deleted = notification_mgr.cleanup_logs(days=retention_days)
        logger.info("[cleanup] 通知日志清理完成，删除 %d 条（保留 %d 天）", deleted, retention_days)
    except Exception:
        logger.exception("[cleanup] 通知日志清理失败")


register_job_func("notification_cleanup", _cleanup_notification_logs)


def _release_suppressed_notifications(notification_mgr=None):
    """每5分钟检查并补发静音时段暂存的通知。"""
    if notification_mgr is None:
        from .manager import get_manager

        notification_mgr = get_manager().notification_mgr
    try:
        count = notification_mgr.release_suppressed_notifications()
        if count > 0:
            logger.info("[release] 补发压制通知: %d 条", count)
    except Exception:
        logger.exception("[release] 补发压制通知失败")


register_job_func("release_suppressed", _release_suppressed_notifications)


def _acquire_scheduler_lock() -> bool:
    """尝试获取调度器互斥锁。返回 True=获取成功，False=已有其他 worker 在运行。"""
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS scheduler_lock (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            pid INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            heartbeat_at TEXT NOT NULL
        )
    """)
    pid = os.getpid()
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    try:
        db.execute(
            "INSERT INTO scheduler_lock (id, pid, started_at, heartbeat_at) VALUES (1, ?, ?, ?)",
            (pid, now_str, now_str),
        )
        logger.info("调度器互斥锁已获取 (PID=%d)", pid)
        return True
    except Exception:
        row = db.fetchone("SELECT pid, heartbeat_at FROM scheduler_lock WHERE id = 1")
        if row:
            try:
                heartbeat = time.mktime(time.strptime(row["heartbeat_at"], "%Y-%m-%d %H:%M:%S"))
                if time.time() - heartbeat > _STALE_TIMEOUT:
                    db.execute(
                        "UPDATE scheduler_lock SET pid=?, started_at=?, heartbeat_at=? WHERE id=1",
                        (pid, now_str, now_str),
                    )
                    logger.warning("调度器互斥锁已接管（前 PID=%d 心跳超时）", row["pid"])
                    return True
                else:
                    logger.info("调度器已在 PID=%d 运行，本 worker 跳过", row["pid"])
            except (ValueError, OSError):
                pass
        return False


def _heartbeat_loop() -> None:
    """心跳线程：定期更新 heartbeat_at 表示本 worker 存活。"""
    db = _get_db()
    while not _heartbeat_stop.wait(_HEARTBEAT_INTERVAL):
        try:
            result = db.execute(
                "UPDATE scheduler_lock SET heartbeat_at=? WHERE id=1",
                (time.strftime("%Y-%m-%d %H:%M:%S"),),
            )
            if result.rowcount == 0:
                # 兜底：id=1 记录被 stop_scheduler 清理后，重建并更新
                db.execute(
                    "INSERT OR IGNORE INTO scheduler_lock (id, pid, started_at, heartbeat_at) "
                    "VALUES (1, 0, datetime('now', 'localtime'), datetime('now', 'localtime'))"
                )
                db.execute(
                    "UPDATE scheduler_lock SET heartbeat_at=? WHERE id=1",
                    (time.strftime("%Y-%m-%d %H:%M:%S"),),
                )
        except Exception:
            pass


def start_scheduler():
    """启动调度器：获取互斥锁 → 注册定时任务 → 启动心跳线程。"""
    if not _acquire_scheduler_lock():
        return

    cfg = ConfigManager()
    for job_id, cron_key, enabled_key in [
        ("auto_scan", "tasks.auto_scan_cron", "tasks.auto_scan_enabled"),
        ("auto_announce", "tasks.auto_announce_cron", "tasks.auto_announce_enabled"),
        ("auto_backup", "tasks.auto_backup_cron", "tasks.auto_backup_enabled"),
    ]:
        default_enabled = (job_id == "auto_backup") or cfg.get(enabled_key, False)
        if cfg.get(enabled_key, default_enabled):
            default_cron = "0 3 * * 0" if job_id == "auto_backup" else "0 0 * * *"
            _add_cron_job(job_id, cfg.get(cron_key, default_cron))
    _add_interval_job("validity_wake", 300)
    # 通知日志定期清理（从配置读取间隔）
    cleanup_interval = int(cfg.get("notification.log_cleanup_interval_hours", 24))
    _add_interval_job("notification_cleanup", cleanup_interval * 3600)
    _add_interval_job("release_suppressed", 300)  # 每5分钟检查静音补发
    scheduler.start()
    _heartbeat_stop.clear()
    threading.Thread(target=_heartbeat_loop, daemon=True, name="scheduler-heartbeat").start()
    logger.info("APScheduler 已启动")


def _check_validity_schedule(notification_mgr=None, adapter_mgr=None):
    """APScheduler 唤醒函数：检查是否到了 validity 执行时间。"""
    import math
    from datetime import datetime, timedelta

    config = ConfigManager()
    first_execution_str = config.get("validity.first_execution")
    next_run_str = config.get("validity.next_run")
    round_completed = config.get("validity.round_completed", False)

    if first_execution_str is None:
        return

    if round_completed:
        config.set("validity.round_completed", False)
        config.set("validity.checked_count", 0)
        now = datetime.now()
        config.set("validity.next_run", (now + timedelta(minutes=1)).isoformat())
        config.save()
        logger.info("validity 轮次完成，自动重置，下一轮将于 1 分钟后开始")
        return

    now = datetime.now()

    if next_run_str is None:
        try:
            first_execution = datetime.fromisoformat(first_execution_str)
        except (ValueError, TypeError):
            logger.warning("validity.first_execution 格式无效: %s", first_execution_str)
            return
        if now < first_execution:
            return
    else:
        try:
            next_run = datetime.fromisoformat(next_run_str)
        except (ValueError, TypeError):
            logger.warning("validity.next_run 格式无效: %s", next_run_str)
            return
        if now < next_run:
            return

    from pilotstd.core.validity_checker import run_validity_check

    run_validity_check(notification_mgr=notification_mgr, update_counters=True, adapter_mgr=adapter_mgr)

    check_ratio = config.get("validity.check_ratio", 25)
    total_weeks = config.get("validity.total_weeks", 4)
    total_runs = math.ceil(100 / check_ratio)
    total_days = total_weeks * 7
    interval_days = math.ceil(total_days / total_runs)

    next_dt = now + timedelta(days=interval_days)
    config.set("validity.next_run", next_dt.isoformat())
    config.save()
    logger.info("validity 下次执行时间: %s（间隔 %d 天）", next_dt.isoformat(), interval_days)


def stop_scheduler():
    """优雅关闭调度器：停止心跳 → 等待任务完成 → 释放互斥锁。"""
    _heartbeat_stop.set()
    scheduler.shutdown(wait=True)
    try:
        _get_db().execute("DELETE FROM scheduler_lock WHERE id=1")
    except Exception:
        pass
    logger.info("APScheduler 已停止")


def update_job(job_id: str, cron: str, enabled: bool):
    """根据启用状态动态更新定时任务：启用时添加/更新 cron，禁用时移除。"""
    if enabled and scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=CronTrigger.from_crontab(cron))
    elif enabled and not scheduler.get_job(job_id):
        _add_cron_job(job_id, cron)
    elif not enabled and scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
