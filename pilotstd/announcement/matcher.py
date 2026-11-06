# 模块：项目//匹配器脚本
# 公告交叉比对器—公告标准清单↔_索引，更新_

import json
import logging
from datetime import datetime
from typing import Any, Optional, Set

from pilotstd.core.status import Status
from pilotstd.core.time_utils import iso_now

from ..core.db import Database
from ..core.file_index import FILE_INDEX_TABLE
from ._content_cleaner import clean_announcement_content  # noqa: F401 — 重导出
from .parser import normalize_std_code
from .source_corrections import correct_std_code

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
        standard_category: str | None = None,
        update_existing: bool = False,
    ) -> dict[str, Any]:
        """逐条公告明细比对 file_index，命中则写入两张表（批量模式）。

        入库前先按 announce_no 归一化：同一公告的所有条目强制统一 publish_date、
        announcement_title、standard_count，消除 HTML/PDF 混合解析导致的字段不一致。
        standard_category：收藏分类语义化枚举（批次7），由适配器传入；
        缺省时按 source_site 精确映射（SOURCE_SITE_TO_STANDARD_TYPE），映射不到落 Unknown。
        """
        if standard_category is None:
            from pilotstd.constants.announce_types import SOURCE_SITE_TO_STANDARD_TYPE

            standard_category = SOURCE_SITE_TO_STANDARD_TYPE.get(source_site, "Unknown")

        result: dict[str, Any] = {
            "matched": 0,
            "updated": 0,
            "inserted": 0,
            "duplicates": 0,
            "details": [],
            "new_versions": [],
        }
        if not items:
            return result

        # ── 归一化：按公告号合并元数据 ──
        items = self._normalize(items)

        log_rows: list[tuple[Any, ...]] = []
        cache_rows: list[tuple[Any, ...]] = []
        now = iso_now()

        for item in items:
            self._process_item(item, source_site, standard_category, now, log_rows, cache_rows, result)

        # 批量写入：先写记录表再写缓存表，减少数据库往返次数
        if log_rows:
            inserted, ignored = self._bulk_insert_records(log_rows, update_existing=update_existing)
            result["inserted"] = inserted
            result["duplicates"] = ignored
            logger.info(
                "announcement_record 入库: inserted=%d duplicates=%d (items=%d)",  # i18n-allow: 内部入库日志
                inserted,
                ignored,
                len(log_rows),
            )
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

    def _process_item(self, item, source_site, standard_category, now, log_rows, cache_rows, result):
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
        std_code = correct_std_code(source_site, announce_no, std_name, std_code)
        # 入库唯一键口径：破折号归一（- / — / － / – / −）。否则同一标准以两种写法
        # 各落一行，UNIQUE(source_site,pid,standard_number,language) 拦不住。
        std_code = normalize_std_code(std_code)

        parsed = self._parse_std_code(std_code)
        if not parsed:
            return
        announce_year = int(parsed.get("year") or 0)

        matches = self._find_in_file_index(
            parsed["logical_code"], parsed["number"], announce_year
        )
        match_type = "new"

        # 直接匹配失败时，用_尝试替代号匹配
        if not matches and replaces_code:
            replaced_parsed = self._parse_std_code(replaces_code)
            if replaced_parsed:
                matches = self._find_in_file_index(
                    replaced_parsed["logical_code"], replaced_parsed["number"], announce_year
                )
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
                standard_category,  # 批次7：收藏分类（17 列）
                item.get("language", "") or "",
                item.get("foreign_name", "") or "",
            )
        )

        # 修改单只入 announcement_record，不写 announcement_match：
        # 它与本体共用标准号，写缓存会用修改单的实施日期覆盖本体状态（D4-3）。
        if "修改单" in (std_name or ""):
            return

        if not matches:
            return
        result["matched"] += 1
        self._write_matches(
            matches, item, match_type, source_site, now, cache_rows, result, parsed, announce_year, std_code
        )

    def _write_matches(
        self,
        matches: list[dict[str, Any]],
        item: dict[str, Any],
        match_type: str,
        source_site: str,
        now: str,
        cache_rows: list[tuple[Any, ...]],
        result: dict[str, Any],
        parsed: dict[str, Any],
        announce_year: int,
        std_code: str,
    ) -> None:
        """把命中的 index 行写成缓存：被代替用旧版年份，发现新版不覆盖旧行。"""
        written_new_keys: set[str] = set()
        for fi_row in matches:
            fi_year = int(fi_row.get("year") or 0)
            # 公告年代号更旧（重抓历史公告）时不得覆盖本地新版缓存
            if announce_year and fi_year and announce_year < fi_year:
                continue
            # “被代替”匹配的是**旧标准**：公告年代号是新标准的年份，不能据此判“发现新版”，
            # 否则旧标准永远写不进被代替缓存、还会生成不存在的标准号（2026-11-04 审计 P0）。
            cache_year = announce_year if match_type != "replaced" else 0
            # 缓存键的代号统一用**公告解析出的规范写法**（GB/T）；索引里可能存 GBT，
            # 若沿用索引写法会让按 standard_number 的查询（validity L1 / 前端）找不到。
            cache_code = (
                str(fi_row.get("logical_code") or "")
                if match_type == "replaced"
                else str(parsed.get("logical_code") or fi_row.get("logical_code") or "")
            )
            new_key = self._cache_key(cache_code, fi_row, cache_year)
            if new_key in written_new_keys:
                continue
            updated, is_new_version = self._build_cache_row(
                fi_row, item, match_type, source_site, now, cache_rows, cache_year, cache_code
            )
            if is_new_version:
                written_new_keys.add(new_key)
            if not updated:
                continue
            result["updated"] += 1
            detail = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
            if match_type == "replaced":
                detail += f" -> {std_code}"
            if is_new_version:
                # i18n-allow: 内部日志
                detail += f" (发现新版 {parsed['logical_code']} {parsed['number']}-{announce_year})"
                result.setdefault("new_versions", []).append(
                    f"{parsed['logical_code']} {parsed['number']}-{announce_year}"
                )
            result["details"].append(detail)

    def _parse_std_code(self, std_code: str) -> Optional[dict[str, Any]]:
        """解析标准编号字符串为 logical_code + number + year。委托公用解析器。

        ⚠️ 必须回传 `raw_code`（带斜杠形态，如 `GB/T`）而不是 `code`：`file_index`
        存的是解析器产出的 `logical_code`（`GB/T`、`DB11/T`），而 `parse_std_number`
        的 `code` 已去掉斜杠（`GBT`）。用 `code` 查索引会让全部斜杠类标准匹配失败
        （2026-11-04 生产实测：含斜杠公告 201,499 条，matched=1 仅 1 条）。
        """
        from ..core.std_utils import parse_std_number

        r = parse_std_number(std_code)
        if r:
            return {
                "logical_code": r.get("raw_code") or r["code"],
                "number": r["number"],
                "year": int(r.get("year") or 0),
            }
        return None

    @staticmethod
    def _cache_key(code: str, fi_row, year: int) -> str:
        """缓存键：`代号 编号[.分部]-年代号`（分部标准必须带分部号，见 D7 修复）。"""
        part = int(fi_row.get("part") or -1)
        suffix = f".{part}" if part > 0 else ""
        return f"{code} {fi_row['number']}{suffix}-{year}"

    def _find_in_file_index(
        self, logical_code: str, number: int, year: int = 0
    ) -> list[dict[str, Any]]:
        """在 file_index 中查找匹配记录：代号双向兼容 + 同号多版本按年代号优先。

        - 代号：`GB/T` ↔ `GBT` 双向兼容（历史行可能存任一种写法）；
          用 `IN (?, ?)` 而不是 `REPLACE(...)`，避免函数包列导致索引失效；
        - 年代号：先找同年代号的行；没有再退回同号全部行（用于“发现新版”判定）。
        """
        normalized = logical_code.replace("/", "")
        slash = f"{normalized[:2]}/{normalized[2:]}" if len(normalized) > 2 else normalized
        codes = tuple({logical_code, normalized, slash})
        placeholders = ",".join("?" for _ in codes)
        base = (
            f"SELECT * FROM {FILE_INDEX_TABLE} "
            f"WHERE logical_code IN ({placeholders}) AND number=?"
        )
        params: tuple[Any, ...] = (*codes, number)
        if year:
            same_year = self._db.fetchall(base + " AND year=?", (*params, year))
            if same_year:
                return same_year
        return self._db.fetchall(base, params)

    def _build_cache_row(
        self,
        fi_row,
        item,
        match_type,
        source_site,
        now,
        cache_rows,
        announce_year: int = 0,
        cache_code: str = "",
    ) -> tuple[bool, bool]:
        """构建公告缓存行：根据实施日期判定状态（现行/即将实施/被代替），写入缓存列表。

        返回 `(是否写入, 是否“发现新版”)`。

        **发现新版**：公告年代号大于本地文件年代号时，以公告自身年代号建缓存键
        （如 `GB/T 1234-2020`），并标注 `is_new_version=True` / `local_year`，
        **不覆盖**本地旧版（2010）的状态行——否则旧版会被贴上新版状态，且
        永远不会有“本地缺少新版”的对比结果（2026-11-04 实测）。
        """
        fi_year = int(fi_row.get("year") or 0)
        code = cache_code or str(fi_row.get("logical_code") or "")
        is_new_version = bool(announce_year and fi_year and announce_year > fi_year)
        std_number = self._cache_key(code, fi_row, announce_year if is_new_version else fi_year)
        today = datetime.now().date()
        implementation_date = item.get("implementation_date", "")
        publish_date = item.get("publish_date", "")

        # 状态判定优先级：被代替 > 即将实施 > 现行
        if match_type == "replaced":
            status = Status.SUPERSEDED.value
        elif implementation_date:
            try:
                impl_date = datetime.fromisoformat(implementation_date).date()
                status = Status.UPCOMING.value if today < impl_date else Status.ACTIVE.value
            except (ValueError, TypeError):
                # 已知可忽略：实施日期解析失败默认"现行"
                status = Status.ACTIVE.value
        else:
            status = Status.ACTIVE.value

        cache_data = {
            "status": status,
            "standard_name": (item.get("std_name", "") if is_new_version else fi_row["std_name"])
            or item.get("std_name", "")
            or fi_row["std_name"],
            "replaces": item.get("replaces_code", ""),
            "publish_date": publish_date,
            "implementation_date": implementation_date,
            "announcement_title": item.get("announcement_title", ""),
            "attachment_url": item.get("attachment_url", ""),
            "attachment_path": item.get("attachment_path", ""),
            "match_status": "new_version" if is_new_version else "exact",
            "is_new_version": is_new_version,
            "local_year": fi_year if is_new_version else None,
            "is_adopted": False,
            "source_site": source_site,
        }

        result_json = json.dumps(cache_data, ensure_ascii=False)
        cache_rows.append((std_number, source_site, result_json, now, None))
        logger.info(
            "公告更新缓存: %s -> %s%s",  # i18n-allow: 内部日志
            std_number,
            status,
            "（发现新版）" if is_new_version else "",  # i18n-allow: 内部日志
        )
        return True, is_new_version

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

    def _bulk_insert_records(
        self, rows: list[tuple[Any, ...]], update_existing: bool = False
    ) -> tuple[int, int]:
        """批量插入公告记录到 announcement_record 表，返回 (实际插入, 被唯一键忽略)。

        `INSERT OR IGNORE` 会静默丢弃冲突行，调用方曾因此看不到"解析 42 条、入库 21 条"
        的差异；这里用 rowcount 把两个数都暴露出来。

        `update_existing=True`（仅单条公告重解析用）改为 `ON CONFLICT DO UPDATE`：
        命中唯一键时**原地更新**，保留 row id —— 否则 `DELETE + INSERT` 会因
        `user_favorites.record_id` 等外键引用而直接 `FOREIGN KEY constraint failed`
        （2026-11-03 线上 reparse 30 号实测）。
        """
        if not rows:
            return 0, 0
        suffix = ""
        if update_existing:
            suffix = (
                " ON CONFLICT(source_site, pid, standard_number, language) DO UPDATE SET "
                "announce_no=excluded.announce_no, std_name=excluded.std_name, "
                "publish_date=excluded.publish_date, implement_date=excluded.implement_date, "
                "expiry_date=excluded.expiry_date, superseded_by=excluded.superseded_by, "
                "confidence=excluded.confidence, row_index=excluded.row_index, "
                "status=excluded.status, fetched_at=excluded.fetched_at, "
                "matched=excluded.matched, announcement_title=excluded.announcement_title, "
                "standard_count=excluded.standard_count, standard_type=excluded.standard_type, "
                "foreign_name=excluded.foreign_name"
            )
        inserted = 0
        # 分批插入：避免单条数据库查询过长导致性能下降
        for i in range(0, len(rows), self._BATCH_SIZE):
            batch = rows[i : i + self._BATCH_SIZE]
            placeholders = ",".join("(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)" for _ in batch)
            flat_values = [item for row in batch for item in row]
            cur = self._db.execute(
                "INSERT INTO announcement_record "
                "(source_site, pid, announce_no, standard_number, std_name, "
                "publish_date, implement_date, expiry_date, superseded_by, confidence, row_index,"
                " status, fetched_at, matched, announcement_title, standard_count, standard_type,"
                " language, foreign_name) "
                f"VALUES {placeholders}"
                + (suffix if update_existing else " ON CONFLICT DO NOTHING"),
                flat_values,
            )
            inserted += int(cur.rowcount or 0)
        return inserted, len(rows) - inserted

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
