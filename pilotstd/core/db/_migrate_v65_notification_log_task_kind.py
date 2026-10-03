# 模块：项目/核心/数据库/迁移_v65脚本
# v65：notification_log 追加 task_kind 列（阶段 2.5a，零行为变更）
#
# 背景：`task_kind` 自 2a 起由 `mapping.project()` 产出，但 2b 只回填了
# `notify_event`/`content_type`（当时 `NotificationMessage` 无该字段）。
# 2.5a 把它接到消息模型并落库——消费点是阶段 2.5b 的聚合键切换。
#
# 列类型 TEXT（非 JSON）：它是**标量字符串**（值域见 mapping.TASK_KINDS），
# 不需要 _json_codec 编解码；与 1a/1b/1c 的非标量列形成对照。
#
# 铁律：已执行迁移源码不可变（P-106）→ 只能新增版本号追加（同 v48…v64 的追加范式）。

from typing import Any

from ._constants import migration


@migration(65)
def _migrate_v65_notification_log_task_kind(db: Any) -> None:
    """notification_log 追加 task_kind 列（幂等；列已存在则跳过）。"""
    # 列名与类型取自本文件常量（R-009：SQLite 的 ALTER TABLE 列名无法参数化）
    try:
        db.execute("ALTER TABLE notification_log ADD COLUMN task_kind TEXT NOT NULL DEFAULT ''")
    except Exception:
        # 列已存在则跳过（幂等；与 v27/v29/v40/v62/v63/v64 等既有追加迁移同款防御）
        pass
