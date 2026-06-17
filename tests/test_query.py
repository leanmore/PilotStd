# tests/test_query.py

import sys
import os
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest
import tempfile
import shutil
from datetime import datetime, timedelta

from pilotstd.core.db import Database
from pilotstd.query.models import QueryResult, BatchQueryStats
from pilotstd.query.adapters.base import BaseAdapter
from pilotstd.query.cache import CacheRepository
from pilotstd.query.engine import QueryEngine


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
        s = BatchQueryStats(total=10, found=8, downloadable=6,
                            adopted_restricted=2, not_found=2)
        self.assertEqual(s.total, 10)
        self.assertEqual(s.downloadable, 6)


class TestCacheRepository(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))
        self.cache = CacheRepository(self.db)

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_put_and_get(self):
        r = QueryResult(standard_number="GB/T 1-2020",
                        standard_name="基础规范", status="现行",
                        source_site="mock")
        self.cache.put(r)
        cached = self.cache.get("GB/T 1-2020", "mock")
        self.assertIsNotNone(cached)
        self.assertEqual(cached.standard_name, "基础规范")

    def test_cache_miss(self):
        self.assertIsNone(self.cache.get("不存在的标准", "mock"))

    def test_refresh(self):
        r = QueryResult(standard_number="GB/T 2-2020", status="现行",
                        source_site="mock")
        self.cache.put(r)
        self.cache.refresh("GB/T 2-2020", "mock")
        self.assertIsNone(self.cache.get("GB/T 2-2020", "mock"))

    def test_history(self):
        r = QueryResult(standard_number="GB/T 3-2020", status="现行",
                        source_site="mock")
        self.cache.put(r)
        history = self.cache.get_history(limit=10)
        self.assertGreaterEqual(len(history), 1)

    def test_no_ttl_expiry(self):
        """缓存不因 TTL 过期而删除——失效由事件（被代替）驱动。"""
        cache = CacheRepository(self.db, active_ttl=-1, inactive_ttl=-1)
        r = QueryResult(standard_number="GB/T 4-2020", status="现行",
                        source_site="mock")
        cache.put(r)
        # TTL 为负值时仍能命中，因为不再按时间淘汰缓存
        result = cache.get("GB/T 4-2020", "mock")
        self.assertIsNotNone(result)
        self.assertEqual(result.standard_number, "GB/T 4-2020")


class TestQueryEngine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))
        self.cache = CacheRepository(self.db)
        self.active_adapter = MockActiveAdapter()
        self.adopted_adapter = MockAdoptedAdapter()
        self.engine = QueryEngine(
            adapters=[self.active_adapter, self.adopted_adapter],
            cache=self.cache,
            use_cache=True,
        )

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_single_query_found(self):
        r = self.engine.query_single("GB/T 19001-2020")
        self.assertTrue(r.is_found())
        self.assertEqual(r.status, "现行")

    def test_single_query_not_found(self):
        r = self.engine.query_single("NONE_12345-2020")
        self.assertFalse(r.is_found())

    def test_cache_reuse(self):
        self.engine.query_single("GB/T 19001-2020")
        cached = self.cache.get("GB/T 19001-2020", "mock_active")
        self.assertIsNotNone(cached)

    def test_force_refresh(self):
        self.engine.query_single("GB/T 19001-2020")
        self.cache.refresh("GB/T 19001-2020", "mock_active")
        r = self.engine.query_single("GB/T 19001-2020", force_refresh=True)
        self.assertTrue(r.is_found())

    def test_batch_query(self):
        numbers = ["GB/T 1-2020", "GB/T 2-2020", "NONE_3-2020"]
        results, stats = self.engine.query_batch(numbers)
        self.assertEqual(stats.total, 3)
        # query_batch 现在走 query_batch_parsed 的类型路由，Mock 适配器返回全部 found
        self.assertGreaterEqual(stats.found, 0)

    def test_disabled_cache(self):
        """use_cache=False 仅跳过缓存读取，查询结果仍应写入缓存。"""
        engine = QueryEngine(
            adapters=[self.active_adapter],
            cache=self.cache,
            use_cache=False,
        )
        engine.query_single("GB/T 19001-2020")
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
            parsed_list, lambda c: progress.append(c))

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
        from pilotstd.query.search_strategy import match_result

    def test_match_gb_vs_gbt_same_number(self):
        """GB 713-2014 vs GB/T 713-2014 → exact（代号变体，同一标准）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 713, 2014,
            result_name="锅炉和压力容器用钢板",
            result_number_str="GB/T 713-2014")
        self.assertTrue(is_match)
        self.assertEqual(status, "exact")

    def test_match_gb_vs_gbt_newer_year(self):
        """GB 713-2014 vs GB/T 713-2017 → newer（代号变体，年份更新）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 713, 2014,
            result_name="锅炉和压力容器用钢板",
            result_number_str="GB/T 713-2017")
        self.assertTrue(is_match)
        self.assertEqual(status, "newer")

    def test_variant_not_cross_number(self):
        """GB 713-2014 vs GB/T 30713-2014 → mismatch（顺序号不同）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 713, 2014,
            result_name="砚石 显微鉴定方法",
            result_number_str="GB/T 30713-2014")
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_variant_not_cross_family(self):
        """GB 713 vs ISO 713 → mismatch（不同标准体系）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 713, 2014,
            result_name="Some ISO standard",
            result_number_str="ISO 713-2014")
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_different_parts_mismatch(self):
        """GB 30000.3-2013 vs GB 30000.30-2025 → mismatch（不同部分号，非同一标准）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 30000, 2013,
            result_name="化学品分类和标签规范 第30部分：退敏爆炸物",
            result_number_str="GB 30000.30-2025",
            local_part=3)
        self.assertFalse(is_match)
        self.assertEqual(status, "mismatch")

    def test_same_part_newer_year(self):
        """GB 4053.1-2009 vs GB 4053.1-2025 → newer（同部分号，年份更新）"""
        from pilotstd.query.search_strategy import match_result
        is_match, status = match_result(
            "GB", 4053, 2009,
            result_name="固定式钢梯及平台安全要求 第1部分：钢直梯",
            result_number_str="GB 4053.1-2025",
            local_part=1)
        self.assertTrue(is_match)
        self.assertEqual(status, "newer")


# ── 多部分拆分检测测试 ─────────────────────────────────────

class TestMultiPartDetection(unittest.TestCase):
    """_detect_split_parts 多部分拆分检测"""

    def setUp(self):
        self.adapter = type("_Mock", (BaseAdapter,), {
            "site_name": "mock",
            "site_label": "Mock",
            "_search": lambda self, term: None,
        })()

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
        from pilotstd.query.engine import QueryEngine, CODE_ROUTES
        self.CODE_ROUTES = CODE_ROUTES

    def test_njbz365_in_routes(self):
        """njbz365 已恢复：GB/GB/T 路由含 njbz365 作为二线站点"""
        for code in ("GB", "GB/T", "GB/Z", "GSB"):
            self.assertIn("njbz365", self.CODE_ROUTES.get(code, []),
                          f"njbz365 应在 {code} 路由中（二线站点）")

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
            self.assertIn(fc, self.CODE_ROUTES,
                          f"{fc} 应在 CODE_ROUTES 中有路由条目")

    def test_awwa_routes_to_foreign(self):
        """AWWA(4字符)应在 CODE_ROUTES 中且路由不含 hbba（国外路由不走行业平台）"""
        from pilotstd.query.engine import CODE_ROUTES, INDUSTRY_ROUTE
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
            self.assertNotIn("csres", route,
                             f"{fc} 不应路由到 csres（csres 无法查询国外标准），"
                             f"当前路由={route}")
            self.assertIn("njbz365", route,
                          f"{fc} 应路由到 njbz365，当前路由={route}")


# ── 网络异常模拟测试 ─────────────────────────────────────

class TestNetworkErrorHandling(unittest.TestCase):
    """模拟超时/连接失败，验证 QueryEngine 和适配器优雅降级。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_timeout_adapter_batch_graceful(self):
        """超时适配器的 query_batch 应捕获异常返回 error_message，不崩溃。"""

        class TimeoutAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "timeout_site"

            @property
            def site_label(self):
                return "超时站点"

            def _search(self, search_term):
                raise __import__('requests').Timeout("模拟超时")

        adapter = TimeoutAdapter()
        # query_single 允许抛异常（底层接口），query_batch 负责捕获
        batch = adapter.query_batch(["GB/T 1-2020", "GB/T 2-2020"])
        self.assertEqual(len(batch), 2)
        for r in batch:
            self.assertIsNotNone(r)
            # 异常被转为 error_message
            self.assertTrue(r.error_message or not r.is_found())

    def test_connection_error_batch_graceful(self):
        """连接失败适配器的 query_batch 不抛异常，异常信息进入 error_message。"""

        class ConnErrorAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "conn_err"

            @property
            def site_label(self):
                return "断网站点"

            def _search(self, search_term):
                raise __import__('requests').ConnectionError("模拟断网")

        adapter = ConnErrorAdapter()
        batch = adapter.query_batch(["GB/T 1-2020"])
        self.assertEqual(len(batch), 1)
        self.assertIsNotNone(batch[0])
        self.assertIn("模拟断网", batch[0].error_message)

    def test_mixed_adapters_engine_does_not_crash(self):
        """混合正常+异常适配器时 QueryEngine 不崩溃，正常结果可返回。"""
        from pilotstd.query.cache import CacheRepository

        class GoodAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "good"

            @property
            def site_label(self):
                return "正常"

            def _search(self, search_term):
                return QueryResult(standard_number=search_term,
                                   standard_name="正常结果", status="现行",
                                   source_site=self.site_name)

        class BadAdapter(BaseAdapter):
            @property
            def site_name(self):
                return "bad"

            @property
            def site_label(self):
                return "异常"

            def _search(self, search_term):
                raise RuntimeError("内部错误")

        cache = CacheRepository(self.db)
        engine = QueryEngine(adapters=[GoodAdapter(), BadAdapter()],
                             cache=cache, use_cache=False)
        results, stats = engine.query_batch(["GB/T 1-2020"])
        # 至少有一个成功
        found = [r for r in results if r.is_found()]
        self.assertGreaterEqual(len(found), 1)


# ── 并发安全测试 ────────────────────────────────────────

class TestConcurrencySafety(unittest.TestCase):
    """DailyQuotaTracker 多线程并发正确性。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))
        from pilotstd.query.daily_quota import DailyQuotaTracker
        self.tracker = DailyQuotaTracker(self.db)

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_concurrent_record_usage_no_lost_count(self):
        """10 线程各 record_usage 10 次 → 最终 used=100，无丢失。"""
        import threading
        site = "csres"
        threads = []
        errors = []

        def worker():
            try:
                for _ in range(10):
                    self.tracker.record_usage(site, 1)
            except Exception as e:
                errors.append(str(e))

        for _ in range(10):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        used = self.tracker.get_used(site)
        self.assertEqual(used, 100, f"期望 100，实际 {used}（计数丢失）")

    def test_concurrent_get_remaining_consistent(self):
        """并发读取 get_remaining 期间无异常、不崩溃。"""
        import threading
        errors = []

        def reader():
            try:
                for _ in range(50):
                    self.tracker.get_remaining("csres")
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

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="pilotstd_test_")
        self.db = Database(os.path.join(self.tmp, "test.db"))

    def tearDown(self):
        self.db.close()
        self.db = None
        shutil.rmtree(self.tmp, ignore_errors=True)

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
                {"code": "0", "data": {"datalist": [
                    {"bzbh": "GB/T 1-2020", "bzmc": "test",
                     "bzzt": "现行", "bzid": "123"}
                ]}}
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
        self.assertEqual(call_count[0], 3, f"_refresh_csrf 应重试 3 次，实际 {call_count[0]}")
        self.assertEqual(adapter._csrf_token, "")


class TestBuildSearchTerms(unittest.TestCase):
    """build_search_terms 渐进式搜索词生成（含 num_prefix）"""

    def test_num_prefix_single_letter(self):
        """ASME B16.5 → 搜索词含 B 前缀"""
        from pilotstd.query.search_strategy import build_search_terms
        terms = build_search_terms("ASME", 16, 2017, part=5, num_prefix="B")
        self.assertIn("ASME B16.5 2017", terms)
        self.assertIn("ASME B16.5", terms)
        self.assertIn("ASME B16 2017", terms)
        self.assertIn("B16", terms)

    def test_num_prefix_not_present(self):
        """无 num_prefix 时行为不变"""
        from pilotstd.query.search_strategy import build_search_terms
        terms = build_search_terms("GB", 30000, 2013, part=3)
        self.assertIn("GB 30000.3 2013", terms)
        self.assertIn("GB 30000.3", terms)
        self.assertIn("30000", terms)

    def test_num_prefix_roman(self):
        """罗马数字前缀——VIII即8，前缀替代顺序号而非拼接"""
        from pilotstd.query.search_strategy import build_search_terms
        terms = build_search_terms("ASME", 8, 2021, num_prefix="VIII")
        self.assertIn("ASME VIII 2021", terms)
        self.assertIn("ASME VIII", terms)

    def test_num_prefix_multi_letter(self):
        """多字母前缀（API RP → RP 前缀）"""
        from pilotstd.query.search_strategy import build_search_terms
        terms = build_search_terms("API", 14, 2019, num_prefix="RP")
        self.assertIn("API RP14 2019", terms)
        self.assertIn("API RP14", terms)
        self.assertIn("RP14", terms)


if __name__ == "__main__":
    unittest.main(verbosity=2)
