# 模块：项目/核心/_检查器脚本
# 标准时效性检查模块 — 跟踪标准现行/废止状态变更
# 1:本地公告缓存表2:网络适配器查询3:历史状态对比

import logging
import random
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from .db import Database

logger = logging.getLogger(__name__)

_TABLE = "standard_validity"


class ValidityChecker:
    """标准时效性检查器。

    三级检查策略：
      L1 — 查 announcement_match / announcement_record
      L2 — 查适配器（QueryEngine 实时查询）
      L3 — 对比 standard_validity 历史记录
    """

    def __init__(self, db: Database):
        self._db = db
        self._ensure_last_changed_at_column()

    def _ensure_last_changed_at_column(self) -> None:
        """确保 standard_validity 表存在 last_changed_at 字段（首次启动自动迁移）。"""
        try:
            cols = self._db.fetchall("PRAGMA table_info(standard_validity)")
            col_names = [c["name"] for c in cols]
            if "last_changed_at" not in col_names:
                self._db.execute("ALTER TABLE standard_validity ADD COLUMN last_changed_at TEXT")
                self._db.execute("UPDATE standard_validity SET last_changed_at = updated_at")
                logger.info("standard_validity 表已添加 last_changed_at 字段并回填")
        except Exception as e:
            logger.warning("last_changed_at 迁移跳过: %s", e)

    # ── 注册新标准 ──────────────────────────────────────────────

    def register_new_standard(self, standard_number: str, notification_mgr: Any = None) -> None:
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
        if notification_mgr:
            try:
                notification_mgr.send_event(
                    "standard_first_registered",
                    {
                        "standard_number": standard_number,
                    },
                )
            except Exception as e:
                logger.warning("首次登记通知发送失败: %s, error=%s", standard_number, e)

    # ── 状态更新 ──────────────────────────────────────────────

    def update_status(self, standard_number: str, new_status: str, notification_mgr: Any = None) -> None:
        """更新标准时效性状态，设置下次检查时间=now + total_weeks*7 天。
        状态变更时同步更新 last_changed_at，未变化时仅更新 updated_at。
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        from .config import ConfigManager

        total_weeks = ConfigManager().get("validity.total_weeks", 4)
        next_check = (now + timedelta(days=total_weeks * 7)).isoformat()
        row = self._db.fetchone(
            f"SELECT status, check_count FROM {_TABLE} WHERE standard_number=?",
            (standard_number,),
        )
        if row:
            if row["status"] != new_status:
                self._db.execute(
                    f"UPDATE {_TABLE} SET status=?, last_checked_at=?, next_check_at=?, "
                    "last_status=?, last_status_updated_at=?, last_changed_at=?, "
                    "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                    (new_status, now_iso, next_check, row["status"], now_iso, now_iso, now_iso, standard_number),
                )
                if notification_mgr:
                    try:
                        # 第一步：标准废止事件已合并进本事件，
                        # 通过"是否已过期"字段区分废止（替代原独立事件，避免双通知）
                        is_expired = new_status == "已废止"
                        notification_mgr.send_event(
                            "standard_status_changed",
                            {
                                "standard_number": standard_number,
                                "old_status": row["status"],
                                "new_status": new_status,
                                "is_expired": is_expired,
                                "changed_at": datetime.now().isoformat(),
                            },
                        )
                    except Exception as e:
                        logger.warning("状态变更通知发送失败: %s, error=%s", standard_number, e)
            else:
                self._db.execute(
                    f"UPDATE {_TABLE} SET last_checked_at=?, next_check_at=?, "
                    "check_count=check_count+1, updated_at=? WHERE standard_number=?",
                    (now_iso, next_check, now_iso, standard_number),
                )
        else:
            self._db.execute(
                f"INSERT INTO {_TABLE} (standard_number, status, last_checked_at, "
                "next_check_at, last_changed_at, check_count, created_at, updated_at) "
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

    def count_due_standards(self) -> int:
        """到期标准总数（轻量 COUNT 查询，不加载数据）。"""
        now = datetime.now(timezone.utc).isoformat()
        row = self._db.fetchone(
            f"SELECT COUNT(*) as cnt FROM {_TABLE} WHERE next_check_at <= ?",
            (now,),
        )
        return row["cnt"] if row else 0

    def get_due_standards_random(self, limit: int) -> list[str]:
        """随机采样 limit 条到期标准号（数据库层 ORDER BY RANDOM() + LIMIT，避免全量加载到 Python 内存）。"""
        now = datetime.now(timezone.utc).isoformat()
        rows = self._db.fetchall(
            f"SELECT standard_number FROM {_TABLE} WHERE next_check_at <= ? ORDER BY RANDOM() LIMIT ?",
            (now, limit),
        )
        return [r["standard_number"] for r in rows]

    @staticmethod
    def random_slice(candidates: list[str], week_number: int, batch_size: int = 50) -> list[str]:
        """从候选列表中随机切片取约 1/4（固定种子，同周结果一致）。"""
        if not candidates:
            return []
        # 复制后，避免修改原列表
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

        L1 — 查本地公告缓存（announcement_match + announcement_record）
        L2 — 查适配器实时查询（需传 query_engine）
        L3 — 对比历史状态记录

        返回: {"status": str, "previous": str|None} 或 None（查询失败）
        """
        # ──1:公告缓存表（仅 announcement_record 含 std_name 列）──
        try:
            row = self._db.fetchone(
                "SELECT std_name FROM announcement_record WHERE standard_number=? LIMIT 1",
                (standard_number,),
            )
            if row:
                result = self._determine_status(standard_number, row)
                if result:
                    return result
        except Exception:
            logger.exception("查询公告缓存失败: %s", standard_number)

        # ──2:适配器实时查询──
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

        # ──3:历史状态对比──
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


# ──流水线函数（已提取至__流水线脚本）──

from ._validity_pipeline import (  # noqa: E402, F401 — 由 API/调度器导入消费
    _finalize_validity_round,
    _process_validity_batch,
    _sample_due_standards,
    run_validity_check,
)
