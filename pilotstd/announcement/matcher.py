# pilotstd/announcement/matcher.py
# 公告交叉比对器 — 公告标准清单 ↔ file_index，更新 announcement_cache

import json
import logging
from datetime import datetime
from typing import Any, Optional

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
        announcement_code: str = "",
        announcement_date: str = "",
        source_site: str = "announcement",
    ) -> dict[str, Any]:
        """逐条公告明细比对 file_index，命中则更新缓存。

        Args:
            items: [{std_code, std_name, replaces_code, publish_date,
                     implementation_date, announcement_title, attachment_url}, ...]
            announcement_code: 公告号，如 "2026年第19号"
            announcement_date: 公告落款日期

        Returns:
            {matched: int, updated: int, details: [str]}
        """
        result: dict[str, Any] = {"matched": 0, "updated": 0, "details": []}

        for item in items:
            std_code = item.get("std_code", "")
            replaces_code = item.get("replaces_code", "")

            # 解析标准编号为 logical_code + number
            parsed = self._parse_std_code(std_code)
            if not parsed:
                continue

            # 在 file_index 中查找匹配的标准
            matches = self._find_in_file_index(parsed["logical_code"], parsed["number"])

            # 区分匹配类型：std_code 匹配 → 新标准，replaces_code 匹配 → 旧标准被代替
            match_type = "new"  # 默认为新标准

            if not matches:
                # 也检查 replaces_code 是否匹配（被代替的旧标准）
                if replaces_code:
                    replaced_parsed = self._parse_std_code(replaces_code)
                    if replaced_parsed:
                        matches = self._find_in_file_index(
                            replaced_parsed["logical_code"], replaced_parsed["number"]
                        )
                        match_type = "replaced"

            if not matches:
                continue

            result["matched"] += 1
            for fi_row in matches:
                updated = self._update_cache(fi_row, item, match_type, source_site)
                if updated:
                    result["updated"] += 1
                    detail = (
                        f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
                    )
                    if match_type == "replaced":
                        detail += f" → 被代替: {std_code}"
                    result["details"].append(detail)

        return result

    def _parse_std_code(self, std_code: str) -> Optional[dict[str, Any]]:
        """解析标准编号字符串为 logical_code + number。委托公用解析器。"""
        from ..core.std_utils import parse_std_number

        r = parse_std_number(std_code)
        if r:
            return {"logical_code": r["code"], "number": r["number"]}
        return None

    def _find_in_file_index(
        self, logical_code: str, number: int
    ) -> list[dict[str, Any]]:
        """在 file_index 中查找匹配 logical_code + number 的记录。"""
        return self._db.fetchall(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=?",
            (logical_code, number),
        )

    def _update_cache(
        self,
        fi_row: dict[str, Any],
        item: dict[str, Any],
        match_type: str,
        source_site: str = "announcement",
    ) -> bool:
        """更新 announcement_cache 中的标准状态。

        match_type:
          "new" — 公告标准编号匹配到 file_index，此为新标准
          "replaced" — 公告代替标准号匹配到 file_index，此为被代替的旧标准

        写入字段全部来自公告原文，不凭空捏造。
        """
        std_number = f"{fi_row['logical_code']} {fi_row['number']}-{fi_row['year']}"
        now = datetime.now().isoformat()
        today = datetime.now().date()

        replaces_code = item.get("replaces_code", "")
        implementation_date = item.get("implementation_date", "")
        publish_date = item.get("publish_date", "")

        # 状态判断
        if match_type == "replaced":
            # 被代替的旧标准
            status = "被代替"
        elif implementation_date:
            # 有实施日期：比较今天与实施日期
            try:
                impl_date = datetime.fromisoformat(implementation_date).date()
                status = "即将实施" if today < impl_date else "现行"
            except (ValueError, TypeError):
                status = "现行"
        else:
            # 无实施日期（指导性技术文件）→ 直接现行
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

        # upsert
        existing = self._db.fetchone(
            f"SELECT id FROM {CACHE_TABLE} WHERE standard_number=?", (std_number,)
        )
        if existing:
            self._db.execute(
                f"UPDATE {CACHE_TABLE} SET result_json=?, cached_at=? WHERE id=?",
                (result_json, now, existing["id"]),
            )
        else:
            self._db.execute(
                f"INSERT INTO {CACHE_TABLE} "
                "(standard_number, source_site, result_json, cached_at, expires_at) "
                "VALUES (?, 'announcement', ?, ?, NULL)",  # expires_at=NULL = 永久
                (std_number, result_json, now),
            )

        logger.info(f"公告更新缓存: {std_number} → {status}")
        return True
