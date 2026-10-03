# 模块：项目/核心/数据库/迁移_v64脚本
# v64：notification_log 追加「交互能力」列（阶段 1c，零行为变更）
#
# 背景：通知此前没有任何交互能力（无按钮、无回调、无附件、拿不到渠道消息 ID）。
# 本批加 4 列承载交互数据：
#   actions              动作规格列表（JSON 数组文本）
#   callback_data        回调载荷（**纯字符串**，<= 64 字节，格式 v1|message_id|action|arg）
#   attachments          附件规格列表（JSON 数组文本）
#   channel_message_ids  渠道名 -> 渠道消息 ID（JSON 对象文本）
#
# 列类型判断：4 列全部 TEXT，理由：
#   1. **与 1b 的 task_context 同款**——本仓非标量落库一律 TEXT + json.dumps/loads
#      （notification_queue.event_data、user_preferences.preference_value），
#      复用同一编解码模块 _json_codec，不为单个字段发明新范式；
#   2. SQLite 的 JSON1 扩展（json_extract 等）在旧库/精简构建上不保证存在，不依赖；
#   3. 这 4 列都只整存整取、不做 SQL 层查询（阶段 3 的回调按 message_id 反查，
#      用的是本表的**独立列** message_id（1a 已建），不是 JSON 内部字段）。
#   callback_data 本身是字符串，取 TEXT 属自然映射（不需要 JSON 编解码）。
#
# 铁律：已执行迁移源码不可变（P-106）→ 只能新增版本号追加（同 v48…v63 的追加范式）。

from typing import Any

from ._constants import migration


@migration(64)
def _migrate_v64_notification_log_interactive(db: Any) -> None:
    """notification_log 追加 4 个交互能力列（幂等；列已存在则跳过）。"""
    # 列名与类型取自本文件常量元组（R-009：SQLite 的 ALTER TABLE 列名无法参数化）
    for col, decl in (
        ("actions", "TEXT NOT NULL DEFAULT ''"),
        ("callback_data", "TEXT NOT NULL DEFAULT ''"),
        ("attachments", "TEXT NOT NULL DEFAULT ''"),
        ("channel_message_ids", "TEXT NOT NULL DEFAULT ''"),
    ):
        try:
            db.execute(f"ALTER TABLE notification_log ADD COLUMN {col} {decl}")
        except Exception:
            # 列已存在则跳过（幂等；与 v27/v29/v40/v62/v63 等既有追加迁移同款防御）
            pass
