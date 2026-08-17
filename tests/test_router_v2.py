# tests/test_router_v2.py
# 阶段二：三级漏斗路由引擎 v2.0 单元测试
# 验证 v2.0 路由引擎修复 v1.0 的所有已知失效模式 + 解决三处设计矛盾

from pathlib import Path

import pytest

from pilotstd.query.routing.router_v2 import (
    IntentParser,
    QuotaManager,
    RouterEngine,
    load_capabilities,
)

# YAML 位于项目根 config/ 目录，用 __file__ 定位避免依赖运行时 cwd
_YAML_PATH = Path(__file__).parent.parent / "config" / "site_capabilities.yaml"


@pytest.fixture(scope="module")
def capabilities():
    """模块级共享：加载一次真实能力模型，避免每个测试重复读文件。"""
    return load_capabilities(str(_YAML_PATH))


@pytest.fixture
def parser():
    return IntentParser()


@pytest.fixture
def quota(capabilities):
    return QuotaManager(capabilities)


@pytest.fixture
def engine(capabilities, quota):
    return RouterEngine(capabilities, quota)


def _exhaust(quota: QuotaManager, *site_ids: str) -> None:
    """循环消耗指定站点配额直到耗尽，模拟配额满状态。"""
    for sid in site_ids:
        while quota.consume(sid):
            pass


# ── 任务 2.1：意图解析器 ──────────────────────────────────


class TestIntentParser:
    """意图解析器 5 个验收用例。"""

    def test_parse_gb_std(self, parser):
        """(a) 验证国标标准号解析 (b) 基础能力，无历史失效"""
        intent = parser.parse("GB/T 12345-2020")
        assert intent.std_type == "GB/T"
        assert intent.industry is None
        assert intent.is_international is False
        assert intent.is_keyword_query is False

    def test_parse_hj_industry(self, parser):
        """(a) 验证环保标准号同时推断领域 (b) 基础能力，无历史失效"""
        intent = parser.parse("HJ 123-2020")
        assert intent.std_type == "HJ"
        assert intent.industry == "环保"
        assert intent.is_international is False
        assert intent.is_keyword_query is False

    def test_parse_iso_international(self, parser):
        """(a) 验证国际标准号识别 (b) 基础能力，无历史失效"""
        intent = parser.parse("ISO 9001:2015")
        assert intent.std_type == "ISO"
        assert intent.industry is None
        assert intent.is_international is True
        assert intent.is_keyword_query is False

    def test_parse_keyword_industry(self, parser):
        """(a) 验证纯关键词查询识别行业 (b) 基础能力，无历史失效"""
        intent = parser.parse("食品安全管理体系")
        assert intent.std_type is None
        assert intent.industry == "食品"
        assert intent.is_international is False
        assert intent.is_keyword_query is True

    def test_parse_unknown_fallback(self, parser):
        """(a) 验证无法识别时的兜底 (b) 基础能力，无历史失效"""
        intent = parser.parse("随机无意义字符串")
        assert intent.std_type is None
        assert intent.industry is None
        assert intent.is_international is False
        assert intent.is_keyword_query is True


# ── 任务 2.4：路由引擎 6 个核心用例 ────────────────────────


class TestRouterEngine:
    """三级漏斗路由引擎 6 个验收用例。"""

    def test_gb_exact_match_l1(self, parser, engine):
        """(a) 验证国标精准匹配走 L1 (b) 基础 L1 功能，无历史失效"""
        chain = engine.route(parser.parse("GB/T 12345"))
        assert chain.sites[:3] == ["std_gov", "csres", "cssn"], f"L1 命中应为国标站，实际={chain.sites}"

    def test_gb_quota_exhausted_fallback_l2(self, parser, quota, engine):
        """(a) 验证国标 L1 全满后降级 L2 (b) 修复 v1.0 核心失效：国标查询误路由到 mee"""
        _exhaust(quota, "std_gov", "csres", "cssn")
        chain = engine.route(parser.parse("GB/T 12345"))
        # 核心断言：mee 绝不在路由链中
        assert "mee" not in chain.sites, f"国标查询绝不能路由到 mee，实际链={chain.sites}"
        # L2 综合站兜底
        assert "ahbz" in chain.sites or "njbz365" in chain.sites, f"L2 应命中综合站，实际={chain.sites}"
        assert any("L2" in d for d in chain.decisions), f"应记录 L2 降级决策，实际={chain.decisions}"

    def test_env_exact_match_l1(self, parser, engine):
        """(a) 验证环保标准精准匹配 mee (b) 特色站精准路由，无历史失效"""
        chain = engine.route(parser.parse("HJ 123-2020"))
        assert "mee" in chain.sites, f"环保标准应命中 mee，实际={chain.sites}"

    def test_international_route_skips_l1(self, parser, engine):
        """(a) 验证国际标准跳过 L1 走 L2 (b) 修复设计矛盾1：ISO 查询不应命中 iso_gov"""
        chain = engine.route(parser.parse("ISO 9001"))
        # L1 站点列表为空：iso_gov 不在链中（L1 被跳过）
        assert "iso_gov" not in chain.sites, f"ISO 查询应跳过 L1，实际={chain.sites}"
        # L2 命中全综合站 njbz365
        assert "njbz365" in chain.sites, f"ISO 查询应命中 njbz365，实际={chain.sites}"
        assert all("L2" in d for d in chain.decisions), f"决策应全部为 L2，实际={chain.decisions}"

    def test_keyword_exploration_l3(self, parser, engine):
        """(a) 验证纯关键词跳过 L1/L2 直接 L3 (b) 修复设计矛盾2：关键词不应走 L2"""
        chain = engine.route(parser.parse("食品安全管理体系"))
        # L2 站点列表为空：国内综合站均不在链中
        for l2_site in ("ahbz", "hbba", "gongbiaoku"):
            assert l2_site not in chain.sites, f"纯关键词应跳过 L2 的 {l2_site}，实际={chain.sites}"
        # L3 命中全综合站
        assert "njbz365" in chain.sites, f"L3 应命中全综合站，实际={chain.sites}"
        assert all("low_confidence_exploration" in d for d in chain.decisions), "L3 决策应含低置信标记"

    def test_l2_reliability_sort(self, parser, quota, engine):
        """(a) 验证 L2 按 reliability 权重排序 (b) 修复设计矛盾3：medium 应排在 unknown 之前"""
        _exhaust(quota, "std_gov", "csres", "cssn")
        chain = engine.route(parser.parse("GB/T 12345"))
        sites = chain.sites
        assert "gongbiaoku" in sites and "ahbz" in sites, f"L2 应含 gongbiaoku 和 ahbz，实际={sites}"
        # gongbiaoku(medium=0.6) 排在 ahbz(unknown=0.0) 之前
        assert sites.index("gongbiaoku") < sites.index("ahbz"), (
            f"gongbiaoku(medium) 应排在 ahbz(unknown) 之前，实际={sites}"
        )


class TestLoadCapabilities:
    """能力模型加载完整性。"""

    def test_loads_all_21_sites(self, capabilities):
        """验证 YAML 加载出完整 21 个站点。"""
        assert len(capabilities) == 21, f"应加载 21 个站点，实际={len(capabilities)}"
        ids = {s.site_id for s in capabilities}
        assert len(ids) == 21, f"站点 ID 不应重复，实际={len(ids)}"

    def test_mee_excludes_gb(self, capabilities):
        """验证 mee 能力模型已修正（阶段一产出）：supported_types 不含 GB。"""
        mee = next(s for s in capabilities if s.site_id == "mee")
        assert "GB" not in mee.capabilities.supported_types, f"mee 不应含 GB，实际={mee.capabilities.supported_types}"


# ── 任务 2.3：动态配额管理器 ──────────────────────────────


class TestQuotaManager:
    """配额管理器验收：层级过滤 + 配额消耗 + 溢出控制。"""

    def test_layer_filtering(self, quota, parser):
        """(a) 验证 L1/L2/L3 层级过滤正确 (b) 三层漏斗的基础边界"""
        intent = parser.parse("GB/T 12345")
        l1 = quota.get_available_sites("L1", intent)
        l2 = quota.get_available_sites("L2", intent)
        l3 = quota.get_available_sites("L3", intent)
        assert all(s.classification.level1 == "特色" for s in l1), "L1 应全是特色站"
        assert all(s.classification.level2 in ("国内综合", "全综合") for s in l2), "L2 应全是综合站"
        assert all(s.classification.level2 == "全综合" for s in l3), "L3 应全是全综合站"

    def test_consume_exhausted_returns_false(self, quota):
        """(a) 验证配额耗尽后 consume 返回 False (b) 配额硬上限生效"""
        # csres 的 batch_limit=10，快速耗尽
        for _ in range(10):
            assert quota.consume("csres") is True
        assert quota.consume("csres") is False, "耗尽后 consume 应返回 False"

    def test_is_exhausted(self, quota):
        """(a) 验证 is_exhausted 判定 (b) 未知站点视为已耗尽"""
        assert quota.is_exhausted("csres") is False
        _exhaust(quota, "csres")
        assert quota.is_exhausted("csres") is True
        assert quota.is_exhausted("nonexistent") is True

    def test_get_available_sites_excludes_exhausted(self, quota, parser):
        """(a) 验证配额满的站点被排除 (b) 无跨层自动溢出，只返回本层未满站点"""
        intent = parser.parse("GB/T 12345")
        _exhaust(quota, "std_gov")
        l1_ids = [s.site_id for s in quota.get_available_sites("L1", intent)]
        assert "std_gov" not in l1_ids, f"耗尽后 std_gov 不应出现在 L1 可用列表，实际={l1_ids}"
