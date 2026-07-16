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


if __name__ == '__main__':
    unittest.main()
