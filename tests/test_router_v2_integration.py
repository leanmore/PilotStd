# tests/test_router_v2_integration.py
# 阶段三：路由引擎集成测试 — 灰度开关 + 单例 + 批量路径代号识别

from pilotstd.query.engine._core_types import EngineCore
from pilotstd.query.engine._routing import RoutingHandler
from pilotstd.query.routing.router_v2 import (
    get_routing_service,
    is_v2_enabled,
)


class TestFeatureFlag:
    """灰度开关测试。"""

    def test_v2_enabled_by_default(self, monkeypatch):
        """(a) 验证 2026-11-07 起默认启用 v2 (b) 无需环境变量"""
        monkeypatch.delenv("ROUTING_ENGINE_VERSION", raising=False)
        assert is_v2_enabled() is True

    def test_v2_enabled_via_env(self, monkeypatch):
        """(a) 显式 v2 仍启用 (b) 大小写/空格容错"""
        monkeypatch.setenv("ROUTING_ENGINE_VERSION", " V2 ")
        assert is_v2_enabled() is True

    def test_v2_can_rollback_via_env(self, monkeypatch):
        """(a) 部署时设置 v1 可回滚 (b) 不需要改代码"""
        monkeypatch.setenv("ROUTING_ENGINE_VERSION", "v1")
        assert is_v2_enabled() is False


class TestRoutingServiceSingleton:
    """RoutingService 单例 + 正交接口测试。"""

    def test_singleton_shared_instance(self):
        """(a) 验证 get_routing_service 返回同一实例 (b) 批量 Worker 共享配额管理器"""
        s1 = get_routing_service()
        s2 = get_routing_service()
        assert s1 is s2, "两次调用应返回同一单例实例"

    def test_orthogonal_interfaces(self):
        """(a) 验证 get_route_chain 与 consume_quota 两个正交接口 (b) 任务3.1 验收"""
        svc = get_routing_service()
        chain = svc.get_route_chain("GB/T 12345-2020")
        assert chain.sites, "国标查询应返回非空路由链"
        assert svc.consume_quota("std_gov") is True, "配额充足时应能扣减"


class TestRoutingHandlerV2:
    """批量路径 v2 代号识别测试。"""

    def _v2_handler(self, monkeypatch) -> RoutingHandler:
        """构造 v2 模式下的 RoutingHandler。"""
        monkeypatch.setenv("ROUTING_ENGINE_VERSION", "v2")
        return RoutingHandler(EngineCore())

    def test_v2_chain_gb(self, monkeypatch):
        """(a) 验证批量路径代号 GB/T 走 v2 L1 国标精准匹配 (b) 阶段二测试1"""
        handler = self._v2_handler(monkeypatch)
        chain = handler._get_priority("GB/T")
        assert chain[:3] == ["std_gov", "csres", "cssn"], f"国标应命中 std_gov/csres/cssn，实际={chain}"

    def test_v2_chain_env(self, monkeypatch):
        """(a) 验证批量路径代号 HJ 走 v2 L1 环保精准匹配 (b) 阶段二测试3"""
        handler = self._v2_handler(monkeypatch)
        chain = handler._get_priority("HJ")
        assert chain == ["mee"], f"环保标准应命中 mee，实际={chain}"

    def test_v2_chain_iso_skips_l1(self, monkeypatch):
        """(a) 验证批量路径代号 ISO 跳过 L1 走 L2 (b) 阶段二测试4 矛盾1修复"""
        handler = self._v2_handler(monkeypatch)
        chain = handler._get_priority("ISO")
        assert "iso_gov" not in chain, f"ISO 应跳过 L1 的 iso_gov，实际={chain}"
        assert chain == ["njbz365"], f"ISO 应命中全综合站 njbz365，实际={chain}"
