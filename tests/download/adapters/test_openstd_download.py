"""openstd_download.py 覆盖率补测 — 异常/重试/边界路径 (85% → 95%+)"""

import builtins
from unittest.mock import MagicMock, patch

import pytest
import requests
from pytest_httpserver import HTTPServer

from pilotstd.download.adapters.openstd_download import (
    OpenstdDownloadAdapter,
    parse_hcno_from_search_page,
)
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


def _register_detail(server: HTTPServer, standard_number: str = "GB/T 1234-2020") -> None:
    """详情页（新路径 /newGbInfo）：含标准号，避免触发 hcno 有效性告警。"""
    server.expect_request("/newGbInfo", method="GET").respond_with_data(
        f"<html><title>{standard_number}</title></html>", content_type="text/html; charset=utf-8"
    )


def _register_search(
    server: HTTPServer, hcno: str, standard_number: str = "GB/T 1234-2020", extra_rows: str = ""
) -> None:
    """openstd 搜索页：行内 showInfo(hcno) 与标准号配对（适配器的 hcno 权威来源）。"""
    rows = f"""<a href="javascript:void(0)" onclick="showInfo('{hcno}');">{standard_number}</a>""" + extra_rows
    server.expect_request("/std_list_type", method="GET").respond_with_data(
        f"<html><table>{rows}</table></html>", content_type="text/html; charset=utf-8"
    )


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
        assert "无法获取下载标识(hcno)" in task.error_message

    def test_extra_none_returns_none(self, adapter):
        """extra 为 None → None + error_message"""
        task = DownloadTask(
            standard_number="GB/T 1234-2020",
            source_site="openstd_download",
            extra=None,
        )
        result = adapter.download(task)
        assert result is None
        assert "无法获取下载标识(hcno)" in task.error_message

    def test_hcno_resolved_from_openstd_search_page(self, adapter, server):
        """extra 无 hcno → 从 openstd 搜索页按标准号解析 hcno，并用它下载。"""
        _register_search(server, "4D1FD002A12678A75A4B7C42C1DE87EE", "GB/T 1234-2020")
        _register_detail(server)
        _register_captcha_and_verify(server)
        _register_viewgb_pdf(server)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task(hcno="")
            result = adapter.download(task)

        assert result is not None and result[:4] == b"%PDF"
        view_calls = [req for req, _ in server.log if "/viewGb" in req.path]
        assert view_calls, "必须请求 /viewGb"
        assert view_calls[-1].args.get("hcno") == "4D1FD002A12678A75A4B7C42C1DE87EE", "必须用搜索页解析出的 hcno"

    def test_query_result_pid_is_not_used_as_hcno(self, adapter, server):
        """防回归：std_gov 的 pid（query_result.hcno）绝不能被当 hcno 用。

        2026-09 事故：pid 在 openstd 侧不被识别（newGbInfo 对 pid/篡改/空返回同一页面），
        旧实现回退 pid 后失败被推迟到验证码阶段、伪装成"验证码问题"（生产 15/15 error）。
        """
        _register_search(server, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "OTHER-STD-2020")  # 搜索页无目标标准号
        task = make_task(hcno="", query_result_hcno="PID_FROM_STD_GOV")

        with patch.object(adapter, "_handle_captcha") as captcha:
            result = adapter.download(task)

        assert result is None
        assert "无法获取下载标识(hcno)" in task.error_message
        assert not captcha.called, "解析不到 hcno 时不得进入验证码阶段"
        assert not [req for req, _ in server.log if "/viewGb" in req.path], "不得用 pid 去下载"

    def test_search_row_number_must_match(self, adapter, server):
        """防回归：搜索页返回其它标准时不得取首条（否则会把别的标准全文当成本条下载）。"""
        _register_search(server, "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", "GB 2024-2016")
        task = make_task(hcno="")

        with patch.object(adapter, "_handle_captcha") as captcha:
            assert adapter.download(task) is None
        assert not captcha.called


# ════════════════════════════════════════════════════════════
# T2: showGb 网络异常
# ════════════════════════════════════════════════════════════


class TestShowGbError:
    def test_detail_page_connection_error_is_not_fatal(self, adapter, server):
        """详情页预访问失败不致命：仍应继续验证码 + viewGb（实测最小序列不需要详情页）。"""
        _register_captcha_and_verify(server)
        _register_viewgb_pdf(server)
        real_get = adapter._session.get

        def flaky_get(url, *args, **kwargs):
            """只让详情页请求失败，其余请求走真实 mock server。"""
            if "/newGbInfo" in url:
                raise requests.ConnectionError("mocked")
            return real_get(url, *args, **kwargs)

        adapter._session.get = flaky_get  # type: ignore[method-assign]
        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
        assert result is not None and result[:4] == b"%PDF"


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
        """viewGb 网络异常（两轮都失败）→ None + 'PDF 下载请求失败'"""
        _register_detail(server)
        real_get = adapter._session.get

        def flaky_get(url, *args, **kwargs):
            if "/viewGb" in url:
                raise requests.Timeout("mocked")
            return real_get(url, *args, **kwargs)

        adapter._session.get = flaky_get  # type: ignore[method-assign]
        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)

        assert result is None
        assert "PDF 下载请求失败" in task.error_message

    def test_view_gb_empty_first_round_then_pdf(self, adapter, server):
        """viewGb 首轮空内容 → 自动重开下载页重试并成功（站点授权偶发未落地）。"""
        _register_detail(server)
        server.expect_request("/viewGb", method="GET").respond_with_data("", status=200)
        real_get = adapter._session.get
        state = {"n": 0}

        def flaky_get(url, *args, **kwargs):
            if "/viewGb" in url:
                state["n"] += 1
                if state["n"] == 1:
                    return real_get(url, *args, **kwargs)  # 第一次：mock 返回空
                resp = requests.Response()
                resp.status_code = 200
                resp._content = b"%PDF-1.4\nfake content\n%%EOF"
                resp.headers["Content-Type"] = "application/pdf"
                resp.headers["Content-Disposition"] = 'attachment; filename="retry.pdf"'
                return resp
            return real_get(url, *args, **kwargs)

        adapter._session.get = flaky_get  # type: ignore[method-assign]
        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)

        assert result is not None and result[:4] == b"%PDF"
        assert state["n"] == 2, "首轮空内容后必须重试一次"
        assert (task.extra or {}).get("filename_from_header") == "retry.pdf"

    def test_view_gb_non_200(self, adapter, server):
        """viewGb HTTP 500 → None"""
        _register_detail(server)
        server.expect_request("/viewGb", method="GET").respond_with_data(status=500)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "viewGb HTTP 500" in task.error_message

    def test_view_gb_empty_content(self, adapter, server):
        """viewGb 返回空内容 → None"""
        _register_detail(server)
        server.expect_request("/viewGb", method="GET").respond_with_data("", status=200)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            task = make_task()
            result = adapter._do_download("TEST123", task)
            assert result is None
            assert "空内容" in task.error_message

    def test_view_gb_non_pdf_small_html(self, adapter, server):
        """viewGb 返回小体积 HTML（<1000B）→ 非 PDF"""
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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
        _register_detail(server)
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

# ════════════════════════════════════════════════════════════
# T9: 端点路径守卫（防回归）
# ════════════════════════════════════════════════════════════


class TestEndpointPathGuard:
    """openstd 2026-09 把下载端点从 /bzgk/gb/* 迁到 /bzgk/std/*。

    旧路径下 GET 是 301（requests 自动跟随，看不出问题），但 POST 遇 301 会被降级为
    GET、表单体丢失 → verifyCode 恒 error（生产 15/15 失败的根因之一）。
    这里把"必须用 /bzgk/std"钉成断言，避免下次又改回旧路径。
    """

    def test_base_url_is_std_namespace(self):
        assert OpenstdDownloadAdapter.BASE_URL.endswith("/bzgk/std"), (
            "下载端点必须走 /bzgk/std（旧 /bzgk/gb 会 301，POST 体丢失导致 verifyCode 恒 error）"
        )

    def test_search_url_shares_base_namespace(self, adapter):
        assert adapter.search_url == f"{adapter.BASE_URL}/std_list_type", (
            "hcno 搜索页必须与 BASE_URL 同源（站点路径迁移时只改一处）"
        )

    def test_all_requests_use_std_paths(self, adapter, server):
        """全流程请求路径都必须落在 mock server 的 /gc、/verifyCode、/viewGb、/newGbInfo 上。"""
        _register_search(server, "4D1FD002A12678A75A4B7C42C1DE87EE", "GB/T 1234-2020")
        _register_detail(server)
        _register_captcha_and_verify(server)
        _register_viewgb_pdf(server)

        with patch.object(adapter, "_handle_captcha", return_value=None):
            adapter.download(make_task(hcno=""))

        paths = [req.path for req, _ in server.log]
        assert paths, "必须发生请求"
        assert not [p for p in paths if p.startswith("/bzgk")], "不应出现硬编码站点路径"

# ════════════════════════════════════════════════════════════
# T10: hcno 解析器（多点匹配 / 无匹配 / 归一化）
# ════════════════════════════════════════════════════════════


def _row(hcno: str, label: str) -> str:
    """按 openstd 搜索页真实结构生成一行结果。"""
    return f'<a href="javascript:void(0)" onclick="showInfo(\'{hcno}\');">{label}</a>'


class TestHcnoParser:
    """搜索页解析必须"按标准号精确匹配"，任何情况下都不得退化为"取首条"。"""

    def test_picks_matching_row_not_first(self):
        """目标在第二行时必须返回第二行的 hcno（真实事故：首条是别的标准）。"""
        html = _row("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "GB 2024-2016") + _row(
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB", "GB/T 5310-2008"
        )
        assert (
            parse_hcno_from_search_page(html, "GB/T 5310-2008")
            == "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        )
        # 反向也成立：搜第一条时给第一条
        assert (
            parse_hcno_from_search_page(html, "GB 2024-2016")
            == "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        )

    def test_no_match_returns_empty_not_first(self):
        """无匹配必须返回空串（不能退化成首条）。"""
        html = _row("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "GB 2024-2016")
        assert parse_hcno_from_search_page(html, "GB/T 5310-2008") == ""

    def test_empty_target_returns_empty(self):
        html = _row("AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "GB 2024-2016")
        assert parse_hcno_from_search_page(html, "") == ""
        assert parse_hcno_from_search_page(html, "   ") == ""

    def test_normalization_case_and_spacing(self):
        """输入/页面写法差异（大小写、空格、全角空格、破折号、全角斜杠）都要能对上。"""
        html = _row("CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC", "GB/T  150.1—2024")
        for query in (
            "GB/T 150.1-2024",
            "gb/t150.1-2024",
            "GB／T 150.1—2024",
            "GB/T\u3000150.1-2024",
        ):
            assert (
                parse_hcno_from_search_page(html, query) == "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
            ), f"归一化失败: {query!r}"

    def test_ignores_rows_without_matchable_number(self):
        """页面里夹杂"查看详细"等非标准号锚点时不误伤。"""
        html = (
            _row("DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD", "查看详细")
            + _row("EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE", "GB/T 7597-2026")
        )
        assert (
            parse_hcno_from_search_page(html, "GB/T 7597-2026")
            == "EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
        )

    def test_short_or_non_hex_ids_ignored(self):
        """hcno 必须是 16-40 位十六进制；占位/脏数据不得被当成 hcno。"""
        html = _row("NOT_A_HCNO", "GB/T 1234-2020") + _row(
            "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF", "GB/T 1234-2020"
        )
        assert (
            parse_hcno_from_search_page(html, "GB/T 1234-2020")
            == "FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
        )
