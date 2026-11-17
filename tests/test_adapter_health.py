"""适配器健康检查 + A-47 默认结果分类测试。"""

from __future__ import annotations

from pilotstd.query import health_probe
from pilotstd.query.engine._batch_dispatcher import pending_fallback_result


class _Found:
    def is_found(self) -> bool:
        return True


class _FakeAdapter:
    def query_standards(self, number: str):
        return [_Found()]


class _ErrorAdapter:
    def query_standards(self, number: str):
        raise RuntimeError("boom")


def test_pending_fallback_is_chain_exhausted():
    result = pending_fallback_result(("GB/T", 1, 2020, "x"))
    assert result.status == "待确认"
    assert result.match_status == "chain_exhausted"


def test_health_probe_found_and_error(monkeypatch, tmp_path):
    monkeypatch.setattr(health_probe, "PROBES", {"fake": "GB/T 1-2020", "bad": "GB/T 2-2020"})
    monkeypatch.setattr(health_probe, "PROBE_PENDING", {})
    monkeypatch.setattr(health_probe, "_HEALTH_FILE", str(tmp_path / "health.json"))
    monkeypatch.setattr(
        "pilotstd.query.adapters.registry.ALL_ADAPTERS",
        {"fake": _FakeAdapter, "bad": _ErrorAdapter},
    )
    result = health_probe.run_health_check(timeout=2)
    by_site = {r["site"]: r for r in result["results"]}
    assert by_site["fake"]["status"] == "found"
    assert by_site["bad"]["status"] == "error"
    assert result["summary"] == {"found": 1, "no_result": 0, "error": 1, "probe_pending": 0}
    assert (tmp_path / "health.json").exists()


def test_probe_one_direct_install(monkeypatch):
    monkeypatch.setattr(
        "pilotstd.query.adapters.registry.ALL_ADAPTERS",
        {"fake": _FakeAdapter, "bad": _ErrorAdapter},
    )
    ok = health_probe._probe_one("fake", "GB/T 1-2020", 2)
    bad = health_probe._probe_one("bad", "GB/T 2-2020", 2)
    assert ok["status"] == "found" and ok["elapsed_ms"] >= 0
    assert bad["status"] == "error" and "boom" in bad["error"]
