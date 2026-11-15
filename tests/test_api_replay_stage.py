"""受控投放端点（M1 #2）的校验/执行/开关测试。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api.replay_stage import router, stage_one, validate_item
from tests._auth_helpers import admin_cookies


def test_validate_rejects_source_outside_roots(tmp_path):
    with pytest.raises(ValueError):
        validate_item("/etc/passwd", "/inbox/__replay_x/a.pdf")


def test_validate_rejects_target_outside_prefix(tmp_path):
    with pytest.raises(ValueError):
        validate_item("/inbox/a.pdf", "/standards/stolen.pdf")
    with pytest.raises(ValueError):
        validate_item("/inbox/a.pdf", "/inbox/other/a.pdf")


def test_validate_rejects_same_path():
    with pytest.raises(ValueError):
        validate_item("/inbox/a.pdf", "/inbox/a.pdf")


def test_stage_one_copy_and_move(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x", encoding="utf-8")
    copied = tmp_path / "b.txt"
    stage_one("copy", str(src), str(copied), True)
    assert copied.exists() and src.exists()
    assert copied.stat().st_mtime >= src.stat().st_mtime - 1

    moved = tmp_path / "c.txt"
    stage_one("move", str(src), str(moved), False)
    assert moved.exists() and not src.exists()


def test_endpoint_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PILOTSTD_ENABLE_REPLAY_STAGE", raising=False)
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app, cookies=admin_cookies())
    r = client.post(
        "/api/admin/replay-stage",
        json={"items": [{"source": "/inbox/a.pdf", "target": "/inbox/__replay_x/a.pdf"}]},
    )
    assert r.status_code == 403
