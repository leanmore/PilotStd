"""query/__init__.py 补测 — 懒加载适配器函数。"""
import pytest


class TestLazyLoader:
    def test_get_csres_adapter(self):
        from pilotstd.query import _get_csres_adapter
        cls = _get_csres_adapter()
        assert cls.__name__ == "CsresAdapter"

    def test_get_njbz365_adapter(self):
        from pilotstd.query import _get_njbz365_adapter
        cls = _get_njbz365_adapter()
        assert cls.__name__ == "Njbz365Adapter"

    def test_get_hbba_adapter(self):
        from pilotstd.query import _get_hbba_adapter
        cls = _get_hbba_adapter()
        assert cls.__name__ == "HbbaAdapter"

    def test_get_iso_gov_adapter(self):
        from pilotstd.query import _get_iso_gov_adapter
        cls = _get_iso_gov_adapter()
        assert cls.__name__ == "IsoGovAdapter"

    def test_get_ttbz_adapter(self):
        from pilotstd.query import _get_ttbz_adapter
        cls = _get_ttbz_adapter()
        assert cls.__name__ == "TTBZAdapter"

    def test_get_mock_adapter_returns_class_or_none(self):
        from pilotstd.query import _get_mock_adapter
        result = _get_mock_adapter()
        assert result is None or hasattr(result, "__name__")

    def test_top_level_exports(self):
        import pilotstd.query as q
        assert q.QueryResult is not None
        assert q.QueryEngine is not None
        assert q.SiteRotator is not None
