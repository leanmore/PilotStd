"""cookie_mgr.py 单元测试 — 7 个业务函数全覆盖。
================================================================
ROI 预检: 150 行中 ~100 行业务逻辑，跳过 DB I/O（已委托 config）。
浏览器/scheduler 流程已 # pragma: no cover。
================================================================
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.wechat_ip.cookie_mgr import (
    _decrypt_cookiecloud_aes,
    _derive_fernet_key,
    decrypt_cookie,
    encrypt_cookie,
    fetch_cookiecloud,
    mask_cookie,
    parse_cookie_header,
)

# ════════════════════════════════════════════════════════════
# 1. _derive_fernet_key — SHA256 + B64 派生
# ════════════════════════════════════════════════════════════

class TestDeriveFernetKey:
    def test_produces_valid_base64_key(self):
        key = _derive_fernet_key("my_secret")
        assert isinstance(key, bytes)
        assert len(key) == 44  # 32 bytes → 44 base64 chars

    def test_deterministic_same_secret(self):
        k1 = _derive_fernet_key("secret")
        k2 = _derive_fernet_key("secret")
        assert k1 == k2

    def test_different_secrets_produce_different_keys(self):
        k1 = _derive_fernet_key("apple")
        k2 = _derive_fernet_key("orange")
        assert k1 != k2

    def test_empty_secret_produces_key(self):
        """空字符串也能产生有效 key（不崩溃）。"""
        key = _derive_fernet_key("")
        assert isinstance(key, bytes)
        assert len(key) == 44


# ════════════════════════════════════════════════════════════
# 2-3. encrypt_cookie + decrypt_cookie — Roundtrip
# ════════════════════════════════════════════════════════════

class TestEncryptDecrypt:
    def test_roundtrip(self):
        """加密→解密循环，数据一致。"""
        original = "session=abc123; token=xyz789"
        encrypted = encrypt_cookie(original, "my_secret")
        assert encrypted != original
        decrypted = decrypt_cookie(encrypted, "my_secret")
        assert decrypted == original

    def test_different_secret_fails_decrypt(self):
        """不同密钥解密应失败。"""
        encrypted = encrypt_cookie("data", "secret_a")
        with pytest.raises(Exception):
            decrypt_cookie(encrypted, "secret_b")

    def test_unicode_cookie(self):
        """含中文的 Cookie 字符串可正常加解密。"""
        original = "name=张三; value=测试"
        encrypted = encrypt_cookie(original, "key")
        assert decrypt_cookie(encrypted, "key") == original


# ════════════════════════════════════════════════════════════
# 4. parse_cookie_header — HeaderString 解析
# ════════════════════════════════════════════════════════════

class TestParseCookieHeader:
    def test_standard_format(self):
        result = parse_cookie_header("a=1; b=2; c=3")
        assert result == {"a": "1", "b": "2", "c": "3"}

    def test_handles_whitespace(self):
        result = parse_cookie_header(" a = 1 ;  b = 2 ")
        assert result == {"a": "1", "b": "2"}

    def test_empty_string_returns_empty(self):
        assert parse_cookie_header("") == {}

    def test_no_equals_skipped(self):
        """无 = 的部分被跳过。"""
        result = parse_cookie_header("valid=1; novalue; also=2")
        assert result == {"valid": "1", "also": "2"}

    def test_empty_value_allowed(self):
        """等号后为空 → value=''"""
        result = parse_cookie_header("key=")
        assert result == {"key": ""}


# ════════════════════════════════════════════════════════════
# 5. _decrypt_cookiecloud_aes — AES-256-GCM
# ════════════════════════════════════════════════════════════

class TestDecryptCookiecloudAes:
    def test_data_too_short_returns_empty(self):
        """原始数据 < 32 字节 → 返回 ''。"""
        # 25 bytes base64 → too short
        import base64
        short = base64.b64encode(b"x" * 25).decode()
        key = base64.b64encode(b"k" * 32).decode()
        assert _decrypt_cookiecloud_aes(short, key) == ""

    def test_exception_returns_empty_and_logs(self, caplog):
        """AES 解密异常 → 返回 '' + warning 日志。"""
        caplog.set_level(logging.WARNING)
        mock_aesgcm = MagicMock()
        mock_aesgcm.decrypt.side_effect = Exception("auth failed")

        import base64
        raw = base64.b64encode(b"x" * 48).decode()  # 48 bytes
        key = base64.b64encode(b"k" * 32).decode()

        with patch(
            "pilotstd.wechat_ip.cookie_mgr.AESGCM", return_value=mock_aesgcm
        ):
            result = _decrypt_cookiecloud_aes(raw, key)

        assert result == ""
        assert any("AES 解密失败" in rec.message for rec in caplog.records)

    def test_successful_decrypt(self):
        """正常 AES-GCM 解密 → 返回明文。"""
        import base64
        import os

        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plaintext = b'{"cookie_data": {}}'
        key_bytes = os.urandom(32)
        aesgcm = AESGCM(key_bytes)
        iv = os.urandom(16)
        ciphertext = aesgcm.encrypt(iv, plaintext, None)
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        raw = base64.b64encode(iv + ct + tag).decode()
        key_b64 = base64.b64encode(key_bytes).decode()

        result = _decrypt_cookiecloud_aes(raw, key_b64)
        assert result == '{"cookie_data": {}}'


# ════════════════════════════════════════════════════════════
# 6. fetch_cookiecloud — HTTP + JSON + 域名匹配
# ════════════════════════════════════════════════════════════

class TestFetchCookiecloud:
    def _make_cookiecloud_response(
        self, domain="work.weixin.qq.com", cookie_name="session", cookie_value="abc",
        user_key="test_user", password="pwd",
    ):
        """构造标准 CookieCloud 加密响应，user_key+password 可定制。"""
        import base64
        import hashlib
        import json
        import os

        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        cookie_data = {
            "cookie_data": {
                "some_domain": [
                    {
                        "domain": domain,
                        "cookies": [
                            {"name": cookie_name, "value": cookie_value}
                        ],
                    }
                ]
            }
        }
        plaintext = json.dumps(cookie_data).encode()
        key_str = user_key
        if password:
            key_str = user_key + "-" + password
        key_md5 = hashlib.md5(key_str.encode()).hexdigest()
        key_bytes = base64.b64decode(key_md5)
        aesgcm = AESGCM(key_bytes)
        iv = os.urandom(16)
        ciphertext = aesgcm.encrypt(iv, plaintext, None)
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        encrypted_b64 = base64.b64encode(iv + ct + tag).decode()
        return {"encrypted": encrypted_b64}

    def test_finds_wechat_domain_cookie(self):
        """域名匹配 work.weixin.qq.com → 返回 Cookie 字符串。"""
        data = self._make_cookiecloud_response(domain="work.weixin.qq.com")
        mock_resp = MagicMock()
        mock_resp.json.return_value = data

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "test_user", "pwd")
            assert result is not None
            assert "session=abc" in result

    def test_no_wechat_domain_falls_back_to_all_cookies(self):
        """无企业微信域 → 回退返回全部 Cookie。"""
        data = self._make_cookiecloud_response(
            domain="other.example.com", user_key="user", password="pwd"
        )
        mock_resp = MagicMock()
        mock_resp.json.return_value = data

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "user", "pwd")
            assert result is not None
            assert "session=abc" in result

    def test_http_error_returns_none(self):
        """HTTP 请求异常 → 返回 None + warning。"""
        with patch("requests.get", side_effect=Exception("timeout")):
            result = fetch_cookiecloud("http://down.local", "u", "")
            assert result is None

    def test_not_encrypted_returns_none(self):
        """返回数据未加密 → 返回 None。"""
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"encrypted": None}

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "u", "")
            assert result is None

    def test_decrypt_failure_returns_none(self):
        """AES 解密失败 → 返回 None。"""
        data = {"encrypted": "invalid_base64!!!"}
        mock_resp = MagicMock()
        mock_resp.json.return_value = data

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "u", "")
            assert result is None

    def test_json_decode_error_returns_none(self):
        """解密后非有效 JSON → 返回 None。"""
        import base64
        import hashlib
        import os

        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plaintext = b"not json"
        key_str = "test-pwd"
        key_md5 = hashlib.md5(key_str.encode()).hexdigest()
        key_bytes = base64.b64decode(key_md5)
        aesgcm = AESGCM(key_bytes)
        iv = os.urandom(16)
        ciphertext = aesgcm.encrypt(iv, plaintext, None)
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        encrypted_b64 = base64.b64encode(iv + ct + tag).decode()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"encrypted": encrypted_b64}

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "test", "pwd")
            assert result is None

    def test_empty_cookie_data_returns_none(self):
        """cookie_data 为空 → 返回 None。"""
        import base64
        import hashlib
        import os

        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        plaintext = b'{"cookie_data": {}}'
        key_str = "test-pwd"
        key_md5 = hashlib.md5(key_str.encode()).hexdigest()
        key_bytes = base64.b64decode(key_md5)
        aesgcm = AESGCM(key_bytes)
        iv = os.urandom(16)
        ciphertext = aesgcm.encrypt(iv, plaintext, None)
        tag = ciphertext[-16:]
        ct = ciphertext[:-16]
        encrypted_b64 = base64.b64encode(iv + ct + tag).decode()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"encrypted": encrypted_b64}

        with patch("requests.get", return_value=mock_resp):
            result = fetch_cookiecloud("http://cc.local", "test", "pwd")
            assert result is None


# ════════════════════════════════════════════════════════════
# 7. mask_cookie — 脱敏
# ════════════════════════════════════════════════════════════

class TestMaskCookie:
    def test_long_cookie_masked(self):
        result = mask_cookie("abcdefghijklmnopqrstuvwxyz1234567890")
        assert "***" in result
        assert result.startswith("abcdefghijkl")
        # cookie[-8:] → 最后8个字符
        assert result.endswith("34567890")

    def test_short_cookie_fully_masked(self):
        """长度 ≤ 20 → 返回 '***'。"""
        result = mask_cookie("short")
        assert result == "***"

    def test_exactly_boundary_length(self):
        """长度 = 21 → 部分脱敏。"""
        result = mask_cookie("a" * 21)
        assert "***" in result
        assert result != "***"
