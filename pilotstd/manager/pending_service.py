# pilotstd/manager/pending_service.py
# PendingService — 待确认清单管理 + 下载等待队列 + 本地缓存查询

import json
import logging
from datetime import datetime, timedelta

from ..query.models import QueryResult
from ..query.search_strategy import MATCH_SCORE

logger = logging.getLogger(__name__)


class PendingService:
    """待确认清单与下载等待队列管理服务。

    负责：
      - 待确认项的增删改查（pending_lookup 表）
      - 下载等待队列管理（download_queue 表，未到公开期的标准）
      - 本地缓存查询（standard_info_cache + announcement_cache），供 GUI 离线查询
    """

    def __init__(self, db, file_index):
        """注入依赖。

        Args:
            db: Database 实例
            file_index: FileIndexRepository 实例（提供 _db 访问）
        """
        self._db = db
        self._file_index = file_index

    # ── 待确认清单 ─────────────────────────────────────────────

    def record_pending(self, pending_items: list) -> None:
        """将待确认项写入 pending_lookup 表（已存在则跳过）。"""
        now = datetime.now().isoformat()
        for parsed in pending_items:
            std_num = parsed.get_full_number()
            existing = self._db.fetchone(
                "SELECT id FROM pending_lookup WHERE standard_number=? AND status='pending'",
                (std_num,))
            if existing:
                continue
            self._db.execute(
                "INSERT INTO pending_lookup (standard_number, std_name, found_name, "
                "found_number, match_status, effect_status, score, source_site, "
                "file_path, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
                (std_num, parsed.std_name, parsed.found_name,
                 getattr(parsed, 'found_number', ''), parsed.match_status,
                 parsed.effect_status, MATCH_SCORE.get(parsed.match_status, 0),
                 getattr(parsed, 'found_source_site', ''), parsed.source_path or '',
                 now))

    def resolve_pending(self, pending_items: list, resolution: str) -> None:
        """标记待确认项为已处理。resolution: 'discarded' | 'confirmed'"""
        now = datetime.now().isoformat()
        for parsed in pending_items:
            std_num = parsed.get_full_number()
            self._db.execute(
                "UPDATE pending_lookup SET status=?, resolved_at=? "
                "WHERE standard_number=? AND status='pending'",
                (resolution, now, std_num))

    def get_pending_items(self) -> list:
        """获取所有待确认项。"""
        return self._db.fetchall(
            "SELECT * FROM pending_lookup WHERE status='pending' ORDER BY created_at")

    # ── 下载等待队列 ───────────────────────────────────────────

    def enqueue_download_wait(self, parsed) -> None:
        """写入下载等待队列（未到公开期的标准）。"""
        num = getattr(parsed, 'found_number', '') or parsed.get_full_number()
        name = parsed.found_name or parsed.std_name or ''
        pub_str = getattr(parsed, 'found_publish_date', '')
        if not pub_str:
            return
        try:
            pub_dt = datetime.strptime(pub_str, "%Y-%m-%d")
        except ValueError:
            return
        available_dt = pub_dt + timedelta(days=28)
        existing = self._db.fetchone(
            "SELECT id FROM download_queue WHERE standard_number=? AND status='waiting'",
            (num,))
        if existing:
            return
        self._db.execute(
            "INSERT INTO download_queue (standard_number, standard_name, "
            "publish_date, expected_available, created_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'waiting')",
            (num, name, pub_str, available_dt.isoformat(), datetime.now().isoformat()))

    def get_due_downloads(self) -> list:
        """获取公开期已到的下载等待项。"""
        return self._db.fetchall(
            "SELECT * FROM download_queue WHERE status='waiting' AND expected_available <= ?",
            (datetime.now().isoformat(),))

    def remove_download_queue(self, standard_number: str) -> None:
        """从下载等待队列中移除指定项。"""
        self._db.execute(
            "UPDATE download_queue SET status='done' WHERE standard_number=?",
            (standard_number,))

    # ── 重试限制 ────────────────────────────────────────────

    def increment_requery_count(self, standard_number: str) -> int:
        """重新查询次数 +1，返回当前次数。无行时自动插入。"""
        cur = self._db.fetchone(
            "SELECT requery_count FROM pending_lookup WHERE standard_number=?",
            (standard_number,))
        if cur is None:
            # 自动插入新行，初始 requery_count=1
            self._db.execute(
                "INSERT INTO pending_lookup (standard_number, requery_count) VALUES (?, 1)",
                (standard_number,))
            return 1
        new_count = (cur.get("requery_count", 0) or 0) + 1
        self._db.execute(
            "UPDATE pending_lookup SET requery_count=? WHERE standard_number=?",
            (new_count, standard_number))
        return new_count

    def get_requery_count(self, standard_number: str) -> int:
        """返回当前重试次数。"""
        cur = self._db.fetchone(
            "SELECT requery_count FROM pending_lookup WHERE standard_number=?",
            (standard_number,))
        return (cur.get("requery_count", 0) or 0) if cur else 0

    def is_requery_exhausted(self, standard_number: str) -> bool:
        """重试次数 >= 3 → 不允许再自动查询。"""
        return self.get_requery_count(standard_number) >= 3

    def mark_manual_required(self, standard_number: str) -> None:
        """标记为'建议手动查询'，从 pending 循环中移除。"""
        self._db.execute(
            "UPDATE pending_lookup SET status='manual_required', "
            "resolved_at=? WHERE standard_number=?",
            (datetime.now().isoformat(), standard_number))

    # ── 本地缓存查询 ─────────────────────────────────────────

    def query_local_cache(self, parsed_list: list) -> list:
        """从本地缓存（standard_info_cache + announcement_cache）查询标准信息。
        返回 [(idx, QueryResult), ...]，供 GUI 离线查询模式使用。
        """
        results = []
        for i, parsed in enumerate(parsed_list):
            std_num = parsed.get_full_number()
            # 先查网络缓存
            row = self._db.fetchone(
                "SELECT result_json FROM standard_info_cache "
                "WHERE standard_number = ? LIMIT 1", (std_num,))
            result_json = row.get("result_json") if row else None
            source = "local_db"
            if not result_json:
                # 回退到公告缓存
                row = self._db.fetchone(
                    "SELECT result_json FROM announcement_cache "
                    "WHERE standard_number = ? LIMIT 1", (std_num,))
                result_json = row.get("result_json") if row else None
                source = "local_db(公告)"
            if result_json:
                try:
                    cached = json.loads(result_json)
                    result = QueryResult(
                        standard_number=std_num,
                        standard_name=cached.get("standard_name", ""),
                        status=cached.get("status", ""),
                        match_status=cached.get("match_status", ""),
                        is_adopted=cached.get("is_adopted", False),
                        source_site=source,
                        hcno=cached.get("hcno", ""),
                        replaces=cached.get("replaces", ""),
                        publish_date=cached.get("publish_date", ""),
                        implementation_date=cached.get("implementation_date", ""),
                    )
                except (json.JSONDecodeError, TypeError):
                    result = QueryResult(standard_number=std_num,
                                         error_message="缓存解析失败", source_site=source)
            else:
                result = QueryResult(standard_number=std_num,
                                     error_message="本地数据库未找到", source_site="local_db")
            results.append((i, result))
        return results
