# 模块：项目//匹配器脚本
# 公告交叉比对器—公告标准清单↔_索引，更新_

import json
import logging
from datetime import datetime
from typing import Any, Optional, Set

from ..core.db import Database
from ..core.file_index import FILE_INDEX_TABLE
from ._content_cleaner import clean_announcement_content  # noqa: F401 — 重导出

logger = logging.getLogger(__name__)

CACHE_TABLE = "announcement_match"


class AnnouncementMatcher:
    """将公告中的标准清单与本地 file_index 交叉比对，
    发现匹配时更新 announcement_match。"""

    def __init__(self, db: Database) -> None:
        self._db = db

    def match_and_update(
        self,
        items: list[dict[str, Any]],
        source_site: str = "announcement",
    ) -> dict[str, Any]:
        """逐条公告明细比对 file_index，命中则写入两张表（批量模式）。

        入库前先按 announce_no 归一化：同一公告的所有条目强制统一 publish_date、
        announcement_title、standard_count，消除 HTML/PDF 混合解析导致的字段不一致。
        """
        result: dict[str, Any] = {"matched": 0, "updated": 0, "details": []}
        if not items:
            return result

        # ── 归一化：按公告号合并元数据 ──
        items = self._normalize(items)

        log_rows: list[tuple[Any, ...]] = []
        cache_rows: list[tuple[Any, ...]] = []
        now = datetime.now().isoformat()

        for item in items:
            self._process_item(item, source_site, now, log_rows, cache_rows, result)

        # 批量写入：先写记录表再写缓存表，减少数据库往返次数
        if log_rows:
            self._bulk_insert_records(log_rows)
            # 入库成功后回写_，确保有数据的公告不显示"待解析"
            announce_nos = {row[2] for row in log_rows}
            for anno in announce_nos:
                self._db.execute(
                    "UPDATE announcements SET parse_status='completed', updated_at=? WHERE announce_no=?",
                    (now, anno),
                )
        if cache_rows:
            self._bulk_upsert_cache(cache_rows)
        return result

    @staticmethod
    def _normalize(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按 announce_no 分组，统一各条目的公告级元数据。

        - publish_date: 取组内第一个非空值
        - announcement_title: 取组内第一个非空值
        - standard_count: 动态计算 = 该公告下条目总数

        ⚠️ 警告：standard_count 在此处仅表示"所属公告包含的条目数"，
        同一公告的所有记录共享此值，不代表全局唯一标准数。
        统计总数时必须使用 COUNT(*) 或 COUNT(DISTINCT standard_number)，
        严禁使用 SUM(standard_count)，否则会导致数据呈 N² 膨胀。
        """
        from collections import defaultdict

        # 按公告号分组，同公告条目汇聚以便统一元数据
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in items:
            anno = item.get("announce_no", "")
            if anno:
                groups[anno].append(item)

        for anno, group in groups.items():
            # 找第一个非空的_
            best_date = ""
            for it in group:
                d = it.get("publish_date", "")
                if d:
                    best_date = d
                    break
            # 找第一个非空的
            best_title = ""
            for it in group:
                t = it.get("announcement_title", "")
                if t:
                    best_title = t
                    break
            # 实际条目数（非全局去重数，仅表示同公告下条目数量）
            total = len(group)

            for idx, it in enumerate(group):
                if best_date:
                    it["publish_date"] = best_date
                if best_title:
                    it.setdefault("announcement_title", best_title)
                it["standard_count"] = total
                it["row_index"] = idx + 1  # 同公告内从 1 开始递增

        return items

    def _process_item(self, item, source_site, now, log_rows, cache_rows, result):
        """逐条处理公告明细：解析标准编号 → 查 file_index → 命中则写缓存和日志。"""
        std_code = item.get("std_code", "")
        replaces_code = item.get("replaces_code", "")
        pid = item.get("_pid", "")
        announce_no = item.get("announce_no", "")
        publish_date = item.get("publish_date", "")
        std_name = item.get("std_name", "")
        implement_date = item.get("implementation_date", "")
        expiry_date = item.get("expiry_date", "")
        confidence = item.get("confidence", 0.0)
        row_index = item.get("row_index", 0)

        parsed = self._parse_std_code(std_code)
        if not parsed:
            return

        matches = self._find_in_file_index(parsed["logical_code"], parsed["number"])
        match_type = "new"

        # 直接匹配失败时，用_尝试替代号匹配
        if not matches and replaces_code:
            replaced_parsed = self._parse_std_code(replaces_code)
            if replaced_parsed:
                matches = self._find_in_file_index(replaced_parsed["logical_code"], replaced_parsed["number"])
                match_type = "replaced"

        matched = 1 if matches else 0
        log_rows.append(
            (
                source_site,
                pid,
                announce_no,
                std_code,
                std_name or None,
                publish_date,
                implement_date,
                expiry_date,
                replaces_code,
                confidence,
                row_index,
                "draft",
                now,
                matched,
                item.get("announcement_title", "") or None,
                item.get("standard_count"),
            )
        )

        if not matches:
            return
        result["matched"] += 1
        for fi_row in matches:
            updated = self._build_cache_row(fi_row, item, match_type, source_site, now, cache_rows)
            if updated:
                result["updated"] += 1
                detail = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
                if match_type == "replaced":
                    detail += f" -> {std_code}"
                result["details"].append(detail)

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

    def _build_cache_row(
        self,
        fi_row,
        item,
        match_type,
        source_site,
        now,
        cache_rows,
    ) -> bool:
        """构建公告缓存行：根据实施日期判定状态（现行/即将实施/被代替），写入缓存列表。"""
        std_number = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
        today = datetime.now().date()
        implementation_date = item.get("implementation_date", "")
        publish_date = item.get("publish_date", "")

        # 状态判定优先级：被代替 > 即将实施 > 现行
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
            "replaces": item.get("replaces_code", ""),
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
        logger.info("公告更新缓存: %s -> %s", std_number, status)
        return True

    def _get_complete_pids(self, source_site: str) -> Set[str]:
        """返回已完全解析的公告 PID 集合（所有条目 std_name 均非空）。"""
        # 计数(*)=计数(_)确保该公告下所有条目都有名称
        cursor = self._db.execute(
            "SELECT pid FROM announcement_record "
            "WHERE source_site=? "
            "GROUP BY pid "
            "HAVING COUNT(*) = COUNT(std_name) AND COUNT(*) > 0",
            (source_site,),
        )
        rows = cursor.fetchall()
        return {row[0] for row in rows}

    _BATCH_SIZE = 50

    def _bulk_insert_records(self, rows: list[tuple[Any, ...]]) -> None:
        """批量插入公告记录到 announcement_record 表，按 _BATCH_SIZE 分批。"""
        if not rows:
            return
        # 分批插入：避免单条数据库查询过长导致性能下降
        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            self._db.execute(
                "INSERT OR IGNORE INTO announcement_record "
                "(source_site, pid, announce_no, standard_number, std_name, "
                "publish_date, implement_date, expiry_date, superseded_by, confidence, row_index,"
                " status, fetched_at, matched, announcement_title, standard_count) "
                f"VALUES {placeholders}",
                flat_values,
            )

    def _bulk_upsert_cache(self, rows: list[tuple[Any, ...]]) -> None:
        """批量 upsert 公告缓存到 announcement_match 表，按 _BATCH_SIZE 分批。"""
        if not rows:
            return
        # 用插入实现幂等插入或更新，以_为主键
        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            self._db.execute(
                "INSERT OR REPLACE INTO announcement_match "
                "(standard_number, source_site, result_json, cached_at, expires_at) "
                f"VALUES {placeholders}",
                flat_values,
            )
