# pilotstd/core/db.py — SQLite 连接管理：WAL 模式、版本迁移、多线程安全
# 使用线程本地连接复用减少连接创建开销，异常包装为 DatabaseError 避免内部结构泄露

import logging
import os
import sqlite3
import threading
from typing import Any, Callable, Literal, Optional, Sequence

# 当前期望的 schema 版本号（每次新增迁移 +1）
CURRENT_SCHEMA_VERSION = 24

# 迁移注册表：版本号 → 迁移函数（接收 Database 实例）
MIGRATIONS: dict[int, Callable[..., Any]] = {}


def migration(version: int) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """装饰器：注册迁移函数到指定版本号。"""

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        MIGRATIONS[version] = fn
        return fn

    return decorator


class DatabaseError(Exception):
    """数据库操作失败时抛出的通用异常，不暴露内部结构。"""

    pass


class Database:
    """SQLite 数据库管理器，启用 WAL 模式，支持版本迁移，线程本地连接复用。
    支持上下文管理器协议：with Database(path) as db: ..."""

    def __init__(self, db_path: str) -> None:
        self._db_path = os.path.abspath(db_path)
        self._write_lock = threading.Lock()  # 仅写操作加锁，WAL 模式下并发读安全
        # 线程本地连接：每个线程复用同一连接，减少重复打开开销
        self._local = threading.local()
        self._all_conns: list[Any] = []  # 追踪所有线程创建的连接，供 close_all() 遍历关闭
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
            # 9p 文件系统（Docker Desktop Windows bind mount）不支持 WAL 锁，
            # 回退为 DELETE 模式。检测方式：打开后立即设 WAL，异常则换 DELETE。
            try:
                conn.execute("PRAGMA journal_mode=WAL")
            except sqlite3.OperationalError:
                conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA foreign_keys=ON")
        finally:
            conn.close()

    @property
    def schema_version(self) -> int:
        """返回当前数据库的 schema 版本号（0 = 全新/未初始化）。"""
        try:
            row = self.fetchone("SELECT MAX(version) FROM _schema_version")
            if row and row["MAX(version)"] is not None:
                val = row["MAX(version)"]
                if isinstance(val, bytes):
                    val = val.decode("utf-8")
                return int(val)
            return 0
        except DatabaseError:
            # 新数据库无 _schema_version 表，fetchone 会失败，正常返回 0
            return 0
        except Exception as e:
            logging.getLogger("pilotstd.db").warning("读取 schema 版本失败: %s", e)
            return 0

    def _run_migrations(self) -> None:
        """按序执行所有待执行迁移。迁移前自动备份数据库。"""
        current = self.schema_version
        target = CURRENT_SCHEMA_VERSION
        if current >= target:
            return
        # 迁移前自动备份，防止迁移失败导致数据库损坏
        logger = logging.getLogger("pilotstd.db")
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
                    logger.exception("迁移 v%d 失败，数据库可能处于不一致状态", v)
                    raise DatabaseError(f"数据库迁移失败(v{v})，请从备份恢复") from e
            self.execute("INSERT OR REPLACE INTO _schema_version (version) VALUES (?)", (v,))

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接，首次访问时创建。"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.text_factory = str
            conn.execute("PRAGMA busy_timeout=5000")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._all_conns.append(conn)  # 追踪连接，供 close_all() 遍历关闭
        return self._local.conn  # type: ignore[no-any-return]  # thread-local 存储无精确类型

    def connect(self) -> sqlite3.Connection:
        """创建新的独立连接（供 backup 等特殊场景使用）。"""
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
            except (
                sqlite3.IntegrityError,
                sqlite3.OperationalError,
                sqlite3.DatabaseError,
            ) as e:
                try:
                    conn.rollback()
                except Exception:
                    pass  # 自动提交模式下可能无活跃事务
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
        # WAL 模式：纯读操作不加锁，多线程可并发读取
        conn = self._get_conn()
        try:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]
        except (
            sqlite3.IntegrityError,
            sqlite3.OperationalError,
            sqlite3.DatabaseError,
        ) as e:
            logging.getLogger("pilotstd.db").error("SQL查询失败: %s", sql)
            raise DatabaseError("数据库查询失败") from e

    def fetchone(self, sql: str, params: Sequence[Any] = ()) -> Optional[dict[str, Any]]:
        rows = self.fetchall(sql, params)
        return rows[0] if rows else None

    @property
    def path(self) -> str:
        return self._db_path

    def backup(self, backup_path: str | None = None) -> str:
        """使用 SQLite backup API 创建一致性快照，返回备份路径。"""
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
            logger = logging.getLogger("pilotstd.db")
            logger.info("数据库已备份至: %s", backup_path)
            return backup_path
        except Exception as e:
            logger = logging.getLogger("pilotstd.db")
            logger.warning("数据库备份失败: %s", e)
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
        """关闭所有线程创建的数据库连接（应用 shutdown 时调用）。"""
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
        """更新适配器查询统计（总查询数+成功数+响应时间+冷却次数）。"""
        try:
            self.execute(
                "INSERT INTO adapter_stats "
                "(adapter_name, total_queries, successful_queries, "
                " total_response_time, cooldown_count, last_cooldown_reason, "
                " last_cooldown_at, last_updated) "
                "VALUES (?, 1, ?, ?, ?, ?, "
                " CASE WHEN ? THEN datetime('now') ELSE NULL END, "
                " datetime('now')) "
                "ON CONFLICT(adapter_name) DO UPDATE SET "
                "total_queries = total_queries + 1, "
                "successful_queries = successful_queries + ?, "
                "total_response_time = total_response_time + ?, "
                "cooldown_count = cooldown_count + ?, "
                "last_cooldown_reason = CASE WHEN ? THEN ? "
                "   ELSE adapter_stats.last_cooldown_reason END, "
                "last_cooldown_at = CASE WHEN ? THEN datetime('now') "
                "   ELSE adapter_stats.last_cooldown_at END, "
                "last_updated = datetime('now')",
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
        """从数据库读取适配器历史成功率（0-1），无数据返回 -1。"""
        try:
            row = self.fetchone(
                "SELECT total_queries, successful_queries FROM adapter_stats WHERE adapter_name = ?",
                (adapter_name,),
            )
            if row and row["total_queries"] > 0:
                return row["successful_queries"] / row["total_queries"]  # type: ignore[no-any-return]  # sqlite3.Row 返回 Any
        except Exception:
            pass
        return -1.0

    def get_adapter_stats_all(self) -> list[dict[str, Any]]:
        """返回所有适配器的统计汇总（供报告使用）。"""
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


# ── 迁移定义 ──────────────────────────────────────────────


@migration(2)
def _migrate_v2_add_file_index(db: Database) -> None:
    """v2：新增 file_index 表（本地文件索引持久化）。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS file_index (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            logical_code TEXT NOT NULL DEFAULT '',
            number INTEGER NOT NULL DEFAULT 0,
            year INTEGER NOT NULL DEFAULT 0,
            part INTEGER NOT NULL DEFAULT -1,
            std_name TEXT NOT NULL DEFAULT '',
            file_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '现行',
            scanned_at TEXT NOT NULL DEFAULT ''
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_file_index_hash ON file_index(file_hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_file_index_code ON file_index(logical_code, number)")


@migration(3)
def _migrate_v3_queue_and_pending(db: Database) -> None:
    """v3：下载等待队列表 + 待确认清单表 + file_index 补充 status 列（兼容 v2 旧库）。"""
    # 下载等待队列表
    db.execute("""
        CREATE TABLE IF NOT EXISTS download_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            standard_name TEXT NOT NULL DEFAULT '',
            publish_date TEXT NOT NULL DEFAULT '',
            expected_available TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            retry_count INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'waiting'
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_download_queue_status ON download_queue(status)")

    # 待确认清单表
    db.execute("""
        CREATE TABLE IF NOT EXISTS pending_lookup (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            std_name TEXT NOT NULL DEFAULT '',
            found_name TEXT NOT NULL DEFAULT '',
            found_number TEXT NOT NULL DEFAULT '',
            match_status TEXT NOT NULL DEFAULT '',
            effect_status TEXT NOT NULL DEFAULT '',
            score INTEGER NOT NULL DEFAULT 0,
            source_site TEXT NOT NULL DEFAULT '',
            file_path TEXT NOT NULL DEFAULT '',
            source_name TEXT NOT NULL DEFAULT '',
            final_name TEXT NOT NULL DEFAULT '',
            reason TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT '',
            resolved_at TEXT NOT NULL DEFAULT ''
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_pending_lookup_status ON pending_lookup(status)")

    # 兼容 v2 旧库：补充 status 列（先检查是否存在，避免误报 ERROR）
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(file_index)")}
    if "status" not in cols:
        db.execute("ALTER TABLE file_index ADD COLUMN status TEXT NOT NULL DEFAULT '现行'")


@migration(4)
def _migrate_v4_add_fetch_checkpoint(db: Database) -> None:
    """v4：新增公告抓取日志表。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS fetch_checkpoint (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_site TEXT NOT NULL UNIQUE,
            last_fetched_at TEXT NOT NULL DEFAULT '',
            last_notice_date TEXT NOT NULL DEFAULT ''
        )
    """)


@migration(5)
def _migrate_v5_announcement_match(db: Database) -> None:
    """v5：独立的公告缓存表，与网络查询缓存分离。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS announcement_match (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL,
            source_site TEXT NOT NULL DEFAULT 'announcement',
            result_json TEXT NOT NULL,
            cached_at TEXT NOT NULL,
            expires_at TEXT
        )
    """)
    db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_announcement_match_lookup "
        "ON announcement_match(standard_number, source_site)"
    )


@migration(6)
def _migrate_v6_add_rotator_state(db: Database) -> None:
    """v6: 站点冷却状态持久化表，支持跨进程共享冷却信息。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS rotator_state (
            site_name TEXT PRIMARY KEY,
            request_count INTEGER NOT NULL DEFAULT 0,
            daily_count INTEGER NOT NULL DEFAULT 0,
            daily_date TEXT NOT NULL DEFAULT '',
            cooldown_until REAL NOT NULL DEFAULT 0.0,
            consecutive_errors INTEGER NOT NULL DEFAULT 0,
            active_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)


@migration(7)
def _migrate_v7_add_last_checked(db: Database) -> None:
    """v7: file_index 增加 last_checked 列 + 索引，支持增量清理。"""
    try:
        db.execute("ALTER TABLE file_index ADD COLUMN last_checked TEXT")
    except Exception:
        logging.getLogger("pilotstd.db").debug("v7 迁移：last_checked 列可能已存在", exc_info=True)
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_file_index_last_checked ON file_index(last_checked)"
    )  # 加速 WHERE last_checked < ? 增量查询


@migration(8)
def _migrate_v8_drop_expires_at(db: Database) -> None:
    """v8: standard_info_cache 删除 expires_at 列（缓存失效已改为事件驱动）。"""
    # 表可能尚未创建（CacheRepository 惰性初始化），先检查表是否存在
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        logging.getLogger("pilotstd.db").debug("v8 迁移：standard_info_cache 表不存在，跳过")
        return
    if "expires_at" in cols:
        db.execute("ALTER TABLE standard_info_cache DROP COLUMN expires_at")


@migration(9)
def _migrate_v9_add_requery_count(db: Database) -> None:
    """v9: pending_lookup 表加 requery_count 列（待确认三次重试限制）。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(pending_lookup)")}
    if not cols:
        return  # 表尚未创建（惰性初始化），跳过
    if "requery_count" not in cols:
        db.execute("ALTER TABLE pending_lookup ADD COLUMN requery_count INTEGER DEFAULT 0")


@migration(10)
def _migrate_v10_add_source_and_status_history(db: Database) -> None:
    """v10: standard_info_cache 加 source 列（数据来源）和 status_history 列（状态变更记录）。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(standard_info_cache)")}
    if not cols:
        return  # 表尚未创建（惰性初始化），跳过
    if "source" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN source TEXT NOT NULL DEFAULT 'network'")
    if "status_history" not in cols:
        db.execute("ALTER TABLE standard_info_cache ADD COLUMN status_history TEXT NOT NULL DEFAULT ''")


@migration(11)
def _migrate_v11_add_daily_limits(db: Database) -> None:
    """v11: rotator_state 加 daily_count 和 daily_date 列（站点日请求上限）。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(rotator_state)")}
    if not cols:
        return  # 表尚未创建（惰性初始化），跳过
    if "daily_count" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_count INTEGER NOT NULL DEFAULT 0")
    if "daily_date" not in cols:
        db.execute("ALTER TABLE rotator_state ADD COLUMN daily_date TEXT NOT NULL DEFAULT ''")


@migration(12)
def _migrate_v12_adapter_stats(db: Database) -> None:
    """v12: 适配器查询统计表（成功率持久化）。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS adapter_stats (
            adapter_name TEXT PRIMARY KEY,
            total_queries INTEGER DEFAULT 0,
            successful_queries INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now'))
        )
    """)


@migration(13)
def _migrate_v13_adapter_stats_extend(db: Database) -> None:
    """v13: adapter_stats 扩展响应时间+冷却统计字段。"""
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(adapter_stats)")}
    if not cols:
        return
    if "avg_response_time" not in cols:
        db.execute("ALTER TABLE adapter_stats ADD COLUMN avg_response_time REAL DEFAULT 0")
    if "total_response_time" not in cols:
        db.execute("ALTER TABLE adapter_stats ADD COLUMN total_response_time REAL DEFAULT 0")
    if "cooldown_count" not in cols:
        db.execute("ALTER TABLE adapter_stats ADD COLUMN cooldown_count INTEGER DEFAULT 0")
    if "last_cooldown_reason" not in cols:
        db.execute("ALTER TABLE adapter_stats ADD COLUMN last_cooldown_reason TEXT")
    if "last_cooldown_at" not in cols:
        db.execute("ALTER TABLE adapter_stats ADD COLUMN last_cooldown_at TEXT")


@migration(14)
def _migrate_v14_api_keys(db: Database) -> None:
    """v14: API Key 管理表。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_id TEXT NOT NULL UNIQUE,
            key_hash TEXT NOT NULL UNIQUE,
            description TEXT NOT NULL DEFAULT '',
            scopes TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            expires_at TEXT,
            last_used_at TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_by TEXT NOT NULL DEFAULT ''
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_is_active ON api_keys(is_active)")


@migration(15)
def _migrate_v15_announcement_record(db: Database) -> None:
    """v15: 公告抓取全量日志表，记录所有抓取到的公告明细（含未匹配的），用于去重和审计追溯。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS announcement_record (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_site TEXT NOT NULL,
            pid TEXT NOT NULL,
            announce_no TEXT,
            standard_number TEXT NOT NULL,
            std_name TEXT,
            publish_date TEXT,
            fetched_at TEXT NOT NULL,
            matched INTEGER DEFAULT 0,
            UNIQUE(source_site, pid, standard_number)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_pid ON announcement_record(source_site, pid)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_standard ON announcement_record(standard_number)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_fetch_checkpoint_matched ON announcement_record(matched)")


@migration(16)
def _migrate_v16_validity_status(db: Database) -> None:
    """v16: 标准时效性检查表——跟踪标准现行/废止状态变更。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS standard_validity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            standard_number TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT '未知',
            last_checked_at TEXT,
            next_check_at TEXT,
            last_status TEXT,
            last_status_updated_at TEXT,
            check_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_next_check ON standard_validity(next_check_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_validity_standard ON standard_validity(standard_number)")


@migration(17)
def _migrate_v17_notification_log(db: Database) -> None:
    """v17: 通知发送日志表——记录所有渠道的通知发送记录。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            channel TEXT NOT NULL,
            title TEXT,
            body TEXT,
            standard_number TEXT,
            status TEXT NOT NULL DEFAULT 'success',
            error_msg TEXT,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_sent_at ON notification_log(sent_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notif_event_type ON notification_log(event_type)")


@migration(19)
def _migrate_v19_users(db: Database) -> None:
    """v19: 用户表——确保超级用户认证表始终存在（与 docker/users.py 保持同步）。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            must_change_password INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(users)")}
    if "role" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "must_change_password" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")


@migration(20)
def _migrate_v20_register_runtime_tables(db: Database) -> None:
    """v20: 登记运行时自建表（daily_quota / task_queue / scheduler_lock）。

    这三张表由各自的业务模块在运行时自建（不在此处定义 CREATE），
    v20 仅确保表存在性检查通过，并在 _schema_version 中留下审计痕迹。
    """
    for tbl in ("daily_quota", "task_queue", "scheduler_lock"):
        exists = db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
        if not exists:
            # 表不存在时由运行时模块自建，此处仅记录日志
            pass


@migration(21)
def _migrate_v21_user_layouts(db: Database) -> None:
    """v21: 用户布局持久化表——跨设备同步仪表板布局。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_layouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            layout_key TEXT NOT NULL DEFAULT 'dashboard',
            layout_data TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, layout_key)
        )
    """)


@migration(22)
def _migrate_v22_user_preferences(db: Database) -> None:
    """v22: 用户配置表——统一存储所有用户可修改的配置项。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            preference_key TEXT NOT NULL,
            preference_value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, preference_key)
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_key ON user_preferences(user_id, preference_key)")


@migration(23)
def _migrate_v23_cache_system(db: Database) -> None:
    """v23: 统一缓存系统——数据源版本追踪 + 缓存表扩展 + 缓存配置。"""
    # 数据源版本追踪表
    db.execute("""
        CREATE TABLE IF NOT EXISTS data_source_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_name TEXT NOT NULL UNIQUE,
            version TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for src in ("file_index", "announcement", "validity"):
        db.execute(
            "INSERT OR IGNORE INTO data_source_versions (source_name, version) VALUES (?, 'initial')",
            (src,),
        )

    # 缓存配置表
    db.execute("""
        CREATE TABLE IF NOT EXISTS cache_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key TEXT NOT NULL UNIQUE,
            config_value TEXT NOT NULL,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    for ck, cv in (("max_size_mb", "50"), ("auto_cleanup", "true"), ("cleanup_ratio", "0.1")):
        db.execute(
            "INSERT OR IGNORE INTO cache_config (config_key, config_value) VALUES (?, ?)",
            (ck, cv),
        )

    # 扩展三张缓存表——先确保表存在（CI 空库场景），再添加新列
    for table in ("standard_info_cache", "standard_validity", "announcement_record"):
        # 检查表是否存在（空库中运行时自建表尚未创建）
        existing = db.fetchone(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        if not existing:
            # 表不存在时创建最小结构（与运行时自建逻辑一致）
            if table == "standard_info_cache":
                db.execute("""
                    CREATE TABLE IF NOT EXISTS standard_info_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        standard_number TEXT NOT NULL,
                        source_site TEXT NOT NULL,
                        result_json TEXT NOT NULL,
                        cached_at TEXT NOT NULL,
                        source TEXT NOT NULL DEFAULT 'network',
                        status_history TEXT NOT NULL DEFAULT ''
                    )
                """)
            elif table == "standard_validity":
                db.execute("""
                    CREATE TABLE IF NOT EXISTS standard_validity (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        standard_number TEXT NOT NULL UNIQUE,
                        status TEXT NOT NULL DEFAULT '未知',
                        last_checked_at TEXT,
                        next_check_at TEXT,
                        last_status TEXT,
                        last_status_updated_at TEXT,
                        check_count INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            elif table == "announcement_record":
                db.execute("""
                    CREATE TABLE IF NOT EXISTS announcement_record (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_site TEXT NOT NULL,
                        pid TEXT NOT NULL,
                        announce_no TEXT,
                        standard_number TEXT NOT NULL,
                        std_name TEXT,
                        publish_date TEXT,
                        fetched_at TEXT NOT NULL,
                        matched INTEGER DEFAULT 0,
                        UNIQUE(source_site, pid, standard_number)
                    )
                """)

        cols = {r["name"] for r in db.fetchall(f"PRAGMA table_info({table})")}
        if "source_version" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN source_version TEXT DEFAULT ''")
        if "data_state" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN data_state TEXT DEFAULT 'valid'")
        if "last_accessed_at" not in cols:
            db.execute(f"ALTER TABLE {table} ADD COLUMN last_accessed_at TEXT DEFAULT NULL")


@migration(24)
def _migrate_v24_task_queue_enhance(db: Database) -> None:
    """v24: 任务队列扩展——重试/超时/优先级/队列名。"""
    # 先确保表存在（CI 空库场景）
    existing = db.fetchone(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='task_queue'",
    )
    if not existing:
        db.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL UNIQUE,
                task_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                total_items INTEGER DEFAULT 0,
                completed_items INTEGER DEFAULT 0,
                failed_items INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                result_json TEXT DEFAULT '',
                error_log TEXT DEFAULT ''
            )
        """)
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(task_queue)")}
    additions = [
        ("retry_count", "INTEGER DEFAULT 0"),
        ("max_retries", "INTEGER DEFAULT 3"),
        ("timeout_seconds", "INTEGER DEFAULT 300"),
        ("started_at", "TEXT"),
        ("finished_at", "TEXT"),
        ("priority", "INTEGER DEFAULT 0"),
        ("queue_name", "TEXT DEFAULT 'default'"),
    ]
    for col_name, col_def in additions:
        if col_name not in cols:
            db.execute(f"ALTER TABLE task_queue ADD COLUMN {col_name} {col_def}")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority ON task_queue(status, priority, created_at)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_task_queue_queue_name ON task_queue(queue_name)")


@migration(18)
def _migrate_v18_fetch_task_adapter_health(db: Database) -> None:
    """v18: 异步抓取任务表 + 适配器熔断健康表。"""
    db.execute("""
        CREATE TABLE IF NOT EXISTS fetch_task (
            id TEXT PRIMARY KEY,
            task_type TEXT DEFAULT 'announcement',
            status TEXT DEFAULT 'pending',
            progress INTEGER DEFAULT 0,
            result_data TEXT,
            error_msg TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS adapter_health (
            adapter_name TEXT PRIMARY KEY,
            freeze_count INTEGER DEFAULT 0,
            first_freeze_time TIMESTAMP,
            frozen_until TIMESTAMP,
            fail_streak INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
