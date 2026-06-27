# pilotstd/query/cache.py
# 查询结果本地持久化缓存（SQLite）— 双表回退，事件驱动失效

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from ..core.db import Database
from ..core.file_index import ANNOUNCEMENT_CACHE_TABLE
from .models import QueryResult

CACHE_TABLE = "standard_info_cache"
DEFAULT_ACTIVE_TTL_DAYS = 30
DEFAULT_INACTIVE_TTL_DAYS = 7


class CacheRepository:
    """标准信息缓存仓库。先查网络查询缓存，不命中回退公告缓存。

    缓存失效由事件驱动（网络查询返回"被代替"或公告比对命中），不由时间驱动。
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

    # ---- 公共 API ----

    def get(self, standard_number: str, source_site: str) -> Optional[QueryResult]:
        """查缓存：先 standard_info_cache，不命中回退 announcement_match。"""
        # 先查网络查询缓存
        row = self._db.fetchone(
            f"SELECT * FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
            (standard_number, source_site),
        )
        if row:
            # 过滤 QueryResult 不接受的字段（适配器可能挂临时属性，如 csres 的 _csres_detail_url）
            _valid = {f.name for f in QueryResult.__dataclass_fields__.values()}
            data = {k: v for k, v in json.loads(row["result_json"]).items() if k in _valid}
            return QueryResult(**data)

        # 不命中则回退查公告缓存
        ann_row = self._db.fetchone(
            f"SELECT standard_number, result_json FROM {ANNOUNCEMENT_CACHE_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if ann_row:
            data = json.loads(ann_row["result_json"])
            # 公告缓存 JSON 不含 standard_number，需注入
            data["standard_number"] = ann_row["standard_number"]
            data.setdefault("source_site", "announcement")
            # 过滤 QueryResult 不接受的公告元数据字段
            _valid = {f.name for f in QueryResult.__dataclass_fields__.values()}
            data = {k: v for k, v in data.items() if k in _valid}
            return QueryResult(**data)

        return None

    def put(self, result: QueryResult, source: str = "network") -> None:
        """写入缓存。source: network / announcement / manual。"""
        existing = self._db.fetchone(
            f"SELECT id, source FROM {CACHE_TABLE} WHERE standard_number=? AND source_site=?",
            (result.standard_number, result.source_site),
        )
        result_json = json.dumps(result.__dict__, ensure_ascii=False)

        if existing:
            # 已有记录时不覆盖 source（保留首次数据来源标记）
            self._db.execute(
                f"UPDATE {CACHE_TABLE} SET result_json=?, cached_at=? WHERE id=?",
                (result_json, datetime.now().isoformat(), existing["id"]),
            )
        else:
            self._db.execute(
                f"INSERT INTO {CACHE_TABLE} (standard_number, source_site, "
                "result_json, cached_at, source) VALUES (?, ?, ?, ?, ?)",
                (
                    result.standard_number,
                    result.source_site,
                    result_json,
                    datetime.now().isoformat(),
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
        entry["changed_at"] = datetime.now().isoformat()
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
        return self._db.fetchall(
            f"SELECT * FROM {CACHE_TABLE} ORDER BY cached_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )

    def clear_all(self) -> None:
        self._db.execute(f"DELETE FROM {CACHE_TABLE}")

    # ---- 内部 ----

    def _ensure_table(self) -> None:
        self._db.execute(f"""
            CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                standard_number TEXT NOT NULL,
                source_site TEXT NOT NULL,
                result_json TEXT NOT NULL,
                cached_at TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'network',
                status_history TEXT NOT NULL DEFAULT ''
            )
        """)
        self._db.execute(
            f"CREATE UNIQUE INDEX IF NOT EXISTS idx_cache_lookup ON {CACHE_TABLE}(standard_number, source_site)"
        )
        self._db.execute(f"CREATE INDEX IF NOT EXISTS idx_cache_cached_at ON {CACHE_TABLE}(cached_at)")

    def _delete(self, row_id: int) -> None:
        self._db.execute(f"DELETE FROM {CACHE_TABLE} WHERE id=?", (row_id,))
