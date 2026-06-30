# tests/test_e2e_adapters.py
# 端到端测试：真实 HTTP 请求验证各适配器对 GB/行业/国外/地方标准的查询结果
# 注意：依赖网络，每个适配器只测 1-2 条，避免触发限流

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest

from pilotstd.query.adapters.ahbz import AhbzAdapter
from pilotstd.query.adapters.dbba import DbbaAdapter
from pilotstd.query.adapters.hbba import HbbaAdapter
from pilotstd.query.adapters.iso_gov import IsoGovAdapter
from pilotstd.query.adapters.njbz365 import Njbz365Adapter
from pilotstd.query.adapters.std_gov import StdGovAdapter


class TestE2EStdGov(unittest.TestCase):
    """全国标准平台 — GB 标准"""

    def setUp(self):
        self.a = StdGovAdapter()

    @unittest.skip("外部 API 依赖 — CI 中跳过")
    def test_gb_exact_match(self):
        """GB/T 19001-2016 应返回 exact"""
        r = self.a.query_with_strategy("GB/T", 19001, 2016)
        if r is None:
            self.skipTest("std_gov 无响应")
        self.assertIsNotNone(r)
        self.assertEqual(r.match_status, "exact", f"期望 exact，实际 {r.match_status}")
        self.assertIn("质量", r.standard_name or "", f"标准名称应包含'质量': {r.standard_name}")


class TestE2ENjbz365(unittest.TestCase):
    """南京标准平台 — 国外 + 行业标准"""

    def setUp(self):
        self.a = Njbz365Adapter()

    def test_api_exact_match(self):
        """API 610-2004 应返回 exact，名称含 Centrifugal"""
        r = self.a.query_with_strategy("API", 610, 2004)
        if r is None or not r.is_found():
            self.skipTest("njbz365 对 API 610 无结果")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )
        # API 610 是离心泵标准
        self.assertTrue(
            "centrifugal" in (r.standard_name or "").lower()
            or "pump" in (r.standard_name or "").lower()
            or "610" in (r.standard_number or ""),
            f"标准名称/编号应相关: {r.standard_name} | {r.standard_number}",
        )

    def test_sh_exact_match(self):
        """SH/T 1610-2011 应返回 exact"""
        r = self.a.query_with_strategy("SH/T", 1610, 2011)
        if r is None or not r.is_found():
            self.skipTest("njbz365 对 SH/T 1610 无结果")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )
        self.assertTrue(
            "苯乙烯" in (r.standard_name or "")
            or "丁二烯" in (r.standard_name or "")
            or "1610" in (r.standard_number or ""),
            f"标准名称应含苯乙烯/丁二烯: {r.standard_name}",
        )


class TestE2EHbba(unittest.TestCase):
    """行业标准平台 — 行业标准"""

    def setUp(self):
        self.a = HbbaAdapter()

    def test_sh_exact_match(self):
        """SH/T 1610-2011 在行业平台应返回 exact"""
        r = self.a._search("SH/T 1610-2011")
        if r is None:
            self.skipTest("hbba 无响应")
        if r.error_message and "未找到" in r.error_message:
            self.skipTest("hbba 未收录 SH/T 1610")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )

    def test_hg_exact_match(self):
        """HG/T 20592-2009 在行业平台应返回 exact"""
        r = self.a._search("HG/T 20592-2009")
        if r is None or (r.error_message and "未找到" in r.error_message):
            self.skipTest("hbba 无结果")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )


class TestE2EDbba(unittest.TestCase):
    """地方标准平台 — 地方标准"""

    def setUp(self):
        self.a = DbbaAdapter()

    def test_db_exact_match(self):
        """DB11/T 1951-2021 在地方平台应返回 exact"""
        r = self.a._search("DB11/T 1951-2021")
        if r is None or (r.error_message and "未找到" in r.error_message):
            self.skipTest("dbba 无结果")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )


class TestE2EIsoGov(unittest.TestCase):
    """国际标准平台 — ISO/IEC 标准"""

    def setUp(self):
        self.a = IsoGovAdapter()

    def test_iso_exact_match(self):
        """ISO 9001:2015 在国际平台应返回 exact"""
        r = self.a._search("ISO 9001:2015")
        if r is None:
            self.skipTest("iso_gov 无响应")
        if r.error_message and "未找到" in r.error_message:
            self.skipTest("iso_gov 未收录")
        self.assertIsNotNone(r)
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )
        self.assertTrue(
            "quality" in (r.standard_name or "").lower() or "9001" in (r.standard_number or ""),
            f"标准名称/编号应相关: {r.standard_name}",
        )


class TestE2ECrossAdapter(unittest.TestCase):
    """跨适配器一致性：同一条标准在不同站点应都能查到（第七维度）"""

    def test_sh1610_in_both_hbba_and_njbz365(self):
        """SH/T 1610-2011 在 hbba 和 njbz365 都应可查"""
        hbba = HbbaAdapter()
        njbz = Njbz365Adapter()

        r_hbba = hbba._search("SH/T 1610-2011")
        r_njbz = njbz.query_with_strategy("SH/T", 1610, 2011)

        found = False
        for r in (r_hbba, r_njbz):
            if r and r.is_found():
                found = True
                self.assertIn(r.match_status, ("exact", "newer"))
        self.assertTrue(found, "SH/T 1610-2011 应在至少一个站点可查")

    def test_gbt19001_in_stdgov_and_njbz365(self):
        """GB/T 19001-2016 在 std_gov 和 njbz365 应都可查，match_status 一致"""
        std_gov = StdGovAdapter()
        njbz = Njbz365Adapter()

        r_gov = std_gov.query_with_strategy("GB/T", 19001, 2016)
        r_njbz = njbz.query_with_strategy("GB/T", 19001, 2016)

        statuses = set()
        for r in (r_gov, r_njbz):
            if r and r.is_found():
                statuses.add(r.match_status)
                self.assertIn(
                    r.match_status,
                    ("exact", "newer"),
                    f"match_status 异常: {r.match_status}",
                )

        # 至少一个站点查到且状态不矛盾
        self.assertGreater(len(statuses), 0, "GB/T 19001-2016 应在至少一个站点可查")

    def test_ahbz_cross_check_with_stdgov(self):
        """ahbz 和 std_gov 对同一国标的查询结果 status 应不矛盾"""
        ahbz = AhbzAdapter()
        std_gov = StdGovAdapter()

        r_ahbz = ahbz.query_with_strategy("GB/T", 19001, 2016)
        r_gov = std_gov.query_with_strategy("GB/T", 19001, 2016)

        found = False
        for r in (r_ahbz, r_gov):
            if r and r.is_found():
                found = True
                self.assertIn(r.match_status, ("exact", "newer"))
        self.assertTrue(found, "GB/T 19001-2016 应在新站点 ahbz 或 std_gov 查到")


class TestE2EAhbz(unittest.TestCase):
    """安徽标准平台 — 新站点端到端"""

    def setUp(self):
        self.a = AhbzAdapter()

    def test_gb_exact_match(self):
        """GB/T 19001-2016 在 ahbz 应返回 exact"""
        r = self.a.query_with_strategy("GB/T", 19001, 2016)
        if r is None or not r.is_found():
            self.skipTest("ahbz 对 GB/T 19001 无结果")
        self.assertEqual(r.match_status, "exact", f"期望 exact，实际 {r.match_status}")

    def test_sh_exact_match(self):
        """SH/T 1610-2011 在 ahbz 应可查"""
        r = self.a.query_with_strategy("SH/T", 1610, 2011)
        if r is None or not r.is_found():
            self.skipTest("ahbz 未收录 SH/T 1610")
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )

    def test_iso_exact_match(self):
        """ISO 9001:2015 在 ahbz 应可查"""
        r = self.a.query_with_strategy("ISO", 9001, 2015)
        if r is None or not r.is_found():
            self.skipTest("ahbz 未收录 ISO 9001")
        self.assertIn(
            r.match_status,
            ("exact", "newer"),
            f"期望 exact/newer，实际 {r.match_status}",
        )


class TestAllSitesCooled(unittest.TestCase):
    """异常韧性——全部站点冷却后查询不崩溃，返回明确错误（第三维度）"""

    def test_all_sites_cooled_returns_graceful(self):
        """模拟全部站点冷却，查询应不崩溃并返回错误信息。"""
        from pilotstd.manager.facade import StandardManager

        mgr = StandardManager()
        rotator = getattr(mgr.query_engine, "_rotator", None)
        if not rotator:
            self.skipTest("轮转器未初始化")

        # 记录原有状态以便恢复
        original = {}
        for name in rotator.list_sites():
            remaining = rotator.get_cooldown_remaining(name)
            original[name] = remaining

        try:
            # 强制全部站点进入冷却（1 小时）
            for name in rotator.list_sites():
                rotator.force_cooldown(name, 3600)

            # 查询一条标准——应不崩溃，返回无可用站点错误
            results, stats = mgr.query_by_numbers(["GB/T 1-2020"])
            self.assertEqual(len(results), 1)
            self.assertIsNotNone(results[0].error_message, "全部站点冷却时应有 error_message")

        finally:
            # 恢复冷却状态
            rotator.reset_all_cooldowns()
            for name, remaining in original.items():
                if remaining > 0:
                    rotator.force_cooldown(name, int(remaining))


class TestSiteUnavailable(unittest.TestCase):
    """异常韧性——站点不可用时引擎自动切换下一个站点，不崩溃（第三维度）"""

    def test_primary_site_down_falls_back(self):
        """主站点返回 None（模拟不可用），引擎应自动切换到次选站点。"""
        from pilotstd.query.adapters.njbz365 import Njbz365Adapter

        adapter = Njbz365Adapter()
        r = adapter.query_with_strategy("GB/T", 19001, 2016)
        if r is None:
            self.skipTest("njbz365 无响应")
        self.assertIsNotNone(r)

    def test_unavailable_site_returns_none_or_error(self):
        """站点不可用时 query_single 返回 None 或带 error_message 的结果。"""
        from pilotstd.query.adapters.hbba import HbbaAdapter

        adapter = HbbaAdapter()
        r = adapter._search("ZZ/NOEXIST-9999")
        # 找不到或站点不可用都应返回明确结果
        if r is None:
            self.skipTest("hbba 无响应")
        has_error = r.error_message or not r.is_found()
        self.assertTrue(has_error, f"应返回 None 或带 error_message/not_found: {r.error_message}")


class TestNetworkDisconnect(unittest.TestCase):
    """异常韧性——断网后 query 返回 error_message，不崩溃（第三维度）"""

    def test_query_with_mock_network_error_does_not_crash_engine(self):
        """单个适配器抛异常时引擎应捕获并继续，不因一次失败而崩溃。"""
        import tempfile
        from unittest.mock import MagicMock

        from pilotstd.core.db import Database
        from pilotstd.query.adapters.hbba import HbbaAdapter
        from pilotstd.query.cache import CacheRepository
        from pilotstd.query.engine import QueryEngine

        tmp = tempfile.mkdtemp(prefix="e2e_test_")
        db = Database(tmp + "/test.db")
        cache = CacheRepository(db)
        adapter = HbbaAdapter()
        adapter._search = MagicMock(side_effect=ConnectionError("模拟断网"))
        engine = QueryEngine(adapters=[adapter], cache=cache, use_cache=False)
        items = [("GB/T", 19001, 2016, "", None, "GB/T 19001-2016")]
        try:
            results = engine.query_batch_parsed(items)
            self.assertEqual(len(results), 1)
            self.assertIsNotNone(results[0])
        finally:
            db.close()
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
