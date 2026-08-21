# 模块：项目/核心/配置/脚本
# 敏感字段加解密—从配置脚本拆分

import os
from typing import Any

_SENSITIVE_SUFFIXES = (
    ".api_key",
    ".secret_key",
    ".secret_id",
    ".access_key_id",
    ".access_key_secret",
)


def _get_fernet(config_dir: str) -> Any:
    """获取 Fernet 加密实例（挂载 config 目录场景专用）。

    设计原则：
    - 仅信任 {config_dir}/.fernet_key 文件，不依赖环境变量或 DB 存储
    - 文件存在 → 直接使用
    - 文件缺失 + DB 有旧密文 → 显式报错（禁止静默生成新 Key）
    - 文件缺失 + DB 无旧密文 → 生成新 Key 并写入文件（首次初始化）
    """
    import logging
    import sqlite3

    from cryptography.fernet import Fernet

    from pilotstd.core.config.paths import get_db_path

    logger = logging.getLogger(__name__)

    key_path = os.path.join(config_dir, ".fernet_key")

    # ===== 1. 优先读取密钥文件 =====
    if os.path.exists(key_path):
        try:
            with open(key_path, "rb") as f:
                key = f.read().strip()
            if key:
                logger.info("已加载 Fernet Key: %s", key_path)
                return Fernet(key)
        except Exception as e:
            logger.error("读取 Key 文件失败: %s", e)
            raise RuntimeError(f"Key 文件 {key_path} 读取失败，请检查权限或内容完整性") from e

    # ===== 2. 文件不存在，执行安全保护检查 =====
    logger.warning("Key 文件 %s 不存在，正在检查 DB 中是否已有加密数据...", key_path)

    has_old_data = False
    conn = None
    try:
        db_path = get_db_path()
        conn = sqlite3.connect(db_path)
        # 检查是否存在 Fernet 加密特征前缀 gAAAAA
        cur = conn.execute("SELECT 1 FROM user_credentials WHERE credentials LIKE 'gAAAAA%' LIMIT 1")
        has_old_data = cur.fetchone() is not None
    except sqlite3.Error as e:
        # DB 尚未初始化或表不存在，视为全新安装
        logger.warning("无法查询 DB（可能为全新安装）: %s", e)
        has_old_data = False
    finally:
        if conn is not None:
            conn.close()

    # ===== 3. 有旧密文但无密钥 → 严禁自动生成，必须报错 =====
    if has_old_data:
        raise RuntimeError(
            f"❌ Fernet Key 文件 ({key_path}) 缺失，但数据库中已存在加密凭证！\n"
            "自动生成新 Key 将导致所有旧凭证永久损坏。\n"
            "解决方案：\n"
            "  1. 从备份恢复原始 .fernet_key 文件到挂载目录；\n"
            "  2. 或清空 user_credentials 表后重启容器重新配置。"
        )

    # ===== 4. 无旧密文 → 全新安装，生成新密钥并持久化 =====
    logger.info("未检测到旧加密数据，判定为全新安装，生成新 Fernet Key...")
    new_key = Fernet.generate_key()

    # 确保 config 目录存在（兼容挂载目录首次为空的情况）
    os.makedirs(config_dir, exist_ok=True)

    with open(key_path, "wb") as f:
        f.write(new_key)

    # 设置文件权限为仅所有者可读写
    if os.name != "nt":
        os.chmod(key_path, 0o600)

    logger.info("新 Key 已保存至 %s (权限 0600)", key_path)
    logger.info("【重要】请立即备份此 Key: %s", new_key.decode())

    return Fernet(new_key)


def _walk_sensitive(data: dict[str, Any], *, encrypt: bool, fernet: Any, prefix: str = "") -> dict[str, Any]:
    """递归遍历嵌套字典，对所有敏感字段加密/解密。内存中始终明文。"""
    result: dict[str, Any] = {}
    for k, v in data.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result[k] = _walk_sensitive(v, encrypt=encrypt, fernet=fernet, prefix=full_key)
        elif isinstance(v, str) and v and _is_sensitive(full_key):
            if encrypt:
                result[k] = fernet.encrypt(v.encode()).decode()
            else:
                if v.startswith("gAAAAA"):
                    try:
                        result[k] = fernet.decrypt(v.encode()).decode()
                    except Exception:
                        result[k] = ""
                else:
                    result[k] = v
        else:
            result[k] = v
    return result


def _is_sensitive(full_key: str) -> bool:
    return any(full_key.endswith(s) for s in _SENSITIVE_SUFFIXES)
