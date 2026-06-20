# tests/test_router_extended.py
# 流水线路由器扩展测试：覆盖 GB/行业/国外/地方标准的全部分类规则

import os
import sys

root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import unittest

from pilotstd.core.file_utils import make_standard_filename
from pilotstd.models import ParsedStdInfo
from pilotstd.pipeline.router import PipelineRouter


def _p(
    code,
    number,
    year,
    effect_status="",
    match_status="",
    is_adopted=False,
    found_replaces="",
    source_path="",
    std_name="测试标准",
    part=None,
    num_prefix="",
    num_suffix="",
    language="",
):
    # 用 make_standard_filename 生成规范的 source_path，确保 router 能正确路由到 organize
    if not source_path:
        fname = make_standard_filename(
            code,
            number,
            year,
            std_name,
            part,
            language=language,
            num_prefix=num_prefix,
            num_suffix=num_suffix,
        )
        source_path = f"/tmp/{fname}"
    return ParsedStdInfo(
        raw_filename=f"{code} {number}-{year}.pdf",
        logical_code=code,
        number=number,
        year=year,
        std_name=std_name,
        source_name=std_name,
        source_path=source_path,
        effect_status=effect_status,
        match_status=match_status,
        is_adopted=is_adopted,
        found_replaces=found_replaces,
        part=part,
        num_prefix=num_prefix,
        num_suffix=num_suffix,
        language=language,
    )


class TestRouterClassifyAfterQuery(unittest.TestCase):
    """验证 classify_after_query 对所有标准类型的路由结果。"""

    def setUp(self):
        self.router = PipelineRouter()

    def _buckets(self, items):
        return self.router.classify_after_query(items)

    # ════════════════════════════════════════════════════════════
    # GB 标准各状态
    # ════════════════════════════════════════════════════════════

    def test_gb_active_exact(self):
        p = _p("GB/T", 19001, 2020, "现行", "exact", std_name="质量管理体系")
        b = self._buckets([p])
        self.assertEqual(len(b["organize"]), 1)

    def test_gb_active_newer(self):
        p = _p("GB/T", 19001, 2016, "现行", "newer")
        b = self._buckets([p])
        self.assertEqual(len(b["pending"]), 1)  # 规则0: 非exact→pending

    def test_gb_repealed_with_replaces(self):
        p = _p("GB", 150, 1998, "废止", "exact", found_replaces="GB/T 150.1-2011")
        b = self._buckets([p])
        self.assertEqual(len(b["download"]), 1)

    def test_gb_repealed_no_replaces(self):
        p = _p("GB", 12345, 1990, "废止", "exact", found_replaces="")
        b = self._buckets([p])
        self.assertEqual(len(b["expire"]), 1)

    def test_gb_pending_goes_to_pending(self):
        p = _p("GB", 99999, 2099, "待确认", "related")
        b = self._buckets([p])
        self.assertEqual(len(b["pending"]), 1)

    # ════════════════════════════════════════════════════════════
    # 行业标准 — 不可下载
    # ════════════════════════════════════════════════════════════

    def test_industry_newer_not_gb_no_download(self):
        """行业标准 newer → 不可下载（只有 GB 类可进 download）"""
        p = _p("SH/T", 1610, 2001, "现行", "newer")
        b = self._buckets([p])
        # 规则1 限 is_gb → SH/T newer 不会进 download
        self.assertEqual(len(b["download"]), 0)

    def test_industry_repealed_no_download(self):
        p = _p("NB/T", 47013, 2005, "废止", "exact", found_replaces="NB/T 47013-2015")
        b = self._buckets([p])
        # 规则4/5: 废止 + 有替代 → download 但限 is_gb → 进 expire
        self.assertEqual(len(b["expire"]), 1)

    def test_industry_active_exact(self):
        p = _p("HG/T", 20592, 2009, "现行", "exact", std_name="钢制管法兰")
        b = self._buckets([p])
        self.assertEqual(len(b["organize"]), 1)

    # ════════════════════════════════════════════════════════════
    # 国外标准 — 不可下载
    # ════════════════════════════════════════════════════════════

    def test_foreign_newer_not_gb_no_download(self):
        """API 标准 newer → 不可下载（is_gb=False）"""
        p = _p("API", 610, 2004, "现行", "newer")
        b = self._buckets([p])
        self.assertEqual(len(b["download"]), 0)

    def test_foreign_active_exact(self):
        p = _p("ASME", 1, 2021, "现行", "exact", std_name="Boiler Code")
        b = self._buckets([p])
        self.assertEqual(len(b["organize"]), 1)

    def test_foreign_not_found(self):
        p = _p("DIN", 11851, 1998, "", "")
        b = self._buckets([p])
        self.assertEqual(len(b["pending"]), 1)

    def test_foreign_repealed_no_download(self):
        p = _p("BS", 1092, 2018, "废止", "exact", found_replaces="BS EN 1092.1-2025")
        b = self._buckets([p])
        # 废止 + 有替代 but 非 GB → expire
        self.assertEqual(len(b["expire"]), 1)

    # ════════════════════════════════════════════════════════════
    # 地方标准
    # ════════════════════════════════════════════════════════════

    def test_local_active_exact(self):
        p = _p("DB35", 1234, 2020, "现行", "exact", std_name="福建省地方标准")
        b = self._buckets([p])
        self.assertEqual(len(b["organize"]), 1)

    def test_local_not_found(self):
        p = _p("DB11", 9999, 2099, "", "")
        b = self._buckets([p])
        self.assertEqual(len(b["pending"]), 1)

    # ════════════════════════════════════════════════════════════
    # 边界条件
    # ════════════════════════════════════════════════════════════

    def test_empty_items(self):
        b = self._buckets([])
        for k in ("organize", "normalize", "expire", "download", "pending"):
            self.assertEqual(len(b.get(k, [])), 0)

    def test_即将实施_goes_to_fallback(self):
        """即将实施状态不在明确规则中 → fallback"""
        p = _p("GB/T", 4053, 2025, "即将实施", "exact")
        b = self._buckets([p])
        self.assertEqual(len(b["fallback"]), 1)

    def test_multi_item_mixed_types(self):
        """混合标准类型 → 各自正确分桶（规则0: non-exact→pending）"""
        items = [
            _p("GB/T", 55555, 2020, "现行", "exact", std_name="质量管理体系"),
            _p("GB/T", 19001, 2016, "现行", "newer"),  # → pending（规则0）
            _p("SH/T", 1610, 2011, "现行", "exact", std_name="苯乙烯-丁二烯橡胶"),
            _p("API", 610, 2004, "现行", "newer"),  # → pending（规则0）
            _p("GB", 12345, 1990, "废止", "exact", found_replaces=""),  # → expire
            _p("DIN", 11851, 1998, "", ""),  # → pending
        ]
        b = self._buckets(items)
        total = sum(len(v) for v in b.values())
        self.assertEqual(total, 6, "6条标准应全部分配")
        self.assertEqual(len(b["download"]), 0)  # newer不复进download
        self.assertEqual(len(b["pending"]), 3)  # GB newer + API newer + DIN
        self.assertGreaterEqual(len(b["expire"]), 1)  # GB 废止


class TestRouterApplyActions(unittest.TestCase):
    """验证 apply_actions 正确设置 next_action。"""

    def setUp(self):
        self.router = PipelineRouter()

    def test_apply_actions_sets_next_action(self):
        items = [
            _p("GB/T", 19001, 2020, "现行", "exact", std_name="质量管理体系"),
            _p("GB/T", 19001, 2016, "现行", "newer"),
            _p("GB", 12345, 1990, "废止", "exact", found_replaces=""),
            _p("SH/T", 9999, 2020, "待确认", "related"),
            _p("GB/T", 99999, 2099, "即将实施", "exact"),
        ]
        self.router.apply_actions(items)

        # 验证各标准被正确分类
        actions = {p.next_action for p in items}
        self.assertIn("archive", actions)
        self.assertIn("not_found", actions)  # 即将实施 → not_found


if __name__ == "__main__":
    unittest.main()
