"""路由调度器测试 — 按状态标记分堆，冷启动/热启动兼容"""

import pytest

from pilotstd.models import ParsedStdInfo
from pilotstd.pipeline.router import PipelineRouter


def make_parsed(
    code="GB",
    number=19001,
    year=2020,
    name="测试标准",
    effect_status="待确认",
    next_action="pending",
    found_replaces="",
    match_status="",
):
    """快速构造 ParsedStdInfo 测试数据"""
    p = ParsedStdInfo(
        raw_filename=f"{code}{number}-{year}.pdf",
        logical_code=code,
        number=number,
        year=year,
        std_name=name,
        source_name=name,
        source_path=f"C:\\test\\{code}{number}-{year}.pdf",
    )
    p.effect_status = effect_status
    p.next_action = next_action
    p.found_replaces = found_replaces
    p.match_status = match_status
    return p


class TestPipelineRouter:
    @pytest.fixture
    def router(self):
        return PipelineRouter()

    # === 第一轮判断（扫描后） ===

    def test_cold_start_all_pending_goes_to_query(self, router):
        """冷启动：全部"待确认"→全部送查询"""
        items = [make_parsed(effect_status="待确认") for _ in range(5)]
        result = router.classify_after_scan(items)
        assert result["query"] == items
        assert result["archive"] == []
        assert result["fallback"] == []

    def test_hot_start_archive_skips_query(self, router):
        """热启动：缓存命中的已确认现行跳查询直通归档"""
        archive_item = make_parsed(effect_status="现行", next_action="archive")
        pending_item = make_parsed(effect_status="待确认")
        result = router.classify_after_scan([archive_item, pending_item])
        assert result["archive"] == [archive_item]
        assert result["query"] == [pending_item]

    def test_not_found_goes_to_fallback(self, router):
        """未识别的走兜底镜像"""
        nf = make_parsed(next_action="not_found", effect_status="")
        result = router.classify_after_scan([nf])
        assert result["fallback"] == [nf]
        assert result["query"] == []

    # === 第二轮判断（查询后） ===

    def test_after_query_current_goes_to_organize(self, router):
        """查询后现行→归档（文件名已符合规范格式）"""
        items = [make_parsed(effect_status="现行")]
        # 设置 source_path 使其与 make_standard_filename 输出匹配
        items[0].source_path = "C:\\test\\GB 19001-2020 测试标准.pdf"
        result = router.classify_after_query(items)
        assert result["organize"] == items
        assert result["normalize"] == []
        assert result["expire"] == []
        assert result["download"] == []

    def test_after_query_current_nonmatching_goes_to_normalize(self, router):
        """现行但文件名不符合规范→先重命名再归档"""
        items = [make_parsed(effect_status="现行")]
        # 默认 source_path 是 "C:\test\GB19001-2020.pdf"，不符合规范格式
        result = router.classify_after_query(items)
        assert result["normalize"] == items
        assert result["organize"] == []

    def test_after_query_expired_goes_to_expire(self, router):
        """查询后废止/作废→过期作废归档"""
        expired = make_parsed(effect_status="废止")
        abolished = make_parsed(effect_status="作废")
        result = router.classify_after_query([expired, abolished])
        assert result["expire"] == [expired, abolished]
        assert result["organize"] == []

    def test_after_query_has_new_version_goes_to_download(self, router):
        """查询后有替代标准→下载新版"""
        has_new = make_parsed(effect_status="被代替")
        has_new.found_replaces = "GB/T 19001-2026"
        result = router.classify_after_query([has_new])
        assert result["download"] == [has_new]

    def test_after_query_non_gb_with_replaces_goes_to_expire(self, router):
        """非国标（如 HG）有替代也应走 expire，因 gb688 无法下载"""
        non_gb = make_parsed(code="HG", effect_status="被代替", found_replaces="HG/T 1234-2026")
        result = router.classify_after_query([non_gb])
        assert result["expire"] == [non_gb]
        assert result["download"] == []

    def test_after_query_gb_with_replaces_goes_to_download(self, router):
        """国标+被代替+有替代 → 下载新版"""
        gb_replaced = make_parsed(code="GB/T", effect_status="被代替", found_replaces="GB/T 19001-2026")
        result = router.classify_after_query([gb_replaced])
        assert result["download"] == [gb_replaced]
        assert result["expire"] == []

    def test_after_query_not_found_goes_to_fallback(self, router):
        """查询后仍未查到→兜底镜像"""
        nf = make_parsed(effect_status="未查到", next_action="not_found")
        result = router.classify_after_query([nf])
        assert result["fallback"] == [nf]

    def test_after_query_mixed_buckets(self, router):
        """混合状态：各归各堆"""
        current = make_parsed(effect_status="现行")
        current.source_path = "C:\\test\\GB 19001-2020 测试标准.pdf"
        expired = make_parsed(effect_status="废止")
        pending = make_parsed(effect_status="待确认")
        nf = make_parsed(effect_status="")  # 空状态 → pending（与 manager 统一）
        result = router.classify_after_query([current, expired, pending, nf])
        assert result["organize"] == [current]
        assert result["expire"] == [expired]
        assert result["pending"] == [pending, nf]
        assert result["fallback"] == []

    # === apply_actions 合并方法 ===

    def test_apply_actions_sets_next_action(self, router):
        """apply_actions 分类并设置 next_action"""
        current = make_parsed(effect_status="现行")
        current.source_path = "C:\\test\\GB 19001-2020 测试标准.pdf"
        expired = make_parsed(effect_status="废止")
        pending = make_parsed(effect_status="待确认")
        nf = make_parsed(effect_status="")  # 空状态 → pending（与 manager 统一）
        items = [current, expired, pending, nf]
        buckets = router.apply_actions(items)
        assert current.next_action == "archive"
        assert expired.next_action == "expire"
        assert pending.next_action == "pending"
        assert nf.next_action == "pending"
        assert buckets["organize"] == [current]
        assert buckets["expire"] == [expired]
        assert buckets["pending"] == [pending, nf]
        assert buckets["fallback"] == []

    def test_apply_actions_normalize_sets_next_action(self, router):
        """现行但文件名不规范 → normalize → next_action='normalize'"""
        items = [make_parsed(effect_status="现行")]
        buckets = router.apply_actions(items)
        assert items[0].next_action == "normalize"
        assert buckets["normalize"] == items
        assert buckets["organize"] == []

    # === match_status 检查（与 manager 统一） ===

    def test_match_status_newer_gb_to_download(self, router):
        """match_status="newer" + GB → pending（规则0: 非exact统一pending，等重查）"""
        item = make_parsed(
            code="GB/T",
            number=19001,
            year=2016,
            effect_status="现行",
            match_status="newer",
        )
        result = router.classify_after_query([item])
        assert result["pending"] == [item]
        assert result["download"] == []

    def test_match_status_newer_gb_expired_to_download(self, router):
        """match_status="newer" + GB + 废止 → pending（规则0: 非exact统一pending，等重查）"""
        item = make_parsed(
            code="GB",
            number=12345,
            year=2010,
            effect_status="废止",
            match_status="newer",
        )
        result = router.classify_after_query([item])
        assert result["pending"] == [item]
        assert result["download"] == []

    def test_match_status_newer_non_gb_not_download(self, router):
        """match_status="newer" + 非GB → pending（规则0: 非exact统一pending）"""
        item = make_parsed(
            code="HG",
            number=1234,
            year=2018,
            effect_status="现行",
            match_status="newer",
        )
        result = router.classify_after_query([item])
        assert result["download"] == []
        assert result["pending"] == [item]

    def test_newer_exists_locally_skips_download(self, router):
        """match_status="newer" 新版已在本地 → pending（规则0: 非exact统一pending）"""
        old = make_parsed(
            code="GB",
            number=4053,
            year=2009,
            effect_status="现行",
            match_status="newer",
        )
        newer = make_parsed(
            code="GB",
            number=4053,
            year=2025,
            effect_status="即将实施",
            match_status="exact",
        )
        result = router.classify_after_query([old, newer])
        assert result["download"] == []
        assert result["pending"] == [old]

    def test_newer_exists_locally_same_code_diff_part(self, router):
        """同代号同序号但不同部分号 → pending（规则0: 非exact统一pending，不因部分号差异改变）"""
        old = make_parsed(
            code="GB",
            number=4053,
            year=2009,
            effect_status="现行",
            match_status="newer",
        )
        old.part = 1
        newer = make_parsed(
            code="GB",
            number=4053,
            year=2025,
            effect_status="即将实施",
            match_status="exact",
        )
        newer.part = 2
        result = router.classify_after_query([old, newer])
        assert result["pending"] == [old]  # 规则0: newer→pending
        assert result["download"] == []

    def test_newer_exists_locally_with_part_match(self, router):
        """同代号同序号同部分号 newer → pending（规则0）"""
        old = make_parsed(
            code="GB/T",
            number=47013,
            year=2015,
            effect_status="现行",
            match_status="newer",
        )
        old.part = 3
        newer = make_parsed(
            code="GB/T",
            number=47013,
            year=2023,
            effect_status="现行",
            match_status="exact",
        )
        newer.part = 3
        result = router.classify_after_query([old, newer])
        assert result["download"] == []
        assert result["pending"] == [old]

    def test_newer_exists_locally_is_static(self):
        """_newer_exists_locally 静态方法可直接调用"""
        old = make_parsed(code="GB", number=4053, year=2009)
        old.match_status = "newer"
        newer = make_parsed(code="GB", number=4053, year=2025)
        newer.match_status = "exact"
        # 只有 old 有 match_status="newer"，newer 有 exact
        assert PipelineRouter._newer_exists_locally(old, [old, newer]) is True
        # newer 是 exact，不是 newer，不应触发检查
        assert PipelineRouter._newer_exists_locally(newer, [old, newer]) is False
