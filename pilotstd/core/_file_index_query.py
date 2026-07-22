# pilotstd/core/_file_index_query.py
# 文件索引查询混入 — 从 file_index.py 提取
# THREADING: single-threaded, no lock needed

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from pilotstd.models import ParsedStdInfo

# 核心表名常量，统一管理避免硬编码字符串散布
FILE_INDEX_TABLE = "file_index"
NETWORK_CACHE_TABLE = "standard_info_cache"
ANNOUNCEMENT_CACHE_TABLE = "announcement_match"

logger = logging.getLogger(__name__)


class _FileIndexQueryMixin:
    """文件索引查询方法集合（混入 FileIndexRepository）。

    所有方法通过 self._db 访问数据库连接，_db 由 FileIndexRepository.__init__ 注入。
    """

    # ---- 基础读取 ----

    def get(self, file_path: str) -> Optional[dict[str, Any]]:
        return self._db.fetchone(f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))

    def get_all(self) -> list[dict[str, Any]]:
        return self._db.fetchall(f"SELECT * FROM {FILE_INDEX_TABLE} ORDER BY logical_code, number, part")

    def find_by_standard(
        self, logical_code: str, number: int, year: int, part: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """查找同标准号的所有索引记录（用于去重：分类变化致旧路径残留）。"""
        part_val = part if part is not None else -1
        return self._db.fetchall(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=? AND year=? AND part=?",
            (logical_code, number, year, part_val),
        )

    def find_by_hash(self, file_hash: str) -> Optional[dict[str, Any]]:
        """通过文件哈希查找（用于检测移动/重命名）。"""
        return self._db.fetchone(f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_hash=?", (file_hash,))

    # ---- 统计 ----

    def count(self) -> int:
        """返回索引表中的记录总数。"""
        row = self._db.fetchone(f"SELECT COUNT(*) as cnt FROM {FILE_INDEX_TABLE}")
        return row["cnt"] if row else 0

    def get_status_stats(self) -> dict[str, int]:
        """返回按状态分组的统计：现行/废止/待确认/即将实施数量。"""
        try:
            rows = self._db.fetchall(
                f"SELECT status, COUNT(*) as cnt FROM {FILE_INDEX_TABLE} WHERE status IS NOT NULL GROUP BY status"
            )
            s = {r["status"]: r["cnt"] for r in rows}
        except Exception:
            return {"current": 0, "expired": 0, "pending": 0, "upcoming": 0}
        return {
            "current": s.get("现行", 0),
            "expired": s.get("废止", 0) + s.get("被代替", 0),
            "pending": s.get("待确认", 0),
            "upcoming": s.get("即将实施", 0),
        }

    # ---- 缓存恢复 ----

    def restore_parsed(self, file_path: str) -> Optional["ParsedStdInfo"]:
        """从索引恢复 ParsedStdInfo，同时查缓存填充查询结果字段。"""
        row = self.get(file_path)
        if not row:
            return None
        import os

        from ..models import ParsedStdInfo

        info = ParsedStdInfo(
            raw_filename=os.path.basename(file_path),
            logical_code=row["logical_code"],
            number=row["number"],
            raw_number=row.get("raw_number", ""),
            year=row["year"],
            part=row["part"] if row["part"] != -1 else None,
            std_name=row["std_name"],
            source_path=file_path,
        )
        self._restore_cache_fields(info)
        return info

    def _restore_cache_fields(self, info: "ParsedStdInfo") -> None:
        """从缓存表恢复查询结果字段。

        优先级：网络缓存（主数据源）> 公告缓存（补充）。
        网络缓存须检查过期时间，公告缓存永久有效。
        """
        std_num = info.get_full_number()

        row = self._db.fetchone(
            f"SELECT result_json FROM {NETWORK_CACHE_TABLE} WHERE standard_number = ? LIMIT 1",
            (std_num,),
        )
        if row and row["result_json"]:
            self._apply_cache_result(row["result_json"], info)
            return

        ann_row = self._db.fetchone(
            f"SELECT result_json FROM {ANNOUNCEMENT_CACHE_TABLE} WHERE standard_number = ? LIMIT 1",
            (std_num,),
        )
        if ann_row and ann_row["result_json"]:
            self._apply_cache_result(ann_row["result_json"], info)

    @staticmethod
    def _apply_cache_result(result_json: str, info: "ParsedStdInfo") -> None:
        """将缓存的 JSON 结果应用到 ParsedStdInfo 对象。"""
        try:
            cached = json.loads(result_json)
            if cached.get("match_status") == "exact":
                info.effect_status = cached.get("status", "")
                info.found_name = cached.get("standard_name", "")
                info.is_adopted = cached.get("is_adopted", False)
                info.match_status = "exact"
        except (json.JSONDecodeError, TypeError):
            pass

    # ---- 移动检测 ----

    def find_moved_files(self, candidates: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """检测文件移动/重命名：哈希命中但路径不同的返回原索引记录。
        Args:
            candidates: [(file_path, file_hash), ...] 未被路径匹配到的文件列表
        Returns:
            [{"old_path": ..., "new_path": ..., "logical_code": ..., ...}, ...]
        """
        result = []
        for new_path, file_hash in candidates:
            if not file_hash:
                continue
            row = self.find_by_hash(file_hash)
            if row and row["file_path"] != new_path:
                result.append(
                    {
                        "old_path": row["file_path"],
                        "new_path": new_path,
                        "logical_code": row["logical_code"],
                        "number": row["number"],
                        "year": row["year"],
                        "part": row["part"],
                        "std_name": row["std_name"],
                    }
                )
        return result

    # ---- 联合查询 ----

    def get_full_info(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """联合本地文件索引与两个缓存表，返回离线完整信息。
        JOIN 使用 LIKE 前缀匹配，兼容新旧两种连接号格式。
        网络缓存优先，过期后回退到公告缓存。
        """
        rows = self._db.fetchall(
            f"SELECT fi.*, "
            f"nc.result_json AS nc_result_json, "
            f"nc.cached_at AS nc_cached_at, "
            f"ac.result_json AS ac_result_json, "
            f"ac.cached_at AS ac_cached_at "
            f"FROM {FILE_INDEX_TABLE} fi "
            f"LEFT JOIN {NETWORK_CACHE_TABLE} nc "
            f"ON nc.standard_number LIKE (fi.logical_code || ' ' || fi.number || '%') "
            f"LEFT JOIN {ANNOUNCEMENT_CACHE_TABLE} ac "
            f"ON ac.standard_number LIKE (fi.logical_code || ' ' || fi.number || '%') "
            f"WHERE fi.logical_code = ? AND fi.number = ?",
            (logical_code, number),
        )
        result = []
        for row in rows:
            info = {
                "file_path": row["file_path"],
                "logical_code": row["logical_code"],
                "number": row["number"],
                "year": row["year"],
                "part": row["part"] if row["part"] != -1 else None,
                "std_name": row["std_name"],
                "effect_status": "",
                "found_name": "",
                "is_adopted": False,
                "match_status": "",
                "cached_at": "",
            }
            # 优先网络缓存，回退到公告缓存
            cache_json = None
            if row["nc_result_json"]:
                cache_json = row["nc_result_json"]
                info["cached_at"] = row["nc_cached_at"] or ""
            if cache_json is None and row["ac_result_json"]:
                cache_json = row["ac_result_json"]
                info["cached_at"] = row["ac_cached_at"] or ""
            if cache_json:
                try:
                    cached = json.loads(cache_json)
                    info["effect_status"] = cached.get("status", "")
                    info["found_name"] = cached.get("standard_name", "")
                    info["is_adopted"] = cached.get("is_adopted", False)
                    info["match_status"] = cached.get("match_status", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(info)
        return result
