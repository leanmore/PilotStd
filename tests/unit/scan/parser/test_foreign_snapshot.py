# tests/unit/scan/parser/test_foreign_snapshot.py
"""ForeignHandlerMixin Phase 0/1 行为快照测试。

通过入口函数 _post_process_foreign 覆盖全部 6 个分组，
每个分组 >=2 用例（正常 + 边界）。
"""

from __future__ import annotations

from pilotstd.models import ParsedStdInfo
from pilotstd.scan.parser._foreign import _post_process_foreign


class TestForeignPostProcess:
    """_post_process_foreign 入口：按 _FOREIGN_GROUP_MAP 分组路由。"""

    # -- pure_numeric (group 1): no processing needed --

    def test_pure_numeric_no_change_ul(self):
        """UL -> pure numeric, num_prefix stays empty."""
        info = ParsedStdInfo(
            raw_filename="UL 1234-2020 standard.pdf",
            logical_code="UL",
            number=1234,
            year=2020,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == ""
        assert info.logical_code == "UL"

    def test_pure_numeric_no_change_ieee(self):
        """IEEE -> pure numeric, no changes."""
        info = ParsedStdInfo(
            raw_filename="IEEE 802.3-2022.pdf",
            logical_code="IEEE",
            number=802,
            year=2022,
        )
        _post_process_foreign(info)
        assert info.year == 2022
        assert info.logical_code == "IEEE"

    # -- letter_class (group 2): extract letter -> num_prefix --

    def test_letter_class_astm(self):
        """ASTM A 370 -> num_prefix set to A."""
        info = ParsedStdInfo(
            raw_filename="ASTM A 370-2020.pdf",
            logical_code="ASTM",
            number=370,
            year=2020,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "A"

    def test_letter_class_jis(self):
        """JIS Z -> num_prefix set to Z."""
        info = ParsedStdInfo(
            raw_filename="JIS Z 8720-2018.pdf",
            logical_code="JIS",
            number=8720,
            year=2018,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "Z"

    def test_letter_class_nf(self):
        """NF E -> num_prefix set to E."""
        info = ParsedStdInfo(
            raw_filename="NF E 22-345-2015.pdf",
            logical_code="NF",
            number=22,
            year=2015,
            part=345,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "E"

    def test_letter_class_no_match_keeps_empty(self):
        """Edge: no space between letter and number -> regex won't match."""
        info = ParsedStdInfo(
            raw_filename="ASTM A370-2020.pdf",
            logical_code="ASTM",
            number=370,
            year=2020,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == ""

    # -- type_prefix (group 3): extract type prefix -> num_prefix --

    def test_type_prefix_api(self):
        """API RP -> num_prefix set to RP."""
        info = ParsedStdInfo(
            raw_filename="API RP 2A-2010.pdf",
            logical_code="API",
            number=2,
            year=2010,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "RP"

    def test_type_prefix_iec_tr(self):
        """IEC TR -> num_prefix=TR, logical_code corrected to IEC."""
        info = ParsedStdInfo(
            raw_filename="IEC TR 61000-3-2020.pdf",
            logical_code="IEC TR",
            number=61000,
            year=2020,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "TR"
        assert info.logical_code == "IEC"

    def test_type_prefix_mss_sp(self):
        """MSS SP -> num_prefix set to SP."""
        info = ParsedStdInfo(
            raw_filename="MSS SP-44-2019.pdf",
            logical_code="MSS",
            number=44,
            year=2019,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "SP"

    def test_type_prefix_mil(self):
        """MIL-STD -> num_prefix set to STD."""
        info = ParsedStdInfo(
            raw_filename="MIL-STD 810G.pdf",
            logical_code="MIL",
            number=810,
            year=0,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "STD"

    def test_type_prefix_sae(self):
        """SAE AMS -> num_prefix set to AMS."""
        info = ParsedStdInfo(
            raw_filename="SAE AMS 1234-2020.pdf",
            logical_code="SAE",
            number=1234,
            year=2020,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "AMS"

    # -- multi_prefix (group 4): no processing needed --

    def test_multi_prefix_no_change_din(self):
        """DIN -> multi-prefix, num_prefix preserved."""
        info = ParsedStdInfo(
            raw_filename="DIN EN 12345-2020.pdf",
            logical_code="DIN EN",
            number=12345,
            year=2020,
            num_prefix="EN",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "EN"

    def test_multi_prefix_no_change_bs(self):
        """BS -> multi-prefix, preserved."""
        info = ParsedStdInfo(
            raw_filename="BS EN 60721-2019.pdf",
            logical_code="BS EN",
            number=60721,
            year=2019,
            num_prefix="EN",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "EN"

    # -- special_sep (group 5): GOST dot-numbers / ASME BPVC --

    def test_special_sep_gost_two_part(self):
        """GOST R 52857.1 -> number=52857, part=1."""
        info = ParsedStdInfo(
            raw_filename="GOST R 52857.1-2005.pdf",
            logical_code="GOST R",
            number=52857,
            year=2005,
            part=None,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.number == 52857
        assert info.part == 1
        assert info.year == 2005

    def test_special_sep_gost_three_part(self):
        """GOST 8.417.2 -> num_prefix=8, number=417, part=2."""
        info = ParsedStdInfo(
            raw_filename="GOST 8.417.2-2015.pdf",
            logical_code="GOST",
            number=8,
            year=2015,
            num_prefix="",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "8"
        assert info.number == 417
        assert info.part == 2

    def test_special_sep_asme_non_bpvc(self):
        """ASME non-BPVC -> no changes."""
        info = ParsedStdInfo(
            raw_filename="ASME B16.5-2020.pdf",
            logical_code="ASME",
            number=16,
            year=2020,
            num_prefix="B",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "B"

    # -- unique (group 6): ANSI / CAC / ITU --

    def test_unique_ansi_no_change(self):
        """ANSI -> double-signature, no processing needed."""
        info = ParsedStdInfo(
            raw_filename="ANSI/API 1234-2020.pdf",
            logical_code="ANSI/API",
            number=1234,
            year=2020,
        )
        _post_process_foreign(info)
        assert info.logical_code == "ANSI/API"

    def test_unique_cac_no_prefix_change(self):
        """CAC: CAC_PREFIXES includes CAC itself, set iteration order matters."""
        info = ParsedStdInfo(
            raw_filename="CAC CODEX STAN 192-1995.pdf",
            logical_code="CAC",
            number=192,
            year=1995,
        )
        _post_process_foreign(info)
        assert info.logical_code in ("CAC", "Codex Stan")

    def test_unique_itu_with_year(self):
        """ITU: fills year from raw when year==0."""
        info = ParsedStdInfo(
            raw_filename="ITU-T G.992.1-1999.pdf",
            logical_code="ITU",
            number=992,
            year=0,
        )
        _post_process_foreign(info)
        assert info.year == 1999

    def test_unique_itu_year_already_set(self):
        """Edge: ITU year already set -> unchanged."""
        info = ParsedStdInfo(
            raw_filename="ITU-R M.1457-2019.pdf",
            logical_code="ITU",
            number=1457,
            year=2019,
        )
        _post_process_foreign(info)
        assert info.year == 2019

    # -- unknown code --

    def test_unknown_code_no_change(self):
        """Edge: code not in _FOREIGN_GROUP_MAP -> no changes."""
        info = ParsedStdInfo(
            raw_filename="XYZ 1234-2020.pdf",
            logical_code="XYZ",
            number=1234,
            year=2020,
            num_prefix="P",
        )
        _post_process_foreign(info)
        assert info.num_prefix == "P"
        assert info.logical_code == "XYZ"
