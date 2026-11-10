# 模块：项目/核心/__流水线脚本
# 有效性检查流水线函数—从_检查器脚本提取

from __future__ import annotations

import logging
import math
import threading
import time as _time
from typing import TYPE_CHECKING, Any

from pilotstd.core.time_utils import iso_now

from . import validity_log
from .status import Status

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
        if row and isinstance(row["std_name"], str) and row["std_name"]:
            return row["std_name"]
    except Exception as e:
        # 只用于详情列表的「名称」补充：查不到就显示标准号，有效性判定本身不受影响。
        # 故保持 debug；若 DB 真故障，有效性流程自身会有更明显的失败。
        logger.debug("std_name lookup failed for %s: %s", std_no, e)
    return ""


def _enqueue_gb_replacement(db: Any, new_standard: str, new_name: str) -> None:
    """被 GB 家族替代时，把新标准放入下载等待队列（自动补下）。"""
    if not new_standard:
        return
    from .std_utils import is_gb_code, parse_std_number

    parsed = parse_std_number(new_standard)
    if not parsed or not is_gb_code(str(parsed.get("raw_code", ""))):
        return
    try:
        existing = db.fetchone(
            "SELECT id FROM download_queue WHERE standard_number=? AND status='waiting'",
            (new_standard,),
        )
        if existing:
            return
        now = iso_now()
        db.execute(
            "INSERT INTO download_queue (standard_number, standard_name, publish_date,"
            " expected_available, created_at, status) VALUES (?, ?, ?, ?, ?, 'waiting')",
            (new_standard, new_name, "", now[:10], now),
        )
    except Exception as e:
        logger.warning("替代标准入下载队列失败: %s, error=%s", new_standard, e)  # i18n-allow: 内部日志


def _record_change(db: Any, std_no: str, new_status: str, result: dict, apply_side_effects: bool = False) -> dict:
    """记录一次状态变更；仅在证据充分（L2 且开关开启）时才把替代标准放入下载队列。"""
    detail = {
        "standard": std_no,
        "name": _std_name(db, std_no),
        "reason": new_status,
        "new_standard": result.get("new_standard", ""),
        "new_standard_name": result.get("new_standard_name", ""),
    }
    if apply_side_effects:
        _enqueue_gb_replacement(
            db,
            str(result.get("new_standard", "") or ""),
            str(result.get("new_standard_name", "") or ""),
        )
    return detail


def _process_validity_batch(
    candidates: list[str],
    checker: ValidityChecker,
    db: Any,
    notification_mgr: Any,
    batch_size: int,
    batch_interval: int,
    query_engine: Any = None,
    l2_workers: int = 1,
) -> tuple[int, list[str], list[dict], list[dict]]:
    """逐条检查标准时效性，更新状态，发送批量通知。

    返回 (changed, changed_list, failed_list, change_detail)。
    `query_engine` 非空时 L2（适配器实时查询）才可达；为空则仍只有 L1/L3。
    `l2_workers > 1` 时**只并发执行网络查询**（check_standard），DB 写入仍在主线程
    串行执行——`Database` 是 thread-local 连接 + 写锁，读可并发（D3-6）。
    """
    from concurrent.futures import ThreadPoolExecutor

    def _check_one(std_no: str):
        try:
            return std_no, checker.check_standard(std_no, query_engine=query_engine), None
        except Exception as exc:  # noqa: BLE001 — 单条失败不得中断整轮
            return std_no, None, exc

    if l2_workers > 1 and query_engine is not None and len(candidates) > 1:
        with ThreadPoolExecutor(max_workers=min(l2_workers, len(candidates))) as pool:
            checked = list(pool.map(_check_one, candidates))
    else:
        checked = [_check_one(std_no) for std_no in candidates]

    changed = 0
    changed_list: list[str] = []
    failed_list: list[dict] = []
    change_detail: list[dict] = []
    for i, (std_no, result, error) in enumerate(checked):
        if error is not None:
            failed_list.append({"standard": std_no, "name": _std_name(db, std_no), "error": str(error)})
            validity_log.record(db, std_no, error=error)
            _notify_failed(notification_mgr, db, std_no, error)
        elif result and result.get("query_failed"):
            err = str(result["query_failed"])
            failed_list.append({"standard": std_no, "name": _std_name(db, std_no), "error": err})
            validity_log.record(db, std_no, result=result, error=err)
            _notify_failed(notification_mgr, db, std_no, RuntimeError(err))
        elif result:
            validity_log.record(db, std_no, result=result)
            if _apply_validity_result(
                std_no,
                result,
                checker,
                db,
                notification_mgr,
                change_detail,
                checked_count=i + 1,
                failed_count=len(failed_list),
            ):
                changed_list.append(std_no)
                changed += 1
        else:
            validity_log.record(db, std_no, error="no result")
        if i > 0 and i % batch_size == 0 and batch_interval > 0:
            _time.sleep(batch_interval)
    return changed, changed_list, failed_list, change_detail


def _apply_validity_result(
    std_no: str,
    result: dict,
    checker: ValidityChecker,
    db: Any,
    notification_mgr: Any,
    change_detail: list[dict],
    checked_count: int = 0,
    failed_count: int = 0,
) -> bool:
    """把单条检查结果落库；状态确有变化时追加变更明细并每 10 条发一次批次报告。"""
    old_row = db.fetchone(f"SELECT status FROM {_TABLE} WHERE standard_number=?", (std_no,))
    old_status = old_row["status"] if old_row else None
    new_status = result["status"] or Status.ACTIVE.value
    evidence = str(result.get("evidence", "L3"))
    checker.update_status(
        std_no,
        new_status,
        notification_mgr,
        str(result.get("new_standard", "") or ""),
        str(result.get("new_standard_name", "") or ""),
        str(result.get("new_standard_implementation_date", "") or ""),
        evidence=evidence,
    )
    if not old_status or old_status == new_status:
        return False
    change_detail.append(
        _record_change(db, std_no, new_status, result, checker.should_apply_side_effects(evidence))
    )
    if len(change_detail) % 10 == 0 and notification_mgr:
        try:
            notification_mgr.send_event(
                "validity_batch_report",
                {
                    "count": checked_count,
                    "changed": len(change_detail),
                    "failed": failed_count,
                    "adapter_status": {},
                    "change_detail": change_detail[-10:],
                },
            )
        except Exception as e:
            logger.warning("时效性批次报告通知发送失败: %s", e)
    return True


def _notify_failed(notification_mgr: Any, db: Any, std_no: str, error: Exception) -> None:
    """单条检查失败的通知（失败不阻断整轮）。"""
    if not notification_mgr:
        return
    try:
        failed_payload = {"standard_number": std_no, "error": str(error)}
        failed_name = _std_name(db, std_no)
        if isinstance(failed_name, str) and failed_name:
            failed_payload["standard_name"] = failed_name
        notification_mgr.send_event("validity_standard_failed", failed_payload)
    except Exception as e2:
        logger.warning("标准检查失败通知发送失败: %s, error=%s", std_no, e2)


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
        # 失败样本不计入“已检查”：否则超时/适配器异常也会推进轮次（D3-5）。
        failed_standards = {str(f.get("standard", "")) for f in failed_list}
        success_count = max(0, len(candidates) - len(failed_standards))
        new_count = current_count + success_count
        config.set("validity.checked_count", new_count)
        try:
            # 只统计**格式合法**的标准号：历史库里存在 ` 11120-2011` 这类缺代号的脏行，
            # 它们永远无法被解析检查，计入分母会让 round_completed 永远不成立。
            total_row = db.fetchone(
                "SELECT COUNT(*) AS cnt FROM standard_validity"
                " WHERE standard_number GLOB '[A-Z]*'"
            )
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
                        cycle_change_list = [
                            f"{r['standard_number']} {_std_name(db, r['standard_number'])}".strip()
                            for r in changes
                        ]
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
        except Exception as e:
            # 周期记账失败不阻断已完成的本轮检查，但必须可观测
            logger.warning("validity round bookkeeping failed: %s", e)
        config.save()
    return adapters_status


# ── 统一入口 ──
def run_validity_check(
    notification_mgr: Any = None,
    db: Any = None,
    adapter_mgr: Any = None,
    update_counters: bool = False,
    query_engine: Any = None,
) -> dict:
    """执行时效性检查，供 API 和调度器共同调用。

    `query_engine` 传空时 L2 适配器比对不可达（只有 L1/L3）；API 与调度器都应传入。
    """
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
        l2_workers = int(config.get("validity.l2_concurrency", 3) or 3)

        candidates, _sample_size = _sample_due_standards(checker, check_ratio)
        if not candidates:
            return {"ok": True, "checked": 0, "changed": 0}

        changed, changed_list, failed_list, change_detail = _process_validity_batch(
            candidates, checker, db, notification_mgr, batch_size, batch_interval, query_engine, l2_workers
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

                # 一级缺陷修复：堆栈细节只进系统日志，通知仅携带用户可读错误（避免原始异常直出）
                logger.error("Validity system failed: %s\n%s", e, traceback.format_exc()[:500])
                notification_mgr.send_event(
                    "validity_system_failed",
                    {"error": str(e)},
                )
            except Exception as e2:
                logger.warning("时效性系统失败通知发送失败: %s", e2)  # i18n-allow: 内部日志
        return {"ok": False, "checked": 0, "changed": 0, "error": str(e)}
    finally:
        _VALIDITY_LOCK.release()
