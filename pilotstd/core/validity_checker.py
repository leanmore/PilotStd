# pilotstd/core/validity_checker.py
# 标准时效性检查模块 — 跟踪标准现行/废止状态变更
# L1: 本地公告缓存表  L2: 网络适配器查询  L3: 历史状态对比

import logging
import random
import threading
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
                self._db.commit()
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
            except Exception:
                pass

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

        L1 — 查本地公告缓存（announcement_match + announcement_record）
        L2 — 查适配器实时查询（需传 query_engine）
        L3 — 对比历史状态记录

        返回: {"status": str, "previous": str|None} 或 None（查询失败）
        """
        # ── L1: 公告缓存表 ──
        for table in ("announcement_match", "announcement_record"):
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


# ── 模块级并发锁 ──────────────────────────────────────────
_VALIDITY_LOCK = threading.Lock()


# ── 纯执行函数（API + 调度器共用）───────────────────────────


def _sample_due_standards(checker: ValidityChecker, check_ratio: int) -> tuple[list[str], int]:
    """到期标准 → 数据库层随机采样 → 返回 (候选列表, 采样数)。
    不再全量加载 + Python 洗牌，改为 COUNT + ORDER BY RANDOM() LIMIT 两步查询。"""
    import math

    total_due = checker.count_due_standards()
    if total_due == 0:
        return [], 0

    sample_size = max(1, math.ceil(total_due * check_ratio / 100))
    candidates = checker.get_due_standards_random(sample_size)
    return candidates, sample_size


def _process_validity_batch(
    candidates: list[str],
    checker: ValidityChecker,
    db: Any,
    notification_mgr: Any,
    batch_size: int,
    batch_interval: int,
) -> tuple[int, list[str], list[dict]]:
    """逐条检查标准时效性，更新状态，发送批量通知。返回 (changed, changed_list, failed_list)。"""
    import time as _time

    from .config import _TABLE

    changed = 0
    changed_list: list[str] = []
    failed_list: list[dict] = []
    for i, std_no in enumerate(candidates):
        try:
            result = checker.check_standard(std_no)
            if result:
                old_row = db.fetchone(
                    f"SELECT status FROM {_TABLE} WHERE standard_number=?",
                    (std_no,),
                )
                old_status = old_row["status"] if old_row else None
                new_status = result["status"] or "现行"
                checker.update_status(std_no, new_status, notification_mgr)
                if old_status and old_status != new_status:
                    changed_list.append(std_no)
                    changed += 1
                    if len(changed_list) % 10 == 0 and notification_mgr:
                        try:
                            notification_mgr.send_event(
                                "validity_batch_report",
                                {
                                    "count": 0,
                                    "changed": 10,
                                    "failed": 0,
                                    "adapters": {},
                                    "change_detail": changed_list[-10:],
                                },
                            )
                        except Exception:
                            pass
        except Exception as e:
            failed_list.append({"standard": std_no, "error": str(e)})
            if notification_mgr:
                try:
                    notification_mgr.send_event(
                        "validity_standard_failed",
                        {"standard_number": std_no, "error": str(e)},
                    )
                except Exception:
                    pass
        if i > 0 and i % batch_size == 0 and batch_interval > 0:
            _time.sleep(batch_interval)
    return changed, changed_list, failed_list


def _finalize_validity_round(
    config: Any,
    db: Any,
    candidates: list[str],
    changed_list: list[str],
    failed_list: list[dict],
    adapter_mgr: Any,
    notification_mgr: Any,
    update_counters: bool,
) -> dict:
    """统计适配器状态、更新计数器、发送轮次汇总。返回 adapters_status。"""
    adapters_status: dict = {}
    if adapter_mgr:
        try:
            adapters_status = adapter_mgr.get_all_status()
        except Exception as e:
            logger.warning("获取适配器状态失败: %s", e)

    if update_counters:
        current_count = config.get("validity.checked_count", 0)
        new_count = current_count + len(candidates)
        config.set("validity.checked_count", new_count)
        try:
            total_row = db.fetchone("SELECT COUNT(*) AS cnt FROM standard_validity")
            total = total_row["cnt"] if total_row else 0
            if total > 0 and new_count >= total:
                config.set("validity.round_completed", True)
                if notification_mgr:
                    try:
                        changes = db.fetchall(
                            "SELECT standard_number FROM standard_validity "
                            "WHERE last_changed_at IS NOT NULL "
                            "ORDER BY last_changed_at DESC LIMIT 200"
                        )
                        cycle_change_list = [r["standard_number"] for r in changes]
                        notification_mgr.send_event(
                            "validity_round_summary",
                            {
                                "total_checks": new_count,
                                "total_changes": len(cycle_change_list),
                                "total_failures": len(failed_list),
                                "change_list": cycle_change_list,
                                "adapter_summary": adapters_status,
                            },
                        )
                    except Exception:
                        pass
        except Exception:
            pass
        config.save()
    return adapters_status


def run_validity_check(
    notification_mgr: Any = None, db: Any = None, adapter_mgr: Any = None, update_counters: bool = False
) -> dict:
    """执行时效性检查，供 API 和调度器共同调用。"""
    if not _VALIDITY_LOCK.acquire(blocking=False):
        return {"ok": False, "checked": 0, "changed": 0, "error": "检查正在执行中"}
    try:
        if db is None:
            from .config import get_db_path
            from .db import Database

            db = Database(get_db_path())

        from .config import ConfigManager

        config = ConfigManager()
        checker = ValidityChecker(db)
        check_ratio = config.get("validity.check_ratio", 25)
        batch_size = config.get("validity.batch_size", 50)
        batch_interval = config.get("validity.batch_interval", 5)

        candidates, _sample_size = _sample_due_standards(checker, check_ratio)
        if not candidates:
            return {"ok": True, "checked": 0, "changed": 0}

        changed, changed_list, failed_list = _process_validity_batch(
            candidates, checker, db, notification_mgr, batch_size, batch_interval
        )

        adapters_status = _finalize_validity_round(
            config, db, candidates, changed_list, failed_list, adapter_mgr, notification_mgr, update_counters
        )

        if notification_mgr:
            try:
                notification_mgr.send_event(
                    "validity_batch_report",
                    {
                        "count": len(candidates),
                        "changed": len(changed_list),
                        "failed": len(failed_list),
                        "adapters": adapters_status,
                    },
                )
            except Exception:
                pass

        logger.info(
            "时效性检查完成: checked=%d changed=%d failed=%d", len(candidates), len(changed_list), len(failed_list)
        )
        return {"ok": True, "checked": len(candidates), "changed": len(changed_list)}
    except Exception as e:
        logger.exception("时效性检查执行失败")
        if notification_mgr:
            try:
                import traceback

                notification_mgr.send_event(
                    "validity_system_failed",
                    {"error": str(e), "traceback": traceback.format_exc()[:500]},
                )
            except Exception:
                pass
        return {"ok": False, "checked": 0, "changed": 0, "error": str(e)}
    finally:
        _VALIDITY_LOCK.release()
