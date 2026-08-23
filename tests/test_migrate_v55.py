# tests/test_migrate_v55.py — Key 指纹校验与惰性迁移测试（任务 3）
"""验证 CredentialHelper 的指纹校验与旧格式惰性迁移：

- 旧格式记录首次读取时自动迁移为带指纹的新格式
- 指纹不匹配（Key 变更）时明确报错
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_helper(fernet_key: bytes, db=None):
    """构造带指定密钥的助手实例（Mock 数据库）。"""
    from unittest.mock import MagicMock

    from cryptography.fernet import Fernet

    from pilotstd.core.notification._credentials import CredentialHelper

    helper = CredentialHelper.__new__(CredentialHelper)
    helper._db = db or MagicMock()
    helper._fernet = Fernet(fernet_key)
    helper._fernet_key = fernet_key
    return helper


def _old_format(fernet_key: bytes, data: dict) -> str:
    """构造旧格式凭据：整段加密密文。"""
    import json

    from cryptography.fernet import Fernet

    return Fernet(fernet_key).encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


class TestFingerprintMigration:
    """指纹校验与惰性迁移验证。"""

    def test_lazy_migration(self):
        """旧格式记录首次读取 → 返回正确凭据 → 再查 DB 确认已迁移为新格式。"""
        import json

        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        helper = _make_helper(key)
        old = _old_format(key, {"enabled": "true", "bot_token": "123456:REAL", "chat_id": "-100"})

        # 模拟迁移后 DB 中的新格式值（execute 写入后 fetchone 返回它）
        migrated_payload = {}

        def _fake_execute(sql, params):
            migrated_payload["value"] = params[0]
            return None

        helper._db.execute.side_effect = _fake_execute
        helper._db.fetchone.return_value = {"credentials": old}

        result = helper.get_channel(1, "telegram")

        assert result is not None
        assert result["bot_token"] == "123456:REAL"
        # 惰性迁移已触发：UPDATE 语句写入带指纹的新格式
        assert migrated_payload.get("value") is not None
        payload = json.loads(migrated_payload["value"])
        assert payload["v"] == 1
        assert payload["fp"] == helper._key_fingerprint()
        assert payload["ct"]  # 含加密密文
        # 迁移后的新格式可被再次解密
        helper2 = _make_helper(key)
        helper2._db.fetchone.return_value = {"credentials": migrated_payload["value"]}
        again = helper2.get_channel(1, "telegram")
        assert again is not None
        assert again["bot_token"] == "123456:REAL"

    def test_fingerprint_mismatch_raises(self):
        """Key 变更后读取旧 Key 加密的凭据 → 指纹不匹配明确报错（返回 None 并记录警告）。"""
        import hashlib
        import json

        from cryptography.fernet import Fernet

        key1 = Fernet.generate_key()
        key2 = Fernet.generate_key()  # 模拟 Key 变更后的新 Key
        helper = _make_helper(key2)
        ct = Fernet(key1).encrypt(json.dumps({"enabled": "true", "bot_token": "X"}).encode()).decode()
        fp1 = hashlib.sha256(key1).hexdigest()[:8]
        new_format = json.dumps({"v": 1, "fp": fp1, "ct": ct})
        helper._db.fetchone.return_value = {"credentials": new_format}

        result = helper.get_channel(1, "telegram")

        # 指纹不匹配 → 捕获异常返回 None（get_channel 内部记录警告）
        assert result is None

    def test_new_format_roundtrip(self):
        """新格式凭据正常解密往返（同 Key 场景）。"""
        import json

        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        helper = _make_helper(key)
        ct = helper._fernet.encrypt(
            json.dumps({"enabled": "true", "bot_token": "123456:REAL"}).encode()
        ).decode()
        new_format = json.dumps({"v": 1, "fp": helper._key_fingerprint(), "ct": ct})
        helper._db.fetchone.return_value = {"credentials": new_format}

        result = helper.get_channel(1, "telegram")

        assert result is not None
        assert result["bot_token"] == "123456:REAL"