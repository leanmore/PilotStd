# tests/e2e/test_detect_ip_e2e.py
"""E2E test for detect_ip() — verifies majority-vote HTTP orchestration.

Queries ALL sources, returns most frequent valid IP (majority vote).
Provides resilience against transient source failures and poisoned responses.

Import path: pilotstd/wechat_ip/detector.py
  from pilotstd.wechat_ip.detector import detect_ip, DEFAULT_SOURCES
"""

from __future__ import annotations

import responses

from pilotstd.wechat_ip.detector import DEFAULT_SOURCES, detect_ip


def _setup_baseline():
    """Register all default sources as 500 for safe baseline."""
    for url, _extractor in DEFAULT_SOURCES:
        responses.add(responses.GET, url, status=500)


# ── 3-source majority ──────────────────────────────────────


@responses.activate
def test_detect_ip_returns_majority_ip():
    """3/4 sources agree on same IP → majority returned."""
    _setup_baseline()

    ip = "203.0.113.42"
    responses.replace(responses.GET, DEFAULT_SOURCES[0][0], body=f"{ip}\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[1][0], body=f"当前 IP: {ip} (广东)\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[2][0], body=ip, status=200)
    # Source 3 stays 500

    result = detect_ip()

    assert result == ip
    assert len(responses.calls) == len(DEFAULT_SOURCES)


# ── Split-vote determinism ─────────────────────────────────


@responses.activate
def test_detect_ip_handles_split_vote_deterministically():
    """2v2 split: result must be deterministic (first-encountered wins)."""
    _setup_baseline()

    ip_a, ip_b = "203.0.113.1", "203.0.113.2"
    responses.replace(responses.GET, DEFAULT_SOURCES[0][0], body=f"{ip_a}\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[1][0], body=f"{ip_a}\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[2][0], body=f"{ip_b}\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[3][0], body=f"{ip_b}\n", status=200)

    result = detect_ip()

    # Counter.most_common breaks ties by insertion order → ip_a (first seen) wins
    # Sorted-first matches this behavior and guards against impl changes
    expected = sorted([ip_a, ip_b])[0]
    assert result == expected, f"Split vote should return sorted-first IP, got {result}"
    assert len(responses.calls) == len(DEFAULT_SOURCES)


# ── Graceful degradation ───────────────────────────────────


@responses.activate
def test_detect_ip_returns_none_when_all_sources_fail():
    """All sources return 500 → None."""
    _setup_baseline()

    assert detect_ip() is None
    assert len(responses.calls) == len(DEFAULT_SOURCES)


@responses.activate
def test_detect_ip_filters_invalid_responses():
    """Valid HTTP but garbage body → does not pollute majority count."""
    _setup_baseline()

    ip = "203.0.113.42"
    responses.replace(responses.GET, DEFAULT_SOURCES[0][0], body=f"{ip}\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[1][0], body="not-an-ip\n", status=200)
    responses.replace(responses.GET, DEFAULT_SOURCES[2][0], body=f"{ip}\n", status=200)
    # Source 3 stays 500

    assert detect_ip() == ip
    assert len(responses.calls) == len(DEFAULT_SOURCES)
