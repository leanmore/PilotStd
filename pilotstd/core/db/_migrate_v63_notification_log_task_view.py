# 模块：项目/核心/数据库/迁移_v63脚本
# v63：notification_log 追加「任务视角」列（阶段 1b，零行为变更）
#
# 背景：通知此前只有"事件类型"，没有"这属于哪个任务"的概念。本批加 4 列承载任务视角：
#   task_id       关联 Task 实体（投影自 task_queue.task_id）
#   notify_event  通知事件（三层模型 10 类之一，如 task_progress/task_result/task_failure/user_activity）
#   content_type  主内容类型（text/field_list/status_change/list/task_progress/action_prompt）
#   task_context  任务上下文快照（JSON 文本）
#
# task_context 的列类型选 TEXT 的理由（SQLite 无原生 JSON 类型）：
#   1. 本项目既有非标量落库一律走 TEXT + json.dumps/loads（如 notification_queue.event_data、
#      user_preferences.preference_value），保持一致可复用同一编解码模块 _json_codec；
#   2. SQLite 的 JSON1 扩展（json_extract 等）在旧库/精简构建上不保证存在，故不依赖它；
#   3. 本项目不对该列做 SQL 层查询（只整存整取），无需可索引的结构化列。
#
# 铁律：已执行迁移源码不可变（P-106，改动会触发 checksum 不匹配导致库无法启动）
# → 只能新增版本号追加（同 v48…v62 的追加范式）。

from typing import Any

from ._constants import migration


@migration(63)
def _migrate_v63_notification_log_task_view(db: Any) -> None:
    """notification_log 追加 4 个任务视角列（幂等；列已存在则跳过）。"""
    # 列名与类型取自本文件常量元组（R-009：SQLite 的 ALTER TABLE 列名无法参数化，
    # 故只能用同文件字面量，禁止外部数据拼接）
    for col, decl in (
        ("task_id", "TEXT NOT NULL DEFAULT ''"),
        ("notify_event", "TEXT NOT NULL DEFAULT ''"),
        ("content_type", "TEXT NOT NULL DEFAULT ''"),
        # 空槽用 ''（而非 '{}'）：读回时 '' 经 _json_codec.loads_dict 同样得到 {}，
        # 两者语义等价，取更短且与「未设置」一致的表征。
        ("task_context", "TEXT NOT NULL DEFAULT ''"),
    ):
        try:
            db.execute(f"ALTER TABLE notification_log ADD COLUMN {col} {decl}")
        except Exception:
            # 列已存在则跳过（幂等；与 v27/v29/v40/v62 等既有追加迁移同款防御）
            pass
