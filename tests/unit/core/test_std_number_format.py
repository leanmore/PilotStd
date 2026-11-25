# tests/unit/core/test_std_number_format.py — 批次10（P1-7.1 B-11）规范编号/归档键表示层
"""`build_standard_number` / `ParsedStdInfo.get_full_number` / `make_standard_filename` 统一表示口径。

已查阅：
- `docs/plans/2026-11-25-p1-api-refresh.md` §3.2 R2（实跑证据：`ASME BB16.5-2020` 双前缀、
  `API SPEC 6DD-2021` 双后缀、`ASME 8.1-2025.pdf` 丢卷册、validity 登记对 ASME/BPVC 全被拒）
- `docs/plans/2026-11-24-p1-api-asme-gap.md` §4 G5/G7（year=0 记录与编号表示）

修复前（2026-11-25 实测）：
- `get_full_number` 把 `num_prefix`/`num_suffix` 与已含前后缀的 `raw_number` 再拼一次；
- `build_standard_number` 无 `num_suffix` 参数、多词前缀与序号直接粘连（`API STD610`）；
- `CANONICAL_KEY_RE=^\\S+ \\d+` 不接受字母前缀键 → `validity_checker.register_new_standard` 判畸形拒绝；
- `make_standard_filename` 未接收 `num_prefix` → BPVC 下载件名丢卷册。
"""

import pytest

from pilotstd.core.db import Database
from pilotstd.core.file_utils import make_standard_filename
from pilotstd.core.std_utils import build_standard_number, is_canonical_standard_number
from pilotstd.core.validity_checker import ValidityChecker
from pilotstd.models import ParsedStdInfo


class TestBuildStandardNumber:
    """规范键：`CODE [类型词/系列词] <编号><后缀>[.部分]-<年份>`，year=0 省略年份。"""

    @pytest.mark.parametrize(
        "code, number, part, year, num_prefix, num_suffix, expected",
        [
            # 既有 P2-11 契约不得回归
            ("TSG", 11, None, 2020, "", "", "TSG 11-2020"),
            ("GB/T", 1, 1, 2020, "", "", "GB/T 1.1-2020"),
            ("TSG", 7, None, None, "", "", "TSG 7"),
            ("TSG", 8002, None, 2022, "Z", "", "TSG Z8002-2022"),
            # item 4：类型词与序号之间必须有空格（修复前 API STD610）
            ("API", 610, None, 2004, "STD", "", "API STD 610-2004"),
            ("API", 6, None, 2021, "SPEC", "D", "API SPEC 6D-2021"),
            ("API", 2, None, 0, "RP", "A-WSD", "API RP 2A-WSD"),
            ("API", 579, 1, 0, "", "", "API 579-1"),
            # ASME 分类字母系列（单字母前缀紧贴序号）
            ("ASME", 16, 5, 2020, "B", "", "ASME B16.5-2020"),
            ("ASME", 16, 5, 0, "B", "", "ASME B16.5"),
            # ASME 系列词：PTC 空格、CSD 连字符
            ("ASME", 4, None, 2013, "PTC", "", "ASME PTC 4-2013"),
            ("ASME", 1, None, 2024, "CSD", "", "ASME CSD-1-2024"),
            # BPVC 卷/册/篇：罗马卷号必须带 BPVC 前缀，册篇字母落点号分段
            ("ASME", 8, 1, 2025, "VIII", "", "ASME BPVC.VIII.1-2025"),
            ("ASME", 2, None, 0, "II", "D", "ASME BPVC.II.D"),
            ("ASME", 2, None, 2021, "II", "D.M", "ASME BPVC.II.D.M-2021"),
            # 三级编号：第三级保留在 num_suffix（报告 §5 口径）
            ("ASME", 112, 18, 0, "A", ".1", "ASME A112.18.1"),
        ],
    )
    def test_format(self, code, number, part, year, num_prefix, num_suffix, expected):
        assert build_standard_number(code, number, part, year, num_prefix, num_suffix) == expected


class TestCanonicalKeyAcceptsNewForms:
    """`is_canonical_standard_number` 必须接受带字母前缀/类型词/BPVC 的规范键，仍拒绝畸形键。"""

    @pytest.mark.parametrize(
        "key",
        [
            "GB/T 1.1-2020",
            "TSG 11-2020",
            "TSG Z8002-2022",
            "API STD 610-2004",
            "API RP 2A-WSD",
            "API 579-1",
            "ASME B16.5-2020",
            "ASME BPVC.VIII.1-2025",
            "ASME BPVC.II.D",
            "ASME A112.18.1",
            "GB/T 12345",
        ],
    )
    def test_accept(self, key):
        assert is_canonical_standard_number(key) is True

    @pytest.mark.parametrize("key", ["", " 11-2020", "unknown-file.pdf", "  ", "abc"])
    def test_reject(self, key):
        assert is_canonical_standard_number(key) is False


class TestGetFullNumber:
    """`get_full_number` 不得重复拼接 B 通道原串里已有的前缀/后缀（报告 §3.2 R2）。"""

    @pytest.mark.parametrize(
        "fields, expected",
        [
            # B 通道 raw_number 已含前缀/后缀（修复前 → ASME BB16.5-2020 / API SPEC 6DD-2021）
            (
                dict(logical_code="ASME", number=16, raw_number="B16", num_prefix="B", part=5, year=2020),
                "ASME B16.5-2020",
            ),
            (
                dict(
                    logical_code="API",
                    number=6,
                    raw_number="6D",
                    num_prefix="SPEC",
                    num_suffix="D",
                    year=2021,
                ),
                "API SPEC 6D-2021",
            ),
            # A 通道无 raw_number：按字段拼装
            (dict(logical_code="API", number=6, year=2021, num_suffix="D"), "API 6D-2021"),
            (
                dict(logical_code="API", number=2, year=0, num_prefix="RP", num_suffix="A-WSD"),
                "API RP 2A-WSD",
            ),
            (dict(logical_code="API", number=579, year=0, part=1), "API 579-1"),
            # BPVC：卷号/册篇不得丢（修复前 → ASME VIII1-2025 / ASME 8.1-2025）
            (
                dict(logical_code="ASME", number=8, num_prefix="VIII", part=1, year=2025),
                "ASME BPVC.VIII.1-2025",
            ),
            (
                dict(logical_code="ASME", number=2, year=0, num_prefix="II", num_suffix="D"),
                "ASME BPVC.II.D",
            ),
            (
                dict(logical_code="ASME", number=2, num_prefix="II", num_suffix="D.M", year=2021),
                "ASME BPVC.II.D.M-2021",
            ),
            # 既有国标口径不得回归（raw_number 保留前导零是既有展示契约）
            (dict(logical_code="GB/T", number=1, part=1, year=2020), "GB/T 1.1-2020"),
            (dict(logical_code="GB/T", number=1, year=2020, raw_number="001"), "GB/T 001-2020"),
        ],
    )
    def test_full_number(self, fields, expected):
        info = ParsedStdInfo(raw_filename="x.pdf", **fields)
        assert info.get_full_number() == expected


class TestMakeStandardFilename:
    """BPVC 下载文件名必须保留卷/册（报告 §3.2 R2：修复前 `ASME 8.1-2025.pdf`）。"""

    def test_bpvc_filename_keeps_volume(self):
        assert make_standard_filename("ASME", 8, 2025, part=1, num_prefix="VIII") == (
            "ASME BPVC.VIII.1-2025.pdf"
        )

    def test_asme_letter_series_filename(self):
        assert make_standard_filename("ASME", 16, 2020, part=5, num_prefix="B") == "ASME B16.5-2020.pdf"

    def test_api_suffix_and_no_year_filename(self):
        assert (
            make_standard_filename("API", 2, 0, num_prefix="RP", num_suffix="A-WSD")
            == "API RP 2A-WSD.pdf"
        )
        assert make_standard_filename("API", 579, 0, part=1) == "API 579-1.pdf"

    def test_series_word_separator(self):
        assert make_standard_filename("API", 610, 2004, num_prefix="STD") == "API STD 610-2004.pdf"
        assert make_standard_filename("ASME", 4, 2013, num_prefix="PTC") == "ASME PTC 4-2013.pdf"
        assert make_standard_filename("ASME", 1, 2024, num_prefix="CSD") == "ASME CSD-1-2024.pdf"


@pytest.fixture
def checker(tmp_path):
    db = Database(str(tmp_path / "fmt.db"))
    yield ValidityChecker(db)
    db.close()


class TestValidityRegistration:
    """规范键必须能通过合法性登记（修复前 ASME B/Y 系列与 BPVC 全被判畸形拒绝）。"""

    @pytest.mark.parametrize(
        "key",
        [
            "ASME B16.5-2020",
            "ASME BPVC.VIII.1-2025",
            "API STD 610-2004",
            "API RP 2A-WSD",
            "ASME A112.18.1",
        ],
    )
    def test_register_accepts(self, checker, key):
        checker.register_new_standard(key)
        row = checker._db.fetchone(
            "SELECT COUNT(*) AS c FROM standard_validity WHERE standard_number=?", (key,)
        )
        assert row["c"] == 1, f"{key} 应登记成功"

    def test_register_still_rejects_malformed(self, checker):
        checker.register_new_standard(" 11-2020")
        row = checker._db.fetchone(
            "SELECT COUNT(*) AS c FROM standard_validity WHERE standard_number=?", (" 11-2020",)
        )
        assert row["c"] == 0
