# docker/users.py — 多用户管理（SQLite 持久化）
import hashlib
import os
import secrets

from pilotstd import ADMIN_ROLE
from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database

SALT_BYTES = 32
MIN_PASSWORD_LEN = 8  # 最小密码长度
_db_instance: Database | None = None  # 缓存的 Database 实例


def _hash(password: str, salt: str = "") -> tuple[str, str]:
    """SHA-256 哈希密码。返回 (hash_hex, salt_hex)。"""
    if not salt:
        salt = secrets.token_hex(SALT_BYTES)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000)
    return h.hex(), salt


def _get_db() -> Database:
    """返回缓存的 Database 实例，避免每次调用创建新包装对象。"""
    global _db_instance
    if _db_instance is None:
        _db_instance = Database(get_db_path())
    return _db_instance


def init_users_table() -> None:
    """创建用户表并确保默认 admin 用户存在。"""
    db = _get_db()
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
    # 迁移：从旧表结构补齐可能缺失的列（须在 SELECT 之前，否则新列查询失败）
    # 先检查列是否存在再 ALTER，避免列已存在时产生 ERROR 日志误报
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(users)")}
    if "role" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "must_change_password" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")
    # 管理员用户名（可通过 ADMIN_USERNAME 环境变量自定义）
    admin_user = os.environ.get("ADMIN_USERNAME", "admin")
    # 常见弱密码列表，用于检测已存在管理员是否需要强制改密
    WEAK_PASSWORDS = ["admin", "123456", "password", "admin123", "12345678"]

    # 确保管理员用户存在
    existing = db.fetchone(
        "SELECT id, password_hash, salt, must_change_password FROM users WHERE username = ?",
        (admin_user,),
    )
    if not existing:
        admin_pass = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        must_change = 0 if os.environ.get("ADMIN_PASSWORD") else 1  # 自动生成密码则强制改密
        if not os.environ.get("ADMIN_PASSWORD"):
            print(
                f"\n{'=' * 60}\n"
                f"  ⚠️  ADMIN_PASSWORD 环境变量未设置！\n"
                f"  已自动生成管理员密码: {admin_pass}\n"
                f"  请保存此密码，或设置 ADMIN_PASSWORD 环境变量。\n"
                f"{'=' * 60}\n"
            )
        h, s = _hash(admin_pass)
        db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, salt, role, must_change_password) "
            "VALUES (?, ?, ?, ?, ?)",
            (admin_user, h, s, ADMIN_ROLE, must_change),
        )
    else:
        # 已有管理员用户：检测弱密码，若哈希匹配弱密码则强制改密
        if not existing["must_change_password"]:
            for weak in WEAK_PASSWORDS:
                h_check, _ = _hash(weak, existing["salt"])
                if h_check == existing["password_hash"]:
                    db.execute(
                        "UPDATE users SET must_change_password = 1 WHERE username = ?",
                        (admin_user,),
                    )
                    print(f"\n{'=' * 60}\n  ⚠️  检测到管理员密码为弱密码，已要求首次登录后修改！\n{'=' * 60}\n")
                    break


def verify_user(username: str, password: str) -> bool:
    """验证用户名和密码。"""
    db = _get_db()
    row = db.fetchone("SELECT password_hash, salt FROM users WHERE username = ?", (username,))
    if not row:
        return False
    h, _ = _hash(password, row["salt"])
    return h == row["password_hash"]


def list_users() -> list[dict]:
    db = _get_db()
    rows = db.fetchall("SELECT id, username, role, created_at FROM users ORDER BY id")
    return [dict(r) for r in rows]


def _validate_password(password: str) -> str | None:
    """校验密码强度，返回错误信息或 None（通过）。"""
    if len(password) < MIN_PASSWORD_LEN:
        return f"密码长度不能少于 {MIN_PASSWORD_LEN} 位"
    if not any(c.isalpha() for c in password):
        return "密码必须包含至少一个字母"
    if not any(c.isdigit() for c in password):
        return "密码必须包含至少一个数字"
    return None


def add_user(username: str, password: str, role: str = "user") -> bool:
    err = _validate_password(password)
    if err:
        raise ValueError(err)
    db = _get_db()
    existing = db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
    if existing:
        return False
    h, s = _hash(password)
    db.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
        (username, h, s, role),
    )
    return True


def delete_user(user_id: int) -> bool:
    db = _get_db()
    # 不允许删除最后一个 admin
    admin_count = db.fetchone("SELECT COUNT(*) as cnt FROM users WHERE role = ?", (ADMIN_ROLE,))
    row = db.fetchone("SELECT role FROM users WHERE id = ?", (user_id,))
    if not row:
        return False
    if row["role"] == ADMIN_ROLE and admin_count and admin_count["cnt"] <= 1:
        return False  # 至少保留一个 admin
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return True


def check_must_change_password(username: str) -> bool:
    """检查用户是否需要强制修改密码。"""
    db = _get_db()
    row = db.fetchone("SELECT must_change_password FROM users WHERE username = ?", (username,))
    return bool(row and row["must_change_password"])


def get_user_role(username: str) -> str:
    """获取用户角色。用户不存在返回空字符串。"""
    db = _get_db()
    row = db.fetchone("SELECT role FROM users WHERE username = ?", (username,))
    return row["role"] if row else ""


def clear_must_change_password(username: str) -> None:
    """清除强制改密标记。"""
    db = _get_db()
    db.execute("UPDATE users SET must_change_password = 0 WHERE username = ?", (username,))


def change_password(username: str, old_password: str, new_password: str) -> bool:
    if not verify_user(username, old_password):
        return False
    err = _validate_password(new_password)
    if err:
        raise ValueError(err)
    db = _get_db()
    h, s = _hash(new_password)
    db.execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
        (h, s, username),
    )
    # 清除强制改密标记
    clear_must_change_password(username)
    return True


# ── 登录失败计数持久化 ──


def init_login_attempts_table() -> None:
    """创建登录失败记录表。"""
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            ip TEXT NOT NULL,
            attempt_time REAL NOT NULL
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip)")


def record_login_failure(ip: str) -> None:
    """记录一次登录失败。"""
    import time

    db = _get_db()
    db.execute("INSERT INTO login_attempts (ip, attempt_time) VALUES (?, ?)", (ip, time.time()))


def clear_login_failures(ip: str) -> None:
    """清除指定 IP 的登录失败记录（登录成功后调用）。"""
    db = _get_db()
    db.execute("DELETE FROM login_attempts WHERE ip = ?", (ip,))


def count_recent_failures(ip: str, cutoff: float) -> int:
    """返回指定 IP 在 cutoff 时间之后的失败次数。"""
    db = _get_db()
    row = db.fetchone(
        "SELECT COUNT(*) as cnt FROM login_attempts WHERE ip = ? AND attempt_time > ?",
        (ip, cutoff),
    )
    return row["cnt"] if row else 0
