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
from datetime import date, timedelta
from typing import Any, Optional

from pilotstd.core.config import get_db_path
from pilotstd.core.db.database import Database

logger = logging.getLogger(__name__)

# ── 批处理约束 ─────────────────────────────────────────────
BATCH_SIZE = 10
MAX_RETRIES = 3
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


def get_records_by_status(limit: int = BATCH_SIZE) -> list[dict[str, Any]]:
    """扫描待处理记录（pending/failed，未达重试上限，已过冷却期，且为国标）。

    冷却期语义与现有 archive_retry_service 一致：announcement_record.publish_date
    距今不足 COOLDOWN_DAYS 天的不处理（发布保护窗口）。
    类别闸：仅 NationalStd（国标）有下载适配器（std_gov→openstd_download 是唯一映射），
    行标/地标在此直接排除，不进入下载阶段也不消耗重试次数。
    """
    db = _new_db()
    try:
        cooldown_cutoff = (date.today() - timedelta(days=COOLDOWN_DAYS)).isoformat()
        rows = db.fetchall(
            "SELECT fd.id, fd.favorite_id, fd.user_id, fd.record_id, ar.publish_date"
            " FROM favorite_downloads fd"
            " JOIN announcement_record ar ON fd.record_id = ar.id"
            " WHERE fd.status IN ('pending', 'failed')"
            " AND fd.standard_type = 'NationalStd'"
            " AND (fd.retry_count IS NULL OR fd.retry_count < ?)"
            " AND COALESCE(NULLIF(TRIM(ar.publish_date), ''), CURRENT_DATE) <= ?"
            " ORDER BY fd.last_attempt ASC NULLS FIRST, fd.updated_at ASC"
            " LIMIT ?",
            (MAX_RETRIES, cooldown_cutoff, limit),
        )
        return [dict(r) for r in rows]
    finally:
        db.close()


def process_pending_downloads() -> int:
    """阶段 1（当前唯一阶段）：pending/failed → 调用下载 → done / failed / abandoned。

    复用现有 download_to_inbox（下载+归档一体，内部自行更新 downloading/archiving/done/failed）；
    处理器在其返回后按实际落库状态判定成败并原子维护重试计数。
    """
    records = get_records_by_status()
    processed = 0
    today = date.today().isoformat()

    for rec in records:
        fd_id = rec["id"]
        record_id = rec["record_id"]
        user_id = rec["user_id"]
        favorite_id = rec["favorite_id"]

        try:
            from pilotstd.tasks.favorite_download import download_to_inbox  # 延迟导入避免循环依赖

            download_to_inbox(favorite_id, user_id, record_id)

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
            else:
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
                    # 而不是永远看到一条"pending"却再也下不下来
                    _notify_abandoned(user_id, record_id, error)
                else:
                    logger.warning("[链] 下载失败(第%d次): record_id=%s, user_id=%s", new_count, record_id, user_id)

        except Exception as e:  # download_to_inbox 自身异常（未内部捕获时兜底）
            update_status(record_id, user_id, STATUS_FAILED, error=str(e), retry_increment=True)
            logger.error("[链] 下载异常: record_id=%s, user_id=%s, error=%s", record_id, user_id, e)

        processed += 1

    return processed


def _notify_abandoned(user_id: int, record_id: int, error: str) -> None:
    """重试耗尽后的放弃通知（自 archive_retry_service 迁移而来）。

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


def process_chain() -> dict[str, int]:
    """主入口：由 cron 调用。

    ★ 倒序执行框架：先处理最下游，再处理上游，防止同一次运行中
    上游产出被下游立即消费而退化为同步链式调用。
    当前仅"下载"阶段（贴合现有 download_to_inbox 一体链路）；
    未来扩展规范化/归档阶段时，在 stats 中按 下游→上游 顺序追加阶段调用。
    """
    stats: dict[str, int] = {}
    logger.info("[链] 开始处理收藏下载链（倒序）...")

    # ① 最下游优先（当前即唯一阶段：下载即归档）
    stats["download"] = process_pending_downloads()

    logger.info("[链] 处理完成: %s", stats)
    return stats
