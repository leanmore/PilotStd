# pilotstd/monitor/config.py
"""文件监控配置读写——存储到数据库 cache_config 表。"""

from typing import Any

DEFAULTS = {
    "enabled": "true",
    "watch_path": "/inbox",
    "delay_seconds": "5",
    "recursive": "true",
    "file_patterns": ".pdf,.docx,.doc",
    "ignore_patterns": "~$,.tmp,.swp",
    "auto_archive": "true",
    "last_processed": "",
    "processed_today": "0",
    "success_today": "0",
    "failed_today": "0",
}


def _db():
    from pilotstd.core.config import get_db_path
    from pilotstd.core.db import Database

    return Database(get_db_path())


def get_config() -> dict[str, Any]:
    """获取监控配置。未配置的项使用默认值。"""
    db = _db()
    rows = db.fetchall("SELECT config_key, config_value FROM cache_config WHERE config_key LIKE 'monitor.%'")
    cfg = {}
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


def increment_stat(key: str) -> None:
    """递增统计计数。"""
    db = _db()
    db.execute(
        "INSERT OR REPLACE INTO cache_config (config_key, config_value, updated_at) "
        "VALUES (?, CAST(COALESCE((SELECT CAST(config_value AS INTEGER) "
        "FROM cache_config WHERE config_key=?), 0) + 1 AS TEXT), datetime('now', 'localtime'))",
        (f"monitor.{key}", f"monitor.{key}"),
    )


def set_last_processed(path: str) -> None:
    """记录最后处理的文件路径和时间。"""
    db = _db()
    from datetime import datetime

    db.execute(
        "INSERT OR REPLACE INTO cache_config (config_key, config_value, updated_at) "
        "VALUES (?, ?, datetime('now', 'localtime'))",
        ("monitor.last_processed", f"{datetime.now().isoformat()} | {path}"),
    )
