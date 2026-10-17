"""有效性流水线的静默吞错（体检 D-8 第 5 批）。

- `_std_name`：查询失败原直接返回 ""（详情列表名称静默为空）；
- 周期记账失败原 pass（轮次计数/总结通知丢失无痕迹）。
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from pilotstd.core._validity_pipeline import _std_name


def test_std_name_lookup_failure_logs(caplog) -> None:
    db = MagicMock()
    db.fetchone.side_effect = RuntimeError("db down")
    with caplog.at_level(logging.DEBUG, logger="pilotstd.core._validity_pipeline"):
        assert _std_name(db, "GB/T 1-2020") == ""
    assert "std_name lookup failed" in caplog.text


def test_std_name_returns_empty_when_missing(caplog) -> None:
    db = MagicMock()
    db.fetchone.return_value = None
    assert _std_name(db, "GB/T 1-2020") == ""
