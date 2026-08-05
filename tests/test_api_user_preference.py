# tests/test_api_user_preference.py
# user_preference API 集成测试 — GET / PATCH / DELETE /api/user-preference

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.user_preference import router
from docker.auth import get_current_user_id


def _build_client():
    """构建独立 FastAPI app（不含 AuthMiddleware，避免认证干扰端点测试）。"""
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _mock_auth(app, username=1):
    """注入 get_current_user_id 依赖覆盖，模拟已登录用户。

    get_current_user_id 返回 user_id（int），因此 mock 使用整数 1。
    """
    app.dependency_overrides[get_current_user_id] = lambda: username


class TestUserPreferenceAPI:
    """user_preference 端点测试"""

    @patch("docker.api.user_preference.get_user_by_id")
    @patch("pilotstd.manager.settings_manager.UserPreferenceManager.get_preferences")
    def test_get_preferences_returns_full_data(self, mock_get, mock_user):
        mock_user.return_value = {"id": 1, "username": "testuser", "role": "user"}
        mock_get.return_value = {"ui": {"theme": "dark", "language": "zh-CN"}}

        client = _build_client()
        _mock_auth(client.app)

        r = client.get("/api/user-preference")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "success"
        assert data["data"]["ui"]["theme"] == "dark"

    @patch("docker.api.user_preference.get_user_by_id")
    def test_get_preferences_user_not_found(self, mock_user):
        mock_user.return_value = None

        client = _build_client()
        _mock_auth(client.app)

        r = client.get("/api/user-preference")
        assert r.status_code == 404

    @patch("docker.api.user_preference.get_user_by_id")
    @patch("pilotstd.manager.settings_manager.UserPreferenceManager.update_preferences")
    def test_patch_preferences_updates_and_returns(self, mock_update, mock_user):
        mock_user.return_value = {"id": 1, "username": "testuser", "role": "user"}
        mock_update.return_value = {"ui": {"theme": "dark", "language": "zh-CN"}}

        client = _build_client()
        _mock_auth(client.app)

        r = client.patch("/api/user-preference", json={"updates": {"ui": {"theme": "dark"}}})
        assert r.status_code == 200
        assert r.json()["data"]["ui"]["theme"] == "dark"

    @patch("docker.api.user_preference.get_user_by_id")
    def test_patch_preferences_user_not_found(self, mock_user):
        mock_user.return_value = None

        client = _build_client()
        _mock_auth(client.app)

        r = client.patch("/api/user-preference", json={"updates": {"ui": {"theme": "dark"}}})
        assert r.status_code == 404

    @patch("docker.api.user_preference.get_user_by_id")
    @patch("pilotstd.manager.settings_manager.UserPreferenceManager.update_preferences")
    def test_patch_empty_updates_ok(self, mock_update, mock_user):
        mock_user.return_value = {"id": 1, "username": "testuser", "role": "user"}
        mock_update.return_value = {"ui": {"theme": "light", "language": "zh-CN"}}

        client = _build_client()
        _mock_auth(client.app)

        r = client.patch("/api/user-preference", json={"updates": {}})
        assert r.status_code == 200

    @patch("docker.api.user_preference.get_user_by_id")
    @patch("pilotstd.manager.settings_manager.UserPreferenceManager.reset_preferences")
    def test_delete_preferences_resets_to_defaults(self, mock_reset, mock_user):
        mock_user.return_value = {"id": 1, "username": "testuser", "role": "user"}
        mock_reset.return_value = {"ui": {"theme": "light", "language": "zh-CN"}}

        client = _build_client()
        _mock_auth(client.app)

        r = client.delete("/api/user-preference")
        assert r.status_code == 200
        assert r.json()["message"] == "已恢复默认设置"

    @patch("docker.api.user_preference.get_user_by_id")
    def test_delete_preferences_user_not_found(self, mock_user):
        mock_user.return_value = None

        client = _build_client()
        _mock_auth(client.app)

        r = client.delete("/api/user-preference")
        assert r.status_code == 404

    def test_unauthenticated_returns_401(self):
        """无认证时端点返回 401（FastAPI dependency override 未设时，get_current_user_id 抛出 401）。"""
        client = _build_client()
        # 不设置 dependency_overrides，让真实的 get_current_user_id 执行
        r = client.get("/api/user-preference")
        assert r.status_code == 401
