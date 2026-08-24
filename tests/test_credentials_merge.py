# tests/test_credentials_merge.py — set_channel 合并语义测试（任务 2）
"""验证 CredentialHelper.set_channel 的 Merge 语义：

- 增量提交仅覆盖传入字段，保留 DB 现有值
- 掩码值（***）与空值不覆盖真实凭据
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _make_helper(fernet_key):
    """构造带 Mock 数据库与真实 Fernet 的助手实例。"""
    from unittest.mock import MagicMock

    from cryptography.fernet import Fernet

    from pilotstd.core.notification._credentials import CredentialHelper

    helper = CredentialHelper.__new__(CredentialHelper)
    helper._db = MagicMock()
    helper._fernet = Fernet(fernet_key)
    helper._fernet_key = fernet_key
    return helper


def _encrypt(fernet, data: dict) -> str:
    """用真实 Fernet 加密字典，模拟 DB 中已有凭据。"""
    import json

    return fernet.encrypt(json.dumps(data, ensure_ascii=False).encode()).decode()


def _capture_inserts(db):
    """捕获 set_channel 的 INSERT 调用参数（忽略惰性迁移的 UPDATE）。"""
    inserts = []

    def _fake_execute(sql, params):
        if sql.startswith("INSERT OR REPLACE"):
            inserts.append((sql, params))

    db.execute.side_effect = _fake_execute
    return inserts


class TestCredentialsMerge:
    """set_channel 合并语义验证。"""

    def test_partial_update(self):
        """提交 {enabled: False}，断言原有 bot_token 未被覆盖。"""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        fernet = Fernet(key)
        helper = _make_helper(key)
        existing = _encrypt(fernet, {"enabled": "true", "bot_token": "123456:REAL", "chat_id": "-100"})
        helper._db.fetchone.return_value = {"credentials": existing}
        inserts = _capture_inserts(helper._db)

        helper.set_channel(1, "telegram", {"enabled": False})

        assert len(inserts) == 1
        stored = inserts[0][1][2]  # credentials 参数
        import json

        decrypted = json.loads(fernet.decrypt(stored.encode()).decode())
        assert decrypted["enabled"] == "false"  # 开关已更新
        assert decrypted["bot_token"] == "123456:REAL"  # 原有 token 保留
        assert decrypted["chat_id"] == "-100"

    def test_mask_rejected(self):
        """P2-2 加固：提交 {bot_token: '***'} 抛 ValueError，DB 无写入（原子拒绝）。"""
        import pytest
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        fernet = Fernet(key)
        helper = _make_helper(key)
        existing = _encrypt(fernet, {"enabled": "true", "bot_token": "123456:REAL", "chat_id": "-100"})
        helper._db.fetchone.return_value = {"credentials": existing}
        inserts = _capture_inserts(helper._db)

        with pytest.raises(ValueError):
            helper.set_channel(1, "telegram", {"enabled": True, "bot_token": "***"})

        assert len(inserts) == 0  # 无任何写入（原子性）

    def test_empty_skip(self):
        """提交 {bot_token: ''}，断言原有 bot_token 未被覆盖。"""
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        fernet = Fernet(key)
        helper = _make_helper(key)
        existing = _encrypt(fernet, {"enabled": "true", "bot_token": "123456:REAL", "chat_id": "-100"})
        helper._db.fetchone.return_value = {"credentials": existing}
        inserts = _capture_inserts(helper._db)

        helper.set_channel(1, "telegram", {"enabled": True, "bot_token": ""})

        assert len(inserts) == 1
        stored = inserts[0][1][2]
        import json

        decrypted = json.loads(fernet.decrypt(stored.encode()).decode())
        assert decrypted["bot_token"] == "123456:REAL"  # 空值被拦截
