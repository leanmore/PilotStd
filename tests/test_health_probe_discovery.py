"""G-25：探针自动发现的第二数据源兜底（2026-11-24）。

背景：G-25 记录「探针自动发现**已执行未改善**」（found 6 / probe_pending 11，
覆盖率卡在 60%）。根因是一个**死循环**：

  `discover_probes()` 只从 `standard_info_cache` 的 exact 记录发现探针，
  而该表**只存"曾经查成功过"的站点** —— 一个站点若从未查成功，
  就永远没有 exact 缓存，于是永远 `probe_pending`。

修法：加第二数据源 `file_index` 表（已归档的真实标准号）作为兜底。
探针只需要一个「该站点理论上应该能查到」的标准号来验证可达性，
不需要该站点的历史成功记录。

本测试锁住：
  1. 数据源 1（exact 缓存）优先，不被兜底覆盖
  2. 数据源 1 未覆盖的站点，用 `file_index` 表兜底
  3. 两表都空时返回空（不伪造探针）
  4. 兜底探针格式正确（`CODE NUMBER-YEAR`）
  5. 数据库异常时不抛、返回已发现部分

注：`discover_probes()` 内部 `from pilotstd.core.db import Database`（函数内导入），
故用 `patch.dict(sys.modules, ...)` 替换 `pilotstd.core.db` 模块的 `Database` 属性。
"""

import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pilotstd.query import health_probe  # noqa: E402


def _patch_db(cache_rows, file_index_rows):
    """按 SQL 分流返回假数据：替换 `pilotstd.core.db.Database`。"""

    class _FakeDB:
        def __init__(self, *_a, **_kw):
            pass

        def fetchall(self, sql, params=()):
            if "standard_info_cache" in sql:
                return cache_rows
            if "FROM file_index" in sql:
                return file_index_rows
            return []

    fake_mod = types.ModuleType("pilotstd.core.db")
    fake_mod.Database = _FakeDB  # type: ignore[attr-defined]
    return patch.dict(sys.modules, {"pilotstd.core.db": fake_mod})


def test_exact_cache_takes_priority():
    """数据源 1 命中的站点不被兜底覆盖。"""
    cache = [{"source_site": "ccsn", "standard_number": "GB/T 1234-2020"}]
    fi = [{"logical_code": "GB", "number": 9999, "year": 2019}]

    with _patch_db(cache, fi):
        found = health_probe.discover_probes()

    assert found["ccsn"] == "GB/T 1234-2020"  # 用 exact 记录，不是兜底


def test_fallback_covers_sites_without_cache():
    """数据源 1 未覆盖的站点，用 file_index 表兜底。"""
    cache: list[dict] = []  # 无任何 exact 缓存（G-25 的死循环场景）
    fi = [{"logical_code": "GB", "number": 50011, "year": 2010}]

    with _patch_db(cache, fi):
        found = health_probe.discover_probes()

    # 所有 probe_pending 站点都应拿到探针（不再永久 pending）
    assert set(found) == set(health_probe.PROBE_PENDING)
    assert all(v == "GB 50011-2010" for v in found.values())


def test_fallback_format_without_year():
    """year 缺失时探针格式为 `CODE NUMBER`（不多余的连字符）。"""
    with _patch_db([], [{"logical_code": "GB", "number": 50011, "year": None}]):
        found = health_probe.discover_probes()

    assert found["ccsn"] == "GB 50011"


def test_both_sources_empty_returns_empty():
    """两表都空 → 返回空，不伪造探针。"""
    with _patch_db([], []):
        found = health_probe.discover_probes()

    assert found == {}


def test_discovery_failure_does_not_raise():
    """数据库异常时返回空（不抛异常、不阻断主流程）。"""

    class _BoomDB:
        def __init__(self, *_a, **_kw):
            pass

        def fetchall(self, *_a, **_kw):
            raise RuntimeError("db down")

    fake_mod = types.ModuleType("pilotstd.core.db")
    fake_mod.Database = _BoomDB  # type: ignore[attr-defined]
    with patch.dict(sys.modules, {"pilotstd.core.db": fake_mod}):
        found = health_probe.discover_probes()

    assert found == {}


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
