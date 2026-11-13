# 模块：项目//配置脚本
"""文件监控配置读写——存储到数据库 cache_config 表。统计值由 MonitorStats 管理。"""

import logging
import threading
from datetime import date
from typing import Any

logger = logging.getLogger("pilotstd.monitor")

DEFAULTS = {
    "enabled": "true",
    "watch_path": "/inbox",
    "delay_seconds": "5",
    "recursive": "true",
    "file_patterns": ".pdf,.docx,.doc",
    "ignore_patterns": "~$,.tmp,.swp",
    "auto_archive": "true",
    # P3-16 / 08#23：启动时补扫 watch_path 下已存在的文件（默认开；热水位见 catchup_watermark）
    "scan_existing_on_start": "true",
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
    for bool_key in ("enabled", "recursive", "auto_archive", "scan_existing_on_start"):
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
        "scan_existing_on_start",
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


# ── 启动补扫水位 + 最后处理文件（P3-16 / 08#23）────────────────
# 存在 cache_config 的 `monitor_state.*` 命名空间：不会被 get_config() 的
# `monitor.%` 前缀匹配，避免把运行时状态混进用户配置。
_WATERMARK_KEY = "monitor_state.catchup_watermark"
_LAST_PROCESSED_KEY = "monitor_state.last_processed"


def _get_state(key: str) -> str:
    """读取 monitor_state.* 的字符串值；任何异常返回空串（调用方用自己的默认值）。"""
    try:
        db = _db()
        row = db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
        return str(row["config_value"]) if row and row["config_value"] is not None else ""
    except Exception as e:
        logger.warning("monitor state read failed (%s): %s", key, e)
        return ""


def _set_state(key: str, value: str) -> None:
    """写入 monitor_state.*；失败只 warning，不阻断监控主流程。"""
    try:
        db = _db()
        db.execute(
            "INSERT OR REPLACE INTO cache_config (config_key, config_value, updated_at) "
            "VALUES (?, ?, datetime('now', 'localtime'))",
            (key, value),
        )
    except Exception as e:
        logger.warning("monitor state save failed (%s): %s", key, e)


def get_catchup_watermark() -> float:
    """上次启动补扫的**开始时间**（epoch 秒）。

    未跑过 / 读取失败返回 0.0 ⇒ 首次启动必须处理全部存量（不能用默认值把存量跳过）。
    存"开始时间"而不是"完成时间"：补扫期间新增的文件（mtime 晚于开始时间）下次仍会被处理。
    """
    raw = _get_state(_WATERMARK_KEY)
    try:
        return float(raw) if raw else 0.0
    except ValueError:
        logger.warning("monitor catchup watermark invalid: %r", raw)
        return 0.0


def set_catchup_watermark(ts: float) -> None:
    """补扫正常跑完后推进水位（被 stop 打断时不调用，下次重扫更安全）。"""
    _set_state(_WATERMARK_KEY, f"{float(ts):.3f}")


def get_last_processed() -> str:
    """最后处理文件的路径（状态页 `last_processed`）。"""
    return _get_state(_LAST_PROCESSED_KEY)


def set_last_processed(path: str) -> None:
    """记录最后处理文件（每批一次，不是每文件）。"""
    _set_state(_LAST_PROCESSED_KEY, str(path))


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
        """检查日期是否变化，跨天自动落盘昨日数据并归零。调用方不应持有锁。"""
        today = date.today().isoformat()
        needs_flush = False
        with self._lock:
            if self._stats_date is None:
                self._stats_date = today
                return
            if self._stats_date != today:
                needs_flush = True
        if needs_flush:
            self._flush()
            with self._lock:
                self._stats = {"processed": 0, "success": 0, "failed": 0}
                self._stats_date = today
                self._dirty = False

    def load_today(self) -> None:
        """启动时从 monitor_stats 恢复当天计数（P1-05）。

        只读当天行；DB 不可用/表缺失时 warning 后保持内存 0，不阻断启动。
        """
        try:
            db = self._get_db()
            rows = db.fetchall(
                "SELECT stat_key, stat_value FROM monitor_stats WHERE stat_date=?",
                (date.today().isoformat(),),
            )
        except Exception as e:
            logger.warning("monitor stats restore failed: %s", e)
            return
        with self._lock:
            for row in rows:
                key = row["stat_key"]
                if key in self._stats:
                    self._stats[key] = int(row["stat_value"] or 0)
            # 恢复值来自库，不需要再写回
            self._dirty = False

    def increment(self, key: str) -> None:
        """内存计数 +1。锁内仅做内存操作，_ensure_date 在锁外调用。"""
        with self._lock:
            if key in self._stats:
                self._stats[key] += 1
                self._dirty = True
        self._ensure_date()

    def _flush(self) -> None:
        """批量写入 DB（日切或关闭时调用）。锁内仅做数据拷贝，DB I/O 在锁外执行。"""
        snapshot: dict[str, int] = {}
        snapshot_date: str = ""
        with self._lock:
            if not self._dirty or not self._stats_date:
                return
            snapshot = self._stats.copy()
            snapshot_date = self._stats_date
            self._dirty = False
        # DB I/O 在锁外执行，避免长时间持锁
        db = self._get_db()
        for key, value in snapshot.items():
            db.execute(
                "INSERT OR REPLACE INTO monitor_stats (stat_key, stat_value, stat_date) VALUES (?, ?, ?)",
                (key, value, snapshot_date),
            )

    def flush_and_close(self) -> None:
        """应用关闭时调用，落盘当前数据。"""
        self._flush()
        if self._db:
            self._db.close()
            self._db = None

    def get_today_stats(self) -> dict[str, int]:
        """返回当天统计（内存值）。"""
        with self._lock:
            today = date.today().isoformat()
            if self._stats_date is None:
                self._stats_date = today
            return self._stats.copy()


_monitor_stats: MonitorStats | None = None


def get_monitor_stats() -> MonitorStats:
    """获取 MonitorStats 全局单例。"""
    global _monitor_stats
    if _monitor_stats is None:
        _monitor_stats = MonitorStats()
    return _monitor_stats
