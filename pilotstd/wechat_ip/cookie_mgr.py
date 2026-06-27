# pilotstd/wechat_ip/cookie_mgr.py
"""Cookie 管理器——CookieCloud 拉取 + 手动导入 + 加密存储。

支持三种来源：CookieCloud > 手动导入 > 自动登录（暂未实现）

CookieCloud API 规范（http://<host>:<port>/get/<user_key>）：
  返回加密的 Cookie JSON，使用 AES-256-GCM 解密。
"""

import base64
import hashlib
import json
import logging
from typing import Optional

import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

logger = logging.getLogger(__name__)

COOKIECLOUD_TIMEOUT = 15


def _derive_fernet_key(secret: str) -> bytes:
    """从用户密钥派生 Fernet 加密密钥。"""
    h = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(h[:32])


def encrypt_cookie(cookie_str: str, secret: str) -> str:
    """加密 Cookie 字符串。"""
    f = Fernet(_derive_fernet_key(secret))
    return f.encrypt(cookie_str.encode()).decode()


def decrypt_cookie(encrypted: str, secret: str) -> str:
    """解密 Cookie 字符串。"""
    f = Fernet(_derive_fernet_key(secret))
    return f.decrypt(encrypted.encode()).decode()


def parse_cookie_header(header_string: str) -> dict[str, str]:
    """解析浏览器 HeaderString 格式的 Cookie。

    格式: "key1=value1; key2=value2"
    """
    cookies: dict[str, str] = {}
    for part in header_string.split(";"):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies


def _decrypt_cookiecloud_aes(data_b64: str, key_b64: str) -> str:
    """AES-256-GCM 解密 CookieCloud 数据。

    CookieCloud 使用 AES-GCM 加密，格式为 base64(iv + ciphertext + tag)。
    """
    try:
        raw = base64.b64decode(data_b64)
        key = base64.b64decode(key_b64)
        # CookieCloud 使用 16 字节 IV + ciphertext + 16 字节 tag
        if len(raw) < 32:
            return ""
        iv = raw[:16]
        tag = raw[-16:]
        ciphertext = raw[16:-16]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(iv, ciphertext + tag, None).decode("utf-8")
    except Exception as e:
        logger.warning("CookieCloud AES 解密失败: %s", e)
        return ""


def fetch_cookiecloud(server_url: str, user_key: str, password: str = "") -> Optional[str]:
    """从 CookieCloud 服务端拉取并解密 Cookie。

    CookieCloud 加密方式：AES-256-GCM，密钥为 md5(user_key + '-' + password) 的 hex。
    """
    url = server_url.rstrip("/") + "/get/" + user_key
    try:
        resp = requests.get(url, timeout=COOKIECLOUD_TIMEOUT)
        data = resp.json()
    except Exception as e:
        logger.warning("CookieCloud 请求失败: %s", e)
        return None

    if not data.get("encrypted"):
        logger.warning("CookieCloud 返回数据未加密或格式异常")
        return None

    # 派生解密密钥：md5(user_key + '-' + password)
    key_str = user_key
    if password:
        key_str = user_key + "-" + password
    key_md5 = hashlib.md5(key_str.encode()).hexdigest()

    decrypted = _decrypt_cookiecloud_aes(data["encrypted"], key_md5)
    if not decrypted:
        return None

    try:
        cookie_data = json.loads(decrypted)
    except json.JSONDecodeError:
        logger.warning("CookieCloud 解密后非有效 JSON")
        return None

    # 查找 work.weixin.qq.com 的 Cookie
    for domain_info in cookie_data.get("cookie_data", {}).values():
        if not isinstance(domain_info, list):
            continue
        for item in domain_info:
            if isinstance(item, dict) and "work.weixin.qq.com" in item.get("domain", ""):
                cookies = item.get("cookies", [])
                # 构造 Cookie 字符串
                parts = []
                for c in cookies:
                    if isinstance(c, dict):
                        parts.append(f"{c.get('name', '')}={c.get('value', '')}")
                result = "; ".join(parts)
                logger.info("CookieCloud: 提取到企业微信 Cookie (%d 个键)", len(parts))
                return result

    # 回退：遍历所有域名的 Cookie
    all_parts = []
    for domain_info in cookie_data.get("cookie_data", {}).values():
        if not isinstance(domain_info, list):
            continue
        for item in domain_info:
            if isinstance(item, dict):
                for c in item.get("cookies", []):
                    if isinstance(c, dict):
                        all_parts.append(f"{c.get('name', '')}={c.get('value', '')}")
    if all_parts:
        logger.info("CookieCloud: 未找到企业微信域，回退返回全部 Cookie (%d 个键)", len(all_parts))
        return "; ".join(all_parts)

    logger.warning("CookieCloud 未找到有效 Cookie 数据")
    return None


def mask_cookie(cookie: str) -> str:
    """脱敏显示 Cookie。"""
    if len(cookie) <= 20:
        return "***"
    return cookie[:12] + "***" + cookie[-8:]
