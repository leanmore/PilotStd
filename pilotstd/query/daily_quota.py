# pilotstd/query/daily_quota.py
# 每日查询配额追踪器（SQLite 持久化）
# 日限额统一从 site_config.SiteState.daily_limit 读取，此处不再硬编码

import logging
import threading
from datetime import date
from typing import Dict

from ..core.db import Database

logger = logging.getLogger(__name__)

# 详情页查询保底次数——搜索不能耗尽，留这些给详情页
DETAIL_RESERVE = {
    "csres": 30,
    "njbz365": 50,
    "hbba": 30,
}


class DailyQuotaTracker:
    """按站点追踪每日查询次数，持久化到 SQLite。"""

    def __init__(self, db: Database, limits: Dict[str, int] | None = None):
        self._db = db
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS daily_quota (
                site_name TEXT NOT NULL,
                query_date TEXT NOT NULL,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (site_name, query_date)
            )
        """)
        self._today = str(date.today())
        self._limits = dict(limits or {})
        self._lock = threading.RLock()
        self._ensure_today_rows()

    def _ensure_date(self) -> None:
        """跨天自动更新日期标记并初始化新日期的配额行"""
        today = str(date.today())
        if self._today != today:
            self._today = today
            self._ensure_today_rows()

    def _ensure_today_rows(self) -> None:
        """确保所有已注册站点在今天有配额记录行。"""
        for site in self._limits:
            row = self._db.fetchone(
                "SELECT count FROM daily_quota WHERE site_name=? AND query_date=?",
                (site, self._today),
            )
            if row is None:
                self._db.execute(
                    "INSERT INTO daily_quota (site_name, query_date, count) VALUES (?, ?, 0)",
                    (site, self._today),
                )

    def get_remaining(self, site_name: str) -> int:
        """返回该站点今日剩余可用次数。"""
        with self._lock:
            self._ensure_date()
            limit = self._limits.get(site_name, 500)
            row = self._db.fetchone(
                "SELECT count FROM daily_quota WHERE site_name=? AND query_date=?",
                (site_name, self._today),
            )
            if row is None:
                return limit
            used: int = row["count"]
            return max(0, limit - used)

    def record_usage(self, site_name: str, count: int) -> int:
        """记录消耗次数，返回剩余可用次数。"""
        with self._lock:
            self._ensure_date()
            # 确保该站点的今日行存在（_ensure_today_rows 只覆盖 _limits 中的站点）
            existing = self._db.fetchone(
                "SELECT count FROM daily_quota WHERE site_name=? AND query_date=?",
                (site_name, self._today),
            )
            if existing is None:
                self._db.execute(
                    "INSERT INTO daily_quota (site_name, query_date, count) VALUES (?, ?, 0)",
                    (site_name, self._today),
                )
            self._db.execute(
                "UPDATE daily_quota SET count = count + ? WHERE site_name=? AND query_date=?",
                (count, site_name, self._today),
            )
            return self.get_remaining(site_name)

    def get_used(self, site_name: str) -> int:
        """返回今日已使用次数。"""
        with self._lock:
            self._ensure_date()
            row = self._db.fetchone(
                "SELECT count FROM daily_quota WHERE site_name=? AND query_date=?",
                (site_name, self._today),
            )
            count: int = row["count"] if row else 0
            return count

    def get_search_remaining(self, site_name: str) -> int:
        """返回搜索可用次数（总额 - 已用 - 详情页保底）。"""
        raw = self.get_remaining(site_name)
        reserve = DETAIL_RESERVE.get(site_name, 0)
        return max(0, raw - reserve)

    def can_use_for_detail(self, site_name: str) -> bool:
        """是否还有详情页额度可用。"""
        return self.get_remaining(site_name) > 0

    def get_all_remaining(self) -> dict[str, int]:
        """返回所有站点的剩余配额。"""
        return {s: self.get_remaining(s) for s in self._limits}
