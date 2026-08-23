"""CredentialHelper — 用户渠道凭证 CRUD（SQLite + Fernet 加密）。"""

from __future__ import annotations

import hashlib
import json as _json
import logging
from datetime import datetime
from typing import Any, cast

logger = logging.getLogger(__name__)


class CredentialHelper:
    """用户渠道凭证读写。

    复用 config.json 的 Fernet 密钥（.fernet_key）。
    凭证在 DB 中存储为加密的 JSON 字符串。
    """

    # 掩码特征集合（兼容不同前端风格），命中即视为"未修改"跳过写回
    MASKED_VALUES = {"***", "•••", "******", "MASKED_", "**********"}

    def __init__(self, db: Any, config_dir: str) -> None:
        self._db = db
        from pilotstd.core.config.crypto import _get_fernet

        self._fernet = _get_fernet(config_dir)
        # 保存密钥原文，供指纹校验（哈希摘要前缀）使用
        self._fernet_key: bytes = self._fernet._signing_key + self._fernet._encryption_key

    # ── 读取 ─────────────────────────────────────────────────

    def get_all(self, user_id: int) -> dict[str, dict[str, str]]:
        """获取某用户所有渠道凭证，返回 {channel: {key: value}}。

        user_id=1 且 DB 无数据时，尝试从 config.json 紧急回退并自动补迁。
        """
        rows = self._db.fetchall(
            'SELECT "channel", "credentials" FROM "user_credentials" WHERE "user_id"=?',
            (user_id,),
        )
        if not rows and user_id == 1:
            fallback = self._try_fallback_from_config()
            if fallback:
                for channel, creds in fallback.items():
                    self.set_channel(user_id, channel, creds)
                return fallback
        result: dict[str, dict[str, str]] = {}
        for row in rows:
            ch_name = row["channel"] if isinstance(row, dict) else row[0]
            try:
                cred_raw = row["credentials"] if isinstance(row, dict) else row[1]
                result[ch_name] = self._decrypt_credentials(cred_raw, user_id, ch_name)
            except Exception:
                logger.warning("解密渠道 %s 凭证失败，跳过", ch_name)
        return result

    def get_channel(self, user_id: int, channel: str) -> dict[str, str] | None:
        """读取某渠道凭证，校验 Key 指纹；旧格式自动惰性迁移为新格式。"""
        row = self._db.fetchone(
            'SELECT "credentials" FROM "user_credentials" WHERE "user_id"=? AND "channel"=?',
            (user_id, channel),
        )
        if not row:
            return None
        # 兼容行对象与元组两种取值方式
        cred_raw = row["credentials"] if isinstance(row, dict) else row[0]
        try:
            return self._decrypt_credentials(cred_raw, user_id, channel)
        except Exception:
            logger.warning("解密渠道 %s 凭证失败", channel)
            return None

    def _key_fingerprint(self) -> str:
        """返回当前加密密钥的 8 位哈希指纹（十六进制前缀）。"""
        return hashlib.sha256(self._fernet_key).hexdigest()[:8]

    def _decrypt_credentials(self, cred_raw: str, user_id: int, channel: str) -> dict[str, str]:
        """解密凭据；识别指纹新格式，旧格式首次读取时惰性迁移。"""
        # 新格式：版本号 + 指纹 + 密文三字段结构
        try:
            payload = _json.loads(cred_raw)
        except _json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict) and payload.get("v") == 1 and payload.get("ct"):
            stored_fp = payload.get("fp") or ""
            current_fp = self._key_fingerprint()
            if stored_fp != current_fp:
                raise ValueError(
                    f"Fernet key fingerprint mismatch: stored={stored_fp}, "
                    f"current={current_fp}. Please reconfigure."
                )
            plain = self._fernet.decrypt(payload["ct"].encode()).decode()
            return cast("dict[str, str]", _json.loads(plain))
        # 旧格式：整体为加密密文，解密后惰性迁移补写指纹
        plain = self._fernet.decrypt(cred_raw.encode()).decode()
        result = cast("dict[str, str]", _json.loads(plain))
        self._migrate_to_new_format(user_id, channel, result)
        return result

    def _migrate_to_new_format(self, user_id: int, channel: str, data: dict) -> None:
        """将旧格式凭据迁移为带指纹的新格式（直接写库，禁止调用写入方法防递归）。"""
        encrypted = self._fernet.encrypt(_json.dumps(data, ensure_ascii=False).encode()).decode()
        payload = _json.dumps({"v": 1, "fp": self._key_fingerprint(), "ct": encrypted}, ensure_ascii=False)
        self._db.execute(
            "UPDATE user_credentials SET credentials = ?, updated_at = ? "
            "WHERE user_id = ? AND channel = ?",
            (payload, datetime.now().isoformat(), user_id, channel),
        )

    # ── 写入 ─────────────────────────────────────────────────

    def set_channel(self, user_id: int, channel: str, credentials: dict[str, str]) -> None:
        """合并语义写入渠道凭证，仅覆盖传入的非掩码字段。

        以 DB 现有值为基线，避免增量提交（掩码字段被过滤）整体覆盖导致凭据丢失。
        """
        existing = self.get_channel(user_id, channel) or {}
        merged: dict[str, str] = {k: str(v) for k, v in existing.items()}
        for k, v in credentials.items():
            if k == "enabled":
                merged[k] = "true" if v else "false"
            # 拦截掩码值和空值，防止覆盖真实凭据
            elif v and str(v).strip() not in self.MASKED_VALUES:
                merged[k] = str(v)
        plain = _json.dumps(merged, ensure_ascii=False)
        encrypted = self._fernet.encrypt(plain.encode()).decode()
        self._db.execute(
            'INSERT OR REPLACE INTO "user_credentials"'
            ' ("user_id", "channel", "credentials", "updated_at")'
            " VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (user_id, channel, encrypted),
        )

    def delete_channel(self, user_id: int, channel: str) -> None:
        """删除某渠道凭证。"""
        self._db.execute(
            'DELETE FROM "user_credentials" WHERE "user_id"=? AND "channel"=?',
            (user_id, channel),
        )

    # ── 紧急回退（迁移中断自救） ─────────────────────────────

    def _try_fallback_from_config(self) -> dict[str, dict[str, str]] | None:
        """从 config.json 读取旧渠道配置，仅作为紧急救援。"""
        try:
            from pilotstd.core.config import ConfigManager as _CM

            cfg = _CM()
            channels = (cfg._data.get("notification") or {}).get("channels") or {}
            if not channels:
                return None
            result: dict[str, dict[str, str]] = {}
            for ch_name, ch_cfg in channels.items():
                if isinstance(ch_cfg, dict) and ch_cfg:
                    cleaned = {k: str(v) for k, v in ch_cfg.items() if isinstance(v, str)}
                    if cleaned:
                        result[ch_name] = cleaned
            return result if result else None
        except Exception:
            return None
