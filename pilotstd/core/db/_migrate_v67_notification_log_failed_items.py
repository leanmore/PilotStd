# 模块：项目/核心/数据库/迁移_v67脚本
# v67：notification_log 追加 failed_items 列（批量导入/汇总的**逐条失败明细**落库）
#
# 为什么需要这一列：需求①要求"大批量导入（查询/下载/规范化/存档）失败时，详细说明各自总数
# + 标准号 + 标准名"。此前汇总事件只传计数（total/success/failed），**没有失败名单** ⇒ 用户只看到
# "失败 7 条"，看不到"哪一类失败 × 哪个标准号 × 叫什么"。明细先由生产侧采集进 payload
# （`failed_items`，4 列固定口径：standard_number / standard_name / error_type / error_message），
# 再经 `NotificationMessage.failed_items` 透传，本迁移负责**建列**；运行期写入由
# `_manager_ops.py` 的 INSERT 负责（先例：task_context / actions / attachments / channel_message_ids
# 均为 TEXT 存 JSON）。
#
# 口径与边界（与 B1 裁定一致）：
#   · 列类型 TEXT 存 JSON 文本（沿用既有 JSON 列先例），默认 `'[]'` ⇒ 旧行/无明细行**语义为"无明细"**；
#   · **不加索引**：明细检索仍走 correlation_id / message_id（它们是既有列），列本身无需索引；
#   · 不改任何既有列语义 ⇒ **历史数据无需迁移**（无明细即 `[]`，读侧自然降级）。
#
# 幂等（可重复执行）：补列前先 `PRAGMA table_info` 探测，列已存在即跳过（先例：_migrate_v54.py 同款做法）。

from typing import Any

from ._constants import migration


@migration(67)
def _migrate_v67_notification_log_failed_items(db: Any) -> None:
    """notification_log 补 failed_items 列（TEXT 存 JSON，默认 '[]'；探测式幂等）。"""
    tables = {r["name"] for r in db.fetchall("SELECT name FROM sqlite_master WHERE type='table'")}
    if "notification_log" not in tables:
        return

    cols = {r["name"] for r in db.fetchall("PRAGMA table_info(notification_log)")}
    if "failed_items" in cols:
        return

    db.execute(
        "ALTER TABLE notification_log ADD COLUMN failed_items TEXT NOT NULL DEFAULT '[]'"
    )
