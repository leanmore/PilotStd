"""D-13 P1：国外标准后处理（_foreign）各分组分支覆盖。"""

from __future__ import annotations

from pilotstd.models import ParsedStdInfo
from pilotstd.scan.parser._foreign import _post_process_foreign


def _info(code: str, raw: str, year: int = 2020) -> ParsedStdInfo:
    return ParsedStdInfo(raw_filename=raw, logical_code=code, number=1, year=year)


def test_unknown_group_is_noop() -> None:
    info = _info("XYZ", "XYZ 1-2020")
    _post_process_foreign(info)
    assert info.num_prefix == ""


def test_letter_class_groups() -> None:
    for code, raw, expected in (
        ("ASTM", "ASTM A 123-2020", "A"),
        ("JIS", "JIS B 1234-2020", "B"),
        ("CSA", "CSA C 22.2-2020", "C"),
        ("AWWA", "AWWA D 100-2020", "D"),
        ("NF", "NF C 15-100-2020", "C"),
    ):
        info = _info(code, raw)
        _post_process_foreign(info)
        assert info.num_prefix == expected


def test_type_prefix_groups() -> None:
    cases = (
        ("API", "API SPEC 1-2020", "SPEC"),
        ("MSS", "MSS SP 55-2020", "SP"),
        ("MIL", "MIL-STD-810G", "STD"),
        ("SAE", "SAE J 123-2020", "J"),
        ("IEC", "IEC TR 123-2020", "TR"),
    )
    for code, raw, expected in cases:
        info = _info(code, raw)
        _post_process_foreign(info)
        assert info.num_prefix == expected
    # IEC 类型前缀同时把 logical_code 修正为 IEC
    iec = _info("IEC TR", "IEC TR 123-2020")
    _post_process_foreign(iec)
    assert iec.logical_code == "IEC"


def test_gost_special_sep_both_shapes() -> None:
    info = _info("GOST", "GOST R ISO 12345.6.7-2020")
    _post_process_foreign(info)
    assert (info.num_prefix, info.number, info.part, info.year) == ("12345", 6, 7, 2020)

    info2 = _info("GOST", "GOST 12345.6-2021")
    _post_process_foreign(info2)
    assert (info2.number, info2.part, info2.year) == (12345, 6, 2021)


def test_unique_groups_cac_itu_and_ansi_noop() -> None:
    cac = _info("CAC", "Codex Stan 123-2020")
    _post_process_foreign(cac)
    assert cac.logical_code == "Codex Stan"

    itu = _info("ITU", "ITU-T G.1-1999", year=0)
    _post_process_foreign(itu)
    assert itu.year == 1999

    ansi = _info("ANSI", "ANSI 1-2020")
    _post_process_foreign(ansi)
    assert ansi.logical_code == "ANSI"


def test_asme_special_sep_is_noop() -> None:
    info = _info("ASME", "ASME BPVC I-2020")
    _post_process_foreign(info)
    assert info.logical_code == "ASME"
