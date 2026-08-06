# tests/test_api_user_preference.py
# user_preferences API 集成测试 — GET/PUT/DELETE /api/user/preferences

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.user import router
from docker.auth import get_current_user_id
from docker.manager import get_manager_dep


def _build_client(mgr=None):
    app = FastAPI()
    app.include_router(router)
    # 依赖覆盖：get_manager_dep 是 async，返回一个直接值 FastAPI 会自动处理
    if mgr:
        app.dependency_overrides[get_manager_dep] = lambda: mgr
    app.dependency_overrides[get_current_user_id] = lambda: 1
    return TestClient(app)


class TestUserPreferencesAPI:
    """新 user_preferences 端点测试（RESTful KV API）"""

    # ── GET /api/user/preferences/{key} ──

    def test_get_single_preference_found(self):
        mgr = MagicMock()
        mgr.user_service.get_preference.return_value = {
            "key": "ui", "value": {"theme": "dark"}, "updated_at": "2026-01-01"
        }
        client = _build_client(mgr)
        r = client.get("/api/user/preferences/ui")
        assert r.status_code == 200
        assert r.json()["key"] == "ui"
        assert r.json()["value"]["theme"] == "dark"

    def test_get_single_preference_not_found(self):
        mgr = MagicMock()
        mgr.user_service.get_preference.return_value = {"key": "unknown", "value": None}
        client = _build_client(mgr)
        r = client.get("/api/user/preferences/unknown")
        assert r.status_code == 200
        assert r.json()["value"] is None

    # ── PUT /api/user/preferences/{key} ──

    def test_put_single_preference_ok(self):
        mgr = MagicMock()
        mgr.user_service.save_preference.return_value = {"ok": True, "key": "theme"}
        client = _build_client(mgr)
        r = client.put("/api/user/preferences/theme", json={"value": "dark"})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_put_single_preference_missing_value(self):
        mgr = MagicMock()
        client = _build_client(mgr)
        r = client.put("/api/user/preferences/theme", json={})
        assert r.status_code == 400

    # ── PUT /api/user/preferences (batch) ──

    def test_put_preferences_batch_ok(self):
        mgr = MagicMock()
        mgr.user_service.save_preferences_batch.return_value = {"ok": True, "count": 2}
        client = _build_client(mgr)
        r = client.put("/api/user/preferences", json={
            "preferences": {"theme": "dark", "lang": "zh-CN"}
        })
        assert r.status_code == 200
        assert r.json()["ok"] is True

    def test_put_preferences_batch_missing_field(self):
        mgr = MagicMock()
        mgr.user_service.save_preferences_batch.return_value = {"error": "缺少 preferences 字段"}
        client = _build_client(mgr)
        r = client.put("/api/user/preferences", json={})
        assert r.status_code == 400

    # ── DELETE /api/user/preferences/{key} ──

    def test_delete_preference_ok(self):
        mgr = MagicMock()
        mgr.user_service.delete_preference.return_value = {"ok": True, "key": "theme"}
        client = _build_client(mgr)
        r = client.delete("/api/user/preferences/theme")
        assert r.status_code == 200
        assert r.json()["ok"] is True

    # ── GET /api/user/preferences (batch) ──

    def test_get_all_preferences_ok(self):
        mgr = MagicMock()
        mgr.user_service.get_preferences.return_value = {
            "preferences": {"ui": {"theme": "dark"}, "sidebar_collapsed": False}
        }
        client = _build_client(mgr)
        r = client.get("/api/user/preferences")
        assert r.status_code == 200
        assert r.json()["preferences"]["ui"]["theme"] == "dark"

    # ── 未认证 ──

    def test_unauthenticated_returns_401(self):
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        r = client.get("/api/user/preferences/ui")
        assert r.status_code == 401

    # ── key 中包含特殊字符（: / 等） ──

    def test_get_preference_with_colon_in_key(self):
        mgr = MagicMock()
        mgr.user_service.get_preference.return_value = {
            "key": "layout:dashboard", "value": [{"i": "stats"}], "updated_at": ""
        }
        client = _build_client(mgr)
        r = client.get("/api/user/preferences/layout:dashboard")
        assert r.status_code == 200
        assert r.json()["key"] == "layout:dashboard"
