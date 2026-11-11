"""P2-02：死配置 validity.update_interval 已从出厂默认删除。"""

from pilotstd.core.config.defaults import FACTORY_DEFAULTS


def test_update_interval_not_in_factory_defaults():
    assert "validity.update_interval" not in FACTORY_DEFAULTS


def test_total_weeks_remains_the_source():
    assert FACTORY_DEFAULTS["validity.total_weeks"] == 4
