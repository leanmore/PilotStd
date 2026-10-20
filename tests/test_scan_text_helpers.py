"""D-13 P1：版次识别与文件名规范化正则的直测覆盖。"""

from __future__ import annotations

from pilotstd.scan.edition_detect import edition_skip_pattern, extract_edition

# 导入即执行模块级正则编译；同时验证每个正则至少能命中真实样本
from pilotstd.scan.filename_normalizer import (
    _EDITION_ALL,
    _EDITION_HYBRID,
    _EN_CN_CODE,
    _EN_MARK,
    _EXTRA_DESC,
    _ZH_MARK,
)


def test_extract_edition_variants() -> None:
    assert extract_edition("标准 第10版", "中文版") == "第10版"
    assert extract_edition("standard 10th edition", "英文版") == "10th"
    assert extract_edition("standard 10th edition", "中文版") == "第10版"
    assert extract_edition("standard Tenth Edition", "英文版") == "Tenth Edition"
    assert extract_edition("standard Tenth Edition", "中文版") == "第10版"
    assert extract_edition("no match here", "英文版") == ""
    assert edition_skip_pattern()


def test_filename_normalizer_patterns_match_samples() -> None:
    assert _ZH_MARK.search("GB 1-2020 中文版")
    assert _EN_MARK.search("GB 1-2020 (English)")
    assert _EN_CN_CODE.search("GB 1-2020_CN")
    assert _EDITION_ALL.search("GB 1-2020 第2版")
    assert _EDITION_HYBRID.search("GB 1-2020_5th_中文版")
    assert _EXTRA_DESC.search("GB 1-2020 +中英对照")
