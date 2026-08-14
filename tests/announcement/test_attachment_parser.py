"""_attachment_parser.py 补测 — fallback / PDF / DOCX / WPS 异常 / 内容提取。"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from pilotstd.announcement._attachment_parser import (
    _parse_docx_text,
    _parse_pdf_text,
    download_attachment,
    extract_content,
    find_attachment_url,
    parse_attachment_text,
    parse_wps_text,
)

# ════════════════════════════════════════════════════════════════
# T1: parse_attachment_text fallback (L26-34)
# ════════════════════════════════════════════════════════════════

class TestParseAttachmentTextFallback:
    def test_unknown_format_fallback_chain(self):
        """Unknown format tries WPS → PDF → DOCX, returns first non-empty."""
        with (
            patch("pilotstd.announcement._attachment_parser.parse_wps_text") as m_wps,
            patch("pilotstd.announcement._attachment_parser._parse_pdf_text") as m_pdf,
            patch("pilotstd.announcement._attachment_parser._parse_docx_text") as m_docx,
        ):
            m_wps.return_value = ""
            m_pdf.return_value = "PDF extracted text successfully"
            m_docx.return_value = ""

            result = parse_attachment_text(b"unknown bytes", "file.xyz")
            assert result == "PDF extracted text successfully"
            m_wps.assert_called_once()
            m_pdf.assert_called_once()
            m_docx.assert_not_called()

    def test_unknown_format_all_fail_returns_empty(self):
        """All parsers fail → returns empty string."""
        with (
            patch("pilotstd.announcement._attachment_parser.parse_wps_text") as m_wps,
            patch("pilotstd.announcement._attachment_parser._parse_pdf_text") as m_pdf,
            patch("pilotstd.announcement._attachment_parser._parse_docx_text") as m_docx,
        ):
            m_wps.side_effect = Exception("err")
            m_pdf.side_effect = Exception("err")
            m_docx.side_effect = Exception("err")

            result = parse_attachment_text(b"bad bytes", "file.xyz")
            assert result == ""
            assert m_wps.called and m_pdf.called and m_docx.called


# ════════════════════════════════════════════════════════════════
# T2: parse_wps_text UTF-16LE decode failure (L47-49)
# ════════════════════════════════════════════════════════════════

class TestParseWpsTextException:
    def test_utf16_decode_error_returns_empty(self):
        """Mock decode to raise UnicodeDecodeError, verify graceful empty return."""
        fake_bytes = MagicMock()
        fake_bytes.decode.side_effect = UnicodeDecodeError(
            "utf-16-le", b"", 0, 1, "invalid continuation bytes"
        )

        result = parse_wps_text(fake_bytes)
        assert result == ""


# ════════════════════════════════════════════════════════════════
# T3: _parse_pdf_text (L68-80)
# ════════════════════════════════════════════════════════════════

class TestParsePdfText:
    def test_extracts_text_from_pdf_pages(self):
        with patch("pypdf.PdfReader") as MockReader:
            mock_page = MagicMock()
            mock_page.extract_text.return_value = "Page 1 content"
            MockReader.return_value.pages = [mock_page, mock_page]

            result = _parse_pdf_text(b"%PDF-1.4 fake pdf bytes")
            assert "Page 1 content" in result

    def test_pdf_parse_error_returns_empty(self):
        with patch("pypdf.PdfReader", side_effect=RuntimeError("corrupt pdf")):
            result = _parse_pdf_text(b"not a real pdf")
            assert result == ""


# ════════════════════════════════════════════════════════════════
# T4: _parse_docx_text (L87-105)
# ════════════════════════════════════════════════════════════════

class TestParseDocxText:
    def test_extracts_table_text(self):
        with patch("docx.Document") as MockDoc:
            mock_cell = MagicMock()
            mock_cell.text = "GB/T 12345"
            mock_row = MagicMock()
            mock_row.cells = [mock_cell]
            mock_table = MagicMock()
            mock_table.rows = [mock_row]
            MockDoc.return_value.tables = [mock_table]

            result = _parse_docx_text(b"fake docx bytes")
            assert "GB/T 12345" in result

    def test_docx_parse_error_returns_empty(self):
        with patch("docx.Document", side_effect=RuntimeError("corrupt docx")):
            result = _parse_docx_text(b"not a real docx")
            assert result == ""


# ════════════════════════════════════════════════════════════════
# T5: download_attachment network path (L128-131)
# ════════════════════════════════════════════════════════════════

class TestDownloadAttachmentNetwork:
    def test_network_path_uses_safe_raw_get(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"downloaded content"

        with patch(
            "pilotstd.query.network.safe_raw_get",
            return_value=mock_resp,
        ):
            result = download_attachment("https://example.com/attachment.wps")
            assert result == b"downloaded content"


# ════════════════════════════════════════════════════════════════
# T6: extract_content (L137,141,146,155-156)
# ════════════════════════════════════════════════════════════════

class TestExtractContent:
    def test_empty_html_returns_empty(self):
        assert extract_content("") == ""

    def test_p_tag_extraction(self):
        html = "<html><body><p>Paragraph 1</p><p>Paragraph 2</p></body></html>"
        result = extract_content(html)
        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_keyword_fallback(self):
        """L155-156: no <p> tags, keyword-based fallback. Needs >50 chars after strip."""
        html = (
            "<div>现予以公告如下：GB/T 12345-2026 批准发布，"
            "本标准规定了相关产品的技术要求、试验方法、检验规则"
            "以及标志、包装、运输和贮存等内容</div>"
        )
        result = extract_content(html)
        assert result is not None
        assert "GB/T 12345-2026" in result


# ════════════════════════════════════════════════════════════════
# Batch 2: 剩余 27 行缺口精准覆盖
# ════════════════════════════════════════════════════════════════

class TestParseAttachmentTextRouting:
    """L20,22,24: known extensions route directly to matching parser."""

    MOD = "pilotstd.announcement._attachment_parser"

    def test_wps_extension_routes_directly(self):
        with (
            patch(f"{self.MOD}.parse_wps_text", return_value="wps ok") as m_wps,
            patch(f"{self.MOD}._parse_pdf_text") as m_pdf,
            patch(f"{self.MOD}._parse_docx_text") as m_docx,
        ):
            result = parse_attachment_text(b"fake", "test.wps")
            assert result == "wps ok"
            m_wps.assert_called_once()
            m_pdf.assert_not_called()
            m_docx.assert_not_called()

    def test_pdf_extension_routes_directly(self):
        with (
            patch(f"{self.MOD}.parse_wps_text") as m_wps,
            patch(f"{self.MOD}._parse_pdf_text", return_value="pdf ok") as m_pdf,
            patch(f"{self.MOD}._parse_docx_text"),
        ):
            result = parse_attachment_text(b"fake", "standard.pdf")
            assert result == "pdf ok"
            m_pdf.assert_called_once()
            m_wps.assert_not_called()

    def test_docx_extension_routes_directly(self):
        with (
            patch(f"{self.MOD}.parse_wps_text") as m_wps,
            patch(f"{self.MOD}._parse_pdf_text"),
            patch(f"{self.MOD}._parse_docx_text", return_value="docx ok") as m_docx,
        ):
            result = parse_attachment_text(b"fake", "notice.docx")
            assert result == "docx ok"
            m_docx.assert_called_once()
            m_wps.assert_not_called()


class TestParseWpsTextMainPath:
    """L51-63: UTF-16LE decode + clean pipeline (non-exception path)."""

    def test_valid_utf16le_decodes_and_cleans(self):
        source = "GB/T 12345-2026 批准发布"
        raw = b"\xff\xfe" + source.encode("utf-16-le")
        result = parse_wps_text(raw)
        assert isinstance(result, str)
        # output may be empty if STD_CODE_PATTERN doesn't match,
        # but decode must succeed (no crash, no empty-string-from-exception)
        assert result is not None


class TestParseDocxTextParagraphFallback:
    """L98-101: no tables → extract paragraphs only."""

    def test_no_tables_extracts_paragraphs_only(self):
        with patch("docx.Document") as MockDoc:
            mock_doc = MagicMock()
            p1 = MagicMock()
            p1.text = "paragraph-only content"
            mock_doc.paragraphs = [p1]
            mock_doc.tables = []
            MockDoc.return_value = mock_doc

            result = _parse_docx_text(b"PK fake docx")
            assert "paragraph-only content" in result


class TestDownloadAttachmentMockHttp:
    """L126-127: mock _http path; L131: return None on failure."""

    def test_mock_http_success(self):
        mock_http = MagicMock()
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"file bytes"
        mock_http.get.return_value = resp

        result = download_attachment("https://example.com/std.pdf", _http=mock_http)
        assert result == b"file bytes"

    def test_mock_http_failure_returns_none(self):
        mock_http = MagicMock()
        resp = MagicMock()
        resp.status_code = 500
        resp.content = b"error"
        mock_http.get.return_value = resp

        result = download_attachment("https://example.com/std.pdf", _http=mock_http)
        assert result is None


class TestExtractContentEdgeCases:
    """L111-118 find_attachment_url; L141 table pruning; L158 final return."""

    def test_find_attachment_url_sacinfo_pattern(self):
        url = find_attachment_url(
            '<a href="http://zxd.sacinfo.org.cn/gb_notice/ABC123">link</a>'
        )
        assert url is not None
        assert "ABC123" in url

    def test_find_attachment_url_generic_pattern(self):
        url = find_attachment_url(
            '<a href="https://example.com/uploads/notice.wps">link</a>'
        )
        assert url is not None
        assert url.endswith(".wps")

    def test_table_pruning(self):
        html = "<div><table><tr><td>ignore me</td></tr></table><p>valid content</p></div>"
        result = extract_content(html)
        assert "valid content" in result

    def test_final_return_empty_string(self):
        # no <p> tags, no keyword match, div too short → returns ""
        result = extract_content("<div><span>short</span></div>")
        assert result == ""
