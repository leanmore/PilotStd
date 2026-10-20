"""D-13 P1：ExactMatcher 的错误/回退分支覆盖（正常解析由 test_scanner 覆盖）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pilotstd.scan.parser._exact_matcher import ExactMatcher


def _match(**groups):
    groups = {str(k): v for k, v in groups.items()}
    m = MagicMock()
    m.group.side_effect = lambda key: groups.get(str(key))
    m.end.return_value = 10
    return m


def _parser() -> MagicMock:
    p = MagicMock()
    p.code_mapping = {"GB": "GB"}
    p._normalize_year.return_value = 2020
    p._clean_std_name.side_effect = lambda s: s.strip()
    p._validate_result.return_value = True
    p._trim_prefix.side_effect = lambda prefix, text: prefix
    p._extract_number.return_value = (1, "", "1")
    p._extract_num_prefix.return_value = ""
    p._extract_part.return_value = None
    p._build_result.return_value = SimpleNamespace(logical_code="GB")
    return p


def _matcher(parser=None) -> ExactMatcher:
    parser = parser or _parser()
    parser.regex = MagicMock()
    parser.regex_no_year = MagicMock()
    parser.regex_typed = MagicMock()
    parser.regex_typed_v2 = MagicMock()
    parser.regex_db = MagicMock()
    return ExactMatcher(parser)


def test_db_invalid_number_and_validation_failure() -> None:
    m = _matcher()
    m.regex_db.match.return_value = _match(code="11", type="T", number="abc", year="2020")
    assert m._exact_match_db("DB11/T abc-2020") is None

    m.regex_db.match.return_value = _match(code="11", type="T", number="1", year="2020")
    m._parser._validate_result.return_value = False
    assert m._exact_match_db("DB11/T 1-2020") is None


def test_group_invalid_number_and_validation_failure() -> None:
    m = _matcher()
    m._parser._validate_result.return_value = False
    assert m._build_group_result("T/X 1-2020", _match(org="X", number="1", year="2020"), "T/X") is None

    m._parser._validate_result.return_value = True
    assert m._build_group_result("T/X abc-2020", _match(org="X", number="abc", year="2020"), "T/X") is None


def test_bpvc_unknown_roman_and_validation_failure() -> None:
    m = _matcher()
    with patch("pilotstd.scan.parser._exact_matcher._ASME_BPVC_RE") as regex:
        regex.match.return_value = _match(**{"1": "ZZZ", "2": None, "3": "2020"})
        assert m._exact_match_bpvc("ASME ZZZ-2020") is None

    with patch("pilotstd.scan.parser._exact_matcher._ASME_BPVC_RE") as regex:
        regex.match.return_value = _match(**{"1": "I", "2": None, "3": "2020"})
        m._parser._validate_result.return_value = False
        assert m._exact_match_bpvc("ASME I-2020") is None


def test_itu_validation_failure() -> None:
    m = _matcher()
    m._parser._validate_result.return_value = False
    assert m._exact_match_itu("ITU-T G.992.1-1999") is None


def test_exact_match_number_none() -> None:
    m = _matcher()
    m.regex.match.return_value = _match(prefix="GB", number="1", part=None, year="2020")
    m._parser._extract_number.return_value = (None, "", "")
    assert m._exact_match("GB 1-2020") is None


def test_no_year_number_none_and_missing_suffix() -> None:
    m = _matcher()
    m.regex_no_year.match.return_value = _match(prefix="MIL", number="1", part=None)
    m._parser._extract_number.return_value = (None, "", "")
    assert m._exact_match_no_year("MIL 1") is None

    m._parser._extract_number.return_value = (1, "", "1")
    assert m._exact_match_no_year("MIL 1") is None


def test_typed_fallback_and_endorser() -> None:
    m = _matcher()
    m.regex_typed.match.return_value = None
    m.regex_typed_v2.match.return_value = _match(
        prefix="GB", number="1", part=None, year="2020", endorser="EN"
    )
    m._parser._build_result.return_value = SimpleNamespace(logical_code="GB/EN")
    result = m._exact_match_typed("GB 1-2020 EN")
    assert result is not None
    assert m.regex_typed_v2.match.called

    m.regex_typed_v2.match.return_value = _match(prefix="GB", number="1", part=None, year="2020", endorser=None)
    m._parser._extract_number.return_value = (None, "", "")
    assert m._exact_match_typed("GB 1-2020") is None


def test_fuzzy_early_returns() -> None:
    m = _matcher()
    assert m._fuzzy_match_with_context("no year here") is None
    assert m._fuzzy_match_with_context("GB 2020") is None
    assert m._fuzzy_match_with_context("1234 2020") is None

    m._parser._validate_result.return_value = False
    assert m._fuzzy_match_with_context("GB 1234 2020") is None
