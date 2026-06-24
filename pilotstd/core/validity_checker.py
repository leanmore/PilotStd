# pilotstd/core/validity_checker.py
# 标准时效性检查模块 — 跟踪标准现行/废止状态变更
# L1: 本地公告缓存表  L2: 网络适配器查询  L3: 历史状态对比

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .db import Database

logger = logging.getLogger(__name__)

_TABLE = "standard_validity_status"


class ValidityChecker:
    """标准时效性检查器。

    三级检查策略：
      L1 — 查 announcement_cache / announcement_fetch_log
      L2 — 查适配器（QueryEngine 实时查询）
      L3 — 对比 standard_validity_status 历史记录
    """

    def __init__(self, db: Database):
        self._db = db

    # ── 注册新标准 ──────────────────────────────────────────────

    def register_new_standard(self, standard_number: str) -> None:
        """归档后注册新标准，初始状态='未知'，next_check_at=now（立即可查）。"""
        now = datetime.now(timezone.utc).isoformat()
        existing = self._db.fetchone(
            f"SELECT id FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if existing:
            return
        self._db.execute(
            f"INSERT INTO {_TABLE} (standard_number, status, next_check_at, created_at, updated_at) "
            "VALUES (?, '未知', ?, ?, ?)",
            (standard_number, now, now, now),
        )

    # ── 状态更新 ──────────────────────────────────────────────

    def update_status(self, standard_number: str, new_status: str, notification_mgr: Any = None) -> None:
        """更新标准时效性状态，设置下次检查时间=now+28天。
        状态变更时记录 last_status + last_status_updated_at，并触发通知事件。
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        next_check = (now + timedelta(days=28)).isoformat()
        row = self._db.fetchone(
            f"SELECT status, check_count FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if row:
            # 状态变更时记录旧状态+变更时间
            if row["status"] != new_status:
                self._db.execute(
                    f"UPDATE {_TABLE} SET status=?, last_checked_at=?, next_check_at=?, "
                    "last_status=?, last_status_updated_at=?, check_count=check_count+1, updated_at=? "
                    "WHERE standard_number=?",
                    (new_status, now_iso, next_check, row["status"], now_iso, now_iso, standard_number),
                )
                # 触发通知事件
                if notification_mgr:
                    try:
                        event_type = "standard_expired" if new_status == "已废止" else "standard_status_changed"
                        notification_mgr.send_event(
                            event_type,
                            {
                                "standard_number": standard_number,
                                "old_status": row["status"],
                                "new_status": new_status,
                            },
                        )
                    except Exception:
                        pass
            else:
                self._db.execute(
                    f"UPDATE {_TABLE} SET last_checked_at=?, next_check_at=?, "
                    "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                    (now_iso, next_check, now_iso, standard_number),
                )
        else:
            self._db.execute(
                f"INSERT INTO {_TABLE} (standard_number, status, last_checked_at, "
                "next_check_at, last_status_updated_at, check_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, 1, ?, ?)",
                (standard_number, new_status, now_iso, next_check, now_iso, now_iso, now_iso),
            )

    # ── 到期标准查询 ──────────────────────────────────────────

    def get_due_standards(self) -> list[str]:
        """查询所有 next_check_at <= now 的到期标准号。"""
        now = datetime.now(timezone.utc).isoformat()
        rows = self._db.fetchall(
            f"SELECT standard_number FROM {_TABLE} WHERE next_check_at <= ? ORDER BY next_check_at ASC",
            (now,),
        )
        return [r["standard_number"] for r in rows]

    @staticmethod
    def random_slice(candidates: list[str], week_number: int, batch_size: int = 50) -> list[str]:
        """从候选列表中随机切片取约 1/4（固定种子，同周结果一致）。"""
        if not candidates:
            return []
        # 复制后 shuffle，避免修改原列表
        shuffled = list(candidates)
        rng = random.Random(week_number)
        rng.shuffle(shuffled)
        start = (week_number % max(1, (len(shuffled) + batch_size - 1) // batch_size)) * batch_size
        return shuffled[start : start + batch_size]

    # ── 状态检查 ──────────────────────────────────────────────

    def check_standard(
        self,
        standard_number: str,
        query_engine: Any = None,
    ) -> Optional[dict[str, Optional[str]]]:
        """检查单个标准的时效性状态。

        L1 — 查本地公告缓存（announcement_cache + announcement_fetch_log）
        L2 — 查适配器实时查询（需传 query_engine）
        L3 — 对比历史状态记录

        返回: {"status": str, "previous": str|None} 或 None（查询失败）
        """
        # ── L1: 公告缓存表 ──
        for table in ("announcement_cache", "announcement_fetch_log"):
            try:
                row = self._db.fetchone(
                    f"SELECT std_name, publish_date FROM {table} WHERE standard_number=? LIMIT 1",
                    (standard_number,),
                )
                if row:
                    result = self._determine_status(standard_number, row)
                    if result:
                        return result
            except Exception:
                pass

        # ── L2: 适配器实时查询 ──
        if query_engine:
            try:
                from ..core.std_utils import parse_std_number

                parsed = parse_std_number(standard_number)
                if parsed:
                    results = query_engine.query_standards(
                        [(parsed["code"], parsed["number"], parsed.get("year", 0), "", None, "")]
                    )
                    if results and results[0].is_found():
                        return {
                            "status": results[0].status or "现行",
                            "previous": None,
                        }
            except Exception:
                pass

        # ── L3: 历史状态对比 ──
        row = self._db.fetchone(
            f"SELECT status, last_status FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if row:
            return {
                "status": row["status"],
                "previous": row["last_status"],
            }

        return None

    def _determine_status(self, standard_number: str, row: dict) -> Optional[dict[str, Optional[str]]]:
        """从缓存行判断现行/废止状态。"""
        std_name = row.get("std_name", "")
        name_lower = std_name.lower() if std_name else ""
        # 废止标记词
        for keyword in ("废止", "作废", "被代替", "abolished", "withdrawn", "obsolete"):
            if keyword in name_lower:
                return {"status": "已废止", "previous": None}
        # 有名称但无废止标记 → 现行
        if std_name:
            return {"status": "现行", "previous": None}
        return None

    # ── 统计 ──────────────────────────────────────────────────

    def get_status_summary(self) -> dict[str, int]:
        """返回各状态的标准数量统计。"""
        rows = self._db.fetchall(f"SELECT status, COUNT(*) as cnt FROM {_TABLE} GROUP BY status")
        return {r["status"]: r["cnt"] for r in rows}
