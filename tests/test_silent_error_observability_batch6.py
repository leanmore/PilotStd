"""静默吞错第 6 批：归档/扫描路径（体检 D-8）。

覆盖 `OrganizeHandler._backfill_std_name` 的两条静默分支：
- `standard_info_cache` 查询失败（原 `pass` → 名称静默回填失败）；
- `result_json` 非法 JSON（原 `pass` → 同上）。
其余本批改动（expire/mirror/organizer/scan 的 OSError 与缓存失效）为 debug 日志，
行为不变，由既有 organize/scan 回归覆盖。
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

from pilotstd.manager.facade._organize import OrganizeHandler


def _parsed() -> SimpleNamespace:
    return SimpleNamespace(std_name="", found_name="", logical_code="GB/T", number=1, year=2020)


def test_backfill_lookup_failure_logs(caplog) -> None:
    handler = object.__new__(OrganizeHandler)
    db = MagicMock()
    db.fetchone.side_effect = RuntimeError("db down")
    handler._core = SimpleNamespace(db=db)
    parsed = _parsed()

    with caplog.at_level(logging.DEBUG, logger="pilotstd.manager.facade._organize"):
        assert handler._backfill_std_name(parsed) is parsed
    assert "standard_info_cache lookup failed" in caplog.text


def test_backfill_invalid_json_logs(caplog) -> None:
    handler = object.__new__(OrganizeHandler)
    db = MagicMock()
    db.fetchone.return_value = {"result_json": "{not json"}
    handler._core = SimpleNamespace(db=db)
    parsed = _parsed()

    with caplog.at_level(logging.DEBUG, logger="pilotstd.manager.facade._organize"):
        assert handler._backfill_std_name(parsed) is parsed
    assert "result_json parse failed" in caplog.text
