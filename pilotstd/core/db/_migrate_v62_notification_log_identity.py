# 模块：项目/核心/数据库/迁移_v62脚本
# v62：notification_log 追加「通知身份」列（阶段 1a，零行为变更）
#
# 背景：通知系统此前只有"发送日志行号"，没有消息身份——聚合后的消息无法回溯、
# 回调无处定位、投递态与回执态无从记录。本批先加列（不写入值），
# 写入由 NotificationMessage 新字段的默认值承载，故对既有行为零影响。
#
# 铁律：已执行迁移源码不可变（P-106，改动会触发 checksum 不匹配导致库无法启动）
# → 只能新增版本号追加（同 v48…v61 的追加范式）。
#
# 列语义（详见 docs/plans/notification-redesign/02-目标架构.md §2.2）：
#   message_id      通知消息稳定 ID；回调据此定位渠道消息
#   correlation_id  同一次业务运行的关联键（同一批次多条通知可归组）
#   delivery_status 投递态 pending/sent/failed/suppressed/edited
#   ack_status      回执态 none/delivered/read/acted
#
# 注意：**不动 `status` 列**——那是业务结果态（success/failure），
# 与投递态语义不同；复用会让历史数据被误读（见 04-影响面.md §六 第 5 项）。

from typing import Any

from ._constants import migration


@migration(62)
def _migrate_v62_notification_log_identity(db: Any) -> None:
    """notification_log 追加 4 个通知身份列（幂等；列已存在则跳过）。"""
    # 列名与类型取自本文件常量元组（R-009：动态表名/列名不得拼外部数据；
    # SQLite 的 ALTER TABLE 列名无法参数化，故只能用同文件字面量）
    for col, decl in (
        ("message_id", "TEXT NOT NULL DEFAULT ''"),
        ("correlation_id", "TEXT NOT NULL DEFAULT ''"),
        ("delivery_status", "TEXT NOT NULL DEFAULT 'pending'"),
        ("ack_status", "TEXT NOT NULL DEFAULT 'none'"),
    ):
        try:
            db.execute(f"ALTER TABLE notification_log ADD COLUMN {col} {decl}")
        except Exception:
            # 列已存在则跳过（幂等；与 v27/v29/v40 等既有追加迁移同款防御）
            pass
