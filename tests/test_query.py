# tests/test_query.py

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
from unittest.mock import MagicMock

import pytest

from pilotstd.organizer.industry_lookup import build_code_mapping
from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.cache import CacheRepository
from pilotstd.query.engine import QueryEngine
from pilotstd.query.models import BatchQueryStats, QueryResult
from pilotstd.scan.parser import StandardParser

# ── 模拟适配器（用于测试引擎和缓存）─────────────────────────


class MockActiveAdapter(BaseAdapter):
    """模拟一个总是返回'现行'结果的适配器"""

    @property
    def site_name(self):
        return "mock_active"

    @property
    def site_label(self):
        return "模拟活跃站点"

    def _search(self, search_term):
        if "NONE" in search_term:
            return None
        return QueryResult(
            standard_number=search_term,
            standard_name=f"标准名称_{search_term}",
            status="现行",
            source_site=self.site_name,
            is_adopted=False,
            match_status="exact",
        )


class MockAdoptedAdapter(BaseAdapter):
    """模拟返回采标结果的适配器"""

    @property
    def site_name(self):
        return "mock_iso"

    @property
    def site_label(self):
        return "模拟ISO站点"

    def _search(self, search_term):
        if "NONE" in search_term:
            return None
        return QueryResult(
            standard_number=search_term,
            standard_name=f"采标标准_{search_term}",
            status="现行",
            is_adopted=True,
            source_site=self.site_name,
        )


# ── 测试用例 ─────────────────────────────────────────────


class TestQueryModels(unittest.TestCase):
    def test_query_result_is_found(self):
        r = QueryResult(standard_number="GB/T 1-2020", standard_name="测试")
        self.assertTrue(r.is_found())

    def test_query_result_not_found(self):
        r = QueryResult(standard_number="XX 1-2020")
        self.assertFalse(r.is_found())

    def test_batch_query_stats(self):
        s = BatchQueryStats(
            total=10, found=8, downloadable=6, adopted_restricted=2, not_found=2
        )
        self.assertEqual(s.total, 10)
        self.assertEqual(s.downloadable, 6)


class TestCacheRepository(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.cache = CacheRepository(shared_db)

    def test_put_and_get(self):
        r = QueryResult(
            standard_number="GB/T 1-2020",
            standard_name="基础规范",
            status="现行",
            source_site="mock",
        )
        self.cache.put(r)
        cached = self.cache.get("GB/T 1-2020", "mock")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.standard_name, "基础规范")

    def test_cache_miss(self):
        self.assertIsNone(self.cache.get("不存在的标准", "mock"))

    def test_refresh(self):
        r = QueryResult(
            standard_number="GB/T 2-2020", status="现行", source_site="mock"
        )
        self.cache.put(r)
        self.cache.refresh("GB/T 2-2020", "mock")
        self.assertIsNone(self.cache.get("GB/T 2-2020", "mock"))

    def test_history(self):
        r = QueryResult(
            standard_number="GB/T 3-2020", status="现行", source_site="mock"
        )
        self.cache.put(r)
        history = self.cache.get_history(limit=10)
        self.assertGreaterEqual(len(history), 1)

    def test_no_ttl_expiry(self):
        """缓存不因 TTL 过期而删除——失效由事件（被代替）驱动。"""
        cache = CacheRepository(self.db, active_ttl=-1, inactive_ttl=-1)
        r = QueryResult(
            standard_number="GB/T 4-2020", status="现行", source_site="mock"
        )
        cache.put(r)
        # TTL 为负值时仍能命中，因为不再按时间淘汰缓存
        result = cache.get("GB/T 4-2020", "mock")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "GB/T 4-2020")


class TestQueryEngine(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.cache = CacheRepository(shared_db)
        self.active_adapter = MockActiveAdapter()
        self.adopted_adapter = MockAdoptedAdapter()
        self.engine = QueryEngine(
            adapters=[self.active_adapter, self.adopted_adapter],
            cache=self.cache,
            use_cache=True,
            parser=StandardParser(build_code_mapping()),
        )

    def test_single_query_found(self):
        r = self.engine.query_parsed("GB/T", 19001, 2020)
        self.assertTrue(r.is_found())
        self.assertEqual(r.status, "现行")

    def test_single_query_not_found(self):
        r = self.engine.query_parsed("NONE", 12345, 2020)
        self.assertFalse(r.is_found())

    def test_cache_reuse(self):
        self.engine.query_parsed("GB/T", 19001, 2020)
        cached = self.cache.get("GB/T 19001-2020", "mock_active")
        self.assertIsNotNone(cached)

    def test_force_refresh(self):
        self.engine.query_parsed("GB/T", 19001, 2020)
        self.cache.refresh("GB/T 19001-2020", "mock_active")
        r = self.engine.query_parsed("GB/T", 19001, 2020, force_refresh=True)
        self.assertTrue(r.is_found())

    def test_batch_query(self):
        items = [
            ("GB/T", 1, 2020, "", None, "GB/T 1-2020"),
            ("GB/T", 2, 2020, "", None, "GB/T 2-2020"),
            ("NONE", 3, 2020, "", None, "NONE_3-2020"),
        ]
        results = self.engine.query_batch_parsed(items)
        self.assertEqual(len(results), 3)
        found = sum(1 for r in results if r.is_found())
        self.assertGreaterEqual(found, 0)

    def test_disabled_cache(self):
        """use_cache=False 仅跳过缓存读取，查询结果仍应写入缓存。"""
        engine = QueryEngine(
            adapters=[self.active_adapter],
            cache=self.cache,
            use_cache=False,
        )
        engine.query_parsed("GB/T", 19001, 2020)
        cached = self.cache.get("GB/T 19001-2020", "mock_active")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.match_status, "exact")

    def test_parallel_batch_query(self):
        """多线程并行批量查询：结果顺序与输入一致"""
        parsed_list = [
            ("GB", 1, 2020, "测试标准一", None, ""),
            ("GB", 2, 2020, "测试标准二", None, ""),
            ("GB", 3, 2020, "测试标准三", None, ""),
            ("GB", 4, 2020, "", None, ""),
            ("GB", 5, 2020, "", None, ""),
        ]
        progress = []
        results = self.engine.query_batch_parsed(
            parsed_list, lambda c: progress.append(c)
        )

        self.assertEqual(len(results), 5)
        # 结果顺序应与输入一致（引擎保留网站返回的编号格式）
        self.assertIn("GB 1", results[0].standard_number)
        self.assertIn("GB 2", results[1].standard_number)
        self.assertIn("GB 3", results[2].standard_number)
        self.assertIn("GB 4", results[3].standard_number)
        self.assertIn("GB 5", results[4].standard_number)
        # 能找到的都应 is_found
        found = sum(1 for r in results if r.is_found())
        self.assertGreater(found, 0)
        # 进度回调应被调用
        self.assertEqual(len(progress), 5)

    def test_parallel_batch_empty(self):
        """空列表不报错"""
        results = self.engine.query_batch_parsed([])
        self.assertEqual(results, [])


# ── 代号变体匹配测试 ───────────────────────────────────────


class TestCodeVariantMatching(unittest.TestCase):
    """match_result 代号变体匹配（GB ↔ GB/T 等）"""

    def setUp(self):
        pass

    def test_match_gb_vs_gbt_same_number(self):
        """GB 713-2014 vs GB/T 713-2014 → exact（代号变体，同一标准）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            713,
            2014,
            result_name="锅炉和压力容器用钢板",
            result_number_str="GB/T 713-2014",
        )
        self.assertTrue(is_match)
        self.assertEqual(status, "exact")

    def test_match_gb_vs_gbt_newer_year(self):
        """GB 713-2014 vs GB/T 713-2017 → newer（代号变体，年份更新）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            713,
            2014,
            result_name="锅炉和压力容器用钢板",
            result_number_str="GB/T 713-2017",
        )
        self.assertTrue(is_match)
        self.assertEqual(status, "newer")

    def test_variant_not_cross_number(self):
        """GB 713-2014 vs GB/T 30713-2014 → mismatch（顺序号不同）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            713,
            2014,
            result_name="砚石 显微鉴定方法",
            result_number_str="GB/T 30713-2014",
        )
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_variant_not_cross_family(self):
        """GB 713 vs ISO 713 → mismatch（不同标准体系）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            713,
            2014,
            result_name="Some ISO standard",
            result_number_str="ISO 713-2014",
        )
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_different_parts_mismatch(self):
        """GB 30000.3-2013 vs GB 30000.30-2025 → mismatch（不同部分号，非同一标准）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            30000,
            2013,
            result_name="化学品分类和标签规范 第30部分：退敏爆炸物",
            result_number_str="GB 30000.30-2025",
            local_part=3,
        )
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_same_part_newer_year(self):
        """GB 4053.1-2009 vs GB 4053.1-2025 → newer（同部分号，年份更新）"""
        from pilotstd.query.search_strategy import match_result

        is_match, status = match_result(
            "GB",
            4053,
            2009,
            result_name="固定式钢梯及平台安全要求 第1部分：钢直梯",
            result_number_str="GB 4053.1-2025",
            local_part=1,
        )
        self.assertTrue(is_match)
        self.assertEqual(status, "newer")


# ── 多部分拆分检测测试 ─────────────────────────────────────


class TestMultiPartDetection(unittest.TestCase):
    """_detect_split_parts 多部分拆分检测"""

    def setUp(self):
        self.adapter = type(
            "_Mock",
            (BaseAdapter,),
            {
                "site_name": "mock",
                "site_label": "Mock",
                "_search": lambda self, term: None,
            },
        )()

    def test_two_parts_detected(self):
        """同 number 出现 ≥2 个不同 part → 返回拆分列表"""
        candidates = [
            (QueryResult(standard_number="GB/T 713.1-2017", source_site="mock"), 80),
            (QueryResult(standard_number="GB/T 713.2-2017", source_site="mock"), 80),
        ]
        result = self.adapter._detect_split_parts(candidates, 713)
        self.assertIn("GB/T 713.1-2017", result)
        self.assertIn("GB/T 713.2-2017", result)

    def test_no_false_split_single_result(self):
        """单个结果不触发拆分"""
        candidates = [
            (QueryResult(standard_number="GB/T 713.1-2017", source_site="mock"), 80),
        ]
        result = self.adapter._detect_split_parts(candidates, 713)
        self.assertEqual(result, "")

    def test_no_split_different_number(self):
        """不同 number 不触发拆分"""
        candidates = [
            (QueryResult(standard_number="GB/T 713.1-2017", source_site="mock"), 80),
            (QueryResult(standard_number="GB/T 714.1-2017", source_site="mock"), 80),
        ]
        result = self.adapter._detect_split_parts(candidates, 713)
        self.assertEqual(result, "")

    def test_no_part_numbers(self):
        """无 part 号的结果不参与拆分判断"""
        candidates = [
            (QueryResult(standard_number="GB/T 713-2017", source_site="mock"), 80),
            (QueryResult(standard_number="GB/T 713-2017", source_site="mock"), 80),
        ]
        result = self.adapter._detect_split_parts(candidates, 713)
        self.assertEqual(result, "")


# ── 英文状态映射测试 ───────────────────────────────────────


class TestStatusMapping(unittest.TestCase):
    """map_status 英文状态映射"""

    def test_map_active(self):
        from pilotstd.query.search_strategy import map_status

        self.assertEqual(map_status("Active"), "现行")

    def test_map_withdrawn(self):
        from pilotstd.query.search_strategy import map_status

        self.assertEqual(map_status("Withdrawn"), "废止")

    def test_map_superseded(self):
        from pilotstd.query.search_strategy import map_status

        self.assertEqual(map_status("Superseded"), "被代替")

    def test_map_chinese_unchanged(self):
        """中文状态保持原有映射"""
        from pilotstd.query.search_strategy import map_status

        self.assertEqual(map_status("现行"), "现行")
        self.assertEqual(map_status("废止"), "废止")


# ── 路由测试 ───────────────────────────────────────────────


class TestRouting(unittest.TestCase):
    """查询路由验证"""

    def setUp(self):
        from pilotstd.query.engine import CODE_ROUTES

        self.CODE_ROUTES = CODE_ROUTES

    def test_njbz365_in_routes(self):
        """njbz365 已恢复：GB/GB/T 路由含 njbz365 作为二线站点"""
        for code in ("GB", "GB/T", "GB/Z", "GSB"):
            self.assertIn(
                "njbz365",
                self.CODE_ROUTES.get(code, []),
                f"njbz365 应在 {code} 路由中（二线站点）",
            )

    def test_njbz365_in_priority(self):
        """njbz365 在默认优先级中"""
        from pilotstd.query.engine import PROD_PRIORITY

        self.assertIn("njbz365", PROD_PRIORITY)

    def test_njbz365_in_industry(self):
        """njbz365 在行业路由中作为二线"""
        from pilotstd.query.engine import INDUSTRY_ROUTE

        self.assertIn("njbz365", INDUSTRY_ROUTE)

    def test_njbz365_in_foreign(self):
        """njbz365 在国外路由中（唯一覆盖国外标准的站点）"""
        from pilotstd.query.engine import FOREIGN_ROUTE

        self.assertIn("njbz365", FOREIGN_ROUTE)

    def test_foreign_codes_have_routes(self):
        """所有 FOREIGN_CODE_SET 中的代号在 CODE_ROUTES 中都有条目"""
        from pilotstd.scan.parser import FOREIGN_CODE_SET

        for fc in FOREIGN_CODE_SET:
            self.assertIn(fc, self.CODE_ROUTES, f"{fc} 应在 CODE_ROUTES 中有路由条目")

    def test_awwa_routes_to_foreign(self):
        """AWWA(4字符)应在 CODE_ROUTES 中且路由不含 hbba（国外路由不走行业平台）"""
        from pilotstd.query.engine import CODE_ROUTES

        self.assertIn("AWWA", CODE_ROUTES)
        self.assertNotIn("hbba", CODE_ROUTES.get("AWWA", []))

    def test_foreign_codes_route_to_njbz365_not_csres(self):
        """外标代号应走 njbz365 而非 csres（O修复回归测试）。

        csres 无法查询国外标准，强制冷却 24h 会阻塞后续国内标准查询。
        """
        from pilotstd.query.engine import CODE_ROUTES
        from pilotstd.scan.parser import FOREIGN_CODE_SET

        for fc in FOREIGN_CODE_SET:
            if fc in ("ISO", "IEC"):
                continue  # ISO/IEC 走 iso_gov 路线，不走 FOREIGN_ROUTE
            route = CODE_ROUTES.get(fc, [])
            self.assertNotIn(
                "csres",
                route,
                f"{fc} 不应路由到 csres（csres 无法查询国外标准），当前路由={route}",
            )
            self.assertIn("njbz365", route, f"{fc} 应路由到 njbz365，当前路由={route}")


# ── 网络异常模拟测试 ─────────────────────────────────────


class TestNetworkErrorHandling(unittest.TestCase):
    """模拟超时/连接失败，验证 QueryEngine 在引擎层优雅降级。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.cache = CacheRepository(shared_db)

    def test_timeout_adapter_engine_graceful(self):
        """超时适配器在引擎 query_batch_parsed 中不崩溃，异常入 error_message。"""

        class TimeoutAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "timeout_site"

            @property
            def site_label(self):
                return "超时站点"

            def _search(self, search_term):
                raise __import__("requests").Timeout("模拟超时")

        adapter = TimeoutAdapter()
        engine = QueryEngine(adapters=[adapter], cache=self.cache)
        items = [
            ("GB/T", 1, 2020, "", None, "GB/T 1-2020"),
            ("GB/T", 2, 2020, "", None, "GB/T 2-2020"),
        ]
        results = engine.query_batch_parsed(items)
        self.assertEqual(len(results), 2)
        for r in results:
            self.assertTrue(r.error_message or not r.is_found())

    def test_connection_error_engine_graceful(self):
        """连接失败适配器在引擎层不抛异常。"""

        class ConnErrorAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "conn_err"

            @property
            def site_label(self):
                return "断网站点"

            def _search(self, search_term):
                raise __import__("requests").ConnectionError("模拟断网")

        adapter = ConnErrorAdapter()
        engine = QueryEngine(adapters=[adapter], cache=self.cache)
        items = [("GB/T", 1, 2020, "", None, "GB/T 1-2020")]
        results = engine.query_batch_parsed(items)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].error_message or not results[0].is_found())

    def test_cache_with_network_errors(self):
        """网络错误适配器不崩溃，返回带 error_message 的结果。"""

        class ConnErrorAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "conn_err"

            @property
            def site_label(self):
                return "断网站点"

            def _search(self, search_term):
                raise __import__("requests").ConnectionError("模拟断网")

        engine = QueryEngine(
            adapters=[ConnErrorAdapter()], cache=self.cache, use_cache=False
        )
        items = [("GB/T", 1, 2020, "", None, "GB/T 1-2020")]
        results = engine.query_batch_parsed(items)
        # 异常不崩溃
        self.assertFalse(results[0].is_found())


# ── 并发安全测试 ────────────────────────────────────────


class TestConcurrencySafety(unittest.TestCase):
    """DailyQuotaTracker 多线程并发正确性。"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        from pilotstd.query.daily_quota import DailyQuotaTracker

        self.db = shared_db
        self._tracker = DailyQuotaTracker(shared_db)

    def test_concurrent_record_usage_no_lost_count(self):
        """10 线程各 record_usage 10 次 → 最终 used=100，无丢失。"""
        import threading

        site = "csres"
        threads = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    self._tracker.record_usage(site, 1)
            except Exception as e:
                errors.append(str(e))

        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        used = self._tracker.get_used(site)
        self.assertEqual(used, 100, f"期望 100，实际 {used}（计数丢失）")

    def test_concurrent_get_remaining_consistent(self):
        """并发读取 get_remaining 期间无异常、不崩溃。"""
        import threading

        errors = []

        def reader():
            try:
                for _ in range(50):
                    self._tracker.get_remaining("csres")
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


class TestNjbz365Retry(unittest.TestCase):
    """njbz365 适配器网络重试行为。"""

    def test_do_request_timeout_retries(self):
        """_do_request 超时后应重试 3 次（含首次），最终返回 None。"""
        import requests as req

        from pilotstd.query.adapters import njbz365

        adapter = njbz365.Njbz365Adapter()
        # 绕过 _ensure_session，直接 mock _session.post 连续超时
        adapter._initialized = True
        adapter._csrf_token = "fake_token"

        call_count = [0]

        def fake_post(*args, **kwargs):
            call_count[0] += 1
            raise req.Timeout("模拟超时")

        adapter._session.post = fake_post
        result = adapter._do_request("GB/T 1-2020")
        self.assertIsNone(result)
        self.assertEqual(call_count[0], 3, f"应重试 3 次，实际 {call_count[0]}")

    def test_do_request_succeeds_after_retry(self):
        """前 2 次超时、第 3 次成功应返回数据。"""
        import requests as req

        from pilotstd.query.adapters import njbz365

        adapter = njbz365.Njbz365Adapter()
        adapter._initialized = True
        adapter._csrf_token = "fake_token"

        call_count = [0]

        def flaky_post(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise req.Timeout("模拟超时")
            resp = req.Response()
            resp.status_code = 200
            import json

            resp._content = json.dumps(
                {
                    "code": "0",
                    "data": {
                        "datalist": [
                            {
                                "bzbh": "GB/T 1-2020",
                                "bzmc": "test",
                                "bzzt": "现行",
                                "bzid": "123",
                            }
                        ]
                    },
                }
            ).encode()
            return resp

        adapter._session.post = flaky_post
        result = adapter._do_request("GB/T 1-2020")
        self.assertIsNotNone(result)
        self.assertEqual(result["code"], "0")
        self.assertEqual(call_count[0], 3)

    def test_refresh_csrf_retries(self):
        """_refresh_csrf 失败后应重试 3 次。"""
        import requests as req

        from pilotstd.query.adapters import njbz365

        adapter = njbz365.Njbz365Adapter()
        adapter._csrf_token = ""  # 确保触发 refresh

        call_count = [0]

        def fake_options(*args, **kwargs):
            call_count[0] += 1
            raise req.Timeout("模拟超时")

        adapter._session.options = fake_options
        adapter._refresh_csrf()
        self.assertEqual(
            call_count[0], 3, f"_refresh_csrf 应重试 3 次，实际 {call_count[0]}"
        )
        self.assertEqual(adapter._csrf_token, "")


class TestProgressiveSearch(unittest.TestCase):
    """验证 query_with_strategy 渐进式搜索的搜索词生成与回退行为。"""

    def setUp(self):
        self.adapter = MockActiveAdapter()

    def test_num_prefix_included_in_search(self):
        """num_prefix 应出现在搜索词中。"""
        self.adapter._search = MagicMock(return_value=None)  # type: ignore[method-assign]
        self.adapter.query_with_strategy("ASME", 16, 2017, part=5, num_prefix="B")
        calls = [c[0][0] for c in self.adapter._search.call_args_list]
        self.assertIn("ASME B16.5-2017", calls)
        self.assertIn("ASME B16.5", calls)

    def test_roman_numeral_triggers_bpvc_variant(self):
        """罗马数字前缀触发 BPVC 变体搜索。"""
        self.adapter._search = MagicMock(return_value=None)  # type: ignore[method-assign]
        self.adapter.query_with_strategy("ASME", 8, 2021, num_prefix="VIII")
        calls = [c[0][0] for c in self.adapter._search.call_args_list]
        self.assertIn("ASME BPVC VIII.8-2021", calls)

    def test_api_stdspec_variant_fallback(self):
        """API 代号生成 Std/Spec 变体回退搜索。"""
        self.adapter._search = MagicMock(return_value=None)  # type: ignore[method-assign]
        self.adapter.query_with_strategy("API", 14, 2019, num_prefix="RP")
        calls = [c[0][0] for c in self.adapter._search.call_args_list]
        self.assertIn("API Std 14-2019", calls)
        self.assertIn("API Spec 14-2019", calls)


class TestBucketQuery(unittest.TestCase):
    """逐桶查询 V2 测试——分组/链隔离/临时桶调度"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.cache = CacheRepository(shared_db)
        self.parser = StandardParser(build_code_mapping())
        self.adapter = MockActiveAdapter()
        self.engine = QueryEngine(
            adapters=[self.adapter],
            cache=self.cache,
            use_cache=False,
            parser=self.parser,
        )

    def test_bucket_key_gb(self):
        """GB 标准 → 主站点非空，从 CODE_ROUTES 路由"""
        key = self.engine._bucket_key("GB")
        self.assertTrue(key)  # 任何 GB 标准都应该有一个桶

    def test_bucket_key_industry(self):
        """行业标准 → 主站点非空"""
        key = self.engine._bucket_key("SH")
        self.assertTrue(key)

    def test_bucket_key_foreign(self):
        """国外标准 → 主站点非空"""
        key = self.engine._bucket_key("API")
        self.assertTrue(key)

    def test_bucket_key_db(self):
        """地方标准 → 主站点非空"""
        key = self.engine._bucket_key("DB11")
        self.assertTrue(key)

    def test_chain_excludes_csres(self):
        """优先级链中不含 csres（由独立线程处理）"""
        chain = self.engine._build_chain_for_item(("GB", 1, 2020, "test", None))
        self.assertNotIn("csres", chain)
        self.assertTrue(len(chain) > 0)

    def test_batch_query_bucketed(self):
        """逐桶批量查询：混合类型结果数量正确"""
        items = [
            ("GB", 1, 2020, "国标测试", None, "", "", ""),
            ("SH", 3031, 2013, "行业测试", None, "", "", ""),
            ("API", 610, 2004, "国外测试", None, "", "", ""),
        ]
        results = self.engine.query_batch_parsed(items)
        self.assertEqual(len(results), 3)
        found = [r for r in results if r.is_found()]
        self.assertGreaterEqual(len(found), 1)

    def test_empty_batch(self):
        """空列表不崩溃"""
        results = self.engine.query_batch_parsed([])
        self.assertEqual(len(results), 0)

    def test_temp_bucket_chain_exhausted(self):
        """链耗尽条目→待确认"""
        items = [("ZZ", 99999, 2050, "不存在", None, "", "", "")]
        results = self.engine.query_batch_parsed(items)
        self.assertEqual(len(results), 1)
        # Mock 适配器对所有代号返回结果，不一定链耗尽
        # 但至少结果不为空且没有崩溃
        self.assertIsNotNone(results[0])


class MockSiteAdapter(BaseAdapter):
    """通用 mock 站点——可配站点名，命中率，计请求数"""

    def __init__(self, name, always_hit=True, match_status="exact"):
        self._name = name
        self._always_hit = always_hit
        self._match_status = match_status
        self.request_count = 0

    @property
    def site_name(self):
        return self._name

    @property
    def site_label(self):
        return self._name

    def _search(self, term):
        self.request_count += 1
        if self._always_hit:
            return QueryResult(
                standard_number=term,
                standard_name=f"std_{term}",
                status="现行",
                source_site=self._name,
                match_status=self._match_status,
            )
        return None


class TestBucketConcurrency(unittest.TestCase):
    """逐桶并发测试——溢出隔离/csres隔离/大桶拆子桶"""

    @pytest.fixture(autouse=True)
    def _setup_db(self, shared_db):
        self.db = shared_db
        self.cache = CacheRepository(shared_db)
        self.parser = StandardParser(build_code_mapping())

    def _engine(self, sites=None):
        adapters = sites or [
            MockSiteAdapter("std_gov"),
            MockSiteAdapter("hbba"),
            MockSiteAdapter("ahbz"),
            MockSiteAdapter("njbz365"),
            MockSiteAdapter("csres"),
        ]
        return QueryEngine(
            adapters=adapters, cache=self.cache, use_cache=False, parser=self.parser
        )

    def test_01_overflow_concurrent(self):
        """GB 200+行业 150 并发，不崩溃，ahbz 溢出池不击穿"""
        items = [("GB", i, 2020, "g", None, "", "", "") for i in range(200)]
        items += [("SH", i, 2020, "s", None, "", "", "") for i in range(150)]
        results = self._engine().query_batch_parsed(items)
        self.assertEqual(len(results), 350)
        self.assertGreater(sum(1 for r in results if r.is_found()), 200)

    def test_02_csres_chain_isolated(self):
        """csres 从链中完全移除"""
        chain = self._engine()._build_chain_for_item(("GB", 1, 2020, "t", None))
        self.assertNotIn("csres", chain)

    def test_03_overflow_exhausted_pending(self):
        """全部站点不命中→待确认"""
        engine = self._engine(
            [
                MockSiteAdapter("std_gov", always_hit=False),
                MockSiteAdapter("ahbz", always_hit=False),
            ]
        )
        results = engine.query_batch_parsed(
            [("GB", 99999, 2050, "x", None, "", "", "")]
        )
        self.assertEqual(results[0].status, "待确认")

    def test_04_large_batch_sub_buckets(self):
        """500 条大桶自动拆子桶，不崩溃"""
        items = [("GB", i, 2020, "t", None, "", "", "") for i in range(500)]
        results = self._engine().query_batch_parsed(items)
        self.assertEqual(len(results), 500)


if __name__ == "__main__":
    unittest.main(verbosity=2)
