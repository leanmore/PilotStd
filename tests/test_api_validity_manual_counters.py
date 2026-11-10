"""P1-01：手动 /api/validity/run 必须推进轮次计数（update_counters=True）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.validity import router as validity_router
from docker.manager import get_manager_dep
from tests._auth_helpers import admin_cookies


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(validity_router)
    app.dependency_overrides[get_manager_dep] = lambda: MagicMock()
    return TestClient(app, cookies=admin_cookies())


def test_manual_run_updates_counters(client: TestClient) -> None:
    fake = {"ok": True, "checked": 3, "changed": 1}
    with patch("pilotstd.core.validity_checker.run_validity_check", return_value=fake) as do_check:
        r = client.post("/api/validity/run")

    assert r.status_code == 200
    assert r.json() == {"ok": True, "checked": 3, "changed": 1}
    assert do_check.call_args.kwargs["update_counters"] is True


def test_manual_run_failure_returns_500(client: TestClient) -> None:
    with patch(
        "pilotstd.core.validity_checker.run_validity_check",
        return_value={"ok": False, "checked": 0, "changed": 0, "error": "执行失败"},
    ):
        r = client.post("/api/validity/run")
    assert r.status_code == 500
