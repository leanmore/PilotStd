# 模块：项目/核心/__流水线脚本
# 有效性检查流水线函数—从_检查器脚本提取

from __future__ import annotations

import logging
import math
import threading
import time as _time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .validity_checker import ValidityChecker  # 仅类型标注用，运行时延迟导入以避免循环引用


def _get_validity_checker_class():
    """延迟导入 ValidityChecker，避免 _validity_pipeline ↔ validity_checker 循环引用。"""
    from .validity_checker import ValidityChecker as VC

    return VC


_TABLE = "standard_validity"

logger = logging.getLogger(__name__)
_VALIDITY_LOCK = threading.Lock()


# ── 阶段1：随机采样到期标准 ──
def _sample_due_standards(checker: ValidityChecker, check_ratio: int) -> tuple[list[str], int]:
    """到期标准 → 数据库层随机采样 → 返回 (候选列表, 采样数)。
    不再全量加载 + Python 洗牌，改为 COUNT + ORDER BY RANDOM() LIMIT 两步查询。"""

    total_due = checker.count_due_standards()
    if total_due == 0:
        return [], 0

    sample_size = max(1, math.ceil(total_due * check_ratio / 100))
    candidates = checker.get_due_standards_random(sample_size)
    return candidates, sample_size


# ── 阶段2：逐条检查并更新状态 ──
def _std_name(db: Any, std_no: str) -> str:
    """查询标准名称（validity 详情列表补充信息；查不到返回空串）。"""
    try:
        row = db.fetchone(
            "SELECT std_name FROM announcement_record WHERE standard_number = ?", (std_no,)
        )
        if row and row["std_name"]:
            return str(row["std_name"])
    except Exception:
        pass
    return ""


def _process_validity_batch(
    candidates: list[str],
    checker: ValidityChecker,
    db: Any,
    notification_mgr: Any,
    batch_size: int,
    batch_interval: int,
) -> tuple[int, list[str], list[dict], list[dict]]:
    """逐条检查标准时效性，更新状态，发送批量通知。

    返回 (changed, changed_list, failed_list, change_detail)——
    change_detail 供最终批次报告的"变更详情"节使用（B-11）。
    """

    changed = 0
    changed_list: list[str] = []
    failed_list: list[dict] = []
    change_detail: list[dict] = []
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
                    change_detail.append(
                        {
                            "standard": std_no,
                            "name": _std_name(db, std_no),
                            "reason": new_status,
                        }
                    )
                    if len(change_detail) % 10 == 0 and notification_mgr:
                        try:
                            notification_mgr.send_event(
                                "validity_batch_report",
                                {
                                    "count": 0,
                                    "changed": 10,
                                    "failed": 0,
                                    "adapter_status": {},
                                    "change_detail": change_detail[-10:],
                                },
                            )
                        except Exception as e:
                            logger.warning("时效性批次报告通知发送失败: %s", e)
        except Exception as e:
            failed_list.append({"standard": std_no, "name": _std_name(db, std_no), "error": str(e)})
            if notification_mgr:
                try:
                    notification_mgr.send_event(
                        "validity_standard_failed",
                        {"standard_number": std_no, "error": str(e)},
                    )
                except Exception as e2:
                    logger.warning("标准检查失败通知发送失败: %s, error=%s", std_no, e2)
        if i > 0 and i % batch_size == 0 and batch_interval > 0:
            _time.sleep(batch_interval)
    return changed, changed_list, failed_list, change_detail


# ── 阶段3：通知 + 汇总统计 ──
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
                # 轮次计数递增
                round_count = config.get("validity.round_count", 0)
                new_round = round_count + 1
                config.set("validity.round_count", new_round)
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
                                "round": new_round,
                            },
                        )
                    except Exception as e:
                        logger.warning("时效性周期总结通知发送失败: %s", e)
        except Exception:
            pass
        config.save()
    return adapters_status


# ── 统一入口 ──
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
        checker = _get_validity_checker_class()(db)
        check_ratio = config.get("validity.check_ratio", 25)
        batch_size = config.get("validity.batch_size", 50)
        batch_interval = config.get("validity.batch_interval", 5)

        candidates, _sample_size = _sample_due_standards(checker, check_ratio)
        if not candidates:
            return {"ok": True, "checked": 0, "changed": 0}

        changed, changed_list, failed_list, change_detail = _process_validity_batch(
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
                        "adapter_status": adapters_status,
                        "change_detail": change_detail,
                        "failed_detail": failed_list,
                    },
                )
            except Exception as e:
                logger.warning("时效性批次报告通知发送失败: %s", e)

        logger.info(
            "时效性检查完成: checked=%d changed=%d failed=%d", len(candidates), len(changed_list), len(failed_list)
        )
        return {"ok": True, "checked": len(candidates), "changed": len(changed_list)}
    except Exception as e:
        logger.exception("时效性检查执行失败")
        if notification_mgr:
            try:
                import traceback

                # P1 修复：堆栈细节只进系统日志，通知仅携带用户可读错误（避免 raw 异常直出）
                logger.error("Validity system failed: %s\n%s", e, traceback.format_exc()[:500])
                notification_mgr.send_event(
                    "validity_system_failed",
                    {"error": str(e)},
                )
            except Exception as e2:
                logger.warning("时效性系统失败通知发送失败: %s", e2)
        return {"ok": False, "checked": 0, "changed": 0, "error": str(e)}
    finally:
        _VALIDITY_LOCK.release()
