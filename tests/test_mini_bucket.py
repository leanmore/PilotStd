"""_mini_bucket.py 补测 — 使用 mini_bucket_mock_tree。"""
from unittest.mock import MagicMock, patch

from pilotstd.query.engine._mini_bucket import MiniBucketHandler, _apply_request_interval
from tests.fixtures.engine_mock_tree import mini_bucket_mock_tree


class TestApplyRequestInterval:
    def test_with_interval(self):
        rot = MagicMock()
        rot._sites = {"test": MagicMock()}
        rot._sites["test"].request_interval = 0.5
        ctx = {"metrics": MagicMock()}
        with patch("pilotstd.query.engine._mini_bucket.time.sleep") as m:
            _apply_request_interval(rot, "test", ctx)
            m.assert_called_once()

    def test_no_interval(self):
        rot = MagicMock()
        rot._sites = {"test": MagicMock()}
        rot._sites["test"].request_interval = 0
        _apply_request_interval(rot, "test", {})

    def test_no_rotator(self):
        _apply_request_interval(None, "x", {})

    def test_no_metrics(self):
        rot = MagicMock()
        rot._sites = {"t": MagicMock()}
        rot._sites["t"].request_interval = 1.0
        with patch("pilotstd.query.engine._mini_bucket.time.sleep"):
            _apply_request_interval(rot, "t", {})


class TestMiniBucketHandler:
    def test_init(self):
        with mini_bucket_mock_tree() as (core, routing, single):
            h = MiniBucketHandler(core, routing, single)
            assert h._core is core
            assert h._MINI_BUCKET_SIZE == 50
            assert h._MINI_BUCKET_STAGGER == 5

    def test_build_buckets_no_weights(self):
        with mini_bucket_mock_tree() as (core, routing, single):
            h = MiniBucketHandler(core, routing, single)
            items = list(range(120))
            chain = ["site_a", "site_b"]
            buckets = h._build_mini_buckets(items, chain, None)
            assert len(buckets) >= 1
            for name, bucket_items in buckets:
                assert name in chain
                assert len(bucket_items) <= 50

    def test_build_buckets_with_weights(self):
        with mini_bucket_mock_tree() as (core, routing, single):
            h = MiniBucketHandler(core, routing, single)
            items = list(range(100))
            chain = ["a", "b"]
            weights = [60, 40]
            buckets = h._build_mini_buckets(items, chain, weights)
            assert len(buckets) >= 1

    def test_build_buckets_cooled_site(self):
        with mini_bucket_mock_tree({"a": {"cooldown_until": 9e99}}) as (core, routing, single):
            h = MiniBucketHandler(core, routing, single)
            items = list(range(50))
            chain = ["a", "b"]
            weights = [50, 50]
            buckets = h._build_mini_buckets(items, chain, weights)
            for name, _ in buckets:
                assert name != "a"
