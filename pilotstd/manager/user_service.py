# pilotstd/manager/user_service.py
# 用户管理服务 — 供 API 层调用

import hashlib
import json
import secrets
from typing import Any


class UserService:
    """用户管理业务逻辑。"""

    def __init__(self, manager: Any):
        self._mgr = manager

    @staticmethod
    def _hash_password(password: str) -> str:
        salt = secrets.token_hex(16)
        return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

    def get_user_id(self, username: str) -> int | None:
        row = self._mgr.db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
        return row["id"] if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """按用户 ID 查询用户信息（供 API 层迁移）。"""
        row = self._mgr.db.fetchone("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
        return dict(row) if row else None

    # ── 布局 ─────────────────────────────────

    def get_layout(self, user_id: int) -> dict[str, Any]:
        row = self._mgr.db.fetchone(
            "SELECT layout_data FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
            (user_id,),
        )
        return {"layout": row["layout_data"] if row else None}

    def save_layout(self, user_id: int, layout_data: str) -> dict[str, Any]:
        if not layout_data:
            return {"error": "缺少 layout 字段"}
        self._mgr.db.execute(
            "INSERT OR REPLACE INTO user_layouts (user_id, layout_key, layout_data, updated_at) "
            "VALUES (?, 'dashboard', ?, datetime('now', 'localtime'))",
            (user_id, layout_data),
        )
        return {"ok": True}

    def delete_layout(self, user_id: int) -> dict[str, Any]:
        self._mgr.db.execute(
            "DELETE FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
            (user_id,),
        )
        return {"ok": True}

    # ── 首选项 ─────────────────────────────────

    def get_preferences(self, user_id: int) -> dict[str, Any]:
        rows = self._mgr.db.fetchall(
            "SELECT preference_key, preference_value, updated_at "
            "FROM user_preferences WHERE user_id=? ORDER BY preference_key",
            (user_id,),
        )
        return {"preferences": {r["preference_key"]: json.loads(r["preference_value"]) for r in rows}}

    def get_preference(self, user_id: int, key: str) -> dict[str, Any]:
        row = self._mgr.db.fetchone(
            "SELECT preference_key, preference_value, updated_at "
            "FROM user_preferences WHERE user_id=? AND preference_key=?",
            (user_id, key),
        )
        if row is None:
            return {"key": key, "value": None}
        return {
            "key": row["preference_key"],
            "value": json.loads(row["preference_value"]),
            "updated_at": row["updated_at"],
        }

    def save_preference(self, user_id: int, key: str, value: Any) -> dict[str, Any]:
        self._mgr.db.execute(
            "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at) "
            "VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (user_id, key, json.dumps(value, ensure_ascii=False)),
        )
        return {"ok": True, "key": key}

    def save_preferences_batch(self, user_id: int, preferences: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(preferences, dict) or not preferences:
            return {"error": "缺少 preferences 字段"}
        for key, val in preferences.items():
            self._mgr.db.execute(
                "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at) "
                "VALUES (?, ?, ?, datetime('now', 'localtime'))",
                (user_id, key, json.dumps(val, ensure_ascii=False)),
            )
        return {"ok": True, "count": len(preferences)}

    def delete_preference(self, user_id: int, key: str) -> dict[str, Any]:
        self._mgr.db.execute(
            "DELETE FROM user_preferences WHERE user_id=? AND preference_key=?",
            (user_id, key),
        )
        return {"ok": True, "key": key}
