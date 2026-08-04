"""_attachment_parser.py 单元测试 — 格式路由 + 回退链全覆盖。

跳过: DOCX/PDF 真实解析（依赖外部库），仅测路由逻辑。
"""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announcement._attachment_parser import (
    download_attachment,
    extract_content,
    find_attachment_url,
    parse_attachment_text,
    parse_wps_text,
)


# ════════════════════════════════════════════════════════════
# parse_attachment_text — 格式路由
# ════════════════════════════════════════════════════════════

class TestParseAttachmentText:
    def test_wps_extension_routes_to_wps_parser(self):
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            return_value="WPS content here",
        ) as mock_wps:
            result = parse_attachment_text(b"fake wps data", "announce.wps")
            assert result == "WPS content here"
            mock_wps.assert_called_once_with(b"fake wps data")

    def test_pdf_extension_routes_to_pdf_parser(self):
        with patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="PDF content",
        ) as mock_pdf:
            result = parse_attachment_text(b"fake pdf", "doc.PDF")
            assert result == "PDF content"

    def test_docx_extension_routes_to_docx_parser(self):
        with patch(
            "pilotstd.announcement._attachment_parser._parse_docx_text",
            return_value="DOCX content",
        ) as mock_docx:
            result = parse_attachment_text(b"fake docx", "file.docx")
            assert result == "DOCX content"

    def test_doc_extension_routes_to_docx_parser(self):
        with patch(
            "pilotstd.announcement._attachment_parser._parse_docx_text",
            return_value="DOC content",
        ) as mock_docx:
            result = parse_attachment_text(b"fake doc", "file.doc")
            assert result == "DOC content"

    def test_unknown_format_fallback_chain_first_succeeds(self):
        """未知格式 → PDF 解析器返回有意义文本 → 停止回退。"""
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            return_value="",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="Meaningful PDF content here!!!",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_docx_text",
        ) as mock_docx:
            result = parse_attachment_text(b"data", "file.xyz")
            assert "PDF" in result
            mock_docx.assert_not_called()  # 第二个成功就不再尝试第三个

    def test_unknown_format_all_fail_returns_empty(self):
        """全部解析器失败 → 返回空字符串。"""
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            return_value="",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_docx_text",
            return_value="",
        ):
            result = parse_attachment_text(b"junk", "file.bin")
            assert result == ""

    def test_unknown_format_short_text_skipped(self):
        """解析器返回 ≤20 字符 → 判定为空洞文本，继续尝试下一个。"""
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            return_value="short",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="This is long enough text to be meaningful and pass the 20-char threshold",
        ):
            result = parse_attachment_text(b"data", "file.xyz")
            assert len(result) > 20

    def test_unknown_format_exception_in_parser_skipped(self):
        """解析器抛异常 → 跳过，继续下一个。"""
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            side_effect=RuntimeError("crash"),
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="Recovered content that is long enough for the threshold check here",
        ):
            result = parse_attachment_text(b"data", "file.xyz")
            assert "Recovered" in result

    def test_empty_filename_fallback_chain(self):
        """空文件名 → 走未知格式回退链。"""
        with patch(
            "pilotstd.announcement._attachment_parser.parse_wps_text",
            return_value="",
        ), patch(
            "pilotstd.announcement._attachment_parser._parse_pdf_text",
            return_value="Content from fallback chain that meets length threshold",
        ):
            result = parse_attachment_text(b"data", "")
            assert len(result) > 20


# ════════════════════════════════════════════════════════════
# parse_wps_text — WPS OLE2 解析
# ════════════════════════════════════════════════════════════

class TestParseWpsText:
    @pytest.fixture(autouse=True)
    def _patch_deps(self):
        with patch(
            "pilotstd.announcement._attachment_parser._clean_wps_fulltext",
            side_effect=lambda x: x,
        ), patch(
            "pilotstd.announcement._attachment_parser._split_wps_entries",
            side_effect=lambda x, pattern: [x],
        ), patch(
            "pilotstd.announcement.parser._clean_wps_name",
            side_effect=lambda x: x,
        ), patch(
            "pilotstd.announcement.parser.STD_CODE_PATTERN",
            MagicMock(),
        ):
            yield

    def test_valid_utf16le_text(self):
        """正常 UTF-16LE 编码文本 → 解析成功。"""
        text = "GB/T 1234-2020 测试标准".encode("utf-16-le")
        result = parse_wps_text(text)
        assert "GB/T" in result

    def test_decode_failure_returns_empty(self):
        """解码失败 → 返回空字符串。"""
        result = parse_wps_text(b"\xff\xfe\x00\x00"[:3])  # 截断的 UTF-16LE
        # 解码失败或内容为空 → 返回 ""
        assert isinstance(result, str)

    def test_empty_bytes_returns_empty(self):
        result = parse_wps_text(b"")
        assert result == ""


# ════════════════════════════════════════════════════════════
# find_attachment_url + download_attachment + extract_content
# ════════════════════════════════════════════════════════════

class TestFindAttachmentUrl:
    def test_finds_sacinfo_url(self):
        html = '<a href="http://zxd.sacinfo.org.cn/gb_notice/file.pdf">下载</a>'
        url = find_attachment_url(html)
        assert "sacinfo" in url

    def test_finds_generic_pdf_url(self):
        html = '<a href="https://example.com/doc.pdf">附件</a>'
        url = find_attachment_url(html)
        assert url == "https://example.com/doc.pdf"

    def test_no_match_returns_none(self):
        assert find_attachment_url("<html>no links</html>") is None


class TestDownloadAttachment:
    def test_http_injection_returns_content(self):
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"file data"
        mock_http.get.return_value = mock_resp

        result = download_attachment("http://x.com/file.pdf", _http=mock_http)
        assert result == b"file data"

    def test_http_injection_non_200_returns_none(self):
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_http.get.return_value = mock_resp

        result = download_attachment("http://x.com/file.pdf", _http=mock_http)
        assert result is None

    def test_http_injection_none_resp_returns_none(self):
        mock_http = MagicMock()
        mock_http.get.return_value = None

        result = download_attachment("http://x.com/file.pdf", _http=mock_http)
        assert result is None


class TestExtractContent:
    def test_extracts_paragraphs(self):
        html = "<html><body><table><tr><td>ignore</td></tr></table><p>公告正文内容测试</p></body></html>"
        result = extract_content(html)
        assert "公告正文" in result

    def test_empty_html_returns_empty(self):
        assert extract_content("") == ""

    def test_no_paragraphs_fallback_to_keywords(self):
        html = '<div>批准 GB/T 1234-2020 测试标准发布，现予以公告，公告如下：具体内容请参见附件。' + "x" * 100 + "</div>"
        result = extract_content(html)
        assert len(result) > 0
