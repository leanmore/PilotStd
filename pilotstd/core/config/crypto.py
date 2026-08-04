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
    """懒初始化 Fernet——密钥存于 config 目录，首次自动生成。"""
    from cryptography.fernet import Fernet

    key_path = os.path.join(config_dir, ".fernet_key")
    try:
        with open(key_path, "rb") as f:
            key = f.read()
    except FileNotFoundError:
        key = Fernet.generate_key()
        os.makedirs(os.path.dirname(key_path), exist_ok=True)
        with open(key_path, "wb") as f:
            f.write(key)
        if os.name != "nt":
            os.chmod(key_path, 0o600)
    return Fernet(key)


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
