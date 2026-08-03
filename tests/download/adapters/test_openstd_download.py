"""openstd_download.py 覆盖率补测 — 异常/重试/边界路径 (85% → 95%+)"""

import builtins
import re
from unittest.mock import MagicMock, patch

import pytest
import requests
from pytest_httpserver import HTTPServer

from pilotstd.download.adapters.openstd_download import OpenstdDownloadAdapter
from pilotstd.download.models import DownloadTask

BASE = OpenstdDownloadAdapter.BASE_URL


# ── 辅助：构造最小 Task ──


def make_task(hcno: str = "TEST123", query_result_hcno: str = "") -> DownloadTask:
    task = DownloadTask(
        standard_number="GB/T 1234-2020",
        source_site="openstd_download",
        extra={"hcno": hcno} if hcno else {},
    )
    if query_result_hcno:
        qr = MagicMock()
        qr.hcno = query_result_hcno
        task.query_result = qr
    return task


# ── Fixtures ──


@pytest.fixture
def server(httpserver: HTTPServer):
    """提供 mock server 实例，每个测试自行配置 expectations"""
    return httpserver


@pytest.fixture
def adapter(server):
    """适配器指向 mock server"""
    session = requests.Session()
    adp = OpenstdDownloadAdapter(session=session)
    adp.BASE_URL = server.url_for("").rstrip("/")
    return adp


def _register_showgb(server: HTTPServer) -> None:
    server.expect_request("/showGb", method="GET").respond_with_data(status=302)


def _register_captcha_and_verify(server: HTTPServer) -> None:
    server.expect_request("/gc", method="GET").respond_with_data(
        b"x89PNGrnx1an", content_type="image/png"
    )
    server.expect_request("/verifyCode", method="POST").respond_with_data("success")


def _register_viewgb_pdf(server: HTTPServer, filename: str = "test.pdf") -> None:
    server.expect_request("/viewGb", method="GET").respond_with_data(
        b"%PDF-1.4\nfake content\n%%EOF",
        content_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ════════════════════════════════════════════════════════════
# T1: hcno 缺失 / 回退
# ════════════════════════════════════════════════════════════


class TestHcnoResolution:
    def test_missing_hcno_returns_none(self, adapter):
        """extra 无 hcno，query_result 也无 → None + error_message"""
        task = DownloadTask(
            standard_number="GB/T 1234-2020",
            source_site="openstd_download",
            extra={},
        )
        result = adapter.download(task)
        assert result is None
        assert "缺少 hcno" in task.error_message

    def test_extra_none_returns_none(self, adapter):
        """extra 为 None → None + error_message"""
        task = DownloadTask(
            standard_number="GB/T 1234-2020",
            source_site="openstd_download",
            extra=None,
        )
        result = adapter.download(task)
        assert result is None
        assert "缺少 hcno" in task.error_message

    def test_hcno_fallback_to_query_result(self, adapter, server):
        """extra 无 hcno，从 query_result.hcno 回退获取 → 正常下载"""
        _register_showgb(server)
        _register_captcha_and_verify(server)
        _register_viewgb_pdf(server)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task(hcno="", query_result_hcno="QR_HCNO_001")
            result = adapter.download(task)
            assert result is not None
            assert result[:4] == b"%PDF"


# ════════════════════════════════════════════════════════════
# T2: showGb 网络异常
# ════════════════════════════════════════════════════════════


class TestShowGbError:
    def test_show_gb_connection_error_returns_none(self, adapter):
        """showGb 网络连接异常 → None + '建立会话失败'"""
        with patch.object(
            adapter._session, "get", side_effect=requests.ConnectionError("mocked")
        ):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "建立会话失败" in task.error_message


# ════════════════════════════════════════════════════════════
# T3: 验证码处理异常
# ════════════════════════════════════════════════════════════


class TestCaptchaFailure:
    def test_ocr_fails_without_callback(self, adapter, server):
        """ddddocr 返回空串，无 callback → 两次重试后识别失败"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value=""):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert "验证码识别失败" in task.error_message

    def test_callback_returns_invalid_then_fail(self, adapter, server):
        """callback 返回长度≠4 → 重试后仍失败"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        adapter._captcha_callback = lambda _: "12"

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value=""):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert "验证码识别失败" in task.error_message

    def test_verify_code_non_success_twice(self, adapter, server):
        """verifyCode 两次返回非 success → 提交失败"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/verifyCode", method="POST").respond_with_data("failure")
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/verifyCode", method="POST").respond_with_data("failure")

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value="ABCD"):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert "验证码提交失败" in task.error_message

    def test_ddddocr_import_error_falls_back_to_callback(self, adapter, server):
        """ddddocr ImportError → 走 callback 兜底 → 验证通过"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/verifyCode", method="POST").respond_with_data("success")

        adapter._captcha_callback = lambda _: "WXYZ"
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "ddddocr":
                raise ImportError("mocked")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert task.error_message == ""

    def test_ddddocr_exception_falls_back_to_callback(self, adapter, server):
        """ddddocr 抛出非 ImportError 异常 → callback 兜底"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/verifyCode", method="POST").respond_with_data("success")

        adapter._captcha_callback = lambda _: "ABCD"
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "ddddocr":
                raise RuntimeError("ocr engine crashed")
            return real_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert task.error_message == ""

    def test_captcha_image_fetch_error(self, adapter, server):
        """验证码图片 GET 失败 → 立即返回 None"""
        with patch.object(
            adapter._session, "get", side_effect=requests.ConnectionError("mocked")
        ):
            task = make_task()
            result = adapter._handle_captcha("TEST123", task)
            assert result is None
            assert "验证码图片获取失败" in task.error_message

    def test_verify_code_request_exception_then_retry(self, adapter, server):
        """verifyCode POST 网络异常 → 第1次重试，第2次也异常 → 返回失败"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value="ABCD"):
            with patch.object(
                adapter._session, "post",
                side_effect=requests.ConnectionError("mocked")
            ):
                task = make_task()
                result = adapter._handle_captcha("TEST123", task)
                assert result is None
                assert "验证码提交失败" in task.error_message

    def test_verify_code_first_exception_second_success(self, adapter, server):
        """verifyCode POST 第1次异常 → 重试 → 第2次成功"""
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/verifyCode", method="POST").respond_with_data("success")

        import ddddocr

        call_count = [0]

        def post_side_effect(url, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.ConnectionError("mocked")
            resp = MagicMock()
            resp.text = "success"
            return resp

        with patch.object(ddddocr.DdddOcr, "classification", return_value="ABCD"):
            with patch.object(adapter._session, "post", side_effect=post_side_effect):
                task = make_task()
                result = adapter._handle_captcha("TEST123", task)
                assert result is None
                assert task.error_message == ""


# ════════════════════════════════════════════════════════════
# T4: viewGb 异常 + Content-Disposition
# ════════════════════════════════════════════════════════════


class TestViewGbErrors:
    def test_view_gb_network_error(self, adapter, server):
        """viewGb 请求异常 → None + 'PDF 下载请求失败'"""
        _register_showgb(server)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            with patch.object(
                adapter._session, "get",
                side_effect=[
                    MagicMock(status_code=302),
                    requests.Timeout("mocked"),
                ]
            ):
                task = make_task()
                result = adapter._do_download("TEST123", task)
                assert result is None
                assert "PDF 下载请求失败" in task.error_message

    def test_view_gb_non_200(self, adapter, server):
        """viewGb HTTP 500 → None"""
        _register_showgb(server)
        server.expect_request("/viewGb", method="GET").respond_with_data(status=500)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "viewGb HTTP 500" in task.error_message

    def test_view_gb_empty_content(self, adapter, server):
        """viewGb 返回空内容 → None"""
        _register_showgb(server)
        server.expect_request("/viewGb", method="GET").respond_with_data("", status=200)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "空内容" in task.error_message

    def test_view_gb_non_pdf_small_html(self, adapter, server):
        """viewGb 返回小体积 HTML（<1000B）→ 非 PDF"""
        _register_showgb(server)
        server.expect_request("/viewGb", method="GET").respond_with_data(
            "<html>error</html>", content_type="text/html", status=200
        )

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "非 PDF" in task.error_message

    def test_view_gb_large_content_with_html(self, adapter, server):
        """viewGb 返回 >1000B 且含 html 前缀 → 非 PDF（覆盖 L151-152）"""
        _register_showgb(server)
        large_html = b"<html>" + b"x" * 1100 + b"</html>"
        server.expect_request("/viewGb", method="GET").respond_with_data(
            large_html, content_type="text/html", status=200
        )

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "非 PDF" in task.error_message

    def test_view_gb_large_binary_no_html_returns_content(self, adapter, server):
        """viewGb 返回 >1000B 且不含 html → 视为有效 PDF（覆盖 L152）"""
        _register_showgb(server)
        binary_data = b"\x00\x01\x02" + b"x" * 1100
        server.expect_request("/viewGb", method="GET").respond_with_data(
            binary_data, content_type="application/octet-stream", status=200
        )

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is not None
            assert result == binary_data

    def test_view_gb_content_disposition_filename(self, adapter, server):
        """viewGb 带 Content-Disposition → extra.filename_from_header 被设置"""
        _register_showgb(server)
        server.expect_request("/viewGb", method="GET").respond_with_data(
            b"%PDF-1.4\ncontent\n%%EOF",
            content_type="application/pdf",
            status=200,
            headers={
                "Content-Disposition": 'attachment; filename="GB_T_1234-2020.pdf"'
            },
        )

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is not None
            assert task.extra["filename_from_header"] == "GB_T_1234-2020.pdf"

    def test_extra_none_gets_initialized_for_filename(self, adapter, server):
        """task.extra 为 None 时，设置 filename 前先初始化为 dict（覆盖 L144）"""
        _register_showgb(server)
        server.expect_request("/viewGb", method="GET").respond_with_data(
            b"%PDF-1.4\ncontent\n%%EOF",
            content_type="application/pdf",
            status=200,
            headers={
                "Content-Disposition": 'attachment; filename="test.pdf"'
            },
        )

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            task.extra = None
            result = adapter._do_download("TEST123", task)
            assert result is not None
            assert task.extra is not None
            assert task.extra["filename_from_header"] == "test.pdf"


# ════════════════════════════════════════════════════════════
# T4b: _do_download 中 captcha 失败 → 提前返回（覆盖 L107）
# ════════════════════════════════════════════════════════════


class TestDoDownloadCaptchaFail:
    def test_captcha_fails_returns_none_from_do_download(self, adapter, server):
        """showGb 成功但 captcha 失败 → _do_download 在 L107 返回 None"""
        _register_showgb(server)
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )
        server.expect_request("/gc", method="GET").respond_with_data(
            b"x89PNG", content_type="image/png"
        )

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value=""):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "验证码识别失败" in task.error_message


# ════════════════════════════════════════════════════════════
# T5: Content-Disposition 解析变体
# ════════════════════════════════════════════════════════════


class TestContentDispositionVariants:
    def _run_with_cd(self, adapter, server, cd_header: str) -> DownloadTask:
        _register_showgb(server)
        headers = {"Content-Disposition": cd_header} if cd_header else {}
        server.expect_request("/viewGb", method="GET").respond_with_data(
            b"%PDF-1.4\ncontent\n%%EOF",
            content_type="application/pdf",
            status=200,
            headers=headers,
        )
        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            adapter._do_download("TEST123", task)
            return task

    def test_filename_single_quoted(self, adapter, server):
        task = self._run_with_cd(adapter, server, "attachment;filename='report.pdf'")
        assert task.extra["filename_from_header"] == "report.pdf"

    def test_filename_unquoted(self, adapter, server):
        task = self._run_with_cd(adapter, server, "attachment;filename=standard.pdf")
        assert task.extra["filename_from_header"] == "standard.pdf"

    def test_filename_with_extra_params(self, adapter, server):
        task = self._run_with_cd(
            adapter, server, 'attachment; filename="doc.pdf"; size=456'
        )
        assert task.extra["filename_from_header"] == "doc.pdf"

    def test_no_filename_in_header(self, adapter, server):
        task = self._run_with_cd(adapter, server, "attachment")
        assert "filename_from_header" not in task.extra

    def test_no_content_disposition_header(self, adapter, server):
        task = self._run_with_cd(adapter, server, "")
        assert "filename_from_header" not in task.extra


# ════════════════════════════════════════════════════════════
# T6: 完整回归
# ════════════════════════════════════════════════════════════


class TestFullDownload:
    def test_full_download_happy_path(self, adapter, server):
        """完整 5 步链路正常通过"""
        _register_showgb(server)
        _register_captcha_and_verify(server)
        _register_viewgb_pdf(server)

        import ddddocr

        with patch.object(ddddocr.DdddOcr, "classification", return_value="WXYZ"):
            task = make_task()
            result = adapter.download(task)
            assert result is not None
            assert result[:4] == b"%PDF"
            assert task.error_message == ""


# ════════════════════════════════════════════════════════════
# T7: can_handle 路由判断
# ════════════════════════════════════════════════════════════


class TestCanHandle:
    @pytest.fixture
    def adapter_no_server(self):
        return OpenstdDownloadAdapter()

    def test_can_handle_matching_site(self, adapter_no_server):
        task = DownloadTask(standard_number="GB/T 1", source_site="openstd_download")
        assert adapter_no_server.can_handle(task) is True

    def test_cannot_handle_different_site(self, adapter_no_server):
        task = DownloadTask(standard_number="GB/T 1", source_site="std_gov")
        assert adapter_no_server.can_handle(task) is False

    def test_cannot_handle_empty_site(self, adapter_no_server):
        task = DownloadTask(standard_number="GB/T 1", source_site="")
        assert adapter_no_server.can_handle(task) is False

    def test_site_name_property(self, adapter_no_server):
        assert adapter_no_server.site_name == "openstd_download"
