# 模块：项目/管理器/_服务脚本
# 用户管理服务—供接口层调用

import hashlib
import json
import secrets
from typing import Any


class UserService:
    """用户管理业务逻辑。"""

    def __init__(self, manager: Any):
        """初始化用户服务，持有 StandardManager 引用。"""
        self._mgr = manager

    @staticmethod
    def _hash_password(password: str) -> str:
        """对密码加盐哈希，返回 salt:hash 格式字符串。"""
        salt = secrets.token_hex(16)
        return salt + ":" + hashlib.sha256((salt + password).encode()).hexdigest()

    def get_user_id(self, username: str) -> int | None:
        """按用户名查询用户 ID，不存在时返回 None。"""
        row = self._mgr.db.fetchone("SELECT id FROM users WHERE username = ?", (username,))
        return row["id"] if row else None

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        """按用户 ID 查询用户信息（供 API 层迁移）。"""
        row = self._mgr.db.fetchone("SELECT id, username, role FROM users WHERE id = ?", (user_id,))
        return dict(row) if row else None

    # ── 布局 ─────────────────────────────────

    def get_layout(self, user_id: int) -> dict[str, Any]:
        """获取用户仪表盘布局数据。"""
        row = self._mgr.db.fetchone(
            "SELECT layout_data FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
            (user_id,),
        )
        return {"layout": row["layout_data"] if row else None}

    def save_layout(self, user_id: int, layout_data: str) -> dict[str, Any]:
        """保存用户仪表盘布局数据（JSON 字符串）。"""
        if not layout_data:
            return {"error": "缺少 layout 字段"}
        self._mgr.db.execute(
            "INSERT OR REPLACE INTO user_layouts (user_id, layout_key, layout_data, updated_at) "
            "VALUES (?, 'dashboard', ?, datetime('now', 'localtime'))",
            (user_id, layout_data),
        )
        return {"ok": True}

    def delete_layout(self, user_id: int) -> dict[str, Any]:
        """删除用户仪表盘布局数据。"""
        self._mgr.db.execute(
            "DELETE FROM user_layouts WHERE user_id=? AND layout_key='dashboard'",
            (user_id,),
        )
        return {"ok": True}

    # ── 首选项 ─────────────────────────────────

    def get_preferences(self, user_id: int) -> dict[str, Any]:
        """获取用户全部偏好设置（KV 表），返回 {preferences: {key: value}}。"""
        rows = self._mgr.db.fetchall(
            "SELECT preference_key, preference_value, updated_at "
            "FROM user_preferences WHERE user_id=? ORDER BY preference_key",
            (user_id,),
        )
        return {"preferences": {r["preference_key"]: json.loads(r["preference_value"]) for r in rows}}

    def get_preference(self, user_id: int, key: str) -> dict[str, Any]:
        """按 key 获取单个用户偏好值，不存在时返回 {key: key, value: None}。"""
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
        """保存单个用户偏好键值对（JSON 序列化存储）。"""
        self._mgr.db.execute(
            "INSERT OR REPLACE INTO user_preferences (user_id, preference_key, preference_value, updated_at) "
            "VALUES (?, ?, ?, datetime('now', 'localtime'))",
            (user_id, key, json.dumps(value, ensure_ascii=False)),
        )
        return {"ok": True, "key": key}

    def save_preferences_batch(self, user_id: int, preferences: dict[str, Any]) -> dict[str, Any]:
        """批量保存用户偏好（一次请求保存多个键值对）。"""
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
        """删除单个用户偏好键。"""
        self._mgr.db.execute(
            "DELETE FROM user_preferences WHERE user_id=? AND preference_key=?",
            (user_id, key),
        )
        return {"ok": True, "key": key}

    # ──统一设置（31：减少网络请求数）─────

    def get_user_settings(self, user_id: int) -> dict[str, Any]:
        """一次返回 layout + preferences。"""
        layout = self.get_layout(user_id)
        prefs = self.get_preferences(user_id)
        return {"layout": layout.get("layout"), "preferences": prefs.get("preferences", {})}

    def save_user_settings(self, user_id: int, data: dict[str, Any]) -> dict[str, Any]:
        """一次保存 layout（可选）和 preferences（可选）。"""
        if "layout" in data:
            self.save_layout(user_id, data["layout"])
        if "preferences" in data:
            prefs = data["preferences"]
            if isinstance(prefs, dict) and prefs:
                self.save_preferences_batch(user_id, prefs)
        return {"ok": True}
