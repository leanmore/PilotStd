# 模块：项目/核心/数据库/迁移_v68脚本
# v68：notification_policy 追加 event_classes 列（订阅粒度从"41 个原始事件"升级为"**10 类**"）
#
# 为什么需要这一列（阶段 4 · P6 · 4a）：
# 现状 `notification_policy(user_id, channel, events)` 的 `events` 存的是**41 个原始业务事件名**；
# 用户裁决（Q1）要求配置入口变成**双层**——第一层按 `notify_event` 10 类订阅（主入口），
# 第二层保留"高级：按业务事件细分"（41 项，原有表达力）。
# 两层的**语义不同**（类 vs 事件），混存进同一列会让"关闭某类"无法表达（并集语义）⇒ 故**单独加列**。
#
# 口径与边界（与 P6 术前设计 §三 方案甲、§六 裁定 1 一致）：
#   · 列类型 TEXT 存 JSON 文本（沿用既有 JSON 列先例），默认 `'[]'` ⇒ **旧行语义为"未设置类别"**；
#   · **读侧双读**（`_policy.py`）：`event_classes` 非空 ⇒ **只用它**（新字段优先，裁定 4 甲）；
#     为空 ⇒ 回退 `events`（保证第 1 层回滚开关 `NOTIFY_REDESIGN_STAGE=3` 真实可用）；
#   · **不改 `events` 语义**、不加索引、不做数据搬迁 ⇒ **历史数据无需迁移**（回滚只需忽略新列）；
#   · `fetch_task` 归并不属本批（裁定 2 乙：本批不动）。
#
# 幂等（可重复执行）：补列前先 `PRAGMA table_info` 探测，列已存在即跳过（先例：_migrate_v67 / _migrate_v54）。
#
# 运维前置（P6 术前设计 §四 第 2 层）：**执行迁移前**请先导出 `notification_policy` 全表快照到仓库外，
# 并记录行数；本迁移会把迁移后的行数写进日志，便于与快照对照。

from typing import Any

from ._constants import migration


@migration(68)
def _migrate_v68_notification_policy_event_classes(db: Any) -> None:
    """notification_policy 补 `event_classes` 列（TEXT 存 JSON，默认 '[]'；探测式幂等）。"""
    tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    if "notification_policy" not in tables:
        return

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(notification_policy)")}
    if "event_classes" in cols:
        return

    db.execute(
        "ALTER TABLE notification_policy ADD COLUMN event_classes TEXT NOT NULL DEFAULT '[]'"
    )
    # 行数留痕：供运维与迁移前快照对照（迁移本身不改数据，这里只是可观测性）
    # 日志文案用 ASCII：G-047（Python 侧 i18n 硬编码）把"新增中文字面量"计为新违规，
    # 而这是给运维/开发者看的诊断、不是用户可见文案 ⇒ 不进 i18n 资源。
    rows = db.fetchall("SELECT COUNT(*) AS n FROM notification_policy")
    count = rows[0]["n"] if rows else 0
    import logging

    logging.getLogger(__name__).info(
        "v68 added notification_policy.event_classes; policy rows=%d (compare with pre-migration snapshot)",
        count,
    )
