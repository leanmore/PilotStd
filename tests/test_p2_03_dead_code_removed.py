"""P2-03 批 1：两个零调用入口已移除，防止被重新加回。

不是行为测试，是删除契约：若有人重新加回，本测试会提醒先确认调用方。
"""

from pilotstd.manager.adapter_manager import AdapterManager
from pilotstd.query.engine import _constants


def test_get_fallback_chain_removed():
    assert not hasattr(_constants, "get_fallback_chain")


def test_execute_request_interval_removed():
    assert not hasattr(AdapterManager, "execute_request_interval")
