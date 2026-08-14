# 模块：项目/核心//迁移_v50脚本
# v50 兜底迁移 — 从 migrations.py 拆出，避免 G-010 单文件超限

from typing import Any


def _migrate_v50_ensure_user_preferences(db: Any) -> None:
    """兜底补建 user_preferences 表，修复部分实例跳过 v22/v49 导致表缺失。

    v48 仅补了 user_layouts/user_settings，未覆盖 user_preferences；
    此处用 IF NOT EXISTS 保证幂等，列结构与 v49 完全一致。
    """
    db.execute("""CREATE TABLE IF NOT EXISTS user_preferences (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL,
        preference_key TEXT NOT NULL, preference_value TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, preference_key))""")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_prefs_uid_key "
        "ON user_preferences(user_id, preference_key)")
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_prefs_pref_key "
        "ON user_preferences(preference_key)")
