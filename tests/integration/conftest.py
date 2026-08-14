# tests/integration/conftest.py
"""Integration test fixtures — pytest-httpserver + monkeypatch for external APIs."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pytest_httpserver import HTTPServer
from werkzeug.wrappers import Response as WerkzeugResponse

# ═══════════════════════════════════════════════════════════════
# Baidu OCR fixtures — mock aip.baidubce.com
# ═══════════════════════════════════════════════════════════════

MOCK_ACCESS_TOKEN = "mock_baidu_access_token_2026"
MOCK_OCR_WORDS = [
    {"words": "标准编号：GB/T 1.1-2020"},
    {"words": "标准名称：标准化工作导则"},
    {"words": "发布日期：2020-06-02"},
]

MINIMAL_PDF = b"%PDF-1.4\nfake pdf for ocr test\n%%EOF"


@pytest.fixture
def baidu_server(httpserver: HTTPServer):
    """Mock Baidu API: /oauth/2.0/token + /rest/2.0/ocr/v1/general_basic."""

    def _handle_token(request):
        if request.args.get("grant_type") != "client_credentials":
            return WerkzeugResponse(
                response=b'{"error":"invalid_grant"}',
                status=400,
                content_type="application/json",
            )
        return WerkzeugResponse(
            response=json.dumps({
                "access_token": MOCK_ACCESS_TOKEN,
                "expires_in": 86400,
            }).encode(),
            status=200,
            content_type="application/json",
        )

    def _handle_ocr(request):
        if request.args.get("access_token") != MOCK_ACCESS_TOKEN:
            return WerkzeugResponse(
                response=b'{"error_code":110,"error_msg":"Access token invalid"}',
                status=401,
                content_type="application/json",
            )
        return WerkzeugResponse(
            response=json.dumps({
                "words_result": MOCK_OCR_WORDS,
                "words_result_num": len(MOCK_OCR_WORDS),
            }).encode(),
            status=200,
            content_type="application/json",
        )

    httpserver.expect_request("/oauth/2.0/token").respond_with_handler(_handle_token)
    httpserver.expect_request("/rest/2.0/ocr/v1/general_basic").respond_with_handler(_handle_ocr)

    yield httpserver


@pytest.fixture
def baidu_provider(baidu_server: HTTPServer, monkeypatch):
    """BaiduOcrProvider with safe_raw_get/safe_raw_post redirected to mock server."""
    import pilotstd.query.network as net

    base = baidu_server.url_for("/")[:-1]  # strip trailing /
    _orig_get = net.safe_raw_get
    _orig_post = net.safe_raw_post

    def _mock_raw_get(url: str, site_name: str, timeout: int = 15, **kw: Any):
        return _orig_get(url.replace("https://aip.baidubce.com", base), site_name, timeout, **kw)

    def _mock_raw_post(url: str, site_name: str, timeout: int = 60, **kw: Any):
        return _orig_post(url.replace("https://aip.baidubce.com", base), site_name, timeout, **kw)

    monkeypatch.setattr(net, "safe_raw_get", _mock_raw_get)
    monkeypatch.setattr(net, "safe_raw_post", _mock_raw_post)

    from pilotstd.announcement.ocr._baidu import BaiduOcrProvider

    return BaiduOcrProvider(api_key="test_ak", secret_key="test_sk")
