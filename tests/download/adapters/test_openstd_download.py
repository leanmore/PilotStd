"""openstd_download.py 核心分支测试 — T1/T2/T3 优先覆盖。"""
from __future__ import annotations

import builtins
import re
import sys
from unittest.mock import MagicMock, patch

import pytest
import responses

from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
from pilotstd.download.models import DownloadTask

BASE = OpenstdDownloadAdapter.BASE_URL


@pytest.fixture
def adapter():
    return OpenstdDownloadAdapter()


@pytest.fixture
def base_task() -> DownloadTask:
    return DownloadTask(
        standard_number="GB/T 12345-2026",
        source_site="openstd_download",
        extra={"hcno": "TEST_HCNO_001"},
    )


# ════════════════════════════════════════════════════════════════
# 辅助：注入 mock ddddocr 到 sys.modules，使函数内 import ddddocr 获取 mock
# ════════════════════════════════════════════════════════════════

def _inject_mock_ocr(captcha_text: str = "ABCD"):
    """注入 mock ddddocr 模块，返回 mock_ocr 实例。"""
    mock_ocr = MagicMock()
    mock_ocr.classification.return_value = captcha_text
    mock_mod = MagicMock()
    mock_mod.DdddOcr.return_value = mock_ocr
    sys.modules["ddddocr"] = mock_mod
    return mock_ocr


@pytest.fixture(autouse=True)
def _cleanup_ddddocr():
    """每个测试后清理 sys.modules 中的 mock。"""
    yield
    sys.modules.pop("ddddocr", None)


# ════════════════════════════════════════════════════════════════
# T1: download() hcno 缺失 — 防御性入口校验
# ════════════════════════════════════════════════════════════════

class TestDownloadMissingHcno:
    def test_extra_empty_and_no_query_result(self, adapter: OpenstdDownloadAdapter):
        task = DownloadTask(
            standard_number="GB/T 99999-2026",
            source_site="openstd_download",
            extra={},
        )
        result = adapter.download(task)
        assert result is None
        assert "缺少 hcno" in task.error_message

    def test_extra_none_and_no_query_result(self, adapter: OpenstdDownloadAdapter):
        task = DownloadTask(
            standard_number="GB/T 99999-2026",
            source_site="openstd_download",
            extra=None,
        )
        result = adapter.download(task)
        assert result is None
        assert "缺少 hcno" in task.error_message

    def test_hcno_from_query_result_fallback(self, adapter: OpenstdDownloadAdapter):
        """extra 无 hcno 时从 query_result.hcno 回退获取。"""

        class FakeQueryResult:
            hcno = "FALLBACK_HCNO"

        task = DownloadTask(
            standard_number="GB/T 88888-2026",
            source_site="openstd_download",
            extra={},
            query_result=FakeQueryResult(),
        )

        # 直接 mock _do_download 验证 hcno 被正确提取
        with patch.object(adapter, "_do_download") as mock_do:
            adapter.download(task)
            mock_do.assert_called_once()
            hcno_arg = mock_do.call_args[0][0]
            assert hcno_arg == "FALLBACK_HCNO"


# ════════════════════════════════════════════════════════════════
# T2: _do_download showGb 网络异常
# ════════════════════════════════════════════════════════════════

class TestDoDownloadShowGbFailure:
    @responses.activate
    def test_show_gb_timeout(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        # 不注册 showGb URL → responses 自动对未匹配请求抛 ConnectionError
        result = adapter.download(base_task)

        assert result is None
        assert "建立会话失败" in base_task.error_message

    @responses.activate
    def test_show_gb_connection_error(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        # 不注册任何 URL → showGb 直接失败
        result = adapter.download(base_task)

        assert result is None
        assert "建立会话失败" in base_task.error_message


# ════════════════════════════════════════════════════════════════
# T3: _do_download viewGb 返回非 PDF 内容
# ════════════════════════════════════════════════════════════════

def _register_showgb_and_captcha():
    """向 responses 注册 showGb 200 + 验证码 mock。"""
    responses.add(
        responses.GET,
        f"{BASE}/showGb?type=download&hcno=TEST_HCNO_001&request_locale=zh",
        status=200,
    )
    responses.add(
        responses.GET,
        re.compile(rf"{re.escape(BASE)}/gc\?"),
        status=200,
        body=b"fake-captcha-png",
    )
    responses.add(
        responses.POST,
        f"{BASE}/verifyCode",
        status=200,
        body="success",
    )


class TestDoDownloadNonPdfContent:
    @responses.activate
    def test_view_gb_returns_html_error_page(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        _inject_mock_ocr("ABCD")
        _register_showgb_and_captcha()
        responses.add(
            responses.GET,
            f"{BASE}/viewGb?hcno=TEST_HCNO_001",
            status=200,
            body=b"<html><body>Access Denied</body></html>",
        )

        result = adapter.download(base_task)

        assert result is None
        assert "非 PDF" in base_task.error_message

    @responses.activate
    def test_view_gb_returns_empty_content(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        _inject_mock_ocr("ABCD")
        _register_showgb_and_captcha()
        responses.add(
            responses.GET,
            f"{BASE}/viewGb?hcno=TEST_HCNO_001",
            status=200,
            body=b"",
        )

        result = adapter.download(base_task)

        assert result is None
        assert "空内容" in base_task.error_message

    @responses.activate
    def test_view_gb_http_403(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        _inject_mock_ocr("ABCD")
        _register_showgb_and_captcha()
        responses.add(
            responses.GET,
            f"{BASE}/viewGb?hcno=TEST_HCNO_001",
            status=403,
        )

        result = adapter.download(base_task)

        assert result is None
        assert "HTTP 403" in base_task.error_message


# ════════════════════════════════════════════════════════════════
# T4-T6: _handle_captcha 验证码重试与兜底逻辑
# ════════════════════════════════════════════════════════════════

class TestHandleCaptcha:
    """验证码识别、重试、callback 兜底的完整分支覆盖。"""

    def _mock_show_gb(self, rsps: responses.RequestsMock) -> None:
        rsps.add(
            responses.GET,
            f"{BASE}/showGb?type=download&hcno=TEST_HCNO_001&request_locale=zh",
            status=200,
        )

    def _mock_view_gb_pdf(self, rsps: responses.RequestsMock) -> None:
        rsps.add(
            responses.GET,
            f"{BASE}/viewGb?hcno=TEST_HCNO_001",
            status=200,
            body=b"%PDF-1.4 fake pdf content for captcha test",
            headers={"Content-Disposition": 'attachment;filename="captcha_test.pdf"'},
        )

    # ── T4: ddddocr ImportError → callback 兜底成功 ──

    @responses.activate
    def test_ddddocr_import_error_callback_fallback(
        self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask
    ):
        """ddddocr 未安装时，captcha_callback 能正确兜底并完成下载。"""
        self._mock_show_gb(responses)
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png",
        )
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="success",
        )
        self._mock_view_gb_pdf(responses)

        callback = lambda img_bytes: "XKCD"
        adapter._captcha_callback = callback

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "ddddocr":
                raise ImportError("No module named 'ddddocr'")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = adapter.download(base_task)

        assert result is not None
        assert result.startswith(b"%PDF-")
        verify_calls = [c for c in responses.calls if "verifyCode" in c.request.url]
        assert len(verify_calls) == 1

    # ── T5: verifyCode 第1次拒绝 → 刷新验证码 → 第2次成功 ──

    @responses.activate
    def test_captcha_retry_second_attempt_success(
        self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask
    ):
        """OCR 正确但服务端第1次拒绝 verifyCode，刷新后第2次成功。"""
        self._mock_show_gb(responses)
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png",
        )
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png-2",
        )
        # 第1次 verifyCode 拒绝，第2次通过
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="fail",
        )
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="success",
        )
        self._mock_view_gb_pdf(responses)

        _inject_mock_ocr("ABCD")

        result = adapter.download(base_task)

        assert result is not None
        assert result.startswith(b"%PDF-")
        gc_calls = [c for c in responses.calls if "/gc?" in c.request.url]
        verify_calls = [c for c in responses.calls if "verifyCode" in c.request.url]
        assert len(gc_calls) == 2
        assert len(verify_calls) == 2

    # ── T6-a: OCR 连续无效 → 不触发 verifyCode ──

    @responses.activate
    def test_captcha_both_attempts_fail(
        self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask
    ):
        """OCR 两次都返回无效结果（非4位），重试耗尽后终止。"""
        self._mock_show_gb(responses)
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png",
        )
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png-2",
        )
        # 不需要 mock verifyCode — OCR 两次都无效，不会走到提交步骤

        mock_ocr = MagicMock()
        mock_ocr.classification.side_effect = ["AB", "XY"]
        mock_mod = MagicMock()
        mock_mod.DdddOcr.return_value = mock_ocr
        sys.modules["ddddocr"] = mock_mod

        try:
            result = adapter.download(base_task)
        finally:
            sys.modules.pop("ddddocr", None)

        assert result is None
        assert "验证码识别失败" in base_task.error_message
        gc_calls = [c for c in responses.calls if "/gc?" in c.request.url]
        verify_calls = [c for c in responses.calls if "verifyCode" in c.request.url]
        assert len(gc_calls) == 2
        assert len(verify_calls) == 0

    # ── T6-b: verifyCode 两次都返回非 success ──

    @responses.activate
    def test_verify_code_both_attempts_fail(
        self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask
    ):
        """OCR 正确但服务端两次拒绝 verifyCode → 重试耗尽。"""
        self._mock_show_gb(responses)
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png",
        )
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"fake-captcha-png-2",
        )
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="fail",
        )
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="fail",
        )

        _inject_mock_ocr("ABCD")

        result = adapter.download(base_task)

        assert result is None
        assert "验证码提交失败" in base_task.error_message
        verify_calls = [c for c in responses.calls if "verifyCode" in c.request.url]
        assert len(verify_calls) == 2


# ════════════════════════════════════════════════════════════════
# T8: Content-Disposition filename 解析
# ════════════════════════════════════════════════════════════════

class TestContentDispositionParsing:
    def _run_full_download(self, adapter: OpenstdDownloadAdapter, task: DownloadTask, cd_header: str):
        with responses.RequestsMock() as rsps:
            rsps.add(
                responses.GET,
                f"{BASE}/showGb?type=download&hcno=TEST_HCNO_001&request_locale=zh",
                status=200,
            )
            rsps.add(
                responses.GET,
                re.compile(rf"{re.escape(BASE)}/gc\?"),
                status=200,
                body=b"fake-captcha-png",
            )
            rsps.add(
                responses.POST,
                f"{BASE}/verifyCode",
                status=200,
                body="success",
            )
            rsps.add(
                responses.GET,
                f"{BASE}/viewGb?hcno=TEST_HCNO_001",
                status=200,
                body=b"%PDF-1.4 fake pdf",
                headers={"Content-Disposition": cd_header} if cd_header else {},
            )
            _inject_mock_ocr("ABCD")
            return adapter.download(task)

    def test_filename_double_quoted(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, 'attachment;filename="GB_T_12345-2026.pdf"')
        assert result is not None
        assert base_task.extra["filename_from_header"] == "GB_T_12345-2026.pdf"

    def test_filename_single_quoted(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, "attachment;filename='report.pdf'")
        assert result is not None
        assert base_task.extra["filename_from_header"] == "report.pdf"

    def test_filename_unquoted(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, "attachment;filename=standard.pdf")
        assert result is not None
        assert base_task.extra["filename_from_header"] == "standard.pdf"

    def test_filename_with_extra_params(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, 'attachment; filename="doc.pdf"; size=456')
        assert result is not None
        assert base_task.extra["filename_from_header"] == "doc.pdf"

    def test_no_filename_in_header(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, "attachment")
        assert result is not None
        assert "filename_from_header" not in base_task.extra

    def test_no_content_disposition_header(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        result = self._run_full_download(adapter, base_task, "")
        assert result is not None
        assert "filename_from_header" not in base_task.extra


# ════════════════════════════════════════════════════════════════
# Happy Path: 5 步完整链路成功
# ════════════════════════════════════════════════════════════════

class TestHappyPath:
    @responses.activate
    def test_full_5_step_download_success(self, adapter: OpenstdDownloadAdapter, base_task: DownloadTask):
        pdf_content = b"%PDF-1.7 complete standard document content here"

        responses.add(
            responses.GET,
            f"{BASE}/showGb?type=download&hcno=TEST_HCNO_001&request_locale=zh",
            status=200,
        )
        responses.add(
            responses.GET,
            re.compile(rf"{re.escape(BASE)}/gc\?"),
            status=200,
            body=b"captcha-image-data",
        )
        responses.add(
            responses.POST,
            f"{BASE}/verifyCode",
            status=200,
            body="success",
        )
        responses.add(
            responses.GET,
            f"{BASE}/viewGb?hcno=TEST_HCNO_001",
            status=200,
            body=pdf_content,
            headers={"Content-Disposition": 'attachment;filename="GB_T_12345-2026.pdf"'},
        )

        _inject_mock_ocr("WXYZ")

        result = adapter.download(base_task)

        assert result == pdf_content
        assert base_task.error_message == ""
        assert base_task.extra["filename_from_header"] == "GB_T_12345-2026.pdf"

        # 验证请求顺序（5 步严格按序）
        assert len(responses.calls) == 4  # showGb, gc, verifyCode, viewGb
        assert "showGb" in responses.calls[0].request.url
        assert "/gc?" in responses.calls[1].request.url
        assert "verifyCode" in responses.calls[2].request.url
        assert "viewGb" in responses.calls[3].request.url
        assert responses.calls[2].request.body == "verifyCode=WXYZ"


# ════════════════════════════════════════════════════════════════
# can_handle 路由判断
# ════════════════════════════════════════════════════════════════

class TestCanHandle:
    def test_can_handle_matching_site(self, adapter: OpenstdDownloadAdapter):
        task = DownloadTask(standard_number="GB/T 1", source_site="openstd_download")
        assert adapter.can_handle(task) is True

    def test_cannot_handle_different_site(self, adapter: OpenstdDownloadAdapter):
        task = DownloadTask(standard_number="GB/T 1", source_site="std_gov")
        assert adapter.can_handle(task) is False

    def test_cannot_handle_empty_site(self, adapter: OpenstdDownloadAdapter):
        task = DownloadTask(standard_number="GB/T 1", source_site="")
        assert adapter.can_handle(task) is False
