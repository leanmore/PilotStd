# pilotstd/core/cache_manager.py
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
from typing import Any, Optional

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
    FILE_INDEX = "file_index"
    ANNOUNCEMENT = "announcement"
    VALIDITY = "validity"


class CacheState(Enum):
    VALID = "valid"
    STALE = "stale"
    REFRESH_PENDING = "refresh_pending"


class CacheManager:
    """统一缓存管理器。

    用法:
        from pilotstd.core.cache_manager import CacheManager
        mgr = CacheManager(db)  # db 为 pilotstd.core.db.Database 实例
    """

    def __init__(self, db):
        self._db = db
        self._max_mb = self._load_config_int("max_size_mb", 50)
        self._auto_cleanup = self._load_config_bool("auto_cleanup", True)
        self._cleanup_ratio = self._load_config_float("cleanup_ratio", 0.1)

    # ── 核心读写 ──────────────────────────────

    def get(self, table: str, key_field: str, key_value: Any, source: DataSource) -> Optional[dict]:
        """读取缓存并校验版本。版本不匹配返回 None。"""
        current_version = self._get_source_version(source)

        row = self._db.fetchone(
            f"SELECT * FROM {table} WHERE {key_field}=?",
            (key_value,),
        )
        if not row:
            return None

        # 更新访问时间
        self._db.execute(
            f"UPDATE {table} SET last_accessed_at=? WHERE {key_field}=?",
            (datetime.now(timezone.utc).isoformat(), key_value),
        )

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
        data_json = json.dumps(data, ensure_ascii=False)
        now = datetime.now(timezone.utc).isoformat()

        self._db.execute(
            f"INSERT OR REPLACE INTO {table} "
            f"({key_field}, result_json, source_version, data_state, last_accessed_at) "
            f"VALUES (?, ?, ?, 'valid', ?)",
            (key_value, data_json, version, now),
        )

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

    # ── LRU 淘汰 ──────────────────────────────

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
            # 先删除 stale
            deleted = self._delete_oldest(table, "stale", ratio)
            deleted_total += deleted

            # 再删除 valid 中最久未访问的
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
        # 方案1: dbstat（需编译时启用 SQLITE_ENABLE_DBSTAT_VTAB）
        try:
            names = "','".join(_MANAGED_TABLES)
            row = self._db.fetchone(
                f"SELECT SUM(pgsize) as total_bytes FROM dbstat WHERE name IN ('{names}')",
            )
            if row and row["total_bytes"]:
                return row["total_bytes"] / (1024 * 1024)
        except Exception:
            pass

        # 方案2: page_count * page_size（数据库文件总大小）
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
                    return (db_bytes * min(ratio, 1.0)) / (1024 * 1024)
                return (db_bytes * 0.3) / (1024 * 1024)  # 假设占 30%
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
        row = self._db.fetchone(
            "SELECT version FROM data_source_versions WHERE source_name=?",
            (source.value,),
        )
        return row["version"] if row else "initial"

    def _bump_version(self, source: DataSource) -> str:
        new_version = datetime.now(timezone.utc).isoformat()
        self._db.execute(
            "UPDATE data_source_versions SET version=?, updated_at=? WHERE source_name=?",
            (new_version, datetime.now(timezone.utc).isoformat(), source.value),
        )
        logger.info("数据源版本升级: %s → %s", source.value, new_version)
        return new_version

    def _load_config_int(self, key: str, default: int) -> int:
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return int(row["config_value"]) if row else default
        except Exception:
            return default

    def _load_config_bool(self, key: str, default: bool) -> bool:
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return row["config_value"] == "true" if row else default
        except Exception:
            return default

    def _load_config_float(self, key: str, default: float) -> float:
        try:
            row = self._db.fetchone("SELECT config_value FROM cache_config WHERE config_key=?", (key,))
            return float(row["config_value"]) if row else default
        except Exception:
            return default
