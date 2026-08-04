# 模块：pilotstd/monitor/config.py
"""文件监控配置读写——存储到数据库 cache_config 表。统计值由 MonitorStats 管理。"""

import threading
from datetime import date
from typing import Any

DEFAULTS = {
    "enabled": "true",
    "watch_path": "/inbox",
    "delay_seconds": "5",
    "recursive": "true",
    "file_patterns": ".pdf,.docx,.doc",
    "ignore_patterns": "~$,.tmp,.swp",
    "auto_archive": "true",
}


def _db():
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    return Database(get_db_path())


def get_config() -> dict[str, Any]:
    """获取监控配置。未配置的项使用默认值。统计值通过 MonitorStats 获取。"""
    db = _db()
    rows = db.fetchall("SELECT config_key, config_value FROM cache_config WHERE config_key LIKE 'monitor.%'")
    cfg: dict[str, Any] = {}
    for r in rows:
        key = r["config_key"].replace("monitor.", "", 1)
        cfg[key] = r["config_value"]
    for k, v in DEFAULTS.items():
        if k not in cfg:
            cfg[k] = v
    # 类型转换
    for bool_key in ("enabled", "recursive", "auto_archive"):
        cfg[bool_key] = cfg.get(bool_key, "true") == "true"
    cfg["delay_seconds"] = int(cfg.get("delay_seconds", "5"))
    cfg["file_patterns"] = [p.strip() for p in cfg.get("file_patterns", ".pdf,.docx,.doc").split(",") if p.strip()]
    cfg["ignore_patterns"] = [p.strip() for p in cfg.get("ignore_patterns", "~$,.tmp,.swp").split(",") if p.strip()]
    return cfg


def set_config(updates: dict) -> None:
    """保存监控配置。"""
    db = _db()
    for key in (
        "enabled",
        "watch_path",
        "delay_seconds",
        "recursive",
        "file_patterns",
        "ignore_patterns",
        "auto_archive",
    ):
        if key in updates:
            val = updates[key]
            if isinstance(val, bool):
                val = "true" if val else "false"
            elif isinstance(val, list):
                val = ",".join(val)
            else:
                val = str(val)
            db.execute(
                "INSERT OR REPLACE INTO cache_config (config_key, config_value, updated_at) "
                "VALUES (?, ?, datetime('now', 'localtime'))",
                (f"monitor.{key}", val),
            )


# ── 监控统计内存计数器 ───────────────────────────────────────────


class MonitorStats:
    """监控统计内存计数器，替代 cache_config 秒级写入。

    每个文件事件仅操作内存计数器，日切或关闭时批量落库到 monitor_stats 表。
    """

    def __init__(self) -> None:
        self._stats: dict[str, int] = {"processed": 0, "success": 0, "failed": 0}
        self._stats_date: str | None = None
        self._db: Any = None
        self._lock = threading.Lock()
        self._dirty = False
        # 首次访问时初始化日期
        self._ensure_date()

    def _get_db(self):
        """惰性获取数据库连接实例。"""
        if self._db is None:
            from pilotstd.core.config import get_db_path
            from pilotstd.core.db import Database

            self._db = Database(get_db_path())
        return self._db

    def _ensure_date(self) -> None:
        """检查日期是否变化，跨天自动落盘昨日数据并归零。"""
        today = date.today().isoformat()
        if self._stats_date is None:
            self._stats_date = today
            return
        if self._stats_date != today:
            self._flush()
            self._stats = {"processed": 0, "success": 0, "failed": 0}
            self._stats_date = today
            self._dirty = False

    def increment(self, key: str) -> None:
        """内存计数 +1，不写 DB。"""
        with self._lock:
            self._ensure_date()
            if key in self._stats:
                self._stats[key] += 1
                self._dirty = True

    def _flush(self) -> None:
        """批量写入 DB（日切或关闭时调用）。"""
        with self._lock:
            if not self._dirty or not self._stats_date:
                return
            db = self._get_db()
            for key, value in self._stats.items():
                db.execute(
                    "INSERT OR REPLACE INTO monitor_stats (stat_key, stat_value, stat_date) VALUES (?, ?, ?)",
                    (key, value, self._stats_date),
                )
            self._dirty = False

    def flush_and_close(self) -> None:
        """应用关闭时调用，落盘当前数据。"""
        self._flush()
        if self._db:
            self._db.close()
            self._db = None

    def get_today_stats(self) -> dict[str, int]:
        """返回当天统计（内存值）。"""
        with self._lock:
            self._ensure_date()
            return self._stats.copy()


_monitor_stats: MonitorStats | None = None


def get_monitor_stats() -> MonitorStats:
    """获取 MonitorStats 全局单例。"""
    global _monitor_stats
    if _monitor_stats is None:
        _monitor_stats = MonitorStats()
    return _monitor_stats
