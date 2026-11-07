# 模块：项目/管理器/_服务脚本
# 时效性检查服务—供接口层调用

import logging
import threading
from typing import Any

from pilotstd.core.time_utils import iso_now

logger = logging.getLogger(__name__)


class ValidityService:
    """时效性检查业务逻辑。"""

    def __init__(self, manager: Any):
        self._mgr = manager
        # 调度器可能并发触发 drain；同一实例只允许一个消费者
        self._queue_lock = threading.Lock()

    def get_history(self, page: int = 1, size: int = 20) -> dict[str, Any]:
        """获取时效性检查历史记录（分页）。"""
        db = self._mgr.db
        offset = (page - 1) * size
        total = db.fetchone(
            "SELECT COUNT(DISTINCT DATE(last_checked_at)) AS cnt "
            "FROM standard_validity WHERE last_checked_at IS NOT NULL"
        )
        rows = db.fetchall(
            "SELECT DATE(last_checked_at) AS check_date, "
            "COUNT(*) AS checked_count, "
            "SUM(CASE WHEN last_status != status THEN 1 ELSE 0 END) AS changed_count "
            "FROM standard_validity "
            "WHERE last_checked_at IS NOT NULL "
            "GROUP BY DATE(last_checked_at) "
            "ORDER BY check_date DESC LIMIT ? OFFSET ?",
            (size, offset),
        )
        return {
            "total": total["cnt"] if total else 0,
            "page": page,
            "page_size": size,
            "items": [
                {
                    "check_date": r["check_date"],
                    "checked_count": r["checked_count"],
                    "changed_count": r["changed_count"],
                    "status": "success",
                }
                for r in rows
            ],
        }

    def enqueue_files(self, file_paths: list[str]) -> dict[str, Any]:
        """将文件路径列表加入时效性检查队列（只入队，不假装已检查）。"""
        db = self._mgr.db
        inserted = 0
        last_error = ""
        now = iso_now()
        for fp in file_paths:
            try:
                cur = db.execute(
                    "INSERT OR IGNORE INTO validity_check_queue "
                    "(file_path, status, error, created_at, updated_at) "
                    "VALUES (?, 'pending', '', ?, ?)",
                    (str(fp), now, now),
                )
                # OR IGNORE：已存在 pending 行时 rowcount=0，不应谎报新增
                inserted += int(cur.rowcount or 0)
            except Exception as e:
                # 单条入队失败不阻断其余文件，但“少入队”必须可见
                last_error = str(e)
                logger.warning("enqueue validity file failed (%s): %s", fp, e)
        return {
            "ok": not last_error or inserted > 0,
            "enqueued": inserted,
            "total": len(file_paths),
            "error": last_error,
        }

    def _standard_number_for_path(self, file_path: str) -> str | None:
        """把 file_index 路径还原为标准号；未索引返回 None。"""
        db = self._mgr.db
        row = db.fetchone(
            "SELECT logical_code, number, part, year FROM file_index WHERE file_path=?",
            (file_path,),
        )
        if not row:
            # Windows 路径分隔符差异的兜底
            row = db.fetchone(
                "SELECT logical_code, number, part, year FROM file_index "
                "WHERE REPLACE(file_path, '\\', '/')=?",
                (file_path.replace("\\", "/"),),
            )
        if not row:
            return None
        code = str(row.get("logical_code") or "").strip()
        number = int(row.get("number") or 0)
        part = int(row.get("part") or -1)
        year = int(row.get("year") or 0)
        if not code or number <= 0:
            return None
        suffix = f".{part}" if part > 0 else ""
        year_suffix = f"-{year}" if year > 0 else ""
        return f"{code} {number}{suffix}{year_suffix}"

    def process_pending(self, limit: int = 20) -> dict[str, int]:
        """消费待检查队列：路径 → 标准号 → 时效性检查 → 更新状态。"""
        if not self._queue_lock.acquire(blocking=False):
            return {"processed": 0, "success": 0, "failed": 0, "skipped": 1}
        try:
            db = self._mgr.db
            # 上次进程崩溃可能留下 running；单消费者下安全地放回待处理
            db.execute(
                "UPDATE validity_check_queue SET status='pending', "  # i18n-allow: 队列状态说明
                "error='上次检查中断，已重新入队', updated_at=? WHERE status='running'",  # i18n-allow: 队列状态说明
                (iso_now(),),
            )
            rows = db.fetchall(
                "SELECT id, file_path FROM validity_check_queue "
                "WHERE status='pending' ORDER BY id LIMIT ?",
                (limit,),
            )
            checker = getattr(self._mgr, "validity_checker", None)
            query_engine = getattr(self._mgr, "query_engine", None)
            success = failed = 0
            for row in rows:
                # 原子认领，避免同一行被重复处理
                cur = db.execute(
                    "UPDATE validity_check_queue SET status='running', updated_at=? "
                    "WHERE id=? AND status='pending'",
                    (iso_now(), row["id"]),
                )
                if int(cur.rowcount or 0) == 0:
                    continue
                std = self._standard_number_for_path(str(row["file_path"]))
                if not std:
                    db.execute(
                        "UPDATE validity_check_queue SET status='failed', error=?, updated_at=? WHERE id=?",
                        ("文件未索引，无法确定标准号", iso_now(), row["id"]),  # i18n-allow: 队列失败原因
                    )
                    failed += 1
                    continue
                if checker is None:
                    db.execute(
                        "UPDATE validity_check_queue SET status='failed', error=?, updated_at=? WHERE id=?",
                        ("时效性检查器未初始化", iso_now(), row["id"]),  # i18n-allow: 队列失败原因
                    )
                    failed += 1
                    continue
                try:
                    result = checker.check_standard(std, query_engine=query_engine)
                    if result is None:
                        raise RuntimeError("check_standard 返回空结果")  # i18n-allow: 内部错误
                    db.execute(
                        "UPDATE validity_check_queue SET status='success', error='', updated_at=? WHERE id=?",
                        (iso_now(), row["id"]),
                    )
                    success += 1
                except Exception as exc:
                    db.execute(
                        "UPDATE validity_check_queue SET status='failed', error=?, updated_at=? WHERE id=?",
                        (str(exc)[:500], iso_now(), row["id"]),
                    )
                    failed += 1
            return {"processed": len(rows), "success": success, "failed": failed, "skipped": 0}
        finally:
            self._queue_lock.release()
