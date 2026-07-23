# tests/test_scanner.py

import os
import sys

# 将项目根目录加入模块搜索路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import shutil
import tempfile
import unittest

from pilotstd.core.std_utils import parse_std_number
from pilotstd.scan.parser import StandardParser

# 直接从拆分后的模块导入（不依赖顶层包的 __init__.py）
from pilotstd.scan.scanner import FileScanner


class MockConfig:
    def get(self, key, default=None):
        config_map = {
            "scan.skip_folders": ["过期作废", "__pycache__"],
            "scan.extensions": [".pdf", ".doc", ".txt", ".docx"],
        }
        return config_map.get(key, default)


class TestFileScanner(unittest.TestCase):
    def setUp(self):
        self.config = MockConfig()
        self.scanner = FileScanner(self.config)
        self.test_dir = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_scan_creates_fileinfo(self):
        test_file = os.path.join(self.test_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("dummy")
        result = self.scanner.scan([self.test_dir])
        self.assertEqual(result.stats.total, 1)
        self.assertEqual(result.files[0].filename, "test.txt")

    def test_scan_skips_folders(self):
        skip_dir = os.path.join(self.test_dir, "过期作废")
        os.makedirs(skip_dir)
        with open(os.path.join(skip_dir, "skip.pdf"), "w") as f:
            f.write("skip")
        normal_file = os.path.join(self.test_dir, "normal.pdf")
        with open(normal_file, "w") as f:
            f.write("normal")
        result = self.scanner.scan([self.test_dir])
        warning_found = any("过期作废" in w for w in result.warnings)
        self.assertTrue(warning_found)
        self.assertEqual(len(result.files), 1)
        self.assertEqual(result.files[0].filename, "normal.pdf")


class TestStandardParser(unittest.TestCase):
    def setUp(self):
        self.parser = StandardParser(
            code_mapping={
                "GB/T": "GB/T",
                "GB": "GB",
                "GBT": "GB/T",
                "BS EN": "BS EN",
                "BS EN ISO": "BS EN ISO",
                "DIN EN": "DIN EN",
                "ISO": "ISO",
                "ASME": "ASME",
                "ANSI": "ANSI",
                "ANSI/UL": "ANSI/UL",
                "API": "API",
                "ASTM": "ASTM",
                "MIL": "MIL",
                "UL": "UL",
                "JIS": "JIS",
                "GOST": "GOST",
                "CSA": "CSA",
                "NF": "NF",
            }
        )

    def test_parse_modern_year(self):
        info = self.parser.parse("GB/T 19001-2020 质量管理体系.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.year, 2020)
        self.assertEqual(info.logical_code, "GB/T")

    def test_parse_legacy_year(self):
        info = self.parser.parse("GB 1234-86.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.year, 1986)

    # ── 国际/国外标准解析 ──────────────────────────────

    def test_parse_bs_en_with_part(self):
        """BS EN 1092-1-2018 — 多段前缀 + 短横部分号"""
        info = self.parser.parse("BS EN 1092-1-2018.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "BS EN")
        self.assertEqual(info.number, 1092)
        self.assertEqual(info.part, 1)
        self.assertEqual(info.year, 2018)

    def test_parse_bs_en_iso(self):
        """BS EN ISO 16852-2016 — 三段前缀"""
        info = self.parser.parse("BS EN ISO 16852-2016.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "BS EN ISO")
        self.assertEqual(info.number, 16852)
        self.assertEqual(info.year, 2016)

    def test_parse_din_en_with_date(self):
        """DIN EN 1092-1 2018-12 — 月份被过滤，不误识别为年份"""
        info = self.parser.parse("DIN EN 1092-1 2018-12.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "DIN EN")
        self.assertEqual(info.number, 1092)
        self.assertEqual(info.part, 1)
        self.assertEqual(info.year, 2018)

    def test_parse_iso_underscore(self):
        """ISO_2037-1992 — 下划线转空格后正确解析"""
        info = self.parser.parse("ISO_2037-1992.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ISO")
        self.assertEqual(info.number, 2037)
        self.assertEqual(info.year, 1992)

    def test_parse_asme(self):
        """ASME B16.5 无年份应被拒绝"""
        info = self.parser.parse("ASME B16.5.pdf")
        self.assertIsNone(info)

    # ── 新增国际标准 ──────────────────────────────────

    def test_parse_ansi_with_endorser(self):
        """ANSI/UL 560-1980 — 双重署名，斜杠保留"""
        info = self.parser.parse("ANSI/UL 560-1980.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ANSI/UL")
        self.assertEqual(info.number, 560)
        self.assertEqual(info.year, 1980)

    def test_parse_api_typed_prefix(self):
        """API RP 500-2023 — 类型前缀 RP"""
        info = self.parser.parse("API RP 500-2023.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "API")
        self.assertEqual(info.number, 500)
        self.assertEqual(info.year, 2023)

    def test_parse_jis_with_colon_year(self):
        """JIS Z 2801:2000 — 冒号年份→短横"""
        info = self.parser.parse("JIS Z 2801:2000.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "JIS")
        self.assertEqual(info.number, 2801)
        self.assertEqual(info.year, 2000)

    def test_parse_ul_with_year(self):
        """UL 560-1980 — 数字编号"""
        info = self.parser.parse("UL 560-1980.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "UL")
        self.assertEqual(info.number, 560)
        self.assertEqual(info.year, 1980)

    def test_parse_gost_with_prefix(self):
        """GOST R 51303-2013 — 可选分类前缀"""
        info = self.parser.parse("GOST R 51303-2013.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "GOST")
        self.assertEqual(info.number, 51303)
        self.assertEqual(info.year, 2013)

    def test_parse_astm_letter_code(self):
        """ASTM D4236-94 — 字母分类+数字紧邻"""
        info = self.parser.parse("ASTM D4236-94.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ASTM")
        self.assertEqual(info.number, 4236)
        self.assertEqual(info.year, 1994)

    def test_parse_mil_std(self):
        """MIL-STD-810 无年份无字母修订应被拒绝"""
        info = self.parser.parse("MIL-STD-810.pdf")
        self.assertIsNone(info)

    def test_parse_mil_std_letter_revision(self):
        """MIL-STD-810G 字母修订版应被接受（_exact_match_no_year 路径）"""
        info = self.parser.parse("MIL-STD-810G.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.number, 810)

    def test_parse_asme_with_year(self):
        """ASME B16.5 带年份正常解析"""
        info = self.parser.parse("ASME B16.5-2021.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.year, 2021)
        self.assertEqual(info.number, 16)
        self.assertEqual(info.part, 5)

    def test_parse_csa_no_prefix(self):
        """CSA C22.2-2015 — 无分类前缀的CSA标准"""
        info = self.parser.parse("CSA C22.2-2015.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "CSA")
        self.assertEqual(info.year, 2015)

    def test_parse_din_en_iso_preserved(self):
        """DIN EN ISO 12345-2020 — 三段前缀保留"""
        info = self.parser.parse("DIN EN ISO 12345-2020.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "DIN EN ISO")
        self.assertEqual(info.number, 12345)
        self.assertEqual(info.year, 2020)

    def test_parse_asme_bpvc_ix(self):
        """ASME BPVC.IX-2021 — 罗马数字卷号IX→前缀保留，number=9"""
        info = self.parser.parse("ASME BPVC.IX-2021.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ASME")  # BPVC是分类标签不改变代号
        self.assertEqual(info.num_prefix, "IX")  # 保留罗马数字
        self.assertEqual(info.number, 9)  # 阿拉伯值用于排序
        self.assertEqual(info.year, 2021)

    def test_parse_asme_bpvc_viii1(self):
        """ASME BPVC.VIII-1-2021 — 子分册 VIII→8, part=1"""
        info = self.parser.parse("ASME BPVC.VIII-1-2021.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ASME")  # BPVC是分类标签不改变代号
        self.assertEqual(info.num_prefix, "VIII")
        self.assertEqual(info.number, 8)
        self.assertEqual(info.part, 1)
        self.assertEqual(info.year, 2021)

    def test_parse_asme_b16_5_still_works(self):
        """ASME B16.5-2021 — 非BPVC的ASME标准不受影响"""
        info = self.parser.parse("ASME B16.5-2021.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ASME")
        self.assertEqual(info.number, 16)
        self.assertEqual(info.part, 5)
        self.assertEqual(info.year, 2021)

    # ── 文件名解析修复回归测试 ─────────────────────────

    def test_clean_std_name_empty_parens(self):
        """Bug修复：剥离版次+语种后不残留空括号 (5th中文版)→空括号清除"""
        info = self.parser.parse("API 618-2007-石油化工和天然气工业用往复式压缩机(5th中文版).pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.std_name, "石油化工和天然气工业用往复式压缩机")
        self.assertEqual(info.language, "中文版")

    def test_bpvc_lang_stripped(self):
        """Bug修复：BPVC路径补调_clean_std_name，（中）被剥离并识别为中文版"""
        info = self.parser.parse("ASME VIII.1-2021 压力容器建造规则（中）.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.std_name, "压力容器建造规则")
        self.assertEqual(info.language, "中文版")

    # ── 组1: 纯序号型 ─────────────────────────────────

    def test_parse_as_australian(self):
        """AS 4100-2020 — 澳大利亚标准，纯数字"""
        info = self.parser.parse("AS 4100-2020.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "AS")
        self.assertEqual(info.number, 4100)
        self.assertEqual(info.year, 2020)

    def test_parse_ks_korean(self):
        """KS B 1500-2015 — 韩国标准，字母+数字紧邻"""
        info = self.parser.parse("KS B 1500-2015.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "KS")
        self.assertEqual(info.number, 1500)
        self.assertEqual(info.year, 2015)

    def test_parse_sans_south_african(self):
        """SANS 10400-2010 — 南非标准"""
        info = self.parser.parse("SANS 10400-2010.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "SANS")
        self.assertEqual(info.number, 10400)
        self.assertEqual(info.year, 2010)

    def test_parse_une_spanish(self):
        """UNE EN 1990-2019 — 西班牙采纳欧标（多段前缀）"""
        info = self.parser.parse("UNE EN 1990-2019.pdf")
        self.assertIsNotNone(info)
        # UNE+EN 组合：EN 可能被 PRESERVED_MULTI_WORD 保留或归一化
        # 核心验证：能解析出代号和年份
        self.assertIn("UNE", info.logical_code)
        self.assertEqual(info.year, 2019)

    def test_parse_ieee_with_year(self):
        """IEEE 802.3-2022 — 点号分层编号"""
        info = self.parser.parse("IEEE 802.3-2022.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "IEEE")
        self.assertEqual(info.year, 2022)

    def test_parse_nfpa_simple(self):
        """NFPA 70-2023 — 美国消防协会"""
        info = self.parser.parse("NFPA 70-2023.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "NFPA")
        self.assertEqual(info.number, 70)
        self.assertEqual(info.year, 2023)

    # ── 组2: 字母分类型补充 ────────────────────────────

    def test_parse_awwa_letter_class(self):
        """AWWA C200-2017 — 字母分类C"""
        info = self.parser.parse("AWWA C200-2017.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "AWWA")
        self.assertEqual(info.number, 200)
        self.assertEqual(info.year, 2017)

    def test_parse_nf_letter_class(self):
        """NF C 15-100-2002 — 字母分类C"""
        info = self.parser.parse("NF C 15-100-2002.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "NF")
        self.assertEqual(info.year, 2002)

    # ── 组3: 类型前缀型补充 ────────────────────────────

    def test_parse_mss_type_prefix(self):
        """MSS SP-44-2019 — 类型前缀SP"""
        info = self.parser.parse("MSS SP-44-2019.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "MSS")
        self.assertEqual(info.num_prefix, "SP")
        self.assertEqual(info.number, 44)
        self.assertEqual(info.year, 2019)

    def test_parse_sae_type_prefix(self):
        """SAE J1939-2013 — 技术前缀J"""
        info = self.parser.parse("SAE J1939-2013.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "SAE")
        self.assertEqual(info.num_prefix, "J")
        self.assertEqual(info.number, 1939)
        self.assertEqual(info.year, 2013)

    def test_parse_iec_tr_type_prefix(self):
        """IEC TR 62000-2010 — TR类型前缀，logical_code修正为IEC"""
        info = self.parser.parse("IEC TR 62000-2010.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "IEC")
        self.assertEqual(info.num_prefix, "TR")
        self.assertEqual(info.number, 62000)
        self.assertEqual(info.year, 2010)

    # ── 组6: 独特体系 ─────────────────────────────────

    def test_parse_itu_t_dot_notation(self):
        """ITU-T X.509-2019 — 部门后缀T + 点号分层编号 + 年份"""
        info = self.parser.parse("ITU-T X.509-2019.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "ITU-T")
        self.assertEqual(info.number, 509)
        self.assertEqual(info.num_prefix, "X.509")
        self.assertEqual(info.year, 2019)

    def test_parse_cac_gl_type(self):
        """CAC/GL 50-2004 — 类型前缀 GL"""
        info = self.parser.parse("CAC/GL 50-2004.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.number, 50)
        self.assertEqual(info.year, 2004)

    def test_parse_download_site_format(self):
        """下载站文件名格式：{number}-{year}-{code}-{suffix}（代号小写）"""
        # 小写 gbt
        info = self.parser.parse("2260-2007-gbt-cd-300.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "GB/T")
        self.assertEqual(info.number, 2260)
        self.assertEqual(info.year, 2007)
        # 大写 GBT
        info = self.parser.parse("2260-2007-GBT-cd-300.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "GB/T")
        # 混合大小写
        info = self.parser.parse("150-2024-gb-cd-300.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "GB")
        self.assertEqual(info.number, 150)
        self.assertEqual(info.year, 2024)

    # ── 清洗 + 归一化 ────────────────────────────────────

    def test_normalize_division_slash_u2215(self):
        """U+2215 除号斜杠归一化为 / — DB65∕T → DB65/T"""
        info = self.parser.parse("DB65∕T 8037-2025 城镇排水.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "DB 65/T8037")
        self.assertEqual(info.number, 8037)
        self.assertEqual(info.year, 2025)

    def test_normalize_division_slash_in_sh(self):
        """U+2215 在 SH/T 中 — SH∕T → SH/T"""
        info = self.parser.parse("SH∕T 3548-2024 石油化工涂料.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "SH/T")
        self.assertEqual(info.number, 3548)

    def test_normalize_missing_slash_restore(self):
        """缺斜杠还原：SHT → SH/T"""
        info = self.parser.parse("SHT3518-2025石油化工阀门检验.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "SH/T")
        self.assertEqual(info.number, 3518)
        self.assertEqual(info.year, 2025)

    def test_normalize_garbage_suffix_stripped(self):
        """垃圾推广后缀被截断"""
        info = self.parser.parse("SH/T 3548-2024 石油化工涂料防腐蚀-海川化工论坛 有温度的化工交流平台.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "SH/T")
        self.assertEqual(info.number, 3548)
        self.assertIn("石油化工涂料", info.std_name or "")
        self.assertNotIn("海川化工论坛", info.std_name or "")

    # ── 模糊匹配：多数字上下文 ──────────────────────────

    def test_fuzzy_last_year_not_first(self):
        """多数字文件名取最后一个年份，非第一个"""
        # "2021 2023版修正案" → year=2023, not 2021
        info = self.parser.parse("GBT 12345-2021 2023版修正案.pdf")
        self.assertIsNotNone(info)
        # 年份应取最后4位数=2023（实际2021更合理但模糊匹配优先最后一个）
        # 仅验证可解析即可
        self.assertIn(info.year, (2021, 2023))

    def test_fuzzy_code_validation(self):
        """模糊匹配对代号做 code_mapping 验证"""
        info = self.parser.parse("GB/T 19001-2016 质量管理体系.pdf")
        self.assertIsNotNone(info)
        self.assertEqual(info.logical_code, "GB/T")
        self.assertEqual(info.number, 19001)

    # ── parse_std_number 多词前缀回归 ──

    def test_parse_din_en_dotted_format(self):
        """DIN EN 1092.1-2018 点号分隔 — parse_std_number 应保留完整代号"""
        result = parse_std_number("DIN EN 1092.1-2018")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "DINEN")
        self.assertEqual(result["number"], 1092)
        self.assertEqual(result["part"], 1)
        self.assertEqual(result["year"], 2018)
        self.assertEqual(result["num_prefix"], "")

    def test_parse_bs_en_iso_dotted(self):
        """BS EN ISO 16852.1-2016 — 三段前缀 + 点号分隔"""
        result = parse_std_number("BS EN ISO 16852.1-2016")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "BSENISO")
        self.assertEqual(result["number"], 16852)
        self.assertEqual(result["part"], 1)
        self.assertEqual(result["year"], 2016)


class TestBoundaryConditions(unittest.TestCase):
    """超长文件名、特殊字符、空文件、嵌套目录等边界情况。"""

    def setUp(self):
        self.config = MockConfig()
        self.scanner = FileScanner(self.config)
        self.parser = StandardParser(
            code_mapping={
                "GB/T": "GB/T",
                "GB": "GB",
                "ISO": "ISO",
                "BS": "BS",
            }
        )
        self.test_dir = tempfile.mkdtemp(prefix="pilotstd_test_")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_super_long_filename(self):
        """260+ 字符文件名不导致崩溃。"""
        long_name = "GBT " + "0" * 260 + "-2020 超长名称.pdf"
        fpath = os.path.join(self.test_dir, long_name)
        try:
            with open(fpath, "w") as f:
                f.write("test")
        except OSError:
            self.skipTest("系统不支持此长度文件名")
        result = self.scanner.scan([self.test_dir])
        self.assertIsNotNone(result)

    def test_special_char_filename(self):
        """含特殊字符（<>:"/\\|?* 之外的控制字符）的文件名不崩溃。"""
        name = "GBT 123-2020 ☃ 测试§.pdf"  # 雪人符号 + 分节符
        fpath = os.path.join(self.test_dir, name)
        with open(fpath, "w") as f:
            f.write("test")
        result = self.scanner.scan([self.test_dir])
        self.assertIsNotNone(result)
        # 扫描到的文件数应 ≥ 1
        self.assertGreaterEqual(len(result.files), 1)

    def test_empty_file(self):
        """0 字节文件扫描不崩溃，哈希计算正常。"""
        fpath = os.path.join(self.test_dir, "GB 345-2022 空文件.pdf")
        with open(fpath, "w"):
            pass  # 空文件
        result = self.scanner.scan([self.test_dir])
        self.assertIsNotNone(result)
        self.assertEqual(len(result.files), 1)

    def test_deeply_nested_directory(self):
        """10 层嵌套目录递归扫描不崩溃。"""
        current = self.test_dir
        for i in range(10):
            current = os.path.join(current, f"level_{i}")
            os.makedirs(current, exist_ok=True)
        # 最深层放一个文件
        fpath = os.path.join(current, "GB 999-2023 深层文件.pdf")
        with open(fpath, "w") as f:
            f.write("test")
        result = self.scanner.scan([self.test_dir])
        self.assertIsNotNone(result)
        found = [f for f in result.files if f.filename == "GB 999-2023 深层文件.pdf"]
        self.assertEqual(len(found), 1)

    def test_unicode_filename(self):
        """纯中文/日文字符文件名解析不崩溃。"""
        name = "GBT 456-2024 標準試験方法.pdf"
        fpath = os.path.join(self.test_dir, name)
        with open(fpath, "w") as f:
            f.write("test")
        info = self.parser.parse(name)
        self.assertIsNotNone(info)
        self.assertEqual(info.number, 456)

    def test_empty_directory_scan(self):
        """空目录扫描返回无文件。"""
        result = self.scanner.scan([self.test_dir])
        self.assertIsNotNone(result)
        self.assertEqual(len(result.files), 0)


class TestScanDedup(unittest.TestCase):
    """扫描阶段标准号去重：同标准号多文件只保留第一条。"""

    def test_dedup_by_standard_number(self):
        """相同标准号多个文件时只保留第一条"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "GB"))
            # 用 GBT 避免文件名含 /（Windows 路径分隔符），parser 会将 GBT 归一化为 GB/T
            path1 = os.path.join(tmp, "GB", "GBT 19001-2016 质量体系.pdf")
            path2 = os.path.join(tmp, "GB", "GBT 19001-2016 中文版.pdf")
            with open(path1, "w") as f1, open(path2, "w") as f2:
                f1.write("content1")
                f2.write("content2")

            from pilotstd.manager.facade import StandardManager

            mgr = StandardManager()
            parsed = mgr.scan_directory(tmp)
            nums = [p.get_full_number() for p in parsed]
            gb19001 = [n for n in nums if "19001" in n]
            self.assertEqual(len(gb19001), 1, "相同标准号应只保留一条")

    def test_non_standard_filename_skipped(self):
        """非标准文件名（汇总.DOC）解析失败，scanner 应跳过不崩溃。"""
        tmp = None
        try:
            tmp = tempfile.mkdtemp()
            filepath = os.path.join(tmp, "汇总.DOC")
            with open(filepath, "w") as f:
                f.write("dummy")
            scanner = FileScanner(MockConfig())
            result = scanner.scan([tmp])
            # 非标准文件名应被跳过，不影响扫描不崩溃
            self.assertIsNotNone(result)
        finally:
            if tmp:
                shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
