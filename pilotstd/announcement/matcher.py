# pilotstd/announcement/matcher.py
# 公告交叉比对器 — 公告标准清单 ↔ file_index，更新 announcement_cache

import json
import logging
from datetime import datetime
from typing import Any, Optional, Set

from ..core.db import Database
from ..core.file_index import FILE_INDEX_TABLE

logger = logging.getLogger(__name__)

CACHE_TABLE = "announcement_cache"


class AnnouncementMatcher:
    """将公告中的标准清单与本地 file_index 交叉比对，
    发现匹配时更新 announcement_cache。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def match_and_update(
        self,
        items: list[dict[str, Any]],
        source_site: str = "announcement",
    ) -> dict[str, Any]:
        """逐条公告明细比对 file_index，命中则写入两张表（批量模式）。

        全量日志写入 announcement_fetch_log（含未匹配的），
        缓存仅写入 announcement_cache（仅匹配 file_index 的记录）。
        pid 从每个 item 的 _pid 字段提取。
        """
        result: dict[str, Any] = {"matched": 0, "updated": 0, "details": []}
        if not items:
            return result

        log_rows: list[tuple[Any, ...]] = []
        cache_rows: list[tuple[Any, ...]] = []
        now = datetime.now().isoformat()

        for item in items:
            std_code = item.get("std_code", "")
            replaces_code = item.get("replaces_code", "")
            pid = item.get("_pid", "")
            announce_no = item.get("announce_no", "")
            publish_date = item.get("publish_date", "")
            std_name = item.get("std_name", "")

            parsed = self._parse_std_code(std_code)
            if not parsed:
                continue

            matches = self._find_in_file_index(parsed["logical_code"], parsed["number"])
            match_type = "new"

            if not matches:
                if replaces_code:
                    replaced_parsed = self._parse_std_code(replaces_code)
                    if replaced_parsed:
                        matches = self._find_in_file_index(
                            replaced_parsed["logical_code"],
                            replaced_parsed["number"],
                        )
                        match_type = "replaced"

            matched = 1 if matches else 0

            # 全量日志：所有条目都记录
            log_rows.append(
                (
                    source_site,
                    pid,
                    announce_no,
                    std_code,
                    std_name or None,
                    publish_date,
                    now,
                    matched,
                )
            )

            if not matches:
                continue

            result["matched"] += 1
            for fi_row in matches:
                updated = self._build_cache_row(fi_row, item, match_type, source_site, now, cache_rows)
                if updated:
                    result["updated"] += 1
                    detail = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
                    if match_type == "replaced":
                        detail += f" → 被代替: {std_code}"
                    result["details"].append(detail)

        # 批量写入
        if log_rows:
            self._bulk_insert_fetch_log(log_rows)
        if cache_rows:
            self._bulk_upsert_cache(cache_rows)

        return result

    def _parse_std_code(self, std_code: str) -> Optional[dict[str, Any]]:
        """解析标准编号字符串为 logical_code + number。委托公用解析器。"""
        from ..core.std_utils import parse_std_number

        r = parse_std_number(std_code)
        if r:
            return {"logical_code": r["code"], "number": r["number"]}
        return None

    def _find_in_file_index(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """在 file_index 中查找匹配 logical_code + number 的记录。"""
        return self._db.fetchall(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=?",
            (logical_code, number),
        )

    # ── 批量写入辅助方法 ──

    def _build_cache_row(
        self,
        fi_row: dict[str, Any],
        item: dict[str, Any],
        match_type: str,
        source_site: str,
        now: str,
        cache_rows: list[tuple[Any, ...]],
    ) -> bool:
        """构建一条 announcement_cache 行数据，追加到 cache_rows。
        逻辑与原 _update_cache 一致：判断状态 → 构建 JSON → 入列。
        """
        std_number = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
        today = datetime.now().date()

        replaces_code = item.get("replaces_code", "")
        implementation_date = item.get("implementation_date", "")
        publish_date = item.get("publish_date", "")

        if match_type == "replaced":
            status = "被代替"
        elif implementation_date:
            try:
                impl_date = datetime.fromisoformat(implementation_date).date()
                status = "即将实施" if today < impl_date else "现行"
            except (ValueError, TypeError):
                status = "现行"
        else:
            status = "现行"

        cache_data = {
            "status": status,
            "standard_name": fi_row["std_name"] or item.get("std_name", ""),
            "replaces": replaces_code,
            "publish_date": publish_date,
            "implementation_date": implementation_date,
            "announcement_title": item.get("announcement_title", ""),
            "attachment_url": item.get("attachment_url", ""),
            "attachment_path": item.get("attachment_path", ""),
            "match_status": "exact",
            "is_adopted": False,
            "source_site": source_site,
        }

        result_json = json.dumps(cache_data, ensure_ascii=False)
        cache_rows.append((std_number, source_site, result_json, now, None))
        logger.info("公告更新缓存: %s → %s", std_number, status)
        return True

    def _get_complete_pids(self, source_site: str) -> Set[str]:
        """返回该站点下已完全解析的公告 PID 集合。
        完全解析 = 该公告下所有标准条目的 std_name 均非空。
        """
        cursor = self._db.execute(
            "SELECT pid FROM announcement_fetch_log "
            "WHERE source_site=? "
            "GROUP BY pid "
            "HAVING COUNT(*) = COUNT(std_name) AND COUNT(*) > 0",
            (source_site,),
        )
        rows = cursor.fetchall()
        return {row[0] for row in rows}

    _BATCH_SIZE = 50  # SQLite 参数上限 999，每批 50 条远低于上限

    def _bulk_insert_fetch_log(self, rows: list[tuple[Any, ...]]) -> None:
        """批量 INSERT OR IGNORE 到 announcement_fetch_log（分批写入，避免 too many SQL variables）。"""
        if not rows:
            return

        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            self._db.execute(
                "INSERT OR IGNORE INTO announcement_fetch_log "
                "(source_site, pid, announce_no, standard_number, std_name, "
                "publish_date, fetched_at, matched) "
                f"VALUES {placeholders}",
                flat_values,
            )

    def _bulk_upsert_cache(self, rows: list[tuple[Any, ...]]) -> None:
        """批量 INSERT OR REPLACE 到 announcement_cache（分批+事务包裹）。"""
        if not rows:
            return

        self._db.execute("BEGIN TRANSACTION;")
        try:
            for i in range(0, len(rows), self._BATCH_SIZE):
                batch = rows[i : i + self._BATCH_SIZE]
                placeholders = ",".join("(?,?,?,?,?)" for _ in batch)
                flat_values = [item for row in batch for item in row]
                self._db.execute(
                    "INSERT OR REPLACE INTO announcement_cache "
                    "(standard_number, source_site, result_json, cached_at, expires_at) "
                    f"VALUES {placeholders}",
                    flat_values,
                )
            self._db.execute("COMMIT;")
        except Exception:
            self._db.execute("ROLLBACK;")
            raise
