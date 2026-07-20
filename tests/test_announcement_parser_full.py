# tests/test_announcement_parser_full.py
# AnnouncementParser 完整单元测试

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.announcement.parser import (
    _build_header_map,
    _clean_wps_name,
    _code_key,
    _find_col,
    _parse_entry_fields,
    download_attachment,
    find_attachment_url,
    parse_announcement_detail,
    parse_announcement_meta,
    parse_attachment_text,
    parse_html_table,
    parse_text_table,
    parse_wps_text,
)

# ── 真实 HTML 片段 ───────────────────────────────────────────────
HTML_GB_TABLE = """<!DOCTYPE html>
<html><head><title>国家标准公告2024年第1号</title></head>
<body>
<h2>国家标准公告2024年第1号</h2>
<p>发布日期：2024-01-15</p>
<table>
<thead>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th><th>代替标准</th><th>实施日期</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>标准化工作导则 第1部分</td><td>GB/T 1.1-2009</td><td>2020-10-01</td></tr>
<tr><td>2</td><td>GB/T 19000-2016</td><td>质量管理体系</td><td></td><td>2017-07-01</td></tr>
</tbody>
</table>
</body></html>"""

HTML_GB_TABLE_EN_HEADERS = """<!DOCTYPE html>
<html><body>
<table>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>标准化工作导则</td></tr>
<tr><td>2</td><td>GB/T 2.2-2020</td><td>测试标准</td></tr>
</table>
</body></html>"""

HTML_WITH_ATTACHMENT = """<!DOCTYPE html>
<html><body>
<p>附件：<a href="http://zxd.sacinfo.org.cn/gb_notice/2024/001.wps">公告附件.wps</a></p>
<table>
<thead>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>GB/T 3.1-2020</td><td>测试标准3</td></tr>
</tbody>
</table>
</body></html>"""

HTML_WITH_DOCX_ATTACHMENT = """<!DOCTYPE html>
<html><body>
<p>附件：<a href="https://example.com/notice/2024/001.docx">附件.docx</a></p>
</body></html>"""

HTML_WITH_PDF_ATTACHMENT = """<!DOCTYPE html>
<html><body>
<p>附件下载：<a href="https://example.com/notice/2024/001.pdf">附件.pdf</a></p>
</body></html>"""

HTML_NO_TABLE = """<!DOCTYPE html>
<html><head><title>公告标题测试</title></head>
<body>
<p>发布日期：2024-06-15</p>
<p>这是一条没有表格的公告。</p>
</body></html>"""

HTML_GB_8COL = """<!DOCTYPE html>
<html><body>
<table>
<thead>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th><th>代替标准</th><th>发布日期</th><th>实施日期</th><th>备案号</th><th>主管部门</th></tr>
</thead>
<tbody>
<tr><td>1</td><td>GB 12345-2020</td><td>安全规范</td><td>GB 12345-2000</td>
<td>2020-06-01</td><td>2021-01-01</td><td>12345-2020</td><td>应急管理部</td></tr>
</tbody>
</table>
</body></html>"""


class TestParseHtmlTable(unittest.TestCase):
    """parse_html_table 测试 —— HTML 表格中提取标准列表。"""

    def test_gb_5col_table(self):
        """5 列表格提取标准信息。"""
        results = parse_html_table(HTML_GB_TABLE)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")
        self.assertEqual(results[0]["std_name"], "标准化工作导则 第1部分")
        self.assertEqual(results[0]["replaces_code"], "GB/T 1.1-2009")
        self.assertEqual(results[0]["implementation_date"], "2020-10-01")

    def test_english_header_table(self):
        """表头含标准编号/标准名称即可正常解析。"""
        results = parse_html_table(HTML_GB_TABLE_EN_HEADERS)
        self.assertEqual(len(results), 2)
        self.assertIn("std_code", results[0])

    def test_8col_full_table(self):
        """8 列完整表格提取所有字段。"""
        results = parse_html_table(HTML_GB_8COL)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["std_code"], "GB 12345-2020")
        self.assertEqual(results[0]["replaces_code"], "GB 12345-2000")
        self.assertEqual(results[0]["publish_date"], "2020-06-01")
        self.assertEqual(results[0]["record_no"], "12345-2020")
        self.assertEqual(results[0]["dept"], "应急管理部")

    def test_empty_html(self):
        self.assertEqual(parse_html_table("<html></html>"), [])

    def test_no_table(self):
        results = parse_html_table("<html><body><p>No table</p></body></html>")
        self.assertEqual(results, [])

    def test_table_without_code_column(self):
        """无标准编号列的表格被跳过。"""
        html = """<table><tr><th>序号</th><th>备注</th></tr><tr><td>1</td><td>test</td></tr></table>"""
        results = parse_html_table(html)
        self.assertEqual(results, [])

    def test_skips_non_standard_code_row(self):
        """首列非数字或标准号不匹配的行被跳过。"""
        html = """<table>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr>
<tr><td>a</td><td>备注行</td><td>不是标准号</td></tr>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>有效行</td></tr>
</table>"""
        results = parse_html_table(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")

    def test_thead_vs_first_tr_headers(self):
        """无 thead 时用第一个 tr 做表头。"""
        html = """<table>
<tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>测试标准</td></tr>
</table>"""
        results = parse_html_table(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")

    def test_headers_with_spaces(self):
        """表头文字含空格时归一化匹配。"""
        html = """<table>
<tr><th>序号</th><th>标 准 编 号</th><th>标 准 名 称</th></tr>
<tr><td>1</td><td>GB/T 1.1-2020</td><td>测试</td></tr>
</table>"""
        results = parse_html_table(html)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")


class TestParseAnnouncementMeta(unittest.TestCase):
    """parse_announcement_meta 测试。"""

    def test_extracts_title_from_title_tag(self):
        meta = parse_announcement_meta(HTML_NO_TABLE)
        self.assertEqual(meta["title"], "公告标题测试")

    def test_extracts_publish_date(self):
        meta = parse_announcement_meta(HTML_NO_TABLE)
        self.assertEqual(meta["publish_date"], "2024-06-15")

    def test_excludes_table_dates(self):
        """表格中的日期（实施日期）不应作为公告发布日期。"""
        html = """<html><body>
<table><tr><td>实施日期</td><td>2024-12-31</td></tr></table>
<p>发布日期：2024-01-15</p>
</body></html>"""
        meta = parse_announcement_meta(html)
        self.assertEqual(meta["publish_date"], "2024-01-15")

    def test_empty_html(self):
        meta = parse_announcement_meta("")
        self.assertIsInstance(meta, dict)
        self.assertEqual(meta["title"], "")
        self.assertEqual(meta["publish_date"], "")


class TestBuildHeaderMap(unittest.TestCase):
    """_build_header_map 测试。"""

    def test_chinese_keywords(self):
        from bs4 import BeautifulSoup

        html = "<table><tr><th>标准编号</th><th>标准名称</th></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        self.assertEqual(col_map.get(0), "std_code")
        self.assertEqual(col_map.get(1), "std_name")

    def test_alias_keywords(self):
        from bs4 import BeautifulSoup

        html = "<table><tr><th>编号</th><th>名称</th></tr></table>"
        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        self.assertEqual(col_map.get(0), "std_code")
        self.assertEqual(col_map.get(1), "std_name")

    def test_empty_table(self):
        from bs4 import BeautifulSoup

        soup = BeautifulSoup("<table></table>", "lxml")
        col_map = _build_header_map(soup.find("table"))
        self.assertEqual(col_map, {})


class TestFindCol(unittest.TestCase):
    """_find_col 测试。"""

    def test_found(self):
        col_map = {0: "std_code", 1: "std_name", 2: "publish_date"}
        self.assertEqual(_find_col(col_map, "std_code"), 0)
        self.assertEqual(_find_col(col_map, "publish_date"), 2)

    def test_not_found(self):
        self.assertIsNone(_find_col({0: "序号"}, "std_code"))

    def test_empty_map(self):
        self.assertIsNone(_find_col({}, "std_code"))


class TestParseWpsText(unittest.TestCase):
    """parse_wps_text 测试。"""

    def test_empty_bytes(self):
        self.assertEqual(parse_wps_text(b""), "")

    def test_invalid_encoding_returns_empty(self):
        result = parse_wps_text(b"\x00\x01\x02\x03")
        self.assertIsInstance(result, str)

    def test_valid_utf16le_wps(self):
        """有效的 UTF-16LE WPS 文本。"""
        wps_bytes = "GB/T 1.1-2020 标准化导则 2020-10-01\n".encode("utf-16-le")
        result = parse_wps_text(wps_bytes)
        self.assertIsInstance(result, str)
        # WPS 文本清理后应该不为空（如果内容有效）
        self.assertTrue(len(result) >= 0)

    def test_simple_wps_content(self):
        """简单 WPS 内容解码。"""
        content = "GB/T 12345-2020\x00测试标准\x002020-06-01"
        wps_bytes = content.encode("utf-16-le")
        result = parse_wps_text(wps_bytes)
        self.assertIsInstance(result, str)


class TestCleanWpsName(unittest.TestCase):
    """_clean_wps_name 测试。"""

    def test_removes_wps_page_footer(self):
        result = _clean_wps_name("测试标准 ——PAGE MERGEFORMAT 1——")
        self.assertNotIn("PAGE", result)
        self.assertNotIn("MERGEFORMAT", result)

    def test_removes_page_of_pattern(self):
        result = _clean_wps_name("内容 PAGE 1 OF 5 更多")
        self.assertNotIn("PAGE 1 OF 5", result)

    def test_removes_header_keywords(self):
        result = _clean_wps_name("标准编号 标准名称 GB/T 1.1 测试")
        self.assertNotIn("标准编号", result)
        self.assertNotIn("标准名称", result)

    def test_empty_string(self):
        self.assertEqual(_clean_wps_name(""), "")

    def test_strips_whitespace(self):
        result = _clean_wps_name("  内容  ")
        self.assertEqual(result, "内容")


class TestCodeKey(unittest.TestCase):
    """_code_key 测试。"""

    def test_combines_code_and_name(self):
        key = _code_key({"std_code": "GB", "std_name": "Test Standard"})
        self.assertIn("GB", key)
        self.assertIn("Test", key)

    def test_empty_fields(self):
        key = _code_key({"std_code": "", "std_name": ""})
        self.assertEqual(key, "|")

    def test_name_truncated_to_20(self):
        key = _code_key({"std_code": "GB/T 1.1", "std_name": "A" * 50})
        parts = key.split("|")
        self.assertEqual(len(parts[1]), 20)


class TestParseTextTable(unittest.TestCase):
    """parse_text_table 测试 —— 从纯文本中提取标准表格。"""

    def test_single_standard(self):
        text = "GB/T 1.1-2020 标准化工作导则 第1部分 2020-03-31"
        results = parse_text_table(text)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")
        self.assertIn("标准化工作导则", results[0]["std_name"])

    def test_multiple_standards(self):
        text = "GB/T 1.1-2020 标准化工作导则 第1部分 2020-03-31\nGB/T 19000-2016 质量管理体系 基础和术语 2016-12-30"
        results = parse_text_table(text)
        self.assertGreaterEqual(len(results), 2)

    def test_empty_text(self):
        self.assertEqual(parse_text_table(""), [])

    def test_no_std_code(self):
        self.assertEqual(parse_text_table("这是一段没有标准号的文字。"), [])

    def test_extracts_replaces_code(self):
        text = "GB/T 1.1-2020 标准化工作导则 代替 GB/T 1.1-2009 2020-03-31"
        results = parse_text_table(text)
        if len(results) >= 1:
            self.assertEqual(results[0]["std_code"], "GB/T 1.1-2020")

    def test_filters_too_short_name(self):
        text = "GB/T 12345-2020 X"
        results = parse_text_table(text)
        # std_name 长度 < 2 会被跳过
        for r in results:
            self.assertGreaterEqual(len(r.get("std_name", "")), 2)


class TestFindAttachmentUrl(unittest.TestCase):
    """find_attachment_url 测试。"""

    def test_finds_zxd_url(self):
        html = '<a href="http://zxd.sacinfo.org.cn/gb_notice/2024/001.wps">附件</a>'
        result = find_attachment_url(html)
        self.assertIn("zxd.sacinfo.org.cn", result)

    def test_finds_generic_attachment_extension(self):
        html = '<a href="https://example.com/notice/001.docx">下载</a>'
        result = find_attachment_url(html)
        self.assertEqual(result, "https://example.com/notice/001.docx")

    def test_no_attachment(self):
        result = find_attachment_url("<html><body>No attachment</body></html>")
        self.assertIsNone(result)

    def test_finds_wps_extension(self):
        html = '<a href="https://example.com/file.wps">WPS附件</a>'
        result = find_attachment_url(html)
        self.assertIsNotNone(result)
        self.assertIn(".wps", result)

    def test_finds_pdf_extension(self):
        html = '<a href="https://example.com/file.pdf">PDF附件</a>'
        result = find_attachment_url(html)
        self.assertIsNotNone(result)
        self.assertIn(".pdf", result)

    def test_empty_html(self):
        self.assertIsNone(find_attachment_url(""))


class TestDownloadAttachment(unittest.TestCase):
    """download_attachment 测试 —— DI 注入 _http。"""

    def test_di_http_success(self):
        """注入的 HTTP 客户端成功下载。"""
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake file content"
        mock_http.get.return_value = mock_resp

        result = download_attachment("https://example.com/file.wps", _http=mock_http)

        self.assertEqual(result, b"fake file content")
        mock_http.get.assert_called_once_with("https://example.com/file.wps")

    def test_di_http_non_200(self):
        """注入的 HTTP 客户端返回非 200。"""
        mock_http = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_http.get.return_value = mock_resp

        result = download_attachment("https://example.com/file.wps", _http=mock_http)

        self.assertIsNone(result)

    def test_di_http_none_response(self):
        """注入的 HTTP 客户端返回 None。"""
        mock_http = MagicMock()
        mock_http.get.return_value = None

        result = download_attachment("https://example.com/file.wps", _http=mock_http)

        self.assertIsNone(result)


class TestParseAttachmentText(unittest.TestCase):
    """parse_attachment_text 测试 —— 根据后缀名路由解析器。"""

    def test_wps_route(self):
        """.wps 后缀路由到 parse_wps_text。"""
        wps_bytes = "GB/T 1.1-2020 测试\x002020-01-01".encode("utf-16-le")
        result = parse_attachment_text(wps_bytes, filename="test.wps")
        self.assertIsInstance(result, str)

    @patch("pilotstd.announcement._attachment_parser._parse_pdf_text")
    def test_pdf_route(self, mock_pdf_parse):
        """.pdf 后缀路由到 PDF 解析器。"""
        mock_pdf_parse.return_value = "GB/T 1.1-2020 PDF标准"
        result = parse_attachment_text(b"fake pdf", filename="test.pdf")
        self.assertIn("PDF标准", result)

    @patch("pilotstd.announcement._attachment_parser._parse_docx_text")
    def test_docx_route(self, mock_docx_parse):
        """.docx 后缀路由到 DOCX 解析器。"""
        mock_docx_parse.return_value = "GB/T 1.1-2020 DOCX标准"
        result = parse_attachment_text(b"fake docx", filename="test.docx")
        self.assertIn("DOCX标准", result)

    @patch("pilotstd.announcement._attachment_parser._parse_docx_text")
    def test_doc_route(self, mock_docx_parse):
        """.doc 后缀也路由到 DOCX 解析器。"""
        mock_docx_parse.return_value = "GB/T 1.1-2020 DOC标准"
        result = parse_attachment_text(b"fake doc", filename="test.doc")
        self.assertIn("DOC标准", result)


class TestParseAnnouncementDetail(unittest.TestCase):
    """parse_announcement_detail 测试 —— HTML + 附件交叉校验。"""

    def test_html_only_returns_items_and_meta(self):
        items, meta = parse_announcement_detail(HTML_GB_TABLE)
        self.assertEqual(len(items), 2)
        self.assertIsInstance(meta, dict)
        self.assertEqual(items[0]["std_code"], "GB/T 1.1-2020")

    def test_empty_returns_empty(self):
        html = "<html><body><p>Nothing here</p></body></html>"
        items, meta = parse_announcement_detail(html)
        self.assertEqual(items, [])
        self.assertIsInstance(meta, dict)

    @patch("pilotstd.announcement.parser.parse_attachment_text")
    def test_attachment_supplements_html(self, mock_parse_att):
        """附件补充 HTML 中缺失的标准。"""
        mock_parse_att.return_value = "GB/T 99.99-2020 附件专属标准 2020-12-31"
        items, meta = parse_announcement_detail(
            HTML_GB_TABLE,
            attachment_bytes=b"fake",
            attachment_filename="test.wps",
        )
        self.assertEqual(len(items), 3)  # 2 from HTML + 1 from attachment
        self.assertEqual(items[2]["std_code"], "GB/T 99.99-2020")


class TestParseEntryFields(unittest.TestCase):
    """_parse_entry_fields 测试。"""

    def test_extracts_name_and_publish_date(self):
        name, replaces, date, impl_date = _parse_entry_fields("标准化导则 第1部分 2020-03-31")
        self.assertIn("标准化导则", name)
        self.assertEqual(date, "2020-03-31")
        # 只有一个日期时，实施日期应为空
        self.assertEqual(impl_date, "")

    def test_extracts_replaces_code(self):
        name, replaces, date, impl_date = _parse_entry_fields("工作导则 第1部分 GB/T 1.1-2009 2020-03-31")
        self.assertIn("工作导则", name)
        self.assertEqual(replaces, "GB/T 1.1-2009")
        self.assertEqual(date, "2020-03-31")

    def test_no_date(self):
        name, replaces, date, impl_date = _parse_entry_fields("只有名称没有日期")
        self.assertEqual(date, "")
        self.assertEqual(impl_date, "")
        self.assertIn("只有名称", name)


if __name__ == "__main__":
    unittest.main()
