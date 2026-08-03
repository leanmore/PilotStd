# tests/e2e/test_detect_ip_e2e.py
"""E2E test for detect_ip() — verifies HTTP orchestration with mocked sources.

Validates the I/O boundary of IP detection:
  - Mode-based consensus across all sources (no short-circuit)
  - Graceful skip of sources returning invalid content or errors
  - Graceful degradation (None) when all sources fail
"""

from __future__ import annotations

import responses

from pilotstd.wechat_ip.detector import DEFAULT_SOURCES, detect_ip


def _mock_all_sources_fail():
    """Pre-register all default sources as failing (500).

    Establishes a safe baseline: any source not explicitly replaced
    returns a controlled 500 instead of escaping as ConnectionError.
    """
    for url, _extractor in DEFAULT_SOURCES:
        responses.add(responses.GET, url, status=500)


@responses.activate
def test_detect_ip_returns_first_valid_source():
    """First source returns valid IP, others fail → mode returns that IP."""
    _mock_all_sources_fail()

    responses.replace(
        responses.GET,
        DEFAULT_SOURCES[0][0],
        body="当前 IP：203.0.113.42 （中国 广东 深圳）\n",
        status=200,
    )

    result = detect_ip()

    assert result == "203.0.113.42"
    # detect_ip 遍历全部源取众数，不短路
    assert len(responses.calls) == len(DEFAULT_SOURCES)


@responses.activate
def test_detect_ip_falls_back_on_invalid_response():
    """First source returns garbage, second returns valid IP → skips invalid."""
    _mock_all_sources_fail()

    responses.replace(
        responses.GET,
        DEFAULT_SOURCES[0][0],
        body="Service Unavailable",
        status=503,
    )
    responses.replace(
        responses.GET,
        DEFAULT_SOURCES[1][0],
        body="203.0.113.99\n",
        status=200,
    )

    result = detect_ip()

    assert result == "203.0.113.99"
    assert len(responses.calls) == len(DEFAULT_SOURCES)


@responses.activate
def test_detect_ip_returns_none_when_all_sources_fail():
    """All sources fail → None, exhausts all sources before giving up."""
    _mock_all_sources_fail()

    result = detect_ip()

    assert result is None
    assert len(responses.calls) == len(DEFAULT_SOURCES), (
        "Should try all sources before returning None"
    )
