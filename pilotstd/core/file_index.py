# pilotstd/core/file_index.py
# 本地文件索引表 — ParsedStdInfo 持久化，避免每次启动重扫

from __future__ import annotations

import logging
import os
import threading
from datetime import datetime
from typing import Any, Optional

from pilotstd.models import ParsedStdInfo

from .db import Database
from .file_utils import hash_file_content

# 核心表名常量，统一管理避免硬编码字符串散布
FILE_INDEX_TABLE = "file_index"
NETWORK_CACHE_TABLE = "standard_info_cache"
ANNOUNCEMENT_CACHE_TABLE = "announcement_match"

logger = logging.getLogger(__name__)


class FileIndexRepository:
    """本地文件索引仓库。"""

    def __init__(self, db: Database):
        self._db = db
        # 校验完成事件：扫描器初始化时需等待校验完成才能依赖索引去重
        self._validation_complete = threading.Event()
        self._stop_event = threading.Event()
        self._validation_thread: threading.Thread | None = None
        # 延迟启动后台校验，避免阻塞启动流程
        self._start_delayed_validation()

    # ---- 校验 ----

    @property
    def is_validation_complete(self) -> bool:
        """校验是否完成。未完成前扫描器应降级，不依赖索引去重。"""
        return self._validation_complete.is_set()

    def stop(self) -> None:
        """停止后台校验线程。设置停止信号，关闭 DB，等待线程退出。"""
        self._stop_event.set()
        self._validation_complete.set()
        if hasattr(self, "_db") and self._db is not None:
            try:
                self._db.close_all()
            except Exception:
                pass
        if self._validation_thread is not None and self._validation_thread.is_alive():
            self._validation_thread.join(timeout=5)

    def _start_delayed_validation(self) -> None:
        """启动后台校验线程。

        延迟策略：根据记录数自适应（5~30s），用 _stop_event.wait() 等待，
        可被 stop() 立即中断。测试模式下跳过延迟。

        校验逻辑（含 os.path.exists 等文件 IO）在 daemon 线程中执行，
        不阻塞主线程。完成或失败均设置 _validation_complete。
        """

        def _run() -> None:
            if self._stop_event.is_set():
                self._validation_complete.set()
                return

            # 计算延迟（秒）
            if os.environ.get("PILOTSTD_TEST_MODE") == "1":
                delay = 0
            else:
                try:
                    row = self._db.fetchone(f"SELECT COUNT(*) AS cnt FROM {FILE_INDEX_TABLE}")
                    row_count = row["cnt"] if row else 0
                    delay = min(30, max(5, row_count / 500))
                except Exception:
                    delay = 10

            # 用 Event.wait() 替代 time.sleep()——可被 stop() 即时中断
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

            try:
                logging.getLogger("pilotstd.file_index").info(
                    "file_index 启动校验完成（延迟 %.1fs），清理 %d 条失效记录",
                    delay,
                    deleted,
                )
            except Exception:
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
        part: Optional[int] = None,
        std_name: str = "",
        file_hash: str = "",
        status: str = "现行",
    ) -> None:
        # 文件存在时自动计算哈希，否则使用传入值（如从缓存恢复场景）
        if not file_hash and os.path.exists(file_path):
            file_hash = hash_file_content(file_path)
        now = datetime.now().isoformat()
        # part 为 None 时用 -1 表示"无分篇"，SQLite 中 -1 便于统一查询
        part_val = part if part is not None else -1
        existing = self._db.fetchone(f"SELECT id FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))
        if existing:
            # 已存在则更新，keep 原有 id 保证外键引用不失效
            self._db.execute(
                f"UPDATE {FILE_INDEX_TABLE} SET logical_code=?, number=?, year=?, "
                "part=?, std_name=?, file_hash=?, status=?, scanned_at=? WHERE id=?",
                (
                    logical_code,
                    number,
                    year,
                    part_val,
                    std_name,
                    file_hash,
                    status,
                    now,
                    existing["id"],
                ),
            )
        else:
            # 新文件直接插入
            self._db.execute(
                f"INSERT INTO {FILE_INDEX_TABLE} "
                "(file_path, logical_code, number, year, part, std_name, file_hash, status, scanned_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    file_path,
                    logical_code,
                    number,
                    year,
                    part_val,
                    std_name,
                    file_hash,
                    status,
                    now,
                ),
            )

    def remove(self, file_path: str) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))

    # ---- 读取 ----

    def get(self, file_path: str) -> Optional[dict[str, Any]]:
        return self._db.fetchone(f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))

    def get_all(self) -> list[dict[str, Any]]:
        return self._db.fetchall(f"SELECT * FROM {FILE_INDEX_TABLE} ORDER BY logical_code, number, part")

    def find_by_standard(
        self, logical_code: str, number: int, year: int, part: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """查找同标准号的所有索引记录（用于去重：分类变化致旧路径残留）。"""
        part_val = part if part is not None else -1
        return self._db.fetchall(
            f"SELECT * FROM {FILE_INDEX_TABLE} WHERE logical_code=? AND number=? AND year=? AND part=?",
            (logical_code, number, year, part_val),
        )

    def find_by_hash(self, file_hash: str) -> Optional[dict[str, Any]]:
        """通过文件哈希查找（用于检测移动/重命名）。"""
        return self._db.fetchone(f"SELECT * FROM {FILE_INDEX_TABLE} WHERE file_hash=?", (file_hash,))

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

    def count(self) -> int:
        """返回索引表中的记录总数。"""
        row = self._db.fetchone(f"SELECT COUNT(*) as cnt FROM {FILE_INDEX_TABLE}")
        return row["cnt"] if row else 0

    def get_status_stats(self) -> dict[str, int]:
        """返回按状态分组的统计：现行/废止/待确认/即将实施数量。"""
        try:
            rows = self._db.fetchall(
                f"SELECT status, COUNT(*) as cnt FROM {FILE_INDEX_TABLE} WHERE status IS NOT NULL GROUP BY status"
            )
            s = {r["status"]: r["cnt"] for r in rows}
        except Exception:
            return {"current": 0, "expired": 0, "pending": 0, "upcoming": 0}
        # 将废止和被代替合并为 expired，统一对外口径
        return {
            "current": s.get("现行", 0),
            "expired": s.get("废止", 0) + s.get("被代替", 0),
            "pending": s.get("待确认", 0),
            "upcoming": s.get("即将实施", 0),
        }

    def clear_all(self) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE}")

    # ---- 内部 ----

    def restore_parsed(self, file_path: str) -> Optional["ParsedStdInfo"]:
        """从索引恢复 ParsedStdInfo，同时查缓存填充查询结果字段。"""
        row = self.get(file_path)
        if not row:
            return None
        from ..models import ParsedStdInfo  # 延迟导入，避免循环引用

        info = ParsedStdInfo(
            raw_filename=os.path.basename(file_path),
            logical_code=row["logical_code"],
            number=row["number"],
            year=row["year"],
            # part=-1 表示无分篇，恢复为 None 以保持类型一致性
            part=row["part"] if row["part"] != -1 else None,
            std_name=row["std_name"],
            source_path=file_path,
        )
        # 从缓存表补充查询结果字段（状态、名称、采标信息）
        self._restore_cache_fields(info)
        return info

    def _restore_cache_fields(self, info: "ParsedStdInfo") -> None:
        """从缓存表恢复查询结果字段。

        优先级：网络缓存（主数据源）> 公告缓存（补充）。
        网络缓存须检查过期时间，公告缓存永久有效。
        """
        from datetime import datetime

        std_num = info.get_full_number()
        datetime.now().isoformat()

        # 先查网络缓存（主数据源，事件驱动失效）
        row = self._db.fetchone(
            f"SELECT result_json FROM {NETWORK_CACHE_TABLE} WHERE standard_number = ? LIMIT 1",
            (std_num,),
        )

        if row and row["result_json"]:
            self._apply_cache_result(row["result_json"], info)
            return

        # 网络缓存未命中，回退到公告缓存（永久有效）
        ann_row = self._db.fetchone(
            f"SELECT result_json FROM {ANNOUNCEMENT_CACHE_TABLE} WHERE standard_number = ? LIMIT 1",
            (std_num,),
        )
        if ann_row and ann_row["result_json"]:
            self._apply_cache_result(ann_row["result_json"], info)

    @staticmethod
    def _apply_cache_result(result_json: str, info: "ParsedStdInfo") -> None:
        """将缓存的 JSON 结果应用到 ParsedStdInfo 对象。"""
        import json

        try:
            cached = json.loads(result_json)
            # 仅 exact 匹配的结果才覆盖字段，避免不准确的数据污染
            if cached.get("match_status") == "exact":
                info.effect_status = cached.get("status", "")
                info.found_name = cached.get("standard_name", "")
                info.is_adopted = cached.get("is_adopted", False)
                info.match_status = "exact"
        except (json.JSONDecodeError, TypeError):
            # 缓存 JSON 损坏时静默跳过，不影响主流程
            pass

    def find_moved_files(self, candidates: list[tuple[str, str]]) -> list[dict[str, Any]]:
        """检测文件移动/重命名：哈希命中但路径不同的返回原索引记录。

        Args:
            candidates: [(file_path, file_hash), ...] 未被路径匹配到的文件列表
        Returns:
            [{"old_path": ..., "new_path": ..., "logical_code": ..., ...}, ...]
        """
        result = []
        for new_path, file_hash in candidates:
            if not file_hash:
                continue
            row = self.find_by_hash(file_hash)
            if row and row["file_path"] != new_path:
                result.append(
                    {
                        "old_path": row["file_path"],
                        "new_path": new_path,
                        "logical_code": row["logical_code"],
                        "number": row["number"],
                        "year": row["year"],
                        "part": row["part"],
                        "std_name": row["std_name"],
                    }
                )
        return result

    def get_full_info(self, logical_code: str, number: int) -> list[dict[str, Any]]:
        """联合本地文件索引与两个缓存表，返回离线完整信息。

        JOIN 使用 LIKE 前缀匹配，兼容新旧两种连接号格式。
        网络缓存优先，过期后回退到公告缓存。
        """
        rows = self._db.fetchall(
            f"SELECT fi.*, "
            f"nc.result_json AS nc_result_json, "
            f"nc.cached_at AS nc_cached_at, "
            f"ac.result_json AS ac_result_json, "
            f"ac.cached_at AS ac_cached_at "
            f"FROM {FILE_INDEX_TABLE} fi "
            f"LEFT JOIN {NETWORK_CACHE_TABLE} nc "
            f"ON nc.standard_number LIKE (fi.logical_code || ' ' || fi.number || '%') "
            f"LEFT JOIN {ANNOUNCEMENT_CACHE_TABLE} ac "
            f"ON ac.standard_number LIKE (fi.logical_code || ' ' || fi.number || '%') "
            f"WHERE fi.logical_code = ? AND fi.number = ?",
            (logical_code, number),
        )

        import json

        result = []
        for row in rows:
            info = {
                "file_path": row["file_path"],
                "logical_code": row["logical_code"],
                "number": row["number"],
                "year": row["year"],
                "part": row["part"] if row["part"] != -1 else None,
                "std_name": row["std_name"],
                "effect_status": "",
                "found_name": "",
                "is_adopted": False,
                "match_status": "",
                "cached_at": "",
            }
            # 优先网络缓存（事件驱动失效，不再按时间过期），回退到公告缓存
            cache_json = None
            if row["nc_result_json"]:
                cache_json = row["nc_result_json"]
                info["cached_at"] = row["nc_cached_at"] or ""
            if cache_json is None and row["ac_result_json"]:
                cache_json = row["ac_result_json"]
                info["cached_at"] = row["ac_cached_at"] or ""
            if cache_json:
                try:
                    cached = json.loads(cache_json)
                    info["effect_status"] = cached.get("status", "")
                    info["found_name"] = cached.get("standard_name", "")
                    info["is_adopted"] = cached.get("is_adopted", False)
                    info["match_status"] = cached.get("match_status", "")
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(info)
        return result
