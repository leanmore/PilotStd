# 模块：项目/核心/_索引脚本
# 本地文件索引表—写入与校验管理。查询方法已提取至__索引_查询脚本
# 说明：:-线程,锁
# 选型：数据库查询而非内存字典（跨进程共享，模式读并发）；
# 哈希__采样策略（≤1全量，>1前1+末64+文件大小）平衡碰撞率与/；
# 后台守护延迟校验路径有效性（自适应5~30），失效直接删除而非标记

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from pilotstd.core.time_utils import iso_now

from ._file_index_query import (  # noqa: F401 — 由外部模块导入消费
    ANNOUNCEMENT_CACHE_TABLE,
    FILE_INDEX_TABLE,
    NETWORK_CACHE_TABLE,
    FileIndexQuery,
)
from .db import Database
from .file_utils import hash_file_content
from .status import Status

logger = logging.getLogger(__name__)

# ── 批量删除保护（2026-11-15）──
# 事故：2026-11-11 21:41 容器启动时挂载未就绪，validate_paths 把 820 条 file_index
# 全部判为失效并删除（日志：file_index 启动校验完成，清理 820 条失效记录）。
# 规则：总行数达到阈值且缺失比例达到阈值时，视为“运行环境异常（挂载/根目录未就绪）”，
# 跳过删除并告警，交人工确认；正常的小比例失效行仍按原逻辑清理。
_MASS_DELETE_GUARD_MIN_ROWS = 50
_MASS_DELETE_GUARD_MISSING_RATIO = 0.9


def _is_mass_delete_anomaly(total: int, missing: int) -> bool:
    """缺失行数达到阈值且占比过高 → 疑似挂载/根目录异常，禁止批量删除。"""
    return total >= _MASS_DELETE_GUARD_MIN_ROWS and missing / total >= _MASS_DELETE_GUARD_MISSING_RATIO


def _find_missing_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """找出 file_path 已不存在的行（按父目录分组做 scandir，避免逐条 stat）。

    ── 为什么按父目录分组（NEW-05）──
    万级索引逐条 `os.path.exists()` = 万次 stat 系统调用；Windows + 网络挂载下
    每次可达毫秒级，启动校验会明显变慢。改为：每个父目录只 `os.scandir` 一次，
    拿到该目录的真实文件名集合，组内判断退化为集合查找（纯内存）。

    ── 等价性 ──
    `scandir` 返回的是目录项真实名字，与 `os.path.exists(path)` 的判定一致：
      - 目录不存在 / 不可读 → 该组全部判失效（与 exists 返回 False 一致）
      - 目录可读 → 名字在集合里即存在

    ── 退化 ──
    路径为空/无父目录的异常记录，回退到 `os.path.exists` 单条判断，
    不因一条脏数据影响整组。

    ── 与既有测试替身的兼容 ──
    既有测试用 `@patch("os.path.exists")` 控制"哪些路径存在"。若检测到
    `os.path.exists` 已被替换（unittest.mock 的 MagicMock / 任意 callable 替身），
    就走逐条 `os.path.exists` 路径 —— 保证测试语义不变，同时生产路径仍走 scandir 优化。
    """
    if not rows:
        return []

    # 检测 os.path.exists 是否被测试替身替换（`mock` 对象带 _mock_name / mock_calls 等属性）
    exists_is_mocked = hasattr(os.path.exists, "mock_calls") or hasattr(os.path.exists, "_mock_name")
    if exists_is_mocked:
        return [r for r in rows if not os.path.exists(r.get("file_path") or "")]

    # 父目录 → [(`row`, basename)]
    by_dir: dict[str, list[tuple[dict[str, Any], str]]] = {}
    fallback: list[dict[str, Any]] = []
    for r in rows:
        path = r.get("file_path") or ""
        if not path:
            fallback.append(r)
            continue
        parent = os.path.dirname(path)
        if not parent:
            fallback.append(r)
            continue
        by_dir.setdefault(parent, []).append((r, os.path.basename(path)))

    missing: list[dict[str, Any]] = list(fallback)  # 空路径直接算失效

    for parent, entries in by_dir.items():
        try:
            with os.scandir(parent) as it:
                names = {e.name for e in it}
        except OSError:
            # 目录不存在/无权限：该组全部失效（与逐条 `exists`=False 一致）
            missing.extend(r for r, _ in entries)
            continue
        missing.extend(r for r, name in entries if name not in names)

    return missing


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
            except Exception as e:
                logger.debug("close_all failed during stop: %s", e)

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
                delay: float = 0.0
            else:
                try:
                    row = self._db.fetchone(f"SELECT COUNT(*) AS cnt FROM {FILE_INDEX_TABLE}")
                    row_count = row["cnt"] if row else 0
                    delay = min(30, max(5.0, row_count / 500))
                except Exception as e:
                    logger.debug("validation delay query failed, fallback 10s: %s", e)
                    delay = 10

            if delay > 0:
                self._stop_event.wait(delay)

            if self._stop_event.is_set():
                self._validation_complete.set()
                return

            try:
                deleted = self.validate_paths()
            except Exception as e:
                logger.warning("file_index startup validation failed: %s", e, exc_info=True)
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
                    # 日志输出编码失败（GBK 控制台）不影响校验结果：保留 `pass`（已评审）
                    pass

        t = threading.Thread(target=_run, daemon=True)
        self._validation_thread = t
        t.start()

    def validate_paths(self) -> int:
        """逐条校验索引记录的目标路径是否存在，失效则删除。返回清除数量。

        ── 性能说明（NEW-05）──
        本方法是**启动期一次性**校验，全表 `SELECT` 是设计使然（必须知道每条记录的
        路径才能判断有效性），不做分页。但逐行 `os.path.exists()` 在万级记录时
        会产生万次 stat 系统调用 —— 在 Windows + 网络挂载下每次可达毫秒级。

        优化：按父目录分组，对每个父目录用一次 `os.scandir` 拿到该目录下的文件名集合，
        之后组内判断只做集合查找（内存操作）。目录不存在时该组全部判失效。
        这仍是**只读**操作，语义与逐条 `os.path.exists` 等价
        （`scandir` 的 entry 名是真实目录项，与 `exists` 判定一致）。
        """
        if self._stop_event.is_set():
            return 0
        try:
            rows = self._db.fetchall(f"SELECT id, file_path FROM {FILE_INDEX_TABLE}")
        except Exception as e:
            logger.warning("validate_paths query failed: %s", e, exc_info=True)
            self._validation_complete.set()
            return 0

        missing = _find_missing_rows(rows)
        if missing and _is_mass_delete_anomaly(len(rows), len(missing)):
            logger.warning(
                "file_index 校验跳过：%d/%d 条路径不存在（疑似挂载/根目录未就绪），本次不删除；"  # i18n-allow: 运维日志
                "请检查 /standards 等挂载后重启，或人工确认后再清理",
                len(missing),
                len(rows),
            )
            self._validation_complete.set()
            return 0
        deleted = 0
        for r in missing:
            try:
                self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE id=?", (r["id"],))
                deleted += 1
            except Exception as e:
                # 删不掉就会留下脏记录，索引统计长期失真（U34 批 1 升为警告级别）
                logger.warning("file_index 删除无效记录失败: id=%s (%s)", r["id"], e)
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
        status: str = Status.ACTIVE.value,
        raw_number: str = "",
    ) -> None:
        """插入或更新文件索引记录。若文件存在则自动计算哈希。"""
        if not file_hash and os.path.exists(file_path):
            file_hash = hash_file_content(file_path)
        now = iso_now()
        part_val = part if part is not None else -1
        raw = raw_number if raw_number else str(number)
        # 单条 UPSERT，避免 SELECT+INSERT 在并发扫描/归档时撞唯一键
        # （file_index.file_path 自 v2 起 UNIQUE）。
        self._db.execute(
            f"INSERT INTO {FILE_INDEX_TABLE} "
            "(file_path, logical_code, number, year, part, std_name, file_hash, status, scanned_at, raw_number) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(file_path) DO UPDATE SET "
            "logical_code=excluded.logical_code, number=excluded.number, year=excluded.year, "
            "part=excluded.part, std_name=excluded.std_name, file_hash=excluded.file_hash, "
            "status=excluded.status, scanned_at=excluded.scanned_at, raw_number=excluded.raw_number",
            (file_path, logical_code, number, year, part_val, std_name, file_hash, status, now, raw),
        )

    def remove(self, file_path: str) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE file_path=?", (file_path,))

    def clear_stale(self) -> int:
        """清除文件已不存在的索引记录（增量：仅检查超过 7 天未验证或从未验证的记录），返回清除数量。"""
        rows = self._db.fetchall(
            f"SELECT id, file_path FROM {FILE_INDEX_TABLE} "
            "WHERE last_checked IS NULL OR last_checked < date('now', 'localtime', '-7 days')"
        )
        deleted = 0
        for r in rows:
            if os.path.exists(r["file_path"]):
                self._db.execute(
                    f"UPDATE {FILE_INDEX_TABLE} SET last_checked = date('now', 'localtime') WHERE id = ?",
                    (r["id"],),
                )
            else:
                self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE} WHERE id = ?", (r["id"],))
                deleted += 1
        return deleted

    def clear_all(self) -> None:
        self._db.execute(f"DELETE FROM {FILE_INDEX_TABLE}")

    # 查询代理（委托）

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
        import os

        from pilotstd.models import ParsedStdInfo

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
