# pilotstd/core/security.py
# 密码安全模块 — 支持 bcrypt（新）与 PBKDF2/SHA256（旧，兼容过渡）

import hashlib
import secrets

from passlib.context import CryptContext  # type: ignore[import-untyped]

# bcrypt 上下文，标记旧算法为 deprecated
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# PBKDF2 参数（与 docker/users.py 保持一致）
PBKDF2_ITERATIONS = 100_000
PBKDF2_ALGORITHM = "sha256"


def is_bcrypt_hash(hashed: str) -> bool:
    """判断是否为 bcrypt 哈希"""
    return hashed.startswith("$2b$") if hashed else False


def get_password_hash(password: str) -> str:
    """使用 bcrypt 生成密码哈希（新用户注册、修改密码）"""
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证密码 — 桌面端格式
    桌面端旧格式：salt:hexdigest（简单 SHA256，一轮）
    新格式：bcrypt（$2b$...）
    """
    if not hashed_password:
        return False

    if is_bcrypt_hash(hashed_password):
        return _pwd_context.verify(plain_password, hashed_password)

    # 桌面端旧格式：salt:hexdigest
    if ":" in hashed_password:
        salt, digest = hashed_password.split(":", 1)
        if len(digest) == 64:
            computed = hashlib.sha256((salt + plain_password).encode()).hexdigest()
            return computed == digest

    return False


def verify_password_with_salt(
    plain_password: str,
    password_hash: str,
    salt: str,
) -> bool:
    """
    验证密码 — Docker 端格式
    Docker 端旧格式：password_hash 是 PBKDF2-HMAC-SHA256 输出，salt 独立存储
    新格式：password_hash 是 bcrypt，salt 列被忽略
    """
    if not password_hash:
        return False

    if is_bcrypt_hash(password_hash):
        return _pwd_context.verify(plain_password, password_hash)

    # Docker 端旧格式：PBKDF2-HMAC-SHA256
    if salt:
        computed = hashlib.pbkdf2_hmac(
            PBKDF2_ALGORITHM,
            plain_password.encode(),
            salt.encode(),
            PBKDF2_ITERATIONS,
        ).hex()
        return computed == password_hash

    return False


def needs_upgrade(hashed_password: str) -> bool:
    """检查密码哈希是否需要升级到 bcrypt"""
    if not hashed_password:
        return True
    return not is_bcrypt_hash(hashed_password)


def generate_salt() -> str:
    """生成随机盐值（用于兼容旧表字段）"""
    return secrets.token_hex(16)
