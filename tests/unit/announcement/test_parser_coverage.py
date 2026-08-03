"""parser.py coverage completion tests."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pilotstd.announcement.parser import (
    _build_header_map,
    _clean_wps_name,
    _ocr_pdf,
    parse_announcement_detail,
    parse_html_table,
    parse_text_table,
)


# -- P0: parse_text_table (L293-326) + helpers --------------------------

class TestParseTextTable:
    def test_t1_empty_text_returns_empty_list(self):
        assert parse_text_table("") == []

    def test_t2_single_entry_no_replaces(self):
        text = "GB/T 1234-2020 某某测试条目名称\n2020-01-01 2020-06-01"
        results = parse_text_table(text)
        assert len(results) == 1
        item = results[0]
        assert item["std_code"] == "GB/T 1234-2020"
        assert "某某测试条目名称" in item["std_name"]
        assert item["publish_date"] == "2020-01-01"
        assert item["implementation_date"] == "2020-06-01"
        assert item["replaces_code"] == ""

    def test_t3_single_entry_with_adjacent_replaces(self):
        # Chinese chars + no newline between codes triggers adjacent replaces
        text = "GB/T 1234-2020 某某标准 GB/T 5678-2010 2020-01-01 2020-06-01"
        results = parse_text_table(text)
        assert len(results) == 1
        item = results[0]
        assert item["std_code"] == "GB/T 1234-2020"
        assert item["replaces_code"] == "GB/T 5678-2010"

    def test_t4_multiple_entries(self):
        text = (
            "GB/T 1111-2020 标准一\n2020-01-01 2020-06-01\n"
            "GB/T 2222-2021 标准二\n2021-03-01 2021-09-01\n"
            "GB/T 3333-2022 标准三\n2022-05-01 2022-11-01"
        )
        results = parse_text_table(text)
        assert len(results) == 3

    def test_t5_short_std_name_filtered(self):
        text = "GB/T 1234-2020 X"
        results = parse_text_table(text)
        assert results == []

    def test_t6_replaces_pattern_in_field_text(self):
        # Chinese chars in field text triggers adjacent detection
        text = "GB/T 1234-2020 某某标准名称 代替 GB/T 9999-2010\n2020-01-01 2020-06-01"
        results = parse_text_table(text)
        assert len(results) == 1
        item = results[0]
        assert item["replaces_code"] == "GB/T 9999-2010"

    def test_t7_no_dates(self):
        text = "GB/T 1234-2020 无日期标准名称条目"
        results = parse_text_table(text)
        assert len(results) == 1
        item = results[0]
        assert item["publish_date"] == ""
        assert item["implementation_date"] == ""


# -- P1: _ocr_pdf page-by-page branch (L366-372) -----------------------

class TestOcrPdf:
    def test_t8_mock_provider_success(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock(), MagicMock()]
        provider = MagicMock()

        with (
            patch("pypdf.PdfReader", return_value=mock_reader),
            patch("pilotstd.announcement.ocr.OcrScheduler",
                  type("Fake", (), {})),
        ):
            result_obj = MagicMock()
            result_obj.ok = True
            result_obj.text = "recognized text"
            provider.recognize_pdf.return_value = result_obj

            text = _ocr_pdf(b"fake-pdf", provider)
            assert "recognized text" in text
            assert provider.recognize_pdf.call_count == 2

    def test_t9_mock_provider_failure(self):
        mock_reader = MagicMock()
        mock_reader.pages = [MagicMock()]
        provider = MagicMock()

        with (
            patch("pypdf.PdfReader", return_value=mock_reader),
            patch("pilotstd.announcement.ocr.OcrScheduler",
                  type("Fake", (), {})),
        ):
            result_obj = MagicMock()
            result_obj.ok = False
            provider.recognize_pdf.return_value = result_obj

            text = _ocr_pdf(b"fake-pdf", provider)
            assert text == ""

    def test_t10_pdf_reader_exception(self):
        provider = MagicMock()

        with (
            patch("pypdf.PdfReader", side_effect=RuntimeError("bad pdf")),
            patch("pilotstd.announcement.ocr.OcrScheduler",
                  type("Fake", (), {})),
        ):
            result_obj = MagicMock()
            result_obj.ok = True
            result_obj.text = "fallback text"
            provider.recognize_pdf.return_value = result_obj

            text = _ocr_pdf(b"bad", provider)
            assert "fallback text" in text
            assert provider.recognize_pdf.call_count == 1


# -- P2: edge cases (L126, L150, L195, L390-391) -----------------------

class TestEdgeCases:
    def test_t11_build_header_map_no_thead(self):
        from bs4 import BeautifulSoup

        html = "<table><tr><th>标准编号</th><th>标准名称</th></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        col_map = _build_header_map(table)
        assert col_map.get(0) == "std_code"
        assert col_map.get(1) == "std_name"

    def test_t12_date_placeholder_normalization(self):
        html = (
            "<table>"
            "<thead><tr><th>序号</th><th>标准编号</th>"
            "<th>标准名称</th><th>发布日期</th></tr></thead>"
            "<tbody><tr><td>1</td><td>GB/T 1234-2020</td>"
            "<td>测试标准</td><td>-</td></tr></tbody>"
            "</table>"
        )
        results = parse_html_table(html)
        assert len(results) == 1
        assert results[0]["publish_date"] == ""

    def test_t13_clean_wps_page_mergeformat(self):
        dirty = "某某条目  — PAGE MERGEFORMAT 3 —  其余内容"
        cleaned = _clean_wps_name(dirty)
        assert "PAGE" not in cleaned
        assert "MERGEFORMAT" not in cleaned
        assert "某某条目" in cleaned

    def test_t14_pdf_ocr_fallback_in_detail(self):
        html = "<html><title>测试公告</title><body>2024-01-01</body></html>"
        mock_provider = MagicMock()
        with (
            patch("pilotstd.announcement.parser.parse_attachment_text",
                  return_value=""),
            patch("pilotstd.announcement.parser._ocr_pdf",
                  return_value="GB/T 9999-2024 OCR标准\n2024-01-01 2024-06-01"),
        ):
            items, meta = parse_announcement_detail(
                html=html,
                attachment_bytes=b"fake-pdf",
                attachment_filename="test.pdf",
                ocr_provider=mock_provider,
            )
            assert len(items) >= 1
            assert items[0]["std_code"] == "GB/T 9999-2024"
