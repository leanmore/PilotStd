"""D-13 补测：/api/user/preferences 与废弃 settings 别名（此前函数级零覆盖）。"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from docker.api import user as user_api


def _req() -> SimpleNamespace:
    return SimpleNamespace(client=SimpleNamespace(host="127.0.0.1"))


def test_preferences_crud_delegates() -> None:
    mgr = MagicMock()
    mgr.user_service.get_preferences.return_value = {"theme": "dark"}
    mgr.user_service.get_preference.return_value = "dark"
    mgr.user_service.save_preference.return_value = {"ok": True}
    mgr.user_service.delete_preference.return_value = {"ok": True}

    assert user_api.get_all_preferences(_req(), user_id=1, mgr=mgr) == {"theme": "dark"}
    assert user_api.get_preference("theme", _req(), user_id=1, mgr=mgr) == "dark"
    assert user_api.put_preference("theme", {"value": "dark"}, _req(), user_id=1, mgr=mgr) == {"ok": True}
    assert user_api.delete_preference("theme", _req(), user_id=1, mgr=mgr) == {"ok": True}
    mgr.user_service.save_preference.assert_called_once_with(1, "theme", "dark")


def test_put_preference_requires_value() -> None:
    resp = user_api.put_preference("theme", {}, _req(), user_id=1, mgr=MagicMock())
    assert resp.status_code == 400
    assert "value" in json.loads(resp.body)["error"]


def test_put_preferences_batch_success_and_error() -> None:
    mgr = MagicMock()
    mgr.user_service.save_preferences_batch.return_value = {"ok": True}
    assert user_api.put_preferences_batch({"preferences": {"a": 1}}, _req(), user_id=1, mgr=mgr) == {"ok": True}
    mgr.user_service.save_preferences_batch.assert_called_once_with(1, {"a": 1})

    mgr.user_service.save_preferences_batch.return_value = {"error": "bad"}
    resp = user_api.put_preferences_batch({"preferences": {}}, _req(), user_id=1, mgr=mgr)
    assert resp.status_code == 400


def test_deprecated_settings_endpoints_warn(caplog) -> None:
    mgr = MagicMock()
    mgr.user_service.get_user_settings.return_value = {"a": 1}
    mgr.user_service.save_user_settings.return_value = {"ok": True}

    with caplog.at_level(logging.WARNING, logger="docker.api.user"):
        assert user_api.get_settings(_req(), user_id=1, mgr=mgr) == {"a": 1}
        assert user_api.put_settings({"a": 1}, _req(), user_id=1, mgr=mgr) == {"ok": True}

    assert "DEPRECATED endpoint /api/user/settings" in caplog.text
