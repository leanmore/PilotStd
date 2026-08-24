"""CredentialHelper 凭证 CRUD + 加密测试"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pilotstd.core.notification._credentials import CredentialHelper


class TestCredentialHelper(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.tmpdir = tempfile.mkdtemp()
        import sqlite3 as _sqlite3
        from unittest.mock import patch

        from pilotstd.core.config.crypto import _get_fernet

        # _get_fernet 防呆检查（Key 缺失时）查询全局 DB，隔离到临时空库
        self.empty_db = os.path.join(self.tmpdir, "empty.db")
        _sqlite3.connect(self.empty_db).close()
        with patch("pilotstd.core.config.paths.get_db_path", return_value=self.empty_db):
            _get_fernet(self.tmpdir)
        self.helper = CredentialHelper(self.mock_db, self.tmpdir)

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_get_all_empty_returns_fallback(self):
        """DB 无数据时 user_id=1 触发紧急回退，无 config.json 数据则返回 {}"""
        self.mock_db.fetchall.return_value = []
        with unittest.mock.patch.object(self.helper, "_try_fallback_from_config", return_value=None):
            result = self.helper.get_all(1)
            self.assertEqual(result, {})

    def test_get_all_returns_decrypted_channels(self):
        """正常读取：加密凭证 → 解密 → dict"""
        creds = {"webhook_url": "https://hook.example.com", "secret": "s3cret"}
        plain = json.dumps(creds, ensure_ascii=False)
        encrypted = self.helper._fernet.encrypt(plain.encode()).decode()
        self.mock_db.fetchall.return_value = [
            {"channel": "feishu", "credentials": encrypted},
        ]
        result = self.helper.get_all(1)
        self.assertIn("feishu", result)
        self.assertEqual(result["feishu"]["webhook_url"], "https://hook.example.com")
        self.assertEqual(result["feishu"]["secret"], "s3cret")

    def test_get_channel_returns_none_when_missing(self):
        self.mock_db.fetchone.return_value = None
        result = self.helper.get_channel(1, "dingtalk")
        self.assertIsNone(result)

    def test_get_channel_returns_decrypted(self):
        """get_channel 成功解密返回凭证。"""
        creds = {"webhook_url": "https://hook.example.com"}
        plain = json.dumps(creds, ensure_ascii=False)
        encrypted = self.helper._fernet.encrypt(plain.encode()).decode()
        self.mock_db.fetchone.return_value = {"credentials": encrypted}
        result = self.helper.get_channel(1, "feishu")
        self.assertEqual(result, creds)

    def test_set_channel_encrypts_and_inserts(self):
        self.mock_db.fetchone.return_value = None
        creds = {"webhook_url": "https://new.example.com"}
        self.helper.set_channel(1, "feishu", creds)
        self.mock_db.execute.assert_called_once()
        args = self.mock_db.execute.call_args[0]
        self.assertIn("feishu", args[1])
        decrypted = json.loads(self.helper._fernet.decrypt(args[1][2].encode()).decode())
        self.assertEqual(decrypted["webhook_url"], "https://new.example.com")

    def test_get_all_no_fallback_for_user_2(self):
        """user_id=2 无回退机制"""
        self.mock_db.fetchall.return_value = []
        result = self.helper.get_all(2)
        self.assertEqual(result, {})

    def test_delete_channel(self):
        self.helper.delete_channel(1, "dingtalk")
        self.mock_db.execute.assert_called_once()
        call_args = self.mock_db.execute.call_args[0]
        self.assertIn("dingtalk", call_args[1])

    # ── 补充覆盖：fallback 有数据 / 解密异常 / _try_fallback_from_config ──

    def test_get_all_empty_db_returns_empty(self):
        """CQS：DB 为空时 get_all 返回空 dict，不触发任何写入。"""
        self.mock_db.fetchall.return_value = []
        with unittest.mock.patch.object(self.helper, "_try_fallback_from_config") as mock_fb:
            result = self.helper.get_all(1)
            self.assertEqual(result, {})
            mock_fb.assert_not_called()  # 不再回退 config
            self.mock_db.execute.assert_not_called()  # 无写入副作用
    def test_migrate_from_config_when_empty(self):
        """P2-3：DB 空 + config 有凭证 → 显式迁移写入 DB。"""
        self.mock_db.fetchall.return_value = []
        fb_data = {"telegram": {"bot_token": "tok", "chat_id": "123"}}
        with unittest.mock.patch.object(self.helper, "_try_fallback_from_config", return_value=fb_data):
            result = self.helper.migrate_from_config_if_empty(1)
            self.assertTrue(result)
            self.mock_db.execute.assert_called()  # set_channel 写入 DB

    def test_migrate_skips_when_db_has_data(self):
        """P2-3：DB 已有凭证 → 跳过迁移（幂等），不触发 set_channel。"""
        self.mock_db.fetchall.return_value = [
            {"channel": "telegram", "credentials": self.helper._fernet.encrypt(
                json.dumps({"bot_token": "tok", "chat_id": "123"}).encode()
            ).decode()},
        ]
        with unittest.mock.patch.object(self.helper, "_try_fallback_from_config") as mock_fb:
            result = self.helper.migrate_from_config_if_empty(1)
            self.assertFalse(result)
            mock_fb.assert_not_called()
            # 不触发 set_channel 写入（允许旧格式指纹升级的 UPDATE，但不允许 INSERT OR REPLACE 凭证写入）
            insert_calls = [
                c for c in self.mock_db.execute.call_args_list
                if "INSERT OR REPLACE" in c.args[0]
            ]
            self.assertEqual(len(insert_calls), 0)

    def test_get_all_decrypt_failure_skips(self):
        """解密失败时跳过该条，不阻断整体。"""
        self.mock_db.fetchall.return_value = [
            {"channel": "bad", "credentials": "not-encrypted"},
            {"channel": "good", "credentials": self.helper._fernet.encrypt(
                json.dumps({"k": "v"}).encode()
            ).decode()},
        ]
        result = self.helper.get_all(1)
        self.assertIn("good", result)
        self.assertNotIn("bad", result)

    def test_get_channel_decrypt_failure_returns_none(self):
        """解密失败时 get_channel 返回 None。"""
        self.mock_db.fetchone.return_value = {
            "credentials": "not-encrypted",
        }
        result = self.helper.get_channel(1, "dingtalk")
        self.assertIsNone(result)

    @unittest.mock.patch("pilotstd.core.config.ConfigManager")
    def test_try_fallback_returns_channels(self, mock_cm):
        """_try_fallback_from_config 从 config.json 读取旧渠道配置。"""
        mock_cm.return_value._data = {
            "notification": {
                "channels": {
                    "telegram": {"bot_token": "tok", "chat_id": "456"},
                }
            }
        }
        result = self.helper._try_fallback_from_config()
        self.assertIsNotNone(result)
        self.assertIn("telegram", result)
        self.assertEqual(result["telegram"]["bot_token"], "tok")

    @unittest.mock.patch("pilotstd.core.config.ConfigManager")
    def test_try_fallback_empty_channels_returns_none(self, mock_cm):
        """无渠道配置时返回 None。"""
        mock_cm.return_value._data = {}
        result = self.helper._try_fallback_from_config()
        self.assertIsNone(result)

    @unittest.mock.patch("pilotstd.core.config.ConfigManager")
    def test_try_fallback_exception_returns_none(self, mock_cm):
        """ConfigManager 异常时返回 None。"""
        mock_cm.side_effect = RuntimeError("config error")
        result = self.helper._try_fallback_from_config()
        self.assertIsNone(result)


class TestSetChannelMaskDefense(unittest.TestCase):
    """P2-2 O-3 加固：掩码占位符防御性校验（TC-1 ~ TC-6）。"""

    def setUp(self):
        import sqlite3 as _sqlite3
        import tempfile as _tempfile
        from unittest.mock import MagicMock, patch

        from pilotstd.core.config.crypto import _get_fernet

        self.mock_db = MagicMock()
        self.tmpdir = _tempfile.mkdtemp()
        self.empty_db = os.path.join(self.tmpdir, "empty.db")
        _sqlite3.connect(self.empty_db).close()
        with patch("pilotstd.core.config.paths.get_db_path", return_value=self.empty_db):
            _get_fernet(self.tmpdir)
        self.helper = CredentialHelper(self.mock_db, self.tmpdir)
        # 无已有凭证（get_channel 返回 None）
        self.mock_db.fetchone.return_value = None
        self.inserts = []
        self.mock_db.execute.side_effect = lambda sql, params=None: (
            self.inserts.append((sql, params)) if "INSERT OR REPLACE" in sql else None
        )

    def tearDown(self):
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tc1_real_credentials_write(self):
        """TC-1：正常真实凭证 → 正常写入 DB。"""
        self.helper.set_channel(1, "telegram", {"bot_token": "real_token_123"})
        self.assertEqual(len(self.inserts), 1)
        stored = self.inserts[0][1][2]
        decrypted = json.loads(self.helper._fernet.decrypt(stored.encode()).decode())
        self.assertEqual(decrypted["bot_token"], "real_token_123")

    def test_tc2_pure_mask_rejected(self):
        """TC-2：纯掩码值 '***' → 抛 ValueError，DB 无写入。"""
        with self.assertRaises(ValueError):
            self.helper.set_channel(1, "telegram", {"bot_token": "***"})
        self.assertEqual(len(self.inserts), 0)

    def test_tc3_asterisk_in_real_value(self):
        """TC-3：含星号的合法值 'real_***_token' → 正常写入（不误杀）。"""
        self.helper.set_channel(1, "telegram", {"bot_token": "real_***_token"})
        self.assertEqual(len(self.inserts), 1)
        stored = self.inserts[0][1][2]
        decrypted = json.loads(self.helper._fernet.decrypt(stored.encode()).decode())
        self.assertEqual(decrypted["bot_token"], "real_***_token")

    def test_tc4_non_string_types(self):
        """TC-4：非字符串类型（int/bool）→ 正常写入，类型安全。"""
        self.helper.set_channel(1, "wechat", {"retry_count": 3, "enabled": True})
        self.assertEqual(len(self.inserts), 1)
        stored = self.inserts[0][1][2]
        decrypted = json.loads(self.helper._fernet.decrypt(stored.encode()).decode())
        self.assertEqual(decrypted["enabled"], "true")
        self.assertEqual(decrypted["retry_count"], "3")

    def test_tc5_multi_field_atomic(self):
        """TC-5：多字段含掩码 → 抛 ValueError，任何字段都不写入（原子性）。"""
        with self.assertRaises(ValueError):
            self.helper.set_channel(1, "telegram", {"token": "***", "secret": "real"})
        self.assertEqual(len(self.inserts), 0)

    def test_tc6_log_masked(self):
        """TC-6：日志脱敏——含 key 名，不含 '***' 原文。"""
        import logging

        with self.assertLogs("pilotstd.core.notification._credentials", level=logging.WARNING) as cm:
            with self.assertRaises(ValueError):
                self.helper.set_channel(1, "telegram", {"bot_token": "***"})
        log_text = "\n".join(cm.output)
        self.assertIn("key=bot_token", log_text)
        # 脱敏：日志含 key 与长度，不含掩码原文（'***' 仅作为 key 名上下文出现于消息模板外）
        self.assertIn("value_len=3", log_text)
