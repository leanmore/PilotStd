"""OCR 设置/诊断接口：provider 字段与本地 OCR 状态可读。"""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from docker.api import announce
from docker.manager import get_manager_dep


def _client() -> TestClient:
    crawler = MagicMock()
    crawler._ocr_config = {"provider": ""}
    crawler._get_ocr_provider.return_value = None
    mgr = MagicMock()
    mgr._announce_svc.crawler = crawler
    app = FastAPI()
    app.include_router(announce.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    return TestClient(app)


def test_ocr_status_reports_dependency_flags() -> None:
    resp = _client().get("/api/announce/ocr-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["configured_provider"] == ""
    assert isinstance(body["rapidocr"], bool)
    assert isinstance(body["onnxruntime"], bool)


def test_ocr_status_never_raises_when_provider_missing() -> None:
    crawler = MagicMock()
    crawler._ocr_config = {"provider": "local"}
    crawler._get_ocr_provider.return_value = None
    mgr = MagicMock()
    mgr._announce_svc.crawler = crawler
    app = FastAPI()
    app.include_router(announce.router)
    app.dependency_overrides[get_manager_dep] = lambda: mgr
    resp = TestClient(app).get("/api/announce/ocr-status")
    assert resp.status_code == 200
    assert resp.json()["configured_provider"] == "local"
