# 容器/脚本—多用户管理（数据库查询持久化）
import hashlib
import logging
import os
import secrets

from pilotstd import ADMIN_ROLE, SUPERUSER_USERNAME
from pilotstd.core.config import get_db_path
from pilotstd.core.db import Database
from pilotstd.core.security import (
    generate_salt,
    get_password_hash,
    needs_upgrade,
    verify_password_with_salt,
)

logger = logging.getLogger(__name__)

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
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
        )
    """)
    # 迁移：从旧表结构补齐可能缺失的列（须在查询之前，否则新列查询失败）
    # 先检查列是否存在再修改，避免列已存在时产生错误日志误报
    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(users)")}
    # ──列名迁移兜底：若有''列但无''，重命名──
    if "user" in cols and "username" not in cols:
        db.execute("ALTER TABLE users RENAME COLUMN user TO username")
        print("[MIGRATION] 已将 users 表列名 user 重命名为 username")
        cols = {r["name"] for r in db.fetchall("PRAGMA table_info(users)")}
    if "role" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'")
    if "must_change_password" not in cols:
        db.execute("ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0")

    if SUPERUSER_USERNAME is not None:
        _ensure_superuser(db, SUPERUSER_USERNAME)


def _ensure_superuser(db: Database, username: str) -> None:
    """确保超级用户存在且角色为 admin（使用 bcrypt 存储密码）。
    - 不存在 → 创建（自动生成或使用 ADMIN_PASSWORD 环境变量）
    - 存在但 role != 'admin' → 校准为 admin
    - 存在且 role == 'admin' → 跳过
    """
    WEAK_PASSWORDS = ["admin", "123456", "password", "admin123", "12345678"]

    existing = db.fetchone(
        "SELECT id, password_hash, salt, role, must_change_password FROM users WHERE username = ?",
        (username,),
    )

    if not existing:
        admin_pass = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(12)
        must_change = 0 if os.environ.get("ADMIN_PASSWORD") else 1
        if not os.environ.get("ADMIN_PASSWORD"):
            print(
                f"\n{'=' * 60}\n"
                f"  ⚠️  ADMIN_PASSWORD 环境变量未设置！\n"
                f"  已自动生成管理员密码: {admin_pass}\n"
                f"  请保存此密码，或设置 ADMIN_PASSWORD 环境变量。\n"
                f"{'=' * 60}\n"
            )
        password_hash = get_password_hash(admin_pass)
        salt = generate_salt()
        db.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, salt, role, must_change_password) "
            "VALUES (?, ?, ?, ?, ?)",
            (username, password_hash, salt, ADMIN_ROLE, must_change),
        )
        print(f"[Init] 超级用户 '{username}' 已创建 (role=admin, bcrypt)")
        return

    # 已存在：校准角色
    if existing["role"] != ADMIN_ROLE:
        db.execute("UPDATE users SET role = ? WHERE username = ?", (ADMIN_ROLE, username))
        print(f"[Init] 已升级现有用户 '{username}' 为 admin")
    else:
        print(f"[Init] 超级用户 '{username}' 角色已正确")

    # 检测弱密码（兼容与旧2格式）
    if not existing["must_change_password"]:
        for weak in WEAK_PASSWORDS:
            if verify_password_with_salt(weak, existing["password_hash"], existing["salt"]):
                db.execute(
                    "UPDATE users SET must_change_password = 1 WHERE username = ?",
                    (username,),
                )
                print(f"\n{'=' * 60}\n  ⚠️  检测到管理员密码为弱密码，已要求首次登录后修改！\n{'=' * 60}\n")
                break


def verify_user(username: str, password: str) -> bool:
    """验证用户名和密码，旧格式密码自动升级为 bcrypt。"""
    db = _get_db()
    row = db.fetchone("SELECT id, password_hash, salt FROM users WHERE username = ?", (username,))
    if not row:
        return False

    password_hash = row["password_hash"]
    salt = row["salt"] or ""

    if not verify_password_with_salt(password, password_hash, salt):
        return False

    # 旧格式（2）自动升级为
    if needs_upgrade(password_hash):
        new_hash = get_password_hash(password)
        db.execute(
            "UPDATE users SET password_hash = ?, salt = '' WHERE id = ?",
            (new_hash, row["id"]),
        )
        logger.info("用户 %s 的密码哈希已自动升级为 bcrypt", username)

    return True


def list_users() -> list[dict]:
    """列出所有用户的 id、用户名、角色和创建时间（按 id 排序）。"""
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


def _determine_role(username: str, superuser_name: str) -> str:
    """根据用户名和超级用户名确定角色。
    - 超级用户 → "admin"
    - 用户名为 "admin"（不区分大小写） → 强制降级为 "user"
    - 其他 → "user"
    """
    if username.lower() == "admin":
        return "user"
    if username == superuser_name:
        return ADMIN_ROLE
    return "user"


def add_user(username: str, password: str, role: str = "user") -> bool:
    """添加用户，使用 bcrypt 存储密码。"""
    # 用户名保护：强制降级为，*禁止创建
    _su = SUPERUSER_USERNAME
    if not _su:
        raise RuntimeError("SUPERUSER_USERNAME is not set — 启动守卫应已拦截，此为防御性检查")
    role = _determine_role(username, _su)
    # 检查是否以超级用户名开头（防止伪造）
    if username != _su and username.lower().startswith(_su.lower()):
        raise ValueError("以超级用户名开头的用户名不允许创建")
    err = _validate_password(password)
    if err:
        raise ValueError(err)
    db = _get_db()
    existing = db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
    if existing:
        return False
    password_hash = get_password_hash(password)
    salt = generate_salt()
    db.execute(
        "INSERT INTO users (username, password_hash, salt, role) VALUES (?, ?, ?, ?)",
        (username, password_hash, salt, role),
    )
    return True


def delete_user(user_id: int) -> bool:
    db = _get_db()
    # 不允许删除超级用户（由环境变量指定）
    row = db.fetchone("SELECT username FROM users WHERE id = ?", (user_id,))
    if not row:
        return False
    if row["username"] == SUPERUSER_USERNAME:
        return False  # 超级用户不可删除
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
    """修改用户密码，使用 bcrypt 存储新密码。"""
    if not verify_user(username, old_password):
        return False
    err = _validate_password(new_password)
    if err:
        raise ValueError(err)
    db = _get_db()
    new_hash = get_password_hash(new_password)
    new_salt = generate_salt()
    db.execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
        (new_hash, new_salt, username),
    )
    # 清除强制改密标记
    clear_must_change_password(username)
    logger.info("用户 %s 的密码已修改", username)
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
    """记录一次登录失败，同时清理超过 7 天的旧记录。"""
    import time

    db = _get_db()
    now = time.time()
    db.execute("INSERT INTO login_attempts (ip, attempt_time) VALUES (?, ?)", (ip, now))
    # 清理超过 7 天的记录，控制表膨胀
    db.execute("DELETE FROM login_attempts WHERE attempt_time < ?", (now - 7 * 86400,))


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


# ── 供其他模块使用的导出函数 ──


def get_user_by_username(username: str):
    """根据用户名获取用户信息（供 user_preference 等模块使用）。"""
    db = _get_db()
    return db.fetchone(
        "SELECT id, username, role FROM users WHERE username = ?",
        (username,),
    )


def get_db_connection():
    """获取数据库连接（供其他模块使用）。"""
    return _get_db()
