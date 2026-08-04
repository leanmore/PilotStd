# pilotstd/core/file_index.py
# 本地文件索引表 — 写入与校验管理。查询方法已提取至 _file_index_query.py
# THREADING: single-threaded, no lock needed
# 选型：SQLite 而非内存字典（跨进程共享，WAL 模式读并发）；
# hash_file_content 采样策略（≤1MB 全量，>1MB 前 1MB+末 64KB+文件大小）平衡碰撞率与 I/O；
# 后台 daemon 延迟校验路径有效性（自适应 5~30s），失效直接 DELETE 而非标记

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime

from ._file_index_query import (  # noqa: F401 — 由外部模块导入消费
    ANNOUNCEMENT_CACHE_TABLE,
    FILE_INDEX_TABLE,
    NETWORK_CACHE_TABLE,
    FileIndexQuery,
)
from .db import Database
from .file_utils import hash_file_content

logger = logging.getLogger(__name__)


class FileIndexRepository:
    """本地文件索引仓库。

    查询方法由 FileIndexQuery 提供（组合注入）；本类管理校验线程、写入和清理逻辑。
    """

    def __init__(self, db: Database):
        self._db = db
        self._query = FileIndexQuery(db)
        self._validation_complete = threading.Event()
        self._stop_event = threading.Event()
        self._validation_thread: threading.Thread | None = None
        self._start_delayed_validation()

    @property
    def db(self) -> Database:
        """公共数据库连接访问器。

        ⚠️ 使用约束：
        - 仅用于只读查询（SELECT）和受控更新（UPDATE）
        - 禁止在该连接上执行 DDL（CREATE/DROP/ALTER）
        - 禁止显式事务管理（BEGIN/COMMIT/ROLLBACK）
        - 连接由 FileIndexRepository 管理，调用方不应自行关闭
        """
        return self._db

    # ---- 校验 ----

    @property
    def is_validation_complete(self) -> bool:
        """校验是否完成。未完成前扫描器应降级，不依赖索引去重。"""
        return self._validation_complete.is_set()

    def stop(self) -> None:
        """停止后台校验线程。设置停止信号，关闭 DB，等待线程退出。"""
        self._stop_event.set()
        self._validation_complete.set()
        if self._validation_thread is not None and self._validation_thread.is_alive():
            self._validation_thread.join(timeout=5)
        if hasattr(self, "_db") and self._db is not None:
            try:
                self._db.close_all()
            except Exception:
                pass

    def _start_delayed_validation(self) -> None:
        """启动后台校验线程。

        延迟策略：根据记录数自适应（5~30s），用 _stop_event.wait() 等待，
        可被 stop() 立即中断。测试模式下跳过延迟。

        校验逻辑（含 os.path.exists 等文件 IO）在 daemon 线程中执行，
        不阻塞主线程。完成或失败均设置 _validation_complete。
        """

        def _run() -> None:
            """后台校验线程入口：自适应延迟后逐条校验文件路径是否存在。"""
            if self._stop_event.is_set():
                self._validation_complete.set()
                return

            if os.environ.get("PILOTSTD_TEST_MODE") == "1":
                delay = 0
            else:
                try:
                    row = self._db.fetchone(f"SELECT COUNT(*) AS cnt FROM {FILE_INDEX_TABLE}")
                    row_count = row["cnt"] if row else 0
                    delay = min(30, max(5, row_count / 500))
                except Exception:
                    delay = 10

            if delay > 0:
                self._stop_event.wait(delay)

            if self._stop_event.is_set():
                self._validation_complete.set()
                return

            try:
                deleted = self.validate_paths()
            except Exception:
                deleted = 0
            self._validation_complete.set()

            if not self._stop_event.is_set():
                try:
                    logger.info(
                        "file_index 启动校验完成（延迟 %.1fs），清理 %d 条失效记录",
                        delay,
                        deleted,
                    )
                except (ValueError, OSError):
                    pass

        t = threading.Thread(target=_run, daemon=True)
        self._validation_thread = t
        t.start()

    def validate_paths(self) -> int:
        """逐条校验索引记录的目标路径是否存在，失效则删除。返回清除数量。"""
        if self._stop_event.is_set():
            return 0
        try:
            rows = self._db.fetchall(f"SELECT id, file_path FROM {FILE_INDEX_TABLE}")
        except Exception:
            self._validation_complete.set()
            return 0
        deleted = 0
        for r in rows:
            if not os.path.exists(r["file_path"]):
                try:
                    self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE id=?", (r["id"],))
                    deleted += 1
                except Exception:
                    logger.debug("删除无效记录失败: id=%s", r["id"], exc_info=True)
        self._validation_complete.set()
        return deleted

    # ---- 写入 ----

    def upsert(
        self,
        file_path: str,
        logical_code: str,
        number: int,
        year: int,
        part: int | None = None,
        std_name: str = "",
        file_hash: str = "",
        status: str = "现行",
        raw_number: str = "",
    ) -> None:
        """插入或更新文件索引记录。若文件存在则自动计算哈希。"""
        if not file_hash and os.path.exists(file_path):
            file_hash = hash_file_content(file_path)
        now = datetime.now().isoformat()
        part_val = part if part is not None else -1
        raw = raw_number if raw_number else str(number)
        existing = self._db.fetchone(f"SELECT id FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))
        if existing:
            self._db.execute(
                f"UPDATE {FILE_INDEX_TABLE} SET logical_code=?, number=?, year=?, "
                "part=?, std_name=?, file_hash=?, status=?, scanned_at=?, raw_number=? WHERE id=?",
                (logical_code, number, year, part_val, std_name, file_hash, status, now, raw, existing["id"]),
            )
        else:
            self._db.execute(
                f"INSERT INTO {FILE_INDEX_TABLE} "
                "(file_path, logical_code, number, year, part, std_name, file_hash, status, scanned_at, raw_number) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (file_path, logical_code, number, year, part_val, std_name, file_hash, status, now, raw),
            )

    def remove(self, file_path: str) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))

    def clear_stale(self) -> int:
        """清除文件已不存在的索引记录（增量：仅检查超过 7 天未验证或从未验证的记录），返回清除数量。"""
        rows = self._db.fetchall(
            f"SELECT id, file_path FROM {FILE_INDEX_TABLE} "
            "WHERE last_checked IS NULL OR last_checked < date('now', '-7 days')"
        )
        deleted = 0
        for r in rows:
            if os.path.exists(r["file_path"]):
                self._db.execute(
                    f"UPDATE {FILE_INDEX_TABLE} SET last_checked = date('now') WHERE id = ?",
                    (r["id"],),
                )
            else:
                self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE id = ?", (r["id"],))
                deleted += 1
        return deleted

    def clear_all(self) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE}")

    # ---- 查询代理（委托 FileIndexQuery）----

    def get(self, file_path: str):
        return self._query.get(file_path)

    def get_all(self):
        return self._query.get_all()

    def find_by_standard(self, logical_code: str, number: int, year: int, part=None):
        return self._query.find_by_standard(logical_code, number, year, part)

    def find_by_hash(self, file_hash: str):
        return self._query.find_by_hash(file_hash)

    def count(self) -> int:
        return self._query.count()

    def get_status_stats(self) -> dict:
        return self._query.get_status_stats()

    def restore_parsed(self, file_path: str):
        """从索引恢复 ParsedStdInfo。委托 FileIndexQuery 查询，本地处理缓存恢复。"""
        row = self._query.get(file_path)
        if not row:
            return None
        from pilotstd.models import ParsedStdInfo
        import os

        info = ParsedStdInfo(
            raw_filename=os.path.basename(file_path),
            logical_code=row["logical_code"],
            number=row["number"],
            raw_number=row.get("raw_number", ""),
            year=row["year"],
            part=row["part"] if row["part"] != -1 else None,
            std_name=row["std_name"],
            source_path=file_path,
        )
        self._restore_cache_fields(info)
        return info

    def find_moved_files(self, candidates):
        return self._query.find_moved_files(candidates)

    def get_full_info(self, logical_code: str, number: int):
        return self._query.get_full_info(logical_code, number)

    def _restore_cache_fields(self, info):
        return self._query._restore_cache_fields(info)

    @staticmethod
    def _apply_cache_result(result_json: str, info):
        return FileIndexQuery._apply_cache_result(result_json, info)
