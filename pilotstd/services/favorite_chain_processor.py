# 模块：项目/服务/收藏_下载链_处理器脚本
"""收藏下载链处理器 — cron 倒序批处理（v54 修复 + 贴合现有"下载即归档"链路）。

由 APScheduler cron（每天 04:00）调用 process_chain()。
状态流转（沿用现有状态名）：
  pending/failed → download_to_inbox（内部 downloading → archiving → done/failed）
  failed 重试上限 MAX_RETRIES 次后 → abandoned（人工介入）

v3.0 改进点（已落实）：
  - user_id 隔离：v54 补列后 WHERE 条件含 record_id + user_id
  - retry_count 原子递增：合并进主 UPDATE（禁止拆分为独立 UPDATE）
  - 倒序执行：process_chain() 保持"先下游后上游"的扩展框架（当前单阶段：下载）
"""

import logging
import os
from collections import Counter
from datetime import date, timedelta
from typing import Any, Optional

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

logger = logging.getLogger(__name__)

# ── 批处理约束 ─────────────────────────────────────────────
# 吞吐交给下载引擎的节奏（batch_size/max_workers/long_rest），此处不再设每次运行条数上限
# 重试上限 7：cron 每天 04:00 触发，失败后次日再试，共 7 天兜底窗口（ADR-007 决策值）
MAX_RETRIES = 7
COOLDOWN_DAYS = int(os.environ.get("ARCHIVE_COOLDOWN_DAYS", "28"))

# ── 状态常量（沿用现有状态名，前端 useFavorite 依赖 done/pending/downloading/archiving）──
STATUS_PENDING = "pending"
STATUS_DOWNLOADING = "downloading"
STATUS_ARCHIVING = "archiving"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
STATUS_ABANDONED = "abandoned"

_ACTIVE_STATUSES = (STATUS_PENDING, STATUS_FAILED)


def _new_db() -> Database:
    """实例化数据库连接（项目惯例：每处调用自行创建/关闭）。"""
    return Database(get_db_path())


def update_status(
    record_id: int,
    user_id: int,
    status: str,
    error: Optional[str] = None,
    local_path: Optional[str] = None,
    retry_increment: bool = False,
) -> None:
    """更新 favorite_downloads 状态（原子操作）。

    - WHERE 条件含 user_id：多用户同 record_id 时精确隔离（v3.0 强制）
    - retry_increment=True 时 retry_count = retry_count + 1 合并进主 UPDATE（原子递增）
    """
    db = _new_db()
    try:
        updates = ["status = ?", "last_attempt = ?", "updated_at = datetime('now')"]
        params: list[Any] = [status, date.today().isoformat()]

        if error is not None:
            updates.append("error_message = ?")
            params.append(error)
        if local_path is not None:
            updates.append("local_path = ?")
            params.append(local_path)
        if retry_increment:
            updates.append("retry_count = retry_count + 1")

        params.extend([record_id, user_id])
        db.execute(
            f"UPDATE favorite_downloads SET {', '.join(updates)}"
            " WHERE record_id = ? AND user_id = ?",
            params,
        )
    finally:
        db.close()


def get_records_by_status(limit: int = 0) -> list[dict[str, Any]]:
    """扫描待处理记录（pending/failed，未达重试上限，已过冷却期，且为国标）。

    冷却期语义：announcement_record.publish_date
    距今不足 COOLDOWN_DAYS 天的不处理（发布保护窗口）。
    类别闸：仅 NationalStd（国标）有下载适配器（std_gov→openstd_download 是唯一映射），
    行标/地标在此直接排除，不进入下载阶段也不消耗重试次数。
    limit=0（默认）表示不限条数：一轮处理全部到期记录，节流由引擎节奏负责。
    """
    db = _new_db()
    try:
        cooldown_cutoff = (date.today() - timedelta(days=COOLDOWN_DAYS)).isoformat()
        rows = db.fetchall(
            "SELECT fd.id, fd.favorite_id, fd.user_id, fd.record_id, fd.standard_no, ar.publish_date"
            " FROM favorite_downloads fd"
            " JOIN announcement_record ar ON fd.record_id = ar.id"
            " WHERE fd.status IN ('pending', 'failed')"
            " AND fd.standard_type = 'NationalStd'"
            " AND (fd.retry_count IS NULL OR fd.retry_count < ?)"
            " AND COALESCE(NULLIF(TRIM(ar.publish_date), ''), CURRENT_DATE) <= ?"
            " ORDER BY fd.last_attempt ASC NULLS FIRST, fd.updated_at ASC"
            " LIMIT ?",
            (MAX_RETRIES, cooldown_cutoff, limit if limit > 0 else -1),
        )
        return [dict(r) for r in rows]
    finally:
        db.close()


def process_pending_downloads(download_engine: Any = None, notify_per_record: bool = True) -> int:
    """阶段 1（当前唯一阶段）：全部到期 pending/failed → 下载 → done / failed / abandoned。

    复用现有 download_to_inbox（下载+归档一体，内部自行更新 downloading/archiving/done/failed）；
    处理器在其返回后按实际落库状态判定成败并原子维护重试计数。

    吞吐不再自设"每天 N 条"上限：传入 download_engine 时交由引擎节奏执行
    （batch_size 分批 + max_workers 并发 + 批间 long_rest 冷却，会话随机延迟在下载内部生效）；
    未传引擎（旧调用方/测试）时退化为顺序处理，功能不变。

    notify_per_record=False（cron 批量路径）：抑制逐条通知，运行结束只发 1 条汇总
    —— 逐条发在一次运行里就有上百条，会触发 Telegram 429（2026-09-21 实测 622/1119
    条被拒、丢失 55.6%）。True 保留逐条语义（单条调用方/测试用）。
    """
    records = get_records_by_status()
    if not records:
        return 0

    today = date.today().isoformat()
    if download_engine is None:
        outcomes = [_process_one_record(rec, today, notify_per_record) for rec in records]
    else:
        outcomes = download_engine.run_paced_batches(
            records, lambda rec: _process_one_record(rec, today, notify_per_record)
        )
    outcomes = [o for o in outcomes if o]

    if not notify_per_record:
        _notify_run_summary(outcomes)
    return len(outcomes)


def _notify_run_summary(outcomes: list[Any]) -> None:
    """按批汇总：一次运行只发 1 条，替代逐条 started/failed/complete/abandoned。

    复用既有 `batch_download_complete` 事件（成功/失败/跳过三计数），
    使通知量从"每条记录 2~3 条"降到"每次运行 1 条"。

    outcomes 元素为 (结局, 明细行)；明细只取前 5 条非成功项，避免汇总本身又变成长消息，
    同时保住"哪条失败了"这一可执行信息（否则汇总会丢细节）。
    """
    if not outcomes:
        return
    counts = Counter(o[0] if isinstance(o, tuple) else o for o in outcomes)
    details = [
        o[1] for o in outcomes if isinstance(o, tuple) and o[1] and o[0] in ("failed", "abandoned", "skipped")
    ][:5]
    try:
        from pilotstd.manager.facade import StandardManager

        StandardManager().notification_mgr.send_event(
            "batch_download_complete",
            {
                "success": counts.get("done", 0),
                "failed": counts.get("failed", 0) + counts.get("abandoned", 0),
                "skipped": counts.get("skipped", 0),
                "details": details,
            },
        )
    except Exception as e:  # noqa: BLE001 — 汇总通知失败不得影响链路结果
        logger.warning("批量汇总通知发送失败: %s", e)


def _process_one_record(rec: dict[str, Any], today: str, notify: bool = True) -> tuple[str, str]:
    """处理单条到期记录：调用下载 → 判定成败 → 维护重试计数与放弃通知。

    返回 (结局, 明细)：结局取 done/failed/abandoned/skipped（供批量汇总计数），
    明细为"标准号：原因"（供汇总展示非成功项）；自身异常一律吸收为失败状态，
    不向批量执行器冒泡。
    """
    fd_id = rec["id"]
    record_id = rec["record_id"]
    user_id = rec["user_id"]
    favorite_id = rec["favorite_id"]
    std_no = rec.get("standard_no") or f"record#{record_id}"

    try:
        from pilotstd.tasks.favorite_download import (  # 延迟导入避免循环依赖
            FavoriteSkip,
            download_to_inbox,
        )

        download_to_inbox(favorite_id, user_id, record_id, notify=notify)

        # 调用后按实际落库状态判定（download_to_inbox 内部已更新状态）
        db = _new_db()
        try:
            st = db.fetchone(
                "SELECT status, retry_count, error_message FROM favorite_downloads WHERE id = ?",
                (fd_id,),
            )
        finally:
            db.close()

        if st and st["status"] == STATUS_DONE:
            # 成功：重置重试计数 + 记录尝试日期
            db = _new_db()
            try:
                db.execute(
                    "UPDATE favorite_downloads SET retry_count = 0, last_attempt = ?,"
                    " updated_at = datetime('now') WHERE id = ?",
                    (today, fd_id),
                )
            finally:
                db.close()
            logger.info("[链] 下载成功: record_id=%s, user_id=%s", record_id, user_id)
            return ("done", "")

        # 失败：retry_count 原子递增（合并进主 UPDATE），达上限转 abandoned
        error = (st["error_message"] if st else None) or "下载失败"
        db = _new_db()
        try:
            after = db.fetchone(
                "SELECT retry_count FROM favorite_downloads WHERE id = ?", (fd_id,)
            )
            new_count = (after["retry_count"] if after else 0) + 1
        finally:
            db.close()
        update_status(record_id, user_id, STATUS_FAILED, error=error, retry_increment=True)
        if new_count >= MAX_RETRIES:
            db = _new_db()
            try:
                db.execute(
                    "UPDATE favorite_downloads SET status = 'abandoned', retry_count = ?,"
                    " last_attempt = ?, updated_at = datetime('now') WHERE id = ?",
                    (new_count, today, fd_id),
                )
            finally:
                db.close()
            logger.warning(
                "[链] 下载放弃（重试 %d 次）: record_id=%s, user_id=%s", new_count, record_id, user_id
            )
            # 放弃是终态，必须留痕：重试耗尽后用户应收到明确提示，
            # 而不是永远看到一条"pending"却再也下不下来（批量路径由运行汇总承载）
            if notify:
                _notify_abandoned(user_id, record_id, error)
            return ("abandoned", f"{std_no}：{error}")

        logger.warning("[链] 下载失败(第%d次): record_id=%s, user_id=%s", new_count, record_id, user_id)
        return ("failed", f"{std_no}：{error}")

    except FavoriteSkip as e:
        # 业务终态跳过（采标版权受限 / 非国标）：重试 7 天结果一样，直接终态
        _abandon_terminal(fd_id, record_id, user_id, today, str(e), notify=notify)
        logger.warning("[链] 下载跳过（终态）: record_id=%s, user_id=%s, reason=%s", record_id, user_id, e)
        return ("skipped", f"{std_no}：{e}")
    except Exception as e:  # download_to_inbox 自身异常（未内部捕获时兜底）
        update_status(record_id, user_id, STATUS_FAILED, error=str(e), retry_increment=True)
        logger.error("[链] 下载异常: record_id=%s, user_id=%s, error=%s", record_id, user_id, e)
        return ("failed", f"{std_no}：{e}")


def _abandon_terminal(
    fd_id: int, record_id: int, user_id: int, today: str, error: str, notify: bool = True
) -> None:
    """业务终态直接放弃：retry_count 拉到上限（保证不再入选）+ 通知一次。

    与"重试耗尽后放弃"的区别：不写 failed、不逐日重试，用户当天就收到明确结论。
    批量路径（notify=False）不发逐条通知，由运行汇总承载。
    """
    db = _new_db()
    try:
        db.execute(
            "UPDATE favorite_downloads SET status = 'abandoned', retry_count = ?,"
            " last_attempt = ?, error_message = ?, updated_at = datetime('now') WHERE id = ?",
            (MAX_RETRIES, today, error[:200], fd_id),
        )
    finally:
        db.close()
    if notify:
        _notify_abandoned(user_id, record_id, error)


def _notify_abandoned(user_id: int, record_id: int, error: str) -> None:
    """重试耗尽后的放弃通知（原 archive_retry_service 的实现随该死代码服务迁入）。

    放弃是终态：原先只有死代码服务会发 archive_abandoned，活跃链仅写日志，
    导致用户对"收藏再也下不下来"无感（生产 28 条 abandoned / 0 条通知）。
    通知失败只记日志，不影响状态机。
    """
    try:
        db = _new_db()
        try:
            row = db.fetchone(
                "SELECT standard_number, std_name FROM announcement_record WHERE id = ?",
                (record_id,),
            )
        finally:
            db.close()
        std_info = f"{row['standard_number']} {row['std_name']}" if row else f"record#{record_id}"

        from pilotstd.manager.facade import StandardManager

        StandardManager().notification_mgr.send_event(
            "archive_abandoned",
            {
                "user_id": user_id,
                "record_id": record_id,
                "standard_info": std_info,
                "error": error,
            },
        )
    except Exception:
        logger.warning("发送归档放弃通知失败", exc_info=True)


def process_chain(download_engine: Any = None, notify_per_record: bool = False) -> dict[str, int]:
    """主入口：由 cron 调用。

    ★ 倒序执行框架：先处理最下游，再处理上游，防止同一次运行中
    上游产出被下游立即消费而退化为同步链式调用。
    当前仅"下载"阶段（贴合现有 download_to_inbox 一体链路）；
    未来扩展规范化/归档阶段时，在 stats 中按 下游→上游 顺序追加阶段调用。

    download_engine：调度器注入的下载引擎，其节奏参数（分批/并发/批间冷却）
    决定本次运行的吞吐；为 None 时退化为顺序处理。

    notify_per_record：默认 False —— 批量运行按批汇总为 1 条通知（防 Telegram 429）；
    传 True 可恢复逐条通知（单条调试用）。
    """
    stats: dict[str, int] = {}
    logger.info("[链] 开始处理收藏下载链（倒序）...")

    # ① 最下游优先（当前即唯一阶段：下载即归档）
    stats["download"] = process_pending_downloads(download_engine, notify_per_record)

    logger.info("[链] 处理完成: %s", stats)
    return stats
