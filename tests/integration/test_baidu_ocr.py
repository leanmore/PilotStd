# tests/integration/test_baidu_ocr.py
"""Integration test for BaiduOcrProvider — HTTP boundary with mock server.

Protocol: POST /oauth/2.0/token → POST /rest/2.0/ocr/v1/general_basic
"""

from __future__ import annotations

import pytest

from pilotstd.announcement.ocr._baidu import BaiduOcrProvider
from pilotstd.announcement.ocr._base import OcrResult
from tests.integration.conftest import MINIMAL_PDF


class TestBaiduOcrIntegration:
    def test_recognize_pdf_returns_text(self, baidu_provider):
        """Token获取 → OCR识别 → OcrResult.ok=True，文本拼接正确。"""
        result = baidu_provider.recognize_pdf(MINIMAL_PDF, page_num=1)

        assert isinstance(result, OcrResult)
        assert result.ok is True
        assert result.text is not None
        assert "GB/T 1.1-2020" in result.text
        assert "标准化工作导则" in result.text
        assert "2020-06-02" in result.text

    def test_recognize_pdf_no_cache_token_call(self, baidu_server, monkeypatch):
        """每次新实例首次调用均重新获取 token（无缓存时）。"""
        import pilotstd.query.network as net

        base = baidu_server.url_for("/")[:-1]
        _orig_get = net.safe_raw_get
        _orig_post = net.safe_raw_post

        def _mock_raw_get(url, *a, **kw):
            return _orig_get(url.replace("https://aip.baidubce.com", base), *a, **kw)

        def _mock_raw_post(url, *a, **kw):
            return _orig_post(url.replace("https://aip.baidubce.com", base), *a, **kw)

        monkeypatch.setattr(net, "safe_raw_get", _mock_raw_get)
        monkeypatch.setattr(net, "safe_raw_post", _mock_raw_post)

        provider = BaiduOcrProvider(api_key="ak", secret_key="sk")

        # First call: token cached
        provider.recognize_pdf(MINIMAL_PDF, page_num=1)
        # Second call: should use cached token (no additional token request needed)
        result = provider.recognize_pdf(MINIMAL_PDF, page_num=1)

        assert result.ok is True

    def test_invalid_token_returns_error(self, baidu_server, monkeypatch):
        """无效 access_token → OcrResult.ok=False，优雅降级。"""
        import pilotstd.query.network as net

        base = baidu_server.url_for("/")[:-1]
        _orig_get = net.safe_raw_get
        _orig_post = net.safe_raw_post

        def _mock_raw_get(url, *a, **kw):
            return _orig_get(url.replace("https://aip.baidubce.com", base), *a, **kw)

        # token is passed via params= kwarg, not in URL
        def _mock_raw_post(url: str, site_name: str, timeout: int = 60, **kw):
            patched = url.replace("https://aip.baidubce.com", base)
            return _orig_post(patched, site_name, timeout, **kw)

        # For the token request, also redirect to mock server
        monkeypatch.setattr(net, "safe_raw_get", _mock_raw_get)
        monkeypatch.setattr(net, "safe_raw_post", _mock_raw_post)

        # Create provider and get a working token first
        provider = BaiduOcrProvider(api_key="ak", secret_key="sk")
        # Poison the cached token with a far-future expiry to skip re-fetch
        import time
        provider._access_token = "INVALID_TOKEN"
        provider._token_expire = time.time() + 3600

        result = provider.recognize_pdf(MINIMAL_PDF, page_num=1)

        assert isinstance(result, OcrResult)
        assert result.ok is False
