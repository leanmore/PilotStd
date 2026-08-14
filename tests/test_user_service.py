"""user_service 补测。"""
from unittest.mock import MagicMock

import pytest

from pilotstd.manager.user_service import UserService


class TestUserService:
    @pytest.fixture
    def svc(self):
        return UserService(MagicMock())

    def test_hash_password_format(self, svc):
        h = svc._hash_password("mypass")
        assert ":" in h
        salt, hash_val = h.split(":")
        assert len(salt) == 32

    def test_hash_password_random_salt(self, svc):
        assert svc._hash_password("same") != svc._hash_password("same")

    def test_get_user_id_found(self, svc):
        svc._mgr.db.fetchone.return_value = {"id": 42}
        assert svc.get_user_id("admin") == 42

    def test_get_user_id_not_found(self, svc):
        svc._mgr.db.fetchone.return_value = None
        assert svc.get_user_id("nobody") is None

    def test_get_layout(self, svc):
        svc._mgr.db.fetchone.return_value = {"layout_data": '{"x":1}'}
        assert svc.get_layout(1)["layout"] == '{"x":1}'

    def test_save_layout(self, svc):
        assert svc.save_layout(1, '{"y":2}')["ok"] is True

    def test_save_layout_empty(self, svc):
        assert "error" in svc.save_layout(1, "")

    def test_get_user_by_id_found(self, svc):
        svc._mgr.db.fetchone.return_value = {"id": 1, "username": "admin", "role": "superadmin"}
        u = svc.get_user_by_id(1)
        assert u["username"] == "admin"

    def test_get_user_by_id_not_found(self, svc):
        svc._mgr.db.fetchone.return_value = None
        assert svc.get_user_by_id(999) is None

    def test_get_preferences(self, svc):
        svc._mgr.db.fetchall.return_value = [
            {"preference_key": "theme", "preference_value": '"dark"'},
            {"preference_key": "lang", "preference_value": '"zh"'},
        ]
        r = svc.get_preferences(1)
        assert r["preferences"]["theme"] == "dark"

    def test_get_preference_found(self, svc):
        svc._mgr.db.fetchone.return_value = {
            "preference_key": "theme", "preference_value": '"light"', "updated_at": "2026-01-01"
        }
        r = svc.get_preference(1, "theme")
        assert r["value"] == "light"

    def test_get_preference_not_found(self, svc):
        svc._mgr.db.fetchone.return_value = None
        r = svc.get_preference(1, "missing")
        assert r["value"] is None

    def test_save_preference(self, svc):
        r = svc.save_preference(1, "theme", "dark")
        assert r["ok"] is True

    def test_save_preferences_batch(self, svc):
        r = svc.save_preferences_batch(1, {"a": 1, "b": 2})
        assert r["ok"] is True
        assert r["count"] == 2

    def test_save_preferences_batch_empty(self, svc):
        r = svc.save_preferences_batch(1, {})
        assert "error" in r

    def test_delete_preference(self, svc):
        r = svc.delete_preference(1, "theme")
        assert r["ok"] is True

    def test_get_user_settings(self, svc):
        svc._mgr.db.fetchone.return_value = {"layout_data": '{"x":1}'}
        svc._mgr.db.fetchall.return_value = [
            {"preference_key": "k", "preference_value": '"v"'}
        ]
        r = svc.get_user_settings(1)
        assert r["layout"] == '{"x":1}'

    def test_save_user_settings(self, svc):
        r = svc.save_user_settings(1, {"layout": '{"y":2}', "preferences": {"k": "v"}})
        assert r["ok"] is True
