# 模块：项目/核心/数据库/迁移_v69脚本
# v69：自愈「通知渠道凭据迁移失败、却已被标记为完成」的历史坏状态（体检 D-5，2026-10-17）。
#
# 问题（实测）：
#   v37+ 的 `_migrate_v37_plus` 把 config.json 的 `notification.channels` 加密写进
#   `user_credentials` 时**吞掉了异常**（`except Exception: pass`），随后**无条件**把
#   `notification._migrated_to_db` 置 True ⇒ 迁移失败但标记已落盘 ⇒ 下次启动不再重试，
#   用户以为通知配置已迁移，实际渠道凭据永久丢失，且日志里一个字都没有。
#
# 为什么新增迁移而不是改 v37（P-106）：
#   `tests/test_migration_checksum_guard.py` 强制「已执行迁移源码不可变」（按 inspect.getsource
#   取哈希比对），改历史迁移会直接红。故按"新增一版修复"的合规路径处理。
#
# 触发条件（三者同时满足才动作，避免无谓写盘）：
#   ① `notification._migrated_to_db` 为 True（旧迁移声称做完了）；
#   ② config.json 的 `notification.channels` 非空（还有源数据可搬）；
#   ③ `user_credentials` 里**缺**这些渠道（以 DB 为 SSOT：DB 已有的绝不覆盖）。
#
# 失败处理：只记 warning，**不抛**。
#   抛错会让本迁移不被记为已应用、每次启动都重试；若凭据本身不可解密（确定性失败），
#   就会把启动拖垮。日志里给出人工处置指引（去设置页重存渠道配置）。
#
# 幂等：可重复执行（已存在的渠道跳过）。

import json as _json
import logging
import os as _os
from typing import Any

from ._constants import migration

logger = logging.getLogger(__name__)

# 与 `_migrate_v37_plus` 同口径：渠道凭据挂在默认用户（user_id=1）下
_CHANNEL_USER_ID = 1


@migration(69)
def _migrate_v69_reheal_notification_credentials(db: Any) -> None:
    """自愈通知渠道凭据：标记说"已迁移"但 DB 里缺渠道时，从 config.json 重做一次。

    日志文案刻意用英文：G-047 会把新增的中文字面量计为新违规（与本目录既有迁移的注释口径一致）。
    """
    try:
        from pilotstd.core.config import ConfigManager as _CM

        cfg = _CM()
        notification = cfg._data.get("notification") or {}
        if not notification.get("_migrated_to_db"):
            # 旧迁移没声称做完 ⇒ 不在本迁移职责内（正常迁移路径会处理）
            return
        channels = notification.get("channels") or {}
        if not channels:
            return

        existing = {
            str(row["channel"])
            for row in db.fetchall(
                'SELECT "channel" FROM "user_credentials" WHERE "user_id" = ?',
                (_CHANNEL_USER_ID,),
            )
        }
        missing = {
            str(name): conf
            for name, conf in channels.items()
            if isinstance(conf, dict) and conf and str(name) not in existing
        }
        if not missing:
            # 健康：DB 里该有的都有（含"根本没有渠道配置"的情况）
            return

        from pilotstd.core.config.crypto import _get_fernet

        fernet = _get_fernet(_os.path.dirname(cfg._filepath))
        healed = 0
        for name, conf in missing.items():
            plain = _json.dumps(conf, ensure_ascii=False)
            encrypted = fernet.encrypt(plain.encode()).decode()
            db.execute(
                'INSERT OR REPLACE INTO "user_credentials"'
                ' ("user_id", "channel", "credentials") VALUES (?, ?, ?)',
                (_CHANNEL_USER_ID, name, encrypted),
            )
            healed += 1
        logger.warning(
            "v69 self-heal: restored %d notification channel credential(s) %s "
            "(the original migration marked itself done despite failing)",
            healed,
            sorted(missing),
        )
    except Exception as exc:
        # 不抛：见文件头"失败处理"。至少要让人在日志里看见，而不是再次静默。
        logger.warning(
            "v69 self-heal failed: %s. Notification channel credentials may still be missing; "
            "open Settings -> Notification and re-save the affected channel(s).",
            exc,
            exc_info=True,
        )
