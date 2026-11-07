"""v2 采样缺口：缓存命中/指定站点必须有 v2_skipped 记录。"""

from pilotstd.query.routing import router_v2_metrics as metrics


def test_record_v2_skip_payload(monkeypatch):
    captured = {}
    monkeypatch.setattr(metrics, "record_decision", lambda payload: captured.update(payload))

    metrics.record_v2_skip("GB/T 1234-2020", "cache_hit", "std_gov")

    assert captured["routing_version"] == "v2_skipped"
    assert captured["reason"] == "cache_hit"
    assert captured["hit_site"] == "std_gov"
    assert len(captured["query_hash"]) == 8


def test_record_v2_skip_without_hit_site(monkeypatch):
    captured = {}
    monkeypatch.setattr(metrics, "record_decision", lambda payload: captured.update(payload))

    metrics.record_v2_skip("GB/T 1234-2020", "preferred_site")

    assert captured["routing_version"] == "v2_skipped"
    assert captured["reason"] == "preferred_site"
    assert captured["hit_site"] == ""
