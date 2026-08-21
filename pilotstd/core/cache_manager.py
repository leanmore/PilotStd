# 模块：项目/核心/缓存_管理器脚本
"""统一缓存管理器——版本驱动失效 + LRU 淘汰 + 大小限制。

设计原则：
  - 无 TTL，由数据源版本变化驱动失效
  - 外部定时任务触发缓存标记为 stale
  - 默认 50MB 上限，超 90% 触发 LRU 淘汰
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, cast

logger = logging.getLogger(__name__)

# 受管理的缓存表
_MANAGED_TABLES = ("standard_info_cache", "standard_validity", "announcement_record")

# 数据源到缓存表的映射
_SOURCE_TABLE_MAP = {
    "file_index": ["standard_info_cache"],
    "announcement": ["announcement_record"],
    "validity": ["standard_validity"],
}


class DataSource(Enum):
    """缓存数据来源类型：文件索引 / 公告 / 有效性检查。"""

    FILE_INDEX = "file_index"
    ANNOUNCEMENT = "announcement"
    VALIDITY = "validity"


class CacheState(Enum):
    """缓存条目生命周期状态：有效 / 过期待刷新 / 刷新中。"""

    VALID = "valid"
    STALE = "stale"
    REFRESH_PENDING = "refresh_pending"


class CacheManager:
    """统一缓存管理器。

    用法示例：传入数据库实例创建缓存管理对象。
    """

    def __init__(self, db):
        self._db = db
        self._ensure_cache_tables()
        # 从数据库加载配置参数，支持运行时动态调整
        self._max_mb = self._load_config_int("max_size_mb", 50)
        self._auto_cleanup = self._load_config_bool("auto_cleanup", True)
        self._cleanup_ratio = self._load_config_float("cleanup_ratio", 0.1)

    def _ensure_cache_tables(self) -> None:
        """确保 cache_config 和 data_source_versions 表存在（防止迁移遗漏时查询失败）。"""
        tables = self._db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('cache_config', 'data_source_versions')"
        )
        existing = {r["name"] for r in tables} if tables else set()
        if "cache_config" not in existing:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS cache_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT NOT NULL UNIQUE,
                    config_value TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            for ck, cv in (("max_size_mb", "50"), ("auto_cleanup", "true"), ("cleanup_ratio", "0.1")):
                self._db.execute(
                    "INSERT OR IGNORE INTO cache_config (config_key, config_value) VALUES (?, ?)", (ck, cv)
                )
        if "data_source_versions" not in existing:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS data_source_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_name TEXT NOT NULL UNIQUE,
                    version TEXT NOT NULL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            for src in ("file_index", "announcement", "validity"):
                self._db.execute(
                    "INSERT OR IGNORE INTO data_source_versions (source_name, version) VALUES (?, 'initial')", (src,)
                )

    # ── 核心读写 ──────────────────────────────

    def get(self, table: str, key_field: str, key_value: Any, source: DataSource) -> Optional[dict]:
        """读取缓存并校验版本。版本不匹配返回 None。"""
        # 获取数据源当前版本，用于与缓存记录的版本比对
        current_version = self._get_source_version(source)

        row = self._db.fetchone(
            f"SELECT * FROM {table} WHERE {key_field}=?",
            (key_value,),
        )
        if not row:
            return None

        # 更新访问时间（用于淘汰排序）
        self._db.execute(
            f"UPDATE {table} SET last_accessed_at=? WHERE {key_field}=?",
            (datetime.now(timezone.utc).isoformat(), key_value),
        )

        # 版本不匹配→标记为→返回，触发上游重新查询
        if row.get("source_version") != current_version:
            self._db.execute(
                f"UPDATE {table} SET data_state='stale' WHERE {key_field}=?",
                (key_value,),
            )
            logger.debug(
                "缓存过期: %s.%s=%s (版本 %s→%s)",
                table,
                key_field,
                key_value,
                row.get("source_version"),
                current_version,
            )
            return None

        return dict(row)

    def set(self, table: str, key_field: str, key_value: Any, data: dict, source: DataSource):
        """写入缓存（带版本标记）。写入后检查大小。"""
        version = self._get_source_version(source)
        # 数据序列化为数据存储，便于后续读取和调试
        data_json = json.dumps(data, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()

        self._db.execute(
            f"INSERT OR REPLACE INTO {table} "
            f"({key_field}, result_json, source_version, data_state, last_accessed_at) "
            f"VALUES (?, ?, ?, 'valid', ?)",
            (key_value, data_json, version, now),
        )

        # 写入后自动检查是否需要淘汰
        if self._auto_cleanup:
            self._check_and_cleanup()

    # ── 失效管理 ─────────────────────────────

    def invalidate_by_source(self, source: DataSource):
        """数据源更新后，将其关联的所有缓存标记为 stale。"""
        new_version = self._bump_version(source)
        tables = _SOURCE_TABLE_MAP.get(source.value, [])
        for table in tables:
            self._db.execute(
                f"UPDATE {table} SET data_state='stale' WHERE source_version!=?",
                (new_version,),
            )
        logger.info("缓存失效: source=%s version=%s tables=%s", source.value, new_version, tables)

    def mark_stale(self, table: str, key_field: str, key_value: Any):
        """手动标记单条缓存为 stale。"""
        self._db.execute(
            f"UPDATE {table} SET data_state='stale' WHERE {key_field}=?",
            (key_value,),
        )

    def mark_valid(self, table: str, key_field: str, key_value: Any, source: DataSource):
        """标记缓存为 valid（刷新完成后调用）。"""
        version = self._get_source_version(source)
        self._db.execute(
            f"UPDATE {table} SET data_state='valid', source_version=? WHERE {key_field}=?",
            (version, key_value),
        )

    # ──淘汰──────────────────────────────

    def cleanup(self, force: bool = False):
        """执行 LRU 淘汰。force=True 时无视大小阈值直接清理。"""
        total_mb = self.get_total_size_mb()
        threshold_mb = self._max_mb * 0.9

        if not force and total_mb < threshold_mb:
            logger.debug("缓存大小 %.1fMB < 阈值 %.1fMB，跳过清理", total_mb, threshold_mb)
            return

        ratio = self._cleanup_ratio
        deleted_total = 0

        for table in _MANAGED_TABLES:
            # 先删除
            deleted = self._delete_oldest(table, "stale", ratio)
            deleted_total += deleted

            # 再删除中最久未访问的
            deleted = self._delete_oldest(table, "valid", ratio)
            deleted_total += deleted

        after_mb = self.get_total_size_mb()
        logger.info("LRU 清理完成: %.1fMB→%.1fMB 删除 %d 条", total_mb, after_mb, deleted_total)

    def _delete_oldest(self, table: str, state: str, ratio: float) -> int:
        """删除指定状态中最久未访问的 ratio 比例的记录。返回删除数。"""
        try:
            count_row = self._db.fetchone(
                f"SELECT COUNT(*) as cnt FROM {table} WHERE data_state=?",
                (state,),
            )
            total = count_row["cnt"] if count_row else 0
            if total == 0:
                return 0
            limit = max(1, int(total * ratio))
            self._db.execute(
                f"DELETE FROM {table} WHERE id IN ("
                f"  SELECT id FROM {table} WHERE data_state=? "
                f"  ORDER BY last_accessed_at ASC LIMIT {limit}"
                f")",
                (state,),
            )
            return limit
        except Exception as e:
            logger.warning("LRU 删除 %s(%s) 失败: %s", table, state, e)
            return 0

    def _check_and_cleanup(self):
        """写入后检查大小，超阈值则清理。"""
        try:
            self.cleanup()
        except Exception as e:
            logger.warning("缓存清理异常: %s", e)

    # ── 统计 ──────────────────────────────────

    def get_stats(self) -> dict:
        """获取各缓存表的统计信息。"""
        tables_stats = {}
        for table in _MANAGED_TABLES:
            rows = self._db.fetchall(f"SELECT data_state, COUNT(*) as cnt FROM {table} GROUP BY data_state")
            tables_stats[table] = {r["data_state"]: r["cnt"] for r in rows}
        return {
            "total_size_mb": round(self.get_total_size_mb(), 2),
            "max_size_mb": self._max_mb,
            "auto_cleanup": self._auto_cleanup,
            "cleanup_ratio": self._cleanup_ratio,
            "tables": tables_stats,
        }

    def get_total_size_mb(self) -> float:
        """计算缓存表总大小（MB）。

        优先 dbstat 虚拟表，降级使用 page_count/page_size，
        最后降级为行数估算。
        """
        # 方案1:（需编译时启用数据库查询__数据库_）
        try:
            names = "','".join(_MANAGED_TABLES)
            row = self._db.fetchone(
                f"SELECT SUM(pgsize) as total_bytes FROM dbstat WHERE name IN ('{names}')",
            )
            if row and row["total_bytes"]:
                return cast(float, row["total_bytes"] / (1024 * 1024))
        except Exception:
            pass

        # 方案2:_*_（数据库文件总大小）
        try:
            row = self._db.fetchone(
                "SELECT page_count * page_size as db_bytes FROM pragma_page_count(), pragma_page_size()"
            )
            if row and row["db_bytes"]:
                db_bytes = row["db_bytes"]
                # 按缓存表行数占比分配
                total_rows = 0
                table_rows = {}
                for table in _MANAGED_TABLES:
                    r = self._db.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
                    cnt = r["cnt"] if r else 0
                    table_rows[table] = cnt
                    total_rows += cnt
                if total_rows > 0:
                    ratio = sum(table_rows.values()) / max(
                        sum(
                            r["cnt"]
                            for r in self._db.fetchall("SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'")
                            if r["cnt"]
                        ),
                        1,
                    )
                    return cast(float, (db_bytes * min(ratio, 1.0)) / (1024 * 1024))
                return cast(float, (db_bytes * 0.3) / (1024 * 1024))
        except Exception:
            pass

        # 方案3: 行数 × 500 字节估算
        total_rows = 0
        for table in _MANAGED_TABLES:
            try:
                r = self._db.fetchone(f"SELECT COUNT(*) as cnt FROM {table}")
                total_rows += r["cnt"] if r else 0
            except Exception:
                pass
        return total_rows * 500 / (1024 * 1024)

    def get_config(self) -> dict:
        """获取当前缓存管理器的配置参数（max_size、自动清理开关、清理比例）。"""
        return {
            "max_size_mb": self._max_mb,
            "auto_cleanup": self._auto_cleanup,
            "cleanup_ratio": self._cleanup_ratio,
        }

    def set_config(self, key: str, value: Any):
        """更新缓存配置。"""
        self._db.execute(
            "INSERT OR REPLACE INTO cache_config (config_key, config_value, updated_at) VALUES (?, ?, ?)",
            (
                key,
                str(value).lower() if isinstance(value, bool) else str(value),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        if key == "max_size_mb":
            self._max_mb = int(value)
        elif key == "auto_cleanup":
            self._auto_cleanup = value if isinstance(value, bool) else value == "true"
        elif key == "cleanup_ratio":
            self._cleanup_ratio = float(value)

    # ── 内部方法 ──────────────────────────────

    def _get_source_version(self, source: DataSource) -> str:
        """查询指定数据源的当前版本号，用于缓存一致性校验。"""
        row = self._db.fetchone(
            "SELECT version FROM data_source_versions WHERE source_name=?",
            (source.value,),
        )
        return row["version"] if row else "initial"

    def _bump_version(self, source: DataSource) -> str:
        """递增数据源版本号（以当前时间戳为新版本），用于触发缓存失效。"""
        new_version = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "UPDATE data_source_versions SET version=?, updated_at=? WHERE source_name=?",
            (new_version, datetime.now(timezone.utc).isoformat(), source.value),
        )
        logger.info("数据源版本升级: %s → %s", source.value, new_version)
        return new_version

    def _load_config_int(self, key: str, default: int) -> int:
        """从 cache_config 表读取整数配置，不存在或解析失败时返回默认值。"""
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return int(row["config_value"]) if row else default
        except Exception:
            return default

    def _load_config_bool(self, key: str, default: bool) -> bool:
        """从 cache_config 表读取布尔配置（存储为 "true"/"false" 字符串）。"""
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return row["config_value"] == "true" if row else default
        except Exception:
            return default

    def _load_config_float(self, key: str, default: float) -> float:
        """从 cache_config 表读取浮点数配置，不存在或解析失败时返回默认值。"""
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return float(row["config_value"]) if row else default
        except Exception:
            return default
