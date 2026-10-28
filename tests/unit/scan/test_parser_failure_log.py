"""A-9：解析失败日志四段化（path/type/error/detail）回归。"""

import logging

from pilotstd.scan.parser import StandardParser


def test_parse_failure_log_has_four_fields(caplog) -> None:
    parser = StandardParser({})
    with caplog.at_level(logging.INFO, logger="pilotstd.scan.parser"):
        assert parser.parse("___unmatchable___.xyz") is None

    msg = caplog.text
    assert "path=___unmatchable___.xyz" in msg
    assert "type=.xyz" in msg
    assert "error=no_match" in msg
    assert "detail=8_matchers" in msg
