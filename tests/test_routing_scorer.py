# tests/test_routing_scorer.py
# Phase 3.1: 路由评分器单元测试（≥15 个用例）

import time

from pilotstd.query.routing.scorer import (
    _collect_runtime_state,
    extract_keywords,
    get_priority_chain,
    get_profile,
    score_adapter,
)


class TestExtractKeywords:
    """关键词提取测试。"""

    def test_std_prefix_gb(self):
        """标准号前缀提取：GB → ['GB']"""
        kw = extract_keywords("GB 12345-2020")
        assert "GB" in kw

    def test_std_prefix_iso(self):
        """标准号前缀提取：ISO → ['ISO']"""
        kw = extract_keywords("ISO 9001-2015")
        assert "ISO" in kw

    def test_industry_energy(self):
        """行业关键词匹配：光伏 → energy 行业"""
        kw = extract_keywords("光伏电站设计规范")
        assert "能源" in kw

    def test_industry_transport(self):
        """行业关键词匹配：JT → 交通"""
        kw = extract_keywords("JT 1234-2020")
        assert "交通" in kw

    def test_no_match(self):
        """无匹配查询词返回空列表或仅通用匹配"""
        kw = extract_keywords("xyz123")
        # 无标准号前缀，无行业关键词
        assert len(kw) == 0


class TestScoreAdapter:
    """适配器评分核心逻辑测试。"""

    def test_prefix_match_boost(self):
        """标准号前缀匹配：GB 查询 std_gov 应加分 ≥ 90（base:70 + prefix:30 - general:10）"""
        result = score_adapter("std_gov", "GB 12345-2020")
        assert result.score >= 90, f"预期≥90，实际{result.score}，原因={result.reasons}"
        assert any("prefix_match" in r for r in result.reasons)

    def test_industry_match_boost(self):
        """行业关键词匹配：光伏查询 energy 应加分 ≥ 70（base:50 + industry:20）"""
        result = score_adapter("energy", "光伏电站设计规范")
        assert result.score >= 70, f"预期≥70，实际{result.score}，原因={result.reasons}"
        assert any("industry_match" in r for r in result.reasons)

    def test_general_adapter_penalty(self):
        """通用适配器降权：std_gov(is_general=True) 分数应低于 匹配的专业适配器"""
        gen = score_adapter("std_gov", "HJ 1234-2020")
        prof = score_adapter("mee", "HJ 1234-2020")
        # mee 是专业环保适配器，应比通用 std_gov 分高
        assert prof.score > gen.score, f"专业适配器 mee({prof.score}) 应 > 通用适配器 std_gov({gen.score})"

    def test_daily_limit_exhausted(self):
        """日限额耗尽 → 分数为 0"""
        result = score_adapter("std_gov", "GB 1-2020", {"daily_used": 1000})
        assert result.score == 0, f"预期0，实际{result.score}"
        assert "daily_limit_exhausted" in result.reasons

    def test_in_cooldown(self):
        """冷却中 → 分数为 0"""
        future = time.time() + 3600  # 1小时后才恢复
        result = score_adapter("std_gov", "GB 1-2020", {"cooldown_until": future})
        assert result.score == 0, f"预期0，实际{result.score}"
        assert "in_cooldown" in result.reasons

    def test_batch_limit_hit(self):
        """批次已满 → 分数为 0"""
        result = score_adapter("std_gov", "GB 1-2020", {"current_batch_count": 200})
        assert result.score == 0, f"预期0，实际{result.score}"
        assert "batch_limit_hit" in result.reasons

    def test_csres_not_excluded_by_scorer(self):
        """评分器不排除 csres：csres 应返回分数 > 0"""
        result = score_adapter("csres", "GB 12345-2020")
        assert result.score > 0, f"评分器不应排除 csres，实际分数={result.score}"
        # csres 的排除逻辑在 _routing.py 硬编码层处理

    def test_unknown_adapter_zero(self):
        """未知适配器 → 分数为 0"""
        result = score_adapter("nonexistent", "GB 1-2020")
        assert result.score == 0
        assert "adapter_not_found" in result.reasons

    def test_iso_routes_to_iso_gov(self):
        """ISO 标准 → iso_gov 应在链中且分数高"""
        result = score_adapter("iso_gov", "ISO 9001-2015")
        assert result.score >= 80, f"ISO→iso_gov 预期≥80，实际{result.score}"

    def test_db_routes_to_dbba(self):
        """DB 标准 → dbba 应在链中且分数高"""
        result = score_adapter("dbba", "DB11/T 1234-2020")
        assert result.score >= 80, f"DB→dbba 预期≥80，实际{result.score}"

    def test_food_safety_to_sppt(self):
        """食品标准 → sppt 应优先"""
        sppt_score = score_adapter("sppt", "食品添加剂 GB 2760")
        gen_score = score_adapter("std_gov", "食品添加剂 GB 2760")
        assert sppt_score.score > gen_score.score, f"sppt({sppt_score.score}) 应 > std_gov({gen_score.score})"

    def test_measurement_to_jjg(self):
        """计量标准 → jjg 应优先"""
        result = score_adapter("jjg", "JJG 123-2020")
        assert result.score >= 80, f"计量→jjg 预期≥80，实际{result.score}"

    def test_railway_to_tdpress(self):
        """铁路标准 → tdpress 应优先"""
        result = score_adapter("tdpress", "TB 1234-2020")
        assert result.score >= 80, f"铁路→tdpress 预期≥80，实际{result.score}"

    def test_cultural_to_ncha(self):
        """文物标准 → ncha 应优先"""
        result = score_adapter("ncha", "WW/T 1234-2020")
        assert result.score >= 80, f"文物→ncha 预期≥80，实际{result.score}"


class TestGetPriorityChain:
    """优先级链集成测试。"""

    def test_chain_non_empty(self):
        """空查询兜底：任何查询词都应返回非空链"""
        chain = get_priority_chain("xyz123")
        assert len(chain) > 0, "空查询应返回非空链（兜底）"

    def test_chain_gb_includes_std_gov(self):
        """GB 查询 → 链包含 std_gov"""
        chain = get_priority_chain("GB 12345-2020")
        assert "std_gov" in chain, f"GB查询链应包含std_gov，实际={chain}"

    def test_chain_iso_includes_iso_gov(self):
        """ISO 查询 → 链包含 iso_gov"""
        chain = get_priority_chain("ISO 9001-2015")
        assert "iso_gov" in chain, f"ISO查询链应包含iso_gov，实际={chain}"

    def test_daily_exhausted_not_in_chain(self):
        """日限额耗尽 → 不在链中"""
        runtime = {"std_gov": {"daily_used": 1000, "cooldown_until": 0, "current_batch_count": 0}}
        chain = get_priority_chain("GB 12345-2020", runtime)
        assert "std_gov" not in chain, f"日限额耗尽的std_gov不应在链中，实际={chain}"

    def test_cooling_not_in_chain(self):
        """冷却中 → 不在链中"""
        future = time.time() + 3600
        runtime = {"std_gov": {"daily_used": 0, "cooldown_until": future, "current_batch_count": 0}}
        chain = get_priority_chain("GB 12345-2020", runtime)
        assert "std_gov" not in chain, f"冷却中的std_gov不应在链中，实际={chain}"


class TestGetProfile:
    """画像读取测试。"""

    def test_profile_exists(self):
        """已知适配器返回非空画像"""
        p = get_profile("std_gov")
        assert p, "std_gov 画像不应为空"
        assert p.get("label"), "应有 label 字段"
        assert "rate_limit" in p, "应有 rate_limit 子字典"

    def test_profile_unknown_returns_empty(self):
        """未知适配器返回空字典"""
        p = get_profile("nonexistent")
        assert p == {}


class TestCollectRuntimeState:
    """运行时状态收集测试。"""

    def test_empty(self):
        """无 rotator/quota 时返回空字典"""
        state = _collect_runtime_state(None, None)
        assert state == {}
