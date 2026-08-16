# tests/test_search_url.py — get_search_url() 回退链边界测试
from unittest.mock import patch

from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.rotator import SiteState


class _DummyAdapter(BaseAdapter):
    """测试用具体适配器（BaseAdapter 为抽象类，不可直接实例化）。"""

    @property
    def site_name(self) -> str:
        return "dummy"

    @property
    def site_label(self) -> str:
        return "Dummy"


class TestUrlFallback:
    """验证 get_search_url() 回退链：配置 search_url > 硬编码 > base_url。"""

    def test_configured_search_url(self):
        adapter = _DummyAdapter()
        with patch("pilotstd.query.site_config.get_site_config") as mock:
            mock.return_value = SiteState(name="dummy", base_url="http://base", search_url="http://config")
            assert adapter.get_search_url() == "http://config"

    def test_empty_search_url_falls_back_to_hardcoded(self):
        adapter = _DummyAdapter()
        adapter.SEARCH_URL = "http://hardcoded"
        with patch("pilotstd.query.site_config.get_site_config") as mock:
            mock.return_value = SiteState(name="dummy", base_url="http://base", search_url="")
            assert adapter.get_search_url() == "http://hardcoded"

    def test_none_config_falls_back_to_hardcoded(self):
        adapter = _DummyAdapter()
        adapter.SEARCH_URL = "http://hardcoded"
        with patch("pilotstd.query.site_config.get_site_config") as mock:
            mock.return_value = None
            assert adapter.get_search_url() == "http://hardcoded"

    def test_ultimate_fallback_to_base_url(self):
        adapter = _DummyAdapter()
        with patch("pilotstd.query.site_config.get_site_config") as mock:
            mock.return_value = SiteState(name="dummy", base_url="http://base", search_url="")
            assert adapter.get_search_url() == "http://base"
