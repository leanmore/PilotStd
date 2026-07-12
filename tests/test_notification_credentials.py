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
        from pilotstd.core.config.crypto import _get_fernet

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
