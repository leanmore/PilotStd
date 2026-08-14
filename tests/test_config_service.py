"""core/config/service.py 补测。"""
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.core.config.service import ConfigService


@pytest.fixture(autouse=True)
def _reset_singleton():
    ConfigService._instance = None


class TestConfigService:
    def test_singleton(self):
        assert ConfigService.get_instance() is ConfigService.get_instance()

    def test_get_system(self):
        svc = ConfigService(MagicMock())
        svc._cfg.get.return_value = "val"
        assert svc.get_system("key") == "val"

    def test_get_system_default(self):
        svc = ConfigService(MagicMock())
        svc._cfg.get = lambda k, d=None: d
        assert svc.get_system("missing", "fb") == "fb"

    def test_set_user_pref_reserved_blocked(self):
        svc = ConfigService(MagicMock())
        with patch("pilotstd.core.config.service.get_current_user_id", return_value=1):
            with pytest.raises(ValueError, match="reserved prefix"):
                svc.set_user_pref("system.x", "v")

    def test_set_user_pref_allowed(self):
        svc = ConfigService(MagicMock())
        mock_db = MagicMock()
        with patch.object(svc, "_get_db", return_value=mock_db):
            with patch("pilotstd.core.config.service.get_current_user_id", return_value=1):
                svc.set_user_pref("theme", "dark")
                mock_db.execute.assert_called_once()

    def test_get_user_pref_cache_hit(self):
        svc = ConfigService(MagicMock())
        svc._pref_cache["user_pref:1:k"] = '"cached"'
        with patch("pilotstd.core.config.service.get_current_user_id", return_value=1):
            assert svc.get_user_pref("k", user_id=1) == "cached"

    def test_get_user_pref_db_fallback(self):
        svc = ConfigService(MagicMock())
        mock_db = MagicMock()
        mock_db.fetchone.return_value = {"preference_value": '"db_val"'}
        with patch.object(svc, "_get_db", return_value=mock_db):
            with patch("pilotstd.core.config.service.get_current_user_id", return_value=1):
                assert svc.get_user_pref("k", user_id=1) == "db_val"

    def test_invalidate_user_cache(self):
        svc = ConfigService(MagicMock())
        svc._pref_cache["user_pref:1:a"] = "v"
        svc.invalidate_user_cache(1)
        assert "user_pref:1:a" not in svc._pref_cache

    def test_invalidate_all_cache(self):
        svc = ConfigService(MagicMock())
        svc._pref_cache["user_pref:1:x"] = "a"
        svc._pref_cache["user_pref:2:y"] = "b"
        svc.invalidate_user_cache(None)
        assert len(svc._pref_cache) == 0
