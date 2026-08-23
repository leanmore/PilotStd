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
    """crypto 模块测试。

    说明：_get_fernet 的"文件缺失 + DB 有旧密文"防呆检查查询全局 DB，
    测试需通过 patch paths.get_db_path 隔离到临时空库（无 user_credentials 表），
    避免真实开发库中的旧凭证导致误判 RuntimeError。
    """

    def _fresh_db_path(self):
        """返回一个不含 user_credentials 表的临时空 DB 路径。"""
        import sqlite3 as _sqlite3

        db = os.path.join(tempfile.mkdtemp(), "empty.db")
        _sqlite3.connect(db).close()
        return db

    def _patch_empty_db(self):
        from unittest.mock import patch

        return patch("pilotstd.core.config.paths.get_db_path", return_value=self._fresh_db_path())

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
            with self._patch_empty_db():
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
            with self._patch_empty_db():
                _get_fernet(tmpdir)
                f2 = _get_fernet(tmpdir)
            # 同一个 Fernet 实例（或至少密钥相同）
            self.assertIsNotNone(f2)
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_get_fernet_raises_when_key_missing_and_old_data(self):
        """防呆：Key 文件缺失 + DB 已有加密凭证 → 必须报错，禁止静默换 Key。"""
        import sqlite3 as _sqlite3
        from unittest.mock import patch

        from pilotstd.core.config.crypto import _get_fernet

        # 构造含 gAAAAA 前缀凭证的临时 DB
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "old.db")
        conn = _sqlite3.connect(db_path)
        conn.execute(
            'CREATE TABLE IF NOT EXISTS "user_credentials" ('
            '"id" INTEGER PRIMARY KEY AUTOINCREMENT,'
            '"user_id" INTEGER NOT NULL,'
            '"channel" TEXT NOT NULL,'
            '"credentials" TEXT NOT NULL,'
            '"created_at" TEXT DEFAULT CURRENT_TIMESTAMP,'
            '"updated_at" TEXT DEFAULT CURRENT_TIMESTAMP,'
            'UNIQUE("user_id", "channel"))'
        )
        conn.execute(
            "INSERT INTO user_credentials (user_id, channel, credentials) VALUES (1, 'telegram', 'gAAAAAabc123')"
        )
        conn.commit()
        conn.close()
        try:
            key_dir = os.path.join(tmpdir, "config")
            with patch("pilotstd.core.config.paths.get_db_path", return_value=db_path):
                with self.assertRaises(RuntimeError) as ctx:
                    _get_fernet(key_dir)
            self.assertIn("Fernet Key 文件", str(ctx.exception))
            # 不应生成新 Key 文件
            self.assertFalse(os.path.exists(os.path.join(key_dir, ".fernet_key")))
        finally:
            import shutil

            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_walk_sensitive_encrypt(self):
        from pilotstd.core.config.crypto import _get_fernet, _walk_sensitive

        tmpdir = tempfile.mkdtemp()
        try:
            with self._patch_empty_db():
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
            with self._patch_empty_db():
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
            with self._patch_empty_db():
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
        with tempfile.TemporaryDirectory(prefix="env_stdroot_") as env_root:
            os.environ["STANDARD_ROOT"] = env_root
            try:
                # env 优先于 config
                root = get_library_root(config)
                self.assertIn("env_stdroot", root)
            finally:
                del os.environ["STANDARD_ROOT"]

    def test_get_data_dir_returns_string(self):
        from pilotstd.core.config.paths import get_data_dir

        path = get_data_dir()
        self.assertIsInstance(path, str)
        self.assertGreater(len(path), 0)


class TestConfigManagerReload(unittest.TestCase):
    """阶段一：ConfigManager.reload() 从磁盘重新加载配置。"""

    def _make_cfg(self, tmp_dir):
        from unittest.mock import patch

        from pilotstd.core.config.manager import ConfigManager

        # ConfigManager 初始化会 save() → _get_fernet 防呆检查查询全局 DB；
        # 隔离到临时空库，避免真实开发库旧凭证误判
        db = os.path.join(tempfile.mkdtemp(), "empty.db")
        import sqlite3 as _sqlite3

        _sqlite3.connect(db).close()
        with patch("pilotstd.core.config.paths.get_db_path", return_value=db):
            return ConfigManager(filepath=os.path.join(tmp_dir, "config.json"))

    def test_reload_refreshes_from_disk(self):
        import json as _json

        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._make_cfg(tmp)
            cfg.set("notification.enabled", True)
            cfg.save()
            # 模拟外部修改配置文件（绕过 ConfigManager）
            with open(cfg._filepath, "w", encoding="utf-8") as f:
                _json.dump({"notification": {"enabled": False}}, f)
            cfg.reload()
            self.assertFalse(cfg.get("notification.enabled"))

    def test_reload_keeps_factory_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._make_cfg(tmp)
            cfg.reload()
            # 重新加载后默认值仍然存在
            self.assertIsNotNone(cfg.get("storage.root_dir"))
            self.assertIsNotNone(cfg.get("notification.enabled"))


if __name__ == "__main__":
    unittest.main()
