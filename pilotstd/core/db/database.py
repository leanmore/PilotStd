# 模块：pilotstd/core/db/database.py
# Database 核心类 — 从 db.py 拆分

import logging
import os
import sqlite3
import threading
import time
from typing import Any, Literal, Optional, Sequence

from ._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseError
from ._migration_checksum import (
    compute_checksum,
    norm_checksum,
    norm_source,
    verify_migration_checksums,
)


class Database:
    """SQLite 数据库管理器，启用 WAL 模式，支持版本迁移，线程本地连接复用。"""

    def __init__(self, db_path: str) -> None:
        """打开/创建 SQLite 数据库：启用 WAL 模式 + 外键 + 自动迁移。"""
        self._db_path = os.path.abspath(db_path)
        self._write_lock = threading.Lock()
        self._local = threading.local()
        self._all_conns: list[Any] = []
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        # 初始化 pragma → 执行迁移，顺序不可颠倒
        self._init_pragma()
        self._run_migrations()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:  # type: ignore[unused-argument]
        self.close_all()
        return False

    def _init_pragma(self) -> None:
        """初始化数据库 pragma：WAL 模式（降级 DELETE）+ 外键强制。"""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.text_factory = str
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA foreign_keys=ON")
        finally:
            conn.close()

    def _acquire_migration_lock(self, timeout: float = 30) -> bool:
        """用 lock 文件实现跨进程排他锁，防止并发迁移。

        使用 os.O_CREAT|O_EXCL 原子创建锁文件，写入当前 PID。
        锁文件 fd 在写入 PID 后立即关闭，不持有句柄。
        检测到 mtime 超过 STALE_LOCK_SECONDS 秒的僵死锁文件会自动清理。
        """
        STALE_LOCK_SECONDS = 30
        lock_path = self._db_path + ".migration_lock"
        start = time.time()
        # 轮询获取文件锁，超时或僵死锁自动清理
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)  # fd 已关闭，仅用文件存在性做锁标记
                self._migration_lock_path = lock_path
                return True
            except FileExistsError:
                try:
                    if time.time() - os.path.getmtime(lock_path) > STALE_LOCK_SECONDS:
                        os.remove(lock_path)
                        continue
                except OSError:
                    continue
                if time.time() - start > timeout:
                    return False
                time.sleep(0.5)

    def _release_migration_lock(self) -> None:
        """释放迁移锁文件。"""
        p = getattr(self, "_migration_lock_path", "")
        if p:
            try:
                os.remove(p)
            except OSError:
                pass
            self._migration_lock_path = ""

    def _ensure_schema_version_table(self) -> None:
        """确保 _schema_version 表包含 version + checksum 列。

        兼容旧库：如果表已存在但无 checksum 列，自动 ALTER TABLE 补齐。
        """
        self.execute(
            "CREATE TABLE IF NOT EXISTS _schema_version "
            "(version INTEGER PRIMARY KEY, checksum TEXT NOT NULL DEFAULT '')"
        )
        # 检查并补齐 checksum 列（兼容旧库）
        cols = {r["name"] for r in self.fetchall("PRAGMA table_info(_schema_version)")}
        if "checksum" not in cols:
            self.execute("ALTER TABLE _schema_version ADD COLUMN checksum TEXT NOT NULL DEFAULT ''")

    # ── 迁移 checksum 校验（委托给 _migration_checksum 模块）──

    @staticmethod
    def _compute_checksum(fn: Any) -> str:
        return compute_checksum(fn)

    @staticmethod
    def _norm_source(source: str) -> str:
        return norm_source(source)

    @staticmethod
    def _norm_checksum(fn: Any) -> str:
        return norm_checksum(fn)

    def _verify_migration_checksums(self) -> None:
        verify_migration_checksums(self)

    @property
    def schema_version(self) -> int:
        try:
            row = self.fetchone("SELECT MAX(version) FROM _schema_version")
            if row and row["MAX(version)"] is not None:
                val = row["MAX(version)"]
                if isinstance(val, bytes):
                    val = val.decode("utf-8")
                return int(val)
            return 0
        except DatabaseError:
            return 0
        except Exception as e:
            logging.getLogger("pilotstd.db").warning("读取 schema 版本失败: %s", e)
            return 0

    def _run_migrations(self) -> None:
        """检查 schema 版本并按序执行未完成的迁移（带备份和 checksum 校验）。"""
        current = self.schema_version
        target = CURRENT_SCHEMA_VERSION
        if current >= target:
            self._verify_migration_checksums()
            return

        logr = logging.getLogger("pilotstd.db")

        if not self._acquire_migration_lock():
            raise DatabaseError("无法获取迁移锁，另一个进程可能正在进行迁移")

        try:
            # 非空库迁移前创建完整备份
            if current > 0:
                backup_path = os.path.join(
                    os.path.dirname(self._db_path),
                    "backups",
                    f"pre_migration_v{current}_to_v{target}.bak",
                )
                self.backup(backup_path)

            self._ensure_schema_version_table()

            if current > 0:
                self._verify_migration_checksums()

            # 按版本号顺序执行所有未完成的迁移
            for v in range(current + 1, target + 1):
                if v in MIGRATIONS:
                    logr.info("开始执行迁移 v%d...", v)
                    t0 = time.time()
                    try:
                        MIGRATIONS[v](self)
                        elapsed = time.time() - t0
                        logr.info("迁移 v%d 完成，耗时 %.2fs", v, elapsed)
                    except Exception as e:
                        elapsed = time.time() - t0
                        logr.exception("迁移 v%d 失败，耗时 %.2fs", v, elapsed)
                        raise DatabaseError(f"数据库迁移失败(v{v})，请从备份恢复") from e
                    checksum = self._norm_checksum(MIGRATIONS[v])
                    self.execute(
                        "INSERT OR REPLACE INTO _schema_version (version, checksum) VALUES (?, ?)",
                        (v, checksum),
                    )
                else:
                    self.execute(
                        "INSERT OR REPLACE INTO _schema_version (version, checksum) VALUES (?, ?)",
                        (v, ""),
                    )
        finally:
            self._release_migration_lock()

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接（线程本地复用，Row 工厂）。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.text_factory = str
            # 设置忙等待超时 + 外键强制 + Row 工厂
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._all_conns.append(conn)
        return self._local.conn  # type: ignore[no-any-return]

    def connect(self) -> sqlite3.Connection:
        """创建独立的 SQLite 连接（不缓存，调用方负责关闭）。"""
        conn = sqlite3.connect(self._db_path)
        conn.text_factory = str
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    # 写操作加写锁，保证线程安全，异常自动回滚
    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
        """执行写 SQL（INSERT/UPDATE/DELETE），自动提交，异常时回滚。"""
        with self._write_lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(sql, params)
                conn.commit()
                return cur
            except (sqlite3.IntegrityError, sqlite3.OperationalError, sqlite3.DatabaseError) as e:
                try:
                    conn.rollback()
                except Exception:
                    pass
                logging.getLogger("pilotstd.db").error("SQL执行失败: %s", sql)
                raise DatabaseError("数据库操作失败") from e

    def executemany(self, sql: str, seq: Sequence[Any]) -> sqlite3.Cursor:
        """批量执行写 SQL，自动提交，异常时回滚。"""
        with self._write_lock:
            conn = self._get_conn()
            try:
                cur = conn.executemany(sql, seq)
                conn.commit()
                return cur
            except Exception as e:
                conn.rollback()
                logging.getLogger("pilotstd.db").error("批量SQL执行失败: %s", sql)
                raise DatabaseError("数据库批量操作失败") from e

    def fetchall(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        """执行查询并返回全部结果（每行转 dict）。"""
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except (sqlite3.IntegrityError, sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logging.getLogger("pilotstd.db").error("SQL查询失败: %s", sql)
            raise DatabaseError("数据库查询失败") from e

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict[str, Any]]:
        """执行查询并返回第一条结果（转 dict），无结果返回 None。"""
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    @property
    def path(self) -> str:
        return self._db_path

    def backup(self, backup_path: str | None = None) -> str:
        """备份数据库到指定路径（默认同目录 .bak）。返回备份路径。"""
        if backup_path is None:
            backup_path = self._db_path + ".bak"
        try:
            # 确保备份目录存在
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            backup_conn = sqlite3.connect(backup_path)
            backup_conn.text_factory = str
            src_conn = self.connect()
            try:
                src_conn.backup(backup_conn)
            finally:
                src_conn.close()
            backup_conn.close()
            logr = logging.getLogger("pilotstd.db")
            logr.info("数据库已备份至: %s", backup_path)
            return backup_path
        except Exception as e:
            logr = logging.getLogger("pilotstd.db")
            logr.warning("数据库备份失败: %s", e)
            return ""

    def close(self) -> None:
        """关闭当前线程的数据库连接。"""
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def close_all(self) -> None:
        """关闭所有已知的数据库连接。"""
        # 遍历关闭所有已知连接
        for conn in self._all_conns:
            try:
                conn.close()
            except Exception:
                pass
        self._all_conns.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None

    # UPSERT 模式：首次插入初始值，后续原子累加
    def update_adapter_stats(
        self,
        adapter_name: str,
        success: bool,
        response_time: float = 0.0,
        cooldown_triggered: bool = False,
        cooldown_reason: str = "",
    ) -> None:
        """更新适配器统计：查询次数、成功率、冷却次数等（静默失败）。"""
        try:
            # UPSERT: INSERT OR REPLACE 配合 ON CONFLICT DO UPDATE 实现原子累加
            self.execute(
                "INSERT INTO adapter_state "
                "(adapter_name, total_queries, successful_queries, "
                " total_response_time, cooldown_count, last_cooldown_reason, "
                " last_cooldown_at, updated_at) "
                "VALUES (?, 1, ?, ?, ?, ?, "
                " CASE WHEN ? THEN datetime('now', 'localtime') ELSE NULL END, "
                " datetime('now', 'localtime')) "
                "ON CONFLICT(adapter_name) DO UPDATE SET "
                "total_queries = total_queries + 1, "
                "successful_queries = successful_queries + ?, "
                "total_response_time = total_response_time + ?, "
                "cooldown_count = cooldown_count + ?, "
                "last_cooldown_reason = CASE WHEN ? THEN ? "
                "   ELSE adapter_state.last_cooldown_reason END, "
                "last_cooldown_at = CASE WHEN ? THEN datetime('now', 'localtime') "
                "   ELSE adapter_state.last_cooldown_at END, "
                "updated_at = datetime('now', 'localtime')",
                (
                    adapter_name,
                    1 if success else 0,
                    response_time,
                    1 if cooldown_triggered else 0,
                    cooldown_reason,
                    cooldown_triggered,
                    1 if success else 0,
                    response_time,
                    1 if cooldown_triggered else 0,
                    cooldown_triggered,
                    cooldown_reason,
                    cooldown_triggered,
                ),
            )
        except Exception:
            pass

    def get_adapter_success_rate(self, adapter_name: str) -> float:
        """查询适配器成功率（0~1），无数据返回 -1.0。"""
        try:
            row = self.fetchone(
                "SELECT total_queries, successful_queries FROM adapter_state WHERE adapter_name = ?",
                (adapter_name,),
            )
            if row and row["total_queries"] > 0:
                return row["successful_queries"] / row["total_queries"]  # type: ignore[no-any-return]
        except Exception:
            pass
        return -1.0

    # 聚合所有适配器统计，计算成功率和平均响应时间
    def get_adapter_stats_all(self) -> list[dict[str, Any]]:
        """查询所有适配器的统计信息（成功率、平均响应时间等）。"""
        try:
            rows = self.fetchall(
                "SELECT adapter_name, total_queries, successful_queries, "
                "total_response_time, cooldown_count, "
                "last_cooldown_reason, last_cooldown_at, updated_at "
                "FROM adapter_state ORDER BY total_queries DESC"
            )
            result = []
            for r in rows:
                total = r["total_queries"]
                success = r["successful_queries"]
                resp_total = r["total_response_time"] or 0
                result.append(
                    {
                        "adapter_name": r["adapter_name"],
                        "total_queries": total,
                        "successful_queries": success,
                        "success_rate": round(success / total, 3) if total > 0 else 0.0,
                        "avg_response_time": round(resp_total / total, 3) if total > 0 else 0.0,
                        "cooldown_count": r["cooldown_count"] or 0,
                        "last_cooldown_reason": r["last_cooldown_reason"] or "",
                        "last_cooldown_at": r["last_cooldown_at"] or "",
                        "last_updated": r["updated_at"] or "",
                    }
                )
            return result
        except Exception:
            return []
