# 容器/调度器脚本—定时任务调度器（含自动备份+优雅关闭+数据库互斥锁）
import logging
import os
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Optional, cast

from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from pilotstd.core.config import ConfigManager, get_db_path
from pilotstd.core.db import Database
from pilotstd.core.task_status import capture_task_error

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

# ✅#43:提取为模块级常量
_VALIDITY_JOB_ID = "validity_check"

# 调度器互斥锁：多工作者部署时，只有一个能抢到锁并启动调度器
_HEARTBEAT_INTERVAL = 30  # 心跳间隔（秒）
_STALE_TIMEOUT = 90  # 心跳超时（秒），超过则认为前 worker 已死
_heartbeat_stop = threading.Event()

# 已注册的任务执行函数表：_->
_job_funcs: dict[str, Callable] = {}

# 进程级数据库连接缓存，避免四个函数各自
_scheduler_db: Optional[Database] = None


def _get_db() -> Database:
    """返回 scheduler 复用的 Database 实例（惰性创建）。"""
    global _scheduler_db
    if _scheduler_db is None:
        _scheduler_db = Database(get_db_path())
    return _scheduler_db


# 不接入统一异常捕获的任务（已有独立异常处理链路）
_EXCLUDED_FROM_CAPTURE = {"validity_check", "auto_backup"}


def register_job_func(job_id: str, func: Callable):
    """注册定时任务执行函数。app.py 启动时调用，将业务函数与 job_id 绑定。
    所有任务统一由 capture_task_error 装饰器记录状态并上报异常；
    validity_check / auto_backup 保留独立异常处理链路，不接入。
    公告类任务额外包装为独立线程执行，不占用调度器线程池。"""
    if job_id not in _EXCLUDED_FROM_CAPTURE:
        func = capture_task_error(job_id)(func)
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
            except Exception as e:
                logger.warning("自动备份成功通知发送失败: %s", e)
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
            except Exception as e:
                logger.warning("自动备份失败通知发送失败: %s", e)


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

# 阶段4:日期提醒
from pilotstd.tasks.date_reminder import run_date_reminder  # noqa: E402


def _date_reminder_wrapper(notification_mgr=None):
    """日期提醒定时任务包装器：从 notification_mgr 获取通知管理器后调用核心提醒逻辑。

    若未传入 notification_mgr，则通过 get_manager() 惰性获取。
    异常被捕获并记录日志，不中断调度器循环。
    """
    if notification_mgr is None:
        from .manager import get_manager

        notification_mgr = get_manager().notification_mgr
    try:
        run_date_reminder(notification_mgr=notification_mgr)
    except Exception:
        logger.exception("日期提醒任务异常")
        raise


register_job_func("date_reminder", _date_reminder_wrapper)


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
                # 兜底：=1记录被_调度器清理后，重建并更新
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


def _scheduler_error_listener(event):
    """APScheduler 任务异常监听器：任务执行异常时发送通知。

    仅由 EVENT_JOB_ERROR 触发（见下方 add_listener）；事件必带 job_id，
    取不到时兜底为 unknown（防御，非正常路径）。
    """
    try:
        from .manager import get_manager

        mgr = get_manager()
        if hasattr(mgr, "notification_mgr") and mgr.notification_mgr:
            job_id = getattr(event, "job_id", None) or "unknown"
            exception = getattr(event, "exception", None) if event else None
            error_msg = str(exception) if exception else "未知异常"
            mgr.notification_mgr.send_event(
                "task_execution_failed",
                {"task_name": job_id, "error": error_msg[:500]},
            )
    except Exception as e:
        logger.warning("定时任务失败通知发送失败: %s", e)


# 监听任务执行异常（任务错误事件码 8192）。曾误用字面量 2**0（等于 1，即调度器启动事件），
# 导致每次调度器启动误发一条"定时任务执行失败/任务：unknown"，而真实任务异常从不通知。
scheduler.add_listener(_scheduler_error_listener, EVENT_JOB_ERROR)


def start_scheduler():
    """启动调度器：获取互斥锁 → 注册定时任务 → 启动心跳线程。"""
    if not _acquire_scheduler_lock():
        return

    cfg = ConfigManager()
    for job_id, cron_key, enabled_key in [
        ("auto_scan", "tasks.auto_scan_cron", "tasks.auto_scan_enabled"),
        ("auto_announce", "tasks.auto_announce_cron", "tasks.auto_announce_enabled"),
        ("auto_backup", "tasks.auto_backup_cron", "tasks.auto_backup_enabled"),
        ("date_reminder", "tasks.date_reminder_cron", "tasks.date_reminder_enabled"),
        ("auto_archive_retry", "tasks.auto_archive_retry_cron", "tasks.auto_archive_retry_enabled"),
        ("auto_health_check", "tasks.auto_health_check_cron", "tasks.auto_health_check_enabled"),
    ]:
        default_enabled = (job_id in ("auto_backup", "auto_health_check")) or cfg.get(enabled_key, False)
        if cfg.get(enabled_key, default_enabled):
            if job_id == "auto_backup":
                default_cron = "0 3 * * 0"
            elif job_id == "auto_archive_retry":
                default_cron = "0 4 * * *"
            elif job_id == "auto_health_check":
                default_cron = "0 * * * *"
            elif job_id == "auto_announce":
                default_cron = "0 1 * * *"
            else:
                default_cron = "0 0 * * *"
            _add_cron_job(job_id, cfg.get(cron_key, default_cron))
    # 通知日志定期清理（从配置读取间隔）
    cleanup_interval = int(cfg.get("notification.log_cleanup_interval_hours", 24))
    _add_interval_job("notification_cleanup", cleanup_interval * 3600)
    # 静音时段补发：每 5 分钟检查一次
    _add_interval_job("release_suppressed", 300)

    # ✅#43:注册时效性检查调度任务
    v_kwargs = _get_validity_cron_kwargs()
    scheduler.add_job(
        _check_validity_schedule,
        trigger=CronTrigger(timezone=timezone.utc, **v_kwargs),
        id=_VALIDITY_JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "已注册 validity_check: CronTrigger(day_of_week=%d, hour=%d, minute=%d UTC)",
        v_kwargs["day_of_week"],
        v_kwargs["hour"],
        v_kwargs["minute"],
    )

    scheduler.start()
    _heartbeat_stop.clear()
    threading.Thread(target=_heartbeat_loop, daemon=True, name="scheduler-heartbeat").start()
    logger.info("APScheduler 已启动")


def _check_validity_schedule(notification_mgr=None, adapter_mgr=None):
    """定时调度器定时触发器唤醒函数：直接执行时效性检查。

    第四十三号：使用定时触发器替代五分钟轮询与下次运行比较。
    调度频率由时间表达式（周几、时、分）控制，
    此函数每次被唤醒即执行一次检查。
    """
    from pilotstd.core.validity_checker import run_validity_check

    # ✅#43:统一使用.
    config = ConfigManager()
    now_utc = datetime.now(timezone.utc)

    # 记录首次执行时间（如果未设置）
    first_execution = config.get("validity.first_execution")
    if first_execution is None:
        config.set("validity.first_execution", now_utc.isoformat())
        config.save()

    run_validity_check(notification_mgr=notification_mgr, update_counters=True, adapter_mgr=adapter_mgr)

    # 更新下次预计执行时间（日志展示用）
    next_job = scheduler.get_job(_VALIDITY_JOB_ID)
    if next_job:
        next_fire = next_job.next_run_time
        if next_fire:
            config.set("validity.next_run", next_fire.isoformat())
    config.save()
    logger.info("validity 检查完成，下次执行时间: %s", config.get("validity.next_run"))


# 注册时效性检查任务执行函数
register_job_func(_VALIDITY_JOB_ID, _check_validity_schedule)


def _get_validity_cron_kwargs():
    """从配置读取时效性检查的 CronTrigger 参数。"""
    config = ConfigManager()
    weekday_1_7 = int(config.get("validity.first_weekday", 1))
    # ✅#43:__:0=,6=；前端传入1=,7=
    day_of_week = max(0, min(6, weekday_1_7 - 1))
    execute_time = config.get("validity.execute_time", "03:00")
    try:
        hour, minute = map(int, execute_time.split(":"))
    except (ValueError, TypeError):
        hour, minute = 3, 0
    return {"day_of_week": day_of_week, "hour": hour, "minute": minute}


def reschedule_validity_job():
    """第四十三号：配置变更后更新调度器定时触发器。异常向上抛出，由调用方处理。"""
    kwargs = _get_validity_cron_kwargs()
    trigger = CronTrigger(timezone=timezone.utc, **kwargs)
    if scheduler.get_job(_VALIDITY_JOB_ID):
        scheduler.reschedule_job(_VALIDITY_JOB_ID, trigger=trigger)
    else:
        scheduler.add_job(
            _check_validity_schedule,
            trigger=trigger,
            id=_VALIDITY_JOB_ID,
            replace_existing=True,
        )
    logger.info(
        "validity 调度已更新: day_of_week=%d, %02d:%02d UTC",
        kwargs["day_of_week"],
        kwargs["hour"],
        kwargs["minute"],
    )


def get_validity_next_run() -> Optional[str]:
    """返回时效性检查的下次执行时间（ISO 字符串）。

    以调度器实时状态为准：/api/validity/config 原先读配置里的 validity.next_run，
    该键仅在任务执行时才刷新，改配置 reschedule 后会滞后；
    且配置读取走的是进程启动快照（见该端点说明），故此处直接问调度器。
    未注册或未调度时返回 None，调用方回退配置文件值。
    """
    job = scheduler.get_job(_VALIDITY_JOB_ID)
    if job is None or job.next_run_time is None:
        return None
    # 定时任务库无类型存根，任务的"下次执行时间"被推断为任意类型；显式强制转换以满足
    # G-038（静态类型门禁）的"返回任意类型"告警（返回值语义上就是字符串）
    return cast(str, job.next_run_time.isoformat())


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
