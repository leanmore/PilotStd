"""E2E test infrastructure — shared fixtures for HTTP-mocked integration tests.

Uses the ``responses`` library (already in requirements-dev.txt) to mock
``requests``-based HTTP calls at the adapter level.
"""

from __future__ import annotations

import pytest
import responses

collect_ignore_glob = ["../conftest.py"]


@pytest.fixture
def mocked_http():
    """Provide a ``responses`` mock router, auto-cleanup after each test.

    Usage::

        def test_something(mocked_http):
            mocked_http.get(
                "https://api.example.com/ip",
                body="1.2.3.4",
            )
            result = do_detect_ip()
            assert result == "1.2.3.4"

    ``assert_all_requests_are_fired=False`` allows partial mock usage
    (some real HTTP calls may coexist with mocked ones during migration).
    """
    with responses.RequestsMock(assert_all_requests_are_fired=False) as router:
        yield router
