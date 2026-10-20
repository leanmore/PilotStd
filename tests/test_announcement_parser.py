# tests/test_announcement_parser.py — 公告解析器测试

import os
import sys
import unittest

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from pilotstd.announcement.parser import (
    _build_header_map,
    _clean_wps_name,
    _code_key,
    _find_col,
    parse_announcement_meta,
    parse_html_table,
    parse_wps_text,
)


class TestParseHtmlTable(unittest.TestCase):
    def test_extracts_standard_list(self):
        html = '''<html><body>
        <table>
        <tr><th>序号</th><th>std_code</th><th>std_name</th></tr>
        <tr><td>1</td><td>GB/T 1.1-2020</td><td>标准化工作导则 第1部分</td></tr>
        <tr><td>2</td><td>GB/T 19000-2016</td><td>质量管理体系</td></tr>
        </table>
        </body></html>'''
        results = parse_html_table(html)
        self.assertIsInstance(results, list)
        if results:
            self.assertIn('std_code', results[0])

    def test_empty_html(self):
        results = parse_html_table('<html></html>')
        self.assertEqual(results, [])

    def test_no_table(self):
        results = parse_html_table('<html><body><p>No table here</p></body></html>')
        self.assertEqual(results, [])


class TestCleanWpsName(unittest.TestCase):
    def test_removes_wps_formatting(self):
        self.assertEqual(_clean_wps_name('GB/T 1.1-2020\x00多余'), 'GB/T 1.1-2020多余')

    def test_strips_whitespace(self):
        result = _clean_wps_name('  测试文件  ')
        self.assertTrue(len(result) > 0)

    def test_empty_string(self):
        result = _clean_wps_name('')
        self.assertEqual(result, '')


class TestCodeKey(unittest.TestCase):
    def test_extracts_code_and_number(self):
        key = _code_key({'std_code': 'GB', 'std_name': 'Test Standard'})
        self.assertIn('GB', key)
        self.assertIn('Test', key)

    def test_empty_fields(self):
        key = _code_key({'std_code': '', 'std_name': ''})
        self.assertEqual(key, '|')


class TestFindCol(unittest.TestCase):
    def test_finds_chinese_name(self):
        col_map = {0: '序号', 1: '标准编号', 2: '标准名称'}
        result = _find_col(col_map, '标准编号')
        self.assertEqual(result, 1)

    def test_finds_english_name(self):
        col_map = {0: 'standard_code', 1: 'standard_name'}
        result = _find_col(col_map, 'standard_code')
        self.assertEqual(result, 0)

    def test_not_found(self):
        col_map = {0: '序号'}
        result = _find_col(col_map, '不存在')
        self.assertIsNone(result)


class TestBuildHeaderMap(unittest.TestCase):
    def test_extracts_headers(self):
        html = '<table><tr><th>std_code</th><th>std_name</th></tr></table>'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        headers = _build_header_map(table)
        self.assertIsInstance(headers, dict)

    def test_empty_table(self):
        html = '<table></table>'
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        headers = _build_header_map(table)
        self.assertEqual(headers, {})


class TestParseAnnouncementMeta(unittest.TestCase):
    def test_extracts_fields(self):
        html = '''
        <html><body>
        <div>公告标题：测试公告</div>
        <div>发布部门：标准化研究院</div>
        <div>发布日期：2024-01-15</div>
        </body></html>
        '''
        meta = parse_announcement_meta(html)
        self.assertIsInstance(meta, dict)

    def test_empty_html(self):
        meta = parse_announcement_meta('')
        self.assertIsInstance(meta, dict)


class TestParseWpsText(unittest.TestCase):
    def test_empty_bytes(self):
        result = parse_wps_text(b'')
        self.assertEqual(result, '')

    def test_invalid_encoding(self):
        result = parse_wps_text(b'\x00\x00\x00\x01\x02')
        self.assertIsInstance(result, str)


class TestFullwidthStandardCodes(unittest.TestCase):
    """HB 公告常见全角连接符：`－`/`／` 不得导致整行被跳过。"""

    def test_fullwidth_dash_and_slash_rows_are_parsed(self):
        html = '''<html><body><table>
        <thead><tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>SJ/T 11460.6.1－2025</td><td>显示光源 第6-1部分</td></tr>
        <tr><td>2</td><td>SJ/T 11460.6.2－2025</td><td>显示光源 第6-2部分</td></tr>
        <tr><td>3</td><td>SJ/T 11461.4.1－2025</td><td>平板显示 第4-1部分</td></tr>
        <tr><td>4</td><td>SJ/T 12089.1.1－2025</td><td>通用多媒体接口 第1-1部分</td></tr>
        <tr><td>5</td><td>DY/Z／14.3—2026</td><td>数字电影 第3部分</td></tr>
        <tr><td>6</td><td>DY/Z？14.5—2026</td><td>数字电影 第5部分</td></tr>
        </tbody></table></body></html>'''
        results = parse_html_table(html)
        from pilotstd.announcement.parser import _normalize_code_text

        codes = {_normalize_code_text(r["std_code"]) for r in results}
        self.assertEqual(
            codes,
            {
                "SJ/T 11460.6.1-2025",
                "SJ/T 11460.6.2-2025",
                "SJ/T 11461.4.1-2025",
                "SJ/T 12089.1.1-2025",
                "DY/Z/14.3-2026",
                "DY/Z/14.5-2026",
            },
        )


class TestMultiSlashAndTypoPrefixes(unittest.TestCase):
    """DB/HB 常见前缀变形：DB52T（无分隔）、NB/SH/T（多斜杠）、HG/T … 一 …、SJ/T-。"""

    def test_variant_prefixes_are_parsed(self):
        html = '''<html><body><table>
        <thead><tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>DB52T 1078-2026</td><td>贵州地标</td></tr>
        <tr><td>2</td><td>DB11/ 2567-2026</td><td>北京地标</td></tr>
        <tr><td>3</td><td>NB/SH/T 0001-2026</td><td>能源行标</td></tr>
        <tr><td>4</td><td>HG/T 6488 一 2026</td><td>化工行标</td></tr>
        <tr><td>5</td><td>SJ/T-12117-2026</td><td>电子行标</td></tr>
        <tr><td>6</td><td>QB T 1750-2026</td><td>轻工行标</td></tr>
        </tbody></table></body></html>'''
        results = parse_html_table(html)
        from pilotstd.announcement.parser import _normalize_code_text

        codes = {_normalize_code_text(r["std_code"]) for r in results}
        self.assertEqual(len(codes), 6)
        self.assertIn("DB52T 1078-2026", codes)
        self.assertIn("DB11/ 2567-2026", codes)
        self.assertIn("NB/SH/T 0001-2026", codes)
        self.assertIn("HG/T 6488 - 2026", codes)
        self.assertIn("SJ/T-12117-2026", codes)
        self.assertIn("QB T 1750-2026", codes)

    def test_every_extracted_code_is_semantically_parseable(self):
        """跨层不变量：公告提取出的每个标准号，matcher 的 parse_std_number 必须能解析。"""
        from pilotstd.core.std_utils import parse_std_number

        html = '''<table><thead><tr><th>序号</th><th>标准编号</th><th>标准名称</th></tr></thead>
        <tbody>
        <tr><td>1</td><td>NB/SH/T 0001-2026</td><td>x</td></tr>
        <tr><td>2</td><td>DB52T 1078-2026</td><td>x</td></tr>
        <tr><td>3</td><td>SJ/T-12117-2026</td><td>x</td></tr>
        </tbody></table>'''
        items = parse_html_table(html)
        self.assertEqual(len(items), 3)
        for item in items:
            self.assertIsNotNone(parse_std_number(item["std_code"]), item["std_code"])


if __name__ == '__main__':
    unittest.main()
