# 模块：项目/查询/缓存脚本
# 查询结果本地持久化缓存（数据库查询）—双表回退，事件驱动失效

from __future__ import annotations

import json
import logging
from datetime import timedelta
from typing import Any, Optional

from pilotstd.core.time_utils import iso_now, now, parse_iso

from ..core.db import Database
from ..core.file_index import ANNOUNCEMENT_CACHE_TABLE
from .models import QueryResult

logger = logging.getLogger(__name__)

CACHE_TABLE = "standard_info_cache"
DEFAULT_ACTIVE_TTL_DAYS = 30
DEFAULT_INACTIVE_TTL_DAYS = 7


class CacheRepository:
    """标准信息缓存仓库。先查网络查询缓存，不命中回退公告缓存。

    主表失效由事件驱动（网络查询返回"被代替"或公告比对命中）；公告回退额外
    受 TTL 约束：`expires_at` 优先，缺失时按 `cached_at + active_ttl` 兜底，
    `data_state='stale'` 一律不命中（P0-02，2026-11-09）。
    """

    def __init__(
        self,
        db: Database,
        active_ttl: int = DEFAULT_ACTIVE_TTL_DAYS,
        inactive_ttl: int = DEFAULT_INACTIVE_TTL_DAYS,
    ):
        self._db = db
        self._active_ttl = active_ttl
        self._inactive_ttl = inactive_ttl
        self._ensure_table()

    # 公共接口

    def get(self, standard_number: str, source_site: str) -> Optional[QueryResult]:
        """查缓存：先 standard_info_cache，不命中回退 announcement_match。"""
        # 先查网络查询缓存
        row = self._db.fetchone(
            f"SELECT * FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
            (standard_number, source_site),
        )
        if row:
            # CacheManager 已将数据源版本变化标记为 stale；stale 不能再当命中，
            # 否则事件驱动失效对查询链路完全无效（2026-11-07 审计）。
            if row.get("data_state") == "stale":
                logger.debug("查询缓存 stale，跳过: %s @%s", standard_number, source_site)  # i18n-allow: 内部缓存日志
                return None
            # 过滤不接受的字段（适配器可能挂临时属性，如的___）
            _valid = {f.name for f in QueryResult.__dataclass_fields__.values()}
            data = {k: v for k, v in json.loads(row["result_json"]).items() if k in _valid}
            return QueryResult(**data)

        # 不命中则回退查公告缓存
        ann_row = self._db.fetchone(
            f"SELECT * FROM {ANNOUNCEMENT_CACHE_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if ann_row:
            # P0-02：公告回退也必须校验新鲜度。matcher 写入的 expires_at 目前为
            # NULL，因此以 cached_at + active_ttl 为兜底，避免旧公告被永久当命中。
            if not self._announcement_cache_fresh(ann_row):
                logger.debug("公告缓存过期/失效，跳过: %s", standard_number)  # i18n-allow: 内部缓存日志
                return None
            data = json.loads(ann_row["result_json"])
            # 公告缓存数据不含_，需注入
            data["standard_number"] = ann_row["standard_number"]
            data.setdefault("source_site", "announcement")
            # 过滤不接受的公告元数据字段
            _valid = {f.name for f in QueryResult.__dataclass_fields__.values()}
            data = {k: v for k, v in data.items() if k in _valid}
            return QueryResult(**data)

        return None

    def _announcement_cache_fresh(self, row: dict[str, Any]) -> bool:
        """公告回退的 TTL 守卫：stale 或已过期 → 不命中。

        - `data_state='stale'` 直接拒绝；
        - `expires_at` 可解析时优先使用；
        - 否则 `cached_at + active_ttl`（active_ttl<=0 表示不按时间过期）；
        - 两个时间都缺失时保守命中（无法判断，不因脏行一刀切）。
        """
        if row.get("data_state") == "stale":
            return False
        expires_at = parse_iso(row.get("expires_at"))
        if expires_at is None and self._active_ttl > 0:
            cached_at = parse_iso(row.get("cached_at"))
            if cached_at is not None:
                expires_at = cached_at + timedelta(days=self._active_ttl)
        return not (expires_at is not None and expires_at <= now())

    def put(self, result: QueryResult, source: str = "network") -> None:
        """写入缓存。source: network / announcement / manual。"""
        existing = self._db.fetchone(
            f"SELECT id, source FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
            (result.standard_number, result.source_site),
        )
        result_json = json.dumps(result.__dict__, ensure_ascii=False)

        if existing:
            # 已有记录时不覆盖（保留首次数据来源标记）
            self._db.execute(
                f"UPDATE {CACHE_TABLE} SET result_json=?, cached_at=?, data_state='fresh' WHERE id=?",
                (result_json, iso_now(), existing["id"]),
            )
        else:
            self._db.execute(
                f"INSERT INTO {CACHE_TABLE} (standard_number, source_site, "
                "result_json, cached_at, source) VALUES (?, ?, ?, ?, ?)",
                (
                    result.standard_number,
                    result.source_site,
                    result_json,
                    iso_now(),
                    source,
                ),
            )

    def append_status_history(self, standard_number: str, source_site: str, entry: dict[str, Any]) -> None:
        """追加状态变更记录到 status_history JSON 数组。
        entry: {status, announcement_number, announcement_date, changed_at, source}
        """
        row = self._db.fetchone(
            f"SELECT id, status_history FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
            (standard_number, source_site),
        )
        if not row:
            return
        import json as _json

        try:
            history = _json.loads(row["status_history"]) if row["status_history"] else []
        except _json.JSONDecodeError:
            history = []
        entry["changed_at"] = iso_now()
        history.append(entry)
        self._db.execute(
            f"UPDATE {CACHE_TABLE} SET status_history=? WHERE id=?",
            (_json.dumps(history, ensure_ascii=False), row["id"]),
        )

    def refresh(self, standard_number: str, source_site: str | None = None) -> None:
        """强制清除指定标准的缓存，下次查询将重新请求。"""
        if source_site:
            self._db.execute(
                f"DELETE FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
                (standard_number, source_site),
            )
        else:
            self._db.execute(f"DELETE FROM {CACHE_TABLE} WHERE standard_number=?", (standard_number,))

    def get_history(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """分页查询缓存历史记录，按缓存时间倒序。"""
        return self._db.fetchall(
            f"SELECT * FROM {CACHE_TABLE} ORDER BY cached_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def clear_all(self) -> None:
        """清空全部缓存数据。"""
        self._db.execute(f"DELETE FROM {CACHE_TABLE}")

    # ---- 内部 ----

    def _ensure_table(self) -> None:
        """创建缓存表及联合索引（幂等），供 __init__ 在启动时调用。

        三列（source_version/data_state/last_accessed_at）为缓存版本化所需，
        与迁移 v23 的 ALTER TABLE 对齐；此处于建表时一并定义，
        避免"迁移先于建表运行导致 ALTER 对不存在表失败"的缺列问题（D-1）。
        """
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL,
                source_site TEXT NOT NULL,
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'network',
                status_history TEXT NOT NULL DEFAULT '',
                source_version TEXT DEFAULT 'initial',
                data_state TEXT DEFAULT 'fresh',
                last_accessed_at TEXT
            )
        """)
        self._db.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_lookup ON {CACHE_TABLE}(standard_number, source_site)"
        )
        self._db.execute(f"CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON {CACHE_TABLE}(cached_at)")

    def _delete(self, row_id: int) -> None:
        """按主键删除单条缓存记录。"""
        self._db.execute(f"DELETE FROM {CACHE_TABLE} WHERE id=?", (row_id,))
