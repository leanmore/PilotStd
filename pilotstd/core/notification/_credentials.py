"""CredentialHelper — 用户渠道凭证 CRUD（SQLite + Fernet 加密）。"""

from __future__ import annotations

import json as _json
import logging
from typing import Any, cast

logger = logging.getLogger(__name__)


class CredentialHelper:
    """用户渠道凭证读写。

    复用 config.json 的 Fernet 密钥（.fernet_key）。
    凭证在 DB 中存储为加密的 JSON 字符串。
    """

    def __init__(self, db: Any, config_dir: str) -> None:
        self._db = db
        from pilotstd.core.config.crypto import _get_fernet

        self._fernet = _get_fernet(config_dir)

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
            try:
                plain = self._fernet.decrypt(row["credentials"].encode()).decode()
                result[row["channel"]] = _json.loads(plain)
            except Exception:
                logger.warning("解密渠道 %s 凭证失败，跳过", row.get("channel"))
        return result

    def get_channel(self, user_id: int, channel: str) -> dict[str, str] | None:
        """获取某渠道凭证，返回 {key: value} 或 None。"""
        row = self._db.fetchone(
            'SELECT "credentials" FROM "user_credentials" WHERE "user_id"=? AND "channel"=?',
            (user_id, channel),
        )
        if not row:
            return None
        try:
            plain = self._fernet.decrypt(row["credentials"].encode()).decode()
            return cast("dict[str, str] | None", _json.loads(plain))
        except Exception:
            logger.warning("解密渠道 %s 凭证失败", channel)
            return None

    # ── 写入 ─────────────────────────────────────────────────

    def set_channel(self, user_id: int, channel: str, credentials: dict[str, str]) -> None:
        """写入或更新某渠道凭证。"""
        plain = _json.dumps(credentials, ensure_ascii=False)
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
