# tests/test_core_config.py — core/config/ 子模块补充测试

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


class TestSettingsSchema(unittest.TestCase):
    def test_setting_def_defaults(self):
        from pilotstd.core.config.settings_schema import FIELD_INPUT, SettingDef

        s = SettingDef(key="test.key", tab="test")
        self.assertEqual(s.key, "test.key")
        self.assertEqual(s.tab, "test")
        self.assertEqual(s.field_type, FIELD_INPUT)
        self.assertEqual(s.default, "")

    def test_get_schema_returns_list(self):
        from pilotstd.core.config.settings_schema import get_schema

        schema = get_schema()
        self.assertIsInstance(schema, list)
        self.assertGreater(len(schema), 0)
        # 每个条目应是 dict
        for item in schema:
            self.assertIsInstance(item, dict)
            self.assertIn("key", item)

    def test_get_schema_by_tab_groups(self):
        from pilotstd.core.config.settings_schema import get_schema_by_tab

        grouped = get_schema_by_tab()
        self.assertIsInstance(grouped, dict)
        self.assertGreater(len(grouped), 0)
        # 验证已知 tab 存在
        self.assertIn("storage", grouped)
        self.assertIn("network", grouped)
        self.assertIn("ocr", grouped)

    def test_field_constants(self):
        from pilotstd.core.config.settings_schema import (
            FIELD_INPUT,
            FIELD_SELECT,
            FIELD_TOGGLE,
        )

        self.assertEqual(FIELD_INPUT, "input")
        self.assertEqual(FIELD_TOGGLE, "toggle")
        self.assertEqual(FIELD_SELECT, "select")

    def test_required_flag(self):
        from pilotstd.core.config.settings_schema import SettingDef

        s = SettingDef(key="k", tab="t", required=True)
        self.assertTrue(s.required)
        s2 = SettingDef(key="k2", tab="t")
        self.assertFalse(s2.required)


class TestConfigCrypto(unittest.TestCase):
    def test_is_sensitive_true(self):
        from pilotstd.core.config.crypto import _is_sensitive

        self.assertTrue(_is_sensitive("ocr.api_key"))
        self.assertTrue(_is_sensitive("ocr.secret_key"))
        self.assertTrue(_is_sensitive("provider.secret_id"))
        self.assertTrue(_is_sensitive("aliyun.access_key_id"))
        self.assertTrue(_is_sensitive("aliyun.access_key_secret"))

    def test_is_sensitive_false(self):
        from pilotstd.core.config.crypto import _is_sensitive

        self.assertFalse(_is_sensitive("storage.root_dir"))
        self.assertFalse(_is_sensitive("network.proxy"))
        self.assertFalse(_is_sensitive(""))

    def test_get_fernet_creates_key(self):
        from pilotstd.core.config.crypto import _get_fernet

        tmpdir = tempfile.mkdtemp()
        try:
            fernet = _get_fernet(tmpdir)
            self.assertIsNotNone(fernet)
            # 密钥文件应已创建
            key_path = os.path.join(tmpdir, ".fernet_key")
            self.assertTrue(os.path.exists(key_path))
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_fernet_reuses_key(self):
        from pilotstd.core.config.crypto import _get_fernet

        tmpdir = tempfile.mkdtemp()
        try:
            _get_fernet(tmpdir)
            f2 = _get_fernet(tmpdir)
            # 同一个 Fernet 实例（或至少密钥相同）
            self.assertIsNotNone(f2)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_walk_sensitive_encrypt(self):
        from pilotstd.core.config.crypto import _get_fernet, _walk_sensitive

        tmpdir = tempfile.mkdtemp()
        try:
            fernet = _get_fernet(tmpdir)
            data = {"storage_root_dir": "/data", "ocr": {"api_key": "secret123"}}
            result = _walk_sensitive(data, encrypt=True, fernet=fernet)
            self.assertNotEqual(result["ocr"]["api_key"], "secret123")
            self.assertEqual(result["storage_root_dir"], "/data")
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_walk_sensitive_decrypt(self):
        from pilotstd.core.config.crypto import _get_fernet, _walk_sensitive

        tmpdir = tempfile.mkdtemp()
        try:
            fernet = _get_fernet(tmpdir)
            original = "secret123"
            data = {"ocr.baidu_api_key": original}
            encrypted = _walk_sensitive(data, encrypt=True, fernet=fernet)
            decrypted = _walk_sensitive(encrypted, encrypt=False, fernet=fernet)
            self.assertEqual(decrypted["ocr.baidu_api_key"], original)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_walk_sensitive_nested(self):
        from pilotstd.core.config.crypto import _get_fernet, _walk_sensitive

        tmpdir = tempfile.mkdtemp()
        try:
            fernet = _get_fernet(tmpdir)
            data = {"provider": {"api_key": "nested_secret"}}
            result = _walk_sensitive(data, encrypt=True, fernet=fernet)
            self.assertNotEqual(result["provider"]["api_key"], "nested_secret")
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)


class TestSecurity(unittest.TestCase):
    def test_is_bcrypt_hash_true(self):
        from pilotstd.core.security import is_bcrypt_hash

        self.assertTrue(is_bcrypt_hash("$2b$12$abcdefghijklmnopqrstuvwxyz1234567890"))
        self.assertFalse(is_bcrypt_hash("sha256:salt:hash"))

    def test_is_bcrypt_hash_empty(self):
        from pilotstd.core.security import is_bcrypt_hash

        self.assertFalse(is_bcrypt_hash(""))

    def test_hash_and_verify(self):
        from pilotstd.core.security import get_password_hash, verify_password

        hashed = get_password_hash("test_password")
        self.assertTrue(verify_password("test_password", hashed))
        self.assertFalse(verify_password("wrong", hashed))

    def test_needs_upgrade(self):
        from pilotstd.core.security import needs_upgrade

        self.assertTrue(needs_upgrade(""))
        self.assertTrue(needs_upgrade("old_sha256_hash"))

    def test_generate_salt(self):
        from pilotstd.core.security import generate_salt

        salt = generate_salt()
        self.assertIsInstance(salt, str)
        self.assertEqual(len(salt), 32)  # hex(16 bytes) = 32 chars

    def test_verify_old_desktop_format(self):
        import hashlib

        from pilotstd.core.security import verify_password

        salt = "randomsalt"
        password = "mypassword"
        digest = hashlib.sha256((salt + password).encode()).hexdigest()
        old_hash = f"{salt}:{digest}"
        self.assertTrue(verify_password(password, old_hash))
        self.assertFalse(verify_password("wrong", old_hash))

    def test_verify_pbkdf2_format(self):
        import hashlib

        from pilotstd.core.security import verify_password_with_salt

        salt = "randomsalt32bytes!!"
        password = "mypassword"
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
        self.assertTrue(verify_password_with_salt(password, hashed, salt))
        self.assertFalse(verify_password_with_salt("wrong", hashed, salt))

    def test_verify_password_empty_hash(self):
        from pilotstd.core.security import verify_password

        self.assertFalse(verify_password("pwd", ""))

    def test_verify_with_salt_empty_hash(self):
        from pilotstd.core.security import verify_password_with_salt

        self.assertFalse(verify_password_with_salt("pwd", "", "salt"))


class TestConfigPaths(unittest.TestCase):
    def test_get_db_path_returns_string(self):
        from pilotstd.core.config.paths import get_db_path

        path = get_db_path()
        self.assertIsInstance(path, str)
        self.assertTrue(path.endswith("pilotstd.db"))

    def test_get_network_timeout_default(self):
        from pilotstd.core.config.paths import get_network_timeout

        config = MagicMock()
        config.get.return_value = 30
        self.assertEqual(get_network_timeout(config), 30)

    def test_get_library_root_from_env(self):
        from pilotstd.core.config.paths import get_library_root

        config = MagicMock()
        config.get.return_value = "/tmp/lib"
        os.environ["STANDARD_ROOT"] = "/env/stdroot"
        try:
            # env 优先于 config
            root = get_library_root(config)
            self.assertIn("env", root)
        finally:
            del os.environ["STANDARD_ROOT"]

    def test_get_data_dir_returns_string(self):
        from pilotstd.core.config.paths import get_data_dir

        path = get_data_dir()
        self.assertIsInstance(path, str)
        self.assertGreater(len(path), 0)


if __name__ == "__main__":
    unittest.main()
