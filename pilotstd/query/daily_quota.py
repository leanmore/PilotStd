# 模块：项目/查询/_脚本
# 每日查询配额追踪器（数据库查询持久化）
# 日限额统一从_配置.._读取，此处不再硬编码

import logging
import threading
from datetime import date
from typing import Any, Dict

from ..core.db import Database
from ..i18n import _

logger = logging.getLogger(__name__)

# 日限额强制上限（阶段3.1:约束条件#1）
MAX_DAILY_LIMIT = 1000

# 详情页查询保底次数——特定站点需为详情查询预留配额，避免搜索耗尽。
# 未列出的站点默认预留 0 次。这不是适配器注册列表，新增适配器无需修改此处。
# 若新站点经验上需要预留配额，按需添加条目即可。
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
        # 阶段3.1:日限额强制上限1000
        self._limits = {k: min(v, MAX_DAILY_LIMIT) for k, v in dict(limits or {}).items()}
        self._lock = threading.RLock()
        self._ensure_today_rows()
        # 当日已发送配额耗尽通知的站点集合（防重复）
        self._quota_exhausted_notified: set[str] = set()
        # 可选的_，用于发送配额耗尽事件
        self._notification_mgr: Any = None

    def set_notification_mgr(self, mgr: Any) -> None:
        """注入通知管理器，供配额耗尽时发送事件。"""
        self._notification_mgr = mgr

    def _ensure_date(self) -> None:
        """跨天自动更新日期标记并初始化新日期的配额行"""
        today = str(date.today())
        if self._today != today:
            self._today = today
            self._quota_exhausted_notified.clear()
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
        """返回该站点今日剩余可用次数。配额首次耗尽时发送通知（每日每站点一次）。"""
        with self._lock:
            self._ensure_date()
            limit = self._limits.get(site_name, 500)
            row = self._db.fetchone(
                "SELECT count FROM daily_quota WHERE site_name=? AND query_date=?",
                (site_name, self._today),
            )
            used: int = row["count"] if row else 0
            remaining = max(0, limit - used)
            if remaining == 0 and site_name not in self._quota_exhausted_notified:
                self._quota_exhausted_notified.add(site_name)
                if self._notification_mgr:
                    try:
                        self._notification_mgr.send_event(
                            "quota_exhausted",
                            {
                                "site_name": site_name,
                                "quota_limit": str(limit),
                                "reset_time": _("明日 0:00"),
                            },
                        )
                    except Exception as e:
                        logger.warning("配额耗尽通知发送失败: %s, error=%s", site_name, e)
            return remaining

    def record_usage(self, site_name: str, count: int) -> int:
        """记录消耗次数，返回剩余可用次数。"""
        with self._lock:
            self._ensure_date()
            # 确保该站点的今日行存在（___只覆盖_中的站点）
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
