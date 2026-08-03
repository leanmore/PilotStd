"""parser.py coverage completion R2."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

from pilotstd.announcement.parser import (
    _build_header_map,
    _clean_wps_name,
    parse_announcement_detail,
    parse_announcement_meta,
    parse_text_table,
)

# Shared HTML table fragment with Chinese headers that match _HEADER_KEYWORD_MAP
_TBL = (
    "<table><thead><tr><th>序号</th><th>标准编号</th>"
    "<th>标准名称</th><th>发布日期</th></tr></thead>"
    "<tbody><tr><td>1</td><td>{code}</td>"
    "<td>{name}</td><td>{date}</td></tr></tbody></table>"
)

def _html(title="test", code="GB/T 1000-2024", name="html-std", date="-"):
    return (
        f"<html><title>{title}</title><body>2024-06-15"
        + _TBL.format(code=code, name=name, date=date)
        + "</body></html>"
    )


# -- L42: parse_announcement_meta title tag present ---------------------

class TestAnnouncementMeta:
    def test_title_tag_present(self):
        html = "<html><head><title>test-title</title></head><body>2024-01-01</body></html>"
        meta = parse_announcement_meta(html)
        assert meta["title"] == "test-title"
        assert meta["publish_date"] == "2024-01-01"


# -- L118, L122, L126: _build_header_map edge cases ---------------------

class TestBuildHeaderMapEdge:
    def test_no_thead_first_tr_th_fallback(self):
        html = "<table><tr><th>编号</th><th>名称</th></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        assert col_map.get(0) == "std_code"
        assert col_map.get(1) == "std_name"

    def test_no_thead_no_th_at_all(self):
        html = "<table><tr><td>data</td></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        assert col_map == {}

    def test_thead_with_empty_th(self):
        html = "<table><thead><tr><th></th><th> </th></tr></thead></table>"
        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        assert col_map == {}


# -- L195: _clean_wps_name keyword list tail ----------------------------

class TestCleanWpsNameTailKeyword:
    def test_tail_keyword_removed(self):
        dirty = "某某条目代替文件号内容"
        cleaned = _clean_wps_name(dirty)
        assert "代替文件号" not in cleaned
        assert "某某条目" in cleaned


# -- L222-225, L296-297: parse_text_table inner loop --------------------

class TestParseTextTableInnerLoop:
    def test_skip_indices_already_skipped(self):
        text = (
            "GB/T 1111-2020 某某名称一 GB/T 2222-2010 2020-01-01 2020-06-01\n"
            "GB/T 3333-2021 某某名称三 2021-01-01 2021-06-01"
        )
        results = parse_text_table(text)
        codes = [r["std_code"] for r in results]
        assert "GB/T 2222-2010" not in codes
        assert "GB/T 1111-2020" in codes
        assert "GB/T 3333-2021" in codes

    def test_field_text_boundary_at_end_of_text(self):
        text = "GB/T 9999-2023 末尾条目名称 2023-01-01 2023-07-01"
        results = parse_text_table(text)
        assert len(results) == 1
        assert results[0]["std_code"] == "GB/T 9999-2023"


# -- L356-364, L376-395: parse_announcement_detail branches -------------

class TestAnnouncementDetailBranches:
    def test_html_only_no_attachment(self):
        items, meta = parse_announcement_detail(_html())
        assert len(items) == 1
        assert items[0]["std_code"] == "GB/T 1000-2024"

    def test_attachment_only_no_html_table(self):
        html = "<html><title>test</title><body>2024-01-01</body></html>"
        with patch("pilotstd.announcement.parser.parse_attachment_text",
                   return_value="GB/T 2000-2024 附件条目\n2024-03-01 2024-09-01"):
            items, meta = parse_announcement_detail(
                html=html, attachment_bytes=b"f", attachment_filename="t.wps")
        assert len(items) == 1
        assert items[0]["std_code"] == "GB/T 2000-2024"

    def test_cross_dedup_attachment_supplement(self):
        att_text = "GB/T 3000-2024 附件独有条目\n2024-05-01 2024-11-01"
        with patch("pilotstd.announcement.parser.parse_attachment_text",
                   return_value=att_text):
            items, meta = parse_announcement_detail(
                html=_html(), attachment_bytes=b"f", attachment_filename="t.wps")
        codes = [i["std_code"] for i in items]
        assert "GB/T 1000-2024" in codes
        assert "GB/T 3000-2024" in codes

    def test_cross_dedup_duplicate_ignored(self):
        # _code_key = std_code + "|" + std_name[:20], must match exactly
        att_text = "GB/T 1000-2024 html-std"
        with patch("pilotstd.announcement.parser.parse_attachment_text",
                   return_value=att_text):
            items, meta = parse_announcement_detail(
                html=_html(), attachment_bytes=b"f", attachment_filename="t.wps")
        assert len(items) == 1

    def test_both_empty_returns_empty_list(self):
        html = "<html><title>empty</title><body></body></html>"
        with patch("pilotstd.announcement.parser.parse_attachment_text",
                   return_value=""):
            items, meta = parse_announcement_detail(
                html=html, attachment_bytes=b"e", attachment_filename="t.wps")
        assert items == []
        assert meta["title"] == "empty"

    def test_pdf_ocr_fallback(self):
        html = "<html><title>pdf-test</title><body>2024-01-01</body></html>"
        with (
            patch("pilotstd.announcement.parser.parse_attachment_text",
                  return_value=""),
            patch("pilotstd.announcement.parser._ocr_pdf",
                  return_value="GB/T 8888-2024 ocr条目\n2024-02-01 2024-08-01"),
        ):
            items, meta = parse_announcement_detail(
                html=html, attachment_bytes=b"p", attachment_filename="test.pdf",
                ocr_provider=MagicMock())
        assert len(items) >= 1
        assert items[0]["std_code"] == "GB/T 8888-2024"

    def test_publish_date_backfill_from_meta(self):
        items, meta = parse_announcement_detail(
            _html(code="GB/T 5555-2024", name="无日期条目", date="-"))
        assert items[0]["publish_date"] == "2024-06-15"
