# pilotstd/core/db/database.py
# Database 核心类 — 从 db.py 拆分

import logging
import os
import sqlite3
import threading
from typing import Any, Literal, Optional, Sequence

from ._constants import CURRENT_SCHEMA_VERSION, MIGRATIONS, DatabaseError
from .migrations import *  # noqa: F403 — 触发所有 @migration 装饰器，填充 MIGRATIONS 字典


class Database:
    """SQLite 数据库管理器，启用 WAL 模式，支持版本迁移，线程本地连接复用。"""

    def __init__(self, db_path: str) -> None:
        self._db_path = os.path.abspath(db_path)
        self._write_lock = threading.Lock()
        self._local = threading.local()
        self._all_conns: list[Any] = []
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._init_pragma()
        self._run_migrations()

    def __enter__(self) -> "Database":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> Literal[False]:
        self.close_all()
        return False

    def _init_pragma(self) -> None:
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
        current = self.schema_version
        target = CURRENT_SCHEMA_VERSION
        if current >= target:
            return
        logr = logging.getLogger("pilotstd.db")
        if current > 0:
            backup_path = os.path.join(
                os.path.dirname(self._db_path),
                "backups",
                f"pre_migration_v{current}_to_v{target}.bak",
            )
            self.backup(backup_path)
        if current == 0:
            self.execute("CREATE TABLE IF NOT EXISTS _schema_version (version INTEGER PRIMARY KEY)")
        for v in range(current + 1, target + 1):
            if v in MIGRATIONS:
                try:
                    MIGRATIONS[v](self)
                except Exception as e:
                    logr.exception("迁移 v%d 失败，数据库可能处于不一致状态", v)
                    raise DatabaseError(f"数据库迁移失败(v{v})，请从备份恢复") from e
            self.execute("INSERT OR REPLACE INTO _schema_version (version) VALUES (?)", (v,))

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.text_factory = str
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._all_conns.append(conn)
        return self._local.conn  # type: ignore[no-any-return]

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.text_factory = str
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def execute(self, sql: str, params: Sequence[Any] = ()) -> sqlite3.Cursor:
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
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except (sqlite3.IntegrityError, sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            logging.getLogger("pilotstd.db").error("SQL查询失败: %s", sql)
            raise DatabaseError("数据库查询失败") from e

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict[str, Any]]:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    @property
    def path(self) -> str:
        return self._db_path

    def backup(self, backup_path: str | None = None) -> str:
        if backup_path is None:
            backup_path = self._db_path + ".bak"
        try:
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
        if hasattr(self._local, "conn") and self._local.conn is not None:
            try:
                self._local.conn.close()
            except Exception:
                pass
            self._local.conn = None

    def close_all(self) -> None:
        for conn in self._all_conns:
            try:
                conn.close()
            except Exception:
                pass
        self._all_conns.clear()
        if hasattr(self._local, "conn"):
            self._local.conn = None

    def update_adapter_stats(
        self,
        adapter_name: str,
        success: bool,
        response_time: float = 0.0,
        cooldown_triggered: bool = False,
        cooldown_reason: str = "",
    ) -> None:
        try:
            self.execute(
                "INSERT INTO adapter_stats "
                "(adapter_name, total_queries, successful_queries, "
                " total_response_time, cooldown_count, last_cooldown_reason, "
                " last_cooldown_at, last_updated) "
                "VALUES (?, 1, ?, ?, ?, ?, "
                " CASE WHEN ? THEN datetime('now', 'localtime') ELSE NULL END, "
                " datetime('now', 'localtime')) "
                "ON CONFLICT(adapter_name) DO UPDATE SET "
                "total_queries = total_queries + 1, "
                "successful_queries = successful_queries + ?, "
                "total_response_time = total_response_time + ?, "
                "cooldown_count = cooldown_count + ?, "
                "last_cooldown_reason = CASE WHEN ? THEN ? "
                "   ELSE adapter_stats.last_cooldown_reason END, "
                "last_cooldown_at = CASE WHEN ? THEN datetime('now', 'localtime') "
                "   ELSE adapter_stats.last_cooldown_at END, "
                "last_updated = datetime('now', 'localtime')",
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
        try:
            row = self.fetchone(
                "SELECT total_queries, successful_queries FROM adapter_stats WHERE adapter_name = ?",
                (adapter_name,),
            )
            if row and row["total_queries"] > 0:
                return row["successful_queries"] / row["total_queries"]  # type: ignore[no-any-return]
        except Exception:
            pass
        return -1.0

    def get_adapter_stats_all(self) -> list[dict[str, Any]]:
        try:
            rows = self.fetchall(
                "SELECT adapter_name, total_queries, successful_queries, "
                "total_response_time, cooldown_count, "
                "last_cooldown_reason, last_cooldown_at, last_updated "
                "FROM adapter_stats ORDER BY total_queries DESC"
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
                        "last_updated": r["last_updated"] or "",
                    }
                )
            return result
        except Exception:
            return []
