# tests/test_engine_single.py
"""SingleQueryHandler 5 步搜索链路单元测试。

覆盖 _single.py 中从 _query_one 提取的 5 个独立方法：
_step_cache_lookup / _step_get_priority_chain / _step_query_adapters
/ _step_quota_exhausted / _step_not_found
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pilotstd.query.engine._single import SingleQueryHandler
from pilotstd.query.models import QueryResult


# ── 辅助工厂 ──

def _make_adapter(name: str, label: str = "", found_result: QueryResult | None = None):
    """用 type() 动态构造 mock 适配器，只暴露 _single.py 需要的属性。"""
    return type(
        f"_Mock{name}",
        (),
        {
            "site_name": name,
            "site_label": label or name,
            "query_with_strategy": lambda self, *a, found=found_result, **kw: found,
        },
    )()


def _make_handler(core=None, routing=None):
    """构造 SingleQueryHandler，注入 mock core 和 routing。"""
    if core is None:
        core = MagicMock()
    if routing is None:
        routing = MagicMock()
    return SingleQueryHandler(core=core, routing=routing)


# ═══════════════════════════════════════════════════════════════
# Step 1: _step_cache_lookup
# ═══════════════════════════════════════════════════════════════

class TestStepCacheLookup(unittest.TestCase):
    """_step_cache_lookup — 缓存查找"""

    def setUp(self):
        self.handler = _make_handler()
        self.target = "GB/T 19001-2020"

    def test_hit_first_adapter(self):
        """首个适配器缓存命中即返回"""
        cached = QueryResult(standard_number=self.target, standard_name="质量管理体系")
        adp1 = _make_adapter("site_a")
        adp2 = _make_adapter("site_b")
        cache = MagicMock()
        cache.get.return_value = cached

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp1, adp2],
            cache=cache,
            use_cache=True,
            force_refresh=False,
        )
        self.assertIs(result, cached)

    def test_hit_second_adapter(self):
        """首个适配器未命中，第二个命中"""
        cached = QueryResult(standard_number=self.target, standard_name="质量管理体系")
        adp1 = _make_adapter("site_a")
        adp2 = _make_adapter("site_b")
        cache = MagicMock()
        cache.get.side_effect = [None, cached]

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp1, adp2],
            cache=cache,
            use_cache=True,
            force_refresh=False,
        )
        self.assertIs(result, cached)

    def test_miss_all_adapters(self):
        """所有适配器均未命中返回 None"""
        adp1 = _make_adapter("site_a")
        adp2 = _make_adapter("site_b")
        cache = MagicMock()
        cache.get.return_value = None

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp1, adp2],
            cache=cache,
            use_cache=True,
            force_refresh=False,
        )
        self.assertIsNone(result)

    def test_use_cache_false_skips(self):
        """use_cache=False 时直接返回 None，不调用 cache.get"""
        adp = _make_adapter("site_a")
        cache = MagicMock()

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp],
            cache=cache,
            use_cache=False,
            force_refresh=False,
        )
        self.assertIsNone(result)
        cache.get.assert_not_called()

    def test_force_refresh_skips(self):
        """force_refresh=True 时跳过缓存"""
        adp = _make_adapter("site_a")
        cache = MagicMock()

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp],
            cache=cache,
            use_cache=True,
            force_refresh=True,
        )
        self.assertIsNone(result)
        cache.get.assert_not_called()

    def test_preferred_site_skips(self):
        """指定 preferred_site 时跳过缓存"""
        adp = _make_adapter("site_a")
        cache = MagicMock()

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp],
            cache=cache,
            use_cache=True,
            force_refresh=False,
            preferred_site="site_b",
        )
        self.assertIsNone(result)
        cache.get.assert_not_called()

    def test_cache_is_none(self):
        """cache 为 None 时安全返回 None"""
        adp = _make_adapter("site_a")

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[adp],
            cache=None,
            use_cache=True,
            force_refresh=False,
        )
        self.assertIsNone(result)

    def test_empty_adapters(self):
        """适配器列表为空时返回 None"""
        cache = MagicMock()

        result = self.handler._step_cache_lookup(
            target=self.target,
            adapters=[],
            cache=cache,
            use_cache=True,
            force_refresh=False,
        )
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════
# Step 2: _step_get_priority_chain
# ═══════════════════════════════════════════════════════════════

class TestStepGetPriorityChain(unittest.TestCase):
    """_step_get_priority_chain — 获取适配器优先级链"""

    def setUp(self):
        self.routing = MagicMock()
        self.handler = _make_handler(routing=self.routing)

    def test_normal_chain(self):
        """路由返回非空链时直接返回"""
        self.routing._get_priority.return_value = ["site_a", "site_b", "site_c"]
        adapters = [_make_adapter("site_a"), _make_adapter("site_b")]
        rotator = MagicMock()

        result = self.handler._step_get_priority_chain(
            logical_code="GB/T",
            preferred_site=None,
            adapters=adapters,
            rotator=rotator,
        )
        self.assertEqual(result, ["site_a", "site_b", "site_c"])
        rotator.wait_for_any_recovery.assert_not_called()

    def test_all_cooldown_with_rotator(self):
        """全冷却且有 rotator 时：等待恢复 → 重试获取链"""
        self.routing._get_priority.side_effect = [
            [],  # 第一次：全部冷却
            ["site_a", "site_b"],  # 恢复后
        ]
        adapters = [_make_adapter("site_a"), _make_adapter("site_b")]
        rotator = MagicMock()

        result = self.handler._step_get_priority_chain(
            logical_code="GB/T",
            preferred_site=None,
            adapters=adapters,
            rotator=rotator,
        )
        self.assertEqual(result, ["site_a", "site_b"])
        rotator.wait_for_any_recovery.assert_called_once()
        self.assertEqual(self.routing._get_priority.call_count, 2)

    def test_all_cooldown_no_rotator(self):
        """全冷却但无 rotator 时：直接返回空列表"""
        self.routing._get_priority.return_value = []
        adapters = [_make_adapter("site_a")]

        result = self.handler._step_get_priority_chain(
            logical_code="GB/T",
            preferred_site=None,
            adapters=adapters,
            rotator=None,
        )
        self.assertEqual(result, [])

    def test_normal_chain_no_rotator(self):
        """正常链 + 无 rotator — 直接返回"""
        self.routing._get_priority.return_value = ["site_x"]
        adapters = [_make_adapter("site_x")]

        result = self.handler._step_get_priority_chain(
            logical_code="GB/T",
            preferred_site=None,
            adapters=adapters,
            rotator=None,
        )
        self.assertEqual(result, ["site_x"])


# ═══════════════════════════════════════════════════════════════
# Step 3: _step_query_adapters
# ═══════════════════════════════════════════════════════════════

class TestStepQueryAdapters(unittest.TestCase):
    """_step_query_adapters — 逐适配器查询"""

    def setUp(self):
        self.core = MagicMock()
        self.core.record = MagicMock()
        self.handler = _make_handler(core=self.core)
        self.target = "GB/T 19001-2020"

    def test_first_adapter_hits(self):
        """首个适配器命中 → 返回 (result, tried, False)"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a", "site_b"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_name, "质量管理体系")
        self.assertEqual(result.source_site, "site_a")
        self.assertEqual(tried, ["site_a"])
        self.assertFalse(quota_exhausted)
        self.core.record.assert_called_once_with("site_a", 1)

    def test_adapters_all_fail(self):
        """全部适配器返回未找到 → (None, tried, False)"""
        not_found = QueryResult(
            standard_number=self.target,
            error_message="未找到匹配结果",
        )
        adp_a = _make_adapter("site_a", found_result=not_found)
        adp_b = _make_adapter("site_b", found_result=not_found)
        adapter_map = {"site_a": adp_a, "site_b": adp_b}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a", "site_b"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertIsNone(result)
        self.assertEqual(tried, ["site_a", "site_b"])
        self.assertFalse(quota_exhausted)

    def test_quota_all_exhausted(self):
        """全部适配器配额为 0 → (None, [], True)"""
        adp_a = _make_adapter("site_a")
        adp_b = _make_adapter("site_b")
        adapter_map = {"site_a": adp_a, "site_b": adp_b}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 0
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a", "site_b"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertIsNone(result)
        self.assertEqual(tried, [])
        self.assertTrue(quota_exhausted)

    def test_skip_exhausted_then_hit(self):
        """跳过配额耗尽的适配器，后续命中"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp_a = _make_adapter("site_a")
        adp_b = _make_adapter("site_b", found_result=found)
        adapter_map = {"site_a": adp_a, "site_b": adp_b}
        quota = MagicMock()
        quota.get_search_remaining.side_effect = [0, 100]  # a 耗尽, b 有余
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a", "site_b"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.source_site, "site_b")
        self.assertEqual(tried, ["site_b"])
        self.assertFalse(quota_exhausted)

    def test_adapter_not_in_map_skipped(self):
        """优先级链中的站点不在 adapter_map 中 → 跳过"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp_b = _make_adapter("site_b", found_result=found)
        adapter_map = {"site_b": adp_b}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a", "site_b"],  # site_a 不在 map 中
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.source_site, "site_b")
        self.assertEqual(tried, ["site_b"])

    def test_quota_is_none(self):
        """quota=None 时正常查询（不检查配额）"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        cache = MagicMock()

        result, tried, quota_exhausted = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a"],
            adapter_map=adapter_map,
            quota=None,
            cache=cache,
        )
        self.assertIsNotNone(result)
        self.assertFalse(quota_exhausted)

    def test_hit_caches_exact_match(self):
        """exact 命中时写入缓存"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        cache.put.assert_called_once()

    def test_hit_non_exact_skips_cache(self):
        """非 exact 命中不写缓存"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="质量管理体系",
            status="现行",
            match_status="fuzzy",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        cache.put.assert_not_called()

    def test_fills_standard_number_when_empty(self):
        """命中结果 standard_number 为空时用 target 填充"""
        found = QueryResult(
            standard_number="",  # 空
            standard_name="质量管理体系",
            status="现行",
            match_status="exact",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        result, _, _ = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="质量管理体系",
            part=None,
            num_prefix="",
            priority=["site_a"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertEqual(result.standard_number, self.target)

    def test_detects_adoption(self):
        """采标检测：status 含"采标" → is_adopted=True, is_downloadable=False"""
        found = QueryResult(
            standard_number=self.target,
            standard_name="采标标准示例",
            status="采标",
            match_status="exact",
        )
        adp = _make_adapter("site_a", found_result=found)
        adapter_map = {"site_a": adp}
        quota = MagicMock()
        quota.get_search_remaining.return_value = 100
        cache = MagicMock()

        result, _, _ = self.handler._step_query_adapters(
            target=self.target,
            logical_code="GB/T",
            number=19001,
            year=2020,
            std_name="采标标准示例",
            part=None,
            num_prefix="",
            priority=["site_a"],
            adapter_map=adapter_map,
            quota=quota,
            cache=cache,
        )
        self.assertTrue(result.is_adopted)
        self.assertFalse(result.is_downloadable)


# ═══════════════════════════════════════════════════════════════
# Step 4: _step_quota_exhausted
# ═══════════════════════════════════════════════════════════════

class TestStepQuotaExhausted(unittest.TestCase):
    """_step_quota_exhausted — 配额耗尽兜底"""

    def test_returns_error_result(self):
        """返回正确的错误结构和消息"""
        result = SingleQueryHandler._step_quota_exhausted("GB/T 19001-2020")

        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, "GB/T 19001-2020")
        self.assertEqual(result.error_message, "所有站点今日配额已用尽，请明日再试")
        self.assertEqual(result.source_site, "")
        self.assertFalse(result.is_found())

    def test_different_targets(self):
        """不同 target 返回不同 standard_number"""
        r1 = SingleQueryHandler._step_quota_exhausted("ISO 9001-2015")
        r2 = SingleQueryHandler._step_quota_exhausted("DIN EN 10204-2005")

        self.assertEqual(r1.standard_number, "ISO 9001-2015")
        self.assertEqual(r2.standard_number, "DIN EN 10204-2005")
        self.assertEqual(r1.error_message, r2.error_message)


# ═══════════════════════════════════════════════════════════════
# Step 5: _step_not_found
# ═══════════════════════════════════════════════════════════════

class TestStepNotFound(unittest.TestCase):
    """_step_not_found — 未找到兜底"""

    def test_returns_error_result(self):
        """返回正确的错误结构和消息"""
        result = SingleQueryHandler._step_not_found(
            "GB/T 19001-2020", tried=["site_a", "site_b"]
        )

        self.assertIsInstance(result, QueryResult)
        self.assertEqual(result.standard_number, "GB/T 19001-2020")
        self.assertEqual(result.error_message, "所有来源均未找到该标准")
        self.assertEqual(result.source_site, "")
        self.assertFalse(result.is_found())

    def test_tried_list_not_affecting_result(self):
        """tried 列表不影响返回的 QueryResult 结构"""
        result = SingleQueryHandler._step_not_found(
            "ISO 9001-2015", tried=[]
        )
        self.assertEqual(result.standard_number, "ISO 9001-2015")
        self.assertFalse(result.is_found())

    def test_tried_with_many_sites(self):
        """tried 列表包含多个站点时仍正常返回"""
        result = SingleQueryHandler._step_not_found(
            "GB/T 1.1-2020", tried=["ahbz", "std_gov", "njbz365", "hbba"]
        )
        self.assertEqual(result.standard_number, "GB/T 1.1-2020")
        self.assertEqual(result.error_message, "所有来源均未找到该标准")
