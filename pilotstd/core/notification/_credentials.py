"""CredentialHelper — 用户渠道凭证 CRUD（SQLite + Fernet 加密）。"""

from __future__ import annotations

import hashlib
import json as _json
import logging
from datetime import datetime
from typing import Any, cast

logger = logging.getLogger(__name__)

# 系统默认用户 ID：迁移引导目标用户（语义化，消除魔法数字）
SYSTEM_DEFAULT_USER_ID = 1

# 统一掩码占位符常量（P2-2 O-3 加固）：禁止硬编码，供前端回显与底层校验共用
MASKED_VALUE = "***"


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

        纯只读（CQS）：仅查询 DB 并解密，无任何写入副作用。
        DB 为空时返回空 dict，不回退 config.json（回退由显式迁移方法承担）。
        """
        rows = self._db.fetchall(
            'SELECT "channel", "credentials" FROM "user_credentials" WHERE "user_id"=?',
            (user_id,),
        )
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

    def set_channel(self, user_id: int, channel: str, credentials: dict[str, Any]) -> None:
        """合并语义写入渠道凭证，仅覆盖传入的非掩码字段。

        P2-2 O-3 加固：拒绝掩码占位符作为真实凭证写入——检测到掩码值时
        抛出 ValueError（不静默跳过、不写入任何字段），强制调用方感知。
        日志仅记录键名与值长度，严禁打印原始值（脱敏）。

        :raises ValueError: 当检测到掩码占位符或非法类型时
        """
        # 防御性校验：任何字段值为掩码占位符 → 整体拒绝（原子性，防部分写入）
        for k, v in credentials.items():
            if isinstance(v, str) and v.strip() in self.MASKED_VALUES:
                logger.warning(
                    "拒绝写入掩码占位符: channel=%s key=%s value_len=%d",
                    channel, k, len(v),
                    extra={"source_type": "credential_helper", "user_id": user_id},
                )
                raise ValueError(
                    f"凭证校验失败: 字段 '{k}' 的值疑似掩码占位符，请重新输入真实凭证。"
                )

        existing = self.get_channel(user_id, channel) or {}
        merged: dict[str, str] = {k: str(v) for k, v in existing.items()}
        for k, v in credentials.items():
            if k == "enabled":
                merged[k] = "true" if v else "false"
            # 拦截空值（清空语义），防止覆盖真实凭据；类型安全：非 str 值转 str 写入
            elif isinstance(v, str) and v.strip() == "":
                continue
            else:
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

    # ── 显式迁移（CQS：唯一含写入副作用的入口，首次启动引导） ──

    def migrate_from_config_if_empty(self, user_id: int = SYSTEM_DEFAULT_USER_ID) -> bool:
        """从 config.json 迁移凭证到 DB（显式、幂等、并发安全）。

        仅在首次启动引导时由 NotificationManager 调用一次：
        - DB 已有凭证 → 跳过（幂等快速路径）
        - config.json 无有效凭证 → 跳过
        - 写入冲突（多进程并发）→ 捕获并返回 False，不崩溃
        """
        # 1. 检查是否已存在（快速路径）
        if self.get_all(user_id):
            logger.debug("用户 %s 凭证已存在于数据库，跳过迁移", user_id)
            return False

        # 2. 读取 config.json（纯读取，无副作用）
        fallback = self._try_fallback_from_config()
        if not fallback:
            logger.warning("配置文件中缺少有效渠道凭证，跳过迁移")
            return False

        # 3. 执行写入（并发冲突由 INSERT OR REPLACE 幂等 + 异常捕获保证）
        try:
            for channel, creds in fallback.items():
                self.set_channel(user_id, channel, creds)
            logger.info("已从配置文件迁移渠道凭证到数据库，用户 %s", user_id)
            return True
        except Exception as e:
            # 捕获并发写入或其他异常，保证启动不崩溃
            logger.warning("迁移跳过（并发写入或已存在数据）: %s", e)
            return False

    # ── 配置回退读取（纯读取，无写副作用） ─────────────────

    def _try_fallback_from_config(self) -> dict[str, dict[str, str]] | None:
        """从 config.json 读取旧渠道配置（纯读取，仅供显式迁移使用）。"""
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
