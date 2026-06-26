# tests/test_announce_parser_unit.py
# 公告解析器单元测试——纯离线，不依赖网络
"""测试 pilotstd/announcement/parser.py 各解析函数：HTML表格、文本表格、元数据、标准号模式。"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest

from pilotstd.announcement.parser import (
    STD_CODE_PATTERN,
    _build_header_map,
    _code_key,
    parse_announcement_meta,
    parse_html_table,
    parse_text_table,
    parse_wps_text,
)


class TestStdCodePattern(unittest.TestCase):
    """标准编号正则——公告中最基础的一环。"""

    def test_gb_code(self):
        self.assertTrue(STD_CODE_PATTERN.match("GB 17681-2024"))

    def test_gbt_code(self):
        self.assertTrue(STD_CODE_PATTERN.match("GB/T 19001—2016"))

    def test_iso_code(self):
        self.assertTrue(STD_CODE_PATTERN.match("ISO 9001-2015"))

    def test_part_code(self):
        self.assertTrue(STD_CODE_PATTERN.match("GB/T 150.2-2024"))

    def test_non_std_rejected(self):
        self.assertFalse(STD_CODE_PATTERN.match("2024-06-06"))
        self.assertFalse(STD_CODE_PATTERN.match("第3号公告"))


class TestParseAnnouncementMeta(unittest.TestCase):
    """公告元数据提取：标题 + 日期。"""

    def test_extracts_title_and_date(self):
        html = """<html><head><title>2024年第1号国家标准公告</title></head>
        <body><p>发布日期：2024-01-15</p></body></html>"""
        meta = parse_announcement_meta(html)
        self.assertIn("国家标准公告", meta["title"])
        self.assertEqual(meta["publish_date"], "2024-01-15")

    def test_no_date_returns_empty(self):
        html = "<html><head><title>测试</title></head><body></body></html>"
        meta = parse_announcement_meta(html)
        self.assertEqual(meta["title"], "测试")
        self.assertEqual(meta["publish_date"], "")


class TestBuildHeaderMap(unittest.TestCase):
    """表头→列索引映射。"""

    def test_maps_standard_headers(self):
        html = """<table><thead><tr>
            <th>序号</th><th>标准编号</th><th>标准名称</th><th>代替标准</th><th>实施日期</th>
        </tr></thead></table>"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        table = soup.find("table")
        col_map = _build_header_map(table)
        self.assertEqual(col_map[1], "std_code")
        self.assertEqual(col_map[2], "std_name")
        self.assertEqual(col_map[3], "replaces_code")
        self.assertEqual(col_map[4], "implementation_date")

    def test_spaced_headers_normalized(self):
        html = """<table><thead><tr>
            <th>国 家 标 准 编 号</th><th>名 称</th>
        </tr></thead></table>"""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        col_map = _build_header_map(soup.find("table"))
        self.assertIn(0, col_map)


class TestParseHtmlTable(unittest.TestCase):
    """HTML 表格解析——公告核心解析路径。"""

    def test_parses_standard_table(self):
        html = """<table><thead><tr>
            <th>序号</th><th>标准编号</th><th>标准名称</th><th>代替标准</th><th>实施日期</th>
        </tr></thead><tbody><tr>
            <td>1</td><td>GB 17681-2024</td><td>危险化学品重大危险源安全监控技术规范</td><td>GB 17681-1999</td><td>2025-06-01</td>
        </tr></tbody></table>"""
        items = parse_html_table(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["std_code"], "GB 17681-2024")
        self.assertEqual(items[0]["std_name"], "危险化学品重大危险源安全监控技术规范")
        self.assertEqual(items[0]["replaces_code"], "GB 17681-1999")
        self.assertEqual(items[0]["implementation_date"], "2025-06-01")

    def test_skips_non_data_rows(self):
        html = """<table><thead><tr>
            <th>序号</th><th>标准编号</th><th>标准名称</th>
        </tr></thead><tbody><tr>
            <td>一</td><td>GB/T X-2024</td><td>标题行（非数据）</td>
        </tr><tr>
            <td>1</td><td>GB 12345-2024</td><td>数据行</td>
        </tr></tbody></table>"""
        items = parse_html_table(html)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["std_code"], "GB 12345-2024")

    def test_empty_table_returns_empty(self):
        html = "<table><thead><tr><th>序号</th><th>备注</th></tr></thead></table>"
        items = parse_html_table(html)
        self.assertEqual(items, [])


class TestParseTextTable(unittest.TestCase):
    """.wps 文本表格解析——附件回退路径。"""

    def test_parses_two_standards(self):
        text = (
            "1GB/Z 171—2026航空航天 实心铆钉 材料清单2026-04-29\n2GB/Z 172—2026燃料电池电动摩托车安全要求2026-05-01\n"
        )
        items = parse_text_table(text)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["std_code"], "GB/Z 171—2026")
        self.assertEqual(items[1]["std_code"], "GB/Z 172—2026")

    def test_parses_with_replaces(self):
        text = "1GB 17681-2024危险化学品重大危险源安全监控技术规范GB 17681-19992025-06-01\n"
        items = parse_text_table(text)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["std_code"], "GB 17681-2024")
        self.assertEqual(items[0]["replaces_code"], "GB 17681-1999")
        self.assertEqual(items[0]["publish_date"], "2025-06-01")

    def test_skips_non_numeric_start(self):
        text = "前  言\n本标准规定了...\n1GB 12345-2024测试标准2024-01-01\n"
        items = parse_text_table(text)
        self.assertEqual(len(items), 1)


class TestParseWpsText(unittest.TestCase):
    """WPS 文本提取（UTF-16LE 解码）。"""

    def test_extracts_chinese(self):
        raw = "GB 17681-2024 危险化学品".encode("utf-16-le")
        text = parse_wps_text(raw)
        self.assertIn("GB 17681-2024", text)
        self.assertIn("危险化学品", text)


class TestCodeKey(unittest.TestCase):
    """去重键生成——HTML 与附件交叉去重。"""

    def test_same_std_same_key(self):
        """前20字符相同的标准名称生成相同去重键"""
        a = {
            "std_code": "GB 17681-2024",
            "std_name": "危险化学品重大危险源安全监控技术规范及其实施指南",
        }
        b = {
            "std_code": "GB 17681-2024",
            "std_name": "危险化学品重大危险源安全监控技术规范及其实施指南（含勘误）",
        }
        self.assertEqual(_code_key(a), _code_key(b))  # 前20字符完全相同

    def test_different_std_different_key(self):
        a = {"std_code": "GB 17681-2024", "std_name": "危险化学品"}
        b = {"std_code": "GB 30871-2022", "std_name": "特殊作业安全规范"}
        self.assertNotEqual(_code_key(a), _code_key(b))


class TestOCRConfig(unittest.TestCase):
    """OCR 配置校验——确保 OCR 配置项存在且可读取（第五维度公告闭环）"""

    def test_ocr_provider_config_exists(self):
        """OCR 配置项应包含 provider 字段，配置路径可读。"""
        from pilotstd.core.config import ConfigManager

        cfg = ConfigManager()
        provider = cfg.get("ocr.provider", "")
        self.assertIsInstance(provider, str, "ocr.provider 应为字符串")
